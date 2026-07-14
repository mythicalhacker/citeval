"""Run one citeval verification and stream contract SSE events (W2-RUNNER).

This is the backend keystone: given a :class:`~citeval_api.contracts.RunRequest`, it drives the
**real** ``citeval`` pipeline end-to-end and fans a run's live progress, cost, and verdict out over
the W1-EVENTS bus as the exact SSE sequence the api_contract (§3) and the FE mock agree on:

    run_start
    stage_start(ingest) … stage_end(ingest) … progress
    stage_start(ground_retraction) … stage_end … progress
    stage_start(ground_scope) … stage_end … progress
    stage_start(adjudicate)
      per round r:  model_call(role,r,start) model_call(role,r,end)  ×(supporter,refuter,critic)
                    debate_round(r) cost_update progress
    stage_end(adjudicate) … progress
    stage_start(report) … stage_end … progress
    run_complete(result=RunResult)          # or error(stage,message) on any failure

The pipeline is **synchronous and blocking** (NCBI round-trips + a long adversarial triad), so
:func:`run_pipeline` offloads the whole run to a worker thread (``asyncio.to_thread``) and lets the
event loop serve the SSE subscribers concurrently. Every SSE frame is published through the
W1-EVENTS bus, which is thread-safe: the worker thread publishes, each async subscriber is woken on
its own loop (see ``events.Stream._fanout_locked``). One serialization point, gap-free ``seq``.

**``citeval`` is imported READ-ONLY.** We touch only the four frozen seams (api_contract §8):
``ground()`` / ``parse_claim_scope()`` (ingest + grounding), ``adjudicate(..., client=, config=)``
(the injected-client + ``on_round`` seams), and ``reporting.render_json`` / ``render_html``. Nothing
here edits ``src/citeval/*`` or reaches into a private pipeline helper — the live debate viz is built
only from what ``on_round`` and the injected client surface.

Two seams do the live streaming:
- **Injected client** — W1-TELEMETRY's :class:`~citeval_api.telemetry.TelemetryModelClient` captures
  each call's full four-tier usage (bucketed by role). We wrap it in :class:`_InstrumentedClient`,
  which brackets every triad call with ``model_call`` ``start``/``end`` frames (``end`` carries the
  call's usage + cost) — role fingerprinted off the system prompt, round incremented at each
  supporter turn.
- **``config.on_round``** — fires once per self-consistency round with the critic's parsed result;
  we turn each into a ``debate_round`` (+ a per-round cumulative ``cost_update`` and a ``progress``
  snapshot from the W1-EVENTS estimator).
"""
from __future__ import annotations

import asyncio
import re
import time
from collections import Counter
from dataclasses import replace
from typing import Any, Optional

# --- citeval (READ-ONLY: only the frozen seams — api_contract §8) ---------------------------
from citeval.adjudicator import AdjudicationConfig, adjudicate
from citeval.claim_scope import parse_claim_scope
from citeval.contracts import CitedIdentifier, ClaimUnit
from citeval.grounding import ground
from citeval.reporting import render_html, render_json

# --- server package (W0 contracts + W1 telemetry/events/progress/pricing) -------------------
from . import pricing
from .contracts import (
    CostUpdateData,
    DebateRoundData,
    ErrorData,
    ModelCallData,
    RawUsage,
    Role,
    RunCompleteData,
    RunMode,
    RunRequest,
    RunResult,
    RunStartData,
    RunTiming,
    Stage,
    StageEndData,
    StageStartData,
    TokenUsage,
)
from .events import BUS, EventBus
from .progress import Benchmarks, ProgressEstimator
from .telemetry import TelemetryModelClient, fingerprint_role

__all__ = ["run_pipeline", "execute_run", "STAGES"]

# The five pipeline stages, in the FROZEN canonical order (contracts.Stage / progress.STAGE_ORDER).
STAGES: tuple[Stage, ...] = ("ingest", "ground_retraction", "ground_scope", "adjudicate", "report")

# Ordinal grade vocabulary (api_contract §7). Kept LOCAL — not imported from a citeval internal —
# so the live running-agreement viz never depends on a private pipeline symbol. It feeds only the
# `debate_round.agreement` meter; the authoritative aggregate rides in the final Verdict.
_ORDINAL_GRADES: tuple[str, ...] = (
    "fully-supported", "supported-with-overreach", "partially-supported",
    "technically-true-but-misleading", "unsupported-for-the-claim", "contradicted",
)
_ORDINAL_SET = frozenset(_ORDINAL_GRADES)

