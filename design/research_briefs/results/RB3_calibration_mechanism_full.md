# Research Brief RB3: Calibration Mechanism and Metric for a Self-Grading Scientific-Citation Adjudication Agent

## TL;DR
- **Confidence:** Build a per-verdict confidence for `substantive_support` from **N=7 self-consistency samples** of the adversarial adjudication run, aggregating the ordinal grades into a modal grade + agreement fraction, then blend with a verbalized-confidence weight (Avg-Conf style) as a secondary signal; abstain to `NOT_ENOUGH_INFO` when modal agreement falls below a threshold set from a risk–coverage curve.
- **Metric:** Report **Brier score** and a **selective risk–coverage curve** as the primary per-axis calibration numbers (each computed both exact-match and ±1-adjacent), with **quadratic-weighted kappa** for agent-vs-expert ordinal agreement; treat **ECE as a caveated secondary** with 3–4 equal-mass bins; conformal adjacent-grade prediction sets are **diagnostic only** and unreliable at this N.
- **Validation:** Validate on a **stratified 30-case single-expert spot check** whose pass criteria are (a) agent-vs-expert concordance and (b) a demonstrated **monotone confidence→accuracy relationship**; detect overconfidence via `mean(confidence) − mean(accuracy)` and the reliability-gap sign, and correct by defaulting to agreement-based confidence plus one-parameter temperature/Platt recalibration.

## Key Findings

- **Logit-based confidence is off the table by contract.** Because Claude Opus 4.8 is accessed through the Anthropic Messages API with no logprob/logit exposure, softmax-response and token-probability P(True) methods cannot be used. The only viable signals are **self-consistency agreement** across sampled generations and **verbalized (self-reported) confidence**, both recalibrated against a small held-out human sample.

- **Self-consistency agreement should be the primary signal; verbalized confidence is a documented failure mode.** Verbalized confidence from RLHF-tuned models is systematically overconfident. Per Zhang et al., "Mind the Confidence Gap" (Feb 2025), "large RLHF-tuned models primarily emit verbalized confidence scores between 80% and 100%, with ECE (Expected Calibration Error) values that can reach 0.30 or higher on knowledge-intensive tasks." Xiong et al. (ICLR 2024, arXiv:2306.13063) found the values "predominantly fall within the 80% to 100% range and are typically in multiples of 5," and that vanilla verbalized confidence gives GPT-4 an "average AUROC of merely 62.7%—close to the 50% random guess threshold," while GPT-3/GPT-3.5/Vicuna show "average ECE exceeding 0.377." Xiong also documents insensitivity to difficulty: on GSM8K, GPT-4 "achieves a near-optimal ECE 0.064 by assigning 100% confidence to all samples," making it "challenging to distinguish between correct and incorrect samples based on the verbalized confidence." Agreement across samples, by contrast, is a behavioral signal that tracks the model's actual sensitivity to the case.

- **Combining the two beats either alone.** Xiong et al. show that "introducing verbalized confidence into the aggregation (e.g., Pair-Rank and Avg-Conf) is more effective compared to consistency-only aggregation (e.g., Consistency), especially when LLM queries are costly... (set to M = 5 queries in our experiment)." Concretely, on GPT-4 averaged over six datasets, their consistency-only aggregator scored mean ECE 0.120 / AUROC 0.669, Avg-Conf 0.148 / 0.669, and Pair-Rank **0.069 / 0.676** — Pair-Rank roughly halving calibration error, Avg-Conf winning failure prediction on 5 of 6 datasets. This justifies keeping verbalized confidence as a *weighting factor*, not a standalone score.

- **Sampling-based consistency is the right family for a small, ambiguous corpus.** Cole et al. (2023), as summarized in "Entropy Alone is Insufficient for Safe Selective Prediction in LLMs" (arXiv:2603.21172), found that "sampling-based consistency measures generally outperform likelihood methods, particularly for ambiguous questions." Multiple 2024–2026 black-box studies replicate a clean split: self-evaluation methods (verbalized, P(True)) reach AUROC ≈ 0.42–0.76, while perturbation/consistency methods reach ≈ 0.78–0.86.

