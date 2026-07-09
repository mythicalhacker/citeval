"""C1 — Ingestion & claim extraction.

Normalizes three input modes into a single ``list[ClaimUnit]`` so every downstream
component receives the same shape:

  a) ``{mode:"claim_pmid",    claim_text, cited_identifier}``      — passthrough
  b) ``{mode:"claim_citation", claim_text, citation_string}``     — resolve to an identifier
  c) ``{mode:"manuscript",     pmcid | jats_path | text}``        — extract (claim, cited_id) pairs

Grounded-and-measured discipline (enforced structurally, not by convention):

  * **Citation linkage is by JATS ``<pub-id>`` match**, never text proximity. A
    citing sentence binds to a cited paper only through the ``<xref rid>`` → ``<ref>``
    → ``<pub-id>`` chain.
  * **Raw JATS XML from NCBI EFetch (db=pmc)** — it preserves ``<xref>`` markers; the
    plain-text connector (which strips them) is never used.
  * **Verbatim guard:** an extracted ``atomic_claim`` is emitted only if it is a
    verbatim substring of the citing paper's whitespace-normalized ``<body>`` text.
  * **Compound citations split by distinct cited identifier, not by clause.** One
    sentence co-citing N distinct papers yields N ``ClaimUnit``s — each the full
    verbatim sentence bound to one cited id, with the co-cites recorded in
    ``citing_source``. ``ClaimUnit.cited_identifier`` is singular, and clause-level
    fragmentation would break the verbatim guard; semantic decomposition is a model
    (C3/C4) task, not deterministic ingestion.

The JATS extraction is a faithful port of ``src/reference/notebook_snippets.py``
(``efetch_pmc_xml_cached`` / ``find_rids_for_source`` / the citing-sentence extractor /
the verbatim guard / the safe display cleaner), re-pointed from lxml to the stdlib
``xml.etree.ElementTree`` to match ``grounding.py`` and avoid a new runtime dependency.
The reference snippet's ``host.mcp(...)`` calls are not reused here — its NCBI EFetch
call is already direct, so only the XML library and the cache path change.
"""
from __future__ import annotations

import html.entities as _htmlent
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from .contracts import CitedIdentifier, ClaimUnit

# --------------------------------------------------------------------------- config
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CROSSREF_BASE = "https://api.crossref.org/works"
# Cache raw JATS next to grounding.py's MeSH cache, under the package .cache/.
_CACHE_DIR = Path(__file__).resolve().parent / ".cache" / "pmc"

_EMAIL = os.environ.get("NCBI_EMAIL", "citeval@example.org")
_TOOL = os.environ.get("NCBI_TOOL", "citeval")
_API_KEY = os.environ.get("NCBI_API_KEY", "")
_MIN_INTERVAL = 0.11 if _API_KEY else 0.34   # NCBI: 10/s with key, 3/s without
_last_call = [0.0]

# DOI that opens a citation string (after any ``doi:`` / URL prefix is stripped). A
# free-text bibliographic reference does not start with ``10.`` and is routed to Crossref.
_DOI_RE = re.compile(r"10\.\d{4,9}/\S+", re.I)


# ----------------------------------------------------------------------------- net
def _throttle() -> None:
    dt = time.time() - _last_call[0]
    if dt < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - dt)
    _last_call[0] = time.time()


