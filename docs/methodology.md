# Methodology — Ground-Truth Citation-Verification Evaluation Set

## Purpose
A starter evaluation set of **17 cases** where every ground-truth label is checkable against structured metadata or an external record, requiring no subjective biological judgement to score. It supports three verification tasks and their metrics:

- **Category A — RETRACTED (7 cases):** the cited paper is retracted. Tests **retraction detection**.
- **Category B — SCOPE_MISMATCH (5 cases):** the claim asserts a human/clinical finding but the cited paper is animal-only by MeSH. Tests **species-scope mismatch detection**.
- **Category C — SUPPORTED (5 cases):** negative control — cited paper not retracted, scope matches, claim consistent with the source. Should **pass clean**. Measures **false-positive rate / specificity**.

Classes are roughly balanced (7 / 5 / 5) so per-class precision and recall are both meaningful.

## Data sources
1. **Retraction Watch database** (maintained by Crossref) — downloaded from the Crossref Labs API (`api.labs.crossref.org/data/retractionwatch`), 70,871 records. Fields used: `RetractionNature`, `Reason`, `RetractionDate`, `OriginalPaperPubMedID`, `OriginalPaperDOI`. This is the ground-truth source for Category A retraction status.
2. **PubMed** (via the PubMed MCP connector) — article metadata, primarily the **MeSH term list** (`mesh_terms`). MeSH organism check-tags (`Animals`, `Mice`, `Rats`, `Macaca mulatta`, `Zebrafish`, …) and population tags (`Adult`, `Aged`, `Middle Aged`, `Infant`, `Child`) are the ground-truth source for scope. Cited PubMed per connector terms of use; article DOIs are recorded in each case.
3. **OpenAlex** (via the literature MCP connector) — the citation graph (`openalex_citations`, papers that cite a given work) to find real citing papers, and the `is_retracted` flag (used to confirm Category C sources are NOT retracted).
4. **NCBI E-utilities EFetch (PMC)** — raw **JATS XML** full text of citing papers. Used instead of the connector's plain-text full text because JATS preserves inline `<xref ref-type="bibr" rid="…">` citation markers and the structured `<ref-list>`, which the plain-text rendering strips.

## How each case is built
1. **Pick a cited source** with a metadata-provable property (retracted per Retraction Watch; animal-only per MeSH; human + unretracted for controls).
2. **Find real citers** via `openalex_citations`, keep those with a **PMCID** (PMC open-access full text).
3. **Fetch the citer's JATS XML** from NCBI EFetch.
4. **Pin the citation by reference-id, not proximity.** Locate the `<ref>` in the citer whose `<pub-id pub-id-type="pmid|doi">` matches the cited source, giving its reference id (`rid`); then find every in-text `<xref rid="…">` pointing to that `rid`. **This makes the claim→cited-source link a structured-metadata match, not a text inference.**
5. **Extract the citing sentence verbatim.**
6. **Fabrication guard:** every stored claim is re-verified as a verbatim substring of the citer's whitespace-normalized full-text body. **All 17 cases pass** (`verbatim_verified=True`). Each row stores both `claim_text_verbatim` (exact, including inline `[n]` markers) and `claim_text` (same text with bracketed/parenthetical numeric citation markers removed for readability; no alphanumeric tokens — e.g. gene names — are ever altered).

## Ground-truth justification per category
- **Category A (RETRACTED):** justified directly by the Retraction Watch record (`RetractionNature='Retraction'`), with the verbatim `Reason` and `RetractionDate` carried in the row. **No inference** — `provenance_label = metadata-grounded`, `inference_flag = False`.
- **Category B (SCOPE_MISMATCH):** the **cited paper's animal-only scope is metadata-grounded** — the exact MeSH organism tags are recorded and `'Humans'` is absent. The **claim-side judgement** (whether the citing sentence over-generalizes the animal finding to humans/clinical use) is a **model reading of the claim wording** and is flagged `inference_flag = True`. Each row records the human/clinical scope markers the model relied on (`claim_scope_evidence`).
- **Category C (SUPPORTED):** **not-retracted** (OpenAlex `is_retracted=False`) and **human scope** (MeSH `Humans` + population tags) are metadata-grounded. That the claim is actually **supported** by the cited paper is a model judgement against the cited **abstract** and is flagged `inference_flag = True`.

## Metadata-grounded vs model-inferred split (honest accounting)
| Provenance | Count | Which part is grounded vs inferred |
|---|---|---|
| Fully metadata-grounded | 7 (all Category A) | Retraction status + citation linkage both from structured records |
| Has a model-inferred component | 10 (all B + C) | Cited-side fact (organism scope / retraction status) is metadata-grounded; the claim-side judgement (over-generalization / support) is model-inferred and flagged |

**Nothing in Category A depends on model judgement.** In B and C, the axis your tool must ultimately decide (does the claim over-reach / is it supported) is inherently a claim-reading task; those rows isolate the metadata-grounded cited-side fact from the model-inferred claim-side judgement so the two never blur. Every B/C row carries an `inference_note` stating exactly which half is which.

## Per-case provenance summary

