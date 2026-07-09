# Source Code Inventory — Prior Claude Science Work

Faithful inventory of the real prior code for porting into the citation-verification
system. Line numbers cite `Claude_Sciences_Notebook_Extraction.txt` (the notebook,
2721 lines) unless stated otherwise. The prose-only intel file is
`Claude_Science_Extraction.txt` (the "science doc", 754 lines).

## TL;DR — what actually exists as code

- **The notebook is entirely conversation 2 (eval-set / corpus assembly).** It preserves
  the **extraction pipeline** (JATS XML → ref-match → verbatim sentence → fabrication guard)
  in full, plus corpus building and LLM claim-classification.
- **The grounding routine (`ground_pmid`) is NOT in the notebook.** Grep confirms zero
  occurrences of `ground_pmid`, `tree_number`, `CommentsCorrections`, `RetractionIn`,
  `id.nlm.nih.gov`, `db=taxonomy`. Its behaviour survives only as (a) prose in the science
  doc and (b) output artifacts in the repo (`grounded.json`, `verdict.json`,
  `citation_grounding_demo.md`). This matches the flag already in
  `01_dependency_graph.md`: "C2 code is a re-implementation, not a port."
- Two data runtimes are interleaved: `host.mcp(...)` / `host.llm(...)` / `host.credentials`
  (the Claude Science connector runtime — **not available in our target env**) and direct
  NCBI E-utilities over `urllib` (**portable**). The extraction core is portable; the
  data-discovery layer (citation graph, ID conversion, metadata) is all connector calls.

---

## a. Cell-by-cell map

The extraction is a partial notebook export; execution counts jump (missing cells
[1]–[6], [9]–[14], [23]–[26], [30], [31] — these covered the Retraction Watch CSV download,
`candidate_sources` assembly, and plan JSON, which are described in the science doc but
**not present as code**).

