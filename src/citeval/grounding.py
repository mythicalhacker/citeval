"""C2 — Resolution & grounding.

Given a cited identifier (PMID/DOI), fetch abstract + MeSH from NCBI efetch,
split organism vs population strictly by MeSH tree number (organism = tree B*,
age/population = tree M01.060*), and determine retraction status by cross-checking
the Retraction Watch registry against NCBI efetch PublicationType + CommentsCorrections.

Everything here is metadata-grounded. No model calls. Designed to be exposed as an
MCP server behind ground().
"""
from __future__ import annotations

import http.client
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from .contracts import (
    CitedIdentifier, CommentsCorrection, GroundedRecord, MeshTag,
    RetractionInfo, RetractionWatchHit,
)

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_DATA_DIR = Path(__file__).resolve().parent / "data"
_CACHE_DIR = Path(__file__).resolve().parent / ".cache"
_MESH_CACHE = _CACHE_DIR / "mesh_tree.json"
_EFETCH_DIR = _CACHE_DIR / "efetch_pubmed"   # cached raw efetch db=pubmed XML (rerun/scale speed)
_EFETCH_PMC_DIR = _CACHE_DIR / "efetch_pmc"  # cached raw efetch db=pmc JATS XML, per PMID (full text)
_PMC_IDCONV = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"

_EMAIL = os.environ.get("NCBI_EMAIL", "citeval@example.org")
_TOOL = os.environ.get("NCBI_TOOL", "citeval")
_API_KEY = os.environ.get("NCBI_API_KEY", "")
_MIN_INTERVAL = 0.11 if _API_KEY else 0.34   # NCBI: 10/s with key, 3/s without
_last_call = [0.0]

SEX_DESCRIPTORS = {"Male", "Female"}

# Full-text evidence budget (WO-C4 full-text grounding §3): ~6000 tokens ≈ 24k chars. The budgeted
# text is BOTH what the adjudicator feeds the triad AND what the verbatim guard uses as an extra
# grounded segment, so it is bounded to keep the (full-text × 7 rounds × 3 agents) cost in check.
FULLTEXT_BUDGET_CHARS = 24000
_PRIORITY_SECTIONS = ("result", "discussion", "conclusion")   # prefer these body sections
_DROP_TAGS = frozenset({"ref-list"})                          # drop the reference list (§3)
# Block-level JATS elements get a separating space appended so a <title> does not glue onto the
# following <p> ("RESULTSThe..."). Inline elements (sub, sup, italic, xref, …) are deliberately
# EXCLUDED so word-glued markup is preserved verbatim (e.g. NUF<sub>2</sub> → "NUF2", not "NUF 2";
# the notebook's clean_display note flags exactly this gene-name corruption).
_BLOCK_TAGS = frozenset({"sec", "title", "p", "label", "list", "list-item", "caption", "abstract",
                         "table-wrap", "fig", "body", "disp-quote", "def-list", "def-item", "term"})
_WS = re.compile(r"\s+")


def _ws_norm(s: str) -> str:
    """Whitespace-normalize (notebook BLOCK 3 `norm`)."""
    return _WS.sub(" ", s or "").strip()


# --------------------------------------------------------------------------- net
def _throttle() -> None:
    dt = time.time() - _last_call[0]
    if dt < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - dt)
    _last_call[0] = time.time()


# A single NCBI blip must not abort a long corpus run (WO-C4 resilience §1). EFetch/id-converter
# fetches occasionally fail transiently — a truncated read (http.client.IncompleteRead), a dropped
# or timed-out connection (urllib.error.URLError / socket.timeout / ConnectionError), or a transient
# server/rate-limit HTTP status. `_get` retries those with exponential backoff (1s, 2s, 4s), and
# re-raises only after the final attempt. A non-transient HTTP status (e.g. 404) fails FAST — a
# retry cannot fix it. Because `_get` backs `_eutils`, this covers EFetch pubmed, EFetch pmc, and
# the PMC id-converter (`_resolve_pmcid`) uniformly.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503})
_FETCH_ATTEMPTS = 4
_BACKOFF_BASE_S = 1.0


