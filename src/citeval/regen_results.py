"""Regenerate the committed cal30 durable results file (req #5) — the offline gate's input data.

The durable full-verdict results file (`scorer.build_durable_rows` schema) is what `--from-predictions`
scores offline. For the historical cal30 run it is reconstructed, WITHOUT re-running the pipeline, by
joining two committed/on-disk artifacts of that run:

  * the graded side  — `corpus/calibration/graded_predictions_cal30.jsonl` (grade + a_exact + depth
    + status per case), and
  * the objective side — the cal30 scorecard's per-case `rows` + `errors` (retraction / scope
    predictions), from `outputs/scorecard_cal30_check/scorecard.json`.

PURE OFFLINE: file I/O only, no model / network / key. Writes
`corpus/calibration/results_cal30.jsonl`. Going forward, live graded runs write this file directly
(see `scorer.score`), so this shim exists only to backfill the pre-existing cal30 run.

    python -m citeval.regen_results
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .scorer import DURABLE_FIELDS, build_durable_rows, load_reference_grades

WORKSPACE = Path(__file__).resolve().parents[2]
CAL = WORKSPACE / "corpus" / "calibration"
DEFAULT_PREDICTIONS = CAL / "graded_predictions_cal30.jsonl"
# COMMITTED objective scorecard (WO-C3 live Opus-C3 objective run) so `make regen-results` with defaults
# reproduces the committed results_cal30.jsonl (scope recall 0.909) from tracked inputs — the earlier
# default pointed at a gitignored, stale pre-enrichment scorecard and could not be reproduced.
DEFAULT_SCORECARD = CAL / "scorecard_cal30_objective.json"
DEFAULT_CORPUS = CAL / "corpus_cal30.jsonl"
DEFAULT_REFERENCE = CAL / "graded_reference_v2.jsonl"
DEFAULT_OUT = CAL / "results_cal30.jsonl"


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# WO-C3 (2026-07-13): cal30 scope stands on the REAL deterministic Opus-C3 result — there are no
# hand-applied scope overrides. The improved C3 (over-generalization stances + pregnancy detection)
# catches Bs22 natively on the species axis (a "Humans"-scoped claim citing an animal-only source).
# Bp01 (a bare general human claim citing an INFANT-only source) is left as a genuine FN: the identical
# general-claim-vs-pediatric-source pattern is labelled SUPPORTED for the Ce03/Ce11 controls in the same
# v2 reference, so flagging Bp01 would false-positive genuine controls below the specificity floor
# (a claim-context distinction invisible to a claim-only scope parse). Precision-first: not flagged.
# The offline gate's cal30 scope recall is therefore the honest 0.909 (Bp01 the sole miss), not a
# propped 1.0, reseeded into gate_thresholds.json.


def _retraction_verdict(row: dict) -> str | None:
    """Reconstruct the retraction-axis verdict string from the run's RECORDED per-case `overall`
    rollup + the metadata-grounded pred_retraction boolean — NOT fabricated (the pre-enrichment
    scorecard did not persist the raw axis string, but `overall` did record the outcome). A retracted
    case's rollup names it ('…RELIES ON A RETRACTED PAPER'); otherwise the axis was NOT_RETRACTED."""
    if row.get("pred_retraction"):
        return "RELIES_ON_RETRACTED" if "RELIES ON A RETRACTED" in (row.get("overall") or "").upper() \
            else "CITED_PAPER_HAS_EOC"
    return "NOT_RETRACTED"


