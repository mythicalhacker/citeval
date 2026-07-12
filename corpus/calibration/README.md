# `corpus/calibration/` — graded-axis calibration reference

## `graded_reference_v2.jsonl`

The **decider-corrected reference** (v2) — the *designated truth* for the graded
`substantive_support` axis. Each row is `{"case_id", "grade"}`, where `grade` is one of the six RB1
ordinal grades (`fully-supported` … `contradicted`). This is **human / decider-corrected** truth,
never model-generated: the whole point of an external reference is to keep C4 from grading its own
homework. `citeval.recalibrate` joins it to `outputs/scorecard/graded_predictions.jsonl` and fits the
`a_exact → P(correct)` Platt map against it.

### Provenance (READ THIS)

This file was **reconstructed** from the `ref_grade` column recorded per case in
`outputs/scorecard/graded_predictions.jsonl` (the full-30 graded run). It is verified to be the same
labels the calibration brief's diagnostics were computed from — joining it reproduces the brief's
cited numbers **exactly**:

| statistic | brief | reproduced |
|---|---|---|
| N (graded, ordinal ref) | 27 | **27** |
| RAW ECE (per-`a_exact`-value bins) | ~0.333 | **0.3333** |
| `a_exact == 1.0` bin accuracy | ~71–86% | **73.7%** (14/19) |
| AUROC (`a_exact` vs exact-correct) | ~0.69–0.75 | **0.7528** |

If the manager holds the canonical `graded_reference_v2.jsonl` and it differs from this
reconstruction, **overwrite this file with the canonical copy and re-run the one command** — the map
refits with no code change:

```
cd src
python -m citeval.recalibrate \
    --predictions ../outputs/scorecard/graded_predictions.jsonl \
    --reference   ../corpus/calibration/graded_reference_v2.jsonl
```

The 3 non-graded cases in the run (1 `ERROR`, 1 `ABSTAINED`/NEI, 1 `NON_SUBSTANTIATING`/`N/A`) have no
ordinal reference and are correctly excluded from the fit — hence 27, not 30.