- **Brier and selective risk stay meaningful at small N; ECE does not.** Brier is a strictly proper scoring rule requiring no binning. ECE is biased and binning-sensitive: per Roelofs et al., "Mitigating Bias in Calibration Error Estimation" (PMLR v151, 2022), "metrics based on equal mass binning consistently outperform equal width binning; exploiting monotonicity in the EMsweep metric helps the most at small sample sizes," corroborating Nixon et al. (2019) and Guo et al. (2017). Conformal prediction needs far more data than this corpus has: per Angelopoulos & Bates, "A Gentle Introduction to Conformal Prediction" (arXiv:2107.07511), "choosing n = 1000 calibration points leads to coverage that is typically between .88 and .92, hence our rough guideline of choosing about 1000 calibration points." At dozens of cases, realized conformal coverage fluctuates widely, so conformal is diagnostic only.

- **A single expert cannot establish inter-annotator agreement.** With one labeler the check validates agent-vs-expert concordance only. Extending to ≥2 labelers enables Cohen's kappa, quadratic-weighted kappa (ordinal), and Krippendorff's alpha (which the LLM-as-judge literature favors for handling >2 raters, missing data, and ordinal distance).

## Details

### Environment recap and the substance-vs-scope purity boundary
The graded axis `substantive_support` is a **6-level ordinal scale** — `fully-supported (0)`, `supported-with-overreach (1)`, `partially-supported (2)`, `technically-true-but-misleading (3)`, `unsupported (4)`, `contradicted (5)` — **plus** an abstention value `NOT_ENOUGH_INFO`. Assign ordinal indices 0–5 in that order and keep the binning/grouping swappable, since the scale is provisional. `substantive_support` grades **only substance**, holding organism/population/dose scope constant: does the cited paper's actual reported finding back the claim's asserted effect, mechanism, direction, and magnitude/certainty? It never up- or down-grades for scope. Scope over-generalization (including implicit over-generalization) is carried by the separate metadata-grounded axes (`retraction`, `species_scope`, `population_scope`), which are scored for accuracy only and never model-calibrated. **All calibration must be computed on the pure substance judgement** — letting a trivially-grounded scope fact depress the graded number would double-count scope and contaminate the graded axis's measured calibration, inflating apparent performance. C3's model-inferred claim-scope confidence is a secondary, optional calibration target handled by the same machinery described below.

