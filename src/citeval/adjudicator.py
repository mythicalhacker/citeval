"""C4 — adversarial adjudicator (RB1/RB2/RB3 finalized).

`adjudicate(grounded, scope, claim_text="") -> Verdict` is a drop-in replacement for
`adjudicator_stub.adjudicate_stub` at the runner seam. It runs an adversarial
**supporter → refuter → critic** pipeline (all **Opus 4.8**) that produces the graded
`substantive_support` axis with a calibrated confidence, while the objective axes
(retraction, species/population scope) come — unchanged and unoverturnable — from the
shared metadata logic in `objective_axes.py`.

RB1/RB2/RB3 integration (design/research_briefs/results/INTEGRATION_SPEC.md):
- **RB1 scale** (`prompts.RB1_GRADES`, grade-1 = `unsupported-for-the-claim`), plus the two
  non-graded outcomes `NOT_ENOUGH_INFO` (abstention) and `N/A — non-substantiating` (Trap 2).
- **RB2 agent design:** evidence-first/grade-last critic; the **full triad** is resampled N
  times (warm advocates diversify spans, a cool critic stays stable); transcripts are
  identity-blinded + order-randomized (deterministically, by sample index — Balanced Position
  Calibration without RNG so tests reproduce); refuter `routes_to="rollup_not_grade"` points
  are **hard-filtered before the critic votes**, so scope over-generalization can never depress
  the grade (CONTEXT_PACK §6; RB1 §D scope-capping OVERRIDDEN).
- **RB3 calibration:** confidence = exact modal agreement `conf_agr = a_exact` over N=7
  (primary), with adjacent agreement `a_adj` and an Avg-Conf `conf_hybrid` (numeric verbalized
  confidences as weights) auxiliary; abstain when `a_exact < tau_abstain` **and the split is
  not adjacent-only**, or when the grades are **non-adjacent multimodal**; never abstain on an
  adjacent-only split. A post-hoc recalibration hook fills `evidence.calibration.note`.

Every threshold is a **PROVISIONAL, recalibratable seed** (RB3 tunes them jointly on the human
spot-check); only `OPUS_MODEL` is a hard invariant. All §6 evidence-dict keys are unchanged so
C5 (`reporting.py`) renders with no fixup; the new numeric signals live in richer keys C5 ignores.

Grounding corpus (WO-C4 full-text): the cited paper's **title + abstract + budgeted PMC full
text** when available (invariant #6: raw JATS from EFetch db=pmc), falling back to title + abstract
when the paper is not in PMC. Full text is fed to the triad and appended as its own verbatim-guard
segment (`_grounding_segments`); `evidence.verbatim_guard.grounding_corpus` reports the actual depth.

No live API in CI: the Anthropic SDK is imported lazily (only when the default client is
constructed), so importing this module never requires a key or a network. Tests inject a mock
client; the pipeline requests `OPUS_MODEL` on every call so the invariant is testable.
"""
from __future__ import annotations

import json
import re
import statistics
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
    EVIDENCE_CACHE_MARK,
    GRADE_VALUES,
    NON_SUBSTANTIATING,
    NOT_ENOUGH_INFO,
    ORDINAL_GRADES,
    ORDINAL_INDEX,
    critic,
    refuter,
    supporter,
)

# ----------------------------------------------------------------------------------
# HARD invariant — never swap to a cheaper/faster model (CLAUDE.md invariant #4).
# ----------------------------------------------------------------------------------
OPUS_MODEL = "claude-opus-4-8"

