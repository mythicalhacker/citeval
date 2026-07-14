# citeval — Built with Claude: Life Sciences

*A citation referee that grades whether a cited paper actually supports the claim citing it —
grounded in external records, adversarially adjudicated on Claude Opus 4.8, proven with a scored eval
corpus, and stress-tested on a held-out set it was never tuned on.*

> **TL;DR** — Three axes (retraction · species/population scope · a six-level *substantive-support*
> grade), every verdict carrying a confidence **tier** and a **provenance** label (metadata-grounded vs.
> model-inferred). Retraction detection is perfect in-domain **and** on a held-out set (P/R **1.00**); the
> graded axis reaches **0.90** quadratic-weighted kappa, is **within one level on every case**, carries
> **zero** confident-but-wrong grades, and recalibrates to an honest **0.08** ECE. Where it's weak
> (population scope — recall **0.71** held-out) we measure it and say so. Reproduce the in-domain
> headlines offline in seconds: `make eval`.

**Navigate this submission.** Start at the [project README](../README.md) · run the **live web UI**
([`server/`](../server/README.md) + [`web/`](../web/README.md) — mock-backed, so it demos with no
API key) · or open the offline, no-key proof pages: the [worked-example showcase](showcase.html) and
the [innovation artifacts](artifacts/index.html). A 2–3 minute guided walkthrough is in
[`DEMO_SCRIPT.md`](DEMO_SCRIPT.md).

---

## Hook

We built a referee for scientific citations: one claim, one cited paper, one question — does the
paper actually support the claim? Partway through, the tool overruled its own answer key: three
citations our corpus had marked clean pointed to genuinely retracted papers — two distinct papers, one
cited twice — and citeval's external grounding was right where our label was wrong. That is the whole thesis in one moment — ground every objective
verdict in external structured truth, and let the metadata overrule the model, even when the model
is us.

## Abstract

citeval takes a scientific claim plus the paper cited to support it and returns a verdict across
three axes: is the cited paper **retracted**, does the claim's **species/population scope** match the
paper's, and how well does the paper **substantively support** the claim on a **six-level scale**.
Every finding carries a confidence **tier** and a **provenance** label — metadata-grounded vs.
model-inferred. The objective axes are grounded in external structured records (Retraction Watch
cross-checked against NCBI; MeSH organism/population tags) under a hard rule: a structured record
beats a model guess. The graded axis runs an adversarial **supporter → refuter → critic** triad on
Claude Opus 4.8, resampled for self-consistency, and calibrated against an independently audited
reference. In-domain, retraction detection is perfect (precision/recall **1.00**), and the graded
axis reaches **0.90 quadratic-weighted kappa**, is **within one level on every case (±1 = 1.00)**,
carries **zero confident-but-wrong grades**, and recalibrates to an honest leave-one-out **ECE of
0.08**. On a **45-case held-out set the system was never tuned on**, retraction still generalizes
perfectly (**1.00**) and the graded fixes hold — and where a weakness exists (scope recall **0.71**,
dragged down by a genuinely ambiguous population case), we measure it and report it rather than
hide it.

## The problem

The dangerous citation error is not the fabricated reference — it is the *real* paper cited for
something it does not quite say. A 2025 systematic review puts the quotation-error rate in the
medical literature at **16.9%**, and most of that is graded distortion — a hedged finding hardened
into a certainty, a mouse result quietly generalized to humans, a number attributed that the paper
never reports — not clean binary fabrication. Meanwhile retracted papers keep being cited as if
live, and 2026 reporting documents fabricated and misattributed citations rising as AI drafting
spreads. The specific, checkable question — *does THIS paper support THIS claim?* — is precisely the
one that literature-scale tools skip: they classify citations that already exist, or synthesize what
the literature says in aggregate, and hand back a bare confidence percentage with no disclosed
basis. citeval answers the narrow question directly, and refuses to answer it with a number it
can't defend.

## The thesis: grounded-and-measured, not model-checks-model

One principle shapes every design decision: **if a choice trades provable grounding for
impressive-looking model output, it is the wrong choice.** Objective facts (retraction, scope) are
decided by external structured data, not by asking a model to grade a model. The subjective axis
(substantive support) is decided by an adversarial process and then *measured* against a reference
that is independent of the grader — and we report not just whether the labels are right but whether
the confidence is honest, and whether any of it survives on data we never tuned on. Where a fact
can't be verified (e.g., dose), it is flagged, never fabricated.

## How it works

