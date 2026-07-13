# citeval — Evaluation SOP

> **CURRENT (final).** The one-command check is now **`make eval`** — the versioned offline gate has
> landed and `corpus/calibration/gate_thresholds.json` exists (thresholds v4). From the repo root:
>
> ```bash
> make eval    # offline, no key, deterministic, <1s → metric | value | threshold | PASS/FAIL + exit code
> ```
>
> Verified healthy baseline: retraction & scope precision 1.00, **scope recall 0.909** (in-domain,
> un-propped), **QWK 0.90**, within-one-level **1.00**, recalibrated LOO-**ECE 0.08**, coverage 0.96,
> **zero confident-but-wrong**; held-out (ext-45): retraction 1.00, scope recall 0.71. **The sections
> below predate the gate landing and the C4 re-grade — where they quote older figures (QWK 0.70,
> ECE 0.16, or "--gate not yet landed"), `make eval` and these numbers supersede them.**

**TL;DR (offline calibration-only check, still valid)** — from `src/`:
```bash
python -m citeval.recalibrate \
    --predictions ../corpus/calibration/graded_predictions_cal30.jsonl \
    --reference   ../corpus/calibration/graded_reference_v2.jsonl
```
Offline, no key, no network, well under a second. (See §3 for the full baseline.)

This SOP answers three questions, deterministically, every time:

| # | Question | Section |
|---|---|---|
| 1 | Does the system work at all? | §1 Fast deterministic check |
| 2 | How accurate is it right now? | §1 (numbers) + §2 (after a code change) |
| 3 | What's the next gap to fix? | §3 Gap diagnosis |

For architecture/invariants see `CLAUDE.md`. This doc is only the run-book: exact commands,
verified against the current `argparse` definitions and, where noted, against a live run.

---

## Conventions used below

- Run everything from `src/` (`cd "<repo_root>/src"`), matching `CLAUDE.md`. Repo root here is
  `/Users/mythicalhacker/dev/Claude Build Life Sciences`.
- `ANTHROPIC_API_KEY` is required only for commands that pass `--graded` **and** actually need to
  grade a new case (live Opus 4.8 — CLAUDE.md invariant #4, never a cheaper model). §1 needs no key.
  `NCBI_EMAIL` / `NCBI_API_KEY` are optional and only raise NCBI rate limits (3/s → 10/s).
- Files this SOP references (all under repo root):
  - `corpus/calibration/corpus_cal3.jsonl` — 3 cases (one each of RETRACTED / SCOPE_MISMATCH /
    SUPPORTED: A10, Bs05, Ch13). Minimum smoke set — proves all three pipeline branches run.
  - `corpus/calibration/corpus_cal9.jsonl` — 9 cases, stratified 3/3/3 across the same three
    ground-truth labels.
  - `corpus/calibration/corpus_cal15.jsonl` — 15 cases. Exists but is **not** part of the ladder
    in §2 below; an optional extra rung if you want a midpoint between cal9 and cal30.
  - `corpus/calibration/corpus_cal30.jsonl` — the full 30-case calibration slice.
  - `corpus/calibration/graded_reference_v2.jsonl` — the designated-truth `substantive_grade` per
    case_id (30 rows). Per CLAUDE.md's anti-circularity rule this must never be model-generated;
    in practice today it is an LLM full-text read (Claude Science) with a blind decider-adjudicated
    correction pass on ambiguous cases (`grade_provenance` field), **pending the human spot-check**
    noted as outstanding in `design/STATUS.md` item 5. Treat today's accuracy numbers as the best
    available estimate, not yet human-certified.
  - `corpus/calibration/graded_predictions_cal30.jsonl` — cached C4 (Opus 4.8) output from the last
    full cal30 run: 30 rows = 27 `GRADED` + 1 `ABSTAINED` (Ch05, title/MeSH-only) + 1
    `NON_SUBSTANTIATING` (Ch15, background citation) + 1 `ERROR` (Bs09, a transient upstream 529
    "Overloaded" — infra, not a verdict, always excluded from every metric and retried on next run).
  - `corpus/calibration/calibration_map.json` — last fitted Platt map (`A=3.0987, B=-2.375,
    n_fit=27`).
- No `gate_thresholds.json` exists anywhere in the repo today (checked). Don't invent a pass/fail
  cutoff that isn't backed by a committed file — see §3.

---

## 1. Fast deterministic check (offline, no API key, seconds)

The everyday "is it healthy" check. **Must not call the live model.** Two tiers: (a) the
calibration numbers — genuinely, unconditionally offline; (b) the fuller scorecard (objective PRF
+ full graded block) — offline **today**, but by cache-warmth, not by a hard guarantee.

### 1a. Calibration numbers — guaranteed offline (do this first, every time)

```bash
cd src
python -m citeval.recalibrate \
    --predictions ../corpus/calibration/graded_predictions_cal30.jsonl \
    --reference   ../corpus/calibration/graded_reference_v2.jsonl
```
Verified against `recalibrate.py`'s actual `argparse` (`--predictions`, `--reference`, `--out`,
`--reference-name` — nothing else). `recalibrate.py` never imports `grounding.py` or
`adjudicator.py`; it only reads two JSONL files and fits a 2-parameter Platt curve by Newton's
method. There is no code path here to a network call, an API key, or a model call. Live-timed just
now: **0.12s** (`real 0m0.124s`), reproducing exactly:

