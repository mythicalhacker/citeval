"""Tests for the ETA / progress estimator (`citeval_api.progress`).

Stdlib `unittest` (pytest is not installed in the eval env — see server/README.md). Run:

    python -m unittest discover -s server/tests -t server -v

Covers the two headline properties (pct monotone, finishes ~100 %) plus: adjudicate dominance and
round-count scaling, rolling-benchmark refinement from `stage_end`, early-stopping, a non-negative
ETA, and cross-run benchmark learning.
"""
import unittest

from citeval_api.contracts import ProgressData
from citeval_api.progress import (
    ADJUDICATE,
    DEFAULT_ADJUDICATE_PER_ROUND_MS,
    PRE_COMPLETE_CEILING,
    STAGE_ORDER,
    Benchmarks,
    ProgressEstimator,
)

# A realistic, fixture-shaped timeline (ms since run_start), mirroring data/schemas/run_result.json.
INGEST_MS = 910.0
GRETRACT_MS = 1480.0
GSCOPE_MS = 1210.0
PER_ROUND_MS = 12100.0
REPORT_MS = 60.0


def play_prelude(est: ProgressEstimator, snaps: list[ProgressData]) -> float:
    """Run the three cheap stages; append a snapshot after each event. Returns elapsed at the
    moment adjudicate is about to start."""
    t = 0.0
    for stage, dur in (("ingest", INGEST_MS), ("ground_retraction", GRETRACT_MS), ("ground_scope", GSCOPE_MS)):
        est.stage_start(stage, t)
        snaps.append(est.snapshot(t))
        t += dur
        est.stage_end(stage, t)
        snaps.append(est.snapshot(t))
    return t


def play_full_run(est: ProgressEstimator, n_rounds: int, per_round_ms: float = PER_ROUND_MS) -> list[ProgressData]:
    """Simulate an entire run with `n_rounds` adjudication rounds, snapshotting after every event."""
    snaps: list[ProgressData] = []
    snaps.append(est.snapshot(0.0))                    # pre-start
    t = play_prelude(est, snaps)

    est.stage_start(ADJUDICATE, t)
    snaps.append(est.snapshot(t))
    adj_start = t
    for r in range(1, n_rounds + 1):
        t = adj_start + r * per_round_ms
        est.round_completed(t, round_index=r)
        snaps.append(est.snapshot(t))
    est.stage_end(ADJUDICATE, t, rounds_run=n_rounds)
    snaps.append(est.snapshot(t))

    est.stage_start("report", t)
    snaps.append(est.snapshot(t))
    t += REPORT_MS
    est.stage_end("report", t)
    snaps.append(est.snapshot(t))

    est.run_complete(t)
    snaps.append(est.snapshot(t))
    return snaps


def assert_monotone(test: unittest.TestCase, snaps: list[ProgressData]) -> None:
    prev = -1.0
    for i, s in enumerate(snaps):
        test.assertGreaterEqual(s.pct, prev, f"pct regressed at snapshot {i}: {s.pct} < {prev}")
        prev = s.pct


class TestSeededBenchmarks(unittest.TestCase):
    def test_seed_total_is_sane_and_adjudicate_dominates(self):
        b = Benchmarks.seeded()
        total = b.expected_total_ms()
        self.assertGreater(total, 80_000.0)      # a ~88 s run, per the fixture
        adj = b.expected_stage_ms(ADJUDICATE)
        self.assertGreater(adj / total, 0.9)     # adjudicate is >90 % of the estimate

    def test_stage_order_is_the_frozen_five(self):
        self.assertEqual(STAGE_ORDER, ("ingest", "ground_retraction", "ground_scope", "adjudicate", "report"))