# Canonical per-round advocate phrasings. The `on_round` seam surfaces only the CRITIC's parsed
# round — the supporter/refuter advocate text is internal to `adjudicate()` and NOT on this seam —
# so the live `debate_round` carries these fixed phrasings (identical to the FE mock's fallbacks, so
# the live and mock streams render the same). The real per-round signal is `critic_grade` +
# `agreement`, both derived from what `on_round` gives us.
_SUPPORTER_STANCE = "The cited text supports the claim."
_REFUTER_STANCE = "The claim over-reaches the cited finding."

# Input sniffing for mode="auto": a bare digit run is a PMID; a `10.xxxx/...` token is a DOI.
_PMID_RE = re.compile(r"^\d+$")
_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


# ============================================================================================
# Request → (mode, ClaimUnit)  — the `ingest` stage
# ============================================================================================
def _effective_mode(request: RunRequest) -> RunMode:
    """Resolve a concrete channel for the run, honouring an explicit ``mode`` and sniffing ``auto``.

    ``auto`` prefers an explicit ``paper_ref`` (numeric → pmid, ``10.x/…`` → doi), then a pasted
    ``citation_string``, then a bring-your-own ``manuscript_text``. Raises when nothing resolvable
    was supplied so the caller sees a clean ``error`` frame rather than a downstream crash.
    """
    if request.mode != "auto":
        return request.mode
    ref = (request.paper_ref or "").strip()
    if ref and _PMID_RE.match(ref):
        return "pmid"
    if ref and (_DOI_RE.match(ref) or ref.lower().startswith("10.")):
        return "doi"
    if (request.citation_string or "").strip():
        return "citation"
    if (request.manuscript_text or "").strip():
        return "manuscript"
    if ref:  # a bare, unclassifiable ref — treat as a PMID rather than guess a DOI
        return "pmid"
    raise ValueError(
        "cannot resolve run mode: supply a paper_ref (PMID/DOI) or a citation_string"
    )


def _ingest(request: RunRequest, mode: RunMode) -> ClaimUnit:
    """C1 — normalize the request's cited-paper channel into one :class:`ClaimUnit`.

    * ``pmid`` / ``doi`` build the identifier directly (offline; grounding does the NCBI fetch),
      exactly as ``slice_runner.run_slice`` does.
    * ``citation`` resolves a pasted reference via the public ``ingestion.ingest`` (a network
      round-trip to Crossref/NCBI), keeping the resolver's provenance on the unit.
    * ``manuscript`` (bring-your-own full text, no NCBI identifier) is a distinct grounding path not
      driven by this single-run runner — surfaced as a clean error rather than silently mishandled.
    """
    ref = (request.paper_ref or "").strip()
    if mode == "pmid":
        if not ref:
            raise ValueError("pmid mode requires a paper_ref")
        return ClaimUnit(atomic_claim=request.claim, cited_identifier=CitedIdentifier("pmid", ref))
    if mode == "doi":
        if not ref:
            raise ValueError("doi mode requires a paper_ref")
        return ClaimUnit(atomic_claim=request.claim,
                         cited_identifier=CitedIdentifier("doi", ref.lower()))
    if mode == "citation":
        cite = (request.citation_string or "").strip()
        if not cite:
            raise ValueError("citation mode requires a citation_string")
        from citeval.ingestion import ingest as _ci_ingest  # public API; only needed on this path
        units = _ci_ingest({"mode": "claim_citation", "claim_text": request.claim,
                            "citation_string": cite})
        if not units:
            raise ValueError(f"citation string did not resolve to a cited paper: {cite!r}")
        return units[0]
    raise ValueError(
        f"runner does not support mode {mode!r} (manuscript bring-your-own-text is a separate "
        "grounding path); supply a PMID/DOI paper_ref or a citation_string"
    )