def _http_get(url: str, timeout: int = 60) -> bytes:
    """The single network seam (tests patch this). Polite User-Agent + NCBI throttle."""
    _throttle()
    req = urllib.request.Request(url, headers={"User-Agent": f"{_TOOL} (mailto:{_EMAIL})"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _eutils(endpoint: str, **params) -> bytes:
    params.setdefault("tool", _TOOL)
    params.setdefault("email", _EMAIL)
    if _API_KEY:
        params.setdefault("api_key", _API_KEY)
    return _http_get(f"{NCBI_BASE}/{endpoint}?{urllib.parse.urlencode(params)}")


# ------------------------------------------------------------------ mode b: resolve
def _extract_doi(citation_string: str) -> Optional[str]:
    """Return a DOI if the citation string *is* a DOI (bare, ``doi:``-prefixed, or a
    doi.org URL); otherwise None (a bibliographic reference → Crossref)."""
    s = re.sub(r"^\s*(?:doi:\s*|https?://(?:dx\.)?doi\.org/)", "", citation_string.strip(), flags=re.I)
    m = _DOI_RE.match(s)
    return m.group(0).rstrip(".,;") if m else None


def _doi_to_pmid(doi: str) -> Optional[str]:
    """DOI → PMID via NCBI esearch ``[AID]`` (same linkage grounding.py uses)."""
    raw = _eutils("esearch.fcgi", db="pubmed", term=f"{doi}[AID]", retmode="json")
    ids = json.loads(raw).get("esearchresult", {}).get("idlist", [])
    return ids[0] if ids else None


def _crossref_bibliographic(query: str) -> Optional[str]:
    """Free-text bibliographic reference → best-match DOI via Crossref REST."""
    url = f"{CROSSREF_BASE}?" + urllib.parse.urlencode(
        {"query.bibliographic": query, "rows": 1, "mailto": _EMAIL})
    items = json.loads(_http_get(url)).get("message", {}).get("items", [])
    return items[0].get("DOI") if items else None


def _resolve_citation_string(citation_string: str) -> tuple[CitedIdentifier, dict]:
    """Resolve a citation string to a cited identifier (PMID preferred, else DOI),
    returning the identifier plus a small resolution-provenance dict."""
    doi = _extract_doi(citation_string)
    resolver = "ncbi_aid"
    if doi is None:
        doi = _crossref_bibliographic(citation_string)
        resolver = "crossref->ncbi_aid"
    if doi is None:
        raise ValueError(f"could not resolve citation string to a DOI/PMID: {citation_string!r}")
    prov = {"resolved_from": citation_string, "resolver": resolver, "doi": doi}
    pmid = _doi_to_pmid(doi)
    if pmid:
        return CitedIdentifier("pmid", pmid), prov
    return CitedIdentifier("doi", doi.lower()), prov


# ------------------------------------------------------------- JATS (ported to ET)
# Sentinel inserted before each in-text bibr <xref>, encoding its rid so a sentence
# can report which references it cites. Sentinels contain NO whitespace, so removing
# them from a whitespace-normalized string leaves exactly ''.join(itertext()) — which
# is what keeps every extracted sentence a verbatim substring of the body.
_RID_TOKEN = re.compile("█RID:([^█]+)█")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _iter_main_refs(root):
    """Yield ``<ref>`` elements of the MAIN article, excluding any inside a
    ``<sub-article>`` or ``<response>`` (peer-review / author-response matter). Those
    carry their own per-article rid space (B1, B2, …) that can collide with the main
    article's, and the citing ``<body>`` we read is always the main one — so binding
    must come only from the main article's reference list. (Hardening over the raw
    reference, which scanned every ``<ref>`` in the document.)"""
    blocked: set = set()
    for container in ("sub-article", "response"):
        for sub in root.iter(container):
            blocked.update(sub.iter())
    for ref in root.iter("ref"):
        if ref not in blocked:
            yield ref


def find_rids_for_source(root, target_pmid: Optional[str] = None,
                         target_doi: Optional[str] = None) -> set:
    """Faithful port (main-article scoped): cited PMID/DOI → set of ``<ref id=...>``
    rids, matched on ``<pub-id>`` (metadata-grounded linkage, never text proximity)."""
    ids: set = set()
    tdoi = (target_doi or "").lower().strip()
    for ref in _iter_main_refs(root):
        rid = ref.get("id")
        if not rid:
            continue
        pmids = [(e.text or "").strip() for e in ref.iter("pub-id") if e.get("pub-id-type") == "pmid"]
        dois = [(e.text or "").strip().lower() for e in ref.iter("pub-id") if e.get("pub-id-type") == "doi"]
        if target_pmid and target_pmid in pmids:
            ids.add(rid)
        elif tdoi and tdoi in dois:
            ids.add(rid)
    return ids


def _ref_identifiers(root) -> dict:
    """rid → CitedIdentifier for every ``<ref>`` carrying a resolvable ``<pub-id>``
    (PMID preferred, else DOI). The inverse of find_rids_for_source, for enumerating
    all cited papers in a manuscript. Refs without a pub-id are omitted (unbindable)."""
    out: dict = {}
    for ref in _iter_main_refs(root):
        rid = ref.get("id")
        if not rid:
            continue
        pmid = next(((e.text or "").strip() for e in ref.iter("pub-id")
                     if e.get("pub-id-type") == "pmid" and (e.text or "").strip()), None)
        doi = next(((e.text or "").strip() for e in ref.iter("pub-id")
                    if e.get("pub-id-type") == "doi" and (e.text or "").strip()), None)
        if pmid:
            out[rid] = CitedIdentifier("pmid", pmid)
        elif doi:
            out[rid] = CitedIdentifier("doi", doi.lower())
    return out


def _render_marked(el) -> str:
    """Serialize a ``<p>`` inserting a rid sentinel before each bibr ``<xref>``'s label.
    Stripping the sentinels reproduces ``''.join(el.itertext())`` for this paragraph,
    EXCLUDING any nested ``<p>`` subtree — a nested ``<p>`` (fig caption, list-item,
    disp-quote) is its own paragraph and is emitted on its own ``body.iter('p')`` pass,
    so rendering it here too would double-count it. The bibr branch appends the xref's
    full ``itertext()`` (not just ``.text``) so a marked-up label like ``<sup>24</sup>``
    still matches the body text and the sentence is not dropped by the verbatim guard."""
    s = el.text or ""
    for c in el:
        if c.tag == "xref" and c.get("ref-type") == "bibr":
            for rid in (c.get("rid") or "").split():
                s += f"█RID:{rid}█"
            s += "".join(c.itertext())
        elif c.tag == "p":
            pass                     # nested paragraph — rendered on its own iteration
        else:
            s += _render_marked(c)
        s += (c.tail or "")
    return s


# A period that closes one of these tokens is an abbreviation, not a sentence boundary —
# without this guard the splitter breaks "…in mice Fig. 2 …" or "…, e.g. The compound…"
# and stores a truncated, meaning-changed fragment (dropping e.g. the species qualifier).
_ABBREV_TAIL = re.compile(
    r"(?:^|[\s(\[])(?:figs?|tabs?|eqs?|refs?|nos?|vs|cf|al|drs?|profs?|mrs?|ms|st|approx"
    r"|ca|pp|p|vols?|secs?|etc|chaps?|ch|e\.g|i\.e|resp|inc|ltd|co)\.$", re.I)


def _dangling_abbrev(piece: str) -> bool:
    return bool(_ABBREV_TAIL.search(_RID_TOKEN.sub("", piece).rstrip()))


def _split_sentences(marked: str) -> list[str]:
    """Split on sentence boundaries, re-joining a split that fell after a known
    abbreviation (the naive regex is the ported reference's; the merge is the fix)."""
    merged: list[str] = []
    for piece in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])", marked):
        if merged and _dangling_abbrev(merged[-1]):
            merged[-1] = f"{merged[-1]} {piece}"
        else:
            merged.append(piece)
    return merged


