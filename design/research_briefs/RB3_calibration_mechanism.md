# RB3 — Calibration of the adjudication agent (the make-or-break)

**Feeds:** Component 4 (confidence + abstention) and Component 6b (the scorer's calibration
metric). Can run in parallel with RB2. This is the highest-risk part of the whole system
(brief §8): the adjudication agent produces both the graded verdict AND the corpus label it
is scored against — it grades its own homework. If it is confidently wrong, the metrics look
clean and the tool is confident nonsense. This brief de-risks that.

## The question

How do we make the agent's graded (substantive-support) judgements **calibrated and honest** —
its stated confidence tracking its actual accuracy — with the ability to **abstain** rather than
force a grade, and how do we **measure** calibration in the scorer? Return a concrete mechanism
and a concrete metric.

## Scope and sources to cover

- **Confidence estimation for LLM judgements**: verbalized confidence and its documented
  failure modes (systematic overconfidence, insensitivity to difficulty); logit/token-prob
  based confidence; **self-consistency / agreement across samples** as a confidence signal;
  ensemble/debate agreement.
- **Selective prediction / abstention**: risk–coverage tradeoffs, thresholds for
  "NOT_ENOUGH_INFO," and how abstention is scored (abstaining on a genuinely ambiguous case is
  correct behavior, not failure).
- **Calibration metrics**: Expected Calibration Error (ECE), Brier score, reliability diagrams,
  selective risk–coverage curves, AUROC of confidence-vs-correctness — which are meaningful on a
  **small, agent-labeled** corpus, and their small-sample caveats.
- **Conformal prediction** as an option for distribution-free confidence sets on the grade.
- **Human-in-the-loop as a calibration check** (not a labeling dependency): how to use a small
  human-verified sample to validate that the agent's confidence is calibrated and unbiased.

## Required deliverable (return exactly this)

1. **Confidence-production mechanism** for C4: the concrete recipe (e.g. self-consistency over N
   adversarial rounds → agreement fraction, optionally combined with a verbalized-confidence
   cross-check), producing a confidence that is meant to correlate with correctness — with a
   rationale for the choice over the alternatives.
2. **Abstention policy**: the decision rule / threshold for emitting `NOT_ENOUGH_INFO` on the
   substantive axis, and how abstentions are recorded so they are not silently counted as
   wrong.
3. **Scorer calibration metric(s)**: which metric(s) the harness (C6b) reports on the graded
   axis, computed per-axis, with the small-sample caveat stated, plus how to render a
   reliability view.
4. **Human spot-check protocol**: sample size, what the human labels, and the **pass criteria**
   that certify the agent's labels are calibrated enough to trust the corpus — designed as a
   check on a *sample*, never full-corpus labeling.
5. **Overconfidence detection + correction**: how to detect systematic overconfidence and what
   to do (temperature on verbalized confidence, threshold recalibration, or fall back to
   agreement-based confidence).

## Acceptance criteria

- On our corpus, verdicts the mechanism marks high-confidence are **measurably** more accurate
  than low-confidence ones (a monotone confidence→accuracy relationship the scorer can show).
- The scorer emits at least one calibration number (e.g. ECE or selective-risk) per graded axis,
  not just accuracy.
- Abstention fires on constructed genuinely-ambiguous cases and does not fire on the clear ones.
- The human spot-check protocol is concrete enough to execute on ~20–40 sampled cases.
