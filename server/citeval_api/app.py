"""FastAPI application for the citeval HTTP/SSE API (W2-SERVER).

A **thin, read-only** web surface over the ``citeval`` package. It never edits ``src/citeval/*``;
it drives the pipeline only through the frozen seams (``adjudicate(..., client=)`` / ``config.on_round``,
already wired by W2-RUNNER) and streams live progress, cost, and verdicts over Server-Sent Events.
The nine routes are exactly those in ``docs/api_contract.md`` §1, mounted under ``/api``:

    1 POST /api/runs            RunRequest  -> RunCreated {run_id}
    2 GET  /api/runs/{id}/events            -> text/event-stream  (run SSE)
    3 GET  /api/runs/{id}                   -> RunResult
    4 POST /api/batch           BatchRequest-> BatchCreated {batch_id}
    5 GET  /api/batch/{id}/events           -> text/event-stream  (batch SSE)
    6 GET  /api/batch/{id}                  -> BatchResult
    7 GET  /api/pricing                     -> PricingInfo
    8 GET  /api/health                      -> {status:"ok"}
    9 GET  /api/showcase                    -> RunResult[]   (cached; NO key needed)

Design:

* **In-memory registries.** ``runs`` / ``batches`` map an id to its record (request, background
  task, final result-or-error). No DB — the process holds live and recently-finished runs.
* **The two-call pattern.** ``POST`` launches a background task and returns the id immediately; the
  client opens ``GET …/events`` (an ``EventSource``) to watch, and/or ``GET …/{id}`` for the final
  result. The W1-EVENTS bus **buffers every frame from seq 0**, so a subscriber that connects late —
  or after the run finished — still replays the whole stream. That makes the stream robust to the
  create→subscribe race with no server-side coordination.
* **SSE transport.** Each frame is emitted verbatim via :meth:`events.Frame.to_sse` (the exact
  ``event:``/``data:`` wire shape the FE ``EventSource`` listeners key off), so no ``sse-starlette``
  dependency is needed — a plain :class:`StreamingResponse` over a bus subscription suffices.
* **Batch is guarded.** W2-BATCH (``citeval_api.batch``) may not be merged yet; it is imported
  behind ``try`` so **runs always work**. Absent it, ``POST /api/batch`` returns ``503`` while every
  run route stays live. The batch entrypoint is called through a signature-tolerant adapter so it
  integrates with zero server changes once it lands.
* **Model client injection.** ``create_app(model_client_factory=…)`` lets a test inject an
  in-process fake Anthropic client (offline, no key); the default (``None``) is the live path where
  W1-TELEMETRY builds a real Opus 4.8 client lazily inside the run.
* **Static web.** If a built SPA is present (``web/dist``) it is served at ``/`` with an
  index-fallback for client-side routes; ``/api`` always takes precedence. In dev the FE runs under
  Vite and reaches this server cross-origin — hence CORS for the Vite origins.

``citeval`` is imported only transitively (read-only) via ``runner``; this module imports nothing
from ``src/citeval`` directly.
"""
from __future__ import annotations

import sys
from pathlib import Path

# --- import path bootstrap (must precede the runner import, which loads `citeval`) --------------
# Make `src/` (the `citeval` package) importable so `uvicorn citeval_api.app:app` works even when
# the process was not started via `server/main.py`. `server/` is already importable (we are being
# imported as `citeval_api.app`), so only `src/` needs adding; adding `server/` too is harmless.
_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT / "src", _ROOT / "server"):
    _s = str(_p)
    if _p.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional
from uuid import uuid4

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from . import pricing
from .contracts import (
    BatchCreated,
    BatchRequest,
    BatchResult,
    Health,
    PricingInfo,
    RunCreated,
    RunRequest,
    RunResult,
)
from .events import BUS, EventBus
from .progress import Benchmarks
from .runner import run_pipeline
from .showcase import load_showcase

__all__ = ["create_app", "app"]

# Headers that keep an SSE stream un-buffered end-to-end (proxies included).
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # disable nginx response buffering for the stream
}

# Default CORS origins: the Vite dev server (5173) and `vite preview` (4173), on both host spellings.
_DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:4173", "http://127.0.0.1:4173",
]
# …plus any localhost/loopback port, so an atypical dev port still works out of the box.
_LOCALHOST_ORIGIN_RE = r"http://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?"