| Cell | Lines | What it does |
|---|---|---|
| [7] | 1–45 | Probe PubMed metadata via `host.mcp("pubmed","get_article_metadata")` on 3 PMIDs; dumps keys. Shows `mesh_terms` is a **flat list**, `article_types` present. |
| [8] | 46–66 | Print `mesh_terms` per PMID (18509334 animal-only, etc.). |
| [15] | 67–107 | Enrich Cat-A shortlist via `host.mcp("literature","openalex_get_work")` for `is_retracted`/`cited_by_count` (format crash on `None`). |
| [16] | 108–162 | Re-report enriched list from saved JSON (all `None` — no key yet). |
| [17] | 163–186 | Inspect one raw `openalex_get_work` → returns `{"error":"openalex_key_required"}`. |
| [18] | 187–198 | `host.credentials.request("openalex")` → gets 22-char key. |
| [19] | 199–272 | Re-enrich all 40 Cat-A sources; `is_retracted=True` + citation counts now populated. |
| [20] | 273–314 | Cat-B candidate PubMed searches via `host.mcp("pubmed","search_articles", sort="relevance")` (animal-model queries). |
| [21] | 315–358 | Cat-C landmark-human-trial searches + fetch B/C metadata (capped at 20). |
| [22] | 359–383 | Batch-fetch all B/C metadata with chunked `fetch_meta` helper (`get_article_metadata`, chunk=15). |
| [27] | 384–416 | Pilot: `host.mcp("literature","openalex_citations", work_id="https://doi.org/…", sort="cited_by_count", max_records=60)` for 3 sources; counts `is_oa`/`with_pmid`. |
| [28] | 417–438 | Convert citer PMIDs→PMCIDs via `host.mcp("pubmed","convert_article_ids", id_type="pmid")`; PMC coverage 13/46/38. |
| [29] | 439–464 | Fetch one PMC full text via `host.mcp("pubmed","get_full_text_article")`; **discovers inline citation markers are stripped** (empty `()`). Reason for the JATS pivot. |
| [37] | 465–539 | Defines `get_citers` (openalex_citations) + `to_pmc` (convert_article_ids); runs both for all candidate sources. |
| [40] | 540–612 | Fetch retracted Cat-A source abstracts (`get_article_metadata`) so classifier knows "the specific finding". |
| [62] | 613–642 | Fetch Cat-C source metadata + abstracts + `mesh_terms` + `article_types`. |
| [63] | 643–666 | Verify Cat-C sources not-retracted via `openalex_get_work` `is_retracted=False`. |
| **[32]** | **667–726** | **JATS parser (PORTABLE):** defines `efetch_pmc_xml`, `txt`, `find_rids_for_source`, `MARK`/`_render`, `sentences_citing` — direct NCBI EFetch `db=pmc` over urllib + lxml. |
| [33] | 727–771 | Pilot extraction loop over ≤15 citers/source; counts examined / ref-matched / sentence-yielding. |
| [34] | 772–825 | Print extracted pilot sentences per source. |
| **[35]** | **826–864** | **Verbatim fabrication guard:** `norm(s)=re.sub(r"\s+"," ",s).strip()`, then `norm(claim) in fulltext_norm`; computes yield (72% ref-matched, 44% usable). |
| [36] | 865–911 | Write `pilot_yield.md`. |
| **[38]** | **912–972** | **Cached extraction fns (PORTABLE):** `efetch_pmc_xml_cached` (disk cache + `time.sleep(0.34)`); re-defines the whole parser (safe-redefine after kernel restart). |
| [39] | 973–1051 | Main extraction: for every source, walk ≤25 PMC citers, `find_rids_for_source`, keep `sentences_citing` filtered `45<=len<=380`. 151 A / 78 B / 57 C citer-hits. |
| [41] | 1052–1080 | Build 151 Cat-A classification items (claim = joined citer sentences + source abstract). |
| [42] | 1081–1121 | Classify Cat-A via `host.llm(reqs, max_concurrency=8)` — `relies_on_finding` / `acknowledges_retraction` / `claim_is_selfcontained`. |
| [43] | 1122–1185 | Parse LLM JSON (`parse_json`); select uncritical finding-reliant claims (84 uncritical, 2 ack). |
| [44] | 1186–1270 | Print best 2 uncritical candidates per chosen source. |
| [45] | 1271–1297 | Print Macchiarini-airway (19022496/22119609) candidates. |
| [46] | 1298–1369 | Finalize 7 Cat-A cases + verbatim guard → **1 fails** (joined non-contiguous sentences). |
| [47] | 1370–1439 | `best_sentence` = longest single sentence that is verbatim; all 7 pass. |
| [48] | 1440–1458 | Inspect miR-34a citer sentences (picks the right gastric-cancer sentence). |
| [49] | 1459–1537 | Add `clean_display`; **bug**: `([A-Za-z])\d{1,3}` corrupts gene name `NUF2`→`NUF`. |
| [50] | 1538–1592 | **Safe `clean_display`**: strips only bracketed `[..]` / parenthetical `(..)` numeric markers; `NUF2` intact. |
| [51] | 1594–1619 | Build 139 Cat-B candidate sentences (animal-only sources). |
| [52] | 1621–1662 | Classify Cat-B scope via `host.llm` + `SYS_B` (asserted_scope / has_explicit_human_marker / drops_species_qualifier / is_mismatch_candidate). |
| [53] | 1664–1715 | Parse B; split **text-grounded** (explicit human marker, 4) vs **model-inferred** (dropped qualifier, 66). |
| [54] | 1717–1798 | Review strong B candidates per source. |
| [55] | 1799–1828 | Expand B extraction to ALL PMC citers (not just 25) → 201 sentences. |
| [56] | 1830–1878 | Pre-filter B with regex `HUMAN` (human/patient/clinical/…) → 29 candidates. |
| [57] | 1880–1938 | Verify B human-attribution via `host.llm` (`attributes_to_human`, `animal_still_named_for_this_claim`, strength). 14 strong. |
| [58] | 1940–2016 | Finalize B cases v1; **organism split by hardcoded `ANIMAL` set**; records `humans_tag_absent`. |
| [59] | 2018–2039 | Review strong human-attribution B candidates. |
| [60] | 2040–2052 | Print full CR-monkey candidate sentence. |
| [61] | 2054–2113 | Rebuild B at 5 cases (cleaner CR-monkey claim; `inference_flag=True`). |
| [64] | 2115–2187 | Build 74 Cat-C items + classify via `host.llm` + `SYS_C` (claim_scope_human / supported_by_source / specific_finding). |
| [65] | 2188–2220 | Print C source abstracts to hand-check support. |
| [66] | 2221–2287 | Finalize 5 Cat-C cases; **population split by hardcoded `POP` set**; carries `oa_is_retracted`, `inference_flag=True`. |
| [67] | 2288–2368 | Assemble unified 17-row table (7A/5B/5C); final verbatim re-verify pass; provenance accounting (7 grounded, 10 inference). |
| [68] | 2369–2430 | Write `eval_set.csv` (pandas) + `eval_set.json` (schema + label/provenance definitions). |
| [69] | 2431–2454 | Build methodology markdown tables. |
| [70] | 2455–2543 | Write `methodology.md`. |
| [71] | 2544–2634 | Load CSV, print every case's claim + justifying metadata. |
| [72] | 2635–2652 | Inspect A06 sentence context (fragment starts mid-sentence). |
| [73] | 2653–2683 | Fix A06 to full sentence; verify C02's "5.8 points" number is in the cited abstract. |
| [74] | 2684–2721 | Persist A06 fix, final verbatim re-verify (all 17 True), regenerate CSV/JSON. |