class TestFullRun(unittest.TestCase):
    def test_monotone_and_finishes_at_100(self):
        est = ProgressEstimator()
        snaps = play_full_run(est, n_rounds=7)
        assert_monotone(self, snaps)
        self.assertEqual(snaps[0].pct, 0.0)         # nothing done yet
        self.assertEqual(snaps[-1].pct, 100.0)      # complete
        self.assertEqual(snaps[-1].est_remaining_ms, 0.0)

    def test_est_total_equals_actual_total_on_completion(self):
        est = ProgressEstimator()
        snaps = play_full_run(est, n_rounds=7)
        actual_total = INGEST_MS + GRETRACT_MS + GSCOPE_MS + 7 * PER_ROUND_MS + REPORT_MS
        self.assertAlmostEqual(snaps[-1].est_total_ms, actual_total, places=1)

    def test_remaining_never_negative_and_ends_zero(self):
        est = ProgressEstimator()
        snaps = play_full_run(est, n_rounds=7)
        for s in snaps:
            self.assertGreaterEqual(s.est_remaining_ms, 0.0)
        self.assertEqual(snaps[-1].est_remaining_ms, 0.0)

    def test_pct_below_ceiling_until_complete(self):
        est = ProgressEstimator()
        snaps = play_full_run(est, n_rounds=7)
        for s in snaps[:-1]:
            self.assertLessEqual(s.pct, PRE_COMPLETE_CEILING)
        self.assertEqual(snaps[-1].pct, 100.0)

    def test_returns_progress_data_contract(self):
        est = ProgressEstimator()
        est.stage_start("ingest", 0.0)
        snap = est.snapshot(100.0)
        self.assertIsInstance(snap, ProgressData)


class TestAdjudicateScaling(unittest.TestCase):
    def test_more_expected_rounds_means_larger_estimate(self):
        # Same observed state, different expected round budget → bigger ETA for more rounds.
        def mid_adjudicate(expected_rounds):
            est = ProgressEstimator(expected_rounds=expected_rounds)
            snaps: list[ProgressData] = []
            t = play_prelude(est, snaps)
            est.stage_start(ADJUDICATE, t)
            est.round_completed(t + PER_ROUND_MS, round_index=1)
            return est.snapshot(t + PER_ROUND_MS).est_total_ms

        self.assertLess(mid_adjudicate(3), mid_adjudicate(7))

    def test_adjudicate_dominates_the_done_work_curve(self):
        # By the time the cheap stages are done, pct is still small — adjudicate is most of the run.
        est = ProgressEstimator()
        snaps: list[ProgressData] = []
        t = play_prelude(est, snaps)
        pct_after_cheap_stages = est.snapshot(t).pct
        self.assertLess(pct_after_cheap_stages, 10.0)

    def test_estimate_grows_as_rounds_run_slower_than_seed(self):
        # A slow triad (rounds longer than the seed) must lengthen the ETA, not stall it.
        fast = ProgressEstimator()
        slow = ProgressEstimator()
        snaps: list[ProgressData] = []
        t = play_prelude(fast, snaps)
        play_prelude(slow, [])
        fast.stage_start(ADJUDICATE, t)
        slow.stage_start(ADJUDICATE, t)
        fast.round_completed(t + PER_ROUND_MS, round_index=1)
        slow.round_completed(t + 3 * PER_ROUND_MS, round_index=1)   # 3x slower per round
        self.assertGreater(
            slow.snapshot(t + 3 * PER_ROUND_MS).est_total_ms,
            fast.snapshot(t + PER_ROUND_MS).est_total_ms,
        )


class TestEarlyStopping(unittest.TestCase):
    def test_short_run_still_completes_monotone_at_100(self):
        est = ProgressEstimator()  # expects 7 rounds by default
        snaps = play_full_run(est, n_rounds=3)  # but the triad early-stops at 3
        assert_monotone(self, snaps)
        self.assertEqual(snaps[-1].pct, 100.0)
        self.assertEqual(snaps[-1].est_remaining_ms, 0.0)

    def test_long_run_beyond_expected_rounds_stays_monotone(self):
        est = ProgressEstimator()
        snaps = play_full_run(est, n_rounds=7)  # default expects 7; run runs the full budget
        assert_monotone(self, snaps)
        self.assertEqual(snaps[-1].pct, 100.0)


class TestMonotoneFloorUnderBenchmarkJump(unittest.TestCase):
    def test_pct_never_regresses_when_estimate_suddenly_grows(self):
        # Round 1 arrives fast (small est), round 2 arrives very slow (est jumps up). pct must not
        # step backward even though the denominator grew.
        est = ProgressEstimator()
        snaps: list[ProgressData] = []
        t = play_prelude(est, snaps)
        est.stage_start(ADJUDICATE, t)
        snaps.append(est.snapshot(t))
        est.round_completed(t + 5_000, round_index=1)
        snaps.append(est.snapshot(t + 5_000))
        est.round_completed(t + 60_000, round_index=2)   # huge gap → per-round estimate balloons
        snaps.append(est.snapshot(t + 60_000))
        assert_monotone(self, snaps)


