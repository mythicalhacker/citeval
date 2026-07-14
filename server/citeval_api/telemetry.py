"""Telemetry-capturing model client for the citeval API (W1-TELEMETRY).

:class:`TelemetryModelClient` is a **read-only wrapper** around the real Anthropic client that
plugs into citeval's injected-client seam (`adjudicate(..., client=)` in
``src/citeval/adjudicator.py``) and, on every model call, records what it cost.

Why a wrapper instead of the pipeline's own ``AnthropicModelClient``:
- The adjudicator's default client throws the SDK ``response.usage`` away after reading
  ``output_tokens``. The server's live cost meter needs the **full** four-tier usage
  (input / output / cache-creation / cache-read) per call, bucketed by debate role.
- W1-CORE-ADJ is about to add **tool-use** to the pipeline (a multi-turn ``messages`` +
  ``tools`` loop). So this client forwards **all** completion kwargs transparently to
  ``messages.create`` — ``messages``/``system``/``model``/``max_tokens`` and, when present,
  ``tools``/``tool_choice``/``thinking`` — rather than hard-coding the current
  ``system``+``user`` signature. It keeps working when the seam grows.

Seam compatibility (see ``adjudicator._complete``): the pipeline prefers
``complete_with_usage(*, model, system, user, max_tokens, temperature) -> (text, output_tokens)``
and falls back to ``complete(...) -> str``. Both are implemented here on top of the lower-level
:meth:`TelemetryModelClient.create`, which is the method a future tool-use loop calls directly to
get the raw SDK response back.

Design rules (mirrors the package's read-only stance): this module imports ``citeval`` and
``citeval_api.{contracts,pricing}`` **read-only** and never edits ``src/citeval/*``. Prompt
caching is preserved by reusing the adjudicator's own content-block / cache-control splitter
(``_content_blocks``) verbatim, so the ~6k-token evidence prefix stays cached across a case's
triad calls.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from typing import Any, Optional

# --- citeval (read-only) --------------------------------------------------------------------
# `_content_blocks` is the adjudicator's user-turn splitter (cache_control breakpoint on the
# reusable evidence prefix). We REUSE it verbatim so this wrapper caches exactly like the
# pipeline's own client — a single source of truth for the cache boundary. `OPUS_MODEL` is the
# CLAUDE.md invariant-#4 model id, used only as a fallback default; the seam always passes it.
# Importing these is pure/offline (the SDK is constructed lazily, never at import time). We import
# rather than reimplement `_content_blocks`: a private local copy could silently drift from the
# adjudicator's real cache boundary and quietly break cache hits (a cost regression no test would
# catch). W1-CORE-ADJ is slated to modify adjudicator.py; if it moves this private symbol the import
# fails LOUDLY at import time (caught by the server tests) — which is the safe failure mode.
from citeval.adjudicator import OPUS_MODEL, _content_blocks
from citeval.prompts import critic, refuter, supporter

from . import pricing
from .contracts import RawUsage, Role, TelemetrySummary

__all__ = ["TelemetryModelClient", "UsageHook", "fingerprint_role", "OPUS_MODEL"]

_LOG = logging.getLogger(__name__)

# A per-call streaming hook: receives the role-tagged :class:`RawUsage` right after it is logged.
UsageHook = Callable[[RawUsage], None]

_WS = re.compile(r"\s+")

# ============================================================================================
# Debate-role fingerprinting — tag each call by matching its system prompt to a role.
# ============================================================================================
# The three adversarial roles' SYSTEM prompts (RB2 wording lives in `citeval.prompts`; we only
# READ them). We fingerprint the `system` kwarg against these so `summarize()` can bucket cost by
# role, and W1-EVENTS can label a `model_call` without the pipeline having to tell us the role.
_ROLE_SYSTEMS: dict[Role, str] = {
    "supporter": supporter.SYSTEM,
    "refuter": refuter.SYSTEM,
    "critic": critic.SYSTEM,
}
# Whitespace-normalized, lower-cased reference text per role (matched robustly below).
_ROLE_NORMS: dict[Role, str] = {r: _WS.sub(" ", s).strip().lower() for r, s in _ROLE_SYSTEMS.items()}
# Each role prompt's distinctive opening sentence ("You are the SUPPORTER in an adversarial
# scientific-citation adjudication") — derived from the imported SYSTEM, not hardcoded. It carries
# the role word, so it is unique per role and stable if W1-CORE-ADJ appends tool-use instructions
# to a SYSTEM (the opening is preserved). This — not blind substring containment — is the anchor:
# a bare word like "random" must NOT match the critic just because its prompt says
# "order-randomized".
_ROLE_SIGNATURES: dict[Role, str] = {
    r: _WS.sub(" ", s.split(".", 1)[0]).strip().lower() for r, s in _ROLE_SYSTEMS.items()
}


def _system_text(system: Any) -> str:
    """Flatten a `system` kwarg to plain text for fingerprinting.

    `system` is a str in the current seam, but the SDK also accepts a list of content blocks
    (dicts or objects with a `.text`, possibly cache-marked). We concatenate the text of every
    block so a cached/structured system prompt still fingerprints. Anything else -> "".
    """
    if isinstance(system, str):
        return system
    if isinstance(system, (list, tuple)):
        parts: list[str] = []
        for block in system:
            if isinstance(block, dict):
                t = block.get("text")
            else:
                t = getattr(block, "text", None)
            if isinstance(t, str):
                parts.append(t)
        return "".join(parts)
    return ""


def fingerprint_role(system: Any) -> Optional[Role]:
    """Tag a call's debate role by matching its system prompt against the three role SYSTEMs.

    Robust to the seam evolving, without over-matching: an exact (normalized, case-insensitive)
    match wins first; then a full-reference containment (so a SYSTEM with appended tool-use
    instructions still matches); finally the role's distinctive opening SIGNATURE ("You are the
    ROLE in an adversarial scientific-citation adjudication"), which survives truncation and
    carries the role word. Matching is anchored on that signature rather than blind substring
    containment, so an unrelated short string never accidentally lands on a role. Returns None for
    a non-debate call (e.g. ingestion) so pricing buckets it as "unknown".
    """
    norm = _WS.sub(" ", _system_text(system)).strip().lower()
    if not norm:
        return None
    for role, ref in _ROLE_NORMS.items():
        if norm == ref or ref in norm:
            return role
    for role, sig in _ROLE_SIGNATURES.items():
        if sig and sig in norm:
            return role
    return None


# ============================================================================================
# Usage extraction — tolerant read of the SDK `response.usage` into a RawUsage.
# ============================================================================================
# The SDK usage fields we capture — the SINGLE source of truth for `_raw_usage` below (which
# iterates this tuple), so adding a tier here actually changes capture. Names must match both the
# SDK `response.usage` attributes and RawUsage's fields (contracts.RawUsage), which line up 1:1.
_USAGE_FIELDS: tuple[str, ...] = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def _read_int(carrier: Any, name: str) -> int:
    """Read one token tier off any usage carrier (SDK object attr / dict / model), coercing to a
    non-negative int. Absent / None / garbage -> 0 (mirrors `pricing._get`: a partial usage object
    never crashes capture, and a negative count can never credit the bill)."""
    if carrier is None:
        return 0
    val = carrier.get(name, 0) if isinstance(carrier, dict) else getattr(carrier, name, 0)
    try:
        n = int(val or 0)
    except (TypeError, ValueError):
        return 0
    return n if n > 0 else 0


def _raw_usage(usage: Any, role: Optional[Role]) -> RawUsage:
    """Project an SDK `response.usage` (or dict) onto a role-tagged :class:`RawUsage`.

    Captures every tier in `_USAGE_FIELDS` verbatim (that tuple is the single source of truth); a
    response with no usage (some mocks) yields an all-zero, role-tagged record so a call is still
    counted (at zero cost)."""
    tiers = {field: _read_int(usage, field) for field in _USAGE_FIELDS}
    return RawUsage(role=role, **tiers)


def _iter_content(resp: Any) -> Iterable[Any]:
    content = getattr(resp, "content", None)
    if isinstance(content, dict):  # defensive: a single block, not a list
        return [content]
    return content or []


def _extract_text(resp: Any) -> str:
    """Concatenate the `text` of every text block on a Message response.

    Tolerant of dict- or object-shaped blocks (real SDK is objects; mocks may use dicts). Non-text
    blocks (e.g. a `tool_use` block from a tool-use turn) are skipped — the tool-use loop reads
    those off the raw response returned by :meth:`create`, not off this text seam.
    """
    parts: list[str] = []
    for block in _iter_content(resp):
        if isinstance(block, dict):
            btype, text = block.get("type"), block.get("text")
        else:
            btype, text = getattr(block, "type", None), getattr(block, "text", None)
        if btype == "text" and isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def _output_tokens(resp: Any) -> Optional[int]:
    """SDK-reported `usage.output_tokens` (None when the response carries no usage) — the value the
    adjudicator's cap-from-data pass reads back through the `complete_with_usage` seam."""
    usage = getattr(resp, "usage", None)
    if usage is None:
        return None
    val = usage.get("output_tokens") if isinstance(usage, dict) else getattr(usage, "output_tokens", None)
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