**Ingestion, with a verbatim guard.** citeval pulls the citing paper's full text as raw JATS XML
from NCBI EFetch (never the plain-text connector, which strips the `<xref>` tags that locate the
citation). Any claim it stores must be a verbatim substring of that whitespace-normalized text — a
structural defense against the very failure mode the field is worried about.

**Axis 1 — Retraction (metadata-grounded).** The cited identifier is checked against a Retraction
Watch index (~29k records) cross-referenced with NCBI. Two independent sources; a positive from
either is a fact the model cannot overturn.

**Axis 2 — Species/population scope (metadata-grounded + model-judged over-generalization).** MeSH
organism and age check-tags, keyed on tree number, establish the cited paper's actual scope
(deterministic). Claude Opus 4.8 then judges whether the claim over-generalizes beyond it — a claim
that silently drops "in mice," or generalizes an infant-only finding to adults. A mismatch requires
*both* a scope-narrow source (by MeSH) *and* an over-reaching claim, so the metadata gates the
model. No surveyed tool couples MeSH check-tags to claim-level scope-mismatch this way.

**Axis 3 — Substantive support (adversarial, graded, on Opus 4.8).** Holding scope constant, an
adversarial triad grades the paper on a six-level ordinal scale — `fully-supported →
supported-with-overreach → partially-supported → technically-true-but-misleading →
unsupported-for-the-claim → contradicted` — the exact non-binary "spin" that the field's SUPPORT /
REFUTE / NOT-ENOUGH-INFO labels can't express. A **supporter** argues the paper backs the claim, a
**refuter** argues it doesn't, and a **critic** adjudicates from a verbatim decisive span, over
multiple self-consistency rounds (up to seven) with order-randomized, identity-blinded transcripts
to blunt position and self-preference bias. A `contradicted` grade is structurally required to rest
on a verbatim span showing the source's *primary* finding runs opposite the claim — so a reversal
must be grounded, not rhetorical.

**Calibrated confidence.** Confidence is the triad's self-consistency agreement across resampled
rounds, then Platt-recalibrated against the reference. Because the map is monotone, recalibration cut
expected calibration error (raw ECE **0.32** → leave-one-out ECE **0.08**) *without touching
discrimination* — AUROC is identical before and after (**0.64**).

**Provenance and tier on every finding.** Each axis verdict is stamped `metadata-grounded |
text-grounded | model-inferred | stub-not-adjudicated`, so a reader always knows whether a verdict
rests on a database record or a model judgment. Substantive support grades substance only; scope
lives on its own axes; the `overall` rollup is swappable.

## What it caught

**It overruled its own answer key.** Building the objective corpus, the dual-source retraction check
flagged three citations — two distinct papers, one cited twice — as retracted that the corpus's own labels had marked clean. Retraction Watch and
NCBI agreed; the labels were wrong. This is invariant #1 — metadata overrides model — firing against
its own makers.

**It caught a fabricated attribution.** One claim credited a named researcher with showing that a
protein "significantly inhibits vascular smooth-muscle-cell proliferation," citing a paper that was
actually about a microRNA in pelvic-floor dysfunction in rats — a different finding, and the named
author does not appear among the paper's authors. All three independent graders returned
**unsupported-for-the-claim** at full confidence.

**It abstained rather than bluff.** It correctly declined to grade the cases that genuinely couldn't
be graded — one with only title/MeSH metadata available, one a background/comparator citation making
no substantive claim — instead of inventing a grade. Failing safe is the property the whole design
exists to guarantee.

**A held-out test proved it generalizes — and told us where it's weak.** We built a separate 45-case
set the system was never tuned on. Retraction generalized *perfectly* (1.00), and the graded
direction-reversal fix held out-of-sample (zero spurious over-escalations; it still caught a genuine
contradiction). Crucially, the same test exposed that an in-domain scope number we had reported as a
perfect 1.00 was **propped up** and did **not** generalize — real out-of-sample recall was ~0.29. So
we fixed the underlying scope logic honestly (recall to **0.71**, precision *rising*), removed the
prop, and let the in-domain number stand on its own at **0.909**. A "grounded-and-measured" system
has to be willing to catch itself; the held-out set is how it did.

**A blind independent adjudication sided with the system, not the reference.** On the six graded
cases where citeval most disagreed with the held-out reference, a blind independent read (claim +
paper only, no answer shown) sided with **citeval on four of six** — the single-pass reference was
the harsher, wrong side. The two it lost are reported honestly below.