def _get(url: str, timeout: int = 30, *, attempts: int = _FETCH_ATTEMPTS,
         backoff_base: float = _BACKOFF_BASE_S) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": f"{_TOOL} (mailto:{_EMAIL})"})
    last_exc: Exception = RuntimeError("no fetch attempt made")   # replaced on first failure
    for attempt in range(attempts):
        _throttle()
        try:
            return urllib.request.urlopen(req, timeout=timeout).read()
        except urllib.error.HTTPError as e:
            if e.code not in _RETRYABLE_STATUS:
                raise                       # 4xx (e.g. 404) — not transient, do not retry
            last_exc = e
        except (urllib.error.URLError, socket.timeout, http.client.IncompleteRead,
                ConnectionError) as e:
            last_exc = e                    # dropped / incomplete / timed-out read — retry
        if attempt + 1 < attempts:
            time.sleep(backoff_base * (2 ** attempt))   # 1s, 2s, 4s
    raise last_exc                          # every attempt failed transiently — surface the last


def _eutils(endpoint: str, **params) -> bytes:
    params.setdefault("tool", _TOOL)
    params.setdefault("email", _EMAIL)
    if _API_KEY:
        params.setdefault("api_key", _API_KEY)
    return _get(f"{NCBI_BASE}/{endpoint}?{urllib.parse.urlencode(params)}")


def _efetch_pubmed_cached(pmid: str) -> bytes:
    """Raw efetch db=pubmed XML, disk-cached by PMID so re-scoring a corpus is fast.
    Same bytes as a live fetch — additive caching, no behavior change."""
    _EFETCH_DIR.mkdir(parents=True, exist_ok=True)
    fp = _EFETCH_DIR / f"{pmid}.xml"
    if fp.exists():
        return fp.read_bytes()
    data = _eutils("efetch.fcgi", db="pubmed", id=pmid, retmode="xml")
    fp.write_bytes(data)
    return data


# ------------------------------------------------------- full text (PMC JATS, invariant #6)
# Raw JATS from EFetch db=pmc, never a plain-text connector (invariant #6). This ports the
# reusable extraction of src/reference/notebook_snippets.py — BLOCK 1 `efetch_pmc_xml` (the
# only direct-E-utilities full-text call there) and BLOCK 3 `body_text` (drop the reference
# list, whitespace-normalize <body>) — to stdlib xml.etree so we add NO lxml dependency
# (CLAUDE.md: no new deps beyond the Anthropic SDK). PMC EFetch JATS is unnamespaced.
def _resolve_pmcid(pmid: str) -> str | None:
    """PMID → PMCID via the NCBI PMC ID Converter (notebook BLOCK 6 `to_pmc`, re-pointed to the
    documented REST endpoint). Returns 'PMC…' or None when the article is not in PMC. Swallows
    network/parse errors (→ None) so a full-text attempt never breaks grounding."""
    url = _PMC_IDCONV + "?" + urllib.parse.urlencode(
        {"ids": str(pmid), "format": "json", "tool": _TOOL, "email": _EMAIL})
    try:
        recs = json.loads(_get(url)).get("records", [])
    except Exception:
        return None
    for r in recs:
        if str(r.get("pmid")) == str(pmid) and r.get("pmcid"):
            return r["pmcid"]
    for r in recs:                      # fallback: any record carrying a PMCID
        if r.get("pmcid"):
            return r["pmcid"]
    return None


def _efetch_pmc_cached(pmid: str) -> bytes | None:
    """Raw PMC JATS XML for a PMID, disk-cached by PMID (mirrors `_efetch_pubmed_cached`).
    Resolves PMID→PMCID first; caches SUCCESSFUL fetches ONLY — a network failure or a
    not-in-PMC PMID is never cached, so it retries next run. Returns None when not in PMC."""
    _EFETCH_PMC_DIR.mkdir(parents=True, exist_ok=True)
    fp = _EFETCH_PMC_DIR / f"{pmid}.xml"
    if fp.exists():
        return fp.read_bytes()
    pmcid = _resolve_pmcid(pmid)
    if not pmcid:
        return None
    data = _eutils("efetch.fcgi", db="pmc", id=str(pmcid).replace("PMC", ""), retmode="xml")
    fp.write_bytes(data)                # reached only on a successful fetch (else _eutils raised)
    return data


def _localname(tag) -> str:
    return tag.rsplit("}", 1)[1] if isinstance(tag, str) and "}" in tag else (tag or "")


def _element_text_skip(el) -> str:
    """`itertext()` minus <ref-list> subtrees (notebook BLOCK 3 `body_text`, which drops the
    reference list). Namespace-agnostic on the tag localname (PMC EFetch JATS is unnamespaced,
    but strip defensively)."""
    parts: list[str] = []

    def walk(e) -> None:
        if _localname(e.tag) in _DROP_TAGS:
            return
        if e.text:
            parts.append(e.text)
        for child in e:
            walk(child)
            if _localname(child.tag) in _BLOCK_TAGS:
                parts.append(" ")          # separate block elements; inline markup stays glued
            if child.tail:
                parts.append(child.tail)

    walk(el)
    return _ws_norm("".join(parts))


