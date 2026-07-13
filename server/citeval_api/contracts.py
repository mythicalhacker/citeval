"""FROZEN wire contracts for the citeval HTTP/SSE API (W0-CONTRACTS).

These Pydantic models are the *single source of truth* every other sprint session codes
against — the FastAPI app (W2-SERVER), the runner/batch (W2-RUNNER/BATCH), telemetry
(W1-TELEMETRY), events (W1-EVENTS), and — mirrored 1:1 — the TypeScript types in
``web/src/lib/types.ts`` and the prose in ``docs/api_contract.md``. If a shape changes here
it changes in all four places, and that is a manager decision (see api_contract.md §Change
control).

Design rules:
- **Pure types only.** No I/O, no business logic, no imports from ``citeval`` or ``fastapi``.
  Importing this module must never need a network, a key, or a heavy dep.
- **``RunResult.verdict`` is deliberately an open ``dict``**, NOT a re-typed model. It carries
  the *verbatim* output of ``citeval.reporting.render_json`` — ``{claim_unit, grounded,
  claim_scope, verdict}`` — whose sub-shapes live in the FROZEN ``citeval.contracts`` and must
  not be forked here. Re-declaring them would create a second, drifting source of truth. The
  canonical example lives in ``data/schemas/run_result.json``; the field-by-field description
  is in ``docs/api_contract.md`` §RunResult.verdict.
- Token accounting has **two shapes on purpose**: :class:`RawUsage` mirrors the Anthropic SDK's
  ``response.usage`` verbatim (what ``pricing.cost_of`` consumes); :class:`TokenUsage` is the
  friendlier four-tier roll-up that rides on ``cost_update`` and :class:`TelemetrySummary`.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ============================================================================================
# Enumerations (kept as Literals so they serialize as plain strings and mirror cleanly to TS)
# ============================================================================================
# How the cited paper was supplied on a single run. `auto` = let the server sniff the input.
RunMode = Literal["pmid", "doi", "citation", "manuscript", "auto"]

# The five pipeline stages, in canonical order. Progress/ETA and the stepper depend on this order.
Stage = Literal["ingest", "ground_retraction", "ground_scope", "adjudicate", "report"]

# The three adversarial debate roles (all Opus 4.8 — CLAUDE.md invariant #4).
Role = Literal["supporter", "refuter", "critic"]

# A model_call brackets one role turn: `start` before the call, `end` after (usage attached).
Phase = Literal["start", "end"]

# Per-item lifecycle state inside a batch grid.
ItemStatus = Literal["queued", "running", "done", "error"]


# ============================================================================================
# REST request bodies
# ============================================================================================
class RunRequest(BaseModel):
    """POST /api/runs body. Exactly one of `paper_ref` / `citation_string` / `manuscript_text`
    is the source of the cited paper; `mode` records (or forces) which channel was used."""
    claim: str
    paper_ref: Optional[str] = None        # a PMID ("22088800") or DOI ("10.1016/...") to resolve
    citation_string: Optional[str] = None  # a pasted free-text reference to parse into an identifier
    manuscript_text: Optional[str] = None  # bring-your-own full text (no NCBI lookup)
    mode: RunMode = "auto"


class BatchItem(BaseModel):
    claim: str
    paper_ref: Optional[str] = None


class BatchRequest(BaseModel):
    """POST /api/batch body — N citations verified concurrently."""
    items: list[BatchItem] = Field(default_factory=list)


class RunCreated(BaseModel):
    """POST /api/runs response."""
    run_id: str


class BatchCreated(BaseModel):
    """POST /api/batch response."""
    batch_id: str


class Health(BaseModel):
    """GET /api/health response."""
    status: Literal["ok"] = "ok"


# ============================================================================================
# Cost / telemetry
# ============================================================================================
class RawUsage(BaseModel):
    """Mirrors the Anthropic SDK `response.usage` verbatim (the shape `pricing.cost_of`
    consumes). `role` is stamped by W1-TELEMETRY's client after fingerprinting the system
    prompt; it is NOT part of the SDK object but rides along so `summarize()` can bucket by role.
    Unknown/absent tiers default to 0 so a partial usage object never crashes costing."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    role: Optional[Role] = None


class TokenUsage(BaseModel):
    """Friendly four-tier roll-up used on `cost_update` and inside :class:`TelemetrySummary`.
    (Distinct from :class:`RawUsage`: this is `cache_write`, the SDK is `cache_creation`.)"""
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0


class RoleCost(BaseModel):
    """Per-role slice of a :class:`TelemetrySummary`."""
    usd: float = 0.0
    n_calls: int = 0
    tokens: TokenUsage = Field(default_factory=TokenUsage)


class TelemetrySummary(BaseModel):
    """Return type of `pricing.summarize(...)` and the `cost` field of a :class:`RunResult`."""
    total_usd: float = 0.0
    per_role: dict[str, RoleCost] = Field(default_factory=dict)
    tokens: TokenUsage = Field(default_factory=TokenUsage)
    n_model_calls: int = 0


class PricingInfo(BaseModel):
    """GET /api/pricing response — the `PRICING` table (USD per MILLION tokens). Values are
    illustrative Opus-class placeholders; see pricing.py's CONFIRM comment."""
    input: float
    output: float
    cache_write: float
    cache_read: float
    unit: Literal["usd_per_million_tokens"] = "usd_per_million_tokens"
    note: str = ""