def _citing_sentences(root) -> list[tuple[str, list[str]]]:
    """Every sentence in the main ``<body>`` that carries ≥1 bibr citation, as
    ``(verbatim_sentence, [rid, ...])``. Sentinels are stripped and the text is
    re-normalized (not just end-stripped), so each sentence is a literal substring of the
    whitespace-normalized body even when an empty ``<xref/>`` leaves adjacent spaces."""
    out: list[tuple[str, list[str]]] = []
    body = root.find(".//body")
    if body is None:
        return out
    for p in body.iter("p"):
        if not any(c.get("ref-type") == "bibr" for c in p.iter("xref")):
            continue
        for ms in _split_sentences(_norm(_render_marked(p))):
            rids = _RID_TOKEN.findall(ms)
            if not rids:
                continue
            out.append((_norm(_RID_TOKEN.sub("", ms)), rids))
    return out


def verbatim_ok(claim: str, body_text: str) -> bool:
    """The fabrication guard: the (normalized) claim must be a substring of the
    (already normalized) citing-body text. ``body_text`` comes from body_text_of()."""
    return _norm(claim) in body_text


def body_text_of(root) -> str:
    """Whitespace-normalized ``<body>`` full text — the verbatim-guard denominator."""
    body = root.find(".//body")
    return _norm("".join(body.itertext())) if body is not None else ""


