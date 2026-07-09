# INTEGRATION_SPEC — RB1 / RB2 / RB3 → C4 + scorer

Integration-ready extraction of the three deep-research reports into the C4 adjudicator
scaffold (branch `master`). Faithful to the reports; every threshold/metric/label below is
quoted from a report or flagged as silent. Full reports live beside this file:
`RB1_ordinal_rubric_full.md`, `RB2_adversarial_adjudication_agent_full.md`,
`RB3_calibration_mechanism_full.md`.

**One conflict dominates this spec:** RB1 §D recommends that scope failure **caps** the
substantive grade; CONTEXT_PACK §6 (frozen design decision) + RB2 + RB3 require scope to stay
**orthogonal** (it gates `overall`, never the grade). §6 wins. See §4 CONFLICT-1.

---

## 1. RB1 — the final ordinal grade scale

### 1.1 Does it match the provisional 6-level + NEI?

**YES — same six grades, same order, plus NEI.** RB1's "Recommendations §1" says: *"Adopt the
6-point scale as the `substantive_support` label space."* Two differences vs the provisional
scaffold vocab (`prompts.RB1_GRADES`):

1. **One label refinement:** provisional `unsupported` → RB1 final **`Unsupported-for-the-Claim`**.
2. **Integer-anchor direction differs across reports (cosmetic, not a reordering):** RB1 anchors
   `Fully Supported (5) … Contradicted (0)`; RB3 anchors `fully-supported (0) … contradicted (5)`.
   The *ordinal ordering* is identical; only the integer label direction flips. The scaffold tuple
   order (`fully-supported` first) equals RB3's index convention — keep it as canonical for ±1
   adjacency and QWK (see §4 CONFLICT-2).

### 1.2 The scale (RB1 final — names verbatim, RB1 integer in parens)

| RB1 int | Grade label | One-line definition (RB1) |
|---|---|---|
| 5 | **Fully Supported** | Source directly establishes the claim at its stated scope, direction, and magnitude; every asserted element is substantiated by a rationale sentence in the source. |
| 4 | **Supported-with-Overreach** | Direction is correct and the source is genuinely on-point, but the claim asserts *more* than the source supports — inflated magnitude, generalized scope, hardened certainty, or a hypothesis restated as a finding. |
| 3 | **Partially Supported** | The claim is multi-part (conjunctive / spans multiple outcomes/populations/conditions) and the source substantiates *some conjuncts but not others*. |
| 2 | **Technically-True-but-Misleading (Spin)** | Every individual statement is literally defensible against the source, but framing, selection, or causal language creates an impression the source's results do not support. |
| 1 | **Unsupported-for-the-Claim** | The source neither substantiates nor contradicts the claim — off-point (wrong population/species/outcome so the claim is not addressed), a different question, or no data on the claim. |
| 0 | **Contradicted** | The source's finding is opposite in direction to the claim; the source refutes or directly undercuts it. |
| — | **NOT_ENOUGH_INFO** | Abstention (RB1 uses "NEI"; RB3 owns the firing rule). |

### 1.3 Inclusion / exclusion criteria (RB1 §A, condensed)

