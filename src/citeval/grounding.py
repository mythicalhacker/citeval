"""C2 — Resolution & grounding.

Given a cited identifier (PMID/DOI), fetch abstract + MeSH from NCBI efetch,
split organism vs population strictly by MeSH tree number (organism = tree B*,
age/population = tree M01.060*), and determine retraction status by cross-checking
the Retraction Watch registry against NCBI efetch PublicationType + CommentsCorrections.

Everything here is metadata-grounded. No model calls. Designed to be exposed as an
MCP server behind ground().
"""
from __future__ import annotations

import json
import os
import re
import time
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

_EMAIL = os.environ.get("NCBI_EMAIL", "citeval@example.org")
_TOOL = os.environ.get("NCBI_TOOL", "citeval")
_API_KEY = os.environ.get("NCBI_API_KEY", "")
_MIN_INTERVAL = 0.11 if _API_KEY else 0.34   # NCBI: 10/s with key, 3/s without
_last_call = [0.0]

SEX_DESCRIPTORS = {"Male", "Female"}


# --------------------------------------------------------------------------- net
def _throttle() -> None:
    dt = time.time() - _last_call[0]
    if dt < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - dt)
    _last_call[0] = time.time()


def _get(url: str, timeout: int = 30) -> bytes:
    _throttle()
    req = urllib.request.Request(url, headers={"User-Agent": f"{_TOOL} (mailto:{_EMAIL})"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def _eutils(endpoint: str, **params) -> bytes:
    params.setdefault("tool", _TOOL)
    params.setdefault("email", _EMAIL)
    if _API_KEY:
        params.setdefault("api_key", _API_KEY)
    return _get(f"{NCBI_BASE}/{endpoint}?{urllib.parse.urlencode(params)}")


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
def ground(identifier: CitedIdentifier) -> GroundedRecord:
    """Resolve + ground a cited paper into a fully metadata-grounded record."""
    errors: list[str] = []
    pmid = _resolve_to_pmid(identifier)
    parsed = _parse_pubmed_xml(_eutils("efetch.fcgi", db="pubmed", id=pmid, retmode="xml"))

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
        provenance={
            "abstract": "NCBI efetch db=pubmed <AbstractText>",
            "mesh": "NCBI efetch <DescriptorName> + NLM MeSH tree numbers (id.nlm.nih.gov)",
            "organism_population_split": "keyed on MeSH tree number (organism B*, population M01.060*)",
            "retraction": "Retraction Watch registry x-checked vs efetch PublicationType + CommentsCorrections",
        },
        grounding_errors=errors,
    )