def clean_display(s: str) -> str:
    """Safe display cleaner (port of the notebook's SAFE variant): strip ONLY bracketed
    or parenthetical numeric citation markers. Never touches word-glued digits, so gene
    names like NUF2 are preserved. Used for citing_source['display'] only — the stored
    atomic_claim stays verbatim."""
    s = re.sub(r"\s*\[[\d,\s–-]+\]", "", s)        # [50], [1,2], [1-3]
    s = re.sub(r"\s*\((?:\d+[,\s–-]*)+\)", "", s)  # (97), (1, 2)
    return re.sub(r"\s+", " ", s).strip()


# -------------------------------------------------------------------- JATS fetch
# Named character entities (&beta;, &mdash;, &micro; …) are ubiquitous in publisher /
# PMC-OA JATS but undefined to stdlib ET (it does not fetch the external DTD), so
# ET.fromstring raises ParseError. Rewrite the ones stdlib knows to numeric refs before
# parsing. Entity names/numeric refs are pure ASCII, so this is encoding-safe on bytes.
# (NCBI EFetch itself returns literal UTF-8, so the acceptance/pmcid path never hits this.)
_ENTITY_RE = re.compile(rb"&([A-Za-z][A-Za-z0-9]*);")
_XML_BUILTIN_ENTITIES = {b"amp", b"lt", b"gt", b"quot", b"apos"}


def _resolve_named_entities(raw: bytes) -> bytes:
    def repl(m):
        name = m.group(1)
        if name in _XML_BUILTIN_ENTITIES:
            return m.group(0)
        cp = _htmlent.name2codepoint.get(name.decode("ascii"))
        return f"&#{cp};".encode("ascii") if cp is not None else m.group(0)
    return _ENTITY_RE.sub(repl, raw)


def efetch_pmc_xml_cached(pmcid: str) -> bytes:
    """Raw PMC JATS XML via NCBI EFetch ``db=pmc`` (preserves ``<xref>``), cached under
    ``.cache/pmc/``. Ported from notebook_snippets; the EFetch call is already direct
    NCBI, so only the cache path and the shared throttle/UA change."""
    num = str(pmcid).replace("PMC", "")
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fp = _CACHE_DIR / f"{num}.xml"
    if fp.exists():
        return fp.read_bytes()
    data = _eutils("efetch.fcgi", db="pmc", id=num, rettype="xml", retmode="xml")
    fp.write_bytes(data)
    return data


def _load_jats_root(req: dict):
    """Parse a JATS root from raw ``text``, a ``jats_path`` file, or a fetched ``pmcid``."""
    if req.get("text") is not None:
        raw = req["text"]
        raw = raw.encode("utf-8") if isinstance(raw, str) else raw
    elif req.get("jats_path") is not None:
        raw = Path(req["jats_path"]).read_bytes()
    elif req.get("pmcid") is not None:
        raw = efetch_pmc_xml_cached(req["pmcid"])
    else:
        raise ValueError("manuscript mode requires one of: pmcid, jats_path, text")
    try:
        return ET.fromstring(_resolve_named_entities(raw))
    except ET.ParseError as e:
        raise ValueError(f"could not parse JATS XML: {e}") from e