# ============================================================================================
# The client
# ============================================================================================
class TelemetryModelClient:
    """Wraps the real Anthropic client, records per-call usage, and implements citeval's
    injected-client completion seam.

    Construct one **per run** (the log is per-run) and inject it:
    ``adjudicate(g, scope, claim, client=TelemetryModelClient())``. Read the cost back with
    :meth:`summarize`; stream a live meter by passing an ``on_usage`` hook.

    Parameters
    ----------
    client:
        The wrapped Anthropic client — anything exposing ``.messages.create(**kwargs)``. When
        None, a live ``anthropic.Anthropic()`` is constructed **lazily** (only then is a key /
        network needed), so importing this module and injecting a mock stay offline.
    on_usage:
        Optional per-call hook, invoked with the role-tagged :class:`RawUsage` right after it is
        appended to the log. Price it with ``pricing.cost_of(usage)``; the four-tier
        :class:`~citeval_api.contracts.TokenUsage` projection is one call away. A raising hook is
        swallowed — telemetry must never crash a (paid) model call.
    """

    def __init__(self, client: Any = None, *, on_usage: Optional[UsageHook] = None) -> None:
        if client is None:
            import anthropic  # lazy: only touched when a live run actually needs the SDK
            client = anthropic.Anthropic()
        self._client = client
        self._on_usage = on_usage
        self._log: list[RawUsage] = []

    # -- streaming hook ---------------------------------------------------------------------
    @property
    def on_usage(self) -> Optional[UsageHook]:
        return self._on_usage

    @on_usage.setter
    def on_usage(self, hook: Optional[UsageHook]) -> None:
        self._on_usage = hook

    def set_on_usage(self, hook: Optional[UsageHook]) -> None:
        """Set (or clear, with None) the per-call usage hook."""
        self._on_usage = hook

    # -- the per-run log --------------------------------------------------------------------
    @property
    def usages(self) -> list[RawUsage]:
        """The per-run usage log — one role-tagged :class:`RawUsage` per model call, in call order.

        Returns per-entry copies (RawUsage is a mutable pydantic model): mutating the returned list
        OR any entry in it cannot corrupt the client's own log — a later :meth:`summarize` prices
        the untouched originals."""
        return [u.model_copy() for u in self._log]

    # Back-compat alias for callers that reach for `.log`.
    log = usages

    def reset(self) -> None:
        """Clear the per-run log (reuse the wrapper for a fresh run)."""
        self._log = []

    # -- the wrapped completion method (the transparent forward) ----------------------------
    def create(self, **kwargs: Any) -> Any:
        """Forward a completion to ``messages.create`` transparently, record its usage, and return
        the **raw SDK response**.

        This is the future-proof core: every kwarg is passed through unchanged —
        ``messages``/``system``/``model``/``max_tokens`` and, when present,
        ``tools``/``tool_choice``/``thinking`` (and anything else W1-CORE-ADJ adds) — so a
        tool-use turn works with no change here. Two adaptations keep the *current* seam working:

        - ``user=<str>`` (the pipeline's text seam) is converted to
          ``messages=[{"role": "user", "content": _content_blocks(user)}]`` using the adjudicator's
          own cache-control splitter, so prompt caching is preserved. If ``messages`` is already
          supplied (tool-use path), ``user`` is ignored in favour of it.
        - ``temperature`` is dropped, never sent — claude-opus-4-8 deprecated it, exactly as the
          pipeline's own ``AnthropicModelClient`` does; keeping it on the interface lets the seam
          call unchanged.

        Any remaining None-valued kwarg (``tools``/``tool_choice``/``thinking``/``system``/
        ``messages``/a future optional) is dropped rather than sent as an explicit null, so we
        forward only what the caller actually set; ``model`` is normalized to the invariant Opus id
        FIRST so a ``model=None`` still resolves to Opus rather than being dropped or sent as null.
        """
        call_kwargs = dict(kwargs)
        # Role is fingerprinted off the ORIGINAL system, before any None-dropping below.
        role = fingerprint_role(call_kwargs.get("system"))

        call_kwargs.pop("temperature", None)  # deprecated on opus-4-8; mirror AnthropicModelClient
        user = call_kwargs.pop("user", None)
        if user is not None and call_kwargs.get("messages") is None:
            call_kwargs["messages"] = [{"role": "user", "content": _content_blocks(user)}]
        # Invariant #4 fallback. `setdefault` would NOT replace an explicit `model=None` (the key
        # exists), so normalize it before the None-drop below — else a caller-built `model=None`
        # would be dropped and the SDK would 400 on a missing model.
        if call_kwargs.get("model") is None:
            call_kwargs["model"] = OPUS_MODEL
        # Forward only kwargs the caller actually set: drop every remaining None-valued optional so
        # we never send a spurious explicit null. `model` is normalized above; `max_tokens` is
        # required, so a None there surfaces loudly at the SDK rather than being masked.
        call_kwargs = {k: v for k, v in call_kwargs.items() if v is not None}

        resp = self._client.messages.create(**call_kwargs)
        self._record(getattr(resp, "usage", None), role)
        return resp

    def complete_with_usage(self, **kwargs: Any) -> tuple[str, Optional[int]]:
        """citeval's preferred seam: one turn -> ``(text, output_tokens)``.

        Accepts the pipeline's keyword call
        (``model, system, user, max_tokens, temperature``) and transparently forwards any extra
        kwargs (``tools`` / ``tool_choice`` / ``thinking`` / ``messages`` / ...) via
        :meth:`create`. ``output_tokens`` is the SDK ``usage.output_tokens`` (None if absent)."""
        resp = self.create(**kwargs)
        return _extract_text(resp), _output_tokens(resp)

    def complete(self, **kwargs: Any) -> str:
        """Back-compat text-only seam (``-> str``), delegating to :meth:`complete_with_usage`."""
        text, _ = self.complete_with_usage(**kwargs)
        return text

    # -- costing ----------------------------------------------------------------------------
    def summarize(self) -> TelemetrySummary:
        """Roll the per-run log into a :class:`TelemetrySummary` via ``pricing`` (which prices each
        entry with :func:`pricing.cost_of` and buckets by the role tag)."""
        return pricing.summarize(self._log)

    # -- internal ---------------------------------------------------------------------------
    def _record(self, usage: Any, role: Optional[Role]) -> None:
        """Capture one call's full usage (role-tagged), append it to the log, and fire the hook."""
        raw = _raw_usage(usage, role)
        self._log.append(raw)  # appended BEFORE the hook fires, so an in-hook read of `usages`/
        #                        `summarize()` already sees this call.
        if self._on_usage is not None:
            try:
                self._on_usage(raw)
            except Exception:  # noqa: BLE001 — a telemetry hook must never crash a (paid) model call
                # Still swallowed (usage is safely logged regardless), but surfaced once so a
                # persistently broken hook — e.g. a downed SSE/cost-meter bus — is not an invisible
                # dead stream for the whole run.
                _LOG.warning("on_usage hook raised; usage still logged", exc_info=True)
