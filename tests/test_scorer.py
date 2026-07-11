"""Unit tests for C6b scorer — RB3 graded-axis calibration metrics.

Stdlib `unittest` only; pure functions tested directly on a small mocked graded-reference
fixture (no live pipeline, no model). Run:

    python -m unittest discover -s tests
"""
from __future__ import annotations

import pathlib
import sys
import unittest

_SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

from citeval import scorer as S
from citeval.contracts import AxisFinding, CitedIdentifier, GroundedRecord, RetractionInfo, Verdict
from citeval.prompts import NON_SUBSTANTIATING, NOT_ENOUGH_INFO
from citeval.slice_runner import graded_enabled


def rec(cid, grade, conf, status, ref):
    return {"case_id": cid, "grade": grade, "confidence": conf, "status": status, "ref_grade": ref}


# --- fake graded pipeline (no network / no model): drive grade/status/depth per cited_pmid -------
def _fake_grounded(pmid: str, full_text: str = "") -> GroundedRecord:
    return GroundedRecord(
        identifier=CitedIdentifier("pmid", pmid), title="t", abstract="a", mesh_all=[],
        organism_tags=[], population_tags=[], sex_tags=[], publication_types=[],
        retraction=RetractionInfo(status="NONE_FOUND"), has_humans=True, full_text=full_text)


def _fake_verdict(pmid: str, grade: str, conf: float, status: str) -> Verdict:
    ev = {"confidence": {"verbalized": "high", "agreement": conf, "n_samples": 7},
          "abstained": status == "ABSTAINED", "non_substantiating": status == "NON_SUBSTANTIATING"}
    axes = [
        AxisFinding("retraction", "NOT_RETRACTED", "high", "metadata-grounded", "d"),
        AxisFinding("species_scope", "SCOPE_CONSISTENT", "high", "metadata-grounded", "d"),
        AxisFinding("population_scope", "SCOPE_CONSISTENT", "high", "metadata-grounded", "d"),
        AxisFinding("substantive_support", grade, "high", "model-inferred", "d", ev),
    ]
    return Verdict(claim="x", cited_identifier=CitedIdentifier("pmid", pmid), overall="ok",
                   axis_findings=axes, stub=False)


def _make_fake_slice(script: dict, calls: list):
    """script: pmid -> (grade, conf, status, full_text). `calls` records (pmid, graded_flag)."""
    def _fake(claim_text, cited_pmid=None, cited_doi=None, *, graded=False, client=None, config=None):
        calls.append((cited_pmid, graded))
        grade, conf, status, ft = script[cited_pmid]
        return {"verdict": _fake_verdict(cited_pmid, grade, conf, status),
                "grounded": _fake_grounded(cited_pmid, ft)}
    return _fake


