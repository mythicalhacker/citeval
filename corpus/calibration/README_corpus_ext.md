# Citation-Verification Corpus Extension

**Deliverables:** `corpus_cal_ext.jsonl` (45 cases) + `graded_reference_ext.jsonl` (45 grades)
Schemas are byte-identical in key set and order to the seed `corpus_cal30.jsonl` / `graded_reference_v2.jsonl`.

## What each case is
A **claim** (a verbatim sentence from a real open-access citing paper) paired with the **cited paper**,
plus an externally-grounded `ground_truth_label`, and — in the grades file — a **blind substantive grade**
of how well the cited paper's *finding* supports the claim.

## How ground truth was established (metadata-grounded, not model judgment)
- **RETRACTED (12 cases):** confirmed on **Retraction Watch** (RW record ID + reason + date) **AND**
  cross-checked against **NCBI PubMed** ('Retracted Publication' article type) **AND** OpenAlex `is_retracted`.
  Every A-case is triple-confirmed; RW record IDs and retraction dates are in `justifying_metadata`/`retraction_*`.
- **SCOPE_MISMATCH — species (12):** cited paper classified **animal-only** from **MeSH organism descriptors**
  via NCBI MeSH **tree numbers** (under B01.* organism branch, lacking the Humans tree
  B01.050.150.900.649.313.988.400.112.400.400). The over-generalization judgment (claim presents an animal
  finding as human/general fact, unqualified and unhedged) is a **separate, model-inferred** axis.
- **SCOPE_MISMATCH — population (5):** cited paper classified **pediatric-only / pregnancy-only** from
  **MeSH age check-tags** (tree M01.060.*). Cross-age over-generalization is model-inferred.
- **SUPPORTED (16):** cited paper carries the **Humans** MeSH descriptor and is not retracted. Split into
  **clean controls (10)** and **hard negatives (6)** — the latter also carry an animal organism tag
  ("species-FP bait") but the human claim is correctly scoped, testing against false species-mismatch flags.

Every verdict carries `confidence_tier` + `provenance_label='metadata-grounded'` + `inference_flag`, with
`inference_note` explicitly separating the **metadata-grounded** fact from the **model-inferred** judgment.

## How substantive grades were produced (blind, scope-held-constant)
Each cited paper's full text (or abstract when full text is not open-access) was read by a blind grader
(reasoning model) under one overriding rule: **grade the finding's substance ONLY — never lower a grade
because the paper is the wrong species/population/dose or is retracted.** Those are separate axes.
6-level scale (best→worst, first boundary test that fires wins): fully-supported / supported-with-overreach /
partially-supported / technically-true-but-misleading / unsupported-for-the-claim / contradicted;
off-scale: N/A — non-substantiating, NOT_ENOUGH_INFO. Each grade has a **verbatim `decisive_span`**
(exact substring of the cited text; empty only for absent-evidence grades), a rationale, and a
`grader_confidence`. `grade_provenance` records full-text vs abstract-only.

The scope-constant rule is demonstrable in the corpus: retracted papers (A-cases) and wrong-species
papers (Bs-cases) receive fully-supported / partially-supported grades wherever the *substance* holds.

## Verbatim guarantee
All 45 `claim_text_verbatim` strings are exact substrings of their citing paper's rendered full text
(`verbatim_verified=true`). All non-empty `decisive_span` strings are exact substrings of the cited text.

## Composition
- Cases: 45 | distinct citing papers: 38 | distinct cited papers: 45
- Category: {'A': 12, 'B': 17, 'C': 16}
- Ground truth: {'RETRACTED': 12, 'SCOPE_MISMATCH': 17, 'SUPPORTED': 16}  (axis: {'species': 12, 'population': 5})
- case_id families: {'A': 12, 'Bs': 12, 'Bp': 5, 'Ce': 10, 'Ch': 6}  (A=retracted, Bs=species, Bp=population, Ce=clean control, Ch=hard negative)
- Substantive grades: {'unsupported-for-the-claim': 9, 'supported-with-overreach': 7, 'fully-supported': 14, 'partially-supported': 7, 'NOT_ENOUGH_INFO': 4, 'contradicted': 2, 'N/A — non-substantiating': 2}
- Grader confidence: {'high': 22, 'medium': 22, 'low': 1} | provenance: {'llm-fulltext-claude-science': 24, 'llm-abstract-only-claude-science': 21}
- Domains (17, all beyond oncology/stem-cell): {'endocrinology': 2, 'gastroenterology': 3, 'hematology': 4, 'microbiome': 5, 'ophthalmology': 2, 'psychiatry': 1, 'pulmonology': 5, 'reproductive': 6, 'cardiology': 1, 'dermatology': 3, 'immunology': 2, 'nephrology': 3, 'rheumatology': 3, 'bone': 1, 'infectious_bacterial': 1, 'neuroscience': 2, 'pain': 1}

## Sourcing
Claims mined from open-access **review** papers (PubMed Central JATS) across 18 searched clinical/biomedical domains (the 45 selected cases span 17 of them);
sentences with exactly one citation marker resolving to a cited PMID were kept and verbatim-verified.
Cited-paper metadata from NCBI E-utilities (PubMed + MeSH) and OpenAlex; retractions from Retraction Watch.

## Reproducibility note
A DOI-parsing bug was caught and fixed during validation: 17/45 cited DOIs were initially extracted from
reference-list entries instead of the article-level DOI. All cited DOIs now come from `Article/ELocationID`
or `PubmedData/ArticleIdList` and were re-verified against title/journal. The fix is in `citation_toolkit.py`.
