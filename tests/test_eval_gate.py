"""Unit tests for the fast, deterministic eval loop — durable results, offline scoring, and the gate.

Stdlib `unittest` only. PURE OFFLINE — NO network, NO key, NO model calls. The reproduction tests read
the COMMITTED cal30 durable results + reference (deterministic committed data, not gitignored
outputs); the gate pass/fail tests use hermetic synthetic fixtures. Run:

    python -m unittest discover -s tests
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

_SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from citeval import eval as E
from citeval import gate as G
from citeval import scorer as S
from citeval.contracts import AxisFinding, CitedIdentifier, GroundedRecord, RetractionInfo, Verdict
from citeval.prompts import NON_SUBSTANTIATING, NOT_ENOUGH_INFO

WORKSPACE = pathlib.Path(__file__).resolve().parent.parent
CAL = WORKSPACE / "corpus" / "calibration"
RESULTS_CAL30 = CAL / "results_cal30.jsonl"
REF_V2 = CAL / "graded_reference_v2.jsonl"
THRESHOLDS = CAL / "gate_thresholds.json"

# The frozen cal30 baseline — the offline path must reproduce these to the last digit or a
# metric-drift regression has slipped in. Reseeded at thresholds_version 3 (code f99d21f) after the
# C4 direction-reversal re-grade: the confident-wrong tail cleared (Ce11 no longer contradicted; A27
# now exact), graded_adjacent -> 1.0, qwk -> 0.895, recal_loo_ece -> 0.079; and Bs09 (previously a
# grounding error) now grades, so n_errors 1 -> 0 and n 29 -> 30.
EXPECT = {
    "retraction_prf": (1.0, 1.0, 1.0),
    "scope_prf": (1.0, 10 / 11, 1.0),      # WO-C3: overrides removed; Bs22 caught natively, Bp01 the
                                           # sole honest FN (general claim vs infant-only source) -> 10/11
    "control_specificity": (9, 9),
    "overall_accuracy": (29, 30),          # WO-C3: Bp01 is now an honest scope FN (was propped) -> 29/30
    "n": 30, "n_errors": 0,
    "accuracy_exact": 16 / 27,
    "accuracy_adjacent": 1.0,
    "qwk": 0.8950900741787354,
    "ece_equal_mass": 0.3174814814814815,
    "coverage": 0.9643,
    "recal_loo_ece": 0.07872545125114414,
    "recal_auroc": 0.6363636363636364,
    "recal_n_fit": 27,
}


# --------------------------------------------------------------------------------------------------
# Hermetic durable-row builders (no files, no model)
# --------------------------------------------------------------------------------------------------
def drow(cid, gt, pred_ret, pred_scope, status, grade, conf, ref, depth="fulltext"):
    return {"case_id": cid, "corpus": "t", "code_version": "t", "ground_truth_label": gt,
            "pred_retraction": pred_ret, "pred_scope": pred_scope, "retraction_verdict": None,
            "species_scope_verdict": None, "population_scope_verdict": None, "overall": "",
            "status": status, "grade": grade, "confidence": conf, "ref_grade": ref,
            "evidence_depth": depth, "elapsed_s": 1.0}


# A clean synthetic run: objective axes perfect, graded 5/6 exact (1 adjacent miss) → passes.
PASS_ROWS = [
    drow("R1", "RETRACTED", True, False, "GRADED", "fully-supported", 0.9, "fully-supported"),
    drow("R2", "RETRACTED", True, False, "GRADED", "partially-supported", 0.6, "partially-supported"),
    drow("S1", "SCOPE_MISMATCH", False, True, "GRADED", "unsupported-for-the-claim", 0.7,
         "unsupported-for-the-claim"),
    drow("S2", "SCOPE_MISMATCH", False, True, "GRADED", "contradicted", 0.8, "contradicted"),
    drow("C1", "SUPPORTED", False, False, "GRADED", "fully-supported", 0.9, "fully-supported"),
    drow("C2", "SUPPORTED", False, False, "GRADED", "supported-with-overreach", 0.5, "fully-supported"),
]


def refs_from(rows):
    return {r["case_id"]: r["ref_grade"] for r in rows if r.get("ref_grade")}


def thresholds_from(res, tau=0.85, min_dist=2):
    """A thresholds dict whose baseline == the measured metrics of `res` (so no spurious regression),
    with the work-order floors. Lets a fixture's OWN good run define its zero-regression baseline.
    The baseline confident-wrong set is GENUINE errors only (distance >= min_dist)."""
    m = G.extract_metrics(res)
    cw = [c["case_id"] for c in G.confident_wrong_cases(res, tau) if c["distance"] >= min_dist]
    return {
        "thresholds_version": 0, "reference_version": "synthetic", "confident_wrong_tau": tau,
        "confident_wrong_min_distance": min_dist,
        "thresholds": {
            "retraction_precision": {"min": 0.95}, "retraction_recall": {"min": 0.95},
            "scope_precision": {"min": 0.95}, "scope_recall": {"min": 0.80},
            "control_specificity": {"min": 0.95}, "graded_exact": {"min": 0.50},
            "graded_adjacent": {"min": 0.80}, "qwk": {"min": 0.0},
            "recal_loo_ece": {"max": 1.0}, "coverage": {"min": 0.90},
        },
        "baseline": {**{k: m[k] for k in G.OBJECTIVE_METRICS},
                     "coverage": m["coverage"], "recal_loo_ece": m["recal_loo_ece"],
                     "confident_wrong_case_ids": cw},
    }


# --------------------------------------------------------------------------------------------------
class OfflineReproductionTests(unittest.TestCase):
    """`--from-predictions` reproduces the live cal30 scorecard's numbers, purely from the file."""

    def setUp(self):
        self.res = S.score_from_predictions(S._load_results(RESULTS_CAL30),
                                            S.load_reference_grades(REF_V2))

    def test_objective_axes_reproduced(self):
        self.assertEqual(self.res["retraction"]["prf"], EXPECT["retraction_prf"])
        self.assertEqual(self.res["scope"]["prf"], EXPECT["scope_prf"])
        self.assertEqual(self.res["control_specificity"], EXPECT["control_specificity"])
        self.assertEqual(self.res["overall_accuracy"], EXPECT["overall_accuracy"])
        self.assertEqual(self.res["n"], EXPECT["n"])
        self.assertEqual(self.res["n_errors"], EXPECT["n_errors"])

    def test_graded_calibration_reproduced(self):
        cal = self.res["calibration"]
        self.assertEqual(cal["coverage"], EXPECT["coverage"])
        self.assertEqual(cal["n_graded"], EXPECT["recal_n_fit"])
        self.assertAlmostEqual(cal["accuracy_exact"], EXPECT["accuracy_exact"], places=12)
        self.assertAlmostEqual(cal["accuracy_adjacent"], EXPECT["accuracy_adjacent"], places=12)
        self.assertAlmostEqual(cal["qwk"], EXPECT["qwk"], places=12)
        self.assertAlmostEqual(cal["ece"], EXPECT["ece_equal_mass"], places=12)

    def test_recal_loo_ece_matches_recalibrate(self):
        recal = self.res["recal"]
        self.assertEqual(recal["status"], "scored")
        self.assertEqual(recal["n_fit"], EXPECT["recal_n_fit"])
        self.assertAlmostEqual(recal["loo_ece"], EXPECT["recal_loo_ece"], places=12)
        self.assertAlmostEqual(recal["auroc"], EXPECT["recal_auroc"], places=12)

    def test_authoritative_reference_wins_over_baked_ref(self):
        # Corrupt the baked ref_grade snapshot; the --graded-reference file must still drive scoring.
        rows = copy.deepcopy(S._load_results(RESULTS_CAL30))
        for r in rows:
            r["ref_grade"] = "contradicted"          # deliberately wrong snapshot
        res = S.score_from_predictions(rows, S.load_reference_grades(REF_V2))
        self.assertAlmostEqual(res["calibration"]["accuracy_exact"], EXPECT["accuracy_exact"], places=12)

    def test_reproduces_without_explicit_reference(self):
        # Finding #3: the committed file bakes the authoritative v2 ref, so scoring it WITHOUT a
        # --graded-reference must reproduce the SAME numbers as with it (calibration and recal in
        # agreement — no 'pending' recal / stale-v1 calibration split).
        rows = S._load_results(RESULTS_CAL30)
        with_ref = S.score_from_predictions(rows, S.load_reference_grades(REF_V2))
        without = S.score_from_predictions(rows, {})
        for k in ("accuracy_exact", "accuracy_adjacent", "qwk", "coverage"):
            self.assertAlmostEqual(without["calibration"][k], with_ref["calibration"][k], places=12)
        self.assertAlmostEqual(without["recal"]["loo_ece"], with_ref["recal"]["loo_ece"], places=12)
        self.assertAlmostEqual(without["recal"]["loo_ece"], EXPECT["recal_loo_ece"], places=12)
        self.assertEqual(without["recal"]["status"], "scored")   # NOT 'pending'

    def test_committed_backfill_axis_verdicts_present(self):
        # Finding #2: the backfill records retraction + species verdicts (population is null but
        # explicitly flagged, never fabricated — invariant #3).
        rows = [r for r in S._load_results(RESULTS_CAL30) if r.get("status") != "ERROR"]
        self.assertTrue(all(r.get("retraction_verdict") for r in rows))
        self.assertTrue(all(r.get("species_scope_verdict") for r in rows))
        for r in rows:
            if r["ground_truth_label"] == "RETRACTED":
                self.assertIn(r["retraction_verdict"], ("RELIES_ON_RETRACTED", "CITED_PAPER_HAS_EOC"))
            else:
                self.assertEqual(r["retraction_verdict"], "NOT_RETRACTED")

    def test_scope_stands_on_real_opus_c3(self):
        # WO-C3: the _LIVE_SCOPE_OVERRIDES props are REMOVED — cal30 scope stands on the real
        # deterministic Opus-C3 result. Bs22 is caught NATIVELY on the species axis (a Humans-scoped
        # claim citing an animal-only source). Bp01 is a genuine, honest FN (a bare general human claim
        # citing an infant-only source — indistinguishable at claim level from the SUPPORTED Ce03/Ce11
        # controls, so it is not flagged, to hold the specificity floor). scope recall = 10/11.
        rows = {r["case_id"]: r for r in S._load_results(RESULTS_CAL30)}
        self.assertTrue(rows["Bs22"]["pred_scope"])
        self.assertEqual(rows["Bs22"]["species_scope_verdict"], "SCOPE_MISMATCH")
        self.assertFalse(rows["Bp01"]["pred_scope"])          # honest FN, not propped
        self.assertEqual(self.res["scope"]["prf"], (1.0, 10 / 11, 1.0))
        self.assertEqual(self.res["scope"]["missed"], ["Bp01"])