```
n_fit = 27
[1] RAW ECE                = 0.3386
[2] in-sample recal ECE    = 0.1425   (overstates calibration at small N)
[3] leave-one-out ECE      = 0.1567   <<< the headline, honest number
[4] AUROC raw = recalibrated = 0.684659   IDENTICAL ✓ (proves the monotone map never touched
                                            discrimination or the emitted grade)
    exact-match grade accuracy = 0.5926
```
It also (re)writes `outputs/calibration_map.json` at its default path — **not** the checked-in
`corpus/calibration/calibration_map.json` snapshot. Pass `--out ../corpus/calibration/calibration_map.json`
if you want to update that file in place instead of the scratch copy.

**Read it as:** if this command errors ("nothing to fit") or refuses to run, the two input files
moved or are empty — that's a P0 for this SOP itself, fix that first. If it runs but the printed
numbers are far off the baseline in §3, go to §3's gap table.

### 1b. Full scorecard (objective PRF + coverage/Brier/QWK/AURC) from the same cache

`recalibrate.py` only gives you calibration/discrimination numbers. For the full scorecard block
(coverage, selective risk, Brier, QWK, AURC, reliability bins) plus the objective-axis
(retraction/scope) precision/recall, you need the scorer's **resume** path, pointed at the cached
predictions:

```bash
cd src
mkdir -p ../outputs/scorecard_cal30_check
cp ../corpus/calibration/graded_predictions_cal30.jsonl \
   ../outputs/scorecard_cal30_check/graded_predictions.jsonl   # must be named exactly this
python -m citeval.scorer --graded \
    --corpus ../corpus/calibration/corpus_cal30.jsonl \
    --graded-reference ../corpus/calibration/graded_reference_v2.jsonl \
    --out ../outputs/scorecard_cal30_check
```
Verified against `scorer.py`'s actual `argparse` (`--graded`, `--corpus`, `--graded-reference`,
`--out` all present). The filename `graded_predictions.jsonl` is a hardcoded constant
(`PREDICTIONS_FILE`) the resume logic looks for inside `--out` — it must be renamed exactly, not
just copied under its original name.

**Live-verified just now, with no `ANTHROPIC_API_KEY` set in the shell at all:** this ran in
**3.2 seconds** and produced a full scorecard — 27/27 labeled cases graded (coverage 1.00),
exact 0.593, ±1-adjacent 0.852, QWK 0.695, AUROC 0.685 (95% CI 0.50–0.86), Brier exact 0.305 /
adjacent 0.131, retraction P/R/Spec 1.00/1.00/1.00, control specificity 9/9. One line said
`Errors: 1 ... Bs09` — see the two caveats below; the run did not stop or need a key.