def _jats_body_sections(root) -> tuple[str, list[tuple[str, str]]]:
    """(body_fulltext, [(section_title, section_text), ...]) from a parsed PMC JATS tree.
    `body_fulltext` is the whole <body> minus the reference list; sections are the top-level
    <sec> blocks. ('' , []) when there is no <body> — an abstract-only PMC record → honest empty."""
    body = root.find(".//body")
    if body is None:
        return "", []
    sections: list[tuple[str, str]] = []
    for sec in body.findall("./sec"):
        title_el = sec.find("./title")
        title = _ws_norm("".join(title_el.itertext())) if title_el is not None else ""
        sections.append((title, _element_text_skip(sec)))
    return _element_text_skip(body), sections


def _pmcid_from_xml(root) -> str:
    for aid in root.iter("article-id"):
        if aid.get("pub-id-type") in ("pmc", "pmcid"):
            v = (aid.text or "").strip()
            if v:
                return v if v.upper().startswith("PMC") else f"PMC{v}"
    return ""


def select_budgeted_fulltext(sections: list[tuple[str, str]], body_fulltext: str,
                             abstract: str, budget: int = FULLTEXT_BUDGET_CHARS) -> str:
    """Budgeted full-text selection (WO-C4 full-text grounding §3).

    Strategy: always PREPEND the abstract, then prefer the Results + Discussion + Conclusions
    body sections (in that priority order); the reference list is already dropped upstream. Fall
    back to leading body text when the sections are not the parseable IMRaD shape (e.g. a body
    with no standard <sec> titles). Truncated to `budget` chars (~6000 tokens). Deterministic."""
    parts: list[str] = []
    used = 0

    def _add(text: str) -> None:
        nonlocal used
        text = _ws_norm(text)
        if not text or used >= budget:
            return
        chunk = text[: budget - used]
        parts.append(chunk)
        used += len(chunk) + 2          # +2 accounts for the "\n\n" joiner

    _add(abstract)                      # abstract always first
    chosen: set[int] = set()
    picked = False
    for kw in _PRIORITY_SECTIONS:
        for i, (title, text) in enumerate(sections):
            if i in chosen:
                continue
            if kw in title.lower():
                _add(text)
                chosen.add(i)
                picked = True
    if not picked:
        _add(body_fulltext)             # fallback: leading body text (non-IMRaD / unparseable secs)
    return "\n\n".join(p for p in parts if p).strip()


def fetch_full_text(pmid: str, abstract: str, errors: list[str] | None = None) -> tuple[str, str]:
    """Best-effort budgeted full text for a PMID + its provenance ('pmc-jats:PMC…' or '').

    Never raises and never fabricates: any failure (not in PMC, network error, unparseable XML,
    no <body>) yields ('', '') — the honest empty value. Successful raw PMC XML is disk-cached."""
    try:
        xml = _efetch_pmc_cached(pmid)
    except Exception as e:              # noqa: BLE001 — full text is best-effort; degrade to empty
        if errors is not None:
            errors.append(f"full_text fetch failed: {e}")
        return "", ""
    if not xml:
        return "", ""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        if errors is not None:
            errors.append(f"full_text parse failed: {e}")
        return "", ""
    body_fulltext, sections = _jats_body_sections(root)
    if not body_fulltext:
        return "", ""                   # abstract-only PMC record → honest empty full text
    budgeted = select_budgeted_fulltext(sections, body_fulltext, abstract)
    if not budgeted:
        return "", ""
    pmcid = _pmcid_from_xml(root)
    return budgeted, (f"pmc-jats:{pmcid}" if pmcid else "pmc-jats")


# ---------------------------------------------------------------------- MeSH tree
def _load_mesh_cache() -> dict:
    if _MESH_CACHE.exists():
        try:
            return json.loads(_MESH_CACHE.read_text())
        except Exception:
            return {}
    return {}


def _save_mesh_cache(cache: dict) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _MESH_CACHE.write_text(json.dumps(cache))


_mesh_cache = _load_mesh_cache()


# Authoritative MeSH tree numbers come from NCBI efetch db=mesh (reliable and
# batchable), NOT id.nlm.nih.gov JSON-LD (representation-dependent + rate-degrades).
# Valid MeSH tree roots are A-N, V, Z.
_TREE_RE = re.compile(r"[A-NVZ]\d{2}(?:\.\d{3})*")


