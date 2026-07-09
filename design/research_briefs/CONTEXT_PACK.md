# Research Context Pack (for RB2, RB3, and any C4-facing research)

Real, frozen artifacts so research designs against the **actual** contracts — not a
reconstruction. This is the anti-drift measure: build to these shapes and the output drops into
the system unchanged.

## 1. Frozen contracts (from `src/citeval/contracts.py`)

**ScopeFrame** (C3 output — what the *claim* asserts):
`organism: str|None; organism_evidence: [str]; population: str|None; population_evidence: [str];
effect: str|None; direction: str|None (increase|decrease|no_change); direction_evidence: [str];
dose_stated: bool; provenance: str; tier: str`
(`direction` was added in the C4-integration bump (2026-07-09) — C3 populates it; C4's refuter uses
it for the direction-reversal probe. Back-compatible optional field; existing consumers ignore it.)

**GroundedRecord** (C2 output — the *cited paper*, all metadata-grounded):
`identifier{type,value}; title; abstract; mesh_all:[str]; organism_tags:[MeshTag];
population_tags:[MeshTag]; sex_tags:[MeshTag]; publication_types:[str]; has_humans:bool;
retraction:RetractionInfo; provenance:{}; grounding_errors:[str]`
- `MeshTag = {descriptor, ui, tree_numbers:[str], major_topic:bool}`
- `RetractionInfo = {status: RETRACTED|EXPRESSION_OF_CONCERN|NONE_FOUND,
  retraction_watch:{present,rw_record_id,reason,date}, ncbi_publication_type_flag:bool,
  comments_corrections:[{ref_type,pmid,source}], source_agreement, provenance:"metadata-grounded"}`

**Verdict** (C4 output — drops into C5/C6):
`claim; cited_identifier; overall; axis_findings:[AxisFinding]; unverifiable_axes:{}; stub:bool;
notes:[str]`
- `AxisFinding = {axis, verdict, tier, provenance, detail, evidence:{}}`
- axes: `"retraction"`, `"species_scope"`, `"population_scope"`, `"substantive_support"`

**Provenance atoms:** `metadata-grounded | text-grounded | model-inferred | stub-not-adjudicated`
(composites allowed, e.g. `"metadata-grounded (cited) + model-inferred (claim)"`).
**Tiers:** `high | medium | low` (| `n/a`).

## 2. The metadata-override boundary (critical for C4 design)

Objective axes — **retraction, species_scope, population_scope** — are decided by C2's structured
metadata and passed to the adjudication agents as **fixed facts they may not overturn**. The
adversarial supporter/refuter/critic reason **only** about the `substantive_support` axis (the
graded one). A model judgement never overrides a structured record; a conflict is scored as the
model being wrong.

## 3. RB1 grade scale — PROVISIONAL (RB1 finalizes it)

Design against this anchor set, and keep grade boundaries **swappable** so RB1's finalized scale
slots in without reshaping the pipeline:
`fully-supported · supported-with-overreach · partially-supported · technically-true-but-misleading
· unsupported · contradicted`, plus an abstention value `NOT_ENOUGH_INFO` (RB3 defines when it
fires).

## 4. Representative eval cases (from `eval_set.json`, the 17-case starter)

Case fields: `case_id, category(A/B/C), claim_text, cited_pmid, cited_title, ground_truth_label,
mismatch_axis, justifying_metadata, provenance_label, inference_flag`.

- **A01 (retracted).** Claim: *"Exogenous c-kit+ cells are currently being used to treat post-MI
  heart failure patients, and early results have shown small, albeit significant functional
  improvements in the heart."* → cites PMID 22088800 (SCIPIO trial) → **RETRACTED**. Agent must
  **defer** to the retraction metadata; the substantive axis reasons about whether the claim leans
  on the discredited finding.
- **B01 (species mismatch).** Claim: *"Resveratrol has shown promising clinical benefits as
  anti-aging, anti-inflammatory, anti-diabetic, anti-viral, anti-neoplastic, and anti-CVD agents."*
  → cites PMID 17086191 (mouse study; MeSH Animals/Mice, no Humans) → **SCOPE_MISMATCH**. The
  refuter must surface that a mouse finding is generalized to human clinical benefit.
- **B05 (the hard one).** Claim: *"…tofacitinib, a STAT3 inhibitor, can regulate microglial
  activation through the JAK/STAT pathway and promote the recovery of motor function after spinal
  cord injury."* → cites PMID 37781508 (rat study) → **SCOPE_MISMATCH**. NOTE: asserts
  therapeutic relevance with **no explicit lexical marker** ("humans"/"patients" absent). The
  lexical scope stub misses it; the refuter's reasoning must catch this *implicit*
  over-generalization. Key acceptance case.
- **C01 (supported control).** Claim: *"In a head-to-head comparison, pembrolizumab showed better
  6-month progression-free survival than ipilimumab and conferred an overall survival benefit."* →
  cites PMID 25891173 (human melanoma trial; Humans + adult tags) → **SUPPORTED**. Must **not** be
  flagged; the critic grades it supported without a forced objection.

## 5. Where results go

Bring the report back to the **Cowork (manager) session**. I reconcile it against these contracts,
finalize `WO-C4`, and hand the build spec to the C4 session.

## 6. Axis semantics & the substantive_support ↔ scope boundary (design decision)

`substantive_support` grades **only substance, holding organism/population/dose scope constant**:
does the cited paper's *actual reported finding* back the claim's asserted **effect, mechanism,
direction, and magnitude/certainty**? It never up- or down-grades for scope.