class DeterminismAndPurityTests(unittest.TestCase):
    def test_deterministic_across_runs(self):
        a = S.score_from_predictions(S._load_results(RESULTS_CAL30), S.load_reference_grades(REF_V2))
        b = S.score_from_predictions(S._load_results(RESULTS_CAL30), S.load_reference_grades(REF_V2))
        self.assertEqual(json.dumps(a["calibration"], sort_keys=True),
                         json.dumps(b["calibration"], sort_keys=True))
        self.assertEqual(a["recal"], b["recal"])
        self.assertEqual(a["retraction"], b["retraction"])

    def test_no_network_no_key(self):
        # Unset the key and make ANY network call explode; the offline path must still score + gate.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with mock.patch.object(urllib.request, "urlopen",
                                   side_effect=AssertionError("offline path hit the network")):
                res, gr = E.run(RESULTS_CAL30, REF_V2, THRESHOLDS)
        self.assertTrue(gr.passed)
        self.assertEqual(gr.exit_code, 0)


class GatePassFailTests(unittest.TestCase):
    def test_committed_baseline_passes(self):
        res, gr = E.run(RESULTS_CAL30, REF_V2, THRESHOLDS)
        self.assertTrue(gr.passed, msg=f"breaches: {gr.breaches}")
        self.assertEqual(gr.exit_code, 0)
        self.assertTrue(all(c.passed for c in gr.checks))

    def test_synthetic_passing_fixture_exits_zero(self):
        res = S.score_from_predictions(PASS_ROWS, refs_from(PASS_ROWS))
        gr = G.evaluate_gate(res, thresholds_from(res))
        self.assertTrue(gr.passed)
        self.assertEqual(gr.exit_code, 0)

    def test_seeded_objective_regression_exits_nonzero(self):
        base = S.score_from_predictions(PASS_ROWS, refs_from(PASS_ROWS))
        thr = thresholds_from(base)
        bad_rows = copy.deepcopy(PASS_ROWS)
        bad_rows[1]["pred_retraction"] = False       # miss a retraction → recall 1.0 → 0.5
        res = S.score_from_predictions(bad_rows, refs_from(bad_rows))
        gr = G.evaluate_gate(res, thr)
        self.assertFalse(gr.passed)
        self.assertNotEqual(gr.exit_code, 0)
        self.assertTrue(any(g.kind == "objective-regression" and g.breach for g in gr.gaps))
        self.assertFalse(next(c for c in gr.checks if c.metric == "retraction_recall").passed)

    def test_seeded_graded_exact_below_floor_exits_nonzero(self):
        thr = thresholds_from(S.score_from_predictions(PASS_ROWS, refs_from(PASS_ROWS)))
        bad_rows = copy.deepcopy(PASS_ROWS)
        for r in bad_rows[:4]:                        # 4/6 graded now wrong → exact 0.33 < 0.50
            r["grade"] = "contradicted"
            r["ref_grade"] = "fully-supported"
        res = S.score_from_predictions(bad_rows, refs_from(bad_rows))
        gr = G.evaluate_gate(res, thr)
        self.assertFalse(gr.passed)
        self.assertFalse(next(c for c in gr.checks if c.metric == "graded_exact").passed)

    def test_new_confident_wrong_genuine_is_a_breach(self):
        base = S.score_from_predictions(PASS_ROWS, refs_from(PASS_ROWS))
        thr = thresholds_from(base)                   # baseline genuine-error set is empty here
        bad_rows = copy.deepcopy(PASS_ROWS)
        bad_rows[0]["confidence"] = 0.99              # confident…
        bad_rows[0]["grade"] = "contradicted"         # …and far-wrong (distance 5) vs fully-supported
        res = S.score_from_predictions(bad_rows, refs_from(bad_rows))
        gr = G.evaluate_gate(res, thr)
        self.assertFalse(gr.passed)
        self.assertTrue(any(g.kind == "confident-wrong" and g.breach for g in gr.gaps))
        self.assertEqual([c["case_id"] for c in gr.confident_wrong], ["R1"])

    def test_new_confident_adjacent_is_not_a_breach(self):
        # Refinement 2: confident but ONLY adjacent (distance 1) is info, never a breach.
        base = S.score_from_predictions(PASS_ROWS, refs_from(PASS_ROWS))
        thr = thresholds_from(base)
        rows = copy.deepcopy(PASS_ROWS)
        rows[0]["confidence"] = 0.99
        rows[0]["grade"] = "supported-with-overreach"   # ref fully-supported → distance 1 (adjacent)
        res = S.score_from_predictions(rows, refs_from(rows))
        gr = G.evaluate_gate(res, thr)
        self.assertTrue(gr.passed)                        # adjacency is not an error
        self.assertEqual([c["case_id"] for c in gr.confident_adjacent], ["R1"])
        self.assertEqual(gr.confident_wrong, [])
        self.assertTrue(all(not g.breach for g in gr.gaps if g.kind.startswith("confident-adjacent")))

    def test_committed_confident_wrong_split(self):
        # On the committed cal30 data (post C4 direction-reversal fix): NO genuine confident-wrong
        # errors remain; the confident cases are all adjacent (distance 1).
        res, gr = E.run(RESULTS_CAL30, REF_V2, THRESHOLDS)
        self.assertEqual({c["case_id"] for c in gr.confident_wrong}, set())   # tail cleared
        self.assertEqual({c["case_id"] for c in gr.confident_adjacent},
                         {"A09", "A10", "A13", "A17", "Bp01", "Bs07", "Ch03", "Ch10"})
        self.assertTrue(all(c["distance"] >= 2 for c in gr.confident_wrong))  # vacuously true (empty)
        self.assertTrue(all(c["distance"] == 1 for c in gr.confident_adjacent))
        self.assertTrue(gr.passed)                        # genuine set empty == baseline → no breach

    def test_objective_absent_row_excluded_like_live(self):
        # Finding #1: a resumed-then-objective-failed durable row (pred_retraction=None, status GRADED)
        # must be EXCLUDED from objective metrics (as live score() excludes it from `rows`) but KEPT in
        # the graded calibration — NOT silently re-admitted as a clean negative (bool(None)==False).
        sim = [
            drow("X", "RETRACTED", None, None, "GRADED", "fully-supported", 0.9, "fully-supported"),
            drow("Y", "RETRACTED", True, False, "GRADED", "fully-supported", 0.9, "fully-supported"),
        ]
        res = S.score_from_predictions(sim, {"X": "fully-supported", "Y": "fully-supported"})
        self.assertEqual(res["n"], 1)                          # X excluded from objective rows
        self.assertEqual(res["retraction"]["prf"][1], 1.0)     # recall 1.0, not 0.5 (X not a FN)
        self.assertEqual(res["calibration"]["n_graded"], 2)    # X still in the graded calibration

    def test_missing_metric_fails_closed(self):
        # A metric that can't be computed (no graded rows → qwk None) must FAIL, never silently pass.
        chk = G._cmp(None, 0.6, "min")
        self.assertFalse(chk)
        chk_max = G._cmp(None, 0.2, "max")
        self.assertFalse(chk_max)


