"""
Reference transcription of the reusable grounding + extraction code from the prior
Claude Science notebook (Claude_Sciences_Notebook_Extraction.txt). Line-number prefixes
stripped; otherwise faithful (NOT a rewrite). This file is documentation, not required
to run.

PROVENANCE / SCOPE
  - The notebook is conversation 2 (eval-set / corpus assembly). It contains the full
    EXTRACTION pipeline but NO grounding routine. There is no `ground_pmid`, no MeSH
    tree-number logic, and no efetch/CommentsCorrections retraction code in the source
    (grep-confirmed). The grounding routine survives only as output schema
    (repo: grounded.json / verdict.json) and prose (Claude_Science_Extraction.txt).
    See design/02_source_code_inventory.md.

TWO RUNTIMES
  - `host.mcp(...)`, `host.llm(...)`, `host.credentials` = Claude Science connector runtime,
    NOT available in our target env  -> every use is tagged `# TODO re-point`.
  - direct NCBI E-utilities over urllib = portable, keep as-is.

Cell/line citations refer to Claude_Sciences_Notebook_Extraction.txt.
"""

import os
import re
import time
import json
import urllib.request
import urllib.parse
from lxml import etree


# =============================================================================
# BLOCK 1 - NCBI EFetch: raw PMC JATS XML  (PORTABLE - cell [32]/[38], lines 675-681, 921-933)
# The only direct-E-utilities call in the notebook. db=pmc returns JATS XML that PRESERVES
# <xref ref-type="bibr" rid="..."> markers and the <ref-list>, which the connector's
# get_full_text_article strips (cell [29]) - that is why the whole pipeline pivots to this.
# No api_key / email / tool params in the original; rate limit is a bare sleep(0.34) ~= 3/s.
# =============================================================================