class PureMetricsTests(unittest.TestCase):
    def test_brier_exact_and_adjacent(self):
        # all correct, conf 1.0 → 0; wrong at conf 1.0 → 1.0
        self.assertAlmostEqual(S.brier([(1.0, True), (1.0, True)]), 0.0)
        self.assertAlmostEqual(S.brier([(1.0, False)]), 1.0)
        self.assertAlmostEqual(S.brier([(0.5, True), (0.5, False)]), 0.25)
        self.assertIsNone(S.brier([]))

    def test_accuracy_exact_and_adjacent(self):
        preds = [0, 1, 2, 5]
        refs = [0, 0, 5, 5]     # exact: idx0,idx3 ; adj: idx0,idx1,idx3
        self.assertAlmostEqual(S.accuracy(preds, refs), 0.5)
        self.assertAlmostEqual(S.accuracy(preds, refs, adjacent=True), 0.75)

    def test_qwk_perfect_and_known(self):
        self.assertAlmostEqual(S.quadratic_weighted_kappa([0, 2, 5], [0, 2, 5]), 1.0)
        # complete disagreement structure gives kappa <= 0
        k = S.quadratic_weighted_kappa([0, 0, 5, 5], [5, 5, 0, 0])
        self.assertLess(k, 0.0)

    def test_selective_risk_coverage_monotone_prefix(self):
        # higher confidence should be the correct ones → low risk at low coverage
        items = [(0.9, True), (0.8, True), (0.4, False), (0.3, False)]
        rc = S.selective_risk_coverage(items)
        self.assertEqual(rc["operating_points"][0]["risk"], 0.0)       # top-1 correct
        self.assertEqual(rc["operating_points"][1]["risk"], 0.0)       # top-2 correct (coverage 0.5)
        # first coverage >= 0.80 is 100% (only 4 items) → 2/4 errors = 0.5
        self.assertEqual(rc["risk_at_80"], 0.5)
        self.assertIsNotNone(rc["aurc"])

    def test_ece_and_reliability_bins_wilson(self):
        items = [(0.9, True), (0.9, True), (0.6, False), (0.6, True)]
        bins = S.reliability_bins(items, n_bins=2)
        self.assertEqual(len(bins), 2)
        for b in bins:
            lo, hi = b["wilson_ci"]
            self.assertLessEqual(lo, b["accuracy"] if False else hi)   # CI well-formed
            self.assertGreaterEqual(lo, 0.0)
            self.assertLessEqual(hi, 1.0)
        self.assertIsNotNone(S.ece(items, n_bins=2))

    def test_auroc_and_bootstrap_deterministic(self):
        items = [(0.9, True), (0.8, True), (0.4, False), (0.2, False)]
        self.assertAlmostEqual(S.auroc(items), 1.0)                     # perfect separation
        ci1 = S.auroc_bootstrap_ci(items, n_boot=200, seed=0)
        ci2 = S.auroc_bootstrap_ci(items, n_boot=200, seed=0)
        self.assertEqual(ci1, ci2)                                      # seeded → reproducible
        self.assertIsNone(S.auroc([(0.5, True), (0.6, True)]))         # one class empty → None

    def test_confidence_spread_flags_degeneracy(self):
        degen = S.confidence_spread([0.95, 0.96, 0.94, 0.95])
        self.assertTrue(degen["degenerate"])                           # saturated near 1.0
        healthy = S.confidence_spread([0.4, 0.6, 0.8, 1.0])
        self.assertFalse(healthy["degenerate"])
        self.assertEqual(S.confidence_spread([])["degenerate"], None)


class CalibrateGradedTests(unittest.TestCase):
    def test_coverage_excludes_abstention_and_non_substantiating(self):
        records = [
            rec("a", "fully-supported", 0.9, "GRADED", "fully-supported"),
            rec("b", "partially-supported", 0.6, "GRADED", "contradicted"),
            rec("c", NOT_ENOUGH_INFO, 0.3, "ABSTAINED", "partially-supported"),
            rec("d", NON_SUBSTANTIATING, 0.5, "NON_SUBSTANTIATING", "fully-supported"),
        ]
        cal = S.calibrate_graded(records)
        self.assertEqual(cal["status"], "scored")
        self.assertEqual(cal["n_labeled"], 4)
        self.assertEqual(cal["n_graded"], 2)                           # only GRADED enter metrics
        self.assertEqual(cal["n_abstained"], 1)
        self.assertEqual(cal["n_non_substantiating"], 1)
        self.assertAlmostEqual(cal["coverage"], 0.5)
        self.assertAlmostEqual(cal["accuracy_exact"], 0.5)             # a correct, b wrong
        self.assertAlmostEqual(cal["selective_risk"], 0.5)

    def test_pending_when_no_reference_labels(self):
        records = [rec("a", "fully-supported", 0.9, "GRADED", None)]
        self.assertEqual(S.calibrate_graded(records)["status"], "pending")


