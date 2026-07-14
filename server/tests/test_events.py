"""Tests for the SSE event bus (`citeval_api.events`).

Written as `unittest.IsolatedAsyncioTestCase` so they run on the stdlib — pytest is NOT installed
in the eval env (see server/README.md). Run:

    python -m unittest discover -s server/tests -t server -v

Covers the three W1-EVENTS guarantees: ordered delivery to many subscribers, buffered replay for a
late subscriber, and a completion sentinel that terminates every stream — plus gap-free `seq`,
cross-thread publishing, stream isolation, and the SSE wire rendering.
"""
import asyncio
import json
import threading
import unittest

from citeval_api.contracts import ProgressData, StageStartData
from citeval_api.events import BUS, EventBus, Frame, StreamClosed, get_bus


async def collect(sub) -> list[Frame]:
    """Drain a subscription to exhaustion (i.e. until the stream closes)."""
    return [frame async for frame in sub]


def seqs(frames: list[Frame]) -> list[int]:
    return [f.seq for f in frames]


class TestOrderedFanOut(unittest.IsolatedAsyncioTestCase):
    async def test_many_subscribers_all_see_same_ordered_gapfree_stream(self):
        bus = EventBus()
        sid = "run_fanout"
        n_subs = 10
        subs = [bus.open(sid) for _ in range(n_subs)]  # all registered BEFORE any publish
        collectors = [asyncio.create_task(collect(s)) for s in subs]

        n_frames = 25
        for i in range(n_frames):
            bus.publish(sid, "progress", {"pct": float(i)}, elapsed_ms=float(i))
        bus.close(sid)

        results = await asyncio.gather(*collectors)
        for frames in results:
            self.assertEqual(len(frames), n_frames)
            self.assertEqual(seqs(frames), list(range(n_frames)))          # gap-free, monotonic
            self.assertEqual([f.data["pct"] for f in frames], [float(i) for i in range(n_frames)])

    async def test_subscriber_started_after_open_still_gets_all_live_frames(self):
        # Opening registers eagerly, so even if the collector task hasn't run yet, nothing is lost.
        bus = EventBus()
        sid = "run_delayed_collector"
        sub = bus.open(sid)
        for i in range(5):
            bus.publish(sid, "stage_start", {"stage": "ingest"}, elapsed_ms=float(i))
        bus.close(sid)
        frames = await collect(sub)  # collector starts only now, drains the queue
        self.assertEqual(seqs(frames), [0, 1, 2, 3, 4])


class TestLateSubscriberReplay(unittest.IsolatedAsyncioTestCase):
    async def test_mid_run_subscriber_replays_backlog_then_continues_live(self):
        bus = EventBus()
        sid = "run_late"
        early = bus.open(sid)
        bus.publish(sid, "run_start", {"mode": "pmid"}, elapsed_ms=0.0)     # seq 0
        bus.publish(sid, "stage_start", {"stage": "ingest"}, elapsed_ms=1.0)  # seq 1

        late = bus.open(sid)  # joins after two frames — must still see them
        bus.publish(sid, "stage_end", {"stage": "ingest", "summary": ""}, elapsed_ms=2.0)  # seq 2
        bus.close(sid)

        early_frames, late_frames = await asyncio.gather(collect(early), collect(late))
        self.assertEqual(seqs(early_frames), [0, 1, 2])
        self.assertEqual(seqs(late_frames), [0, 1, 2])   # from seq 0 despite joining late
        # No duplicate at the backlog→live seam, and the same objects/ordering for both.
        self.assertEqual([f.event for f in late_frames], ["run_start", "stage_start", "stage_end"])

    async def test_subscriber_after_completion_replays_whole_stream_then_stops(self):
        bus = EventBus()
        sid = "run_finished"
        for i in range(4):
            bus.publish(sid, "progress", {"pct": float(i)}, elapsed_ms=float(i))
        bus.close(sid)

        sub = bus.open(sid)  # opened only after close
        frames = await collect(sub)
        self.assertEqual(seqs(frames), [0, 1, 2, 3])

    async def test_two_late_subscribers_are_independent(self):
        bus = EventBus()
        sid = "run_two_late"
        for i in range(3):
            bus.publish(sid, "progress", {"pct": float(i)}, elapsed_ms=float(i))
        a = bus.open(sid)
        b = bus.open(sid)
        bus.publish(sid, "progress", {"pct": 99.0}, elapsed_ms=9.0)
        bus.close(sid)
        fa, fb = await asyncio.gather(collect(a), collect(b))
        self.assertEqual(seqs(fa), [0, 1, 2, 3])
        self.assertEqual(seqs(fb), [0, 1, 2, 3])