- **5 Fully Supported** — *Includes:* verbatim-accurate paraphrase; correctly-hedged claims;
  correctly-narrow claims (Trap 1); ≈ SciFact SUPPORTS. *Excludes (→4):* any assertion of *more*
  than the source shows (broader population, larger effect, causal language on associational data,
  or dropping the source's hedges).
- **4 Supported-with-Overreach** — *Includes:* Greenberg citation-diversion / citation-transmutation;
  moderate "misleading interpretation"; low–moderate conclusion spin; a minor quotation error that
  *inflates*. *Excludes (→5):* source's own hedge/scope preserved. *(→3):* claim is
  single-proposition and the source addresses all of it (defect is degree, not coverage). *(→2):*
  overreach is a substantive over-assertion the data don't reach, not a framing effect on true
  statements.
- **3 Partially Supported** — *Includes:* PUBHEALTH MIXED; CLIMATE-FEVER "only some facets";
  FactReview "only part of a decomposed claim is supported." *Excludes (→4):* defect is
  coverage/decomposition, not degree of a single assertion. *(→2):* at least one conjunct is genuinely
  fully supported and the unsupported parts are simply not established. *(→1):* a material part is
  actually supported.
- **2 Technically-True-but-Misleading** — *Includes:* Boutron/Yavchitz spin (significant
  secondary/subgroup framed as primary, nonsignificant-primary framed as equivalence, causal
  language on correlational data). *Excludes (→3):* no proposition is unsupported — words all true.
  *(→4):* claim does not over-assert a specific substantive fact beyond data; it re-frames true
  facts. *(→1):* literal content is defensible.
- **1 Unsupported-for-the-Claim** — *Includes:* major quotation error of the "fails to
  substantiate / irrelevant" type; Greenberg dead-end citation & amplification; SciFact NOINFO.
  *Excludes (→2):* claim is not merely misframed — source doesn't support the literal content.
  *(→0):* source doesn't contradict; it is silent/irrelevant.
- **0 Contradicted** — *Includes:* SciFact/FEVER REFUTES; de Lacey/Evans major error where the
  reference contradicted the assertion. *Excludes (→1):* source actively opposes rather than being
  silent.

### 1.4 Boundary rules (RB1 §B — five ordered operational tests, apply in order)

1. **Direction test (0 vs everything above):** is the source's finding opposite to the claim? Yes → **0**.
2. **On-point test (1 vs 2–5):** does the source contain data/finding bearing on this claim's
   population, intervention, and outcome? No → **1**. *(This is where the resveratrol-for-humans
   case falls on substance-agnostic reading — but see §4 CONFLICT-1 for how §6 changes this.)*
3. **Decomposition test (identifies 3):** decompose into atomic propositions; genuinely multi-part
   with some-but-not-all conjuncts supported → **3**.
4. **Literal-truth test (2 vs 4):** is every atomic statement literally defensible? If yes but
   framing/selection/causal language misleads → **2**. If instead a specific substantive element
   over-asserts the data (bigger effect, broader population, hypothesis-as-fact) → **4**.
5. **Hedge-preservation test (4 vs 5):** does the claim preserve the source's scope and hedges?
   Yes → **5**; drops a hedge or generalizes → **4**.

**The three hard middle grades (RB1's operational summary):**
*"direction correct but magnitude/scope inflated" = overreach (4); "only part of a multi-part
claim supported" = partial (3); "every word defensible but framing creates a false impression" =
misleading/spin (2).* The **overreach(4) vs spin(2)** boundary is RB1's stated top reliability risk
(both are overstatement; the literal-truth test is the discriminator) and is the first candidate for
grade-collapsing if inter-rater exact agreement < 80% or off-by-two > 5%.

### 1.5 The two traps

- **Trap 1 — Hedged / correctly-scoped-narrow rule:** a claim that accurately states a narrow scope
  ("in mice", "whether this holds in humans is unknown", "including non-human primates and humans")
  asserts exactly what was shown → **Fully Supported (5)**, never overreach. *Adjudication rule:*
  locate the scope qualifiers in the claim sentence; if they match the source's
  population/intervention/outcome, grade on substance alone and apply no indirectness cap. **The
  "B03"-style hedged case → grade 5.**
- **Trap 2 — Passing-mention / non-substantiating exclusion:** method / background / passing
  citations are **out of scope** for support grading. Classify citation intent first
  (SciCite Background / Method / Result-comparison); a citation used purely for a method, dataset,
  tool, or generic background pointer is flagged **`N/A — non-substantiating`** and excluded from
  the ordinal scale. Only grade citations whose function is to substantiate a knowledge claim.
  *(This capability does not exist in the current pipeline — see §4 CONFLICT-4.)*

### 1.6 Mapping onto `substantive_support` — does scope cap or stay orthogonal?

**RB1's own recommendation (§D): scope failure CAPS the grade.** *"Scope failure should CAP the
substantive grade, not merely annotate it."* Recommended capping arithmetic (RB1 flags it as a
*design decision*): a single major indirectness domain (e.g. surrogate outcome for a
patient-important claim) caps at **4**; a fatal/compound indirectness where the claim's target is
simply not addressed (animal finding → human clinical benefit = indirect population *and* indirect
outcome) caps at **1**. Under RB1, the resveratrol/B01 case = **grade 1** (or 2 if framed
true-but-misleading); the B03 hedged case = **5**. Retraction is a *separate orthogonal binary gate*
on both scale-designs.

**This is overridden for our system.** CONTEXT_PACK §6 (frozen) says `substantive_support` "never
up- or down-grades for scope"; scope lives on `species_scope`/`population_scope` and gates
`overall`. RB1 itself flags its capping as a design choice, not a sourced fact, so declining it is
legitimate. **Net rule for us:** adopt RB1's grade names, one-line definitions, inclusion/exclusion
criteria, the five boundary tests, and Trap 1 — but grade **as if scope matched** (hold scope
constant), and let the scope axes + rollup carry the scope failure. See §4 CONFLICT-1 for the exact
consequence (B01 grades high on substance, not 1).

---

## 2. RB2 — supporter / refuter / critic agent design

### 2.1 Roles (RB2 §1)

- **SUPPORTER** (Opus 4.8): builds the strongest evidence-grounded case FOR substantive support
  (effect, direction, magnitude, mechanism, certainty). Emits `support_points` — each with a
  `claim_component`, a verbatim `quoted_span` + `span_id`, and `reasoning` — plus
  `unsupported_components`, a `best_case_summary`, and a self-reported `strongest_grade`.
- **REFUTER** (Opus 4.8): receives shared inputs **plus the supporter transcript**; hunts
  substantive distortion + disconfirming evidence. Emits `refutation_points` each tagged with a
  `distortion_type`, a `targets_support_point` index, a verbatim `quoted_span`+`span_id` (or explicit
  `no_disconfirming_span`), a **`routes_to` ∈ {grade, rollup_not_grade}**, and `reasoning`; plus
  `most_severe_distortion` and **`refuter_grade_pressure` ∈ {none, mild, strong}**. Scope overreach
  is emitted as `over_generalization` but tagged `routes_to="rollup_not_grade"` so it can **never**
  depress the grade.
- **CRITIC** (Opus 4.8): receives shared inputs **plus both transcripts (order-randomized,
  identity-blinded)**; issues the FINAL verdict on `substantive_support` only. Emits `reasoning`,
  `decisive_spans`, `substantive_grade` (RB1 value or NEI), a `confidence` value (interface only —
  RB3 calibrates), `grade_rationale_last`, and `no_span_found`. **Never** issues verdicts on the
  three objective axes.

`distortion_type` (RB2 refuter enum): `direction_reversal · magnitude_inflation · cherry_picking ·
mechanism_mismatch · over_certainty · over_generalization · no_evidence_for_support`.

### 2.2 Prompt structure (RB2 §2)

Each prompt is **System** (role + hard constraints) + **Task** + **Output schema (strict JSON)**.
Hard constraints repeated across all three: (1) **FIXED FACTS** (retraction, species_scope,
population_scope) are immutable — a model value contradicting one is "wrong by construction"; (2)
reason **only** about substantive support, holding scope constant; (3) **every point must quote a
verbatim span** from `EVIDENCE_POOL` or be discarded; (4) route scope-framing overreach to
`rollup_not_grade`, never the grade. The **critic** adds: weigh by evidential quality not
length/order/fluency; transcripts are order-randomized + identity-blinded; abstain to NEI rather
than force a grade; and — critically — **"Produce your reasoning and cite decisive spans FIRST,
then the grade LAST"** (evidence-first / grade-last, per Wang et al., "LLMs are not Fair
Evaluators", ACL 2024).

### 2.3 Critic mapping exchange → grade + confidence (RB2 §3)

Self-consistency: run the **full triad** `N_SAMPLES` times (RB2 default **5**, small odd), each
sample supporter→refuter→critic. Enforce verbatim-span membership (`keep_grounded`); **drop refuter
points with `routes_to != "grade"` before voting**. Take an **ordinal / median-aware majority** over
the critic grades (not plain plurality) so adjacent-grade disagreement collapses toward the center.
Abstain to NEI **before** voting if `grades.count(ABSTAIN) >= ceil(N_SAMPLES/2)`; after voting,
abstain if `agreement < AGREEMENT_FLOOR and ordinal_spread > 2`. Emit grade + agreement + decisive
spans. The deterministic swappable rollup then gates `overall`.

### 2.4 Evidence-span requirement, sampling/determinism, bias mitigations

- **Span discipline:** every support/refute point must quote a verbatim substring of the
  `EVIDENCE_POOL`, re-verified by the critic before a point can move the grade; non-verbatim /
  paraphrased quotes are silently discarded (strongest lever against invented support).
- **Determinism:** critic at **low (near-greedy) temperature** for a stable verdict; supporter and
  refuter **warmer** to diversify arguments/spans; fixed decode seeds + pinned "Opus 4.8"; adaptive
  early-stopping (Adaptive-Consistency; up to 3.2–6.0× sample-budget reduction) optional. Report the
  winning grade **and** inter-sample agreement as a first-class output.
- **Bias mitigations (RB2 §5, all from Zheng et al. NeurIPS 2023):** position bias → randomized /
  alternating transcript order across samples + Balanced Position Calibration; verbosity bias →
  reduce every point to a `(distortion_type, span_id, quoted_span)` tuple, weigh span quality not
  length, discard padding; sycophancy → adversarial roles + evidence-first/grade-last ordering;
  **self-preference/self-enhancement (acute: all three roles are the same model)** → agent-identity
  blinding + score against the fixed `EVIDENCE_POOL`, not the debaters' prose + discard-if-no-span.

### 2.5 Alignment with the built S/R/C + §6 keys + metadata-override

**Broadly ALIGNED — RB2 states its output "drops into C5/C6 unchanged."** Aligned as built:
three-agent supporter→refuter→critic all Opus 4.8; objective axes as fixed facts the agents can't
overturn (`objective_facts` + critic "METADATA OVERRIDE"); verbatim guard discarding non-substring
quotes; self-consistency modal-grade + agreement; the §6 evidence keys
(`confidence{verbalized,agreement,n_samples}`, `calibration{note}`, `supporter{span,point}`,
`refuter{span,objection}`, `abstained`); scope routed to `overall`, not the grade.

**Requires changes (RB2 enhancements the scaffold lacks):**
1. **Evidence-first / grade-last critic output.** Built critic JSON is
   `{"grade","confidence","rationale"}` — grade FIRST. RB2 requires reasoning + decisive_spans
   FIRST, grade LAST. → reorder critic schema.
2. **Position-swap + identity-blinding.** Built critic gets fixed-labeled "SUPPORTER POINTS" /
   "REFUTER POINTS" in fixed order. RB2 requires order-randomized + identity-blinded transcripts
   across samples. → add shuffling/blinding in the pipeline.
3. **Full-triad resampling.** Built scaffold runs supporter/refuter **once** and resamples **only
   the critic** N times over fixed evidence. RB2 (and RB3) resample the **full triad** N times
   (warm agents = span diversity). → structural change + cost note (3N vs N+2 calls; mitigate with
   adaptive early-stopping).
4. **Ordinal/median-aware vote** instead of plain `Counter.most_common` plurality.
5. **Refuter schema:** rename failure modes to RB2's `distortion_type`
   (`unsupported_mechanism→mechanism_mismatch`, `certainty_overstatement→over_certainty`,
   `scope_overgeneralization→over_generalization`), add `no_evidence_for_support`, add explicit
   **`routes_to`** field, and **hard-filter `routes_to="rollup_not_grade"` before voting** (built
   pipeline passes all refuter points to the critic and relies on prompt wording only).
6. **Richer schemas (optional but recommended):** `span_id` indexing on the `EVIDENCE_POOL`,
   supporter `claim_component`/`unsupported_components`/`strongest_grade`, critic `decisive_spans` /
   `no_span_found`, `refuter_grade_pressure` (C01 fabrication canary).

Metadata-override + §6 orthogonality are honored by RB2 exactly as the scaffold enforces them.

---

## 3. RB3 — calibration mechanism, abstention, scorer metric(s), spot-check

### 3.1 Confidence-production mechanism (RB3 Part 1)

Per verdict:
1. **Sample the full adjudication N=7 times** at temperature **0.7–1.0**, fixed seed schedule. Each
   run emits one ordinal grade `gᵢ ∈ {0..5}` plus a **verbalized numeric confidence `Cᵢ ∈ [0,1]`**
   elicited with a "Just Ask for Calibration" prompt (Tian et al., EMNLP 2023) — a numeric
   probability the grade is correct.
2. **Modal grade `g*`** (majority vote); retain the full 6-bin empirical distribution.
3. **Exact agreement** `a_exact = (# == g*) / N`.
4. **Adjacent agreement** `a_adj = (# within ±1 ordinal of g*) / N` (carried because correctness is
   scored both exact and ±1).
5. **Agreement-based confidence** `conf_agr = a_exact` (**primary**), `a_adj` reported alongside;
   normalized entropy / non-adjacent mass flags multimodality.
6. **Verbalized cross-check (Avg-Conf blend)** `conf_hybrid = Σᵢ 1{gᵢ=g*}·Cᵢ / Σᵢ Cᵢ` (verbalized
   confidences as weights, Xiong et al. Avg-Conf Eq. 2 — not a standalone score).
7. **Emitted confidence = `conf_agr`** (primary); `conf_hybrid` + `a_adj` auxiliary; all post-hoc
   recalibrated (Part 5).

Rationale: logits are unavailable (Messages API) → excluded; verbalized-only is systematically
overconfident (clusters 80–100%, ECE ≥ 0.30, AUROC ≈ 62.7% for GPT-4) → demoted to a weight;
self-consistency agreement is the behavioral primary signal.

### 3.2 Abstention policy + exact thresholds (RB3 Part 2)

Emit **NOT_ENOUGH_INFO** when **either**: `a_exact < tau_abstain`, **or** grades are multimodal
across **non-adjacent** bins (mass split more than one grade apart, so even `a_adj` is weak).
**Do NOT abstain for an adjacent-grade-only split** — that is ordinal boundary noise; resolve to
the modal grade with moderate confidence. Set `tau_abstain` from the **selective risk–coverage
curve** on the human-verified sample; **seed `tau_abstain = 0.5`** before data exists. Log each
verdict `status ∈ {GRADED, ABSTAINED}`; **abstentions are excluded from the accuracy/Brier
numerator and denominator** and instead reduce coverage. CI gate: abstention **must** fire on
constructed ambiguous cases and **must not** fire on clear-cut ones.

### 3.3 Scorer calibration metric(s) (RB3 Part 3) — the chosen set

**Primary (report every scoring run, per graded axis):**
- **Brier score** — `mean (conf − correct)²`, computed **once exact-match and once ±1-adjacent**;
  strictly proper, no binning, stable at small N.
- **Selective risk–coverage curve** — plot selective risk vs coverage; report **AURC** + operating
  points (e.g. **risk at 80% coverage**). This is the monotone confidence→accuracy display.
- **Quadratic-weighted kappa (QWK)** — agent vs reference over the 0–5 ordinal,
  `wᵢⱼ = (i−j)²/(N−1)²`; plus **exact-match accuracy** and **±1-adjacent accuracy** as headline
  numbers.

**Secondary / caveated:**
- **ECE** — only with **3–4 equal-mass (adaptive) bins**, never fixed-width, with the explicit
  caveat *"ECE at N in the dozens is a rough diagnostic; high variance"*; always paired with a
  **reliability diagram** (mean-conf vs accuracy per bin, **Wilson binomial CIs**, bin counts
  annotated, points-with-error-bars not a smooth curve).
- **AUROC** of confidence-vs-correctness with a **bootstrap CI** (benchmark: should beat the ~0.5–
  0.65 verbalized-confidence band).
- **Conformal prediction** — assess **only** as adjacent-grade prediction sets, **diagnostic only**;
  split-conformal coverage is unreliable at this N (~1000 calibration points needed).

Requirement satisfied: ≥1 calibration number (Brier and/or selective risk) per graded axis, not
just accuracy.

### 3.4 Human spot-check protocol (RB3 Part 4)

- **30 cases** (within 20–40), **stratified** across the 6 grades **and** confidence tiers
  (~⅓ high, ~⅓ low, + a block of **abstained**). A check on a sample, never full-corpus labeling.
- **Single expert** (default), labels the same **6-level + NEI** substance-only rubric (**scope held
  constant**), **blind** to the agent's grade/confidence; for abstained cases decides independently
  whether the case is gradeable.
- **Pass criteria (single expert):** (a) **exact-match ≥ 0.60** AND **±1-adjacent ≥ 0.85** AND
  **QWK ≥ 0.6**; (b) **monotone confidence→accuracy** — top confidence tier concords measurably more
  than bottom, risk–coverage monotone (hard requirement). Both provisional.
- **Extend to ≥2 labelers:** Cohen's κ (2 raters), QWK (ordinal), Krippendorff's α (>2). *A single
  labeler cannot establish inter-annotator agreement* — one labeler validates agent↔expert
  concordance only.

### 3.5 Overconfidence detection + correction (RB3 Part 5)

Detection: `mean(confidence) − mean(accuracy)` overall + per bin; reliability points **below the
diagonal**; sign of `(conf − acc)` per bin. Correction (in order): (1) **fall back to `conf_agr`**
when the verbalized channel shows 80–100 clustering / low AUROC (default first move); (2)
**one-parameter temperature / Platt scaling** on confidence, fit on the held-out human sample
(prefer over isotonic to avoid overfit at tiny N); (3) **threshold recalibration** — shift
`tau_abstain` + tier cutoffs from the risk–coverage curve. Re-check Brier + reliability after.

### 3.6 Does RB3 confirm or change the provisional constants?

| Provisional constant | RB3 verdict | Detail |
|---|---|---|
| `SELF_CONSISTENCY_ROUNDS = 5` | **CHANGED → 7** | RB3 recommends **N=7** (odd, avoids ties). Revisit to **10–15** if Brier/AURC unstable across reruns. (RB2 kept 5; RB3 owns calibration → 7.) Also changes *what* is sampled: full triad, not critic-only. |
| `ABSTAIN_AGREEMENT_THRESHOLD = 0.6` | **CHANGED → seed 0.5** | Seed `tau_abstain = 0.5`, then **derive from the risk–coverage curve** on verified data. Plus add the non-adjacent-multimodal abstention condition and the "do not abstain on an adjacent-only split" rule. |
| `MIN_VALID_ROUNDS = 3` | **NOT ADDRESSED (silent)** | RB3 does not discuss a parseable-round floor. Keep as an engineering anti-false-confidence guard; consider scaling for N=7 (e.g. ≥4 valid). |
| tier cutoffs `0.8 / 0.6` | **CHANGED / NOT CONFIRMED** | RB3 does not endorse fixed 0.8/0.6 cutoffs. Confidence is primarily `conf_agr` (continuous); tier cutoffs are **data-derived from the risk–coverage curve** + Platt/temperature recalibration. The built "high needs agreement ≥ 0.8 **AND** verbalized == high" gate should be reconsidered — verbalized is a weight, not a gate. Seeds acceptable, must be recalibrated. |
| `VERBALIZED_CONFIDENCE = ("high","medium","low")` | **CHANGED → numeric [0,1]** | RB3 elicits a numeric probability `Cᵢ ∈ [0,1]` ("Just Ask for Calibration"), used as an Avg-Conf weight. Categorical tri-value no longer fits the aggregation. |

---

## 4. Integration delta table

### (a) C4 `prompts/`

| # | File | Change | Source |
|---|---|---|---|
| a1 | `prompts/__init__.py` | Relabel `RB1_GRADES` grade-1 `"unsupported"` → **`"unsupported-for-the-claim"`**. Keep the other 5 names + tuple order (fully-supported → contradicted) — CONFIRMED. | RB1 §1 |
| a2 | `prompts/__init__.py` | Change `VERBALIZED_CONFIDENCE` from `("high","medium","low")` to a **numeric [0,1]** elicitation (critic self-reports a probability). Touches critic schema + aggregation. | RB3 Part 1 |
| a3 | `prompts/critic.py` | **Evidence-first / grade-last:** reorder output JSON to `{reasoning, decisive_spans, grade, confidence, grade_rationale_last}` (grade LAST). | RB2 §2.3 |
| a4 | `prompts/critic.py` | Inject the **five ordered boundary tests** (direction → on-point → decomposition → literal-truth → hedge-preservation) as the grading rubric; require the critic to name the *test* that fired. Add **Trap 1** (hedged/narrow → 5) and **Trap 2** (non-substantiating → N/A) awareness. Keep AXIS BOUNDARY (§6) — **no scope capping** (RB1 §D overridden). | RB1 §B, §C |
| a5 | `prompts/critic.py` | Critic confidence = **numeric [0,1]** ("Just Ask for Calibration"). State transcripts are identity-blinded + order-randomized. | RB3 Part 1; RB2 §5 |
| a6 | `prompts/refuter.py` | Rename `FAILURE_MODES` to RB2 `distortion_type` set + add `no_evidence_for_support`; add **`routes_to` ∈ {grade, rollup_not_grade}** and **`refuter_grade_pressure`** fields. | RB2 §1, §2.2 |
| a7 | `prompts/supporter.py` | (Optional) add `span_id`, `claim_component`, `unsupported_components`, `strongest_grade`; Trap 1/Trap 2 awareness. | RB2 §1 |

### (b) C4 constants (`adjudicator.py`)

| # | Constant / logic | Change | Source |
|---|---|---|---|
| b1 | `SELF_CONSISTENCY_ROUNDS` | 5 → **7** (revisit 10–15). | RB3 §3.6 |
| b2 | Sampling scope | Resample the **full triad** N times (warm supporter/refuter, low-temp critic), not critic-only. Cost 3N vs N+2 — add **adaptive early-stopping**. | RB2 §4; RB3 Part 1 |
| b3 | `ABSTAIN_AGREEMENT_THRESHOLD` | 0.6 → **seed 0.5**, then risk-coverage-derived. | RB3 §3.6 |
| b4 | `_aggregate_rounds` / `_decide_abstention` | Compute `a_adj` + non-adjacent-multimodal dispersion; abstain if `a_exact < tau` OR non-adjacent multimodal; **do NOT abstain on adjacent-only split**. Switch modal vote to **ordinal/median-aware**. Add `conf_hybrid` (Avg-Conf) + `a_adj` to the emitted confidence block; confidence numeric. | RB3 Part 1–2; RB2 §3 |
| b5 | `_confidence_tier` | Replace fixed 0.8/0.6 + verbalized-gate with agreement-primary `conf_agr` + **data-derived cutoffs** + recalibration hook. `CONFIDENCE_HIGH/MEDIUM_AGREEMENT` become recalibratable seeds. | RB3 §3.5–3.6 |
| b6 | Refuter routing | Hard-filter `routes_to == "rollup_not_grade"` before voting (don't rely on prompt wording alone). | RB2 §3 |
| b7 | `MIN_VALID_ROUNDS` | Keep (RB3 silent); consider ≥4 for N=7. | RB3 silent |
| b8 | Recalibration | Add a Platt/temperature mapping applied to emitted confidence; fill `evidence.calibration.note`. | RB3 Part 5 |

### (c) Scorer (`scorer.py`) — the graded-axis calibration (currently "PENDING")

| # | Change | Source |
|---|---|---|
| c1 | Add a `substantive_support` calibration block: **Brier (exact + ±1-adjacent)** + **selective risk–coverage curve** with **AURC** + risk@80%-coverage. | RB3 Part 3 |
| c2 | Add **QWK** (`wᵢⱼ=(i−j)²/(N−1)²` on the 0–5 tuple index) + **exact-match** and **±1-adjacent accuracy** headline numbers. | RB3 Part 3 |
| c3 | Add **ECE** (3–4 equal-mass bins, caveated) + **reliability diagram** (Wilson CIs, bin counts) + **AUROC** (bootstrap CI). Conformal adjacent-grade sets **diagnostic only**. | RB3 Part 3 |
| c4 | **Abstention accounting:** `status ∈ {GRADED, ABSTAINED}`; abstentions excluded from Brier/accuracy numerator+denominator; report `coverage = graded/(graded+abstained)` and `selective_risk = errors/graded` separately. | RB3 Part 2 |
| c5 | **Data dependency:** the scorer needs a 6-level graded ground-truth label per case. `eval_set.json` currently has `ground_truth_label ∈ {RETRACTED, SCOPE_MISMATCH, SUPPORTED}` — **not** a 6-level substantive grade. Add a graded `substantive_support` reference field (from the 30-case spot-check / C6a corpus). Touches the corpus/eval schema + WO-C6a, **not** `contracts.py`. | RB3 Part 4; §3.4 |

### (d) `contracts.py` / CONTEXT_PACK — conflicts & contract touches

**No `contracts.py` field change is strictly required for calibration:** `AxisFinding.evidence` is a
free-form dict (numeric confidence + `conf_hybrid`/`a_adj` fit), and `AxisFinding.verdict: str`
holds any grade string. The §6 evidence-key convention is a rendering contract between C4 and C5,
not a `contracts.py` change.

- **CONFLICT-1 (major) — scope capping vs orthogonality.** RB1 §D ("scope failure **caps** the
  substantive grade"; resveratrol/B01 → grade 1) **directly conflicts** with CONTEXT_PACK §6 (frozen)
  + RB2 + RB3 ("substantive_support **never** up/down-grades for scope; scope is orthogonal, gates
  `overall`"). **§6 wins** — it is the frozen decision, RB2 and RB3 both confirm it, and RB1 itself
  labels its capping a "design decision." **Resolution:** adopt RB1's names/definitions/boundary
  tests/Trap 1, grade **holding scope constant**, and carry scope failure on
  `species_scope`/`population_scope` + the rollup. **Consequence for the corpus:** the resveratrol/B01
  mouse case grades **supported / partially-supported on substance** (RB2's B01 test), **not grade 1**
  — species_scope=MISMATCH + the rollup gate carry the mismatch. Corpus graded labels MUST follow §6,
  not RB1 §D. Do not let RB1's worked-example grades (which bake in capping) leak into corpus labels.

- **CONFLICT-2 (minor) — integer-index direction.** RB1 indexes fully-supported = 5 … contradicted =
  0; RB3 indexes fully-supported = 0 … contradicted = 5. Ordering identical. **Resolution:** use the
  scaffold tuple order (`fully-supported` = index 0 = RB3 convention) as canonical for ±1 adjacency
  and QWK weights. Presentational only; no contract impact.

- **CONFLICT-3 (definitional gap) — surrogate-outcome overreach has no home axis.** RB1's grade-4
  example (b) caps a surrogate-biomarker→patient-outcome claim at 4 via GRADE **outcome**-indirectness
  — a scope-type notion. But the system has only `species_scope` + `population_scope` objective axes
  (dose is unverifiable/flagged); there is **no outcome-scope axis**. Under §6 ("define overreach in
  substance terms — magnitude, certainty, generality — holding scope constant"), surrogate-outcome
  overreach should be graded as **substantive overreach (4)**, not routed to a (nonexistent) scope
  axis. **Flag for manager:** confirm surrogate-vs-patient-important outcome is folded into the
  substantive grade, or decide whether a new outcome-scope axis is warranted (a contract-level change).

- **CONFLICT-4 (new capability) — Trap 2 non-substantiating gate.** RB1 requires a SciCite-style
  citation-intent gate that marks method/background/passing citations **`N/A — non-substantiating`**
  and excludes them from the scale. The pipeline has **no** citation-intent classifier and no `N/A`
  path on `substantive_support`. `AxisFinding.verdict` (free str) can hold `"N/A —
  non-substantiating"`, but the scorer + rollup + abstention accounting must handle it. **Flag for
  manager:** add a pre-adjudication intent gate (C1/C3 or C4 pre-adjudicator) or defer; not a
  `contracts.py` change, but a pipeline + scorer decision.

- **Planned contract bump — `ScopeFrame.direction`.** RB2's refuter `direction_reversal` probe (and
  RB1's direction test) need the asserted effect direction. `ScopeFrame.direction` is a **planned,
  deferred** field (CONTEXT_PACK §1 / `contracts.py` note). Adding it is the one coordinated
  `contracts.py` bump these reports imply — a **manager decision**, made when the refuter consumes it,
  not a worker edit.

- **Temperature reconciliation (note, not a conflict).** RB2 wants a **low-temp critic** (stability)
  + warm agents; RB3 samples the run at **0.7–1.0**. Consistent if the full triad is resampled (warm
  agents give the diversity, critic stays cool). If only the critic were resampled it would need
  nonzero temp — another reason to adopt full-triad resampling (b2).

---

## 5. Bottom line

- **RB1 final scale = provisional 6-level + NEI, CONFIRMED**, with one relabel (`unsupported` →
  `unsupported-for-the-claim`) and an index-direction note. Adopt names, definitions, the five
  boundary tests, and Trap 1; **override RB1 §D scope-capping** in favor of §6 orthogonality.
- **RB2 ALIGNS** with the built supporter/refuter/critic + §6 keys + metadata-override, and asks for
  concrete enhancements (evidence-first/grade-last, position-swap + identity-blinding, full-triad
  resampling, ordinal vote, `routes_to`/`distortion_type`/`refuter_grade_pressure`).
- **RB3 calibration:** confidence = **`conf_agr` = exact modal agreement over N=7** (primary), with
  **Avg-Conf `conf_hybrid`** + **`a_adj`** auxiliary + Platt/temperature recalibration; abstain when
  `a_exact < tau_abstain` (**seed 0.5**) or non-adjacent-multimodal. **Scorer metrics: Brier
  (exact + ±1) + selective risk–coverage/AURC (primary), QWK + exact/±1 accuracy, ECE(caveated) +
  reliability diagram + AUROC(bootstrap), conformal diagnostic-only.** Provisional constants:
  **SELF_CONSISTENCY_ROUNDS 5→7; ABSTAIN 0.6→0.5 seed; tier cutoffs 0.8/0.6 → data-derived;
  verbalized categorical → numeric; MIN_VALID_ROUNDS unaddressed.**
- **Frozen-contract check:** no `contracts.py` field change required for calibration; the only
  contract-level items are the **planned `ScopeFrame.direction` bump** and the possible
  outcome-scope-axis / `N/A` decisions (CONFLICT-3, -4) — all **manager decisions**. The one hard
  conflict with a frozen decision is **RB1 §D vs §6 (CONFLICT-1); §6 governs.**