---

## b. Reusable functions / blocks

### Extraction (portable core)

**`efetch_pmc_xml(pmcid)`** — cell [32], lines 675–681
- Purpose: fetch raw PMC JATS XML for a PMCID.
- In: pmcid (str, "PMC…" or numeric). Out: raw XML bytes.
- External call: `GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={num}&rettype=xml&retmode=xml`, header `User-Agent: python-urllib`, `urllib`.
- **DIRECT-PORTABLE** (pure `urllib` to NCBI; no connector).

**`efetch_pmc_xml_cached(pmcid)`** — cell [38], lines 921–933
- Same as above + on-disk cache `pmc_cache/{num}.xml` and `time.sleep(0.34)` (≈3 req/s) after each live fetch.
- **DIRECT-PORTABLE.** This is the production form.

**`find_rids_for_source(root, target_pmid=None, target_doi=None)`** — cell [32], lines 686–695
- Purpose: given the citer's parsed JATS tree, return the set of reference IDs (`<ref id=…>`) whose `<pub-id>` matches the cited source by PMID or (lowercased) DOI. This is the metadata-grounded citation link.
- In: lxml root, target PMID/DOI. Out: `set` of rid strings.
- External call: none (pure lxml traversal: `root.iter("ref")`, `ref.iter("pub-id")`, filter on `pub-id-type in {pmid,doi}`).
- **DIRECT-PORTABLE.**

**`MARK` + `_render(el, rids)`** — cell [32], lines 697–706
- Purpose: recursively serialize a `<p>` element to text, inserting a sentinel `MARK` (`"█CITE█"`) immediately before any `<xref ref-type="bibr" rid=…>` whose rid is in the target set. Lets sentence-splitting know which sentence carries the citation.
- **DIRECT-PORTABLE** (lxml only).

**`sentences_citing(root, rids)`** — cell [32], lines 708–721
- Purpose: for each `<p>` in `<body>` that contains a matching `<xref>`, render with `_render`, whitespace-normalize, split on `(?<=[.!?])\s+(?=[A-Z0-9(])`, and return every sentence containing `MARK` (marker stripped).
- In: lxml root, rids. Out: list of verbatim citing sentences.
- **DIRECT-PORTABLE.**