class TestCompletionSentinel(unittest.IsolatedAsyncioTestCase):
    async def test_open_subscriber_blocks_until_frame_then_terminates_on_close(self):
        bus = EventBus()
        sid = "run_blocking"
        sub = bus.open(sid)
        bus.publish(sid, "run_start", {"mode": "auto"}, elapsed_ms=0.0)

        first = await asyncio.wait_for(sub.__anext__(), timeout=1.0)
        self.assertEqual(first.seq, 0)

        # No further frames yet: the next pull must block (still-open stream).
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(sub.__anext__(), timeout=0.05)

        bus.close(sid)
        with self.assertRaises(StopAsyncIteration):
            await sub.__anext__()

    async def test_close_is_idempotent(self):
        bus = EventBus()
        sid = "run_idem"
        bus.publish(sid, "progress", {"pct": 1.0}, elapsed_ms=0.0)
        bus.close(sid)
        bus.close(sid)  # must not raise
        sub = bus.open(sid)
        self.assertEqual(seqs(await collect(sub)), [0])

    async def test_context_manager_detaches_subscriber(self):
        bus = EventBus()
        sid = "run_ctx"
        async with bus.open(sid) as sub:
            bus.publish(sid, "progress", {"pct": 1.0}, elapsed_ms=0.0)
            f = await asyncio.wait_for(sub.__anext__(), timeout=1.0)
            self.assertEqual(f.seq, 0)
        stream = bus.stream(sid, create=False)
        self.assertEqual(stream.n_subscribers, 0)  # cleaned up on __aexit__


class TestEnvelopeAndSeq(unittest.IsolatedAsyncioTestCase):
    async def test_bus_stamps_envelope_and_merges_payload(self):
        bus = EventBus()
        sid = "run_env"
        frame = bus.publish(sid, "stage_start", StageStartData(stage="ingest"),
                            elapsed_ms=12.0, ts=1752451200.0)
        self.assertEqual(frame.event, "stage_start")
        self.assertEqual(frame.data["stage"], "ingest")   # payload field preserved
        self.assertEqual(frame.data["run_id"], sid)       # envelope filled
        self.assertEqual(frame.data["seq"], 0)
        self.assertEqual(frame.data["ts"], 1752451200.0)
        self.assertEqual(frame.data["elapsed_ms"], 12.0)

    async def test_seq_is_monotonic_gapfree_across_payload_kinds(self):
        bus = EventBus()
        sid = "run_seq"
        f0 = bus.publish(sid, "run_start", {"mode": "pmid"}, elapsed_ms=0.0)
        f1 = bus.publish(sid, "progress", ProgressData(pct=1.0, est_total_ms=10.0, est_remaining_ms=9.0), elapsed_ms=1.0)
        f2 = bus.publish(sid, "stage_end", stage="report", summary="done", elapsed_ms=2.0)  # kwargs form
        self.assertEqual([f0.seq, f1.seq, f2.seq], [0, 1, 2])
        self.assertEqual(f2.data["stage"], "report")
        self.assertEqual(f2.data["summary"], "done")

    async def test_run_id_always_overrides_payload(self):
        bus = EventBus()
        sid = "run_authoritative"
        # A payload that tries to smuggle a different run_id/seq must not win.
        frame = bus.publish(sid, "progress", {"run_id": "spoof", "seq": 999, "pct": 1.0}, elapsed_ms=0.0)
        self.assertEqual(frame.data["run_id"], sid)
        self.assertEqual(frame.data["seq"], 0)

    async def test_publish_after_close_raises(self):
        bus = EventBus()
        sid = "run_closed"
        bus.publish(sid, "progress", {"pct": 1.0}, elapsed_ms=0.0)
        bus.close(sid)
        with self.assertRaises(StreamClosed):
            bus.publish(sid, "progress", {"pct": 2.0}, elapsed_ms=1.0)

    async def test_bad_payload_type_rejected(self):
        bus = EventBus()
        with self.assertRaises(TypeError):
            bus.publish("run_bad", "progress", 42, elapsed_ms=0.0)  # not model/mapping/None