class SidecarAndSampleTests(unittest.TestCase):
    def test_load_references_only_substantive_grade_key(self):
        """Anti-circularity: only `substantive_grade` is accepted. A bare `grade` key (the shape
        of the scorer's OWN model predictions) must NOT be ingested as a human reference."""
        cases = [{"case_id": "A01", "substantive_grade": "fully-supported"},
                 {"case_id": "A02", "substantive_grade": "not-a-grade"},        # invalid → ignored
                 {"case_id": "A03", "grade": "contradicted"},                   # model-key → ignored
                 {"case_id": "A04"}]
        refs = S.load_graded_references(cases, sidecar_path=None)
        self.assertEqual(refs, {"A01": "fully-supported"})

    def test_graded_flag_fails_closed(self):
        """The graded flag gates a live/paid Opus path, so it must fail CLOSED: unset or any
        common off-spelling stays on the offline stub; only an explicit truthy value enables it."""
        saved = os.environ.pop("CITEVAL_GRADED", None)
        try:
            for off in ("", "0", "false", "FALSE", "No", "off", "none"):
                os.environ["CITEVAL_GRADED"] = off
                self.assertFalse(graded_enabled(), f"{off!r} should be OFF")
            for on in ("1", "true", "yes"):
                os.environ["CITEVAL_GRADED"] = on
                self.assertTrue(graded_enabled(), f"{on!r} should be ON")
            os.environ.pop("CITEVAL_GRADED", None)
            self.assertFalse(graded_enabled())              # unset default OFF
            self.assertTrue(graded_enabled(flag=True))      # explicit --graded ON
        finally:
            if saved is not None:
                os.environ["CITEVAL_GRADED"] = saved
            else:
                os.environ.pop("CITEVAL_GRADED", None)

    def test_sample_manifest_excludes_mislabels_and_leaves_grades_blank(self):
        cases = [{"case_id": cid, "ground_truth_label": "SCOPE_MISMATCH", "confidence_tier": "high",
                  "claim_text": "c", "cited_title": "t", "cited_pmid": "1"}
                 for cid in ("Bs14", "Bp02", "Bp03", "Bs01", "Bs02", "Ce01", "Ch01")]
        manifest = S.sample_calibration_manifest(cases, n=10)
        ids = {m["case_id"] for m in manifest}
        self.assertFalse(ids & set(S.RETRACTION_MISLABELS))            # the 3 mislabels excluded
        self.assertTrue(all(m["substantive_grade"] is None for m in manifest))  # human fills these


class CoverageByDepthTests(unittest.TestCase):
    def test_splits_and_computes_coverage(self):
        records = [
            {"evidence_depth": "fulltext", "status": "GRADED"},
            {"evidence_depth": "fulltext", "status": "GRADED"},
            {"evidence_depth": "fulltext", "status": "ABSTAINED"},
            {"evidence_depth": "abstract", "status": "ABSTAINED"},
            {"evidence_depth": "abstract", "status": "NON_SUBSTANTIATING"},
        ]
        cbd = S.coverage_by_depth(records)
        self.assertEqual(cbd["fulltext"]["n"], 3)
        self.assertEqual(cbd["fulltext"]["graded"], 2)
        self.assertAlmostEqual(cbd["fulltext"]["coverage"], 2 / 3, places=3)
        self.assertEqual(cbd["abstract"]["n"], 2)
        self.assertEqual(cbd["abstract"]["coverage"], 0.0)   # full text lifted coverage over abstract-only

    def test_empty_depth_coverage_is_none(self):
        cbd = S.coverage_by_depth([{"evidence_depth": "fulltext", "status": "GRADED"}])
        self.assertIsNone(cbd["abstract"]["coverage"])


class ReadPredictionsTests(unittest.TestCase):
    def test_tolerates_partial_trailing_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "graded_predictions.jsonl"
            p.write_text('{"case_id": "A", "status": "GRADED"}\n{"case_id": "B", "status":')  # crash mid-write
            done = S.read_predictions(p)
            self.assertEqual(set(done), {"A"})               # partial line skipped, A survives