class TestRollingBenchmarks(unittest.TestCase):
    def test_observe_adjudicate_updates_per_round_via_ema(self):
        b = Benchmarks.seeded()
        before = b.adjudicate_per_round_ms
        b.observe_stage(ADJUDICATE, 70_000.0, rounds_run=7)   # 10 k/round, below the 12.1 k seed
        after = b.adjudicate_per_round_ms
        self.assertLess(after, before)
        expected = (1 - b.alpha) * DEFAULT_ADJUDICATE_PER_ROUND_MS + b.alpha * (70_000.0 / 7)
        self.assertAlmostEqual(after, expected, places=3)

    def test_observe_adjudicate_without_rounds_is_ignored(self):
        b = Benchmarks.seeded()
        before = b.adjudicate_per_round_ms
        b.observe_stage(ADJUDICATE, 999_999.0)  # no rounds_run — must not corrupt per-round figure
        self.assertEqual(b.adjudicate_per_round_ms, before)

    def test_observe_cheap_stage_updates_via_ema(self):
        b = Benchmarks.seeded()
        b.observe_stage("ingest", 1500.0)
        expected = (1 - b.alpha) * 910.0 + b.alpha * 1500.0
        self.assertAlmostEqual(b.stage_ms["ingest"], expected, places=3)

    def test_shared_benchmarks_learn_across_runs(self):
        shared = Benchmarks.seeded()
        seed_per_round = shared.adjudicate_per_round_ms
        # Three runs whose adjudication is consistently ~9 k/round (faster than the 12.1 k seed).
        for _ in range(3):
            est = ProgressEstimator(shared)
            play_full_run(est, n_rounds=7, per_round_ms=9_000.0)
        self.assertLess(shared.adjudicate_per_round_ms, seed_per_round)
        self.assertGreater(shared.adjudicate_per_round_ms, 9_000.0)  # EMA, not a hard jump

    def test_fresh_estimator_uses_seeded_defaults(self):
        est = ProgressEstimator()
        snap = est.snapshot(0.0)
        self.assertEqual(snap.pct, 0.0)
        self.assertGreater(snap.est_total_ms, 80_000.0)
        self.assertAlmostEqual(snap.est_remaining_ms, snap.est_total_ms, places=1)

    def test_observe_unknown_stage_records_a_benchmark(self):
        b = Benchmarks.seeded()
        b.observe_stage("warmup", 321.0)          # a stage name not in the seed set
        self.assertEqual(b.stage_ms["warmup"], 321.0)
        self.assertEqual(b.expected_stage_ms("warmup"), 321.0)


class TestUncoveredBranches(unittest.TestCase):
    """Exercise the internal-counter / defensive paths that the happy-path run does not."""

    def test_round_completed_without_index_uses_internal_counter(self):
        # Driving rounds without an explicit round_index must still advance the ETA by round.
        est = ProgressEstimator()
        snaps: list[ProgressData] = []
        t = play_prelude(est, snaps)
        est.stage_start(ADJUDICATE, t)
        before = est.snapshot(t).pct
        est.round_completed(t + PER_ROUND_MS)          # no round_index → internal +1
        est.round_completed(t + 2 * PER_ROUND_MS)      # no round_index → internal +1
        after = est.snapshot(t + 2 * PER_ROUND_MS)
        self.assertGreater(after.pct, before)
        self.assertGreaterEqual(after.est_total_ms, est.snapshot(t).est_total_ms)

    def test_stage_end_without_matching_stage_start_is_handled(self):
        # A stray stage_end (no preceding stage_start) must not crash and must record a plausible
        # non-negative duration via the benchmark fallback.
        est = ProgressEstimator()
        est.stage_end("ingest", 5000.0)  # never called stage_start("ingest")
        snap = est.snapshot(5000.0)
        self.assertGreaterEqual(snap.est_total_ms, 0.0)
        self.assertGreaterEqual(snap.est_remaining_ms, 0.0)
        self.assertGreaterEqual(snap.pct, 0.0)

    def test_snapshot_elapsed_does_not_regress_the_internal_clock(self):
        est = ProgressEstimator()
        est.stage_start("ingest", 0.0)
        est.snapshot(2000.0)                 # remember elapsed=2000
        # An out-of-order lower snapshot must not drag the remembered clock backward.
        est.snapshot(500.0)
        self.assertGreaterEqual(est._last_elapsed, 2000.0)


if __name__ == "__main__":
    unittest.main()