# ============================================================================================
# Small pure helpers
# ============================================================================================
def _token_usage(raw: Optional[RawUsage]) -> Optional[TokenUsage]:
    """Project a role-tagged SDK :class:`RawUsage` onto the friendly four-tier wire shape
    (``cache_creation`` → ``cache_write``, ``cache_read_input`` → ``cache_read``)."""
    if raw is None:
        return None
    return TokenUsage(
        input=raw.input_tokens,
        output=raw.output_tokens,
        cache_read=raw.cache_read_input_tokens,
        cache_write=raw.cache_creation_input_tokens,
    )


def _running_agreement(grades: list[Optional[str]]) -> float:
    """Running exact-agreement (``a_exact``) over the ordinal grades seen so far: the modal grade's
    share of the graded rounds (mirrors the mock's ``modalCount / n`` and the final aggregate's
    ``a_exact`` definition). Non-ordinal rounds (NEI / N/A / unparsed) don't count toward it."""
    ordinal = [g for g in grades if g in _ORDINAL_SET]
    if not ordinal:
        return 0.0
    counts = Counter(ordinal)
    return round(max(counts.values()) / len(ordinal), 4)


def _grade_of(critic_round: Any) -> Optional[str]:
    """The round's ordinal grade from the critic's parsed dict (``on_round`` arg), or None."""
    if isinstance(critic_round, dict):
        g = critic_round.get("grade")
        if isinstance(g, str):
            return g
    return None


# ============================================================================================
# Injected client wrapper — emits `model_call` start/end around every triad call
# ============================================================================================
class _InstrumentedClient:
    """Wraps W1-TELEMETRY's :class:`TelemetryModelClient` to emit ``model_call`` SSE frames.

    ``adjudicate`` calls ``complete_with_usage`` (preferred) / ``complete`` (fallback) — and, once
    tool-use lands, ``create`` — once per role turn. This wrapper brackets each with a ``start``
    frame (before the call) and an ``end`` frame (after, carrying that call's four-tier usage +
    cost), then delegates to the telemetry client so usage is still captured for the run summary.

    Role is fingerprinted off the ``system`` kwarg (``telemetry.fingerprint_role``); the round is
    incremented on each **supporter** turn (always the first call of a triad), so it aligns 1-for-1
    with ``adjudicate``'s ``rounds_run`` and the ``debate_round`` frame for the same round. A critic
    resample (the pipeline's one-shot retry on a truncated critic) simply emits an extra
    critic ``model_call`` pair in the same round — honest, and harmless to the FE (keyed by
    role/round/phase).
    """

    def __init__(self, telemetry_client: TelemetryModelClient, publish, now_ms):
        self._tc = telemetry_client
        self._publish = publish              # publish(event_name, payload_model)
        self._now = now_ms                   # unused directly (publish stamps elapsed); kept for clarity
        self._round = 0
        self._last_usage: Optional[RawUsage] = None
        # Capture each call's usage as the telemetry client records it, so `end` frames can attach
        # it in O(1) (the wrapper owns this telemetry client, so replacing the hook is safe).
        telemetry_client.set_on_usage(self._capture)

    # -- telemetry capture (fires inside the delegated call, before the `end` frame) ---------
    def _capture(self, raw: RawUsage) -> None:
        self._last_usage = raw

    # -- bracketing ---------------------------------------------------------------------------
    def _before(self, kwargs: dict) -> tuple[Optional[Role], int]:
        role = fingerprint_role(kwargs.get("system"))
        if role == "supporter":
            self._round += 1
        if role is not None:
            self._publish("model_call", ModelCallData(role=role, round=self._round, phase="start"))
        return role, self._round

    def _after(self, role: Optional[Role], rnd: int) -> None:
        if role is None:
            return
        raw = self._last_usage
        self._publish("model_call", ModelCallData(
            role=role, round=rnd, phase="end",
            usage=_token_usage(raw),
            cost_usd=round(pricing.cost_of(raw), 6) if raw is not None else None,
        ))

    # -- the seam methods `adjudicate` may call (all transparently forwarded) -----------------
    def complete_with_usage(self, **kwargs: Any) -> tuple[str, Optional[int]]:
        role, rnd = self._before(kwargs)
        result = self._tc.complete_with_usage(**kwargs)
        self._after(role, rnd)
        return result

    def complete(self, **kwargs: Any) -> str:
        role, rnd = self._before(kwargs)
        result = self._tc.complete(**kwargs)
        self._after(role, rnd)
        return result

    def create(self, **kwargs: Any) -> Any:  # future tool-use loop calls this directly
        role, rnd = self._before(kwargs)
        result = self._tc.create(**kwargs)
        self._after(role, rnd)
        return result

    def summarize(self):
        return self._tc.summarize()