class ObservabilityTests(unittest.TestCase):
    def _cases(self, n):
        return [{"case_id": f"K{i}", "cited_pmid": str(i), "claim_text": "c",
                 "ground_truth_label": "SUPPORTED"} for i in range(n)]

    def test_limit_scores_only_first_n(self):
        cases = self._cases(6)
        script = {str(i): ("fully-supported", 0.9, "GRADED", "body") for i in range(6)}
        calls: list = []
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(S, "run_slice", _make_fake_slice(script, calls)):
            res = S.score(cases, graded=True, out_dir=d, limit=3)
        self.assertEqual(res["n"], 3)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(res["graded_records"]), 3)

    def test_incremental_jsonl_written_per_case(self):
        cases = self._cases(3)
        script = {"0": ("fully-supported", 0.9, "GRADED", "body"),
                  "1": (NOT_ENOUGH_INFO, 0.3, "ABSTAINED", ""),
                  "2": (NON_SUBSTANTIATING, 0.5, "NON_SUBSTANTIATING", "body")}
        calls: list = []
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(S, "run_slice", _make_fake_slice(script, calls)):
            S.score(cases, graded=True, out_dir=d)
            rows = S.read_predictions(Path(d) / "graded_predictions.jsonl")
        self.assertEqual(set(rows), {"K0", "K1", "K2"})
        self.assertEqual(rows["K0"]["evidence_depth"], "fulltext")
        self.assertEqual(rows["K1"]["evidence_depth"], "abstract")
        self.assertEqual(rows["K0"]["status"], "GRADED")

    def test_resume_skips_completed_cases(self):
        cases = self._cases(4)
        script = {str(i): ("fully-supported", 0.9, "GRADED", "body") for i in range(4)}
        with tempfile.TemporaryDirectory() as d:
            pred = Path(d) / "graded_predictions.jsonl"
            # Pre-seed K0, K1 as already computed (a prior interrupted run).
            pred.write_text(
                json.dumps({"case_id": "K0", "status": "GRADED", "grade": "contradicted",
                            "confidence": 0.7, "ref_grade": None, "evidence_depth": "fulltext",
                            "elapsed_s": 1.0}) + "\n"
                + json.dumps({"case_id": "K1", "status": "ABSTAINED", "grade": NOT_ENOUGH_INFO,
                              "confidence": 0.2, "ref_grade": None, "evidence_depth": "abstract",
                              "elapsed_s": 1.0}) + "\n")
            calls: list = []
            with mock.patch.object(S, "run_slice", _make_fake_slice(script, calls)):
                res = S.score(cases, graded=True, out_dir=d)
            # K0,K1 re-run only for the cheap objective axes (graded=False); K2,K3 run graded.
            by_pmid = dict(calls)
            self.assertFalse(by_pmid["0"])           # K0 objective-only (resumed)
            self.assertFalse(by_pmid["1"])           # K1 objective-only (resumed)
            self.assertTrue(by_pmid["2"])            # K2 graded
            self.assertTrue(by_pmid["3"])            # K3 graded
            # The reused K0 prediction keeps its stored grade (not recomputed).
            recs = {r["case_id"]: r for r in res["graded_records"]}
            self.assertEqual(recs["K0"]["grade"], "contradicted")
            self.assertEqual(len(res["graded_records"]), 4)     # all 4 in the final calibration set

    def test_resume_after_partial_line_preserves_recomputed_case(self):
        """A crash left K0 fully written + K1 partial (newline-less). On resume, K1 is recomputed and
        must land on its OWN parseable line — not glued onto the partial line (which would corrupt
        both and durably lose K1). All three cases end up parseable in the durable jsonl."""
        cases = self._cases(3)
        script = {str(i): ("fully-supported", 0.9, "GRADED", "body") for i in range(3)}
        with tempfile.TemporaryDirectory() as d:
            pred = Path(d) / "graded_predictions.jsonl"
            pred.write_text(
                json.dumps({"case_id": "K0", "status": "GRADED", "grade": "contradicted",
                            "confidence": 0.7, "ref_grade": None, "evidence_depth": "fulltext",
                            "elapsed_s": 1.0}) + "\n"
                + '{"case_id": "K1", "status":')          # crash mid-write: partial, no newline
            with mock.patch.object(S, "run_slice", _make_fake_slice(script, [])):
                S.score(cases, graded=True, out_dir=d)
            durable = S.read_predictions(pred)
            self.assertEqual(set(durable), {"K0", "K1", "K2"})   # none lost; K1 recomputed cleanly
            self.assertEqual(durable["K1"]["status"], "GRADED")  # freshly (re)computed, on its own line

    def test_fresh_recomputes_all(self):
        cases = self._cases(2)
        script = {str(i): ("fully-supported", 0.9, "GRADED", "body") for i in range(2)}
        with tempfile.TemporaryDirectory() as d:
            pred = Path(d) / "graded_predictions.jsonl"
            pred.write_text(json.dumps({"case_id": "K0", "status": "GRADED"}) + "\n")
            calls: list = []
            with mock.patch.object(S, "run_slice", _make_fake_slice(script, calls)):
                S.score(cases, graded=True, out_dir=d, fresh=True)
            self.assertTrue(all(g for _pmid, g in calls))       # every case re-run graded


if __name__ == "__main__":
    unittest.main(verbosity=2)
