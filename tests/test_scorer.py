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

import os

from citeval import scorer as S
from citeval.prompts import NON_SUBSTANTIATING, NOT_ENOUGH_INFO
from citeval.slice_runner import graded_enabled


def rec(cid, grade, conf, status, ref):
    return {"case_id": cid, "grade": grade, "confidence": conf, "status": status, "ref_grade": ref}


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