## Results

**Objective axes — in-domain (live Opus 4.8 pipeline):**

| Axis | Precision | Recall | Specificity |
|---|---|---|---|
| Retraction | **1.00** | **1.00** | **1.00** (10 caught, 0 false positives) |
| Species/population scope | **1.00** | **0.909** | **1.00** (10/11; one documented population false-negative) |
| Controls clean | — | — | **1.00** |

**Graded axis — N=27 vs. the blind-decider-audited reference:**

| Metric | Value |
|---|---|
| Quadratic-weighted kappa | **0.90** |
| Within-one-level agreement | **1.00** |
| Exact agreement (grade == reference) | 0.59 (16/27) |
| Recalibrated calibration error (raw → leave-one-out ECE) | 0.32 → **0.08** |
| AUROC (confidence vs. correctness) | 0.64 |
| Coverage (gradable cases graded) | 0.96 (one honest abstention) |
| Confident-but-wrong (high confidence, off by ≥2 levels) | **0** |

**Held-out — 45 fresh cases, never tuned on (out-of-sample):**

| Axis | Result |
|---|---|
| Retraction | P / R / F = **1.00** — generalizes perfectly |
| Scope | precision **0.92**, recall **0.71** (species 0.83, population 0.40), specificity 0.94 |
| Graded (blind tiebreak on the 6 disagreements) | independent adjudication sided with citeval **4/6** |

Read together: the objective half is proven *and generalizes* — retraction is perfect in-domain and
out-of-sample. The graded half is well-calibrated in-domain (κ 0.90, within one level on every case,
honest ECE 0.08, no confident errors) and, out-of-sample, holds up better than a harsh single-pass
reference credits it. And the one real weakness — population scope — is measured, named, and left
honest rather than papered over.

## Honest limitations

- **Population scope recall is genuinely weak (0.40 held-out).** A general claim citing a
  pediatric-only paper is unresolvable from the claim text alone — our own reference labels the
  identical shape *both* ways depending on context we can't see — so we hold precision and accept the
  false-negative rather than flag real controls. An honest ceiling, not a bug we can wish away.
- **The held-out graded reference is a single-pass AI grade, not decider-audited.** The blind
  tiebreak (4/6 for the system) is our evidence that citeval is often the *more* right side, but the
  held-out graded accuracy is preliminary until that reference is adjudicated.
- **N is small** (27 in-domain + 45 held-out) and the calibration map is provisional. AUROC-on-exact
  is modest (0.64) because a mild "supported-with-overreach" lean keeps exact agreement at 0.59 even
  though *every* grade is within one level.
- **Two residual graded errors out-of-sample** — a missed contradiction and an over-confident
  non-substantiating call: the direction-reversal fix grounds the `contradicted` grade but does not
  guarantee catching every reversal.
- **The reference is an independent AI reviewer**, not a human gold standard — independent of the
  grader (the anti-circularity property that matters), but human certification is still pending. And
  an adversarial triad on Opus per verdict is deliberately slow and costly: this is a deep checker
  for the one citation that matters, not a bulk bibliography screener.

## What's next

Per our landscape analysis (`docs/LANDSCAPE.md`), citeval is deliberately **narrow-and-deep** where
the shipped field — Scite, Consensus, Elicit — is broad-and-shallow, and the research benchmarks
(SciFact, MultiVerS, DeepSciVerify) stay at a flat three-way label. citeval's edges are the ones that
survived scrutiny — including a held-out test: metadata that structurally overrides the model, a
MeSH-grounded scope axis, per-verdict provenance, a six-level ordinal for spin, and — rare for a
claim-checker — a *measured, anti-circular, out-of-sample-tested* calibration number. The honest next
steps follow directly from the limitations: (1) close the population-scope gap (resolve
general-vs-pediatric with citing-context, the one bounded weakness the held-out set found); (2)
certify the reference with a human spot-check and grow the graded set; (3) expand corpus scale beyond
the low hundreds. We are not trying to out-scale Scite. We are trying to be the checker you trust on
the one citation that matters — and to prove, with numbers on data we never tuned on, that the trust
is earned.

---

*Reproduce the in-domain headline numbers offline in seconds: `make eval` (details in
`docs/EVAL_SOP.md`). Corpus, predictions, the blind-decider-validated reference, the held-out set, and
the fitted calibration map are in `corpus/calibration/`; the scored harness is
`python -m citeval.scorer`, gated by `python -m citeval.eval`.*
