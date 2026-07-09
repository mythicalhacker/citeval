# WO-C5 — Reporting (extend)

**Owner:** Worker. Read `00_INDEX.md`. Extend the slice's `src/citeval/reporting.py` (already
implemented) — do not rewrite its contract.

## Objective

Extend reporting to render the **graded substantive-support** verdict and its **confidence /
calibration** once C4 produces them, and add a **bring-your-own-paper** live rendering, while
keeping the metadata-grounded vs model-inferred distinction legible at a glance.

## Contract

- **In:** `Verdict` (+ `GroundedRecord`, `ScopeFrame`, `ClaimUnit`). **Out:** markdown + machine
  JSON (existing) plus an **HTML** report option.
- Additive only: existing `render_markdown` / `render_json` signatures stay valid.

## Behavior

- Render the `substantive_support` axis with its RB1 grade, RB3 confidence, and a one-line
  calibration note (e.g. "high-confidence verdicts are empirically N% accurate on the corpus").
- Show the adversarial trace succinctly: the supporter's best supporting span and the refuter's
  strongest objection, each as a quoted span.
- BYO-paper mode: a compact top summary (claim, cited paper, overall) then the per-axis table.
- Keep the provenance legend and the "metadata overrides model" note.

## Deliverables

- Extended `src/citeval/reporting.py` (add `render_html`; extend markdown for the graded axis).
- `tests/test_reporting.py` snapshot tests over a fixture `Verdict` incl. a graded axis.

## Acceptance criteria

- Given a `Verdict` whose `substantive_support` is a real grade + confidence, the report shows
  the grade, the confidence, quoted supporter/refuter spans, and the calibration note.
- Objective axes still render as metadata-grounded; unverifiable axes still listed.
- HTML and markdown carry the same information.

## Out of scope / do not touch

Do not compute verdicts here (rendering only). Do not change `contracts.py` or upstream modules.
