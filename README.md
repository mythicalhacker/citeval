# citeval

**A citation referee for scientific claims.** Give citeval a claim and the paper cited to support it.
It checks retraction records, compares the claim's scope with the paper's metadata, and uses Claude
Opus 4.8 to assess whether the text supports the claim.

Built for **Built with Claude: Life Sciences** (Development Track).

On a 45-case development set, citeval flagged all 12 retraction cases and none of the other 33.
On the same set, the scope checker caught 10 of 12 species mismatches and 2 of 5 population
mismatches, with one false positive. We used these cases to diagnose and repair the scope checker.
The separate substantive-support evaluation uses model-generated reference grades.

## The problem

The dangerous citation error isn't the fabricated reference — it's the *real* paper cited for something
it doesn't quite say. A 2025 systematic review puts the quotation-error rate in the medical literature at
**16.9%**, and most of it is graded distortion: a hedged finding hardened into a certainty, a mouse
result quietly generalized to humans, a number attributed that the paper never reports. Meanwhile
retracted papers keep being cited as if live. citeval answers the narrow, checkable question — *does THIS
paper support THIS claim?* — and refuses to answer it with a number it can't defend.

## Where the evidence comes from

Retraction status comes from publication records. MeSH descriptors identify the species and
populations a paper covers. A model judges whether the citing claim extends beyond that scope.
For substantive support, we compare the adjudicator's grades with separate model-generated readings
of the paper. The [calibration reference](corpus/calibration/README.md) records how those labels were produced.

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

## Results

| Evaluation | Recorded outcome |
|---|---|
| Retractions, original 30 cases | Flagged 10 of 10 retraction cases and none of the other 20. |
| Retractions, 45-case extension | Flagged 12 of 12 retraction cases and none of the other 33. |
| Substantive support, original set | On 27 graded cases, 16 exact matches and all 27 within one level of the model reference. Quadratic-weighted kappa was 0.90. Raw expected calibration error was 0.32 and the leave-one-out estimate after recalibration was 0.08. |
| Scope, original set | Detected 10 of 11 mismatches with no false positives. |
| Scope, 45-case extension | Detected 12 of 17 mismatches with one false positive after the scope repair. |

The [original results](corpus/calibration/results_cal30.jsonl) include revised grades from a prompt
repair prompted by errors on the original set. The [extension results](corpus/calibration/results_ext_objective.jsonl)
record retraction and scope decisions. A [before-and-after report](outputs/wo_c3_scope_report.md)
documents how the scope logic changed after inspecting failures on the extension. The repaired
system still needs evaluation on fresh cases.

## Reproduce it

The offline gate scores the original 30 saved results and requires no API key:

```bash
make eval        # fast offline gate: scores the committed corpus, runs the versioned gate, prints PASS/FAIL + numbers
make test        # full unit-test suite
```

Running the live pipeline on a new claim + paper needs `ANTHROPIC_API_KEY` (and, for higher NCBI limits,
`NCBI_EMAIL` / `NCBI_API_KEY`).

## Run the live UI

A read-only web surface over the pipeline — a live five-stage stepper, the adversarial-debate replay,
and running cost/ETA — that **demos with no API key** (the web app is mock-backed by default). From the
repo root, in two terminals:

```bash
# terminal 1 — API on 127.0.0.1:8000
cd server && pip install -r requirements.txt && python main.py

# terminal 2 — UI on http://localhost:5173 (mock-backed, no key needed)
cd web && npm install && npm run dev
```

- **No build?** Open [`web/standalone/app.html`](web/standalone/app.html) straight in a browser — a
  zero-dependency fallback of the same UI.
- **No key?** The server's `GET /api/showcase` route is keyless — it returns four cached,
  fully-populated verdicts (retraction catch, species-scope mismatch, graded over-reach, honest
  abstention), so a judge renders real output with nothing to configure. An `ANTHROPIC_API_KEY` is
  needed only to start a *new* live run.
- **Prefer to read?** The same cases are baked into offline, no-key proof pages — the
  [worked-example showcase](docs/showcase.html) and the
  [innovation artifacts](docs/artifacts/index.html) — and a 2–3 minute judge walkthrough is in
  [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).

The static demo pages and scorecard text retain the terminology used at the July 2026 event.
For the source of the reference grades and the reuse of the 45 cases, see the [current results](#results).

More detail: [`server/README.md`](server/README.md) · [`web/README.md`](web/README.md).

## What it caught

- **It overruled its own answer key.** Building the objective corpus, the dual-source retraction check
  flagged papers as retracted that the corpus's own labels had marked clean. Retraction Watch and NCBI
  agreed; the labels were wrong — the metadata-overrides-model rule firing against its own makers.
- **It caught a fabricated attribution** — a claim crediting a named researcher with a finding from a
  paper that was actually about something else; three model grades returned
  *unsupported-for-the-claim* at full confidence.
- **It abstained rather than bluff** on cases that genuinely couldn't be graded, instead of inventing a
  grade.
- **The extension exposed missed scope mismatches.** The first version found 5 of 17 on the
  extension. After changes to the scope logic it found 12 of 17 on those same cases.

## Limitations

The repaired scope checker missed three of five population mismatches on the extension. The original
set supplied examples for a grading prompt repair, and substantive-support agreement measures
agreement with model labels. Human review and a new evaluation set would test whether these results
carry over. See the [original hackathon writeup with a later correction](docs/SUBMISSION.md).

## Repo map

- **`src/citeval/`** — the package: `grounding.py` (retraction × scope), `claim_scope.py` (Opus scope),
  `adjudicator.py` (the graded triad), `scorer.py` / `eval.py` (the scored harness + gate),
  `reporting.py` (verdicts).
- **`docs/`** — [`SUBMISSION.md`](docs/SUBMISSION.md) (full writeup), [`LANDSCAPE.md`](docs/LANDSCAPE.md)
  (competitive analysis), `showcase.html` (offline visual case walkthrough), `EVAL_SOP.md`.
- **`corpus/calibration/`** — the corpus, saved predictions, model-generated reference grades, the
  45-case extension, and the fitted calibration map.
- **`data/retraction_watch/`** — the ~29k-record retraction index.