**`txt(el)`** — cell [32], lines 683–684 — helper: `re.sub(r"\s+"," ","".join(el.itertext())).strip()`. **DIRECT-PORTABLE.**

**Verbatim fabrication guard** — cell [35], lines 835–844 (and re-applied [67] 2348–2350, [74] 2701–2702)
- `norm(s) = re.sub(r"\s+"," ", s).strip()`; test `norm(claim) in norm("".join(body.itertext()))`.
- Purpose: prove the stored claim is an exact substring of the citer's whitespace-normalized full-text body (no paraphrase/hallucination).
- **DIRECT-PORTABLE.**

**`body_text(pmcid)`** — cells [47]/[49]/[50]/[58]/[61]/[66]/[67] (e.g. [47] lines 1388–1391)
- Reads cached XML, returns whitespace-normalized `.//body` itertext. The denominator for the guard.
- **DIRECT-PORTABLE.**

**`clean_display(s)`** — cell [50], lines 1554–1558 (safe version)
- Strips only bracketed `[\d,\s–-]+` and parenthetical `(\d…)` citation markers; leaves alphanumerics untouched (fixes the `NUF2`→`NUF` corruption from cell [49]).
- **DIRECT-PORTABLE.**

**Main extraction driver** — cell [39], lines 984–1005
- Loops sources → ≤25 PMC citers → `etree.fromstring(efetch_pmc_xml_cached(pmcid))` → `find_rids_for_source` → `sentences_citing` filtered by length. Emits `{citer_pmid, citer_pmcid, citer_doi, rids, sentences[]}`.
- **DIRECT-PORTABLE core**, but its *inputs* (`allcit` = citers with PMCIDs) come from connector calls (see below).

**`parse_json(t)`** — cell [43], lines 1131–1136 — extract first `{...}` block from LLM text, `json.loads`. **DIRECT-PORTABLE.**

### Data discovery (connector-dependent)

**`fetch_meta(pmids, chunk=15)`** — cell [22], lines 369–374
- Purpose: batched article metadata (title/abstract/`mesh_terms`/`article_types`/DOI).
- External call: `host.mcp("pubmed","get_article_metadata", pmids=…)`.
- **NEEDS-REPOINTING.** Connector `pubmed/get_article_metadata`. Direct equivalent: NCBI `efetch.fcgi?db=pubmed&id=…&retmode=xml` and parse `<AbstractText>`, `<MeshHeading><DescriptorName>`, `<PublicationType>`; or `esummary.fcgi?db=pubmed`. (Abstract+MeSH+pubtypes only come from efetch, not esummary.)

**`get_citers(pmid, doi, maxrec=80)`** — cell [37], lines 478–483
- Purpose: papers that cite a work, sorted by citation count, with PMID/DOI/OA flag.
- External call: `host.mcp("literature","openalex_citations", work_id="https://doi.org/{doi}", sort="cited_by_count", max_records=…)`.
- **NEEDS-REPOINTING.** Connector `literature/openalex_citations`. Direct equivalent: OpenAlex REST `GET https://api.openalex.org/works?filter=cites:{openalex_work_id}&sort=cited_by_count:desc&per-page=…` (first resolve the source to its OpenAlex ID via `/works/doi:{doi}`). Map each result's `ids.pmid`, `ids.doi`, `open_access.is_oa`.

**`to_pmc(pmids)`** — cell [37], lines 485–491
- Purpose: keep only citers with a PMCID (i.e. PMC full text available).
- External call: `host.mcp("pubmed","convert_article_ids", ids=…, id_type="pmid")` (chunk 50).
- **NEEDS-REPOINTING.** Connector `pubmed/convert_article_ids`. Direct equivalent: NCBI PMC ID Converter `GET https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={csv}&format=json` (returns pmcid per pmid), or `elink.fcgi?dbfrom=pubmed&db=pmc`.