# ============================================================================================
# W2-BATCH — imported behind a guard so runs work whether or not it has merged.
# ============================================================================================
try:  # pragma: no cover - exercised by whichever tree does/doesn't have batch.py
    from . import batch as _batch_mod  # type: ignore
except Exception:  # noqa: BLE001 - any import failure => batch simply unavailable
    _batch_mod = None  # type: ignore[assignment]

# Resolve the batch entrypoint by the most likely names (W2-BATCH mirrors the runner's shape).
_batch_entry: Optional[Callable[..., Any]] = None
if _batch_mod is not None:
    for _name in ("run_batch", "execute_batch", "run_batch_pipeline", "batch_pipeline"):
        _fn = getattr(_batch_mod, _name, None)
        if callable(_fn):
            _batch_entry = _fn
            break


def _filter_kwargs(fn: Callable[..., Any], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Keep only the kwargs ``fn`` actually accepts (or all of them if it takes ``**kwargs``), so
    the batch adapter integrates with whatever exact signature W2-BATCH ships."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return dict(kwargs)
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return dict(kwargs)
    return {k: v for k, v in kwargs.items() if k in params}


def _evict_completed(registry: dict[str, Any], bus: EventBus, cap: int) -> None:
    """Bound memory: once ``registry`` exceeds ``cap``, drop the OLDEST **completed** records and
    free their buffered bus streams (``bus.discard``). In-flight / still-streaming runs are never
    evicted — a dict preserves insertion order, so iteration is oldest-first. Without this, every
    finished run would be retained for the process lifetime (the record *and* the bus buffer, which
    duplicates the RunResult in its ``run_complete`` frame), growing memory without bound."""
    if cap <= 0 or len(registry) <= cap:
        return
    for sid in list(registry):
        if len(registry) <= cap:
            break
        task = getattr(registry[sid], "task", None)
        if task is not None and task.done():
            del registry[sid]
            bus.discard(sid)


# ============================================================================================
# In-memory run/batch records.
# ============================================================================================
@dataclass
class RunRecord:
    """One tracked run: its request, the background task driving it, and the terminal outcome
    (exactly one of ``result`` / ``error`` is set once ``task`` finishes)."""
    run_id: str
    request: RunRequest
    task: Optional["asyncio.Task[Any]"] = None
    result: Optional[RunResult] = None
    error: Optional[str] = None


@dataclass
class BatchRecord:
    batch_id: str
    request: BatchRequest
    task: Optional["asyncio.Task[Any]"] = None
    result: Optional[BatchResult] = None
    error: Optional[str] = None


@dataclass
class _AppState:
    bus: EventBus
    benchmarks: Benchmarks
    model_client_factory: Optional[Callable[[], Any]]
    max_retained: int = 512
    runs: dict[str, RunRecord] = field(default_factory=dict)
    batches: dict[str, BatchRecord] = field(default_factory=dict)


# ============================================================================================
# App factory
# ============================================================================================
def create_app(
    *,
    bus: EventBus = BUS,
    benchmarks: Optional[Benchmarks] = None,
    model_client_factory: Optional[Callable[[], Any]] = None,
    cors_origins: Optional[list[str]] = None,
    web_dist: Optional[str | Path] = None,
    serve_web: bool = True,
    max_retained: int = 512,
) -> FastAPI:
    """Build the citeval FastAPI app.

    * ``bus`` — the W1-EVENTS bus runs publish to and SSE routes subscribe from (defaults to the
      process-wide bus the runner uses).
    * ``benchmarks`` — shared rolling ETA state across runs (a fresh one per app by default).
    * ``model_client_factory`` — ``() -> client`` injected into each run (tests pass an in-process
      fake; ``None`` = the live Opus 4.8 path built lazily by W1-TELEMETRY).
    * ``cors_origins`` — override the default Vite dev origins.
    * ``web_dist`` / ``serve_web`` — location of a built SPA to serve at ``/`` (defaults to
      ``web/dist``; only mounted if it exists and ``serve_web`` is true).
    * ``max_retained`` — cap on retained **completed** runs/batches (oldest evicted past this, with
      their bus buffers freed) so a long-lived server's memory stays bounded; ``0`` disables eviction.
    """
    state = _AppState(
        bus=bus,
        benchmarks=benchmarks if benchmarks is not None else Benchmarks(),
        model_client_factory=model_client_factory,
        max_retained=max_retained,
    )

    app = FastAPI(
        title="citeval API",
        version="1",
        summary="Citation-verification pipeline: grounded, measured verdicts over HTTP + SSE.",
    )
    app.state.citeval = state  # introspection hook for tests / diagnostics

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if cors_origins is not None else _DEFAULT_CORS_ORIGINS,
        allow_origin_regex=_LOCALHOST_ORIGIN_RE,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- SSE helper --------------------------------------------------------------------------
    def _sse_response(stream_id: str) -> StreamingResponse:
        """Stream a bus channel as SSE. Opens the subscription inside the generator (on the event
        loop that will iterate it) so its lifecycle — and its detach on client disconnect — is tied
        to the response. Replays from seq 0 (buffered), then live, then ends when the stream seals."""
        async def gen():
            sub = state.bus.open(stream_id)
            try:
                async for frame in sub:
                    yield frame.to_sse()
            finally:
                await sub.aclose()
        return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)

    # ============================ 1) POST /api/runs =====================================
    @app.post("/api/runs", response_model=RunCreated, tags=["runs"])
    async def create_run(req: RunRequest = Body(...)) -> RunCreated:
        run_id = f"run_{uuid4().hex[:12]}"
        rec = RunRecord(run_id=run_id, request=req)
        state.runs[run_id] = rec
        client = state.model_client_factory() if state.model_client_factory is not None else None

        async def _drive() -> None:
            # run_pipeline emits a terminal `error` frame + seals the stream on failure and re-raises;
            # we record the message so GET /api/runs/{id} can surface it as a 500.
            try:
                rec.result = await run_pipeline(
                    req, run_id=run_id, bus=state.bus,
                    client=client, benchmarks=state.benchmarks,
                )
            except Exception as exc:  # noqa: BLE001
                rec.error = f"{type(exc).__name__}: {exc}"

        rec.task = asyncio.create_task(_drive())
        _evict_completed(state.runs, state.bus, state.max_retained)
        return RunCreated(run_id=run_id)

    # ============================ 2) GET /api/runs/{id}/events ==========================
    @app.get("/api/runs/{run_id}/events", tags=["runs"])
    async def run_events(run_id: str) -> StreamingResponse:
        if run_id not in state.runs:
            raise HTTPException(status_code=404, detail=f"unknown run_id {run_id!r}")
        return _sse_response(run_id)

    # ============================ 3) GET /api/runs/{id} =================================
    @app.get("/api/runs/{run_id}", response_model=RunResult, tags=["runs"])
    async def get_run(run_id: str) -> RunResult:
        rec = state.runs.get(run_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"unknown run_id {run_id!r}")
        if rec.error is not None:
            raise HTTPException(status_code=500, detail=rec.error)
        if rec.result is None:
            # Still running — the client should watch GET …/events for liveness.
            raise HTTPException(status_code=409, detail="run still in progress")
        return rec.result

    # ============================ 4) POST /api/batch ====================================
    @app.post("/api/batch", response_model=BatchCreated, tags=["batch"])
    async def create_batch(req: BatchRequest = Body(...)) -> BatchCreated:
        if _batch_entry is None:
            raise HTTPException(
                status_code=503,
                detail="batch pipeline unavailable (W2-BATCH / citeval_api.batch not installed)",
            )
        batch_id = f"batch_{uuid4().hex[:12]}"
        rec = BatchRecord(batch_id=batch_id, request=req)
        state.batches[batch_id] = rec
        client = state.model_client_factory() if state.model_client_factory is not None else None
        kwargs = dict(
            batch_id=batch_id, bus=state.bus, benchmarks=state.benchmarks,
            client=client, model_client_factory=state.model_client_factory,
        )

        async def _drive() -> None:
            # Mirror the run path's offload+seal. `_batch_entry` may be a blocking SYNC function
            # (returns a BatchResult) or an async one; run the CALL in a worker thread so a sync,
            # blocking batch never freezes the event loop (and every other run's SSE stream), then
            # await the result if the entrypoint turned out to be async.
            try:
                res: Any = await asyncio.to_thread(
                    _batch_entry, req, **_filter_kwargs(_batch_entry, kwargs))
                if inspect.isawaitable(res):
                    res = await res
                rec.result = res
            except Exception as exc:  # noqa: BLE001
                rec.error = f"{type(exc).__name__}: {exc}"
            finally:
                # Defensive seal (idempotent, CREATE-if-absent): the run path is sealed by
                # execute_run's `finally` after it always publishes `run_start`/`error` (so the
                # stream exists); batch delegates to W2-BATCH, which on an early failure may publish
                # NOTHING — leaving no stream at all. `bus.close(create=False)` would then no-op and
                # a subscriber that connects afterward would lazily create a fresh, un-sealed stream
                # and block forever. Creating-then-closing guarantees a SEALED stream exists, so any
                # subscriber (before or after) terminates cleanly instead of hanging.
                state.bus.stream(batch_id).close()

        rec.task = asyncio.create_task(_drive())
        _evict_completed(state.batches, state.bus, state.max_retained)
        return BatchCreated(batch_id=batch_id)

    # ============================ 5) GET /api/batch/{id}/events =========================
    @app.get("/api/batch/{batch_id}/events", tags=["batch"])
    async def batch_events(batch_id: str) -> StreamingResponse:
        if batch_id not in state.batches:
            raise HTTPException(status_code=404, detail=f"unknown batch_id {batch_id!r}")
        return _sse_response(batch_id)

    # ============================ 6) GET /api/batch/{id} ================================
    @app.get("/api/batch/{batch_id}", response_model=BatchResult, tags=["batch"])
    async def get_batch(batch_id: str) -> BatchResult:
        rec = state.batches.get(batch_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"unknown batch_id {batch_id!r}")
        if rec.error is not None:
            raise HTTPException(status_code=500, detail=rec.error)
        if rec.result is None:
            raise HTTPException(status_code=409, detail="batch still in progress")
        return rec.result

    # ============================ 7) GET /api/pricing ===================================
    @app.get("/api/pricing", response_model=PricingInfo, tags=["meta"])
    async def get_pricing() -> PricingInfo:
        return PricingInfo(
            input=pricing.PRICING["input"],
            output=pricing.PRICING["output"],
            cache_write=pricing.PRICING["cache_write"],
            cache_read=pricing.PRICING["cache_read"],
            note=pricing.PRICING_NOTE,
        )

    # ============================ 8) GET /api/health ====================================
    @app.get("/api/health", response_model=Health, tags=["meta"])
    async def get_health() -> Health:
        return Health()

    # ============================ 9) GET /api/showcase ==================================
    @app.get("/api/showcase", response_model=list[RunResult], tags=["meta"])
    async def get_showcase() -> list[RunResult]:
        return load_showcase()

    # ---- static SPA (optional) ----------------------------------------------------------------
    _mount_web(app, web_dist, serve_web)
    return app