# ----------------------------------------------------------------------------------
# PROVISIONAL, RECALIBRATABLE seeds — RB3 tunes these JOINTLY on the human spot-check.
# Kept as labeled module constants and mirrored on AdjudicationConfig so research swaps
# them without touching the pipeline. Do NOT treat any of these as finalized.
# ----------------------------------------------------------------------------------
SELF_CONSISTENCY_ROUNDS = 7          # RB3: N=7 full-triad samples (odd; avoids ties). Revisit 10–15.
TAU_ABSTAIN = 0.5                    # RB3 seed; exact-agreement floor below which we consider abstaining
ADJACENT_FLOOR = 0.7                 # a_adj at/above this ⇒ "adjacent-only split" (do NOT abstain)
MIN_VALID_ROUNDS = 4                 # too few parseable ordinal rounds ⇒ abstain (anti-false-confidence; ≥4 for N=7)
CONFIDENCE_HIGH_AGREEMENT = 0.8      # tier=high seed (data-derived by RB3; NOT verbalized-gated)
CONFIDENCE_MEDIUM_AGREEMENT = 0.6    # tier=medium floor seed
ADVOCATE_TEMPERATURE = 0.9           # warm advocates diversify spans (RB2/RB3 0.7–1.0)
CRITIC_TEMPERATURE = 0.2             # cool critic for a stable verdict (RB2 §4)
MAX_TOKENS_ADVOCATE = 1200   # was 900: advocates now quote from budgeted full text — don't truncate mid-quote
MAX_TOKENS_CRITIC = 1500     # was 500: the evidence-first/grade-last JSON must fit PAST its closing brace.
                             # At 500 the critic truncated before the trailing `grade`, so _parse_json→None
                             # dropped ~20/21 rounds and full-text coverage collapsed to 0 (WO-C4 fix).

_WS = re.compile(r"\s+")


# ==================================================================================
# Model client seam (mockable; default wraps the Anthropic Messages API on Opus 4.8)
# ==================================================================================
def _content_blocks(user: str) -> list[dict]:
    """Split a user turn on `EVIDENCE_CACHE_MARK` into a cache-marked evidence prefix + the
    per-call variable tail (Part C — prompt caching). The large reusable evidence block
    (title + abstract + full_text [+ objective facts]) that precedes the mark gets a
    `cache_control={"type":"ephemeral"}` breakpoint, so it is cached across the 3 agents and the
    7 self-consistency rounds of a case (the evidence is identical; only the tail varies). The
    sentinel is STRIPPED — the model never sees it. With no sentinel, a single plain block.

    Pure and SDK-free so it is unit-testable offline; the real client passes the result as the
    user message `content`. Mock clients never call this — they keep `user` as one string and the
    invisible sentinel is inert, so their behaviour is unchanged."""
    prefix, mark, rest = user.partition(EVIDENCE_CACHE_MARK)
    if not mark:
        return [{"type": "text", "text": user}]
    blocks: list[dict] = [{"type": "text", "text": prefix, "cache_control": {"type": "ephemeral"}}]
    if rest:
        blocks.append({"type": "text", "text": rest})
    return blocks