def _parse_trees(record: str) -> list[str]:
    m = re.search(r"Tree Number\(s\):\s*(.+)", record)
    return sorted(set(_TREE_RE.findall(m.group(1)))) if m else []


def _mesh_uid(ui: str) -> str | None:
    """MeSH descriptor UI (D######) -> E-utilities numeric UID (68######)."""
    return "68" + ui[1:] if ui.startswith("D") and ui[1:].isdigit() else None


def _prefetch_trees(uis: list[str]) -> None:
    """Fill the tree-number cache for all missing UIs in ONE efetch db=mesh call.
    Only successful lookups are cached; failures are left uncached so they retry
    next run (never poison the cache with an empty-on-error)."""
    missing = [u for u in dict.fromkeys(uis) if u and u not in _mesh_cache and _mesh_uid(u)]
    if not missing:
        return
    uid_list = [_mesh_uid(u) for u in missing]
    try:
        txt = _eutils("efetch.fcgi", db="mesh", id=",".join(uid_list),
                      retmode="text").decode("utf-8", "ignore")
    except Exception:
        return
    by_idx: dict[int, str] = {}
    for ch in re.split(r"\n(?=\d+:\s)", txt.strip()):
        m = re.match(r"(\d+):", ch)
        if m:
            by_idx[int(m.group(1))] = ch
    updated = False
    for i, u in enumerate(missing, start=1):     # efetch preserves input order
        ch = by_idx.get(i)
        if ch is not None:
            _mesh_cache[u] = _parse_trees(ch)
            updated = True
    if updated:
        _save_mesh_cache(_mesh_cache)


def _tree_numbers(ui: str) -> list[str]:
    return _mesh_cache.get(ui, [])


def _classify(tree_numbers: list[str], descriptor: str) -> str:
    """organism | population | sex | other, keyed on tree number where possible."""
    if any(t.startswith("B") for t in tree_numbers):
        return "organism"
    if any(t.startswith("M01.060") for t in tree_numbers):
        return "population"
    if descriptor in SEX_DESCRIPTORS:
        return "sex"
    return "other"


# ------------------------------------------------------------------- efetch parse
def _text(elem) -> str:
    return "".join(elem.itertext()).strip() if elem is not None else ""


def _resolve_to_pmid(identifier: CitedIdentifier) -> str:
    if identifier.type == "pmid":
        return identifier.value.strip()
    # DOI -> PMID via esearch
    raw = _eutils("esearch.fcgi", db="pubmed", term=f"{identifier.value}[AID]", retmode="json")
    ids = json.loads(raw).get("esearchresult", {}).get("idlist", [])
    if not ids:
        raise ValueError(f"Could not resolve DOI to PMID: {identifier.value}")
    return ids[0]


def _parse_pubmed_xml(xml_bytes: bytes) -> dict:
    root = ET.fromstring(xml_bytes)
    art = root.find(".//PubmedArticle")
    if art is None:
        raise ValueError("No PubmedArticle in efetch response")
    title = _text(art.find(".//ArticleTitle"))
    # abstract (may be multi-section)
    parts = []
    for ab in art.findall(".//Abstract/AbstractText"):
        label = ab.get("Label")
        t = _text(ab)
        parts.append(f"{label}: {t}" if label else t)
    abstract = "\n".join(p for p in parts if p)
    # mesh
    mesh = []
    for mh in art.findall(".//MeshHeadingList/MeshHeading"):
        d = mh.find("DescriptorName")
        if d is not None:
            mesh.append({
                "ui": d.get("UI", ""),
                "descriptor": _text(d),
                "major": d.get("MajorTopicYN", "N") == "Y",
            })
    pub_types = [_text(p) for p in art.findall(".//PublicationTypeList/PublicationType")]
    ccs = []
    for cc in art.findall(".//CommentsCorrectionsList/CommentsCorrections"):
        pmid_el = cc.find("PMID")
        ccs.append({
            "ref_type": cc.get("RefType", ""),
            "pmid": _text(pmid_el) if pmid_el is not None else None,
            "source": _text(cc.find("RefSource")),
        })
    return {"title": title, "abstract": abstract, "mesh": mesh,
            "pub_types": pub_types, "comments_corrections": ccs}


# --------------------------------------------------------------------- retraction
def _load_rw() -> tuple[dict, dict]:
    def _load(name):
        p = _DATA_DIR / name
        return json.loads(p.read_text()) if p.exists() else {}
    return _load("rw_index_pmid.json"), _load("rw_index_doi.json")


_rw_pmid, _rw_doi = _load_rw()


