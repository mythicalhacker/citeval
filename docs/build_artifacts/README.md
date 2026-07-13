# Innovation artifacts (W1-INNOVATION)

Small, **offline, self-contained** HTML pages that make citeval's discipline visible —
demo insurance that renders with the Wi-Fi off, **zero model calls, no API key**.

Each page is *baked* at build time from committed calibration data, so its figures can
never drift from the files that back them. Nothing here imports `citeval` or edits
`src/` — the pages render from committed data alone.

## Build

```bash
python docs/build_artifacts/build_all.py     # regenerate all five pages
```

Runs from anywhere; exits non-zero if a committed number drifts past one of the
build-time assertions, so it doubles as a lightweight regression check. Open the
result at `docs/artifacts/index.html` (plain `file://` works — there are no external
resources).

## The pages

| Build script | Output | What it shows | Reads from |
|---|---|---|---|
| `build_index.py` | `index.html` | Cross-linked overview | all of the below |
| `build_climbdown.py` | `climbdown.html` | It caught its own propped scope metric (1.00 → 0.294 held-out → 0.71 fixed), the confident-wrong tail, and the calibration honesty (raw ECE 0.32 → recal 0.079) | `gate_thresholds.json`, `calibration_map.json`, `scorecard_cal30_objective.json`, `graded_reference_v2.jsonl` |
| `build_spin_spectrum.py` | `spin_spectrum.html` | The six-level citation-fidelity ordinal, one real anchor case per rung; level 3 is defined-but-never-assigned | `spotcheck/decider_packet.md`, `graded_reference_v2.jsonl`, `graded_reference_ext.jsonl`, `corpus_cal*.jsonl` |
| `build_tiebreak.py` | `tiebreak_console.html` | The 6 held-out disagreements, an independent blind read, and the transparent 4/6 tally (2 clean + 2 interpretive + 2 honest losses) | `ext_tiebreak_6.json`, `corpus_cal_ext.jsonl` |
| `build_debate_replay.py` | `debate_replay.html` | The supporter/refuter/critic triad replayed round-by-round for A27 and Ce11, with scope objections routed away from the grade | `transcripts/debate_A27_Ce11.json` |

`_common.py` is the shared design system (dataviz-validated palette, HTML shell,
cross-link nav) — not an artifact itself.

## Invariants

- **Self-contained:** all CSS/JS inline; no external fonts, scripts, or images. The
  only external URLs are informational PubMed/DOI links on cited papers.
- **Data-faithful:** every figure, grade, verbatim span and commit hash traces to a
  committed file. Build-time assertions guard the load-bearing numbers.
- **Read-only w.r.t. the package:** `src/citeval/` and `contracts.py` are never touched.