class AnthropicModelClient:
    """Default model client. Lazily constructs the SDK client so importing this module
    (and running the offline slice/scorer/tests) never needs an API key or a network."""

    def __init__(self) -> None:
        import anthropic  # lazy: only touched when a real adjudication actually runs
        self._client = anthropic.Anthropic()

    def complete(self, *, model: str, system: str, user: str, max_tokens: int,
                 temperature: float = 1.0) -> str:
        # claude-opus-4-8 deprecated temperature; the advocate/critic temperature config is
        # retained on the interface but not sent — self-consistency variance now comes from
        # default-temperature sampling.
        #
        # Part C (prompt caching): the user turn is sent as structured content blocks with a
        # cache_control breakpoint on the large, reused evidence prefix (title/abstract/full_text),
        # cutting repeat input cost/latency across the case's 21 triad calls. The seam signature is
        # unchanged (`user` stays a single str), so mock clients keep working untouched.
        msg = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": _content_blocks(user)}],
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
    `recalibration` is the RB3 post-hoc temperature/Platt map applied to the emitted
    confidence (fills `evidence.calibration.note`); identity when None.
    `OPUS_MODEL` is deliberately NOT a field — the model is a hard invariant, not a knob.
    """
    self_consistency_rounds: int = SELF_CONSISTENCY_ROUNDS
    tau_abstain: float = TAU_ABSTAIN
    adjacent_floor: float = ADJACENT_FLOOR
    min_valid_rounds: int = MIN_VALID_ROUNDS
    confidence_high_agreement: float = CONFIDENCE_HIGH_AGREEMENT
    confidence_medium_agreement: float = CONFIDENCE_MEDIUM_AGREEMENT
    advocate_temperature: float = ADVOCATE_TEMPERATURE
    critic_temperature: float = CRITIC_TEMPERATURE
    max_tokens_advocate: int = MAX_TOKENS_ADVOCATE
    max_tokens_critic: int = MAX_TOKENS_CRITIC
    adaptive_early_stopping: bool = True   # stop once rounds are unanimous (past the min floor)
    rollup: Optional[Callable[[list[AxisFinding]], str]] = None
    recalibration: Optional[Callable[[float], float]] = None
    # Optional per-round progress hook (scorer verbose mode): called `on_round(i, critic_round)`
    # after each triad sample so a slow live case is visibly alive within seconds. Default None
    # (no-op); a raising callback must never crash adjudication, so it is invoked defensively.
    on_round: Optional[Callable[[int, Optional[dict]], None]] = None


# ==================================================================================
# Grounding + verbatim guard
# ==================================================================================
def _norm(s: str) -> str:
    """Whitespace-normalize (mirrors the reference extraction guard's `norm`)."""
    return _WS.sub(" ", s or "").strip()


def _grounding_segments(g: GroundedRecord) -> list[str]:
    """The verbatim-guard denominators: each source field normalized SEPARATELY.

    A verbatim span must lie wholly within one segment — title, abstract, and each full-text
    SECTION are distinct, non-contiguous spans of the paper, so joining them would let a fabricated
    quote straddle a junction and match text that exists contiguously in none. The budgeted full
    text (invariant #6) is stored as its constituent sections joined by blank lines
    (`select_budgeted_fulltext`); we split it back on those blank lines so each section is its OWN
    denominator. That blocks a straddle across the abstract↔body or section↔section boundary (two
    real but non-adjacent fragments) just as keeping title/abstract separate blocks the title↔
    abstract straddle. When full text is unavailable (`g.full_text == ""`) it is simply absent and
    the abstract-only behaviour is unchanged.
    """
    segments = [_norm(g.title), _norm(g.abstract)]
    segments += [_norm(part) for part in re.split(r"\n{2,}", g.full_text)]
    return [seg for seg in segments if seg]


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


def _call_agent(client, system: str, user: str, max_tokens: int,
                temperature: float) -> Optional[dict]:
    """One model turn on Opus 4.8, parsed to a dict (None if unparseable)."""
    text = client.complete(model=OPUS_MODEL, system=system, user=user,
                           max_tokens=max_tokens, temperature=temperature)
    return _parse_json(text)


def _points(raw: Optional[dict]) -> list[dict]:
    if isinstance(raw, dict) and isinstance(raw.get("points"), list):
        return [p for p in raw["points"] if isinstance(p, dict)]
    return []


_SCOPE_TAGS = ("over_generalization", "scope_overgeneralization")


def _routes_to_grade(p: dict) -> bool:
    """A refuter point may move the grade UNLESS it is scope over-generalization.

    The scope TAG is an UNCONDITIONAL, first-priority structural gate (b6): an
    over_generalization point is barred from the grade regardless of what `routes_to` claims
    — the guard must not be defeated by the warm model's self-declared routing (CLAUDE.md:
    "enforce structurally, not by convention"; CONTEXT_PACK §6 — scope never depresses the
    grade). Only for a NON-scope tag is `routes_to` consulted, and any `rollup*` variant
    (case-folded) routes to the rollup so a near-miss string cannot slip a point onto the grade.
    """
    tag = (p.get("distortion_type") or p.get("failure_mode") or "").strip().lower()
    if tag in _SCOPE_TAGS:
        return False
    route = p.get("routes_to")
    if isinstance(route, str) and route.strip():
        return not route.strip().lower().startswith("rollup")
    return True


def _num_conf(r: dict) -> Optional[float]:
    """The critic's numeric self-reported confidence in [0,1] (Avg-Conf weight). None if absent/bad."""
    c = r.get("confidence")
    if isinstance(c, bool):  # bool is an int subclass — reject before the numeric branch
        return None
    if isinstance(c, (int, float)):
        return max(0.0, min(1.0, float(c)))
    return None


def _round_rationale(r: dict) -> str:
    return str(r.get("grade_rationale_last") or r.get("reasoning") or r.get("rationale") or "").strip()


# ==================================================================================
# One triad sample (supporter → refuter → critic), blinded + order-randomized
# ==================================================================================
def _to_argument_points(points: Sequence[dict], reason_key: str) -> list[dict]:
    """Map an advocate's surviving points to the blinded critic-facing shape {quote, claim}."""
    return [{"quote": p.get("quote", ""), "claim": p.get(reason_key, "")} for p in points]


def _blinded_arguments(sup_points: Sequence[dict], ref_grade_points: Sequence[dict],
                       sample_idx: int) -> list[dict]:
    """Two identity-blinded argument blocks in a per-sample-randomized order.

    Deterministic Balanced Position Calibration: even samples present the support case first,
    odd samples present the refute case first — position bias averages out across N without RNG
    (so tests reproduce exactly). Agent identity ("supporter"/"refuter") is stripped.
    """
    sup_block = {"points": _to_argument_points(sup_points, "rationale")}
    ref_block = {"points": _to_argument_points(ref_grade_points, "objection")}
    ordered = [sup_block, ref_block] if sample_idx % 2 == 0 else [ref_block, sup_block]
    for label, block in zip(("A", "B"), ordered):
        block["label"] = label
    return ordered


@dataclass
class _TriadSample:
    critic_round: Optional[dict]
    sup_points: list[dict]
    ref_grade_points: list[dict]
    ref_rollup_points: list[dict]
    sup_discarded: int
    ref_discarded: int


def _run_triad(client, g: GroundedRecord, claim_text: str, direction: Optional[str],
               objective_facts: dict, segments: Sequence[str], sample_idx: int,
               cfg: AdjudicationConfig) -> _TriadSample:
    # Supporter (warm) → verbatim guard. Full text (when present) is fed as extra evidence.
    sup_raw = _call_agent(client, supporter.SYSTEM,
                          supporter.build_user(claim_text, g.title, g.abstract, g.full_text),
                          cfg.max_tokens_advocate, cfg.advocate_temperature)
    sup_points, sup_discarded = _verbatim_survivors(_points(sup_raw), segments, "quote")

    # Refuter (warm) → verbatim guard → routes_to hard-filter (b6).
    ref_raw = _call_agent(client, refuter.SYSTEM,
                          refuter.build_user(claim_text, g.title, g.abstract, direction, g.full_text),
                          cfg.max_tokens_advocate, cfg.advocate_temperature)
    ref_survivors, ref_discarded = _verbatim_survivors(_points(ref_raw), segments, "quote")
    ref_grade_points = [p for p in ref_survivors if _routes_to_grade(p)]
    ref_rollup_points = [p for p in ref_survivors if not _routes_to_grade(p)]

    # Critic (cool) over the blinded, order-randomized arguments — grade-routed points only.
    arguments = _blinded_arguments(sup_points, ref_grade_points, sample_idx)
    critic_user = critic.build_user(claim_text, g.title, g.abstract, arguments,
                                    objective_facts, GRADE_VALUES, direction, g.full_text)
    critic_round = _call_agent(client, critic.SYSTEM, critic_user,
                               cfg.max_tokens_critic, cfg.critic_temperature)
    if critic_round is None:
        # Cheap robustness (WO-C4 fix): a lone truncated/garbled critic response parses to None and
        # would silently drop the whole round. Resample the critic ONCE at the same settings before
        # counting it invalid — a transient truncation usually clears on the retry. At most one retry
        # per round; early-stopping is untouched (it reads the resulting rounds back in the caller).
        critic_round = _call_agent(client, critic.SYSTEM, critic_user,
                                   cfg.max_tokens_critic, cfg.critic_temperature)
    return _TriadSample(critic_round, sup_points, ref_grade_points, ref_rollup_points,
                        sup_discarded, ref_discarded)


def _unanimous_ordinal(rounds: Sequence[Optional[dict]]) -> bool:
    """True iff every parsed round carries the SAME ordinal grade (adaptive early-stop trigger)."""
    seen = set()
    for r in rounds:
        if not isinstance(r, dict):
            return False
        g = r.get("grade")
        if not isinstance(g, str) or g not in ORDINAL_INDEX:   # non-str/unhashable grade ⇒ not unanimous (no hash crash)
            return False
        seen.add(g)
    return len(seen) == 1 and len(rounds) > 0


# ==================================================================================
# Self-consistency aggregation (median-aware ordinal vote + RB3 confidence signals)
# ==================================================================================
@dataclass
class _Aggregate:
    grade: Optional[str]                 # median-aware modal ORDINAL grade (None if no ordinal rounds)
    grade_index: Optional[int]
    a_exact: float                       # conf_agr (primary): fraction of ordinal rounds == g*
    a_adj: float                         # fraction within ±1 ordinal of g*
    conf_hybrid: float                   # Avg-Conf: Σ 1{gᵢ=g*}·Cᵢ / Σ Cᵢ
    n_valid: int                         # # ordinal rounds
    n_nei: int                           # # NOT_ENOUGH_INFO rounds
    n_na: int                            # # N/A — non-substantiating rounds
    n_parsed: int                        # # rounds with ANY recognized grade (ordinal | NEI | N/A)
    n_parse_failed: int                  # # rounds the model answered but we could NOT parse a grade from
    non_adjacent_multimodal: bool
    ordinal_distribution: dict[str, int]
    rationale: str


def _aggregate_rounds(rounds: Sequence[Optional[dict]], cfg: AdjudicationConfig) -> _Aggregate:
    """Median-aware modal ordinal grade + RB3 agreement signals over the valid rounds."""
    indices: list[int] = []
    confidences: list[float] = []          # numeric confidence per ordinal round (aligned to indices)
    rationale_by_grade: dict[str, str] = {}
    n_nei = n_na = n_parsed = n_parse_failed = 0
    for r in rounds:
        if not isinstance(r, dict):
            n_parse_failed += 1   # None: truncated/invalid JSON (the 500-token cap bug) — COUNTED, not dropped
            continue
        gr = r.get("grade")
        # `gr` is an arbitrary parsed-JSON value; guard the hash-based membership test so an
        # UNHASHABLE grade ({"grade": []} / {"grade": {}}) falls through to the parse-failed `else`
        # instead of raising TypeError and aborting the whole case (mirrors scorer.py's str guard).
        if isinstance(gr, str) and gr in ORDINAL_INDEX:
            n_parsed += 1
            indices.append(ORDINAL_INDEX[gr])
            conf = _num_conf(r)
            confidences.append(conf if conf is not None else 0.0)
            rationale_by_grade.setdefault(gr, _round_rationale(r))
        elif gr == NOT_ENOUGH_INFO:
            n_parsed += 1
            n_nei += 1
        elif gr == NON_SUBSTANTIATING:
            n_parsed += 1
            n_na += 1
        else:
            n_parse_failed += 1   # answered but no recognized grade (missing/garbled grade field)

    n_valid = len(indices)
    if n_valid == 0:
        return _Aggregate(None, None, 0.0, 0.0, 0.0, 0, n_nei, n_na, n_parsed, n_parse_failed,
                          False, {}, "")

    counts = Counter(indices)
    present = sorted(counts)
    median_val = statistics.median(indices)
    # g* = observed ordinal grade nearest the median; ties → more frequent, then better (lower) grade.
    g_index = min(present, key=lambda i: (abs(i - median_val), -counts[i], i))
    grade = ORDINAL_GRADES[g_index]

    a_exact = counts[g_index] / n_valid
    a_adj = sum(c for i, c in counts.items() if abs(i - g_index) <= 1) / n_valid
    num = sum(confidences[k] for k in range(n_valid) if indices[k] == g_index)
    den = sum(confidences)
    conf_hybrid = (num / den) if den > 0 else a_exact
    non_adjacent_multimodal = a_adj < cfg.adjacent_floor
    distribution = {ORDINAL_GRADES[i]: c for i, c in sorted(counts.items())}
    return _Aggregate(grade, g_index, a_exact, a_adj, conf_hybrid, n_valid, n_nei, n_na,
                      n_parsed, n_parse_failed, non_adjacent_multimodal, distribution,
                      rationale_by_grade.get(grade, ""))


# ==================================================================================
# Outcome decision — GRADED / ABSTAINED / NON_SUBSTANTIATING (RB3 Part 2)
# ==================================================================================
@dataclass
class _Outcome:
    status: str                # "GRADED" | "ABSTAINED" | "NON_SUBSTANTIATING"
    verdict: str               # the emitted verdict string
    abstained: bool
    non_substantiating: bool
    reason: str


def _decide_outcome(agg: _Aggregate, has_grounded_evidence: bool, rounds_run: int,
                    cfg: AdjudicationConfig) -> _Outcome:
    """Map the aggregate to one of three outcomes.

    Priority (RB2 §2.3 / RB3 Part 2): a critic MAJORITY of `N/A` → non-substantiating (Trap 2,
    off the support scale); a majority of NEI → abstain; otherwise grade on the ordinal rounds,
    abstaining only when the graded signal is untrustworthy — too few valid rounds, no grounded
    evidence, or the split is dispersed. Abstain on the substantive path when the grades are
    non-adjacent multimodal (a_adj < adjacent_floor) OR agreement is below tau_abstain AND the
    split is not a PURE adjacent-only split (a_adj == 1.0). NEVER abstain on a pure adjacent-only
    split — that is ordinal boundary noise, resolve to g* with moderate confidence.
    """
    # NA/NEI majority is over the samples RUN, not the parseable subset (RB2 §2.3): unparseable
    # rounds count AGAINST reaching a majority rather than shrinking the denominator.
    half = -(-rounds_run // 2)  # ceil(rounds_run / 2)
    if agg.n_na >= half and agg.n_na >= agg.n_nei and agg.n_na >= agg.n_valid:
        return _Outcome("NON_SUBSTANTIATING", NON_SUBSTANTIATING, False, True,
                        "Critic majority judged the citation non-substantiating (method/background/"
                        "passing citation) — off the support scale (Trap 2).")
    if agg.n_nei >= half and agg.n_nei >= agg.n_valid:
        return _Outcome("ABSTAINED", NOT_ENOUGH_INFO, True, False,
                        "Critic majority returned NOT_ENOUGH_INFO.")
    if agg.grade is None or agg.n_valid < cfg.min_valid_rounds:
        return _Outcome("ABSTAINED", NOT_ENOUGH_INFO, True, False,
                        "Too few parseable substantive rounds to place a grade.")
    if not has_grounded_evidence:
        return _Outcome("ABSTAINED", NOT_ENOUGH_INFO, True, False,
                        "No verbatim-grounded evidence either way.")
    # `adjacent_only` (the carve-out) is a STRICTLY higher bar than the multimodal floor: ALL
    # mass within ±1 of g*. This leaves a live middle band (some non-adjacent mass, but
    # a_adj ≥ adjacent_floor) where `a_exact < tau_abstain` fires — so tau is not dead code.
    adjacent_only = agg.a_adj >= 1.0
    if agg.non_adjacent_multimodal or (agg.a_exact < cfg.tau_abstain and not adjacent_only):
        return _Outcome("ABSTAINED", NOT_ENOUGH_INFO, True, False,
                        f"Self-consistency dispersed (a_exact={agg.a_exact:.2f}, "
                        f"a_adj={agg.a_adj:.2f}, tau={cfg.tau_abstain}).")
    return _Outcome("GRADED", agg.grade, False, False,
                    agg.rationale or "Graded from the adversarial supporter/refuter exchange.")


def _confidence_tier(agg: _Aggregate, cfg: AdjudicationConfig) -> str:
    """Confidence tier from `conf_agr` = a_exact (RB3 primary). Data-derived seeds; NO
    verbalized-confidence gate (verbalized is a weight, not a gate — RB3 §3.6)."""
    if agg.a_exact >= cfg.confidence_high_agreement:
        return "high"
    if agg.a_exact >= cfg.confidence_medium_agreement:
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

    Non-graded substantive outcomes render distinctly: `N/A — non-substantiating` (a
    passing/method citation) and `NOT_ENOUGH_INFO` (abstention) are NOT grades and NOT each
    other.
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

    # How the substantive axis reads when reported alongside a gate / on its own.
    if sub == NON_SUBSTANTIATING:
        sub_phrase = "substantive support N/A (passing/method citation)"
    elif sub == NOT_ENOUGH_INFO:
        sub_phrase = "substantive support: insufficient evidence (abstained)"
    else:
        sub_phrase = f"substantive grade: {sub}"

    if gates:
        return f"NOT SUPPORTED AS STATED ({'; '.join(gates)}) — {sub_phrase} (held separately)"
    if sub == NON_SUBSTANTIATING:
        return "NON-SUBSTANTIATING CITATION (passing/method reference) — not graded on the support scale"
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


def _dedupe(points: Sequence[dict], reason_key: str) -> list[dict]:
    """Union across rounds, first occurrence wins (round 0 strongest-first stays first)."""
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for p in points:
        key = (str(p.get("quote", "")), str(p.get(reason_key, "")))
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _build_substantive_finding(agg: _Aggregate, outcome: _Outcome, tier: str,
                               sup: list[dict], ref_grade: list[dict], ref_rollup: list[dict],
                               sup_discarded: int, ref_discarded: int, rounds_run: int,
                               cfg: AdjudicationConfig, corpus_label: str) -> AxisFinding:
    verbalized = tier  # §6 `confidence.verbalized` is the emitted tier (a2 reconciliation)
    # Post-hoc recalibration of the emitted (primary) confidence, if a fitted map is supplied.
    calibration_note = ""
    if cfg.recalibration is not None:
        recal = float(cfg.recalibration(agg.a_exact))
        calibration_note = f"recalibrated confidence {recal:.2f} (from agreement {agg.a_exact:.2f})"

    evidence = {
        # --- CONTEXT_PACK §6 headline keys (C5-facing; keep exactly these names/shapes) ------
        "confidence": {"verbalized": verbalized,
                       "agreement": round(agg.a_exact, 4),   # conf_agr = a_exact (primary; numeric)
                       "n_samples": agg.n_valid},
        "calibration": {"note": calibration_note},
        "supporter": _headline(sup, "rationale", "point"),
        "refuter": _headline(ref_grade, "objection", "objection"),
        "abstained": outcome.abstained,
        # --- richer keys (C5 ignores unknown keys; scorer + audit consume them) --------------
        "non_substantiating": outcome.non_substantiating,
        "supporter_points": sup,
        "refuter_points": ref_grade,
        "refuter_scope_notes": ref_rollup,   # over_generalization (routed to rollup, not the grade)
        "verbatim_guard": {"supporter_discarded": sup_discarded,
                           "refuter_discarded": ref_discarded,
                           "grounding_corpus": corpus_label},
        "self_consistency": {"rounds_configured": cfg.self_consistency_rounds,
                             "rounds_run": rounds_run,
                             "rounds_valid": agg.n_valid,
                             "a_exact": round(agg.a_exact, 4),
                             "a_adj": round(agg.a_adj, 4),
                             "conf_hybrid": round(agg.conf_hybrid, 4),
                             "non_adjacent_multimodal": agg.non_adjacent_multimodal,
                             "ordinal_distribution": agg.ordinal_distribution,
                             "n_nei": agg.n_nei,
                             "n_non_substantiating": agg.n_na,
                             "n_parse_failed": agg.n_parse_failed,   # truncated/garbled rounds — VISIBLE, not a silent NEI
                             "grade_ordinal": agg.grade_index,
                             "tau_abstain": cfg.tau_abstain,
                             "adjacent_floor": cfg.adjacent_floor},
    }
    return AxisFinding(
        axis="substantive_support",
        verdict=outcome.verdict,
        tier=tier,
        provenance="model-inferred",  # §6: graded axis is model-inferred (spans are text-grounded)
        detail=outcome.reason,
        evidence=evidence,
    )


# ==================================================================================
# Public entry point — drop-in for adjudicator_stub.adjudicate_stub
# ==================================================================================
def adjudicate(g: GroundedRecord, scope: ScopeFrame, claim_text: str = "", *,
               client=None, config: Optional[AdjudicationConfig] = None) -> Verdict:
    """Adjudicate whether the cited paper substantively supports the claim.

    Same signature/seam as `adjudicate_stub` (extra keyword-only `client`/`config` have
    defaults). `client` must expose
    `complete(*, model, system, user, max_tokens, temperature) -> str`; when None a live
    Opus 4.8 Anthropic client is constructed lazily. Objective axes come from `objective_axes`
    and are passed to the agents as fixed facts they cannot overturn.
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
    direction = scope.direction  # claim's asserted effect direction (refuter/critic direction test)
    # Actual grounding depth for this case (Part B item 6): the verbatim guard + agents saw full
    # text only when it was available; the evidence key reports which, honestly.
    corpus_label = ("title+abstract+fulltext" if g.full_text
                    else "title+abstract (full text unavailable)")

    # 2. Full-triad self-consistency: N rounds, warm advocates + cool critic, blinded transcripts.
    critic_rounds: list[Optional[dict]] = []
    sup_all: list[dict] = []
    ref_grade_all: list[dict] = []
    ref_rollup_all: list[dict] = []
    sup_discarded_total = ref_discarded_total = 0
    rounds_run = 0
    for i in range(cfg.self_consistency_rounds):
        sample = _run_triad(client, g, claim_text, direction, objective_facts, segments, i, cfg)
        critic_rounds.append(sample.critic_round)
        sup_all += sample.sup_points
        ref_grade_all += sample.ref_grade_points
        ref_rollup_all += sample.ref_rollup_points
        sup_discarded_total += sample.sup_discarded
        ref_discarded_total += sample.ref_discarded
        rounds_run += 1
        if cfg.on_round is not None:      # per-round progress (scorer verbose mode); never fatal
            try:
                cfg.on_round(rounds_run, sample.critic_round)
            except Exception:             # noqa: BLE001 — a progress hook must not crash grading
                pass
        # Adaptive early-stopping: stop only once the rounds run are BOTH past the min floor AND
        # a strict majority of the configured N (2*run > N) and unanimous — then the remaining
        # rounds cannot change the median-aware g* regardless of how they vote. Gating on a
        # majority of N (not just min_valid_rounds) keeps g*-preservation structural if N is
        # raised without raising the floor (SELF_CONSISTENCY_ROUNDS notes "Revisit 10–15").
        if (cfg.adaptive_early_stopping and rounds_run >= cfg.min_valid_rounds
                and 2 * rounds_run > cfg.self_consistency_rounds
                and _unanimous_ordinal(critic_rounds)):
            break

    sup_points = _dedupe(sup_all, "rationale")
    ref_grade_points = _dedupe(ref_grade_all, "objection")
    ref_rollup_points = _dedupe(ref_rollup_all, "objection")

    # 3. Aggregate + decide outcome + confidence tier.
    agg = _aggregate_rounds(critic_rounds, cfg)
    has_evidence = bool(sup_points or ref_grade_points)
    outcome = _decide_outcome(agg, has_evidence, rounds_run, cfg)
    tier = "low" if outcome.status != "GRADED" else _confidence_tier(agg, cfg)

    # 4. Substantive finding (§6 evidence keys) + assemble the 4 axes.
    substantive = _build_substantive_finding(
        agg, outcome, tier, sup_points, ref_grade_points, ref_rollup_points,
        sup_discarded_total, ref_discarded_total, rounds_run, cfg, corpus_label)
    findings = [retr, spec, popn, substantive]

    # 5. Swappable rollup for `overall`.
    overall = (cfg.rollup or default_rollup)(findings)

    notes = [
        "Cited-paper metadata is authoritative on objective axes; the supporter/refuter/critic "
        "reason only on substantive_support and may not overturn a structured record "
        "(metadata-override rule).",
        "substantive_support grades substance holding scope constant; scope over-generalization "
        "is carried by the metadata scope axes and folded into `overall` by a swappable rollup "
        "(RB1 §D scope-capping overridden — CONTEXT_PACK §6).",
        f"Verbatim guard: discarded {sup_discarded_total} supporter and {ref_discarded_total} "
        f"refuter point(s) whose quotes were not verbatim spans of the cited {corpus_label}.",
        f"Self-consistency: {rounds_run} full-triad round(s) run; exact agreement "
        f"{agg.a_exact:.2f}, adjacent agreement {agg.a_adj:.2f} over {agg.n_valid} valid round(s).",
    ]
    if agg.n_parse_failed:
        notes.append(f"{agg.n_parse_failed} of {rounds_run} critic round(s) returned "
                     "unparseable/truncated JSON (no grade extracted, resampled once) — counted as "
                     "parse failures, NOT abstentions; raise max_tokens_critic if this recurs.")
    if ref_rollup_points:
        notes.append(f"Refuter noted {len(ref_rollup_points)} scope over-generalization point(s) — "
                     "routed to `overall`, never the substantive grade.")
    if outcome.non_substantiating:
        notes.append("Non-substantiating citation (method/background/passing) — off the support "
                     "scale (Trap 2); recorded so it is not scored as a graded prediction.")
    elif outcome.abstained:
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
