"""In-memory async pub/sub event bus for citeval SSE streams (W1-EVENTS).

One :class:`EventBus` fans a single run's (or batch's) SSE frames out to *any number* of
subscribers — the browser's ``EventSource`` on ``GET /api/runs/{id}/events`` plus, say, a second
tab, a reconnect, or a test harness — each seeing the **same ordered, gap-free** sequence.

Three guarantees, enforced structurally (not by convention):

1. **Ordered, gap-free ``seq``.** The bus is the single serialization point: it stamps a monotonic
   ``seq`` (0, 1, 2, …) onto every frame under a lock, so ``seq`` == the frame's index in the
   stream. No producer can create a gap or a reordering.
2. **Buffered replay for late subscribers.** Every frame is retained. A subscriber that connects
   *after* the run started (or after it finished) still receives the whole stream from ``seq: 0``,
   then continues live with no gap and no duplicate at the seam — because the backlog snapshot and
   the live registration happen in the *same* critical section as a publish.
3. **A completion sentinel.** Closing a stream wakes every subscriber; each drains any remaining
   buffered frames and then its async iterator stops (``StopAsyncIteration``). The SSE layer turns
   that into a transport close after the terminal ``run_complete`` / ``batch_complete`` frame.

**Producer thread-safety.** Publishing is safe from *any* thread, not just the event loop. The
adjudicator's ``config.on_round`` hook is a synchronous callback that a runner will typically fire
from a worker thread (``asyncio.to_thread``); the bus buffers under a ``threading.Lock`` and wakes
each async subscriber on *its own* loop via ``loop.call_soon_threadsafe`` — so a cross-thread
publish never touches an asyncio primitive from the wrong thread.

The bus is transport-agnostic: it deals in :class:`Frame` objects (an event name + a merged
``data`` payload). ``contracts`` is imported read-only only to accept its Pydantic event models as
publish payloads; nothing here imports ``fastapi`` or ``src/citeval``.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Mapping, Optional

try:  # contracts are read-only; used only to normalize Pydantic payloads to dicts.
    from pydantic import BaseModel
except Exception:  # pragma: no cover - pydantic is a hard dep of the server, but stay defensive
    BaseModel = None  # type: ignore[assignment]

# The four envelope keys the bus owns / fills on every frame (contracts.SSEEnvelope).
_ENVELOPE_KEYS = ("run_id", "seq", "ts", "elapsed_ms")

# Internal queue sentinel signalling "stream closed" to a waiting subscriber.
_DONE = object()


class StreamClosed(RuntimeError):
    """Raised when publishing to a stream that has already been closed. A closed stream's ``seq``
    space is sealed; re-opening it would break the gap-free guarantee, so this fails loud."""


@dataclass
class Frame:
    """One SSE frame: the event name plus the fully-merged ``data`` object (envelope +
    event-specific fields). ``seq`` is authoritative in ``data['seq']`` (stamped by the stream)."""

    event: str
    data: dict[str, Any]

    @property
    def seq(self) -> Optional[int]:
        return self.data.get("seq")

    @property
    def run_id(self) -> Optional[str]:
        return self.data.get("run_id")

    def to_sse(self) -> str:
        """Render as an SSE wire frame: ``event: <name>\\ndata: <json>\\n\\n``.

        A convenience for the server layer; ``data`` is JSON-encoded with a stable key order so the
        wire bytes are deterministic for a given frame.
        """
        payload = json.dumps(self.data, ensure_ascii=False, sort_keys=True)
        return f"event: {self.event}\ndata: {payload}\n\n"


class Subscription:
    """An async iterator over one stream, from ``seq: 0`` to close.

    Yields the backlog captured at :meth:`Stream.open` (in order), then live frames as they arrive,
    then stops when the stream closes. Registered eagerly at ``open`` time so no publish can slip
    through between "read the backlog" and "start listening". Also usable as an async context
    manager (``async with stream.open() as sub:``) to guarantee cleanup.
    """

    def __init__(self, stream: "Stream", backlog: list[Frame], done_at_open: bool,
                 queue: "asyncio.Queue[Any]", key: int):
        self._stream = stream
        self._backlog = backlog
        self._i = 0
        self._done_at_open = done_at_open
        self._queue = queue
        self._key = key
        self._closed = False

    def __aiter__(self) -> "Subscription":
        return self

    async def __anext__(self) -> Frame:
        # 1) drain the replay backlog first, in order.
        if self._i < len(self._backlog):
            frame = self._backlog[self._i]
            self._i += 1
            return frame
        # 2) if the stream was already closed when we opened, the backlog was the whole stream.
        if self._done_at_open:
            await self.aclose()
            raise StopAsyncIteration
        # 3) otherwise wait for the next live frame (or the close sentinel).
        item = await self._queue.get()
        if item is _DONE:
            await self.aclose()
            raise StopAsyncIteration
        return item

    async def aclose(self) -> None:
        if not self._closed:
            self._closed = True
            self._stream._detach(self._key)

    async def __aenter__(self) -> "Subscription":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()


class Stream:
    """A single ordered event stream (one run_id or batch_id), with buffered replay.

    Thread-safe: :meth:`publish` and :meth:`close` may be called from any thread; :meth:`open`
    must be called from the subscriber's event loop (it binds a queue to that loop).
    """

    def __init__(self, stream_id: str):
        self.id = stream_id
        self._lock = threading.Lock()
        self._buffer: list[Frame] = []
        self._done = False
        self._next_seq = 0
        self._next_key = 0
        # active live subscribers: key -> (loop, queue)
        self._subscribers: dict[int, tuple[asyncio.AbstractEventLoop, "asyncio.Queue[Any]"]] = {}

    # ---- producer side (thread-safe) -------------------------------------------------------
    def publish(
        self,
        event: str,
        payload: Any = None,
        *,
        elapsed_ms: Optional[float] = None,
        ts: Optional[float] = None,
        **fields: Any,
    ) -> Frame:
        """Append one frame and fan it out. ``payload`` may be a contracts Pydantic model, a
        mapping, or ``None`` (with the event fields passed as keywords). The bus stamps ``seq`` and
        fills any missing envelope fields (``run_id`` always the stream id; ``ts`` defaults to wall
        time; ``elapsed_ms`` defaults to 0). Raises :class:`StreamClosed` after :meth:`close`."""
        data = _as_data(payload)
        data.update(fields)
        # Envelope: run_id/seq are authoritative from the bus; ts/elapsed_ms fill if absent.
        data["run_id"] = self.id
        if ts is not None:
            data["ts"] = float(ts)          # SSEEnvelope.ts is a float (epoch seconds)
        elif "ts" not in data:
            data["ts"] = time.time()
        if elapsed_ms is not None:
            data["elapsed_ms"] = float(elapsed_ms)
        elif "elapsed_ms" not in data:
            data["elapsed_ms"] = 0.0

        with self._lock:
            if self._done:
                raise StreamClosed(f"stream {self.id!r} is closed; cannot publish {event!r}")
            data["seq"] = self._next_seq
            self._next_seq += 1
            frame = Frame(event=event, data=data)
            self._buffer.append(frame)
            # Fan out INSIDE the lock: it serializes the per-subscriber enqueues in seq order, so a
            # live subscriber can never receive seq N+1 before seq N even when two producer threads
            # publish to this stream concurrently (worker-thread on_round vs the loop-thread runner,
            # or concurrent runs feeding a batch stream). call_soon_threadsafe never blocks on the
            # loop, so holding the lock across it is cheap.
            self._fanout_locked(frame)
        return frame

    def close(self) -> None:
        """Seal the stream: no more publishes, and every current/future subscriber terminates
        after draining the buffer. Idempotent."""
        with self._lock:
            if self._done:
                return
            self._done = True
            self._fanout_locked(_DONE)

    def _fanout_locked(self, item: Any) -> None:
        """Enqueue ``item`` (a :class:`Frame` or the ``_DONE`` sentinel) to every live subscriber.

        MUST be called holding ``self._lock`` — that's what keeps live delivery order equal to
        ``seq`` order. A subscriber whose event loop has been torn down (``call_soon_threadsafe``
        raises ``RuntimeError``) is dropped here rather than being allowed to break delivery to the
        healthy subscribers or propagate the error into the producer thread.
        """
        dead: list[int] = []
        for key, (loop, queue) in self._subscribers.items():
            try:
                loop.call_soon_threadsafe(queue.put_nowait, item)
            except RuntimeError:
                dead.append(key)  # loop closed / shutting down — this subscriber is gone
        for key in dead:
            self._subscribers.pop(key, None)

    # ---- consumer side ---------------------------------------------------------------------
    def open(self) -> Subscription:
        """Register a subscriber and snapshot the replay backlog *atomically*.

        Must run inside an event loop. The backlog is every frame published so far; live frames
        (published after this call) arrive via a per-subscriber queue. Because the snapshot and the
        registration share the publish lock, every frame lands in exactly one of the two paths — no
        gap, no duplicate at the seam.
        """
        loop = asyncio.get_running_loop()
        queue: "asyncio.Queue[Any]" = asyncio.Queue()
        with self._lock:
            backlog = list(self._buffer)
            done = self._done
            key = self._next_key
            self._next_key += 1
            if not done:
                self._subscribers[key] = (loop, queue)
        return Subscription(self, backlog, done, queue, key)

    def _detach(self, key: int) -> None:
        with self._lock:
            self._subscribers.pop(key, None)

    # ---- introspection ---------------------------------------------------------------------
    @property
    def is_done(self) -> bool:
        with self._lock:
            return self._done

    @property
    def n_frames(self) -> int:
        with self._lock:
            return len(self._buffer)

    @property
    def n_subscribers(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def frames(self) -> list[Frame]:
        """A snapshot copy of the buffered frames (for tests / late diagnostics)."""
        with self._lock:
            return list(self._buffer)


class EventBus:
    """A registry of :class:`Stream`s keyed by run_id / batch_id.

    Both id kinds share the same code path — a "stream" is just an ordered channel. Create/lookup
    is lazy: publishing or subscribing to an unknown id creates the stream, so a subscriber that
    arrives *before* the producer still attaches and waits.
    """

    def __init__(self) -> None:
        self._streams: dict[str, Stream] = {}
        self._lock = threading.Lock()

    def stream(self, stream_id: str, *, create: bool = True) -> Optional[Stream]:
        """Get (or, by default, create) the stream for ``stream_id``."""
        with self._lock:
            s = self._streams.get(stream_id)
            if s is None and create:
                s = Stream(stream_id)
                self._streams[stream_id] = s
            return s

    def publish(
        self,
        stream_id: str,
        event: str,
        payload: Any = None,
        *,
        elapsed_ms: Optional[float] = None,
        ts: Optional[float] = None,
        **fields: Any,
    ) -> Frame:
        """Publish one frame to ``stream_id`` (creating the stream if new)."""
        return self.stream(stream_id).publish(  # type: ignore[union-attr]
            event, payload, elapsed_ms=elapsed_ms, ts=ts, **fields
        )

    def close(self, stream_id: str) -> None:
        """Close ``stream_id`` if it exists."""
        s = self.stream(stream_id, create=False)
        if s is not None:
            s.close()

    def open(self, stream_id: str) -> Subscription:
        """Open a :class:`Subscription` to ``stream_id`` (creating the stream if new). Eager
        registration — use this (over :meth:`subscribe`) when a publish may race the subscribe."""
        return self.stream(stream_id).open()  # type: ignore[union-attr]

    async def subscribe(self, stream_id: str) -> AsyncIterator[Frame]:
        """Async-generator convenience over :meth:`open`: ``async for frame in bus.subscribe(id)``."""
        sub = self.open(stream_id)
        try:
            async for frame in sub:
                yield frame
        finally:
            await sub.aclose()

    def discard(self, stream_id: str) -> None:
        """Drop a (typically completed) stream to free its buffer. Closes it first so any lingering
        subscriber terminates cleanly."""
        with self._lock:
            s = self._streams.pop(stream_id, None)
        if s is not None:
            s.close()

    def __contains__(self, stream_id: str) -> bool:
        with self._lock:
            return stream_id in self._streams

    def ids(self) -> list[str]:
        with self._lock:
            return list(self._streams)


def _as_data(payload: Any) -> dict[str, Any]:
    """Normalize a publish payload (Pydantic model, mapping, or None) to a fresh mutable dict."""
    if payload is None:
        return {}
    if BaseModel is not None and isinstance(payload, BaseModel):
        return payload.model_dump()
    if isinstance(payload, Mapping):
        return dict(payload)
    raise TypeError(
        f"publish payload must be a pydantic model, a mapping, or None; got {type(payload).__name__}"
    )


# Process-wide default bus, shared by the runner / batch / server sessions that import it.
BUS = EventBus()


def get_bus() -> EventBus:
    """The process-wide default :class:`EventBus`."""
    return BUS


__all__ = [
    "Frame",
    "Stream",
    "Subscription",
    "EventBus",
    "StreamClosed",
    "BUS",
    "get_bus",
]
