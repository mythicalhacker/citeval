# Deep-research briefs — how to run them

These are **standalone** research tasks. You run each in a **separate Claude session**
(ideally invoking the `deep-research` skill), then bring the result back here and I
integrate it into the named component before Claude Code implements. I orchestrate and
consume the research; I do not run it.

Each brief states: the question, the scope/sources to cover, the concrete deliverable it
must return, the component it feeds, and acceptance criteria (how we know the output is
good enough to build on).

## Order

1. **RB1 — Graded deviation rubric** (run first). Defines the label space for the
   substantive-support axis; both the adjudication agent (RB2) and the corpus rubric
   depend on it.
2. **RB2 — Claim-verification agent design** and **RB3 — Calibration** can run in
   **parallel** once RB1's scale exists (RB2 and RB3 both reference the grades RB1 defines,
   but not each other).

## How to run one

Open a new session and paste the brief's body. If the `deep-research` skill is available,
prefix with: *"Use the deep-research skill to answer the following, and return the exact
deliverable specified."* Return the full report here; I'll reconcile it against the
component contract and flag anything that changes the design.

## Why these three

They are the make-or-break of the intellectual core (component 4) and its proof
(component 6). The objective axes (retraction, species/population scope) are already
grounded and working in the slice; these briefs de-risk the one axis that is inherently a
judgement — how much a claim over-reaches its source — and the calibration that keeps that
judgement honest rather than confidently wrong. Expect to spawn follow-up briefs as the
design surfaces gaps; this is a seeded series, not a fixed set.
