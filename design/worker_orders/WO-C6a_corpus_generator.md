# WO-C6a — Corpus generator (Claude Science)

**Owner:** Claude Science session. **Design authority:** this Cowork session (me) — check
rubric-boundary calls with me. Independent track; **needs no research** for the objective tier.

## Why Claude Science
The original extraction notebook (`src/reference/notebook_snippets.py`) ran in Claude Science via
`host.mcp("pubmed"/"openalex", ...)`. Those connectors are native there, so the crown-jewel
functions (`efetch_pmc_xml_cached`, `find_rids_for_source`, `sentences_citing`, verbatim guard)
run with minimal changes — no re-pointing to REST. Path of least resistance for the scaled harvest.

## Objective
Grow the objective-axis corpus well past the 17-case starter, with **metadata-grounded** labels,
fixing the known eval-set defects. Emit cases in the **`eval_set.json` schema** so the scorer
consumes them directly.

## Output contract (one JSON object per case; schema = `eval_set.json`)
`case_id, category (A|B|C), claim_text, claim_text_verbatim, claim_source_pmid/doi/pmcid,
cited_pmid/doi/title/journal, ground_truth_label (RETRACTED|SCOPE_MISMATCH|SUPPORTED),
mismatch_axis ("species"|"population"|""), justifying_metadata (exact MeSH list or RW record
fields), retraction_reason/date (A only), citer_acknowledges_retraction (A only), confidence_tier,
provenance_label, inference_flag, inference_note, verbatim_verified (must be true)`.
**Do not** produce the graded substantive-support label — C4 adds it later. This is the objective
tier plus the case set the graded tier will reuse.

## Pipeline (per seed source)
1. **Seeds:** A from `data/retraction_watch/retraction_candidates.parquet` (genuine retractions w/
   PMID); B/C from MeSH-qualified papers (see rubric).
2. OpenAlex `openalex_citations` → citing works; keep those with a **PMCID**.
3. EFetch **PMC JATS XML** (raw); match `<ref>` `pub-id` to the seed → `rid`; extract each in-text
   `<xref rid>` sentence verbatim.
4. **Verbatim guard:** claim must be a verbatim substring of the citer's whitespace-normalized full
   text — reject otherwise.
5. Assign objective labels from metadata (below); record provenance + inference flags.

## Selection & labeling rubric (the §6 fixes — non-negotiable)
- **Scope by MeSH tree number, not string sets:** organism = tree `B*`, population/age =
  `M01.060*` (reuse the approach in `src/citeval/grounding.py`; `efetch db=mesh`). Do **not**
  resurrect the notebook's hardcoded `ANIMAL`/`POP` sets.
- **Category A:** the claim must **depend on the specific retracted finding** — drop passing /
  methodological mentions. Prefer **uncritical** citations (citer treats the result as valid); set
  `citer_acknowledges_retraction`. Prefer lower-profile retractions (avoid the most infamous —
  too easy); diversify retraction reasons.
- **Category B:** label `SCOPE_MISMATCH` **only if the citing claim actually attributes the
  animal-only finding to humans/clinical use.** EXCLUDE correctly-scoped ("in mice") and hedged
  ("whether this holds in humans is unknown") citers — those are correct, not mismatches. Record
  the human/clinical scope markers relied on (explicit = text-grounded; interpretation =
  model-inferred, flagged). **Populate BOTH axes:** species (animal-only cited, human claim) AND
  **population** (adult-only cited — Adult/Aged/Middle Aged, no Infant/Child — with a pediatric
  claim, or the reverse). The population axis is currently empty; add **≥10**.
- **Category C (controls):** include **hard negatives**, not just easy ones — a human claim citing
  a human study whose abstract also mentions mice; a well-supported human claim citing a paper with
  sparse/messy MeSH. Verify OpenAlex `is_retracted=false` AND cited MeSH scope matches the claim.
- **Source diversity:** no single cited source > ~20% of any class.
- **Model calls are Opus 4.8.** Every classification/labeling call (relies-on-finding for A, the
  claim-scope classifier for B-species, the population-scope classifier for B-population, the
  support check for C) runs on `claude-opus-4-8`. Invariant #4 covers *any classifier or labeler* —
  and a weaker labeler would mislabel the B over-generalizations and corrupt the corpus, which is
  exactly the failure the brief warns against.

## Targets (scale as yield allows; pilot yield ~44% of PMC citers)
~20–30 A · ~20–30 B-species · **≥10 B-population** · ~15 C-easy · **~15 C-hard**. Balance so
per-class precision/recall are meaningful.

## Operational
Checkpoint per seed (resumable); rate-limit NCBI (api_key + email); log yield per source (like
`pilot_yield.md`).

## Deliverables (bring back HERE)
- `corpus/corpus_objective.jsonl` (cases in the schema above).
- `corpus/methodology_corpus.md` (sources, §6-fix rules applied, per-class counts, source-diversity
  check, honest limitations).
Bring both to this Cowork session; I run `python -m citeval.scorer --corpus
corpus/corpus_objective.jsonl` and integrate — same "bring it here" rule as the research reports.

## Acceptance criteria
- Every case `verbatim_verified=true`; objective label justified by a cited metadata field.
- B excludes correctly-scoped/hedged citers; population axis ≥10.
- C includes ≥10 hard negatives; no source > ~20% of a class.
- File loads cleanly into the scorer and produces a per-axis scorecard.

## Out of scope / do not touch
No graded substantive-support label (C4's job). No plain-text full-text connector (strips
`<xref>`). Do not change `contracts.py`.
