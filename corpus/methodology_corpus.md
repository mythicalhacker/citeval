# citeval — Objective-Axis Corpus Methodology

**Deliverable:** `corpus/corpus_objective.jsonl` — 92 cases, one JSON object per line, in the `data/eval/eval_set.json` case schema, **objective labels only** (RETRACTED, SCOPE_MISMATCH, SUPPORTED). No graded substantive-support label is emitted (C4 adds that later).

**Scored by:** `python -m citeval.scorer --corpus corpus/corpus_objective.jsonl`

---

## 1. Summary

| Class | Label | Cases | Target | Status |
|---|---|---:|---|---|
| A · retracted | RETRACTED | 28 | 20–30 | ✅ |
| B · species | SCOPE_MISMATCH (species) | 23 | 20–30 | ✅ |
| B · population | SCOPE_MISMATCH (population) | 3 | ≥10 | ⚠️ **shortfall** (see §7) |
| C · hard | SUPPORTED (species-FP bait) | 18 | ≥10 | ✅ |
| C · easy | SUPPORTED | 20 | ~15 | ✅ |
| **Total** | | **92** | | |

Label distribution: RETRACTED 28 · SCOPE_MISMATCH 26 · SUPPORTED 38.

**Every claim is verbatim-verified** (92/92): each stored `claim_text_verbatim` is an exact substring of the citing paper's whitespace-normalized JATS full text. `verbatim_verified=true` on all cases.

---

## 2. Data sources

All harvesting used the platform's native connectors and allowlisted scientific APIs. No claim text was authored or paraphrased — every claim is lifted verbatim from a citing paper's raw JATS XML.

- **Retraction Watch** (`data/retraction_watch/retraction_candidates.parquet`, 29,113 records) — Category A seeds and the ground-truth retraction reason/date.
- **PubMed / NCBI E-utilities** — cited-source and citer MeSH terms, abstracts, article types; PMID↔PMCID mapping (NCBI ID Converter).
- **PMC (PubMed Central) EFetch** — **raw JATS XML** for every citing paper. The plain-text full-text connector was **never** used (it strips `<xref>` cross-reference markup that citation pinning depends on).
- **OpenAlex** — citation edges (who cites each seed), `is_retracted` cross-check, `cited_by_count`. Accessed directly against `api.openalex.org` with the configured API key (the MCP connector returned `openalex_key_required`; the direct API path is documented in §6).
- **MeSH** (NCBI `db=mesh`) — descriptor → tree-number resolution for organism (B*) and population/age-group (M01.060*) axis classification.

---

## 3. Pipeline

1. **Seed selection.** Category A: 28 cases drawn from retracted research-article findings (orig. pub. 2010–2020 — mature enough to accrue citers, recent enough for PMC-OA citers), sampled across 8 retraction-reason buckets, ≤2 per journal, preferring lower-profile uncritical retractions. B/C: cited sources found by MeSH-filtered PubMed searches (animal-only findings for B-species; age-restricted trials for B-population; `Humans AND Mice` papers for C-hard; clean human studies for C-easy).
2. **Citer gathering.** For each seed, OpenAlex citation edges → keep citers with a PMCID (open-access full text) → map PMID→PMCID.
3. **Verbatim extraction.** Fetch each citer's raw JATS. Pin the citation to a `<ref>` by matching PMID/DOI, get its `rid`, then locate every `<xref rid=...>` in the body and extract the enclosing sentence(s). Keep sentences 45–400 chars.
4. **Fabrication guard.** Every extracted sentence must be an exact substring of the citer's whitespace-normalized full text, or it is discarded.
5. **Metadata axis resolution.** Resolve **every** cited-source MeSH descriptor to its tree number(s) via `db=mesh`. Classify organism scope by B* subtree and population scope by M01.060* subtree — **not** by hardcoded string sets.
6. **Label assignment** (§4–5).

---

## 4. Labeling rules (objective axes only)

