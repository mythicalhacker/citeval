"""`python -m citeval.eval` — the fast, deterministic health check we run after EVERY change (req #4).

Offline-scores the committed cal30 durable results against the committed decider-corrected reference,
runs the versioned GATE, prints PASS/FAIL + numbers + gaps, and exits nonzero on any breach.

PURE OFFLINE: no pipeline, no NCBI, no ANTHROPIC_API_KEY, no network. Runs in well under a second, so
it is cheap enough to run on every change (that is the whole point — the ~1–2 hr live graded run and
the cache-dependent "offline" recompute are NOT a health check; this is).

    python -m citeval.eval                 # score committed cal30 + gate; exit nonzero on breach
    python -m citeval.eval --no-gate       # scorecard only (no PASS/FAIL, always exit 0)
    python -m citeval.eval --print-baseline # emit measured metrics as a baseline block (to reseed)
    make eval                              # same thing, from the repo root
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import gate as G
from . import scorer as S

WORKSPACE = Path(__file__).resolve().parents[2]
CAL = WORKSPACE / "corpus" / "calibration"
DEFAULT_RESULTS = CAL / "results_cal30.jsonl"
DEFAULT_REFERENCE = CAL / "graded_reference_v2.jsonl"
DEFAULT_THRESHOLDS = CAL / "gate_thresholds.json"


def run(results_path: Path, reference_path: Path, thresholds_path: Path, *,
        do_gate: bool = True) -> tuple[dict, "G.GateResult | None"]:
    """Offline-score `results_path` against `reference_path` and (optionally) gate. Returns
    (scorecard_res, gate_result_or_None). No network / model / key."""
    results = S._load_results(results_path)
    references = S.load_reference_grades(reference_path)
    res = S.score_from_predictions(results, references, version="offline")
    if not do_gate:
        return res, None
    thresholds = G.load_thresholds(thresholds_path)
    return res, G.evaluate_gate(res, thresholds)


def _print_baseline(res: dict, tau: float) -> None:
    """Emit the measured metrics as a `baseline` block — paste into gate_thresholds.json to reseed
    after an intended, reviewed change to the baseline."""
    m = G.extract_metrics(res)
    cw = [c["case_id"] for c in G.confident_wrong_cases(res, tau)]
    block = {
        "retraction_precision": m["retraction_precision"], "retraction_recall": m["retraction_recall"],
        "retraction_specificity": m["retraction_specificity"],
        "scope_precision": m["scope_precision"], "scope_recall": m["scope_recall"],
        "scope_specificity": m["scope_specificity"], "control_specificity": m["control_specificity"],
        "graded_exact": m["graded_exact"], "graded_adjacent": m["graded_adjacent"], "qwk": m["qwk"],
        "coverage": m["coverage"], "recal_loo_ece": m["recal_loo_ece"], "auroc": m["auroc"],
        "confident_wrong_case_ids": cw,
    }
    print(json.dumps({"baseline": block}, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description="Fast offline eval gate for citeval.")
    ap.add_argument("--results", default=str(DEFAULT_RESULTS),
                    help="durable results jsonl (default: committed cal30)")
    ap.add_argument("--reference", default=str(DEFAULT_REFERENCE),
                    help="decider-corrected reference jsonl (default: graded_reference_v2)")
    ap.add_argument("--thresholds", default=str(DEFAULT_THRESHOLDS),
                    help="gate_thresholds.json (default: committed)")
    ap.add_argument("--no-gate", dest="gate", action="store_false",
                    help="print the scorecard only; skip the gate (always exits 0)")
    ap.add_argument("--print-baseline", dest="print_baseline", action="store_true",
                    help="emit the measured metrics as a baseline block (to reseed the thresholds)")
    ap.add_argument("--quiet", action="store_true", help="print the gate table only, not the scorecard")
    args = ap.parse_args()

    res, gr = run(Path(args.results), Path(args.reference), Path(args.thresholds),
                  do_gate=args.gate and not args.print_baseline)

    if args.print_baseline:
        tau = G.load_thresholds(args.thresholds).get("confident_wrong_tau", 0.85)
        _print_baseline(res, tau)
        return

    if not args.quiet:
        print(S.render_scorecard(res))
    if gr is None:
        print("[eval] scorecard only (--no-gate) — no PASS/FAIL")
        return
    print(G.render_gate(gr))
    sys.exit(gr.exit_code)


if __name__ == "__main__":
    main()
