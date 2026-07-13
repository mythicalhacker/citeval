"""Cost model for the citeval API (W0-CONTRACTS).

`PRICING` is the per-million-token rate card; `cost_of(usage)` prices one Anthropic
`response.usage`; `summarize(usages)` rolls a run's usages into a :class:`TelemetrySummary`.

Costing is intentionally pure and dependency-light: it reads token counts off *whatever* usage
object it is handed — the live Anthropic SDK's `response.usage` (attribute access), a plain
dict, or a :class:`~server.citeval_api.contracts.RawUsage` — so W1-TELEMETRY can forward the
SDK object verbatim (CLAUDE.md-style: no re-typing at the seam). Missing tiers price as 0.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .contracts import RoleCost, TelemetrySummary, TokenUsage

# ============================================================================================
# PRICING — USD per MILLION tokens, four tiers.
#
# ⚠️ CONFIRM against current Anthropic pricing before any cost is shown as authoritative.
# These are ILLUSTRATIVE Opus-class placeholders (per the sprint contract), NOT a quote. They
# exist so the live cost meter renders a plausible number end-to-end; the manager swaps in the
# confirmed rate card in Wave 3. Keep the four keys stable — telemetry + the UI key off them.
# ============================================================================================
PRICING: dict[str, float] = {
    "input": 15.0,        # CONFIRM — $/1M input tokens
    "output": 75.0,       # CONFIRM — $/1M output tokens
    "cache_write": 18.75,  # CONFIRM — $/1M cache-creation (write) tokens
    "cache_read": 1.50,   # CONFIRM — $/1M cache-read (hit) tokens
}
PRICING_UNIT = "usd_per_million_tokens"
PRICING_NOTE = ("Illustrative Opus-class placeholders — CONFIRM against current Anthropic "
                "pricing before treating any dollar figure as authoritative.")

_MILLION = 1_000_000.0

# Map SDK/dict usage field  ->  the PRICING tier it is billed at.
_TIER_FIELDS: tuple[tuple[str, str], ...] = (
    ("input_tokens", "input"),
    ("output_tokens", "output"),
    ("cache_creation_input_tokens", "cache_write"),
    ("cache_read_input_tokens", "cache_read"),
)


def _get(usage: Any, name: str) -> int:
    """Read one token tier off any usage carrier (SDK object attr, dict key, or model),
    coercing to a non-negative int. Absent/None/garbage -> 0 (a partial usage never crashes
    costing, and a negative count can never credit the bill)."""
    if usage is None:
        return 0
    val = usage.get(name, 0) if isinstance(usage, dict) else getattr(usage, name, 0)
    try:
        n = int(val or 0)
    except (TypeError, ValueError):
        return 0
    return n if n > 0 else 0


def cost_of(usage: Any) -> float:
    """Price a single Anthropic `response.usage` (or dict / :class:`RawUsage`) in USD.

    cost = Σ tier_tokens × PRICING[tier] / 1e6, over input/output/cache_write/cache_read.
    """
    total = 0.0
    for field, tier in _TIER_FIELDS:
        total += _get(usage, field) * PRICING[tier]
    return total / _MILLION


def _role_of(usage: Any) -> str:
    """The debate role tagged onto a usage by W1-TELEMETRY (`usage.role` / `usage["role"]`);
    falls back to "unknown" so an untagged call is still counted, just not per-role."""
    role = usage.get("role") if isinstance(usage, dict) else getattr(usage, "role", None)
    return role or "unknown"


def _tokens_of(usage: Any) -> TokenUsage:
    """Project a raw usage onto the friendly four-tier :class:`TokenUsage` roll-up shape."""
    return TokenUsage(
        input=_get(usage, "input_tokens"),
        output=_get(usage, "output_tokens"),
        cache_write=_get(usage, "cache_creation_input_tokens"),
        cache_read=_get(usage, "cache_read_input_tokens"),
    )


def _add_tokens(dst: TokenUsage, src: TokenUsage) -> None:
    dst.input += src.input
    dst.output += src.output
    dst.cache_read += src.cache_read
    dst.cache_write += src.cache_write


def summarize(usages: Iterable[Any]) -> TelemetrySummary:
    """Roll a run's per-call usages into a :class:`TelemetrySummary`.

    Each element is any usage carrier `cost_of` accepts, optionally role-tagged (`.role`) so the
    per-role breakdown is populated. Order-independent and side-effect-free on the inputs.
    """
    summary = TelemetrySummary()
    for usage in usages:
        cost = cost_of(usage)
        toks = _tokens_of(usage)
        role = _role_of(usage)

        summary.total_usd += cost
        summary.n_model_calls += 1
        _add_tokens(summary.tokens, toks)

        bucket = summary.per_role.get(role)
        if bucket is None:
            bucket = RoleCost()
            summary.per_role[role] = bucket
        bucket.usd += cost
        bucket.n_calls += 1
        _add_tokens(bucket.tokens, toks)

    # Round dollar figures to whole cents-of-a-milli so equality tests + the UI stay stable;
    # token counts stay exact.
    summary.total_usd = round(summary.total_usd, 6)
    for bucket in summary.per_role.values():
        bucket.usd = round(bucket.usd, 6)
    return summary


__all__ = ["PRICING", "PRICING_UNIT", "PRICING_NOTE", "cost_of", "summarize"]
