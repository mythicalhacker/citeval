# citeval

**A citation referee for scientific claims.** Give citeval one claim and the paper cited to support it,
and it decides whether the paper *actually* supports the claim — grounded in external structured
records, adversarially adjudicated on **Claude Opus 4.8**, and proven on a scored eval corpus plus a
held-out set it was never tuned on.

Built for **Built with Claude: Life Sciences** (Development Track).

> **TL;DR** — Three axes (retraction · species/population scope · a six-level *substantive-support*
> grade), every verdict carrying a confidence **tier** and a **provenance** label. Retraction detection
> is perfect in-domain *and* on a held-out set (P/R **1.00**); the graded axis reaches **0.90**
> quadratic-weighted kappa, is **within one level on every case**, carries **zero confident-but-wrong**
> grades, and recalibrates to an honest **0.08** ECE. Where it's weak (population scope), we measure it
> and say so. Reproduce the headline numbers offline in seconds with `make eval`.

## The problem

The dangerous citation error isn't the fabricated reference — it's the *real* paper cited for something
it doesn't quite say. A 2025 systematic review puts the quotation-error rate in the medical literature at
**16.9%**, and most of it is graded distortion: a hedged finding hardened into a certainty, a mouse
result quietly generalized to humans, a number attributed that the paper never reports. Meanwhile
retracted papers keep being cited as if live. citeval answers the narrow, checkable question — *does THIS
paper support THIS claim?* — and refuses to answer it with a number it can't defend.

## Thesis: grounded-and-measured, not model-checks-model

One principle shapes every decision: **if a choice trades provable grounding for impressive-looking model
output, it is the wrong choice.** Objective facts (retraction, scope) are decided by external structured
records, not by asking a model to grade a model — a structured record always overrides the model. The
subjective axis is decided by an adversarial process and then *measured* against a reference that is
independent of the grader, reporting not just whether the labels are right but whether the confidence is
honest, and whether any of it survives on data we never tuned on.

## What it does — three axes, every verdict tiered + provenance-stamped

1. **Retraction** *(metadata-grounded)* — the cited paper is checked against a Retraction Watch index
   (~29k records) cross-referenced with NCBI. Two independent sources; a positive from either is a fact
   the model cannot overturn.
2. **Species / population scope** *(metadata-grounded + model-judged over-generalization)* — MeSH organism
   and age check-tags, keyed on tree number, establish the cited paper's actual scope; Claude Opus 4.8
   then judges whether the claim over-generalizes beyond it (silently drops "in mice", generalizes an
   infant-only finding to adults). A mismatch requires *both* a scope-narrow source *and* an over-reaching
   claim — the metadata gates the model.
3. **Substantive support** *(adversarial, graded on Opus 4.8)* — holding scope constant, a
   **supporter → refuter → critic** triad grades the paper on a six-level ordinal scale
   (`fully-supported → supported-with-overreach → partially-supported → technically-true-but-misleading →
   unsupported-for-the-claim → contradicted`) over multiple self-consistency rounds with order-randomized,
   identity-blinded transcripts — the exact non-binary "spin" that flat SUPPORT / REFUTE / NOT-ENOUGH-INFO
   labels can't express.

## Results (verified offline via `make eval`)

| Axis | Result |
|---|---|
| Retraction — in-domain **and** held-out | precision / recall **1.00** |
| Graded substantive (N=27) | QWK **0.90** · within-one-level **1.00** · recalibrated LOO-ECE **0.08** · **zero** confident-but-wrong · coverage 0.96 |
| Scope — in-domain | precision **1.00** / recall **0.909** |
| Scope — held-out (45 fresh cases, never tuned on) | precision **0.92** / recall **0.71** (species 0.83, population 0.40) |

## Reproduce it

Offline, deterministic, no API key, under two seconds (the retraction index ships pre-built):

```bash
make eval        # fast offline gate: scores the committed corpus, runs the versioned gate, prints PASS/FAIL + numbers
make test        # full unit-test suite
```

Running the live pipeline on a new claim + paper needs `ANTHROPIC_API_KEY` (and, for higher NCBI limits,
`NCBI_EMAIL` / `NCBI_API_KEY`).

## What it caught

- **It overruled its own answer key.** Building the objective corpus, the dual-source retraction check
  flagged papers as retracted that the corpus's own labels had marked clean. Retraction Watch and NCBI
  agreed; the labels were wrong — the metadata-overrides-model rule firing against its own makers.
- **It caught a fabricated attribution** — a claim crediting a named researcher with a finding from a
  paper that was actually about something else; all three independent graders returned
  *unsupported-for-the-claim* at full confidence.
- **It abstained rather than bluff** on cases that genuinely couldn't be graded, instead of inventing a
  grade.
- **A held-out test proved it generalizes — and exposed its own propped metric.** A scope number we had
  reported as a perfect 1.00 did not generalize (~0.29 out-of-sample); we fixed the underlying logic
  honestly (recall to **0.71**, precision *rising*), removed the prop, and let the in-domain number stand
  on its own at **0.909**.

## Honest limitations

Population-scope recall is genuinely weak (0.40 held-out) — a general claim citing a pediatric-only paper
is often unresolvable from the claim text alone. N is small. The calibration reference is an *independent
AI reviewer* — independent of the grader (the anti-circularity property that matters), but not yet
human-certified. An adversarial triad on Opus per verdict is deliberately slow and costly: this is a deep
checker for the one citation that matters, not a bulk bibliography screener. Full detail in
[`docs/SUBMISSION.md`](docs/SUBMISSION.md).

## Repo map

- **`src/citeval/`** — the package: `grounding.py` (retraction × scope), `claim_scope.py` (Opus scope),
  `adjudicator.py` (the graded triad), `scorer.py` / `eval.py` (the scored harness + gate),
  `reporting.py` (verdicts).
- **`docs/`** — [`SUBMISSION.md`](docs/SUBMISSION.md) (full writeup), [`LANDSCAPE.md`](docs/LANDSCAPE.md)
  (competitive analysis), `showcase.html` (offline visual case walkthrough), `EVAL_SOP.md`.
- **`corpus/calibration/`** — the corpus, predictions, the independent reference, the 45-case held-out
  set, and the fitted calibration map.
- **`data/retraction_watch/`** — the ~29k-record retraction index.
