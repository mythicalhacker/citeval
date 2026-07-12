"""Unit tests for C4 confidence recalibration (RB3) — the offline Platt `a_exact -> P(correct)` fit.

Stdlib `unittest` only; PURE OFFLINE — NO network, NO key, NO model calls. Synthetic + hermetic
fixtures (the real predictions live in gitignored `outputs/`, so nothing here reads them). Run:

    python -m unittest discover -s tests
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
import tempfile
import unittest
from pathlib import Path

_SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from citeval import recalibrate as R
from citeval.slice_runner import recalibrate_enabled


# The real full-30 graded run, reduced to its (a_exact, correct) multiset — reconstructed from the
# per-value reliability the brief cites (19@1.0 with 14 correct; 4@0.5714 with 1; 2@0.7143, 1@0.8571,
# 1@0.4286 all wrong). AUROC / raw-ECE depend ONLY on this multiset, so this hermetically reproduces
# the brief's headline numbers without touching gitignored data.
def _real_multiset() -> list[tuple[float, int]]:
    rows: list[tuple[float, int]] = []
    rows += [(1.0, 1)] * 14 + [(1.0, 0)] * 5      # a_exact=1.0: 19 cases, 73.7% correct
    rows += [(0.5714, 1)] * 1 + [(0.5714, 0)] * 3  # a_exact=0.5714: 4 cases, 25% correct
    rows += [(0.7143, 0)] * 2                       # a_exact=0.7143: 2 cases, 0% correct
    rows += [(0.8571, 0)] * 1                       # a_exact=0.8571: 1 case, wrong-and-confident
    rows += [(0.4286, 0)] * 1                       # a_exact=0.4286: 1 case
    return rows


class NumericPrimitiveTests(unittest.TestCase):
    def test_sigmoid_stable_at_extremes(self):
        self.assertAlmostEqual(R.sigmoid(0.0), 0.5)
        self.assertAlmostEqual(R.sigmoid(1000.0), 1.0)      # no overflow
        self.assertAlmostEqual(R.sigmoid(-1000.0), 0.0)     # no overflow
        self.assertTrue(0.0 < R.sigmoid(-50.0) < 0.5 < R.sigmoid(50.0) <= 1.0)

    def test_identity_is_a_singleton_passthrough(self):
        self.assertIs(R.IDENTITY, R._identity)
        for x in (0.0, 0.4286, 1.0):
            self.assertEqual(R.IDENTITY(x), x)

    def test_platt_map_output_stays_in_unit_interval(self):
        # The guaranteed contract is "output is a probability in [0,1]" across the whole a_exact range
        # for ANY fitted params (steep, negative, degenerate) — the shape recalibration must emit.
        for a, b in [(50.0, -25.0), (-50.0, 25.0), (5.57, -4.78), (0.0, 0.0)]:
            m = R.platt_map(a, b)
            for x in (0.0, 0.25, 0.5, 0.75, 1.0):
                self.assertGreaterEqual(m(x), 0.0)
                self.assertLessEqual(m(x), 1.0)


class PlattFitTests(unittest.TestCase):
    def test_recovers_a_known_map_on_synthetic_data(self):
        """Deterministically generate y from a known sigmoid(A*x+B) and recover (A, B) by MLE."""
        a_true, b_true = 3.0, -1.5
        xs: list[float] = []
        ys: list[int] = []
        for i in range(21):                                 # x on a 0..1 grid
            x = i / 20.0
            m = 400
            pos = round(m * R.sigmoid(a_true * x + b_true))
            xs += [x] * m
            ys += [1] * pos + [0] * (m - pos)
        a, b = R.fit_platt(xs, ys)
        self.assertAlmostEqual(a, a_true, delta=0.25)
        self.assertAlmostEqual(b, b_true, delta=0.20)
        # And the fitted curve tracks the true probability across the range.
        fn = R.platt_map(a, b)
        for x in (0.1, 0.5, 0.9):
            self.assertAlmostEqual(fn(x), R.sigmoid(a_true * x + b_true), delta=0.05)

    def test_fit_is_monotone_increasing_when_confidence_tracks_correctness(self):
        rows = _real_multiset()
        a, b = R.fit_platt([x for x, _ in rows], [y for _, y in rows])
        self.assertGreater(a, 0.0)                          # higher a_exact -> higher P(correct)

    def test_empty_dataset_is_degenerate_not_a_crash(self):
        self.assertEqual(R.fit_platt([], []), (0.0, 0.0))

    def test_fit_stays_finite_under_perfect_separation(self):
        """Target smoothing keeps the MLE finite even when the data are perfectly separable."""
        xs = [0.0, 0.0, 1.0, 1.0]
        ys = [0, 0, 1, 1]
        a, b = R.fit_platt(xs, ys)
        self.assertTrue(math.isfinite(a) and math.isfinite(b))
        self.assertGreater(a, 0.0)


class JoinTests(unittest.TestCase):
    def test_build_dataset_filters_and_labels_exactly(self):
        preds = [
            {"case_id": "G1", "status": "GRADED", "grade": "fully-supported", "confidence": 1.0},
            {"case_id": "G2", "status": "GRADED", "grade": "partially-supported", "confidence": 0.5},
            {"case_id": "AB", "status": "ABSTAINED", "grade": "NOT_ENOUGH_INFO", "confidence": 0.0},
            {"case_id": "NS", "status": "NON_SUBSTANTIATING", "grade": "N/A — non-substantiating",
             "confidence": 0.3},
            {"case_id": "ER", "status": "ERROR"},
            {"case_id": "NR", "status": "GRADED", "grade": "fully-supported", "confidence": 1.0},
            {"case_id": "NEI", "status": "GRADED", "grade": "fully-supported", "confidence": 1.0},
        ]
        ref = {"G1": "fully-supported", "G2": "fully-supported", "AB": "fully-supported",
               "NS": "fully-supported", "NEI": "NOT_ENOUGH_INFO"}   # NR absent; NEI ref is non-ordinal
        ds = R.build_dataset(preds, ref)
        # Only the two GRADED preds with an ORDINAL reference survive; correctness is EXACT match.
        self.assertEqual([(cid, y) for cid, _, y in ds], [("G1", 1), ("G2", 0)])
        self.assertEqual([x for _, x, _ in ds], [1.0, 0.5])

    def test_load_reference_is_schema_tolerant(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ref.jsonl"
            p.write_text(
                json.dumps({"case_id": "A", "grade": "fully-supported"}) + "\n" +
                json.dumps({"case_id": "B", "ref_grade": "contradicted"}) + "\n" +
                json.dumps({"case_id": "C", "substantive_grade": "partially-supported"}) + "\n" +
                json.dumps({"case_id": "D"}) + "\n")            # no grade column -> dropped
            ref = R.load_reference(p)
        self.assertEqual(ref, {"A": "fully-supported", "B": "contradicted",
                               "C": "partially-supported"})


class MetricTests(unittest.TestCase):
    def test_ece_hand_checkable(self):
        # bin 1.0: n=2, acc=.5, |1.0-.5|=.5, w=.5 ; bin 0.0: n=2, acc=0, gap=0
        ece, rel = R.ece_and_reliability([1.0, 1.0, 0.0, 0.0], [1.0, 1.0, 0.0, 0.0], [1, 0, 0, 0])
        self.assertAlmostEqual(ece, 0.25)
        self.assertEqual(len(rel), 2)
        top = next(r for r in rel if r["a_exact"] == 1.0)
        self.assertEqual((top["n"], top["acc"], top["gap"]), (2, 0.5, 0.5))

    def test_raw_ece_and_auroc_reproduce_the_briefs_numbers(self):
        rows = _real_multiset()
        self.assertEqual(len(rows), 27)
        xs = [x for x, _ in rows]
        ys = [y for _, y in rows]
        raw_ece, _ = R.ece_and_reliability([round(x, 6) for x in xs], xs, ys)
        self.assertAlmostEqual(raw_ece, 0.3333, places=4)      # brief: RAW ECE ~0.333
        self.assertAlmostEqual(R.auroc(xs, ys), 0.752778, places=5)  # brief: AUROC ~0.69-0.75

    def test_auroc_tie_handling(self):
        # all scores tied -> AUROC 0.5 (no ranking information)
        self.assertAlmostEqual(R.auroc([0.5, 0.5, 0.5, 0.5], [1, 1, 0, 0]), 0.5)
        # perfectly separable -> 1.0
        self.assertAlmostEqual(R.auroc([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0]), 1.0)

    def test_auroc_undefined_when_one_class_absent(self):
        self.assertTrue(math.isnan(R.auroc([0.1, 0.2], [1, 1])))


class MonotoneInvarianceTests(unittest.TestCase):
    def test_monotone_map_leaves_auroc_identical(self):
        rows = _real_multiset()
        xs = [x for x, _ in rows]
        ys = [y for _, y in rows]
        auroc_raw = R.auroc(xs, ys)

        fn = R.platt_map(*R.fit_platt(xs, ys))               # the fitted (strictly increasing) map
        auroc_fitted = R.auroc([fn(x) for x in xs], ys)
        auroc_manual = R.auroc([2.0 * x + 1.0 for x in xs], ys)   # any strictly increasing map

        self.assertEqual(auroc_raw, auroc_fitted)            # EXACT — ranks are preserved
        self.assertEqual(auroc_raw, auroc_manual)
        # (Exact-match GRADE accuracy invariance under recalibration is proven end-to-end through the
        # adjudicator in GradeInvarianceTests — recalibration only rescales confidence, never the grade.)


class LeaveOneOutTests(unittest.TestCase):
    def test_loo_loop_runs_and_returns_a_prediction_per_case(self):
        rows = _real_multiset()
        xs = [x for x, _ in rows]
        ys = [y for _, y in rows]
        loo = R.loo_predictions(xs, ys)
        self.assertEqual(len(loo), len(xs))
        self.assertTrue(all(0.0 <= p <= 1.0 and math.isfinite(p) for p in loo))

    def test_loo_actually_holds_each_point_out(self):
        """Guard against a LOO->in-sample collapse: if `loo_predictions` failed to drop index i it
        would return the in-sample fit exactly, so the honest 'headline' number would be a lie."""
        rows = _real_multiset()
        xs = [x for x, _ in rows]
        ys = [y for _, y in rows]
        insample = [R.platt_map(*R.fit_platt(xs, ys))(x) for x in xs]
        loo = R.loo_predictions(xs, ys)
        # Removing one case measurably shifts the refit — LOO must differ from in-sample somewhere.
        self.assertGreater(max(abs(l - s) for l, s in zip(loo, insample)), 0.01)

    def test_recalibration_lowers_ece_vs_raw(self):
        rows = _real_multiset()
        xs = [x for x, _ in rows]
        ys = [y for _, y in rows]
        keys = [round(x, 6) for x in xs]
        raw_ece, _ = R.ece_and_reliability(keys, xs, ys)
        fn = R.platt_map(*R.fit_platt(xs, ys))
        ins_ece, _ = R.ece_and_reliability(keys, [fn(x) for x in xs], ys)
        loo_ece, _ = R.ece_and_reliability(keys, R.loo_predictions(xs, ys), ys)
        self.assertLess(ins_ece, raw_ece)                   # in-sample improves calibration
        self.assertLess(loo_ece, raw_ece)                   # and it holds out-of-sample (LOO)


class MapPersistenceTests(unittest.TestCase):
    def test_write_has_required_keys_and_round_trips(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sub" / "calibration_map.json"     # parent auto-created
            payload = R.write_calibration_map(p, 5.5, -4.7, 27, version="deadbee")
            self.assertEqual(payload["method"], "platt")
            for k in ("A", "B", "n_fit", "reference", "fit_on", "code_version", "date"):
                self.assertIn(k, payload)
            self.assertEqual(payload["code_version"], "deadbee")
            self.assertEqual(payload["reference"], "graded_reference_v2")
            self.assertEqual(payload["fit_on"], "exact-correct")
            fn = R.load_calibration_map(p)
            self.assertIsNot(fn, R.IDENTITY)
            self.assertAlmostEqual(fn(1.0), R.platt_map(5.5, -4.7)(1.0))

    def test_load_returns_identity_when_file_missing(self):
        fn = R.load_calibration_map("/no/such/calibration_map.json")
        self.assertIs(fn, R.IDENTITY)
        self.assertEqual(fn(0.42), 0.42)

    def test_load_returns_identity_on_unknown_method_or_garbage(self):
        with tempfile.TemporaryDirectory() as d:
            bad_method = Path(d) / "m.json"
            bad_method.write_text(json.dumps({"method": "temperature", "T": 2.0}))
            self.assertIs(R.load_calibration_map(bad_method), R.IDENTITY)
            garbage = Path(d) / "g.json"
            garbage.write_text("{not json")
            self.assertIs(R.load_calibration_map(garbage), R.IDENTITY)

    def test_load_fails_closed_on_degenerate_or_non_finite_map(self):
        """A decreasing (A<=0) or non-finite fit would reverse ranking / poison the note — the loader
        must REFUSE it (identity), never attach it. NaN/Infinity survive json.loads, so guard them."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.json"
            for bad in ({"method": "platt", "A": -6.5, "B": 3.0},        # strictly decreasing
                        {"method": "platt", "A": 0.0, "B": 0.0},          # flat (no discrimination)
                        {"method": "platt", "A": float("nan"), "B": 0.0},
                        {"method": "platt", "A": float("inf"), "B": 0.0},
                        {"method": "platt", "A": 5.0, "B": float("nan")}):
                p.write_text(json.dumps(bad))
                self.assertIs(R.load_calibration_map(p), R.IDENTITY, bad)