**OpenAlex work fetch / retraction flag** — cells [15]/[19]/[63], e.g. lines 655–657
- External call: `host.mcp("literature","openalex_get_work", work_id="https://doi.org/{doi}")` → `is_retracted`, `cited_by_count`, `openalex_id`, `pmid`.
- **NEEDS-REPOINTING.** Direct equivalent: OpenAlex REST `GET https://api.openalex.org/works/doi:{doi}` → `is_retracted`, `cited_by_count`, `id`.

**PubMed search** — cell [20]/[21], lines 296–298
- External call: `host.mcp("pubmed","search_articles", query=…, max_results=…, sort="relevance")` → `pmids`.
- **NEEDS-REPOINTING.** Direct equivalent: `esearch.fcgi?db=pubmed&term=…&retmax=…&sort=relevance`.

**API key acquisition** — cell [18], lines 191–195
- `host.credentials.request("openalex")`. **NEEDS-REPOINTING** → just read `OPENALEX_API_KEY` from env (OpenAlex "polite pool" also accepts `mailto=`).

**Full-text via connector** — cell [29], `host.mcp("pubmed","get_full_text_article")`
- **DO NOT PORT.** Explicitly abandoned (lines 418, 476): it strips inline `<xref>` markers, defeating ref-matching. The whole JATS pivot exists to avoid it.

### Claim-side LLM classification (connector-dependent; the model-judgment seam)

Not grounding or extraction per se — this is the corpus-labeling / claim-scope work
(maps to C3/C4). Included because it is the one place the pipeline **reads text with a
model**, and it is reused three times.

**`host.llm(reqs, max_concurrency=8)`** — cells [42] (1109), [52] (1648), [57] (1900), [64] (2147)
- Purpose: batched structured classification of citing sentences. Three prompt families:
  - `SYS` (A, [42] lines 1089–1098): does the citer *rely on* the retracted finding, and does it *acknowledge* the retraction?
  - `SYS_B` (B, [52] lines 1628–1639): what scope does the claim assert (human / animal / general_unqualified), explicit human marker?
  - `SYS_C` (C, [64] lines 2133–2141): is the claim human-scoped AND supported by the cited abstract?
- **NEEDS-REPOINTING.** `host.llm` → Anthropic Messages API (or batch). Prompts port verbatim; only the transport changes. Note this is the **claim-side, model-inferred** layer the project keeps explicitly separate from metadata.

---

## c. Grounding specifics

**Important: the grounding *routine* is not in the notebook.** What the notebook does for
"grounding" is thin and different from the science-doc spec. The rich version survives
only as **outputs** (`grounded.json`, `verdict.json`) and prose. Below, each item states
where it lives.

### Organism-vs-population MeSH split
- **In the notebook (what actually ran):** a **hardcoded string-set membership test**, not tree numbers.
  - Organisms: `ANIMAL = {"Animals","Mice","Rats","Macaca mulatta","Zebrafish","Rats, Sprague-Dawley","Mice, Inbred C57BL","Disease Models, Animal","Rats, Wistar","Macaca"}`; `orgs=[m for m in mesh if m in ANIMAL]` (cells [58] line 1976, [61] line 2063).
  - Population/age: `POP = {"Adult","Middle Aged","Aged","Young Adult","Aged, 80 and over","Adolescent","Child","Infant"}`; `pop=[m for m in mesh if m in POP]` (cell [66] lines 2233, 2253).
  - Input `mesh` is the **flat `mesh_terms` list** from `host.mcp("pubmed","get_article_metadata")` (cell [7]). Presence/absence of the literal string `"Humans"` is the mismatch signal (`"Humans" not in mesh`).