def _retraction(pmid: str, doi: str, parsed: dict) -> RetractionInfo:
    # Source 1: Retraction Watch registry (primary; carries reason + date)
    rw_rec = _rw_pmid.get(pmid) or (_rw_doi.get(doi.lower()) if doi else None)
    rw = RetractionWatchHit(present=bool(rw_rec))
    if rw_rec:
        rw.rw_record_id = rw_rec.get("rw_record_id")
        rw.reason = rw_rec.get("reason")
        rw.date = rw_rec.get("date")
    # Source 2: NCBI efetch
    pt_flag = "Retracted Publication" in parsed["pub_types"]
    ref_types = {c["ref_type"] for c in parsed["comments_corrections"]}
    ncbi_retracted = pt_flag or ("RetractionIn" in ref_types)
    ncbi_eoc = "ExpressionOfConcernIn" in ref_types
    ccs = [CommentsCorrection(**{k: c[k] for k in ("ref_type", "pmid", "source")})
           for c in parsed["comments_corrections"]
           if c["ref_type"] in ("RetractionIn", "ExpressionOfConcernIn")]
    # Combine
    if rw.present or ncbi_retracted:
        status = "RETRACTED"
    elif ncbi_eoc:
        status = "EXPRESSION_OF_CONCERN"
    else:
        status = "NONE_FOUND"
    if rw.present and ncbi_retracted:
        agreement = "agree"
    elif rw.present:
        agreement = "rw_only"
    elif ncbi_retracted or ncbi_eoc:
        agreement = "ncbi_only"
    else:
        agreement = "none"
    return RetractionInfo(status=status, retraction_watch=rw,
                          ncbi_publication_type_flag=pt_flag,
                          comments_corrections=ccs, source_agreement=agreement)


# --------------------------------------------------------------------------- main
def ground(identifier: CitedIdentifier, *, with_full_text: bool = True) -> GroundedRecord:
    """Resolve + ground a cited paper into a fully metadata-grounded record.

    When `with_full_text` is True (default) the cited paper's budgeted PMC full text is attached
    (invariant #6: raw JATS from EFetch db=pmc, never a plain-text connector); it degrades to the
    honest empty value when unavailable. Callers that never consume the full text (the offline
    stub path) pass `with_full_text=False` to skip the extra PMC round-trip entirely."""
    errors: list[str] = []
    pmid = _resolve_to_pmid(identifier)
    parsed = _parse_pubmed_xml(_efetch_pubmed_cached(pmid))

    _prefetch_trees([m["ui"] for m in parsed["mesh"]])   # one batched db=mesh call
    organism, population, sex = [], [], []
    for m in parsed["mesh"]:
        trees = _tree_numbers(m["ui"])
        tag = MeshTag(descriptor=m["descriptor"], ui=m["ui"],
                      tree_numbers=trees, major_topic=m["major"])
        bucket = _classify(trees, m["descriptor"])
        if bucket == "organism":
            organism.append(tag)
        elif bucket == "population":
            population.append(tag)
        elif bucket == "sex":
            sex.append(tag)

    # DOI for RW cross-lookup
    doi = identifier.value if identifier.type == "doi" else ""
    retraction = _retraction(pmid, doi, parsed)
    has_humans = any(t.descriptor == "Humans" for t in organism)

    # Full text (best-effort; invariant #6). Failure/unavailable → empty (never fabricated).
    full_text, full_text_provenance = (
        fetch_full_text(pmid, parsed["abstract"], errors) if with_full_text else ("", ""))

    provenance = {
        "abstract": "NCBI efetch db=pubmed <AbstractText>",
        "mesh": "NCBI efetch <DescriptorName> + NLM MeSH tree numbers (id.nlm.nih.gov)",
        "organism_population_split": "keyed on MeSH tree number (organism B*, population M01.060*)",
        "retraction": "Retraction Watch registry x-checked vs efetch PublicationType + CommentsCorrections",
    }
    if full_text:
        provenance["full_text"] = ("NCBI efetch db=pmc raw JATS <body> (budgeted: abstract + "
                                   "Results/Discussion/Conclusions, reference list dropped) — invariant #6")

    return GroundedRecord(
        identifier=CitedIdentifier(type="pmid", value=pmid),
        title=parsed["title"],
        abstract=parsed["abstract"],
        mesh_all=[m["descriptor"] for m in parsed["mesh"]],
        organism_tags=organism,
        population_tags=population,
        sex_tags=sex,
        publication_types=parsed["pub_types"],
        retraction=retraction,
        has_humans=has_humans,
        provenance=provenance,
        grounding_errors=errors,
        full_text=full_text,
        full_text_provenance=full_text_provenance,
    )