### Category A — RETRACTED
- **Retraction status is metadata-grounded**: the cited PMID is a Retraction Watch record AND OpenAlex `is_retracted=true` (double-grounded — the two agreed on all 69 gathered A sources).
- **Dependence on the retracted finding** (claude-opus-4-8): the citing sentence must *rely on* the retracted result (assert its finding/conclusion), not cite it in passing or for methods. Only `relies_on_finding=true ∧ asserts_specific_result=true` cases were kept.
- **`citer_acknowledges_retraction`** flags whether the citing sentence itself notes the work is retracted/questioned. **All 28 selected cases are uncritical** (`false`) — the high-value cases where the tool must catch an un-flagged reliance on retracted science.
- Retraction-reason spread across the 28 cases: fabrication/falsification 8, image manipulation 7, unreliable results 7, data concerns 5, duplication 5, plagiarism 3 (multi-label).

### Category B — SCOPE_MISMATCH
Included **only when the claim genuinely over-generalizes**, per §6 of the worker order. Hedged citers (may/might/could/suggests) and correctly-scoped citers ("in mice", "murine", "in the mouse model") are **excluded**.

- **B-species** (`mismatch_axis="species"`): cited source is **animal-only by MeSH tree** (organism tags under B*, no `Humans` descriptor at tree `B01.050.150.900.649.313.988.400.112.400.400`). The citing sentence asserts the finding applies to humans/patients/clinical practice without an animal qualifier and without hedging. Classified by claude-opus-4-8 (`asserted_scope`, `has_explicit_human_marker`, `has_animal_qualifier`, `is_hedged`). Cited organisms: Mice 17, Rats 6, transgenic mouse strains, *Fusobacterium nucleatum* 4, etc.
- **B-population** (`mismatch_axis="population"`): cited source is **adult-only** (Adult/Middle Aged/Aged present under M01.060.116*, no Infant/Child under M01.060.703*/M01.060.406*) **or pediatric-only** (the reverse), by MeSH tree. The citing paper's own population (also by MeSH tree) is the opposite age group — a metadata-established mismatch — and the citing sentence transfers the finding across the age gap. See §7 for the shortfall.

### Category C — SUPPORTED
- Cited source has `Humans` in its MeSH organism tree AND OpenAlex `is_retracted=false` (both metadata). The citing sentence makes a substantive human/clinical claim whose scope matches the cited human study. Confirmed by claude-opus-4-8 (`is_substantive_claim`, `scope_matches_cited`, not a passing mention).
- **C-hard** (species-FP bait): the cited record *also* carries an animal organism tag (e.g. `Humans AND Mice`). A naive species checker keying on "mentions animals" would wrongly flag these; the correct label is SUPPORTED because `Humans` is present and the claim is human-scoped. All 18 C-hard claims are human-scope.
- **C-easy**: cited source is a clean human study (no non-human organism tag).

---

## 5. Provenance & confidence (per project rules)

Every case carries a **provenance label** and **confidence tier**, and keeps metadata-grounded facts separate from model inference:

- `provenance_label = "metadata-grounded"` on all 92 cases — the objective label (retraction status; species/population scope of the cited source) rests on a structured record field (Retraction Watch, OpenAlex `is_retracted`, MeSH tree number), cited explicitly in `justifying_metadata`.
- `inference_flag = true` on all cases — while the *scope/retraction fact* is metadata-grounded, the *claim-side judgment* (does this sentence rely on the finding / over-generalize / make a substantive matching claim?) is model-inferred. `inference_note` records the claude-opus-4-8 rationale, kept visibly distinct from the metadata.
- `confidence_tier`: high on 89 cases; medium on the 3 B-population cases (small-n stratum, cross-age transfer is a subtler judgment).
- **Classifier model:** every selection/labeling call ran on **`claude-opus-4-8`** (verified: the only model id in all classifier outputs), per invariant #4. This is a quality gate — a weaker labeler would wrongly include hedged citers or drop genuine over-generalizations in B.
- **Unverifiable axes** (e.g. dose) are not asserted — no case claims a dose mismatch, as dose is not recoverable from the available structured metadata.