- **In the spec/outputs (grounded.json, science doc — NOT code here):** the principled version keys on **NLM MeSH tree numbers**: organisms = **tree `B`** (e.g. Humans `B01.050.150.900…`, Animals `B01.050`, Mice `B01.050.150.900.649.313.992…`); age groups = **`M01.060`** (Child `M01.060.406`, Child Preschool `M01.060.406.448`); **sex check-tags** (Female/Male) carry **no tree number** and form a separate controlled set (`sex_tags` with `tree_numbers: []`). `grounded.json` provenance string: `"efetch <MeshHeading><DescriptorName> + NLM MeSH tree numbers (id.nlm.nih.gov)"`. The tree numbers were fetched from the NLM linked-data endpoint `id.nlm.nih.gov/mesh/{UI}.json` (science doc lines 50–55), **not** from efetch db=mesh (which the model found wants internal UIDs, science doc line 50). Each tag carries `{descriptor, ui, major_topic, tree_numbers}`.

### Retraction status derivation
- **In the notebook (what ran):** two signals, neither being efetch/CommentsCorrections:
  1. **Retraction Watch CSV** — fields `RetractionNature`, `Reason`, `RetractionDate`, `OriginalPaperPubMedID`, `OriginalPaperDOI` (used as Cat-A ground truth via the `candidate_sources`/`proving_metadata` fields; the download/parse code is in a missing cell, described science doc 214–222 & methodology.md).
  2. **OpenAlex `is_retracted`** — `host.mcp("literature","openalex_get_work")` (cells [19], [63]).
- **In the spec/outputs (grounded.json — NOT code here):** `retraction_status ∈ {RETRACTED, NONE_FOUND}` derived from **efetch `<PublicationType>` containing "Retracted Publication"** + **`<CommentsCorrections RefType=…>`** linkages, emitting `retraction_notices=[{ref_type, ref_source, notice_pmid}]` where `ref_type ∈ {RetractionIn, ExpressionOfConcernIn}`. Grep confirms this efetch/CommentsCorrections code is **absent** from the notebook.

### NCBI Taxonomy
- **Not used anywhere in the notebook** (grep: no `db=taxonomy`). Science doc (line 108) notes `efetch db=taxonomy` is reachable and MeSH tree-B descriptors map to taxa "if you want the taxonomic hierarchy", but no code exercises it.

### NCBI api_key / email / tool / rate-limit parameters
- **No `api_key`, no `email=`, no `tool=`** anywhere (grep confirmed). The only auth-ish detail is header `User-Agent: python-urllib`.
- **Rate limiting** is a bare `time.sleep(0.34)` (≈3 req/s, the keyless NCBI ceiling) between EFetch calls (cell [38] line 932; cell [33] lines 751/761; cell [39] loop). No retry/backoff. For port: add an `api_key` (raises limit to 10 req/s) and `tool`/`email` params, plus retry on HTTP 429/5xx.

---

## d. Extraction specifics