class DurableRowTests(unittest.TestCase):
    def test_build_durable_rows_join_and_roundtrip(self):
        rows = [{"case_id": "X", "gt": "RETRACTED", "pred_retraction": True, "pred_scope": False,
                 "overall": "o", "species_verdict": "sv", "population_verdict": "pv",
                 "retraction_verdict": "rv"}]
        grecs = [{"case_id": "X", "status": "GRADED", "grade": "fully-supported", "confidence": 0.9,
                  "ref_grade": "fully-supported", "evidence_depth": "fulltext", "elapsed_s": 1.2}]
        errs = [{"case_id": "E", "status": "ERROR", "error": "boom", "code_version": "v",
                 "elapsed_s": 0.1}]
        out = S.build_durable_rows(rows, grecs, errs, corpus="t", version="v",
                                   gt_by_case={"E": "SUPPORTED"})
        d = {r["case_id"]: r for r in out}
        self.assertEqual(d["X"]["ground_truth_label"], "RETRACTED")
        self.assertEqual(d["X"]["population_scope_verdict"], "pv")
        self.assertEqual(d["X"]["species_scope_verdict"], "sv")
        self.assertEqual(d["X"]["grade"], "fully-supported")
        self.assertEqual(d["E"]["status"], "ERROR")
        self.assertEqual(d["E"]["ground_truth_label"], "SUPPORTED")     # gt backfilled for the error
        res = S.score_from_predictions(out, {"X": "fully-supported"})
        self.assertEqual(res["n"], 1)
        self.assertEqual(res["n_errors"], 1)
        self.assertEqual(res["calibration"]["n_graded"], 1)

    def test_live_graded_run_writes_durable_file(self):
        cases = [{"case_id": f"K{i}", "cited_pmid": str(i), "claim_text": "c",
                  "ground_truth_label": "SUPPORTED"} for i in range(2)]
        script = {"0": ("fully-supported", 0.9, "GRADED", "body"),
                  "1": ("partially-supported", 0.6, "GRADED", "body")}
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(S, "run_slice", _fake_slice(script)):
            S.score(cases, graded=True, out_dir=d, results_dir=d, corpus_label="unit", version="tv")
            durable_path = Path(d) / "unit_tv.jsonl"
            self.assertTrue(durable_path.exists(), "live graded run must write the durable results file")
            durable = S._load_results(durable_path)
        self.assertEqual({r["case_id"] for r in durable}, {"K0", "K1"})
        for r in durable:                                    # full-verdict contract: objective + graded
            self.assertIn("pred_retraction", r)
            self.assertIn("species_scope_verdict", r)
            self.assertIn("population_scope_verdict", r)
            self.assertEqual(r["code_version"], "tv")
            self.assertEqual(r["corpus"], "unit")


