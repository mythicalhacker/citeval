# RB2 — Claim-verification (supporter / refuter / critic) agent design

**Feeds:** Component 4 (adjudication). **Run after RB1's scale exists** (this brief
references those grades). Can run in parallel with RB3.

## The question

Design the concrete architecture of the adversarial adjudication agent: a **supporter** that
builds the strongest evidence-grounded case that the cited paper supports the claim, a
**refuter** that hunts for scope mismatch and disconfirming evidence, and a **critic** that
adjudicates them into a single graded verdict (RB1 scale) with a confidence and cited evidence
spans. Return the pipeline, the prompt skeletons, and the adjudication logic.

## Scope and sources to cover

- **Scientific claim verification pipelines**: retrieval + stance/entailment (SciFact/VeriSci,
  MultiVerS, ARSJoint, ClaimVer) — how they select evidence sentences and classify
  SUPPORT/REFUTE/NEI; where entailment framing helps and where it is too coarse for graded
  overreach.
- **Multi-agent / debate / self-critique**: debate and self-refine / self-consistency /
  "constitutional"-style critique loops — evidence on whether adversarial roles reduce
  confirmation bias and one-sided reasoning versus a single pass.
- **LLM-as-judge**: best practices and documented failure modes (position bias, verbosity
  bias, sycophancy, self-preference) — so the critic's rubric avoids them.
- **Evidence-grounding discipline**: forcing quoted spans, penalizing claims of support not
  tied to a span, and how to prevent the model inventing support ("evidence must be a verbatim
  span of the cited abstract/full text").

## Required deliverable (return exactly this)

1. **Pipeline diagram + I/O**: what each of supporter, refuter, critic receives (the grounded
   record from C2, the claim scope frame from C3, the cited abstract/full-text spans) and
   emits. All calls are Opus 4.8.
2. **Prompt skeletons** for each role (system role + task + required output schema), with the
   critical constraints baked in:
   - **Metadata-override as a hard constraint**: objective axes (retraction, species/population
     scope) are decided by C2's structured metadata and are given to the agents as *fixed
     facts they may not overturn*; the agents reason only about the substantive-support axis.
   - **Evidence-span requirement**: every support/refute point must quote a verbatim span of
     the cited source or be discarded.
   - **Refuter must specifically probe** scope over-generalization, direction reversal,
     magnitude inflation, and cherry-picking.
3. **Adjudication logic**: how the critic maps the supporter/refuter exchange onto the RB1
   grade + a confidence, and when it must output **abstain / NOT_ENOUGH_INFO** rather than force
   a grade (hand the confidence/abstention mechanism specifics to RB3, but state the interface).
4. **Determinism/repeatability**: sampling strategy (temperature, number of rounds/samples),
   and how repeated runs are made stable enough to score.
5. **Failure-mode mitigations**: concrete choices countering position/verbosity/sycophancy bias
   in the critic.

## Acceptance criteria

- On our eval cases: the refuter surfaces the species scope mismatch on the B-cases; the critic
  **defers to metadata** on retraction/scope (never "argues away" a grounded fact); the C-case
  controls are graded supported without a forced flag.
- Every verdict comes with ≥1 quoted evidence span (or an explicit "no supporting span found").
- Output conforms to the `Verdict` contract (per-axis findings + confidence + provenance) so it
  drops into C5/C6 unchanged.