Logit/token-probability confidence (e.g., Geifman & El-Yaniv softmax response, or Kadavath et al.'s token-probability P(True)) is **excluded** solely because the Messages API exposes no logprobs; it is mentioned here only to document the exclusion.

---

### PART 1 — CONFIDENCE-PRODUCTION MECHANISM

**Recipe (per verdict):**

1. **Sample the adjudication N=7 times at nonzero temperature.** Run the full supporter/refuter/critic adversarial adjudication seven times at temperature 0.7–1.0, with a fixed seed schedule for reproducibility. N=7 is chosen as a practical middle ground: self-consistency and black-box confidence work commonly use M=5–10 samples. Wang et al., "Self-Consistency Improves Chain of Thought Reasoning" (arXiv:2203.11171), sampled up to 40 paths and reported gains of "GSM8K (+17.9%), SVAMP (+11.0%), AQuA (+12.2%), StrategyQA (+6.4%) and ARC-challenge (+3.9%)"; Xiong et al. obtained their headline results at just M=5. Odd N avoids ties in the majority vote. Each run emits one `substantive_support` ordinal grade gᵢ ∈ {0..5} plus a verbalized confidence Cᵢ ∈ [0,1], elicited with a "Just Ask for Calibration" prompt (Tian et al., EMNLP 2023, arXiv:2305.14975) asking for a numeric probability that the grade is correct. Tian et al. found that for RLHF-LMs "such as ChatGPT, GPT-4, and Claude... verbalized confidences emitted as output tokens are typically better-calibrated than the model's conditional probabilities on the TriviaQA, SciQ, and TruthfulQA benchmarks, often reducing the expected calibration error by a relative 50%" — which is why verbalized confidence is retained as a cross-check even though it is not trustworthy alone.

2. **Aggregate the ordinal grades.** Compute the **modal grade g\*** (majority vote). Retain the full empirical distribution over the 6 bins for diagnostics.

3. **Exact agreement fraction:** `a_exact = (# samples equal to g*) / N`.

4. **Adjacent agreement fraction:** `a_adj = (# samples within ±1 ordinal of g*) / N`. Because correctness is scored both exact and ±1-adjacent, carry both fractions through.

5. **Agreement-based confidence:** `conf_agr = a_exact` (primary), with `a_adj` reported alongside. A dispersion measure — normalized entropy of the 6-bin distribution, and whether mass splits across *non-adjacent* bins — flags multimodality.

6. **Verbalized cross-check / blend (Avg-Conf):**
   `conf_hybrid = [ Σᵢ 1{gᵢ = g*} · Cᵢ ] / [ Σᵢ Cᵢ ]`
   This weights the modal vote by the self-reported confidence of the agreeing samples (Xiong et al.'s Avg-Conf, Eq. 2). The verbalized confidences act as weights, not as a standalone score. (Their Pair-Rank variant, which optimizes over pairwise rankings of Top-K guesses, gives lower ECE but is heavier to implement; adopt it only if calibration must be squeezed further.)

7. **Emitted confidence = `conf_agr`** (primary), with `conf_hybrid` and `a_adj` as auxiliary fields. All are post-hoc recalibrated (Part 5).

**Rationale for choosing self-consistency agreement as primary.** It is preferred over *verbalized-only* because verbalized confidence is systematically overconfident, clusters at 80–100, and can be invariant to correctness (findings above). It is preferred over *ensemble/debate across models* because the frozen contract fixes a single model. It is preferred over *logit-based* because logits are unavailable. Verbalized confidence is nonetheless kept as a weighting cross-check because Avg-Conf/Pair-Rank beat consistency-only aggregation, and because Tian et al. show verbalized confidence is the best of the *available* black-box self-reports for RLHF models.

---

### PART 2 — ABSTENTION POLICY

**Decision rule.** Emit `NOT_ENOUGH_INFO` on `substantive_support` when the sampled-grade distribution is too dispersed to support a graded verdict — i.e., when **either**:
- modal agreement `a_exact < tau_abstain`, **or**
- the sampled grades are multimodal across **non-adjacent** bins (mass split more than one grade apart, so even adjacent-tolerant agreement `a_adj` is weak).

Do **not** abstain merely because the split is between two *adjacent* grades — that is genuine ordinal boundary noise, not "not enough info," and should resolve to the modal grade with moderate confidence.

**Setting `tau_abstain`.** Derive it from the selective risk–coverage curve (El-Yaniv & Wiener; Geifman & El-Yaniv) on the human-verified sample: sort verdicts by `conf_agr`, sweep the threshold, plot selective risk (error among non-abstained) versus coverage (fraction non-abstained), and pick the highest coverage at which selective error is at or below the chosen tolerance. Seed value before data exists: `tau_abstain = 0.5` (no strict within-one-grade majority), tightened once the curve exists.

**Recording abstentions so they are never silently counted wrong.** Log each verdict with `status ∈ {GRADED, ABSTAINED}`. Abstentions are **excluded from the accuracy/Brier numerator and denominator** (neither right nor wrong) and instead **reduce coverage**. Report `coverage = graded / (graded + abstained)` and `selective_risk = errors / graded` separately. Abstaining on a genuinely ambiguous case is correct behavior, not failure.

**Acceptance test.** Construct genuinely-ambiguous cases (conflicting evidence, missing effect size, cited paper doesn't clearly address the claimed endpoint) — abstention **must** fire. Construct clear-cut cases (paper directly states the claimed effect and direction) — abstention **must not** fire. Wire this as a CI gate.

---

### PART 3 — SCORER CALIBRATION METRIC(S) (per-axis, for `substantive_support`)

**Primary metrics — Brier score and selective risk–coverage:**

- **Brier score.** Treat emitted confidence `conf_agr` as the predicted probability that the grade is correct, and correctness as the binary outcome (1 if the agent grade matches the reference, else 0). Compute `Brier = mean over graded cases of (conf − correct)²`, **once with exact-match correctness and once with ±1-adjacent correctness**. Brier is strictly proper, needs no binning, and stays meaningful at small N. Optionally report the Murphy decomposition (reliability − resolution + uncertainty), but flag that per-bin decomposition terms are noisy at small N (empty/sparse bins produce unreliable estimates).

- **Selective risk–coverage curve.** Sweep the confidence threshold, plot selective risk vs coverage, and report the **area under the risk–coverage curve (AURC)** plus a couple of operating points (e.g., risk at 80% coverage). This is the direct display of the monotone confidence→accuracy relationship the acceptance criteria demand.

- **Ordinal agreement — quadratic-weighted kappa (QWK).** Report QWK between agent grade and reference over the 0–5 ordinal, `κ = 1 − Σ wᵢⱼOᵢⱼ / Σ wᵢⱼEᵢⱼ` with `wᵢⱼ = (i−j)²/(N−1)²`. QWK gives partial credit for adjacent disagreements and is the standard ordinal-rater metric (Landis–Koch: >0.80 almost perfect, 0.61–0.80 substantial). Also report exact-match accuracy and ±1-adjacent accuracy as headline numbers.

**Secondary / caveated — ECE.** Compute with **3–4 equal-mass (adaptive) bins**, never fixed-width, because fixed-width binning is biased and unstable at small N with high-clustered confidences (Nixon et al. 2019; Roelofs et al. 2022). State explicitly: *"ECE at N in the dozens is a rough diagnostic; bin counts are small and the estimate has high variance."* Always pair ECE with a reliability view.

**Reliability view at small N.** A reliability diagram with 3–4 equal-mass confidence bins plotting mean confidence vs observed accuracy per bin, with **Wilson binomial confidence intervals** on each point and the bin count annotated. Show points with error bars, not a smooth curve.

**AUROC of confidence-vs-correctness.** Report it (confidence as score, correctness as label) as a threshold-free discrimination measure, with a **bootstrap CI**, because at dozens of cases the standard error is large. Benchmark against the literature: documented LLM verbalized-confidence AUROCs are often near 0.5–0.65 (Xiong et al.: GPT-4 "average AUROC of merely 62.7%," and a white-box-vs-black-box gap of "0.522 to 0.605 in AUROC"), so `conf_agr` should be shown to beat that band.

**Conformal prediction.** Assess **only** as adjacent-grade prediction sets on the ordinal scale (e.g., `{partially-supported, technically-true-but-misleading}`), and state plainly that split-conformal coverage guarantees are **unreliable at this N** — stable coverage needs ~1000 calibration points (Angelopoulos & Bates), and with dozens the realized coverage fluctuates widely. Small-sample corrections (e.g., a Beta correction on the significance level) exist but do not manufacture data; treat conformal as a diagnostic visualization of ordinal uncertainty, not a guarantee.

**Requirement satisfied:** at least one calibration number (Brier and/or selective risk) is emitted per graded axis, not just accuracy.

---

### PART 4 — HUMAN SPOT-CHECK PROTOCOL (20–40 sampled cases)

**Sample size:** 30 cases (within 20–40). **Sampling:** stratified to guarantee spread across grades **and** across confidence levels — (a) stratify by the 6 ordinal grades so each populated bin is represented, and (b) by confidence tier, including roughly one-third high-confidence, one-third low-confidence, and a block of **abstained** cases, so the check can test whether confidence predicts concordance. This is a **check on a sample**, never full-corpus labeling.

**What the human labels:** the same 6-level ordinal + `NOT_ENOUGH_INFO` grade on `substantive_support`, applying the identical substance-only rubric (scope held constant), **blind to the agent's grade and confidence**. For abstained cases, the expert independently decides whether the case is genuinely gradeable.

**Pass criteria (single expert):**
- **(a) Concordance:** agent-vs-expert exact-match ≥ **0.60** and ±1-adjacent agreement ≥ **0.85**, with **QWK ≥ 0.6** (substantial). Provisional; set with the team's risk tolerance.
- **(b) Monotone confidence→accuracy:** high-confidence agent verdicts must concord with the expert measurably more than low-confidence ones — accuracy in the top confidence tier exceeds the bottom tier by a clear margin, and the risk–coverage curve is monotone. This is the core "confidence predicts agreement" test and is a hard requirement.

**Extending to ≥2 labelers:** when a second expert is available, compute **Cohen's kappa** (2 raters) or **quadratic-weighted kappa** for the ordinal, and **Krippendorff's alpha** (>2 raters, missing data, ordinal distance). **Explicit note:** a single labeler *cannot* establish inter-annotator agreement; with one labeler the check validates agent-vs-expert concordance only. Stable kappa/alpha estimates need more items than 20–40, so treat any two-labeler kappa on this sample as indicative, not definitive.

---

### PART 5 — OVERCONFIDENCE DETECTION + CORRECTION

**Detection.** On the human-verified sample, compute `mean(confidence) − mean(accuracy)` overall and within each reliability bin. A consistently positive sign indicates systematic overconfidence. Read the same signal off the reliability diagram as points lying **below the diagonal** (confidence > accuracy), and track the sign of `(confidence − accuracy)` per bin. (For calibration context: one 2026 study measured a 9% overconfidence gap — 88% stated confidence vs 79% accuracy — with a "hard-easy effect" where overconfidence rises with difficulty.)

**Correction options:**
- **Fall back to agreement-based confidence when verbalized is miscalibrated (default first move).** Since verbalized confidence is the documented culprit, ship `conf_agr` rather than `conf_hybrid` whenever the verbalized channel shows the 80–100 clustering / low-AUROC pathology.
- **Temperature / Platt-style scaling on the confidence.** Fit a one-parameter logistic recalibration mapping raw confidence to empirical accuracy on the held-out human sample. Temperature scaling is Guo et al.'s (2017) "single-parameter variant of Platt Scaling... surprisingly effective at calibrating predictions."
- **Threshold recalibration.** Shift `tau_abstain` and the confidence-tier cutoffs using the risk–coverage curve on the verified sample.

**Recommended default:** (1) use `conf_agr` as the primary confidence; (2) apply a single-parameter Platt/temperature recalibration fit on the human-verified sample; (3) set thresholds from the risk–coverage curve. **Re-check after correction** by recomputing Brier, the reliability diagram, and `(confidence − accuracy)` per bin on a fresh held-out slice (or via cross-validation on the small sample), confirming reliability points moved onto the diagonal and Brier dropped. Because the fitting sample is tiny, prefer the minimal one-parameter correction over many-parameter isotonic regression to avoid overfitting.

## Recommendations

1. **Ship `conf_agr`** (exact modal-agreement fraction over N=7) as the primary per-verdict confidence; keep `a_adj` and `conf_hybrid` (Avg-Conf) as auxiliary fields. **Benchmark to revisit N:** if AURC or Brier is unstable across reruns, raise N to 10–15.
2. **Emit Brier (exact and ±1-adjacent) and AURC per graded axis** every scoring run; add QWK plus exact/adjacent accuracy. Report ECE only with 3–4 equal-mass bins and a small-N caveat, always beside a reliability diagram with Wilson intervals.
3. **Set `tau_abstain` from the risk–coverage curve**; seed at 0.5 until data exists. Verify abstention fires on constructed ambiguous cases and not on clear ones, as a CI gate.
4. **Run the 30-case stratified single-expert spot check** before trusting any corpus tier; require exact ≥ 0.60, adjacent ≥ 0.85, QWK ≥ 0.6, and a monotone confidence→accuracy gap. Add a second labeler for kappa/alpha as soon as budget allows; do not report inter-annotator agreement from one labeler.
5. **Default overconfidence correction:** prefer `conf_agr`, apply one-parameter temperature/Platt recalibration on the verified sample, shift thresholds; re-check Brier and reliability after.

**Thresholds that change the plan:** if two-labeler QWK is high (≥ 0.8), the corpus tier can expand; if selective risk at target coverage exceeds tolerance, tighten `tau_abstain` or shrink the graded tier; if the conformal calibration set grows toward ~1000, promote conformal adjacent-grade sets from diagnostic to a coverage guarantee.

## Caveats
- All confidence is post-hoc recalibrated against a small human sample; with N in the dozens, every calibration number has wide error bars. Report bootstrap/binomial CIs, not point estimates alone.
- ECE is biased at small N and with high-clustered confidences; it is secondary and caveated (Nixon et al. 2019; Roelofs et al. 2022).
- Conformal coverage guarantees are not reliable at this N (Angelopoulos & Bates: ~1000 points for stable coverage); adjacent-grade prediction sets are diagnostic only.
- A single expert validates agent-vs-expert concordance, not inter-human reliability; kappa/alpha require ≥2 labelers and more items for stability.
- The ordinal scale is provisional; keep binning/grouping swappable so metrics recompute if the scale is finalized.
- Verbalized confidence may be near-uninformative for this model/domain (some studies find it "completely invariant to prediction quality"); the design leans on agreement precisely for this reason.

## References
- Wang, Wei, Schuurmans, Le, Chi, Narang, Chowdhery, Zhou. *Self-Consistency Improves Chain of Thought Reasoning in Language Models.* ICLR 2023. arXiv:2203.11171.
- Xiong, Hu, Lu, Li, Fu, He, Hooi. *Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs.* ICLR 2024. arXiv:2306.13063.
- Tian, Mitchell, Zhou, Sharma, Rafailov, Yao, Finn, Manning. *Just Ask for Calibration.* EMNLP 2023. arXiv:2305.14975.
- Lin, Hilton, Evans. *Teaching Models to Express Their Uncertainty in Words.* TMLR 2022. arXiv:2205.14334.
- Kadavath et al. (Anthropic). *Language Models (Mostly) Know What They Know.* 2022. arXiv:2207.05221.
- Geifman, El-Yaniv. *Selective Classification for Deep Neural Networks.* NeurIPS 2017. arXiv:1705.08500. And *SelectiveNet.* ICML 2019. arXiv:1901.09192.
- El-Yaniv, Wiener. *On the Foundations of Noise-free Selective Classification.* JMLR 2010.
- Guo, Pleiss, Sun, Weinberger. *On Calibration of Modern Neural Networks.* ICML 2017. arXiv:1706.04599.
- Nixon, Dusenberry, Zhang, Jerfel, Tran. *Measuring Calibration in Deep Learning.* CVPR-W 2019. arXiv:1904.01685.
- Roelofs, Cain, Shlens, Mozer. *Mitigating Bias in Calibration Error Estimation.* AISTATS/PMLR v151, 2022. arXiv:2012.08668.
- Naeini, Cooper, Hauskrecht. *Obtaining Well Calibrated Probabilities Using Bayesian Binning.* AAAI 2015.
- Angelopoulos, Bates. *A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification.* arXiv:2107.07511 (Foundations and Trends in ML, 2023).
- Fleiss, Cohen. *The Equivalence of Weighted Kappa and the Intraclass Correlation Coefficient.* 1973. (Quadratic-weighted kappa for ordinal agreement.)
- Krippendorff. *Content Analysis: An Introduction to Its Methodology.* (Krippendorff's alpha.)
- Cole et al. *Selectively Answering Ambiguous Questions.* 2023.
- Kamath, Jia, Liang. *Selective Question Answering under Domain Shift.* ACL 2020.
- Wen et al. *Know Your Limits: A Survey of Abstention in Large Language Models.* TACL 2025.
- Zhang et al. *Mind the Confidence Gap.* Feb 2025 (verbalized confidence 80–100% clustering; ECE ≥ 0.30 on knowledge-intensive tasks).