"""C4 — adversarial adjudicator (mock-first scaffold).

`adjudicate(grounded, scope, claim_text="") -> Verdict` is a drop-in replacement for
`adjudicator_stub.adjudicate_stub` at the runner seam. It runs an adversarial
**supporter → refuter → critic** pipeline (all **Opus 4.8**) that produces the graded
`substantive_support` axis with a confidence tier, while the objective axes
(retraction, species/population scope) come — unchanged and unoverturnable — from the
shared metadata logic in `objective_axes.py`.

What is real now vs. what RB1–RB3 finalize
------------------------------------------
- **Structural (real now):** the three-agent wiring; the metadata-override boundary
  (agents are handed the objective findings as fixed facts and have no code path to
  change them); the **verbatim guard** (every supporter/refuter quote must be a
  whitespace-normalized substring of the cited grounding corpus, or it is discarded and
  counted); the swappable `overall` rollup; the confidence + `NOT_ENOUGH_INFO`
  abstention *interface* (self-consistency over N critic rounds).
- **PROVISIONAL (clearly-labeled constants / injected vocab):** prompt wording (RB2),
  the RB1 grade scale (`prompts.RB1_GRADES`), and the confidence/abstention thresholds
  (`SELF_CONSISTENCY_ROUNDS`, `ABSTAIN_AGREEMENT_THRESHOLD`, tier cutoffs). RB3 tunes the
  self-consistency mechanism and recalibration jointly; the seams are already in place.

Known limitation (WO-C4 manager decision): the grounding corpus is the cited paper's
**title + abstract only** — PubMed metadata carries no full text. Full-text spans slot
into `_grounding_corpus` later without reshaping anything else.

No live API in CI: the Anthropic SDK is imported lazily (only when the default client is
constructed), so importing this module never requires a key or a network. Tests inject a
mock client; the pipeline requests `OPUS_MODEL` on every call so the invariant is testable.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Optional

from .contracts import AxisFinding, GroundedRecord, ScopeFrame, Verdict
from .objective_axes import (
    build_unverifiable_axes,
    population_axis,
    retraction_axis,
    species_axis,
)
from .prompts import (
    GRADE_VALUES,
    NOT_ENOUGH_INFO,
    VERBALIZED_CONFIDENCE,
    critic,
    refuter,
    supporter,
)

# ----------------------------------------------------------------------------------
# HARD invariant — never swap to a cheaper/faster model (CLAUDE.md invariant #4).
# ----------------------------------------------------------------------------------
OPUS_MODEL = "claude-opus-4-8"

# ----------------------------------------------------------------------------------
# PROVISIONAL scaffold defaults — RB3 tunes these JOINTLY. Kept as labeled module
# constants and mirrored on AdjudicationConfig so research swaps them without touching
# the pipeline. Do NOT treat any of these as finalized.
# ----------------------------------------------------------------------------------
SELF_CONSISTENCY_ROUNDS = 5          # critic re-runs over the FIXED grounded evidence
ABSTAIN_AGREEMENT_THRESHOLD = 0.6    # modal-grade agreement below this ⇒ abstain
MIN_VALID_ROUNDS = 3                 # too few parseable rounds ⇒ abstain (anti-false-confidence)
CONFIDENCE_HIGH_AGREEMENT = 0.8      # tier=high needs this agreement AND verbalized "high"
CONFIDENCE_MEDIUM_AGREEMENT = 0.6    # tier=medium floor
MAX_TOKENS_ADVOCATE = 900
MAX_TOKENS_CRITIC = 400

_WS = re.compile(r"\s+")


# ==================================================================================
# Model client seam (mockable; default wraps the Anthropic Messages API on Opus 4.8)
# ==================================================================================
class AnthropicModelClient:
    """Default model client. Lazily constructs the SDK client so importing this module
    (and running the offline slice/scorer/tests) never needs an API key or a network."""

    def __init__(self) -> None:
        import anthropic  # lazy: only touched when a real adjudication actually runs
        self._client = anthropic.Anthropic()

    def complete(self, *, model: str, system: str, user: str, max_tokens: int) -> str:
        msg = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            getattr(b, "text", "") for b in msg.content
            if getattr(b, "type", None) == "text"
        )


# ==================================================================================
# Swappable configuration — the research seam
# ==================================================================================
@dataclass(frozen=True)
class AdjudicationConfig:
    """All PROVISIONAL knobs in one swappable place (RB1/RB3 finalize the values).

    `rollup` is the swappable `overall` policy; when None the module default is used.
    `OPUS_MODEL` is deliberately NOT a field here — the model is a hard invariant, not a knob.
    """
    self_consistency_rounds: int = SELF_CONSISTENCY_ROUNDS
    abstain_agreement_threshold: float = ABSTAIN_AGREEMENT_THRESHOLD
    min_valid_rounds: int = MIN_VALID_ROUNDS
    confidence_high_agreement: float = CONFIDENCE_HIGH_AGREEMENT
    confidence_medium_agreement: float = CONFIDENCE_MEDIUM_AGREEMENT
    max_tokens_advocate: int = MAX_TOKENS_ADVOCATE
    max_tokens_critic: int = MAX_TOKENS_CRITIC
    rollup: Optional[Callable[[list[AxisFinding]], str]] = None


# ==================================================================================
# Grounding + verbatim guard
# ==================================================================================
def _norm(s: str) -> str:
    """Whitespace-normalize (mirrors the reference extraction guard's `norm`)."""
    return _WS.sub(" ", s or "").strip()


def _grounding_segments(g: GroundedRecord) -> list[str]:
    """The verbatim-guard denominators: each source field normalized SEPARATELY.

    A verbatim span must lie wholly within one segment — title and abstract are distinct
    fields, so joining them would let a fabricated quote straddle the title↔abstract
    junction and match text that exists contiguously in neither. KNOWN LIMITATION
    (WO-C4): title + abstract only — no full text in PubMed metadata. Full-text segments
    append here (each its own denominator) when C1 provides them; nothing else changes.
    """
    return [seg for seg in (_norm(g.title), _norm(g.abstract)) if seg]


def _verbatim_survivors(points: Sequence[dict], segments: Sequence[str],
                        quote_key: str) -> tuple[list[dict], int]:
    """Keep only points whose `quote` is a verbatim (normalized) substring of a SINGLE
    source segment.

    Non-verbatim, empty, cross-segment, or non-string quotes are DISCARDED and counted —
    the hard rule (invariant #5) that a support/refute point must quote a real span of the
    cited source or be thrown away. A non-`str` quote is not a quote (a JSON null/number/
    bool must not be coerced into a spurious match), so it is discarded outright.
    """
    survivors: list[dict] = []
    discarded = 0
    for p in points:
        if not isinstance(p, dict):
            discarded += 1
            continue
        raw = p.get(quote_key)
        quote = _norm(raw) if isinstance(raw, str) else ""
        if quote and any(quote in seg for seg in segments):
            survivors.append(p)
        else:
            discarded += 1
    return survivors, discarded


# ==================================================================================
# Model I/O helpers
# ==================================================================================
def _parse_json(text: str) -> Optional[dict]:
    """Tolerant JSON extraction: strip code fences, take the outermost {...}. None on failure."""
    if not isinstance(text, str) or not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        obj = json.loads(t[start:end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _call_agent(client, system: str, user: str, max_tokens: int) -> Optional[dict]:
    """One model turn on Opus 4.8, parsed to a dict (None if unparseable)."""
    text = client.complete(model=OPUS_MODEL, system=system, user=user, max_tokens=max_tokens)
    return _parse_json(text)


def _points(raw: Optional[dict]) -> list[dict]:
    if isinstance(raw, dict) and isinstance(raw.get("points"), list):
        return [p for p in raw["points"] if isinstance(p, dict)]
    return []


# ==================================================================================
# Self-consistency aggregation + abstention (the confidence interface; RB3 tunes it)
# ==================================================================================
@dataclass
class _Aggregate:
    grade: Optional[str]
    agreement: float
    verbalized: str
    n_valid: int
    rationale: str


def _aggregate_rounds(rounds: Sequence[Optional[dict]]) -> _Aggregate:
    """Modal grade + agreement fraction over the valid critic rounds (CONTEXT_PACK §7)."""
    grades: list[str] = []
    confidences: list[str] = []
    rationale_by_grade: dict[str, str] = {}
    for r in rounds:
        if not isinstance(r, dict):
            continue
        g = r.get("grade")
        if g in GRADE_VALUES:
            grades.append(g)
            rationale_by_grade.setdefault(g, str(r.get("rationale", "")).strip())
        c = r.get("confidence")
        if c in VERBALIZED_CONFIDENCE:
            confidences.append(c)
    n_valid = len(grades)
    if n_valid == 0:
        return _Aggregate(None, 0.0, "low", 0, "")
    grade, top = Counter(grades).most_common(1)[0]
    agreement = top / n_valid
    verbalized = Counter(confidences).most_common(1)[0][0] if confidences else "low"
    return _Aggregate(grade, agreement, verbalized, n_valid, rationale_by_grade.get(grade, ""))


def _decide_abstention(agg: _Aggregate, sup: Sequence[dict], ref: Sequence[dict],
                       cfg: AdjudicationConfig) -> bool:
    """Abstain (NOT_ENOUGH_INFO) when the graded signal is not trustworthy.

    PROVISIONAL policy (RB3): abstain if there is no usable critic signal, too few valid
    rounds, the critic itself abstained, self-consistency is below threshold, or there is
    no verbatim-grounded evidence either way. Abstentions are recorded, not scored wrong.
    """
    if agg.grade is None or agg.n_valid < cfg.min_valid_rounds:
        return True
    if agg.grade == NOT_ENOUGH_INFO:
        return True
    if agg.agreement < cfg.abstain_agreement_threshold:
        return True
    if not sup and not ref:
        return True
    return False


def _confidence_tier(agg: _Aggregate, cfg: AdjudicationConfig) -> str:
    """Map (agreement, verbalized) → confidence tier. PROVISIONAL (RB3 recalibrates)."""
    if agg.agreement >= cfg.confidence_high_agreement and agg.verbalized == "high":
        return "high"
    if agg.agreement >= cfg.confidence_medium_agreement:
        return "medium"
    return "low"


# ==================================================================================
# Swappable `overall` rollup policy
# ==================================================================================
def default_rollup(findings: list[AxisFinding]) -> str:
    """Default `overall` policy (CONTEXT_PACK §6): retraction OR scope mismatch gate to
    'not supported as stated' regardless of the substantive grade; otherwise `overall`
    tracks the substantive grade. Combination happens here, in the open — the substantive
    grade is reported ALONGSIDE the gate, never silently depressed by an objective signal.
    """
    by = {f.axis: f for f in findings}
    gates: list[str] = []
    r = by["retraction"].verdict
    if r == "RELIES_ON_RETRACTED":
        gates.append("CITATION RELIES ON A RETRACTED PAPER")
    elif r == "CITED_PAPER_HAS_EOC":
        gates.append("CITED PAPER HAS AN EXPRESSION OF CONCERN")
    if by["species_scope"].verdict == "SCOPE_MISMATCH":
        gates.append("SPECIES SCOPE MISMATCH")
    pop = by.get("population_scope")
    if pop and pop.verdict == "SCOPE_MISMATCH":
        gates.append("POPULATION SCOPE MISMATCH")

    sub = by["substantive_support"].verdict
    if gates:
        return (f"NOT SUPPORTED AS STATED ({'; '.join(gates)}) — substantive grade "
                f"(held separately): {sub}")
    if sub == NOT_ENOUGH_INFO:
        return "INSUFFICIENT EVIDENCE TO GRADE SUBSTANTIVE SUPPORT (abstained)"
    return f"SUBSTANTIVE SUPPORT: {sub}"


# ==================================================================================
# Substantive-support AxisFinding (CONTEXT_PACK §6 evidence keys — C5 reads these)
# ==================================================================================
def _headline(points: Sequence[dict], src_key: str, out_key: str) -> dict:
    """Strongest (first-surviving, strongest-first-ordered) grounded point, §6 shape.

    `src_key` is the reason field on the agent's point (supporter→"rationale",
    refuter→"objection"); `out_key` is the §6 headline field name (supporter→"point",
    refuter→"objection"). These differ for the supporter, so read and write keys are distinct.
    """
    if points:
        p = points[0]
        return {"span": p.get("quote", ""), out_key: p.get(src_key, "")}
    return {"span": "", out_key: ""}


def _build_substantive_finding(agg: _Aggregate, tier: str, abstained: bool,
                               sup: list[dict], ref: list[dict],
                               sup_discarded: int, ref_discarded: int,
                               cfg: AdjudicationConfig) -> AxisFinding:
    grade = NOT_ENOUGH_INFO if abstained else agg.grade
    if abstained:
        detail = ("Abstained (NOT_ENOUGH_INFO): critic self-consistency below threshold or "
                  "insufficient verbatim-grounded evidence to place a substantive grade.")
    else:
        detail = agg.rationale or "Graded from the adversarial supporter/refuter exchange."

    evidence = {
        # --- CONTEXT_PACK §6 headline keys (C5-facing; keep exactly these names) ---------
        "confidence": {"verbalized": agg.verbalized,
                       "agreement": round(agg.agreement, 4),
                       "n_samples": agg.n_valid},
        "calibration": {"note": ""},  # empty until the scorer/RB3 fills recalibration
        "supporter": _headline(sup, "rationale", "point"),
        "refuter": _headline(ref, "objection", "objection"),
        "abstained": abstained,
        # --- richer optional additions (WO-C4 permits; C5 ignores unknown keys) ----------
        "supporter_points": sup,
        "refuter_points": ref,
        "verbatim_guard": {"supporter_discarded": sup_discarded,
                           "refuter_discarded": ref_discarded,
                           "grounding_corpus": "title+abstract"},
        "self_consistency": {"rounds_configured": cfg.self_consistency_rounds,
                             "rounds_valid": agg.n_valid,
                             "agreement": round(agg.agreement, 4),
                             "abstain_threshold": cfg.abstain_agreement_threshold},
    }
    return AxisFinding(
        axis="substantive_support",
        verdict=grade,
        tier=tier,
        provenance="model-inferred",  # §6: graded axis is model-inferred (spans are text-grounded)
        detail=detail,
        evidence=evidence,
    )


# ==================================================================================
# Public entry point — drop-in for adjudicator_stub.adjudicate_stub
# ==================================================================================
def adjudicate(g: GroundedRecord, scope: ScopeFrame, claim_text: str = "", *,
               client=None, config: Optional[AdjudicationConfig] = None) -> Verdict:
    """Adjudicate whether the cited paper substantively supports the claim.

    Same signature/seam as `adjudicate_stub` (extra keyword-only `client`/`config` have
    defaults). `client` must expose `complete(*, model, system, user, max_tokens) -> str`;
    when None a live Opus 4.8 Anthropic client is constructed lazily. Objective axes come
    from `objective_axes` and are passed to the agents as fixed facts they cannot overturn.
    """
    cfg = config or AdjudicationConfig()
    client = client or AnthropicModelClient()

    # 1. Objective axes — fixed metadata facts (single source of truth; not overturnable).
    retr = retraction_axis(g)
    spec = species_axis(g, scope)
    popn = population_axis(g, scope)
    objective_facts = {
        "retraction": {"verdict": retr.verdict, "detail": retr.detail},
        "species_scope": {"verdict": spec.verdict, "detail": spec.detail},
        "population_scope": {"verdict": popn.verdict, "detail": popn.detail},
    }

    segments = _grounding_segments(g)

    # 2. Supporter → verbatim guard.
    sup_raw = _call_agent(client, supporter.SYSTEM,
                          supporter.build_user(claim_text, g.title, g.abstract),
                          cfg.max_tokens_advocate)
    sup_points, sup_discarded = _verbatim_survivors(_points(sup_raw), segments, "quote")

    # 3. Refuter → verbatim guard.
    ref_raw = _call_agent(client, refuter.SYSTEM,
                          refuter.build_user(claim_text, g.title, g.abstract),
                          cfg.max_tokens_advocate)
    ref_points, ref_discarded = _verbatim_survivors(_points(ref_raw), segments, "quote")

    # 4. Critic self-consistency: N rounds over the SAME fixed grounded evidence.
    critic_user = critic.build_user(
        claim_text, g.title, g.abstract, sup_points, ref_points,
        objective_facts, GRADE_VALUES, VERBALIZED_CONFIDENCE,
    )
    rounds = [_call_agent(client, critic.SYSTEM, critic_user, cfg.max_tokens_critic)
              for _ in range(cfg.self_consistency_rounds)]
    agg = _aggregate_rounds(rounds)

    # 5. Abstention + confidence tier (the RB3 interface).
    abstained = _decide_abstention(agg, sup_points, ref_points, cfg)
    tier = "low" if abstained else _confidence_tier(agg, cfg)

    # 6. Substantive finding (with the §6 evidence keys) + assemble the 4 axes.
    substantive = _build_substantive_finding(agg, tier, abstained, sup_points, ref_points,
                                             sup_discarded, ref_discarded, cfg)
    findings = [retr, spec, popn, substantive]

    # 7. Swappable rollup for `overall`.
    overall = (cfg.rollup or default_rollup)(findings)

    notes = [
        "Cited-paper metadata is authoritative on objective axes; the supporter/refuter/critic "
        "reason only on substantive_support and may not overturn a structured record "
        "(metadata-override rule).",
        "substantive_support grades substance holding scope constant; scope over-generalization "
        "is carried by the metadata scope axes and folded into `overall` by a swappable rollup.",
        f"Verbatim guard: discarded {sup_discarded} supporter and {ref_discarded} refuter "
        "point(s) whose quotes were not verbatim spans of the cited title+abstract.",
    ]
    if abstained:
        notes.append("Abstained on substantive_support (NOT_ENOUGH_INFO) — recorded so it is not "
                     "scored as a wrong grade.")

    return Verdict(
        claim=claim_text,
        cited_identifier=g.identifier,
        overall=overall,
        axis_findings=findings,
        unverifiable_axes=build_unverifiable_axes(scope),
        stub=False,
        notes=notes,
    )
