"""ETA / progress estimator for a single citeval run (W1-EVENTS).

W2-RUNNER drives a run through five stages, in the FROZEN canonical order

    ingest → ground_retraction → ground_scope → adjudicate → report

and wants to emit `progress` SSE frames (``pct`` / ``est_total_ms`` / ``est_remaining_ms``; see
``citeval_api.contracts.ProgressData``) as it goes. This module is the pure, deterministic engine
behind those frames: feed it the same lifecycle signals the runner already has —
``stage_start`` / ``round_completed`` (from ``config.on_round``) / ``stage_end`` /
``run_complete`` — and read a :class:`ProgressData` snapshot at any moment.

Two things make a citeval ETA non-trivial, and this module models both:

1. **``adjudicate`` dominates** — the adversarial self-consistency triad is ~96 % of wall-clock
   (~85 s of a ~88 s run). A flat per-stage benchmark would be useless: the estimate lives and
   dies on adjudicate.
2. **``adjudicate`` scales with round count** — the triad runs up to ``rounds_configured`` (7)
   self-consistency rounds but *early-stops*, so its duration is ``per_round_ms × n_rounds``, not
   a constant. We benchmark **per round**, not per stage, and refine the per-round figure from the
   rounds we actually observe.

Everything is **rolling**: the :class:`Benchmarks` seed sensible defaults (measured from the
canonical fixture run) and update from every ``stage_end`` via an EMA, so a long-lived process's
estimates sharpen run-over-run. Share one :class:`Benchmarks` across many
:class:`ProgressEstimator` instances to accumulate that learning.

**No wall clock of its own.** Every method takes the caller's ``elapsed_ms`` (the same value that
rides in the SSE envelope), so the estimator is fully deterministic and testable — identical
inputs always yield identical output.

Pure module: imports only ``contracts`` (read-only) from this package; touches nothing in
``src/citeval``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .contracts import ProgressData

# The five pipeline stages in canonical order (mirror of contracts.Stage / STAGE_ORDER in TS).
# Progress is computed strictly against this order.
STAGE_ORDER: tuple[str, ...] = (
    "ingest", "ground_retraction", "ground_scope", "adjudicate", "report",
)
ADJUDICATE = "adjudicate"

# Seed durations, in ms, measured from the canonical fixture run (data/schemas/run_result.json:
# per_stage_ms). adjudicate is stored PER ROUND (84800 ms / 7 rounds ≈ 12.1 k) because it scales
# with the round count; the others are whole-stage figures.
DEFAULT_STAGE_MS: dict[str, float] = {
    "ingest": 910.0,
    "ground_retraction": 1480.0,
    "ground_scope": 1210.0,
    "report": 60.0,
}
DEFAULT_ADJUDICATE_PER_ROUND_MS: float = 12100.0
# The triad's configured self-consistency budget (adjudicator default `rounds_configured`). Used
# as the expected round count until the run reveals its own (early-stopping shortens it).
DEFAULT_EXPECTED_ROUNDS: float = 7.0

# EMA weight for rolling benchmark updates: new observation gets this share, history keeps the
# rest. 0.3 = "trust history, nudge toward the latest run" — smooth, not jumpy.
DEFAULT_ALPHA: float = 0.3

# Never report a full 100 % from a mid-run snapshot; 100 is reserved for `run_complete`. Mirrors
# the mock server, which clamps interim progress below 100 so the bar only fills on completion.
PRE_COMPLETE_CEILING: float = 99.0


@dataclass
class Benchmarks:
    """Rolling per-stage duration benchmarks, shared (optionally) across runs.

    ``stage_ms`` holds whole-stage durations for the non-adjudicate stages;
    ``adjudicate_per_round_ms`` is the per-round figure for the dominant adjudicate stage;
    ``expected_rounds`` is how many rounds we expect the triad to run. All three are refined from
    observed ``stage_end`` durations via an EMA, so estimates improve as real runs complete.
    """

    stage_ms: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_STAGE_MS))
    adjudicate_per_round_ms: float = DEFAULT_ADJUDICATE_PER_ROUND_MS
    expected_rounds: float = DEFAULT_EXPECTED_ROUNDS
    alpha: float = DEFAULT_ALPHA

    @classmethod
    def seeded(cls) -> "Benchmarks":
        """A fresh benchmark set seeded from the fixture-measured defaults."""
        return cls()

    def expected_stage_ms(self, stage: str, *, rounds: Optional[float] = None) -> float:
        """Best current estimate of ``stage``'s whole duration in ms. For ``adjudicate`` this is
        ``per_round × rounds`` (``rounds`` defaults to :attr:`expected_rounds`)."""
        if stage == ADJUDICATE:
            n = rounds if rounds and rounds > 0 else self.expected_rounds
            return self.adjudicate_per_round_ms * n
        return self.stage_ms.get(stage, 0.0)

    def expected_total_ms(self, *, rounds: Optional[float] = None) -> float:
        """Seed estimate of a whole run's duration (sum over the canonical stage order)."""
        return sum(self.expected_stage_ms(s, rounds=rounds) for s in STAGE_ORDER)

    def observe_stage(self, stage: str, duration_ms: float, *, rounds_run: Optional[int] = None) -> None:
        """Fold one measured stage duration into the rolling benchmark.

        For ``adjudicate`` a positive ``rounds_run`` lets us update the *per-round* figure (and the
        expected round count); without it the observation is ignored rather than corrupting the
        per-round benchmark with a whole-stage number.
        """
        duration_ms = max(0.0, float(duration_ms))
        if stage == ADJUDICATE:
            if rounds_run and rounds_run > 0:
                per = duration_ms / rounds_run
                self.adjudicate_per_round_ms = self._ema(self.adjudicate_per_round_ms, per)
                self.expected_rounds = self._ema(self.expected_rounds, float(rounds_run))
        elif stage in self.stage_ms:
            self.stage_ms[stage] = self._ema(self.stage_ms[stage], duration_ms)
        else:
            # An unknown stage still gets a benchmark so a future estimate can use it.
            self.stage_ms[stage] = duration_ms

    def _ema(self, old: float, new: float) -> float:
        return (1.0 - self.alpha) * old + self.alpha * new


