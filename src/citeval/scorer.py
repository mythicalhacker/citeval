"""C6b — Scorer / harness (objective axes).

Runs the current pipeline over a corpus and reports per-axis + per-class metrics:
retraction detection, species/population scope detection, and specificity on controls.
This is the proof-of-correctness artifact — measured, not asserted.

The graded substantive-support axis is scored once C4 (the adversarial adjudicator) lands;
until then its calibration metric is reported as PENDING and the axis is counted as abstained.

    python -m citeval.scorer                 # scores eval_set.json
    python -m citeval.scorer --corpus path   # scores a generated corpus (jsonl or json)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .slice_runner import EVAL_PATH, run_slice

WORKSPACE = Path(__file__).resolve().parents[2]
OUT_DIR = WORKSPACE / "outputs" / "scorecard"


def _axis(v, axis):
    return next(f for f in v.axis_findings if f.axis == axis)


def _pred(v) -> dict:
    return {
        "retraction": _axis(v, "retraction").verdict in ("RELIES_ON_RETRACTED", "CITED_PAPER_HAS_EOC"),
        "scope": (_axis(v, "species_scope").verdict == "SCOPE_MISMATCH"
                  or _axis(v, "population_scope").verdict == "SCOPE_MISMATCH"),
    }


def _prf(tp, fp, fn, tn):
    prec = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    spec = tn / (tn + fp) if (tn + fp) else None
    return prec, rec, spec


def _fmt(x):
    return "n/a" if x is None else f"{x:.2f}"


def score(cases: list[dict]) -> dict:
    rows = []
    for c in cases:
        r = run_slice(c["claim_text"], cited_pmid=c["cited_pmid"])
        v = r["verdict"]
        pred = _pred(v)
        rows.append({
            "case_id": c.get("case_id", c["cited_pmid"]),
            "gt": c["ground_truth_label"],
            "pred_retraction": pred["retraction"],
            "pred_scope": pred["scope"],
            "overall": v.overall,
            "species_verdict": _axis(v, "species_scope").verdict,
        })

    # Retraction detection: positives = RETRACTED cases; negatives = the rest.
    r_tp = sum(x["gt"] == "RETRACTED" and x["pred_retraction"] for x in rows)
    r_fn = sum(x["gt"] == "RETRACTED" and not x["pred_retraction"] for x in rows)
    r_fp = sum(x["gt"] != "RETRACTED" and x["pred_retraction"] for x in rows)
    r_tn = sum(x["gt"] != "RETRACTED" and not x["pred_retraction"] for x in rows)

    # Scope detection: positives = SCOPE_MISMATCH; negatives = SUPPORTED controls.
    # A-cases excluded (their labeled axis is retraction, not scope) but reported observationally.
    s_rows = [x for x in rows if x["gt"] in ("SCOPE_MISMATCH", "SUPPORTED")]
    s_tp = sum(x["gt"] == "SCOPE_MISMATCH" and x["pred_scope"] for x in s_rows)
    s_fn = sum(x["gt"] == "SCOPE_MISMATCH" and not x["pred_scope"] for x in s_rows)
    s_fp = sum(x["gt"] == "SUPPORTED" and x["pred_scope"] for x in s_rows)
    s_tn = sum(x["gt"] == "SUPPORTED" and not x["pred_scope"] for x in s_rows)

    # Control specificity: SUPPORTED cases clean on BOTH axes.
    controls = [x for x in rows if x["gt"] == "SUPPORTED"]
    clean = sum(not x["pred_retraction"] and not x["pred_scope"] for x in controls)

    # Overall "correct finding" per case.
    def correct(x):
        if x["gt"] == "RETRACTED":
            return x["pred_retraction"]
        if x["gt"] == "SCOPE_MISMATCH":
            return x["pred_scope"]
        return not x["pred_retraction"] and not x["pred_scope"]
    n_correct = sum(correct(x) for x in rows)

    a_scope_fp = [x["case_id"] for x in rows if x["gt"] == "RETRACTED" and x["pred_scope"]]

    return {
        "n": len(rows), "rows": rows,
        "retraction": {"tp": r_tp, "fp": r_fp, "fn": r_fn, "tn": r_tn,
                       "prf": _prf(r_tp, r_fp, r_fn, r_tn)},
        "scope": {"tp": s_tp, "fp": s_fp, "fn": s_fn, "tn": s_tn,
                  "prf": _prf(s_tp, s_fp, s_fn, s_tn),
                  "missed": [x["case_id"] for x in s_rows
                             if x["gt"] == "SCOPE_MISMATCH" and not x["pred_scope"]]},
        "control_specificity": (clean, len(controls)),
        "overall_accuracy": (n_correct, len(rows)),
        "a_scope_observational": a_scope_fp,
    }


def render_scorecard(res: dict) -> str:
    rp, rr, rs = res["retraction"]["prf"]
    sp, sr, ss = res["scope"]["prf"]
    clean, nctrl = res["control_specificity"]
    ncorr, ntot = res["overall_accuracy"]
    L = ["# Scorecard — objective axes (measured)", "",
         f"Corpus: {res['n']} cases. Pipeline: C2 grounding (real) + C3-lite scope (lexical) "
         "+ C4-stub. Graded substantive axis: **PENDING** (adversarial adjudicator + calibration "
         "not yet integrated).", "",
         "## Per-axis metrics", "",
         "| Axis | Precision | Recall | Specificity | TP/FP/FN/TN |",
         "|---|---|---|---|---|",
         f"| Retraction detection | {_fmt(rp)} | {_fmt(rr)} | {_fmt(rs)} | "
         f"{res['retraction']['tp']}/{res['retraction']['fp']}/{res['retraction']['fn']}/{res['retraction']['tn']} |",
         f"| Species/population scope | {_fmt(sp)} | {_fmt(sr)} | {_fmt(ss)} | "
         f"{res['scope']['tp']}/{res['scope']['fp']}/{res['scope']['fn']}/{res['scope']['tn']} |",
         "",
         f"- **Control specificity** (SUPPORTED cases clean on both axes): {clean}/{nctrl}",
         f"- **Overall correct finding**: {ncorr}/{ntot}",
         f"- **Graded-axis calibration**: PENDING (C4 not integrated)", ""]
    if res["scope"]["missed"]:
        L += [f"- **Scope misses (C3-lite limitation, motivates Opus C3 / WO-C3):** "
              f"{', '.join(res['scope']['missed'])} — claim asserts human relevance without an "
              "explicit lexical marker, so the lexical stub cannot detect it.", ""]
    if res["a_scope_observational"]:
        L += [f"- _Observational:_ retracted-case(s) also flagged species mismatch "
              f"({', '.join(res['a_scope_observational'])}) — the cited paper is genuinely "
              "animal-only; not counted in scope metrics.", ""]
    L += ["## Per-case", "", "| case | gt | retraction? | scope? | overall |",
          "|---|---|---|---|---|"]
    for x in res["rows"]:
        L.append(f"| {x['case_id']} | {x['gt']} | {'Y' if x['pred_retraction'] else '·'} | "
                 f"{'Y' if x['pred_scope'] else '·'} | {x['overall'][:46]} |")
    L += ["", "_Retraction + scope labels are metadata-grounded; this scorecard measures the "
          "objective axes. The graded substantive axis is added when C4 lands, with a calibration "
          "metric per RB3._"]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", help="path to a corpus json/jsonl; defaults to eval_set.json")
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()
    if args.corpus:
        p = Path(args.corpus)
        raw = p.read_text().splitlines() if p.suffix == ".jsonl" else None
        cases = [json.loads(l) for l in raw] if raw else json.loads(p.read_text())["cases"]
    else:
        cases = json.loads(EVAL_PATH.read_text())["cases"]
    res = score(cases)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scorecard.md").write_text(render_scorecard(res))
    (out / "scorecard.json").write_text(json.dumps(
        {k: v for k, v in res.items() if k != "rows"} | {"rows": res["rows"]}, indent=2))
    print(render_scorecard(res))
    print(f"[written to {out}/scorecard.md]")


if __name__ == "__main__":
    main()