# --------------------------------------------------------------------- extraction
def _extract_units(root, source: dict) -> list[ClaimUnit]:
    """Walk every pub-id-bound citing sentence; emit one ClaimUnit per distinct cited
    identifier. Sentences failing the verbatim guard, or citing only unbindable refs,
    are dropped."""
    rid_to_id = _ref_identifiers(root)
    body = body_text_of(root)
    units: list[ClaimUnit] = []
    for sentence, rids in _citing_sentences(root):
        # Distinct cited identifiers this sentence references (dedup by type+value,
        # first-seen order; a sentence may repeat or co-cite refs).
        idents: list[tuple[str, CitedIdentifier]] = []
        seen: set = set()
        for rid in rids:
            ci = rid_to_id.get(rid)
            if ci is None:
                continue                      # ref has no pub-id → cannot bind
            key = (ci.type, ci.value)
            if key not in seen:
                seen.add(key)
                idents.append((rid, ci))
        if not idents:
            continue                          # citations present but none bindable
        if not verbatim_ok(sentence, body):   # mandatory fabrication guard
            continue
        co_cited = [{"type": ci.type, "value": ci.value} for _, ci in idents]
        display = clean_display(sentence)
        for rid, ci in idents:
            units.append(ClaimUnit(
                atomic_claim=sentence,
                cited_identifier=ci,
                citing_source={**source, "rid": rid, "co_cited": co_cited, "display": display},
            ))
    return units


# -------------------------------------------------------------------------- modes
def _normalize_identifier(ci) -> CitedIdentifier:
    if isinstance(ci, CitedIdentifier):
        return ci
    if isinstance(ci, dict):
        return CitedIdentifier(type=ci["type"], value=str(ci["value"]))
    raise TypeError(f"cited_identifier must be CitedIdentifier or dict, got {type(ci).__name__}")


def _ingest_claim_pmid(req: dict) -> list[ClaimUnit]:
    """Mode a — passthrough. The claim is caller-supplied (no citing body to guard against)."""
    return [ClaimUnit(atomic_claim=req["claim_text"],
                      cited_identifier=_normalize_identifier(req["cited_identifier"]),
                      citing_source=None)]


def _ingest_claim_citation(req: dict) -> list[ClaimUnit]:
    """Mode b — resolve the citation string, keep the caller-supplied claim text."""
    ident, prov = _resolve_citation_string(req["citation_string"])
    return [ClaimUnit(atomic_claim=req["claim_text"], cited_identifier=ident, citing_source=prov)]


def _ingest_manuscript(req: dict) -> list[ClaimUnit]:
    """Mode c — extract (claim, cited_id) pairs from a citing paper's JATS."""
    root = _load_jats_root(req)
    source: dict = {"mode": "manuscript"}
    if req.get("pmcid"):
        source["pmcid"] = str(req["pmcid"])
        source["source"] = "jats_efetch"
    elif req.get("jats_path"):
        source["jats_path"] = str(req["jats_path"])
        source["source"] = "jats_path"
    else:
        source["source"] = "jats_text"
    return _extract_units(root, source)


_MODES = {
    "claim_pmid": _ingest_claim_pmid,
    "claim_citation": _ingest_claim_citation,
    "manuscript": _ingest_manuscript,
}


def ingest(request: dict) -> list[ClaimUnit]:
    """Normalize any of the three input modes into a ``list[ClaimUnit]``."""
    mode = request.get("mode")
    if mode not in _MODES:
        raise ValueError(f"unknown ingest mode {mode!r}; expected one of {sorted(_MODES)}")
    return _MODES[mode](request)