# ============================================================================================
# Static-web mounting (served only when a built SPA exists).
# ============================================================================================
def _resolve_web_dist(web_dist: Optional[str | Path]) -> Optional[Path]:
    if web_dist is not None:
        p = Path(web_dist)
        return p if p.is_dir() else None
    default = _ROOT / "web" / "dist"
    return default if default.is_dir() else None


def _mount_web(app: FastAPI, web_dist: Optional[str | Path], serve_web: bool) -> None:
    """Serve a built SPA at ``/`` with an index fallback for client-side routes. ``/api`` routes are
    registered first and so always win; unknown non-``/api`` GETs fall back to ``index.html``."""
    if not serve_web:
        return
    dist = _resolve_web_dist(web_dist)
    if dist is None:
        return
    index_file = dist / "index.html"

    # Preserve JSON errors for /api; fall back to the SPA shell for unknown web routes (deep links).
    @app.exception_handler(StarletteHTTPException)
    async def _spa_or_json(request: Request, exc: StarletteHTTPException):
        if (
            exc.status_code == 404
            and request.method in ("GET", "HEAD")
            and not request.url.path.startswith("/api")
            and index_file.is_file()
        ):
            return FileResponse(index_file)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")


# Module-level app for `uvicorn citeval_api.app:app` (live defaults; no key needed until a run).
app = create_app()