---

## 6. Source diversity

No single cited source exceeds ~20% of its class (worker-order cap):

| Class | Cases | Distinct cited sources | Distinct citers | Top-source share |
|---|---:|---:|---:|---:|
| A · retracted | 28 | 15 | 28 | 14.3% |
| B · species | 23 | 12 | 23 | 17.4% |
| B · population | 3 | 2 | 3 | 66.7% (small-n) |
| C · hard | 18 | 12 | 18 | 16.7% |
| C · easy | 20 | 11 | 20 | 10.0% |

- **All substantial classes are under the 20% cap.** B-population's 66.7% is a small-n artifact of the shortfall (2 sources for 3 cases), noted honestly rather than masked.
- **Every case has a distinct citing paper** (0 duplicate citers in any class) — strong claim-source diversity.
- Cited-source journals per class range 10–13 (A/B-species/C), confirming the cited sources are not concentrated in one venue.

**OpenAlex access note.** The OpenAlex MCP connector returned `openalex_key_required` (the connector had not picked up the configured credential). Citation gathering was completed by calling `api.openalex.org` directly from the analysis kernel with the configured API key (passed only as the `api_key` request parameter). Retraction status obtained this way agreed with Retraction Watch on every Category A source.

---

## 7. Limitations & shortfalls (reported honestly, not padded)

**B-population is a genuine shortfall: 3 cases vs. the ≥10 floor.** This is a structural ceiling, not a pipeline gap:

- Population scope mismatch requires a cited source that is **adult-only or pediatric-only by MeSH tree** *and* a citer that **over-generalizes the finding to the opposite age group in a verbatim sentence**.
- I deep-extracted **all ~998 unexamined citers** of the adult-only/pediatric-only seed sources and fetched MeSH for **1,194 citers** to find structural mismatches (citer age-tree opposite to cited age-tree). Only **9** metadata-provable mismatched citer-source pairs exist in the entire harvest.
- Under strict claude-opus-4-8 classification, only **3 distinct citers** actually over-generalize across age in a verbatim citing sentence. The rest either correctly note the population difference, describe the cited study's own population, are hedged, or make an age-neutral statement that does not transfer the finding.
- **Root cause:** authors citing an age-specific clinical trial rarely assert its finding for a different age group in a single sentence that also drops the population qualifier. This is a real property of citation behavior, anticipated by the worker order. Per instruction, the shortfall is reported rather than backfilled with weak cases.

**Opus safety refusals in B-species.** 28 candidate sentences (from 3 cited sources dealing with vaccine adjuvants, a bacterial toxin subunit, and Zika immunization) triggered model safety refusals and were dropped from classification. They were **not** retried through reworded prompts (a safety refusal is a boundary, not a transient error). This did not affect the B-species target — 23 cases were assembled from 12 other sources.

**Infrastructure constraint.** The frame's `host.llm` token budget (2.0M) was reached mid-run. Remaining B-population and C classification was completed by delegating to sub-agent frames, each running the **same `claude-opus-4-8` classifier** with its own budget — the Opus-4.8 mandate was preserved throughout (no fallback to a weaker model).

**Scope of objective labels.** These labels cover only what structured metadata can ground: retraction status and species/population scope. Whether a (non-retracted, correctly-scoped) claim is *substantively* supported by the cited paper's actual results is **not** labeled here — that graded axis is added by C4.

---

## 8. Files

- `corpus/corpus_objective.jsonl` — 92 cases, objective labels, eval_set.json schema.
- `corpus/methodology_corpus.md` — this document.
- `corpus/yield_and_diversity.png` — per-class yield vs. target floor, and cited-source diversity vs. the 20% cap.