# ============================================================================================
# Run result (wraps the frozen citeval render_json — see module docstring)
# ============================================================================================
class RunTiming(BaseModel):
    per_stage_ms: dict[str, float] = Field(default_factory=dict)   # keyed by Stage
    total_ms: float = 0.0
    est_total_ms: float = 0.0


class RunResult(BaseModel):
    """GET /api/runs/{id} response and the payload of `run_complete`.

    `verdict` is the verbatim `citeval.reporting.render_json` dict (open shape on purpose —
    see module docstring). `report_html` is the verbatim `citeval.reporting.render_html` doc."""
    run_id: str
    verdict: dict[str, Any]
    timing: RunTiming = Field(default_factory=RunTiming)
    cost: TelemetrySummary = Field(default_factory=TelemetrySummary)
    report_html: str = ""


class BatchAggregate(BaseModel):
    """`p_r_f` (precision/recall/f1) is present only when the batch items carry gold labels;
    otherwise it stays None and the dashboard hides the P/R/F header."""
    p_r_f: Optional[dict[str, float]] = None
    total_cost_usd: float = 0.0
    total_ms: float = 0.0
    n: int = 0


class BatchResult(BaseModel):
    """GET /api/batch/{id} response and the payload of `batch_complete`."""
    batch_id: str
    items: list[RunResult] = Field(default_factory=list)
    aggregate: BatchAggregate = Field(default_factory=BatchAggregate)


# ============================================================================================
# SSE — envelope + one model per event `data`
# ============================================================================================
class SSEEnvelope(BaseModel):
    """Wraps every SSE frame. The transport puts `event:` = the event name and `data:` = the
    event model below; `run_id/seq/ts/elapsed_ms` are merged into `data` alongside the event
    fields (see api_contract.md §SSE framing). `seq` is monotonic per stream (gap-free), so a
    late/replayed subscriber can order and de-dup."""
    run_id: str
    seq: int
    ts: float          # epoch seconds (float)
    elapsed_ms: float  # ms since run_start


# ---- run-stream events ---------------------------------------------------------------------
class RunStartData(BaseModel):
    mode: RunMode
    paper_ref: Optional[str] = None


class StageStartData(BaseModel):
    stage: Stage


class StageEndData(BaseModel):
    stage: Stage
    summary: str = ""


class ModelCallData(BaseModel):
    """Brackets a single role turn. `usage`/`cost_usd` are populated on `phase="end"` only."""
    role: Role
    round: int
    phase: Phase
    usage: Optional[TokenUsage] = None
    cost_usd: Optional[float] = None


class DebateRoundData(BaseModel):
    """One self-consistency round, emitted from `config.on_round`. `agreement` is the running
    exact-agreement (a_exact) after this round; `critic_grade` is this round's ordinal grade."""
    round: int
    supporter_stance: str
    refuter_stance: str
    critic_grade: str
    agreement: float


class CostUpdateData(BaseModel):
    cumulative_usd: float
    delta_usd: float
    tokens: TokenUsage


class ProgressData(BaseModel):
    pct: float             # 0..100
    est_total_ms: float
    est_remaining_ms: float


class RunCompleteData(BaseModel):
    result: RunResult


class ErrorData(BaseModel):
    stage: Optional[Stage] = None
    message: str


# ---- batch-stream events -------------------------------------------------------------------
class BatchStartData(BaseModel):
    n: int


class ItemUpdateData(BaseModel):
    index: int
    run_id: str
    status: ItemStatus


class BatchProgressData(BaseModel):
    done: int
    total: int
    cost_usd: float
    elapsed_ms: float


class BatchCompleteData(BaseModel):
    result: BatchResult


# ---- name → payload registry (documentation + validation aid) ------------------------------
# The authoritative map of SSE event name → its `data` payload model. W2-SERVER/RUNNER emit
# these; the mock and any validator can look a name up here. Envelope fields are added on top.
SSE_EVENT_MODELS: dict[str, type[BaseModel]] = {
    "run_start": RunStartData,
    "stage_start": StageStartData,
    "stage_end": StageEndData,
    "model_call": ModelCallData,
    "debate_round": DebateRoundData,
    "cost_update": CostUpdateData,
    "progress": ProgressData,
    "run_complete": RunCompleteData,
    "error": ErrorData,
    # batch
    "batch_start": BatchStartData,
    "item_update": ItemUpdateData,
    "batch_progress": BatchProgressData,
    "batch_complete": BatchCompleteData,
}

RUN_EVENT_ORDER: tuple[str, ...] = (
    "run_start", "stage_start", "model_call", "debate_round", "cost_update",
    "progress", "stage_end", "run_complete", "error",
)

__all__ = [
    "RunMode", "Stage", "Role", "Phase", "ItemStatus",
    "RunRequest", "BatchItem", "BatchRequest", "RunCreated", "BatchCreated", "Health",
    "RawUsage", "TokenUsage", "RoleCost", "TelemetrySummary", "PricingInfo",
    "RunTiming", "RunResult", "BatchAggregate", "BatchResult",
    "SSEEnvelope",
    "RunStartData", "StageStartData", "StageEndData", "ModelCallData", "DebateRoundData",
    "CostUpdateData", "ProgressData", "RunCompleteData", "ErrorData",
    "BatchStartData", "ItemUpdateData", "BatchProgressData", "BatchCompleteData",
    "SSE_EVENT_MODELS", "RUN_EVENT_ORDER",
]