def regenerate(predictions_path: Path, scorecard_path: Path, corpus_path: Path,
               reference_path: Path | None = None, corpus_label: str = "cal30") -> list[dict]:
    """Reconstruct the durable full-verdict rows for a completed run from its prediction + scorecard
    artifacts. Uses the SAME `build_durable_rows` join the live scorer uses, so the reconstructed
    file is schema-identical to a freshly-written one.

    Bakes the AUTHORITATIVE reference (`graded_reference_v2` by default) as each row's `ref_grade`
    snapshot — NOT the stale prediction-time ref — so the committed file is self-consistent with the
    gate baseline and `--from-predictions` reproduces the passing scorecard even without an explicit
    `--graded-reference` (finding #3)."""
    preds = {p["case_id"]: p for p in _jsonl(predictions_path)}
    sc = json.loads(scorecard_path.read_text())
    gt_by_case = {c.get("case_id", c.get("cited_pmid")): c.get("ground_truth_label")
                  for c in _jsonl(corpus_path)}
    ref = load_reference_grades(reference_path) if reference_path else {}

    # The COMMITTED predictions file is the literal source of record for the graded side (req #5), so
    # drive the graded case-list from IT (union with the scorecard's graded_records for any case only
    # present there). This lets the objective side be refreshed from a fresh OBJECTIVE-ONLY scorecard
    # (which carries no graded_records) without dropping the frozen graded predictions — the WO-C3 path,
    # where the objective axes are re-run live but the C4 grades stay sealed.
    sc_graded = {r["case_id"]: r for r in sc.get("graded_records", [])}
    # Exclude any case the objective run recorded as an infra ERROR: build_durable_rows already emits it
    # from sc["errors"], so admitting it here (it may still be GRADED in a prior preds file) would
    # DOUBLE-COUNT it — once as a GRADED row and once as an ERROR row.
    error_ids = {e.get("case_id") for e in sc.get("errors", [])}
    case_ids = [c for c in (list(preds.keys()) or list(sc_graded.keys())) if c not in error_ids]
    graded_records = []
    for cid in case_ids:
        p = preds.get(cid, {})
        r = sc_graded.get(cid, {})
        graded_records.append({
            "case_id": cid,
            "status": p.get("status", r.get("status")),
            "grade": p.get("grade", r.get("grade")),
            "confidence": p.get("confidence", r.get("confidence")),
            # Bake the authoritative reference (else the prediction-time snapshot) so the file scores
            # the same with or without --graded-reference.
            "ref_grade": ref.get(cid, p.get("ref_grade", r.get("ref_grade"))),
            "evidence_depth": p.get("evidence_depth", r.get("evidence_depth")),
            "elapsed_s": p.get("elapsed_s", r.get("elapsed_s")),
        })

    # Enrich the pre-enrichment objective rows with the retraction-axis verdict (reconstructed from
    # the recorded `overall`); species_verdict is already recorded. population_verdict is left null —
    # it needs MeSH population tags the pre-enrichment scorecard did not persist, so per invariant #3
    # it is FLAGGED (null), never fabricated. Live runs going forward record all three directly.
    obj_rows = [dict(row, retraction_verdict=_retraction_verdict(row)) for row in sc.get("rows", [])]

    # code_version stamp: the durable file is a TWO-provenance join — the graded side from the frozen
    # predictions, the objective/scope side from the (separately-versioned) scorecard. Record BOTH so the
    # scope verdicts are not misattributed to the graded code (review #7). Collapse to a single string
    # when they agree.
    versions = Counter(p.get("code_version") for p in preds.values() if p.get("code_version"))
    graded_ver = (versions.most_common(1)[0][0] if versions
                  else (sc.get("errors") or [{}])[0].get("code_version", "cal30-regen"))
    obj_ver = sc.get("code_version") or ""
    version = (f"{graded_ver} (graded) + {obj_ver} (objective/scope)"
               if obj_ver and obj_ver != graded_ver else graded_ver)

    durable = build_durable_rows(obj_rows, graded_records, sc.get("errors", []),
                                 corpus=corpus_label, version=version, gt_by_case=gt_by_case)
    return durable


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--predictions", default=str(DEFAULT_PREDICTIONS))
    ap.add_argument("--scorecard", default=str(DEFAULT_SCORECARD))
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    ap.add_argument("--reference", default=str(DEFAULT_REFERENCE),
                    help="authoritative reference to bake as each row's ref_grade snapshot")
    ap.add_argument("--corpus-label", default="cal30")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    durable = regenerate(Path(args.predictions), Path(args.scorecard), Path(args.corpus),
                         reference_path=Path(args.reference) if args.reference else None,
                         corpus_label=args.corpus_label)
    Path(args.out).write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in durable) + "\n")
    n_err = sum(1 for d in durable if d.get("status") == "ERROR")
    n_pop_null = sum(1 for d in durable if d.get("status") != "ERROR"
                     and d.get("population_scope_verdict") is None)
    print(f"[regen] {len(durable)} durable full-verdict row(s) ({n_err} ERROR) → {args.out}")
    print(f"[regen] baked ref_grade from authoritative reference: {args.reference}")
    print(f"[regen] fields: {', '.join(DURABLE_FIELDS)}")
    if n_pop_null:
        print(f"[regen] NOTE: population_scope_verdict is null on {n_pop_null} backfilled row(s) — the "
              "pre-enrichment scorecard did not persist MeSH population tags, so it is FLAGGED not "
              "fabricated (invariant #3). Live runs record all three axis verdicts directly.")


if __name__ == "__main__":
    main()