- **Parser/stack:** `lxml.etree` (`etree.fromstring(xml_bytes)`), traversed with `.iter(tag)` and `.find(".//body")`. Not stdlib ElementTree, not xpath expressions — plain tag iteration. `lxml` install is a hard dependency (cell [38] line 918; kernel restarted mid-session to install it, science doc 433–438).
- **Ref-list / pub-id parsing:** iterate every `<ref>` (`root.iter("ref")`), read `ref.get("id")` for the rid, then `ref.iter("pub-id")` filtering `pub-id-type == "pmid"` / `"doi"`. Match target PMID exactly; match DOI case-insensitively (`.lower().strip()`). See `find_rids_for_source`.
- **In-text marker / xref:** `<xref>` with `ref-type=="bibr"` and `rid` (space-split, since one xref may list several rids: `(c.get("rid") or "").split()`). A `<p>` qualifies if any of its `p.iter("xref")` points into the target rid set.
- **Ref-matching logic:** citation link = "the `<ref>` whose `<pub-id>` equals the cited source's PMID/DOI → its `rid` → every `<xref rid=that>`." This is the deliberate design choice that makes linkage **metadata-grounded, not proximity-guessed** (science doc 419–424, methodology.md §4).
- **Sentence segmentation:** render `<p>` with a `MARK` sentinel before matching xrefs (`_render`), whitespace-normalize, then split on the regex `(?<=[.!?])\s+(?=[A-Z0-9(])` (period/!/? followed by whitespace and an uppercase/digit/paren). Keep only segments still containing `MARK`. Crude but deterministic; known failure modes handled ad hoc: mid-sentence fragments (A06, cells [72]/[73]) and glued citation digits (`PDGFR114`, cell [51]).
- **Length filter:** usable sentences gated to `45 <= len(s) <= 380` in the main run (cell [39] line 1001); pilot used `40..400` (cell [33] line 754); B/C items used `45..360` / `50..340` (cells [51], [64]).
- **Verbatim guard implementation:** whitespace-normalize both sides (`re.sub(r"\s+"," ",…).strip()`) and assert `claim in body_text`. Applied at selection (cells [46]–[66]) and re-verified globally before writing deliverables (cell [67] lines 2348–2350; cell [74] lines 2701–2703 with `assert all(...)`). Each case stores both `claim_text_verbatim` (exact, incl. `[n]` markers) and `claim_text` (display-cleaned).

---

## e. Gaps / not-present (brief vs. actual code)

1. **No `ground_pmid()` grounding routine in the notebook.** The brief's component-2 (fetch abstract + MeSH + retraction, tree-number split) exists only as output schema (`grounded.json`) and prose. Grep: 0 hits for `ground_pmid`, `tree_number`, `CommentsCorrections`, `RetractionIn`, `id.nlm.nih.gov`. Consistent with `01_dependency_graph.md`: "C2 code is a re-implementation, not a port."
2. **No MeSH tree-number logic in code.** The notebook uses hardcoded organism/population string sets against the flat `mesh_terms` list. Tree-B / M01.060 keying is spec-only.
3. **No efetch/CommentsCorrections retraction code.** Retraction in the notebook = Retraction Watch CSV + OpenAlex `is_retracted`. The efetch `<PublicationType>`/`<CommentsCorrections>` method is spec-only.
4. **No direct NCBI metadata/abstract fetch.** All PubMed metadata (abstract, MeSH, pub-types, ID conversion, search) goes through `host.mcp("pubmed",…)`. The **only** direct E-utilities call is `efetch db=pmc` for JATS XML. So abstract + MeSH grounding must be re-implemented directly against efetch db=pubmed.
5. **No NCBI Taxonomy usage.** Reachable per spec, unused in code.
6. **No Retraction Watch download/parse code, no `candidate_sources` assembly code.** These ran in missing cells ([1]–[6], [23]–[26], etc.); only their JSON/CSV outputs and prose remain.
7. **No api_key / email / tool / retry.** Rate limiting is a single hardcoded `sleep(0.34)`.
8. **Population-axis scope mismatch not implemented.** All 5 Cat-B cases are the species axis; pediatric/adult (Infant/Child vs Adult) mismatch was scoped but never populated (methodology.md limitation #4).
9. **Support judgment (C) is abstract-only + model-inferred.** "Does the cited paper support the claim" is judged against the **abstract**, not full text, and flagged `inference_flag=True` (cell [66]). Not a grounded axis.

---

## Claude Science competitive intel

Drawn from the science doc (conversation 1 transcript), which is Claude Science reporting
on its own capabilities. Bears directly on the "grounded-and-measured vs model-checks-model"
thesis.

### Is there a native citation fact-checker? No.
> "There is no built-in, pre-existing 'citation fact-checker' tool I'm calling here; I built
> this evaluator from the grounding primitives, which is exactly what your hackathon tool
> would wrap." (line 122)

Claude Science exposes **grounding primitives** (PubMed/NCBI/OpenAlex connectors), not a
finished verifier. There is no product to match feature-for-feature — the opportunity is a
*measured, calibrated* wrapper.

### Does it re-read the paper with the same model ("model-checks-model")? Explicitly no, for scope/retraction.
The self-described mechanism is **two visibly separated layers** (lines 119–122):
> "Layer A (model-inferred): parse the free-text claim … Layer B (metadata-grounded): the
> paper's scope is **not re-read by the model**. It comes straight from the MeSH organism tags
> via tree number. The grade … is a set membership test on structured fields …, not a model
> re-reading of the abstract."
> "the grade is computed against structured record metadata and external ground-truth (MeSH
> tree, NCBI retraction linkages), **not by re-evaluating the text with the same model**. The
> only model-inferred step is parsing the claim itself." (line 122)