# ============================================================================================
# The synchronous run — publishes every frame to the bus and returns the RunResult
# ============================================================================================
def execute_run(
    request: RunRequest,
    *,
    run_id: str,
    bus: EventBus = BUS,
    client: Any = None,
    config: Optional[AdjudicationConfig] = None,
    benchmarks: Optional[Benchmarks] = None,
) -> RunResult:
    """Drive the whole pipeline synchronously, streaming SSE frames to ``bus`` for ``run_id``.

    Blocking (NCBI + the adversarial triad) — call it from a worker thread (see
    :func:`run_pipeline`). ``client`` is the raw Anthropic-style client injected into the telemetry
    wrapper (None → a live Opus 4.8 client is built lazily; tests pass an in-process fake).
    ``config`` is an optional :class:`AdjudicationConfig` (e.g. RB3 recalibration) whose ``on_round``
    is replaced by the streaming hook. ``benchmarks`` shares rolling ETA learning across runs.

    On any failure it emits a terminal ``error`` frame (tagged with the failing stage) and re-raises;
    the ``finally`` always seals the stream so every subscriber terminates cleanly.
    """
    t0 = time.monotonic()

    def now_ms() -> float:
        return (time.monotonic() - t0) * 1000.0

    def publish(event: str, payload: Any = None) -> None:
        bus.publish(run_id, event, payload, elapsed_ms=now_ms())

    estimator = ProgressEstimator(benchmarks)
    stage_span: dict[str, tuple[float, float]] = {}   # stage -> (start_ms, end_ms)
    last_est_total_ms = 0.0
    current_stage: Optional[Stage] = None
    telemetry_client: Optional[TelemetryModelClient] = None  # built inside the try (adjudicate stage)

    def stage_start(stage: Stage) -> None:
        nonlocal current_stage
        current_stage = stage
        s = now_ms()
        stage_span[stage] = (s, s)
        estimator.stage_start(stage, s)
        publish("stage_start", StageStartData(stage=stage))

    def stage_end(stage: Stage, summary: str, *, rounds_run: Optional[int] = None) -> None:
        nonlocal current_stage, last_est_total_ms
        e = now_ms()
        stage_span[stage] = (stage_span[stage][0], e)
        if stage == "adjudicate":
            estimator.stage_end(stage, e, rounds_run=rounds_run)
        else:
            estimator.stage_end(stage, e)
        publish("stage_end", StageEndData(stage=stage, summary=summary))
        snap = estimator.snapshot(e)
        last_est_total_ms = snap.est_total_ms
        publish("progress", snap)
        current_stage = None

    try:
        mode = _effective_mode(request)
        publish("run_start", RunStartData(mode=mode, paper_ref=request.paper_ref))

        # 1) ingest — resolve the cited-paper channel into a ClaimUnit.
        stage_start("ingest")
        unit = _ingest(request, mode)
        ci = unit.cited_identifier
        stage_end("ingest", f"Resolved cited paper {ci.type.upper()} {ci.value}.")

        # 2) ground_retraction — metadata-ground the cited paper (Retraction Watch/NCBI + MeSH tags,
        #    budgeted full text). This is the expensive external-grounding call; the objective
        #    retraction + scope axes read the record it returns.
        stage_start("ground_retraction")
        g = ground(ci, with_full_text=True)
        r = g.retraction
        stage_end(
            "ground_retraction",
            f"Retraction {r.status} (source agreement: {r.source_agreement}); grounded "
            f"{len(g.organism_tags)} organism / {len(g.population_tags)} population MeSH tag(s).",
        )

        # 3) ground_scope — parse the CLAIM's asserted scope (organism/population/direction). Cheap,
        #    offline; feeds the species/population scope axes + the refuter's direction probe.
        stage_start("ground_scope")
        scope = parse_claim_scope(unit.atomic_claim)
        stage_end(
            "ground_scope",
            f"Claim scope: organism {scope.organism or '(unscoped)'}, direction "
            f"{scope.direction or '(none)'} (tier {scope.tier}).",
        )

        # 4) adjudicate — adversarial self-consistency triad on Opus 4.8. Inject the instrumented
        #    telemetry client + the streaming on_round hook.
        stage_start("adjudicate")
        # Build the telemetry client here, INSIDE the try: on the live path (client=None) its
        # constructor builds a real Anthropic client, which can raise with no key. Constructing it
        # here means such a failure surfaces as an `error` frame tagged `adjudicate` and the
        # `finally` still seals the stream — never a silently unsealed run that hangs subscribers.
        telemetry_client = TelemetryModelClient(client=client)
        round_grades: list[Optional[str]] = []
        prev_cost_usd = 0.0

        def on_round(round_index: int, critic_round: Any, critic_out_tok: Optional[int]) -> None:
            """Turn one self-consistency round into debate_round + cost_update + progress. Runs on
            the same worker thread as `adjudicate`; the bus makes the cross-thread publish safe."""
            nonlocal prev_cost_usd
            e = now_ms()
            grade = _grade_of(critic_round)
            round_grades.append(grade)
            estimator.round_completed(e, round_index=round_index)
            publish("debate_round", DebateRoundData(
                round=round_index,
                supporter_stance=_SUPPORTER_STANCE,
                refuter_stance=_REFUTER_STANCE,
                critic_grade=grade if grade is not None else "(unparsed)",
                agreement=_running_agreement(round_grades),
            ))
            summ = telemetry_client.summarize()
            publish("cost_update", CostUpdateData(
                cumulative_usd=summ.total_usd,
                delta_usd=round(summ.total_usd - prev_cost_usd, 6),
                tokens=summ.tokens,
            ))
            prev_cost_usd = summ.total_usd
            publish("progress", estimator.snapshot(e))

        instrumented = _InstrumentedClient(telemetry_client, publish, now_ms)
        cfg = replace(config, on_round=on_round) if config is not None \
            else AdjudicationConfig(on_round=on_round)
        verdict = adjudicate(g, scope, claim_text=unit.atomic_claim,
                             client=instrumented, config=cfg)
        rounds_run = len(round_grades)
        stage_end("adjudicate", verdict.overall, rounds_run=rounds_run or None)

        # 5) report — render the verbatim JSON verdict + the standalone HTML document.
        stage_start("report")
        verdict_json = render_json(unit, g, scope, verdict)
        report_html = render_html(unit, g, scope, verdict)
        stage_end("report", "Rendered verdict JSON + HTML report.")

        # Assemble the RunResult and finish.
        total_ms = now_ms()
        estimator.run_complete(total_ms)
        per_stage_ms = {s: round(span[1] - span[0], 1) for s, span in stage_span.items()}
        result = RunResult(
            run_id=run_id,
            verdict=verdict_json,
            timing=RunTiming(
                per_stage_ms=per_stage_ms,
                total_ms=round(total_ms, 1),
                est_total_ms=round(last_est_total_ms or total_ms, 1),
            ),
            cost=telemetry_client.summarize(),
            report_html=report_html,
        )
        publish("run_complete", RunCompleteData(result=result))
        return result
    except Exception as exc:  # noqa: BLE001 — surface as a terminal error frame, then re-raise
        publish("error", ErrorData(stage=current_stage,
                                   message=f"{type(exc).__name__}: {exc}"))
        raise
    finally:
        bus.close(run_id)


# ============================================================================================
# Async entry — offload the blocking run to a worker thread
# ============================================================================================
async def run_pipeline(
    request: RunRequest,
    *,
    run_id: str,
    bus: EventBus = BUS,
    client: Any = None,
    config: Optional[AdjudicationConfig] = None,
    benchmarks: Optional[Benchmarks] = None,
) -> RunResult:
    """Async wrapper over :func:`execute_run`: runs the blocking pipeline in a worker thread so the
    event loop stays free to stream the run's SSE frames to subscribers (the bus wakes each
    subscriber on its own loop from the worker thread). Returns the final :class:`RunResult`;
    re-raises any pipeline error after its terminal ``error`` frame has been published and the
    stream sealed."""
    return await asyncio.to_thread(
        execute_run, request,
        run_id=run_id, bus=bus, client=client, config=config, benchmarks=benchmarks,
    )
