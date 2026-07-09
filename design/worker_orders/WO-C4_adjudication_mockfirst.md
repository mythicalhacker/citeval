# WO-C4 — Adjudication (mock-first)

**Owner:** Worker (Track D). Read `00_INDEX.md`. **Build against mocks now; finalize prompts and
grade boundaries when RB1–RB3 land.** This is the intellectual core and the calibration
make-or-break — scaffold it correctly so the research drops in without reshaping the interface.

## Objective

Build `src/citeval/adjudicator.py` exposing `adjudicate(grounded, scope) -> Verdict` — an
adversarial **supporter / refuter / critic** pipeline (all **Opus 4.8**) that grades the
substantive-support axis and attaches a confidence, while treating objective axes as fixed
metadata facts.

## Contract

- **In:** `GroundedRecord` + `ScopeFrame`. **Out:** `contracts.Verdict` — same shape the stub
  emits, but `substantive_support` becomes a real graded verdict (RB1 scale) with a confidence,
  and may be `NOT_ENOUGH_INFO` (abstention).
- Drop-in replacement for `adjudicator_stub.adjudicate_stub` at the runner seam.

## Behavior (scaffold now, fill from research)

- **Supporter:** strongest evidence-grounded case for support; every point quotes a verbatim
  span of the cited abstract/full text.
- **Refuter:** hunts scope over-generalization, direction reversal, magnitude inflation,
  cherry-picking; quotes spans.
- **Critic:** maps the exchange to the RB1 grade + confidence; **defers to C2 metadata on
  objective axes and may not overturn them** (metadata-override as a hard constraint injected
  into the prompt).
- **Axis boundary (CONTEXT_PACK §6):** `substantive_support` grades substance **holding scope
  constant** (effect/mechanism/direction/magnitude/certainty) — it does not up/down-grade for
  species/population/dose. Scope is carried by the metadata-grounded scope axes; the refuter may
  *note* scope-framing overreach but it flows to `overall` via a **swappable rollup**, not by
  depressing the graded number. Default rollup: retraction or scope mismatch gate `overall` to
  "not supported as stated" regardless of the substantive grade.
- **Confidence + abstention:** per RB3 (e.g. self-consistency agreement across N rounds +
  verbalized cross-check; abstain below threshold). Record abstentions so they are not scored as
  wrong.
- Keep prompts in a `prompts/` module so RB2's finalized prompts and RB1's grade boundaries slot
  in without touching the pipeline wiring.

## Deliverables

- `src/citeval/adjudicator.py` + `src/citeval/prompts/` (supporter/refuter/critic).
- `tests/test_adjudicator.py` using **mocked** `GroundedRecord`/`ScopeFrame` fixtures and a mocked
  model client (no live API in CI).

## Acceptance criteria (mock stage)

- Given a mock animal-only grounded record + a Humans scope frame, the critic does **not**
  overturn the metadata species fact and returns a graded substantive verdict + confidence.
- Given an ambiguous fixture, it **abstains** (`NOT_ENOUGH_INFO`).
- Output validates against `Verdict`; drops into C5/C6 unchanged.

## Manager decisions (2026-07-09)

- **Objective-axis SSOT — extract, don't import-privates and don't duplicate.** Move
  `_retraction_axis` / `_species_axis` / `_population_axis` + the `unverifiable_axes` construction
  out of `adjudicator_stub.py` into a new shared `src/citeval/objective_axes.py`; both the stub and
  the real adjudicator import it. Single source of truth for the metadata-override logic, no
  cross-module private imports, and it survives the stub's eventual retirement. This
  behavior-preserving refactor may touch `adjudicator_stub.py` — **keep `adjudicate_stub`'s public
  signature** so `slice_runner`/scorer stay green; re-run the scorer to confirm.
- **Confidence scaffold defaults (PROVISIONAL, RB3 tunes jointly):** `SELF_CONSISTENCY_ROUNDS = 5`,
  `ABSTAIN_AGREEMENT_THRESHOLD ≈ 0.6`. The critic (not the full exchange) runs N times over the
  fixed grounded evidence; modal grade + agreement fraction.
- **Evidence keys:** populate the `substantive_support` `AxisFinding.evidence` with the exact keys
  in CONTEXT_PACK §6 (`confidence`, `calibration`, `supporter{span,point}`, `refuter{span,objection}`,
  `abstained`) so C5 renders you without a fixup. Richer `supporter_points` / `refuter_points` lists
  are optional additions; the §6 single-object keys are the C5-facing headline.
- **Grounding corpus:** title + abstract for now (full-text spans slot in later) — record it as a
  known limitation in the module docstring.
- **Added deliverable:** `src/citeval/objective_axes.py` (plus the behavior-preserving stub edit).

## Out of scope / do not touch

`contracts.py`, C2 metadata logic. Do not finalize grade thresholds until RB1/RB3 return — leave
them as clearly-marked constants.
