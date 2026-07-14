"""Tests for the run pipeline + SSE streamer (`citeval_api.runner`, W2-RUNNER).

Stdlib `unittest` only (pytest is NOT installed in the eval env — see server/README.md). No live
API key and no network are touched:

- The MODEL is a `FakeAnthropic` in-process client (scripted supporter/refuter/critic JSON per
  triad turn, role-selected by fingerprinting the system prompt) — same seam W1-TELEMETRY tests use.
- GROUNDING runs the REAL `citeval.grounding.ground()` offline: the committed NCBI cache fixtures
  are seeded (`seed_ncbi_cache`, shared with the root tests) and full-text fetch is stubbed to the
  honest-empty value so no PMC round-trip is attempted.

Run:
    python -m unittest discover -s server/tests -t server -v
    # or standalone:  python server/tests/test_runner.py

Acceptance (WO W2-RUNNER DoD):
- the FULL ordered SSE sequence — run_start → (per stage: stage_start/stage_end/progress) → per
  adjudicate round (model_call start/end ×{supporter,refuter,critic} → debate_round → cost_update →
  progress) → run_complete — with gap-free `seq`;
- a well-formed `RunResult`: verbatim render_json verdict, per-stage timing over all five stages,
  a TelemetrySummary whose call count matches the model_call frames, and a non-empty report_html;
- the FAILURE path: any pipeline exception emits a terminal `error` frame tagged with the failing
  stage, the stream is always sealed (subscribers terminate — asserted via `wait_for`, so a
  sealing regression fails as a timeout not a hang), and `run_pipeline` re-raises.
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import unittest
from types import SimpleNamespace

# Make `citeval` (src/), `citeval_api` (server/), and the root `tests/` helpers importable without
# installation. MUST precede the `runner` import (it imports `citeval` at module load).
# server/tests/test_runner.py -> parent(server/tests) -> server -> repo root.
_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
for _p in (str(_ROOT / "src"), str(_ROOT / "server"), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _ncbi_cache_fixture import seed_ncbi_cache  # noqa: E402  (root tests/ helper)
from citeval import grounding  # noqa: E402
from citeval.contracts import CitedIdentifier  # noqa: E402
from citeval_api import runner  # noqa: E402
from citeval_api.contracts import RunRequest, RunResult  # noqa: E402
from citeval_api.events import EventBus, Frame  # noqa: E402
from citeval_api.telemetry import fingerprint_role  # noqa: E402


# A vendored PMID (committed under tests/fixtures/ncbi_cache/efetch_pubmed) so grounding is offline.
PMID = "28882997"  # "Dopamine oxidation mediates mitochondrial and lysosomal dysfunction in PD"
CLAIM = ("In human dopaminergic neurons, oxidized dopamine accumulation drives lysosomal "
         "dysfunction.")
GRADE = "supported-with-overreach"  # ordinal → unanimous rounds trigger adaptive early-stop


# ============================================================================================
# A faithful in-process Anthropic fake: `.messages.create(**kwargs) -> Message`.
# ============================================================================================
def _usage(inp=1200, out=300, cache_write=0, cache_read=800):
    return SimpleNamespace(input_tokens=inp, output_tokens=out,
                           cache_creation_input_tokens=cache_write,
                           cache_read_input_tokens=cache_read)


def _message(text):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)],
                           usage=_usage(), stop_reason="end_turn")


class _FakeMessages:
    def __init__(self, outer):
        self._outer = outer

    def create(self, **kwargs):
        self._outer.calls.append(kwargs)
        return self._outer.respond(kwargs)


class FakeAnthropic:
    """Returns role-appropriate JSON per triad turn. The supporter/refuter quote a verbatim run
    from the grounded abstract (so the verbatim guard keeps the point → `has_grounded_evidence`),
    and the critic returns a consistent ordinal grade (so the run adjudicates to a real GRADED
    verdict and adaptive early-stopping fires)."""

    def __init__(self, quote: str):
        self.calls: list[dict] = []
        self._quote = quote
        self.messages = _FakeMessages(self)

    def respond(self, kwargs):
        role = fingerprint_role(kwargs.get("system"))
        if role == "supporter":
            body = {"points": [{"quote": self._quote,
                                "rationale": "the source states this substantive finding",
                                "point": "directly supports the claim"}]}
        elif role == "refuter":
            body = {"points": [{"quote": self._quote,
                                "objection": "the certainty asserted outruns a single study",
                                "routes_to": "grade", "failure_mode": "overreach"}]}
        elif role == "critic":
            body = {"reasoning": "weighs the decisive verbatim spans, substance only",
                    "decisive_spans": [self._quote],
                    "boundary_test_fired": "on-point",
                    "grade": GRADE, "confidence": 0.9,
                    "grade_rationale_last": "supported but with mild over-reach"}
        else:  # pragma: no cover — every adjudicate call is a role turn
            body = {}
        return _message(json.dumps(body))


class _RaisingMessages:
    def create(self, **kwargs):
        raise RuntimeError("simulated model outage")


class RaisingAnthropic:
    """A client whose `messages.create` always raises — used to drive an adjudicate-stage failure
    and prove the runner still emits a terminal `error` frame and seals the stream."""

    def __init__(self):
        self.messages = _RaisingMessages()


# ============================================================================================
# Helpers over a collected frame list.
# ============================================================================================
async def _collect(sub) -> list[Frame]:
    """Drain a subscription to exhaustion — terminates ONLY if the stream is sealed."""
    return [frame async for frame in sub]
async def _drive(bus: EventBus, run_id: str, request: RunRequest, client) -> tuple[list[Frame], RunResult]:
    """Open a subscriber, run the pipeline, and collect every frame + the returned RunResult."""
    sub = bus.open(run_id)                       # eager registration BEFORE the run starts
    task = asyncio.create_task(
        runner.run_pipeline(request, run_id=run_id, bus=bus, client=client))
    frames = [frame async for frame in sub]      # drains until the stream is sealed
    result = await task
    return frames, result


def _names(frames: list[Frame]) -> list[str]:
    return [f.event for f in frames]


def _between(frames: list[Frame], start_event: str, start_stage: str,
             end_event: str, end_stage: str) -> list[Frame]:
    """The frames strictly between stage_start(start_stage) and stage_end(end_stage)."""
    i = next(k for k, f in enumerate(frames)
             if f.event == start_event and f.data.get("stage") == start_stage)
    j = next(k for k, f in enumerate(frames)
             if k > i and f.event == end_event and f.data.get("stage") == end_stage)
    return frames[i + 1:j]


class RunnerPipelineTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Seed the on-disk NCBI cache from committed fixtures so grounding is hermetic + offline,
        # and stub full-text fetch to the honest-empty value (no PMC round-trip).
        seed_ncbi_cache()
        cls._orig_fetch_full_text = grounding.fetch_full_text
        grounding.fetch_full_text = lambda pmid, abstract, errors=None: ("", "")
        # Ground once to derive a guaranteed-verbatim quote (a contiguous run of the abstract).
        g = grounding.ground(CitedIdentifier("pmid", PMID), with_full_text=True)
        assert g.abstract, "vendored fixture must carry an abstract to quote from"
        cls.quote = " ".join(g.abstract.split()[2:12])

    @classmethod
    def tearDownClass(cls):
        grounding.fetch_full_text = cls._orig_fetch_full_text

    async def asyncSetUp(self):
        self.bus = EventBus()
        self.run_id = "run_test_1"
        self.request = RunRequest(claim=CLAIM, paper_ref=PMID, mode="pmid")
        self.frames, self.result = await _drive(
            self.bus, self.run_id, self.request, FakeAnthropic(self.quote))

    # -- envelope / framing -------------------------------------------------------------------
    def test_seq_is_gapfree_and_run_id_stamped(self):
        seqs = [f.data["seq"] for f in self.frames]
        self.assertEqual(seqs, list(range(len(self.frames))))         # 0,1,2,… no gaps
        self.assertTrue(all(f.data["run_id"] == self.run_id for f in self.frames))
        self.assertTrue(all("ts" in f.data and "elapsed_ms" in f.data for f in self.frames))
        # elapsed_ms is monotonic non-decreasing (envelope invariant).
        elapsed = [f.data["elapsed_ms"] for f in self.frames]
        self.assertEqual(elapsed, sorted(elapsed))

    def test_first_and_last_frames(self):
        first = self.frames[0]
        self.assertEqual(first.event, "run_start")
        self.assertEqual(first.data["mode"], "pmid")
        self.assertEqual(first.data["paper_ref"], PMID)
        last = self.frames[-1]
        self.assertEqual(last.event, "run_complete")
        self.assertNotIn("error", _names(self.frames))

    # -- five stages in canonical order -------------------------------------------------------
    def test_all_five_stages_bracketed_in_order(self):
        starts = [f.data["stage"] for f in self.frames if f.event == "stage_start"]
        ends = [f.data["stage"] for f in self.frames if f.event == "stage_end"]
        self.assertEqual(starts, list(runner.STAGES))
        self.assertEqual(ends, list(runner.STAGES))
        # Each stage_end is followed by a progress frame.
        for k, f in enumerate(self.frames):
            if f.event == "stage_end":
                self.assertEqual(self.frames[k + 1].event, "progress")

    def test_progress_is_monotonic_and_bounded(self):
        pcts = [f.data["pct"] for f in self.frames if f.event == "progress"]
        self.assertTrue(pcts, "expected progress frames")
        self.assertEqual(pcts, sorted(pcts))                          # never steps backward
        self.assertTrue(all(0.0 <= p <= 99.0 for p in pcts))         # 100 reserved for completion
        for f in self.frames:
            if f.event == "progress":
                self.assertGreater(f.data["est_total_ms"], 0.0)

    # -- the adjudicate round structure -------------------------------------------------------
    def test_adjudicate_round_sequence(self):
        inner = _between(self.frames, "stage_start", "adjudicate", "stage_end", "adjudicate")
        debates = [f for f in inner if f.event == "debate_round"]
        n_rounds = len(debates)
        self.assertGreaterEqual(n_rounds, 4)                 # ≥ MIN_VALID_ROUNDS before early-stop
        self.assertLessEqual(n_rounds, 7)                    # ≤ SELF_CONSISTENCY_ROUNDS

        # Walk the inner frames and assert each round's exact ordering.
        expected_roles = ["supporter", "supporter", "refuter", "refuter", "critic", "critic"]
        expected_phase = ["start", "end", "start", "end", "start", "end"]
        pos = 0
        for r in range(1, n_rounds + 1):
            block = inner[pos:pos + 9]                        # 6 model_call + debate + cost + progress
            self.assertEqual([b.event for b in block],
                             ["model_call"] * 6 + ["debate_round", "cost_update", "progress"],
                             f"round {r} frame shape")
            for k in range(6):
                self.assertEqual(block[k].data["role"], expected_roles[k])
                self.assertEqual(block[k].data["phase"], expected_phase[k])
                self.assertEqual(block[k].data["round"], r)
            # start frames carry no usage; end frames carry usage + cost.
            for k in (0, 2, 4):
                self.assertIsNone(block[k].data.get("usage"))
                self.assertIsNone(block[k].data.get("cost_usd"))
            for k in (1, 3, 5):
                self.assertIsNotNone(block[k].data["usage"])
                self.assertGreater(block[k].data["cost_usd"], 0.0)
            self.assertEqual(block[6].data["round"], r)
            self.assertEqual(block[6].data["critic_grade"], GRADE)
            self.assertTrue(0.0 <= block[6].data["agreement"] <= 1.0)
            pos += 9
        self.assertEqual(pos, len(inner), "no unexpected frames inside adjudicate")

    def test_cost_update_is_cumulative_and_matches_summary(self):
        cost_updates = [f for f in self.frames if f.event == "cost_update"]
        cumulatives = [f.data["cumulative_usd"] for f in cost_updates]
        self.assertEqual(cumulatives, sorted(cumulatives))            # non-decreasing
        # deltas sum to the final cumulative, which equals the RunResult cost total.
        self.assertAlmostEqual(sum(f.data["delta_usd"] for f in cost_updates),
                               cumulatives[-1], places=6)
        self.assertAlmostEqual(cumulatives[-1], self.result.cost.total_usd, places=6)

    # -- the RunResult ------------------------------------------------------------------------
    def test_run_complete_carries_wellformed_result(self):
        final = self.frames[-1]
        self.assertEqual(final.event, "run_complete")
        self.assertEqual(final.data["result"]["run_id"], self.run_id)

        res = self.result
        self.assertIsInstance(res, RunResult)
        self.assertEqual(res.run_id, self.run_id)

        # verdict is the verbatim render_json shape.
        self.assertEqual(set(res.verdict), {"claim_unit", "grounded", "claim_scope", "verdict"})
        axes = {a["axis"]: a for a in res.verdict["verdict"]["axis_findings"]}
        self.assertEqual(set(axes),
                         {"retraction", "species_scope", "population_scope", "substantive_support"})
        self.assertTrue(axes["substantive_support"]["verdict"])       # a real grade was placed
        self.assertFalse(res.verdict["verdict"]["stub"])              # graded path, not the stub

        # timing over all five stages + a plausible total.
        self.assertEqual(set(res.timing.per_stage_ms), set(runner.STAGES))
        self.assertGreater(res.timing.total_ms, 0.0)
        self.assertGreater(res.timing.est_total_ms, 0.0)

        # cost: one telemetry record per model call (3 per round), bucketed by role.
        n_debates = sum(1 for f in self.frames if f.event == "debate_round")
        self.assertEqual(res.cost.n_model_calls, 3 * n_debates)
        self.assertEqual(sum(1 for f in self.frames if f.event == "model_call"), 6 * n_debates)
        self.assertGreater(res.cost.total_usd, 0.0)
        self.assertLessEqual({"supporter", "refuter", "critic"}, set(res.cost.per_role))

        # report_html is a non-empty standalone document.
        self.assertIn("<html", res.report_html.lower())
        self.assertGreater(len(res.report_html), 200)

    # -- replay guarantee (a late subscriber still sees the whole run) ------------------------
    async def test_late_subscriber_replays_full_stream(self):
        late = self.bus.open(self.run_id)                    # stream already sealed
        replay = [f async for f in late]
        self.assertEqual([f.event for f in replay], _names(self.frames))
        self.assertEqual([f.data["seq"] for f in replay], list(range(len(self.frames))))

    # -- failure path: terminal error frame + guaranteed stream seal + re-raise ---------------
    async def test_error_frame_on_ingest_failure_seals_stream(self):
        # An unsupported channel raises inside the ingest stage (offline; no model needed).
        bus = EventBus()
        run_id = "run_ingest_err"
        sub = bus.open(run_id)
        bad = RunRequest(claim=CLAIM, mode="manuscript", manuscript_text="bring-your-own text")
        task = asyncio.create_task(
            runner.run_pipeline(bad, run_id=run_id, bus=bus, client=object()))
        # wait_for guards the seal guarantee: a regression that leaves the stream open hangs the
        # drain, which surfaces as a TimeoutError here rather than hanging the whole suite.
        frames = await asyncio.wait_for(_collect(sub), timeout=5.0)
        with self.assertRaises(ValueError):
            await task
        self.assertEqual([f.data["seq"] for f in frames], list(range(len(frames))))  # still gap-free
        self.assertEqual(frames[0].event, "run_start")
        err = frames[-1]
        self.assertEqual(err.event, "error")
        self.assertEqual(err.data["stage"], "ingest")
        self.assertTrue(err.data["message"])
        self.assertNotIn("run_complete", _names(frames))
        self.assertTrue(bus.stream(run_id, create=False).is_done)  # sealed

    async def test_error_frame_on_adjudicate_failure_seals_stream(self):
        # Grounding succeeds (vendored cache), then the injected client's model call raises — the
        # failure must be tagged to the adjudicate stage and still seal the stream.
        bus = EventBus()
        run_id = "run_adjudicate_err"
        sub = bus.open(run_id)
        req = RunRequest(claim=CLAIM, paper_ref=PMID, mode="pmid")
        task = asyncio.create_task(
            runner.run_pipeline(req, run_id=run_id, bus=bus, client=RaisingAnthropic()))
        frames = await asyncio.wait_for(_collect(sub), timeout=15.0)
        with self.assertRaises(RuntimeError):
            await task
        names = _names(frames)
        err = frames[-1]
        self.assertEqual(err.event, "error")
        self.assertEqual(err.data["stage"], "adjudicate")
        self.assertTrue(err.data["message"])
        # The pre-adjudicate stream still flowed; the model failed mid-triad, so no run_complete.
        self.assertEqual(names[0], "run_start")
        self.assertIn("stage_end", names)                       # ingest/ground stages completed
        self.assertNotIn("run_complete", names)
        self.assertTrue(bus.stream(run_id, create=False).is_done)  # sealed

    async def test_error_on_client_construction_seals_stream(self):
        # The precise latent-regression guard: on the live path (client=None) the model client is
        # built lazily and can raise with no key. That construction lives INSIDE the try, so the
        # failure must still emit an `error` frame and seal the stream — never a silently unsealed
        # run that hangs every EventSource. Patch the constructor to raise and prove it.
        orig = runner.TelemetryModelClient

        def _boom(*args, **kwargs):
            raise RuntimeError("no ANTHROPIC_API_KEY")

        runner.TelemetryModelClient = _boom
        try:
            bus = EventBus()
            run_id = "run_ctor_err"
            sub = bus.open(run_id)
            req = RunRequest(claim=CLAIM, paper_ref=PMID, mode="pmid")
            task = asyncio.create_task(
                runner.run_pipeline(req, run_id=run_id, bus=bus, client=None))
            frames = await asyncio.wait_for(_collect(sub), timeout=15.0)
            with self.assertRaises(RuntimeError):
                await task
            err = frames[-1]
            self.assertEqual(err.event, "error")
            self.assertEqual(err.data["stage"], "adjudicate")
            self.assertNotIn("run_complete", _names(frames))
            self.assertTrue(bus.stream(run_id, create=False).is_done)  # sealed, not hung
        finally:
            runner.TelemetryModelClient = orig


if __name__ == "__main__":
    unittest.main(verbosity=2)