def efetch_pmc_xml(pmcid):
    num = str(pmcid).replace("PMC", "")
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(
        {"db": "pmc", "id": num, "rettype": "xml", "retmode": "xml"})
    req = urllib.request.Request(url, headers={"User-Agent": "python-urllib"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def efetch_pmc_xml_cached(pmcid):
    num = str(pmcid).replace("PMC", "")
    fp = f"pmc_cache/{num}.xml"
    if os.path.exists(fp):
        return open(fp, "rb").read()
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(
        {"db": "pmc", "id": num, "rettype": "xml", "retmode": "xml"})
    req = urllib.request.Request(url, headers={"User-Agent": "python-urllib"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    open(fp, "wb").write(data)
    time.sleep(0.34)
    return data


# =============================================================================
# BLOCK 2 - JATS parsing: ref-matching + citing-sentence extraction  (PORTABLE - cell [32], lines 683-721)
# This is the crown jewel. All pure lxml, no connector.
#   find_rids_for_source : cited PMID/DOI -> set of <ref id=...> rids (metadata-grounded link)
#   _render              : serialize a <p>, marking in-text <xref> that point to those rids
#   sentences_citing     : split into sentences, return the ones carrying a citation marker
# =============================================================================

def txt(el):
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def find_rids_for_source(root, target_pmid=None, target_doi=None):
    ids = set()
    tdoi = (target_doi or "").lower().strip()
    for ref in root.iter("ref"):
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


MARK = "█CITE█"


def _render(el, rids):
    s = el.text or ""
    for c in el:
        if c.tag == "xref" and c.get("ref-type") == "bibr" and any(r in rids for r in (c.get("rid") or "").split()):
            s += MARK + (c.text or "")
        else:
            s += _render(c, rids)
        s += (c.tail or "")
    return s


def sentences_citing(root, rids):
    out = []
    body = root.find(".//body")
    if body is None:
        return out
    for p in body.iter("p"):
        if not any(c.get("ref-type") == "bibr" and any(r in rids for r in (c.get("rid") or "").split())
                   for c in p.iter("xref")):
            continue
        marked = re.sub(r"\s+", " ", _render(p, rids)).strip()
        msents = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9(])', marked)
        for ms in msents:
            if MARK in ms:
                out.append(ms.replace(MARK, "").strip())
    return out


# =============================================================================
# BLOCK 3 - Verbatim fabrication guard + helpers  (PORTABLE - cell [35] lines 835-844,
#           body_text cell [47] 1388-1391, clean_display SAFE version cell [50] 1554-1558)
# Guard: whitespace-normalize both sides and assert the claim is an exact substring of the
# citer's <body> full text. body_text() is the denominator. clean_display() strips only
# bracketed/parenthetical numeric citation markers (the buggy cell [49] variant that also
# stripped word-glued digits corrupted gene names e.g. NUF2->NUF; this safe version does not).
# =============================================================================

def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def body_text(pmcid):
    root = etree.fromstring(open(f"pmc_cache/{str(pmcid).replace('PMC', '')}.xml", "rb").read())
    b = root.find(".//body")
    return re.sub(r"\s+", " ", "".join(b.itertext())).strip() if b is not None else ""


def verbatim_ok(claim, pmcid):
    # cell [35]: norm(claim) in norm(body); re-run globally in cells [67]/[74] before writing deliverables
    return norm(claim) in body_text(pmcid)


def clean_display(s):
    # ONLY strip clearly bracketed/parenthetical numeric citation markers. Never touch alphanumerics.
    s = re.sub(r"\s*\[[\d,\s–-]+\]", "", s)        # [50], [1,2], [1-3]
    s = re.sub(r"\s*\((?:\d+[,\s–-]*)+\)", "", s)  # (97), (1, 2)
    return re.sub(r"\s+", " ", s).strip()


# =============================================================================
# BLOCK 4 - Main extraction driver  (PORTABLE core - cell [39], lines 984-1005)
# Given `allcit` (per-source list of citers-with-PMCID) and `srcmeta` (source PMID->meta,
# incl. cited_doi), walk citers, fetch JATS, ref-match, keep length-filtered citing sentences.
# NOTE: the *inputs* allcit/srcmeta come from BLOCK 6 connector calls (needs re-pointing).
# =============================================================================

def run_extraction(allcit, srcmeta, drop=frozenset({"11117735", "38985161"}), cap=25, min_len=45, max_len=380):
    extraction = {}  # pmid -> {category, examined, n_hits, hits[]}
    for pmid, info in allcit.items():
        if pmid in drop or "error" in info:
            continue
        src = srcmeta[pmid]
        hits = []
        examined = 0
        for c in info["pmc"][:cap]:
            examined += 1
            try:
                root = etree.fromstring(efetch_pmc_xml_cached(c["pmcid"]))
            except Exception:
                continue
            rids = find_rids_for_source(root, pmid, src["cited_doi"])
            if not rids:
                continue
            sents = [s for s in sentences_citing(root, rids) if min_len <= len(s) <= max_len]
            if sents:
                hits.append({"citer_pmid": c["pmid"], "citer_pmcid": c["pmcid"], "citer_doi": c.get("doi"),
                             "rids": sorted(rids), "sentences": sents})
        extraction[pmid] = {"category": info["category"], "examined": examined, "n_hits": len(hits), "hits": hits}
    return extraction


# =============================================================================
# BLOCK 5 - Grounding AS ACTUALLY IMPLEMENTED IN THE NOTEBOOK  (organism/pop split)
# This is the ONLY grounding code present. It is hardcoded string-set membership over the
# flat mesh_terms list (NOT tree numbers). Cells [58] line 1976, [61] line 2063, [66] lines 2233/2253.
# The tree-number version (organism = tree B, age = M01.060, sex = no tree #) is spec-only:
# see repo grounded.json and design/02_source_code_inventory.md. Do not confuse the two.
# =============================================================================

ANIMAL = {"Animals", "Mice", "Rats", "Macaca mulatta", "Zebrafish", "Rats, Sprague-Dawley",
          "Mice, Inbred C57BL", "Disease Models, Animal", "Rats, Wistar", "Macaca"}
POP = {"Adult", "Middle Aged", "Aged", "Young Adult", "Aged, 80 and over", "Adolescent", "Child", "Infant"}


def split_mesh(mesh):
    """mesh = flat mesh_terms list from get_article_metadata. Returns (organism_tags, population_tags,
    humans_present). Notebook signal for species mismatch is `'Humans' not in mesh`."""
    orgs = [m for m in mesh if m in ANIMAL]
    pop = [m for m in mesh if m in POP]
    return orgs, pop, ("Humans" in mesh)


# =============================================================================
# BLOCK 6 - Data discovery (CONNECTOR-DEPENDENT - all NEEDS-REPOINTING)
# =============================================================================

# --- PubMed metadata (abstract / mesh_terms / article_types / doi) --- cell [22] lines 369-374
# TODO re-point: host.mcp("pubmed","get_article_metadata") -> NCBI efetch db=pubmed&retmode=xml,
#   parse <AbstractText>, <MeshHeading><DescriptorName>, <PublicationType>. (This is ALSO where
#   the real grounding must be rebuilt: abstract + MeSH + retraction linkages all live here.)
def fetch_meta(pmids, chunk=15):
    arts = []
    for i in range(0, len(pmids), chunk):
        m = host.mcp("pubmed", "get_article_metadata", pmids=pmids[i:i + chunk])  # noqa: F821
        arts += m.get("articles", [])
    return arts


# --- Citing works (citation graph) --- cell [37] lines 478-483
# TODO re-point: host.mcp("literature","openalex_citations") -> OpenAlex REST
#   GET https://api.openalex.org/works?filter=cites:{openalex_id}&sort=cited_by_count:desc
#   (first resolve source DOI -> OpenAlex id via /works/doi:{doi}); map ids.pmid, ids.doi, open_access.is_oa
def get_citers(pmid, doi, maxrec=80):
    wid = ("https://doi.org/" + doi) if doi else pmid
    r = host.mcp("literature", "openalex_citations", work_id=wid, sort="cited_by_count", max_records=maxrec)  # noqa: F821
    return [{"pmid": x.get("pmid"), "doi": x.get("doi"), "title": (x.get("title") or "")[:80],
             "year": x.get("publication_year"), "is_oa": x.get("open_access", {}).get("is_oa")}
            for x in r.get("records", [])], r.get("api_total")


# --- PMID -> PMCID (keep only citers with PMC full text) --- cell [37] lines 485-491
# TODO re-point: host.mcp("pubmed","convert_article_ids") -> NCBI PMC ID Converter
#   GET https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={csv}&format=json   (or elink dbfrom=pubmed db=pmc)
def to_pmc(pmids):
    if not pmids:
        return []
    recs = []
    for i in range(0, len(pmids), 50):
        rr = host.mcp("pubmed", "convert_article_ids", ids=pmids[i:i + 50], id_type="pmid").get("records", [])  # noqa: F821
        recs += rr
    return [{"pmid": r["pmid"], "pmcid": r["pmcid"], "doi": r.get("doi")} for r in recs if r.get("pmcid")]


# --- OpenAlex work + is_retracted flag --- cells [19]/[63], lines 655-657
# TODO re-point: host.mcp("literature","openalex_get_work") -> OpenAlex REST
#   GET https://api.openalex.org/works/doi:{doi}  -> is_retracted, cited_by_count, id
def openalex_is_retracted(doi=None, pmid=None):
    w = host.mcp("literature", "openalex_get_work", work_id=("https://doi.org/" + doi) if doi else pmid)  # noqa: F821
    return {"is_retracted": w.get("is_retracted"), "cited_by_count": w.get("cited_by_count"),
            "oa_id": w.get("openalex_id")}


# --- PubMed search --- cell [20] lines 296-298
# TODO re-point: host.mcp("pubmed","search_articles") -> NCBI esearch db=pubmed&term=...&retmax=...&sort=relevance
def search_pubmed(query, max_results=6):
    r = host.mcp("pubmed", "search_articles", query=query, max_results=max_results, sort="relevance")  # noqa: F821
    return r.get("pmids", [])


# --- API key --- cell [18] lines 191-195
# TODO re-point: host.credentials.request("openalex") -> read os.environ["OPENALEX_API_KEY"] (or use mailto= polite pool)


# =============================================================================
# BLOCK 7 - Claim-side LLM classification (CONNECTOR-DEPENDENT; the model-judgment seam)
# Not grounding/extraction - this is corpus labeling / claim-scope judgment (C3/C4). Included
# because it is the ONE place the pipeline reads text with a model, reused 3x. Prompts port
# verbatim; only the transport changes.
# TODO re-point: host.llm(reqs, max_concurrency=8) -> Anthropic Messages API (or Batch API).
# =============================================================================

# JSON extractor for LLM output --- cell [43] lines 1131-1136
def parse_json(t):
    t = t.strip()
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


# Category A prompt: does the citer rely on the retracted finding, and acknowledge the retraction? cell [42] lines 1089-1098
SYS_A = """You classify how a scientific paper CITES another paper. You are given the cited paper's title+abstract (the "SOURCE") and a verbatim sentence from a CITING paper that references it. Return ONLY a JSON object, no prose.

Judge two things:
1. relies_on_finding: does the citing sentence USE or ASSERT the source's specific scientific finding/result as support for a claim? true = the sentence states a finding and leans on this source for it. false = passing/background mention, a methods citation, or the source is cited only in a long list for an unrelated general point.
2. acknowledges_retraction: does the citing sentence itself signal the source is retracted/fraudulent/discredited/debunked/questionable (words like retracted, fraudulent, debunked, discredited, misconduct, falsified, "later retracted", "now-retracted")? true/false.

Also:
3. claim_is_selfcontained: is the sentence understandable as a standalone factual claim (true) or does it need heavy surrounding context / is it fragmentary (false)?
4. rationale: <=20 words.

Output JSON schema exactly: {"relies_on_finding": bool, "acknowledges_retraction": bool, "claim_is_selfcontained": bool, "rationale": "..."}"""

# Category B prompt: does the citing sentence over-generalize an animal-only finding to humans? cell [52] lines 1628-1639
SYS_B = """You analyze whether a CITING sentence over-generalizes an ANIMAL-ONLY finding to humans. The cited SOURCE is an animal study (its MeSH organism tags are given; 'Humans' is absent). You are given a verbatim sentence from a citing paper that references this animal source. Return ONLY JSON.

Classify the SCOPE the citing sentence asserts for the finding it attributes to the source:
- asserted_scope: one of "human" (claims the finding in humans/patients/clinical/people), "adult_human", "animal" (correctly restricts to mouse/rat/monkey/zebrafish/animal model), "general_unqualified" (states finding as a general fact with NO species qualifier at all), "unclear".
- scope_evidence: the exact words in the sentence that establish the scope (e.g. "in patients", "in mice", or "" if none).
- has_explicit_human_marker: true if sentence literally contains human/clinical terms (humans, patients, clinical, people, men, women, adults, individuals). Otherwise false.
- drops_species_qualifier: true if the finding is stated without naming the animal, i.e. it reads as if generally/human-applicable. false if the animal is named.
- is_mismatch_candidate: true if this sentence uses the animal finding in a way that asserts or strongly implies human/general applicability WITHOUT restricting to the animal. false if it correctly keeps it animal-scoped.
- selfcontained: sentence is a standalone factual claim (true/false).
- rationale: <=20 words.

Output exactly: {"asserted_scope":"...","scope_evidence":"...","has_explicit_human_marker":bool,"drops_species_qualifier":bool,"is_mismatch_candidate":bool,"selfcontained":bool,"rationale":"..."}"""

# Category B second pass: does THIS sentence attribute the animal finding to humans/clinical? cell [57] lines 1887-1894
SYS_B_HUMAN = """A citing sentence references an ANIMAL-ONLY source study (organism metadata given; 'Humans' absent from its MeSH). Decide whether THIS sentence, in citing that animal source, attributes or extends the finding to HUMANS or CLINICAL use WITHOUT restricting it to the animal. Return ONLY JSON.

- attributes_to_human: true if the sentence claims/implies the (animal-derived) finding applies to humans, patients, or clinical practice. false if it correctly keeps the claim within animals/model organisms, or the human word is only about a DIFFERENT correctly-human thing.
- human_marker_words: the exact human/clinical words used.
- animal_still_named_for_this_claim: true if THIS finding is still attributed to the animal in the sentence (e.g. "in mice"), false if the animal is dropped.
- strength: "strong" (clear human/clinical claim citing the animal study), "moderate", "weak".
- rationale: <=18 words.
Output exactly: {"attributes_to_human":bool,"human_marker_words":"...","animal_still_named_for_this_claim":bool,"strength":"...","rationale":"..."}"""

# Category C prompt: is this a clean, correct citation (human scope + supported by source abstract)? cell [64] lines 2133-2141
SYS_C = """A citing sentence references a SOURCE that is a HUMAN clinical study (randomized trial or human cohort). Decide whether this is a CLEAN, CORRECT citation. Return ONLY JSON.

- claim_scope_human: true if the citing sentence's asserted finding is about humans/patients/clinical (matching the human source). false if it asserts animals or is scope-ambiguous.
- supported_by_source: true if the specific claim is consistent with / stated in the SOURCE abstract provided. false if the claim asserts something the abstract does not support or contradicts.
- specific_finding: true if the sentence conveys a specific result (effect, comparison, outcome), false if vague/background/methods-only.
- has_human_marker: true if sentence contains human/clinical/patient words.
- selfcontained: standalone factual claim (true/false).
- rationale: <=18 words.
Output exactly: {"claim_scope_human":bool,"supported_by_source":bool,"specific_finding":bool,"has_human_marker":bool,"selfcontained":bool,"rationale":"..."}"""

# Pre-filter regex used before the SYS_B_HUMAN pass --- cell [56] lines 1839-1840
HUMAN_MARKER = re.compile(
    r"\b(human|humans|patient|patients|clinical|clinically|people|men|women|"
    r"adult|adults|individual|individuals|in vivo human|therapeutic|therapy|treatment of)\b", re.I)


def classify_claims(items, system_prompt, make_prompt, max_tokens=200):
    """items -> list of parsed JSON dicts. make_prompt(item)->str.
    TODO re-point: host.llm -> Anthropic Messages/Batch API."""
    reqs = [{"prompt": make_prompt(it), "system": system_prompt, "max_tokens": max_tokens} for it in items]
    results = host.llm(reqs, max_concurrency=8)  # noqa: F821
    return [parse_json(r.get("text", "")) or {} for r in results]