So Claude Science's *demonstrated* approach is already grounded-and-measured on the objective
axes — it is **not** naive model-checks-model. Our differentiation is therefore **not**
"we ground, they don't"; it is: (a) a **calibrated scorer/corpus** proving the grounding
works (their evaluator was ad hoc, unmeasured), and (b) rigorous **provenance separation**
carried through to the report.

### Where even Claude Science concedes model judgment is unavoidable
> "The support-vs-not-support semantic judgment — whether the paper's findings actually back
> the claimed effect (beyond scope). Metadata doesn't carry this; it needs full-text reading
> and is model-inferred." (line 138)

Dose and effect-direction are flagged **UNVERIFIABLE / model-inferred** rather than fabricated
(lines 117–118, verdict.json `unverifiable_axes`). This is the axis where "model-checks-model"
genuinely lives — and where calibration matters most. Match their honesty (flag, don't
fabricate); beat them by measuring the graded axis.

### Grounding it actually uses
- **PubMed MCP connector** (metadata; flattens MeSH to a list, exposes `article_types` incl. "Retracted Publication").
- **NCBI E-utilities** direct HTTP (efetch/esummary/elink) for the structured fields the connector flattens — per-MeSH `MajorTopicYN`, and CommentsCorrections retraction linkages with target PMIDs (line 107).
- **NLM MeSH linked data** `id.nlm.nih.gov/mesh` for authoritative tree numbers — "the ground truth for splitting organism tags from population tags" (line 108).
- **OpenAlex** (`is_retracted` as a secondary retraction signal; citation graph).

### Retraction data limits (differentiation opportunity)
> "there is no dedicated Retraction Watch / Crossref-retraction connector in the catalog …
> The Retraction Watch database (via Crossref) is not on the allowlist — you'd need to request
> that domain or add it as a data source yourself." (line 111)

Native retraction breadth = NCBI's own "Retracted Publication" type + CommentsCorrections,
optionally OpenAlex. Full Retraction Watch coverage is a **build-it-yourself** edge (our
notebook already downloaded the 70,871-record CSV — that breadth is ours to keep).

### Output format to match/differentiate against
- **`grounded.json`** per record: `abstract`, `mesh_all`, and categorized `organism_tags` /
  `age_group_tags` / `sex_tags` / `other_person_tags` (each `{descriptor, ui, major_topic,
  tree_numbers}`), `publication_types`, `retraction_status`, `retraction_notices`
  (`{ref_type, ref_source, notice_pmid}`), and a **`provenance` block naming the source field
  for every value**.
- **`verdict.json`** per check: `layers.claim_parse` (model-inferred, with `confidence`) vs
  `layers.paper_scope_metadata`; `axis_findings.species` (`verdict`, `tier`, `provenance`);
  `unverifiable_axes` (dose / population_subgroup / effect_direction); `retraction_status`.
- Every value carries a **confidence tier** (high/medium) and a **metadata-grounded vs
  model-inferred** provenance label. Matching this provenance discipline is table stakes;
  the differentiator is proving the tiers are **calibrated**.