### Category A — RETRACTED (retraction record is ground truth; all citers cite uncritically)
| case | cited PMID | cited title | retraction reason | retraction date | citer acknowledges retraction? | citing PMID |
|---|---|---|---|---|---|---|
| A01 | 22088800 | Cardiac stem cells in patients with ischaemic | Investigation by Company/Institution;U | 2019-03-14 | no | 24805242 |
| A02 | 22119609 | Tracheobronchial transplantation with a stem- | Criminal Proceedings;Ethical Violation | 2018-07-07 | no | 23973391 |
| A03 | 24837198 | MicroRNA-34A inhibits the growth, invasion an | Duplication of/in Image;Investigation  | 2023-04-21 | no | 26347258 |
| A04 | 25370920 | siRNA-mediated knockdown against NUF2 suppres | Author Unresponsive;Duplication of/in  | 2022-11-10 | no | 31139013 |
| A05 | 21339993 | RNA Interference Targeting Slug Increases Cho | Compromised Peer Review; | 2017-07-10 | no | 23177172 |
| A06 | 12169113 | Repeated Massage-like Stimulation Induces Lon | Error in Text;Euphemisms for Plagiaris | 2009-02-16 | no | 34777247 |
| A07 | 24969506 | ST-segment elevation myocardial infarction in | Error in Methods;Error in Results and/ | 2015-01-31 | no | 28270835 |

*Selection rule (per user):* claims were chosen to **rely on the specific retracted finding** (passing/methodological mentions dropped), and to be **uncritical** — the citer treats the retracted result as valid (the hard case for a detector). `citer_acknowledges_retraction` is `no` for all 7. Two sources are recognizable (Anversa/SCIPIO cardiac stem cells, PMID 22088800; Macchiarini tracheobronchial transplant, PMID 22119609); five are lower-profile. Reasons span fabrication, unreliable data, image duplication/paper-mill, compromised peer review, plagiarism, and methods/results error.

### Category B — SCOPE_MISMATCH (cited scope from MeSH; claim over-generalization model-judged)
| case | cited PMID | cited title | cited organism MeSH (Humans absent) | citing PMID |
|---|---|---|---|---|
| B01 | 17086191 | Resveratrol improves health and survival | ['Animals', 'Mice', 'Mice, Inbred C57BL'] | 23442817 |
| B02 | 17086191 | Resveratrol improves health and survival | ['Animals', 'Mice', 'Mice, Inbred C57BL'] | 18094749 |
| B03 | 19590001 | Caloric restriction delays disease onset | ['Animals', 'Macaca mulatta'] | 23860099 |
| B04 | 37311455 | Ketogenic diet promotes tumor ferroptosi | ['Mice', 'Animals'] | 39202500 |
| B05 | 37781508 | Tofacitinib Promotes Functional Recovery | ['Rats', 'Animals', 'Rats, Sprague-Dawley'] | 41839921 |

### Category C — SUPPORTED control (not retracted + scope match, both metadata-grounded)
| case | cited PMID | cited title | cited population MeSH | citing PMID |
|---|---|---|---|---|
| C01 | 25891173 | Pembrolizumab versus Ipilimumab in Advan | ['Adolescent', 'Adult', 'Aged', 'Ag | 32433532 |
| C02 | 34711976 | The SGLT2 inhibitor dapagliflozin in hea | ['Aged', 'Middle Aged'] | 36943925 |
| C03 | 33945288 | Pembrolizumab Plus Ipilimumab Following  | ['Adult', 'Aged', 'Aged, 80 and ove | 35326731 |
| C04 | 36175048 | Aspirin for Primary Prevention of Cardio | ['Aged'] | 36294361 |
| C05 | 25891173 | Pembrolizumab versus Ipilimumab in Advan | ['Adolescent', 'Adult', 'Aged', 'Ag | 27192565 |

## Confidence tiers
- **high** — Category A: ground truth is a direct external-record lookup.
- **medium** — Category B and C: cited-side fact is metadata-grounded, but the label also depends on a model reading of the claim (B: over-generalization; C: support), which a human annotator could occasionally score differently.

## Limitations (read before using)
1. **Claim-side scope/support in B and C is model-inferred**, not adjudicated against full text. For B, the tool's own job is to detect over-generalization; treat these as the intended target, but a strict reviewer may reclassify a borderline "general_unqualified" claim. For C, support is judged against the cited **abstract**, not the full paper — a claim consistent with the abstract is a reasonable but not exhaustive SUPPORTED label.
2. **Dose and other unverifiable axes are not covered.** Per project rules, only axes provable from structured metadata (retraction, MeSH organism/population) are used as ground truth. Dose mismatch, statistical misuse, and outcome-switching are out of scope for this set.
3. **PMC open-access bias.** Citing papers are limited to those with PMC full text (~44% of examined citers yielded a usable verbatim claim in the pilot). This biases the citer sample toward open-access journals; it does not affect ground-truth correctness.
4. **Population-axis Category B was not populated.** All 5 B cases are the species axis (animal→human). A pediatric-vs-adult population mismatch case was scoped but not included in this starter set; the same MeSH-tag machinery (`Infant`/`Child` vs `Adult`) supports adding them.
5. **Two Category C cases share one cited source** (pembrolizumab trial, PMID 25891173) with distinct claims and distinct citers. Acceptable for a control set; broaden if you want strict source-uniqueness.
6. **Retraction timing.** Category A ground truth is current retraction status. Several claims were published before the cited paper was retracted (legitimately, at the time) — this is realistic and is exactly what a retraction checker should still catch today. `retraction_date` is provided so you can model temporal logic if desired.

## Files
- `eval_set.csv` — the 17 cases, flat table (one row per case).
- `eval_set.json` — same cases with schema/label/provenance definitions for programmatic consumption.
- `candidate_sources.csv` — the wider candidate pool the final cases were drawn from.
- `pilot_yield.md` — the pre-build pilot yield report.