class CliSmokeTests(unittest.TestCase):
    """The literal DONE criteria: a passing fixture exits zero, a seeded-fail exits nonzero."""

    def test_make_eval_committed_exits_zero(self):
        r = subprocess.run([sys.executable, "-m", "citeval.eval"], cwd=str(_SRC),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        self.assertIn("GATE: PASS", r.stdout)

    def test_cli_seeded_fail_exits_nonzero(self):
        rows = copy.deepcopy(S._load_results(RESULTS_CAL30))
        for r in rows:
            if r.get("ground_truth_label") == "RETRACTED" and r.get("status") != "ERROR":
                r["pred_retraction"] = False              # break retraction recall on every A-case
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad_results.jsonl"
            bad.write_text("\n".join(json.dumps(x) for x in rows) + "\n")
            r = subprocess.run(
                [sys.executable, "-m", "citeval.scorer", "--from-predictions", str(bad),
                 "--graded-reference", str(REF_V2), "--gate", "--gate-thresholds", str(THRESHOLDS),
                 "--out", d], cwd=str(_SRC), capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0, msg="a seeded objective regression must fail the gate")
        self.assertIn("GATE: FAIL", r.stdout)


# --------------------------------------------------------------------------------------------------
# Minimal fake graded pipeline for the live-write test (no network / no model)
# --------------------------------------------------------------------------------------------------
def _fake_grounded(pmid, full_text=""):
    return GroundedRecord(
        identifier=CitedIdentifier("pmid", pmid), title="t", abstract="a", mesh_all=[],
        organism_tags=[], population_tags=[], sex_tags=[], publication_types=[],
        retraction=RetractionInfo(status="NONE_FOUND"), has_humans=True, full_text=full_text)


def _fake_verdict(pmid, grade, conf, status):
    ev = {"confidence": {"agreement": conf}, "abstained": status == "ABSTAINED",
          "non_substantiating": status == "NON_SUBSTANTIATING"}
    axes = [AxisFinding("retraction", "NOT_RETRACTED", "high", "metadata-grounded", "d"),
            AxisFinding("species_scope", "SCOPE_CONSISTENT", "high", "metadata-grounded", "d"),
            AxisFinding("population_scope", "SCOPE_CONSISTENT", "high", "metadata-grounded", "d"),
            AxisFinding("substantive_support", grade, "high", "model-inferred", "d", ev)]
    return Verdict(claim="x", cited_identifier=CitedIdentifier("pmid", pmid), overall="ok",
                   axis_findings=axes, stub=False)


def _fake_slice(script):
    def _fake(claim_text, cited_pmid=None, cited_doi=None, *, graded=False, client=None, config=None):
        grade, conf, status, ft = script[cited_pmid]
        return {"verdict": _fake_verdict(cited_pmid, grade, conf, status),
                "grounded": _fake_grounded(cited_pmid, ft)}
    return _fake


if __name__ == "__main__":
    unittest.main()
