# RB1 — The graded deviation rubric

**Feeds:** Component 4 (the `substantive_support` axis label space) and Component 6a (the
graded-corpus labeling rubric). **Run first.**

## The question

When a scientific claim cites a paper, the relationship between claim and cited finding
ranges from fully supported to flatly contradicted. We need a **concrete, ordinal, well-bounded
grading scale** for that relationship, with criteria sharp enough that two careful graders
(or the agent and a human spot-checker) apply it the same way. Produce that scale and its
boundary definitions.

## Scope and sources to cover

Ground the scale in how the scholarly literature already characterizes citation–source
mismatch. Cover, at minimum:

- **Citation accuracy / quotation-error literature** (biomedical): the standard taxonomy of
  citation errors — quotation errors (major/minor), where a citation does not substantiate
  the claim. (e.g., work following Evans/de Lacey, and citation-accuracy review methods.)
- **Citation distortion / "citation as amplifier"** (e.g., Greenberg's work on how
  unsupported claims propagate) — how overreach is characterized beyond binary error.
- **"Spin" / overinterpretation literature** (e.g., Boutron and colleagues on spin in
  abstracts and press releases) — the vocabulary for "technically true but misleading."
- **Scientific claim-verification datasets and their label sets**: SciFact, HealthVer,
  Cochrane/CLIMATE-FEVER, FEVER — how they define SUPPORTS / REFUTES / NOT ENOUGH INFO, and
  where a 3-way label is too coarse for over-reach.
- **Evidence-grading indirectness**: GRADE / systematic-review notions of *indirectness*
  (population, intervention, outcome) — this maps directly onto our scope axes and gives a
  principled way to grade "right finding, wrong population/dose."

## Required deliverable (return exactly this)

1. A **5–7 point ordinal scale** (proposed anchor set to react to, refine, or replace:
   `fully-supported` · `supported-with-overreach` · `partially-supported` ·
   `technically-true-but-misleading` · `unsupported` · `contradicted`), each with:
   - a one-sentence definition,
   - **inclusion criteria** and **exclusion criteria** (what puts a case in this grade vs the
     neighbor above/below),
   - 2–3 **worked biomedical examples** (claim sentence + one-line cited finding).
2. **Boundary decision rules** for the hard adjacencies, especially
   `supported-with-overreach` vs `partially-supported` vs `technically-true-but-misleading`.
3. Explicit handling of the two known traps:
   - **Hedged / correctly-scoped citation is NOT overreach** (a claim that says "in mice" or
     "whether this holds in humans is unknown" must not be graded as over-reaching). State the
     rule that separates genuine over-generalization from careful citation.
   - **Passing / methodological mention** (citing a paper for a method, not its headline
     finding) is out of scope for support-grading — give the rule to detect and exclude it.
4. A short **mapping** of how the scale composes with our already-grounded objective axes
   (species/population scope, retraction): e.g. a claim can be `fully-supported` on substance
   yet fail on scope; specify whether/how scope failures cap the substantive grade.

## Acceptance criteria

- Applying the rubric to our 17 eval cases yields a grade per case, and a second independent
  application (different session) agrees on ≥ ~80% and never differs by more than one adjacent
  grade.
- The rubric explicitly resolves the resveratrol-style case (animal finding, claim asserts
  clinical benefit) and the B03-style hedged case ("including non-human primates and humans")
  differently and correctly.
- Every grade has objective-enough criteria that the adjudication agent can cite *why* a case
  is that grade, not just assert it.