class TestCrossThreadProducer(unittest.IsolatedAsyncioTestCase):
    async def test_publish_from_worker_thread_reaches_async_subscriber(self):
        # Mirrors the real integration: a sync producer (adjudicator.on_round) on a worker thread.
        bus = EventBus()
        sid = "run_thread"
        sub = bus.open(sid)

        def producer():
            for i in range(6):
                bus.publish(sid, "debate_round", {"round": i + 1}, elapsed_ms=float(i))
            bus.close(sid)

        await asyncio.to_thread(producer)   # runs entirely off the event loop
        frames = await collect(sub)
        self.assertEqual(seqs(frames), [0, 1, 2, 3, 4, 5])
        self.assertEqual([f.data["round"] for f in frames], [1, 2, 3, 4, 5, 6])

    async def test_concurrent_producers_deliver_live_frames_in_seq_order(self):
        # Several threads publish to ONE stream while a LIVE subscriber consumes. Live delivery
        # order must equal seq order (the fan-out is serialized under the stream lock). Asserting on
        # the live-received seqs — not the replay buffer — is what exercises the ordering guarantee.
        bus = EventBus()
        sid = "run_concurrent_live"
        sub = bus.open(sid)
        n_threads, per_thread = 4, 50
        total = n_threads * per_thread
        barrier = threading.Barrier(n_threads)

        def producer():
            barrier.wait()  # maximize interleaving across threads
            for _ in range(per_thread):
                bus.publish(sid, "progress", {}, elapsed_ms=0.0)

        async def run_producers():
            await asyncio.gather(*(asyncio.to_thread(producer) for _ in range(n_threads)))
            bus.close(sid)

        producers = asyncio.create_task(run_producers())
        frames = await collect(sub)
        await producers
        # Gap-free 0..total-1, and received strictly in ascending seq order on the wire.
        received = seqs(frames)
        self.assertEqual(received, list(range(total)))

    async def test_concurrent_producer_and_late_subscriber(self):
        bus = EventBus()
        sid = "run_thread_late"
        started = threading.Event()

        def producer():
            for i in range(20):
                bus.publish(sid, "progress", {"pct": float(i)}, elapsed_ms=float(i))
                if i == 0:
                    started.set()
            bus.close(sid)

        task = asyncio.create_task(asyncio.to_thread(producer))
        await asyncio.to_thread(started.wait)  # ensure some frames exist before we subscribe
        sub = bus.open(sid)
        await task
        frames = await collect(sub)
        # Late subscriber still gets the full, ordered, gap-free stream from seq 0.
        self.assertEqual(seqs(frames), list(range(20)))


class TestStreamIsolationAndRegistry(unittest.IsolatedAsyncioTestCase):
    async def test_run_and_batch_streams_are_isolated(self):
        bus = EventBus()
        r = bus.publish("run_1", "run_start", {"mode": "pmid"}, elapsed_ms=0.0)
        b = bus.publish("batch_1", "batch_start", {"n": 3}, elapsed_ms=0.0)
        self.assertEqual(r.seq, 0)
        self.assertEqual(b.seq, 0)           # independent seq spaces
        self.assertIn("run_1", bus.ids())
        self.assertIn("batch_1", bus.ids())
        bus.close("run_1")
        bus.close("batch_1")
        rf = await collect(bus.open("run_1"))
        bf = await collect(bus.open("batch_1"))
        self.assertEqual([f.event for f in rf], ["run_start"])
        self.assertEqual([f.event for f in bf], ["batch_start"])

    async def test_discard_removes_stream(self):
        bus = EventBus()
        bus.publish("run_gone", "progress", {"pct": 1.0}, elapsed_ms=0.0)
        self.assertIn("run_gone", bus)
        bus.discard("run_gone")
        self.assertNotIn("run_gone", bus)

    async def test_module_default_bus_is_shared_singleton(self):
        self.assertIs(get_bus(), BUS)


class TestFrameRendering(unittest.TestCase):
    def test_to_sse_wire_format(self):
        frame = Frame("progress", {"run_id": "r", "seq": 4, "ts": 1.0, "elapsed_ms": 0.0, "pct": 50.0})
        wire = frame.to_sse()
        self.assertTrue(wire.startswith("event: progress\n"))
        self.assertTrue(wire.endswith("\n\n"))
        body = wire.split("data: ", 1)[1].rsplit("\n\n", 1)[0]
        parsed = json.loads(body)
        self.assertEqual(parsed["pct"], 50.0)
        self.assertEqual(parsed["seq"], 4)

    def test_frame_accessors(self):
        frame = Frame("stage_end", {"run_id": "r7", "seq": 2})
        self.assertEqual(frame.seq, 2)
        self.assertEqual(frame.run_id, "r7")


if __name__ == "__main__":
    unittest.main()