**Caveat 1 — the objective-axis recompute is network-free today by incidental cache warmth, not
by guarantee.** Every resumed (non-Opus) case still calls `ground()` fresh to recompute the
retraction/scope prediction (the cached predictions file never stores those — only the graded
axis). `ground()` reads `src/citeval/.cache/efetch_pubmed/{pmid}.xml` and
`src/citeval/.cache/mesh_tree.json` before ever hitting the network, and today those caches are
warm for every PMID in `corpus_cal30.jsonl` (confirmed present on disk), so this resolves with
zero network calls. There is no flag that *guarantees* this — a fresh checkout, a cleared cache,
or a different corpus will silently fall back to live NCBI calls (which need no key, but do need
network, and will retry-with-backoff or fail per-case if unreachable).

**Caveat 2 — one case (Bs09) always attempts a live call, and that's fine.** Its stored status is
`ERROR` (a prior transient 529), and the resume logic deliberately **retries** `ERROR` rows rather
than skipping them (`done_ok` in `scorer.py` excludes non-`ERROR` rows only). So every run of this
recipe makes exactly one attempt to grade Bs09 live. Without a key (or without the `anthropic`
package installed — that's the exact failure seen in the live test above:
`ModuleNotFoundError: No module named 'anthropic'`), that attempt fails fast, is caught by the
per-case error isolation (`score()`'s `try`/`except` — "a single bad PMID never aborts a long
run"), gets logged as a fresh `ERROR` row, and is excluded from every metric — exactly as it
already was in the baseline. **No key is required to complete this check.**

**Caveat 3 — the objective-axis numbers you get here are not necessarily the same numbers the
original live run measured.** Resumed cases run with the offline **lexical** scope parser (C3
stub), not live Opus C3. In the live test above this produced scope recall **0.80** (misses:
Bs22, Bp01 — implicit human-relevance claims with no lexical marker), which is the known lexical
floor, not the ~0.91 that `design/STATUS.md` reports for the original live-Opus-C3 run over the
same 30 cases. Don't read a 0.80 here as a regression — see §3's gap table.

### 1c. The clean fix (landing, not yet merged — do not run this today)

A parallel Claude Code lane is adding a `--gate` mode. Once it lands, treat

```bash
python -m citeval.scorer --graded --gate
```
as the pass/fail command for this whole section. **As of this writing it does not exist:**
`python -m citeval.scorer --help` (verified live) lists only `--corpus, --graded,
--graded-reference, --recalibrate, --recalibration-map, --emit-calibration-sample, --limit,
--fresh, -v, --out` — running `--gate` today fails with `error: unrecognized arguments: --gate`.
Confirm it has landed (re-check `--help`) before relying on it; until then, use §1a + §1b above.
The real gap `--gate` (or an equivalent `--from-predictions` mode) should close: a way to compute
`calibrate_graded()` directly from the joined predictions+reference files with **zero** calls to
`run_slice()`/`ground()` — removing both caveats in §1b, not just the Opus-cost one.

---

## 2. Full re-eval (after any C4 / grading code change)

Trigger: any change to `adjudicator.py`, `prompts/*`, the RB1/RB2/RB3 rubric, or `claim_scope.py`
where it affects scope detection. Slow, costs money (every call is live Opus 4.8 — never a
cheaper model), needs `ANTHROPIC_API_KEY`.

```bash
cd src
export ANTHROPIC_API_KEY=sk-...
```

Graduated ladder — each rung uses its own `--out` (so you can diff rungs afterward) and
`--fresh` (force re-grading against the *new* code rather than silently reusing old predictions).
Always pin `--graded-reference` to the v2 file so every rung scores against the same truth:

```bash
# 1. Smoke (~8 min) — one case per ground-truth label; catches plumbing breaks
#    (crashes, all-ERROR runs, schema mismatches, auth failures)
python -m citeval.scorer --graded --fresh \
    --corpus ../corpus/calibration/corpus_cal3.jsonl \
    --graded-reference ../corpus/calibration/graded_reference_v2.jsonl \
    --out ../outputs/scorecard_cal3

# 2. Medium (~30 min) — stratified 3/3/3 across RETRACTED/SCOPE_MISMATCH/SUPPORTED;
#    catches substance regressions across verdict types, not just crashes
python -m citeval.scorer --graded --fresh \
    --corpus ../corpus/calibration/corpus_cal9.jsonl \
    --graded-reference ../corpus/calibration/graded_reference_v2.jsonl \
    --out ../outputs/scorecard_cal9

# 3. Full calibration (30 cases) — the number that matters for §3's baseline
python -m citeval.scorer --graded --fresh \
    --corpus ../corpus/calibration/corpus_cal30.jsonl \
    --graded-reference ../corpus/calibration/graded_reference_v2.jsonl \
    --out ../outputs/scorecard_cal30
```
All three flags/paths verified against the live `--help` output (§1c). Add `-v` (or set
`CITEVAL_PROGRESS=1`) to any of these to get a per-triad-round progress line on stderr — useful
for `tail -f ../outputs/scorecard_calN/graded_predictions.jsonl` while it runs, since predictions
are flushed incrementally per case (a crash or Ctrl-C never loses completed cases).

Approximate timing is per-case wall-clock (7 self-consistency rounds × 3 agents per case, evidence
prompt-cached across rounds) — expect run-to-run variance; don't kill a rung early for running
longer than the estimate.

**If a rung is interrupted partway** (Ctrl-C, laptop sleep, a burst of transient 529s): do **not**
re-run with `--fresh` again — that re-pays for every case that already finished. Re-run the exact
same command **minus `--fresh`**; the resume logic skips completed cases and retries only the
`ERROR` ones.

**After each rung finishes**, immediately run the §1a fast check against *that rung's* fresh
predictions to get its calibration numbers (swap in `scorecard_cal3` / `scorecard_cal9` /
`scorecard_cal30` as appropriate — this is the cal30 example):
```bash
python -m citeval.recalibrate \
    --predictions ../outputs/scorecard_cal30/graded_predictions.jsonl \
    --reference   ../corpus/calibration/graded_reference_v2.jsonl
```
and read that rung's own `../outputs/scorecard_calN/scorecard.md` for the objective-axis PRF and
the full graded block — this run graded everything live, so neither of §1b's caveats apply here.
Only the cal30 rung's numbers are what §3's baseline table below is comparable against (cal3/cal9
are too small for QWK/AUROC to mean much — they're plumbing/substance checks, not calibration
runs).

---

## 3. How to read it / gap diagnosis

| Symptom | Likely cause | Fix |
|---|---|---|
| **Low coverage** (many `ABSTAINED`, few `GRADED`) | Either genuine abstention on thin evidence, or the critic's JSON got truncated before the closing brace (counted as a parse failure, not abstention) | Check the "coverage by evidence depth" block (full-text vs abstract-only) and the `-v`/`CITEVAL_PROGRESS=1` per-round log for `UNPARSED` lines. Genuine abstention on abstract-only evidence is expected and improves with full-text grounding (this is exactly what `design/STATUS.md` documents: coverage rose from 0.21 to 1.00 across the abstract→full-text fix). `UNPARSED` rounds are a real bug — raise `MAX_TOKENS_CRITIC` in `adjudicator.py` or shrink the evidence budget. |
| **Low exact accuracy, high ±1-adjacent accuracy** | Adjacent ordinal noise — boundary fuzziness between neighboring grades on the 6-level scale (`fully-supported → supported-with-overreach → partially-supported → technically-true-but-misleading → unsupported-for-the-claim → contradicted`) | Expected, not a bug. This is exactly why QWK and ±1-adjacent are reported alongside exact-match. Only escalate if ±1-adjacent *also* drops. |
| **High ECE** | Overconfidence — the raw `a_exact` confidence overstates empirical accuracy | Refit: re-run §1a's `recalibrate.py` on the fresh predictions, read the **LOO** ECE (not in-sample — in-sample overstates calibration at small N), then opt in live via `--recalibrate` on `scorer`/`slice_runner` (fails closed — declines a missing/degenerate map, e.g. `A <= 0`). |
| **A confident-wrong case** (high `a_exact` / tier=`high`, but `grade != reference grade`) | A substantive grading error, not a calibration problem | Autopsy, don't re-threshold: re-run that one `case_id` with `-v`/`CITEVAL_PROGRESS=1` and read the raw supporter/refuter/critic transcript (rationale + `output_tokens` are already stored per round) to see what the critic over-weighted. The fix is a prompt/rubric change (RB1/RB2), never a confidence-threshold tweak. |
| **Any objective-axis regression** (retraction or scope P/R/Spec drops from ~1.00) | A grounding bug — retraction and scope are metadata-grounded and metadata overrides model (CLAUDE.md invariant #1); this axis should not drift with model/prompt changes at all | Investigate immediately, P0. Re-run `python -m citeval.build_rw_index` (stale RW index), check `src/citeval/.cache/efetch_pubmed/` for a stale/corrupted cached record, confirm `data/retraction_watch/retraction_candidates.parquet` didn't change shape. **Exception, not a regression:** scope recall reading ~0.65–0.80 instead of ~0.91–1.00 is the known lexical-only C3 fallback floor (no `ANTHROPIC_API_KEY`, or a resumed/offline recompute per §1b's caveat 3) — confirm which C3 path actually ran before treating it as a break. |
| **AUROC near 0.5** | Confidence isn't discriminating correct from incorrect at all | Check the scorecard's "confidence discrimination" line — saturation near 1.0 for nearly every case is the usual cause (histogram bunched in `[0.9,1.0]`); the fix noted in-repo is to raise the critic temperature. Also sanity-check `n_graded` first: AUROC over a handful of cases is noisy on its own, not necessarily broken (see the 95% CI in the baseline below — it's wide). |

### Baseline numbers (reference point)

From the full cal30 run (`corpus/calibration/corpus_cal30.jsonl` × `graded_reference_v2.jsonl`,
N=27 after excluding 1 infra error [Bs09] + 1 abstention [Ch05] + 1 non-substantiating [Ch15] from
30 total). Live-reproduced 2026-07-12 via §1a/§1b exactly as documented above:

| Axis | Metric | Value |
|---|---|---|
| Objective — retraction | Precision / Recall / Specificity | 1.00 / 1.00 / 1.00 |
| Objective — scope (live Opus C3, per `design/STATUS.md`) | Recall | 0.91 |
| Objective — scope (offline lexical stub, §1b's view) | Recall | 0.80 |
| Objective — control specificity | clean / total | 9 / 9 |
| Graded — coverage | graded / labeled | 27 / 27 (1.00) |
| Graded — accuracy | exact | **0.59** (0.593) |
| Graded — accuracy | ±1-adjacent | **0.85** (0.852) |
| Graded — QWK | quadratic-weighted kappa | **0.70** (0.695) |
| Graded — AUROC | conf vs. correctness | **0.68** (0.685; 95% CI 0.50–0.86) |
| Graded — ECE | raw | 0.34 (0.339) |
| Graded — ECE | recalibrated, leave-one-out (headline) | **0.16** (0.157) |
| Graded — Brier | exact / ±1-adjacent | 0.305 / 0.131 |

Read this table by diffing your new run's numbers against it, row for row, using the gap table
above to interpret any material move (roughly: > 0.05 on exact/adjacent/QWK/AUROC, or > 0.05 on
ECE, is worth investigating rather than shrugging off as noise at N=27).

### Gate thresholds

No `gate_thresholds.json` exists in the repo as of this writing (checked `corpus/calibration/` and
repo-wide). Don't invent a pass/fail cutoff that isn't backed by a committed file — that would be
exactly the kind of unverifiable-axis fabrication CLAUDE.md's invariants forbid for the tool
itself; hold this SOP to the same standard. Until `--gate` (§1c) lands with its own thresholds
file, use the baseline table above as the diff-by-eye reference point.