class ProgressEstimator:
    """Per-run progress/ETA tracker. Feed it lifecycle events, read :meth:`snapshot`.

    Construct one per run. Pass a shared :class:`Benchmarks` to accumulate rolling learning across
    runs; omit it for a fresh seeded set. ``expected_rounds`` overrides the expected triad round
    count for this run only (e.g. when the runner knows the configured budget up front).

    The tracker is deterministic: it never reads a clock. Callers pass ``elapsed_ms`` (ms since
    ``run_start`` — the SSE envelope value) on every method; the latest value is remembered so
    :meth:`snapshot` can be called with no argument.
    """

    def __init__(self, benchmarks: Optional[Benchmarks] = None, *, expected_rounds: Optional[float] = None):
        self.bench = benchmarks if benchmarks is not None else Benchmarks.seeded()
        self._expected_rounds: float = expected_rounds or self.bench.expected_rounds
        # Completed stages → their measured durations (ms).
        self._actual: dict[str, float] = {}
        self._active: Optional[str] = None
        self._active_start_ms: float = 0.0
        self._rounds_done: int = 0
        self._complete: bool = False
        self._total_ms: float = 0.0            # exact total, known only at run_complete
        self._last_pct: float = 0.0            # monotonic floor for pct
        self._last_elapsed: float = 0.0

    # ---- lifecycle signals -----------------------------------------------------------------
    def stage_start(self, stage: str, elapsed_ms: float) -> None:
        """A stage began at ``elapsed_ms``. Resets the round counter when adjudicate starts."""
        self._touch(elapsed_ms)
        self._active = stage
        self._active_start_ms = float(elapsed_ms)
        if stage == ADJUDICATE:
            self._rounds_done = 0

    def round_completed(
        self,
        elapsed_ms: float,
        *,
        round_index: Optional[int] = None,
        expected_rounds: Optional[float] = None,
    ) -> None:
        """One adversarial self-consistency round finished (from ``config.on_round``).

        ``round_index`` is 1-based when known (authoritative); otherwise the internal counter
        increments. ``expected_rounds`` may raise the run's expected total (e.g. the triad decided
        to keep going) — it never lowers it, so the ETA doesn't optimistically shrink mid-stage.
        """
        self._touch(elapsed_ms)
        if round_index is not None:
            self._rounds_done = max(self._rounds_done, int(round_index))
        else:
            self._rounds_done += 1
        if expected_rounds:
            self._expected_rounds = max(self._expected_rounds, float(expected_rounds))
        # We never expect fewer rounds than we've already seen.
        self._expected_rounds = max(self._expected_rounds, float(self._rounds_done))

    def stage_end(self, stage: str, elapsed_ms: float, *, rounds_run: Optional[int] = None) -> None:
        """A stage finished at ``elapsed_ms``. Records its measured duration and folds it into the
        rolling benchmark. For adjudicate, ``rounds_run`` defaults to the observed round count."""
        self._touch(elapsed_ms)
        start = self._active_start_ms if self._active == stage else self._stage_start_fallback(stage, elapsed_ms)
        duration = max(0.0, float(elapsed_ms) - start)
        self._actual[stage] = duration
        if stage == ADJUDICATE:
            rounds_run = rounds_run if rounds_run is not None else self._rounds_done
            if rounds_run and rounds_run > 0:
                self._expected_rounds = float(rounds_run)
            self.bench.observe_stage(stage, duration, rounds_run=rounds_run or None)
        else:
            self.bench.observe_stage(stage, duration)
        if self._active == stage:
            self._active = None

    def run_complete(self, elapsed_ms: float) -> None:
        """The run finished at ``elapsed_ms``. Pins the exact total and forces pct to 100."""
        self._touch(elapsed_ms)
        self._complete = True
        self._total_ms = float(elapsed_ms)
        self._active = None

    # ---- readout ---------------------------------------------------------------------------
    def snapshot(self, elapsed_ms: Optional[float] = None) -> ProgressData:
        """Current :class:`ProgressData`. ``elapsed_ms`` defaults to the last value seen."""
        if elapsed_ms is None:
            elapsed = self._last_elapsed
        else:
            # Guard the remembered elapsed the same way the lifecycle methods do via _touch: an
            # out-of-order snapshot must not drag the monotonic clock backward.
            elapsed = max(self._last_elapsed, float(elapsed_ms))
            self._last_elapsed = elapsed

        est_total = self._est_total_ms(elapsed)
        if self._complete:
            pct = 100.0
            remaining = 0.0
            est_total = self._total_ms or est_total
        else:
            done = self._done_work_ms(elapsed)
            raw = 100.0 * done / est_total if est_total > 0 else 0.0
            pct = min(raw, PRE_COMPLETE_CEILING)
            pct = max(pct, self._last_pct)        # monotonic: never step backward
            remaining = max(est_total - elapsed, 0.0)

        self._last_pct = pct
        return ProgressData(
            pct=round(pct, 1),
            est_total_ms=round(est_total, 1),
            est_remaining_ms=round(remaining, 1),
        )

    @property
    def pct(self) -> float:
        return self._last_pct

    # ---- internals -------------------------------------------------------------------------
    def _touch(self, elapsed_ms: float) -> None:
        # elapsed_ms is monotonic per the envelope; guard against a stray regression anyway.
        self._last_elapsed = max(self._last_elapsed, float(elapsed_ms))

    def _stage_start_fallback(self, stage: str, elapsed_ms: float) -> float:
        # A stage_end without a matching stage_start (defensive): assume the benchmarked duration.
        return max(0.0, float(elapsed_ms) - self.bench.expected_stage_ms(stage, rounds=self._expected_rounds))

    def _observed_per_round_ms(self, elapsed: float) -> Optional[float]:
        """Per-round rate inferred from the rounds seen so far in the active adjudicate stage."""
        if self._active == ADJUDICATE and self._rounds_done > 0:
            return max(0.0, elapsed - self._active_start_ms) / self._rounds_done
        return None

    def _expected_for(self, stage: str, elapsed: float) -> float:
        """Best-known whole duration of ``stage``: its measured actual if complete, else a
        benchmark estimate (adjudicate refined live from the rounds observed this run)."""
        if stage in self._actual:
            return self._actual[stage]
        if stage == ADJUDICATE:
            per = self._observed_per_round_ms(elapsed) or self.bench.adjudicate_per_round_ms
            n = max(self._expected_rounds, float(self._rounds_done))
            return per * n
        return self.bench.expected_stage_ms(stage)

    def _est_total_ms(self, elapsed: float) -> float:
        total = sum(self._expected_for(s, elapsed) for s in STAGE_ORDER)
        # The run can't plausibly be shorter than time already spent.
        return max(total, elapsed)

    def _done_work_ms(self, elapsed: float) -> float:
        done = 0.0
        for stage in STAGE_ORDER:
            if stage in self._actual:
                done += self._actual[stage]
            elif stage == self._active:
                exp = self._expected_for(stage, elapsed)
                in_stage = max(0.0, elapsed - self._active_start_ms)
                # Fill the active stage's share by elapsed time within it, clamped so an
                # over-running stage can't claim more than its estimated share before stage_end.
                done += min(in_stage, exp)
            # future stages contribute nothing yet
        return done


__all__ = [
    "STAGE_ORDER",
    "ADJUDICATE",
    "DEFAULT_STAGE_MS",
    "DEFAULT_ADJUDICATE_PER_ROUND_MS",
    "DEFAULT_EXPECTED_ROUNDS",
    "DEFAULT_ALPHA",
    "PRE_COMPLETE_CEILING",
    "Benchmarks",
    "ProgressEstimator",
]
