# CLAUDE.md — `citeval` (citation-verification system)

## What this is
Given a scientific claim + the paper cited to support it, decide whether the paper actually
supports the claim: detect **retraction**, **species/population scope mismatch**, and grade
**substantive over-reach** — with every verdict carrying a **confidence tier** and a **provenance
label** (metadata-grounded vs model-inferred), proven by a **scored eval corpus**.

**Thesis (shapes every decision):** *grounded-and-measured, not model-checks-model.* We grade
against external structured ground truth (Retraction Watch, MeSH organism/population tags keyed on
tree number, NCBI), run adversarial adjudication, grade deviation on a scale, and prove it with a
scored corpus. If a choice trades provable grounding for impressive-looking model output, it is the
wrong choice.

## Non-negotiable invariants (enforce structurally, not by convention)
1. **Metadata overrides model** on objective axes (retraction, species/population scope). A model
   value never overturns a structured record; a conflict is scored as the model being wrong.
2. **Every axis finding carries `tier` + `provenance`** (`metadata-grounded | text-grounded |
   model-inferred | stub-not-adjudicated`; composites allowed).
3. **Unverifiable axes (e.g. dose) are flagged, never fabricated.**
4. **Opus 4.8 on every model call.** No cheaper/faster model anywhere.
5. **Verbatim guard:** any stored claim must be a verbatim substring of the citing paper's
   whitespace-normalized full text.
6. **Raw JATS XML from NCBI EFetch** for citation context — never the plain-text connector (strips
   `<xref>`).
7. `substantive_support` grades substance **holding scope constant**; scope lives on its own axes;
   `overall` is a swappable rollup. See `design/research_briefs/CONTEXT_PACK.md` §6.

## Repo map (canonical locations)
- `src/citeval/` — the package. `contracts.py` = **FROZEN** shared types (never edit across a
  contract). Built: `grounding.py` (C2), `reporting.py` (C5 base), `scorer.py` (C6b),
  `adjudicator_stub.py` (C4 stub), `claim_scope.py` (C3-lite), `slice_runner.py`, `build_rw_index.py`.
- `src/reference/notebook_snippets.py` — ported extraction code to reuse (JATS ref-match, verbatim guard).
- `data/eval/eval_set.json` — 17-case starter (**demo fixture + schema reference, NOT the corpus**).
- `data/retraction_watch/retraction_candidates.parquet` — ~29k genuine retractions.
- `data/schemas/{grounded,verdict}.json` — proven output-shape examples.
- `design/` — living specs: `01_dependency_graph.md`, `03_thin_slice_contracts.md`,
  `04_component_contracts.md`; `worker_orders/` (build orders + `00_INDEX.md`); `research_briefs/`
  (RB1–3 + `CONTEXT_PACK.md` + `results/`).
- `outputs/` — generated (scorecard, slice reports); gitignored. `corpus/` — C6a output lands here.
- `docs/` — background (methodology, pilot, source extractions).

## Run
```bash
cd src
python -m citeval.build_rw_index       # once; builds RW index from data/retraction_watch parquet
python -m citeval.slice_runner --demo  # end-to-end on A01/B01/C01 with built-in verification
python -m citeval.scorer               # scored harness run over data/eval/eval_set.json
```
Set `NCBI_EMAIL` / `NCBI_API_KEY` for higher NCBI rate limits. MeSH tree cache persists in
`src/citeval/.cache/` (never cached on fetch failure).

## Status / ownership
- **Built & green:** C2 grounding, C5 reporting (base), C6b scorer, C4 stub, C3-lite. Slice passes.
- **Worker tracks** (build against contracts, own your module, don't touch `contracts.py`): C1
  ingestion, C3 scope (Opus), C5 reporting (extend), C4 adjudicator (mock-first). See
  `design/worker_orders/`.
- **C6a corpus → Claude Science** (`WO-C6a`). **Research RB1–3 → separate sessions**; results to
  `design/research_briefs/results/`. The manager (Cowork session) integrates on `main`.

## Working rules for a build session
- Read your work-order in `design/worker_orders/` + `CONTEXT_PACK.md`. Build **only your module**.
- Work on your own git worktree/branch; the manager merges to `main`.
- Definition of done: your unit tests pass **and** `python -m citeval.scorer` still runs (no regression).
- If you think a **contract** must change, STOP and raise it — that is a manager decision.