class ResolveRecalibrationTests(unittest.TestCase):
    """The production opt-in seam — fails closed and never auto-enables on a missing/unfit map."""

    def test_disabled_returns_none_and_no_note(self):
        fn, note = R.resolve_recalibration(False)
        self.assertIsNone(fn)
        self.assertEqual(note, "")

    def test_enabled_but_missing_map_declines_with_warning(self):
        fn, note = R.resolve_recalibration(True, "/no/such/map.json")
        self.assertIsNone(fn)                                # NEVER auto-enabled on a missing map
        self.assertIn("WITHOUT recalibration", note)

    def test_enabled_with_real_map_attaches_it(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "map.json"
            R.write_calibration_map(p, 5.5, -4.7, 27, version="v")
            fn, note = R.resolve_recalibration(True, p)
        self.assertTrue(callable(fn))
        self.assertIn("ON", note)
        self.assertAlmostEqual(fn(1.0), R.platt_map(5.5, -4.7)(1.0))

    def test_recalibrate_enabled_flag_and_env_fail_closed(self):
        import os
        from unittest import mock
        # Isolate from an ambient CITEVAL_RECALIBRATE export (else the first assertFalse flakes).
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CITEVAL_RECALIBRATE", None)
            self.assertFalse(recalibrate_enabled(False))
            self.assertTrue(recalibrate_enabled(True))
            os.environ["CITEVAL_RECALIBRATE"] = "1"
            self.assertTrue(recalibrate_enabled(False))
            os.environ["CITEVAL_RECALIBRATE"] = "off"
            self.assertFalse(recalibrate_enabled(False))    # off-spelling stays disabled


class ReportTests(unittest.TestCase):
    def test_report_is_labeled_and_proves_auroc_unchanged(self):
        rows = _real_multiset()
        dataset = [(f"c{i}", x, y) for i, (x, y) in enumerate(rows)]
        text, summary = R.fit_report(dataset, reference_name="graded_reference_v2", version="deadbee")
        # The three ECEs are all present and clearly labeled.
        self.assertIn("RAW calibration", text)
        self.assertIn("in-sample", text)
        self.assertIn("leave-one-out", text)
        self.assertIn("deadbee", text)                       # code_version stamped in the report
        self.assertIn("IDENTICAL", text)                     # AUROC-unchanged proof printed
        self.assertTrue(summary["auroc_unchanged"])
        self.assertAlmostEqual(summary["auroc_raw"], summary["auroc_recal"])
        self.assertAlmostEqual(summary["raw_ece"], 0.3333, places=4)
        self.assertLess(summary["loo_ece"], summary["raw_ece"])
        self.assertEqual(summary["n_fit"], 27)


class GradeInvarianceTests(unittest.TestCase):
    """End-to-end proof of the 'monotonic ⇒ exact-accuracy unchanged' half of the invariant: pushing a
    recalibration map through the real adjudicator changes ONLY evidence.calibration.note — the
    emitted grade (hence exact-match accuracy) is byte-identical with and without the map."""

    def _adjudicate(self, recal):
        from citeval import adjudicator as A
        from citeval.contracts import CitedIdentifier, GroundedRecord, RetractionInfo, ScopeFrame

        class _Client:
            def complete(self, *, model, system, user, max_tokens, temperature=1.0):
                if system.startswith("You are the SUPPORTER"):
                    return json.dumps({"points": [{"quote": "a", "rationale": "s"}]})
                if system.startswith("You are the REFUTER"):
                    return json.dumps({"points": []})
                return json.dumps({"grade": "partially-supported", "confidence": 0.8,
                                   "grade_rationale_last": "g"})

        g = GroundedRecord(identifier=CitedIdentifier("pmid", "1"), title="t", abstract="a",
                           mesh_all=[], organism_tags=[], population_tags=[], sex_tags=[],
                           publication_types=[], retraction=RetractionInfo(status="NONE_FOUND"),
                           has_humans=True, full_text="")
        cfg = A.AdjudicationConfig(self_consistency_rounds=2, min_valid_rounds=1,
                                   adaptive_early_stopping=False, recalibration=recal)
        v = A.adjudicate(g, ScopeFrame(organism="Humans", provenance="model-inferred"),
                         claim_text="c", client=_Client(), config=cfg)
        sub = next(f for f in v.axis_findings if f.axis == "substantive_support")
        return sub.verdict, (sub.evidence or {}).get("calibration", {}).get("note", "")

    def test_recalibration_changes_only_the_note_not_the_grade(self):
        grade_off, note_off = self._adjudicate(None)
        grade_on, note_on = self._adjudicate(lambda x: x * 0.5)   # a valid strictly-increasing map
        self.assertEqual(grade_off, grade_on)                      # grade identical ⇒ exact acc identical
        self.assertEqual(note_off, "")                             # no map ⇒ empty calibration note
        self.assertIn("recalibrated confidence", note_on)          # map ⇒ calibrated confidence in note


if __name__ == "__main__":
    unittest.main(verbosity=2)