Scope over-generalization — **including implicit, B05-style** — is carried by the metadata-grounded
`species_scope` / `population_scope` axes. The claim's asserted scope, including reasonable
**implicit** inference ("promote functional recovery" ⇒ therapeutic/human relevance), is **C3's
job**, emitted with a confidence tier and `model-inferred` provenance on the claim side; C4's
**deterministic** comparison against C2 metadata then sets the scope verdict (composite provenance).
So B05 is caught on `species_scope`, and the refuter does **not** smuggle scope into the graded axis.

`overall` is an explicit, **swappable rollup policy**: by default a retraction or a scope mismatch
**gates** `overall` to "not supported as stated" regardless of the substantive grade; otherwise
`overall` tracks the substantive grade. Axis combination happens here, in the open — not by letting
an objective signal depress the graded number.

**Why (and not the reverse):** the graded axis is the one RB3 must calibrate and the one §8 calls
make-or-break. Letting the perfectly-grounded scope signal depress it would (a) double-count scope
and (b) contaminate the graded axis's measured calibration with a trivially-grounded fact —
inflating apparent performance, the exact "looks clean but is confident nonsense" failure the system
exists to catch. A pure graded axis calibrates against the *true* difficulty of the substantive
judgement.

**Implication for RB1:** define the "supported-with-overreach" / "technically-true-but-misleading"
grades in **substance** terms (magnitude, certainty, generality of mechanism), holding scope
constant; scope-type overreach lives on the scope axes.

### `substantive_support` AxisFinding shape (rendering convention — NOT a contract change)

`AxisFinding.evidence` is a free-form dict. For the graded `substantive_support` axis, **C4
produces** and **C5 reads** these exact keys (so the producer/consumer agree without a `contracts.py`
change; if keys change later, only C4 and C5's extractor move):

- `verdict` = the RB1 grade (or `NOT_ENOUGH_INFO` on abstention); `tier` = confidence tier;
  `provenance` = `model-inferred`; `detail` = the critic's one-line rationale.
- `evidence = {`
  - `"confidence": {"verbalized": "high|medium|low", "agreement": <0..1 float>, "n_samples": <int>},`
  - `"calibration": {"note": "<one line from the scorer/RB3; empty until available>"},`
  - `"supporter": {"span": "<verbatim cited-text quote>", "point": "<why it supports>"},`
  - `"refuter": {"span": "<verbatim quote>", "objection": "<why it doesn't>"},`
  - `"abstained": <bool>   # true ⇔ verdict == NOT_ENOUGH_INFO`
  - `}`
- C5 reads defensively: a missing `supporter`/`refuter` renders as "no supporting span found".

### RB1–3 integration decisions (2026-07-09)

- **Scale (RB1):** the 6-level + `NOT_ENOUGH_INFO` scale is confirmed; grade-1 relabeled
  `unsupported-for-the-claim`. Keep the 0→5 integer order (RB3 convention) for ±1-adjacent / QWK.
- **CONFLICT resolved — §6 governs over RB1 §D.** RB1's worked examples *cap* the substantive grade
  on a scope failure (B01 mouse → 1). **Rejected.** `substantive_support` grades substance holding
  scope constant; scope failure gates `overall`, never the grade. Corpus graded labels follow §6
  (B01 graded on substance) — capping would contaminate the graded axis's calibration with a
  trivially-grounded scope fact, the exact failure §6 forbids.
- **Outcome / surrogate overreach folds into the substantive grade** (supported-with-overreach /
  technically-true-but-misleading). No new objective axis — no structured outcome field exists, so it
  is a model judgement and belongs on the graded axis.
- **Passing / methodological citations →** critic emits `N/A — non-substantiating`; rollup + scorer
  treat it as non-graded (excluded from grading metrics, like an abstention but a distinct reason).
- **`ScopeFrame.direction` added** (the deferred bump) — C3 populates it; C4's refuter uses it.

## 7. Measurement & environment constraints (for RB3 and the scorer)

- **Model access = black-box.** The adjudication agent is Opus 4.8 via the Anthropic Messages API,
  which does **not** expose token logprobs. Confidence must come from **multi-sample /
  self-consistency agreement + verbalized confidence** (with recalibration) — not logit-based methods.
- **Graded-axis cardinality.** `substantive_support` = the RB1 **6-level ordinal** (provisional) +
  `NOT_ENOUGH_INFO` abstention — *not* a 4-level scale. Measure correctness **both exact-match and
  adjacent-tolerant (±1 grade)**, mirroring RB1's "≤1 adjacent grade" agreement criterion. Keep any
  grouping swappable (RB1 finalizes the scale).
- **Corpus size.** Objective tier → low hundreds; the agent-**graded** tier is dozens → low hundreds
  early. Prefer metrics that stay meaningful at small N — **Brier, selective risk–coverage,
  confidence-vs-accuracy curves**; report **ECE cautiously** (few wide bins + small-sample caveat);
  assess **conformal prediction** only as adjacent-grade prediction sets, and say plainly if N makes
  it unreliable.
- **Calibration target = the `substantive_support` axis.** Objective axes (retraction, scope) are
  metadata-grounded — scored for accuracy, not model-calibrated. C3's model-inferred claim-scope
  confidence is a secondary, optional target.
- **Human spot-check.** Default: a **single expert** (~20–40 sampled cases); pass criteria =
  agent↔expert concordance + "agent confidence predicts agent↔expert agreement." Design the protocol
  to **extend to ≥2 labelers with inter-annotator agreement** (Cohen's κ / Krippendorff's α) when
  available; a single labeler cannot establish IAA, so that check validates agent↔expert concordance,
  not inter-human reliability.
