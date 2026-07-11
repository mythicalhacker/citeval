"""Critic role — maps the grounded (blinded) argument exchange to an RB1 grade + confidence.

RB2 wording (INTEGRATION_SPEC §2.2/§2.3); the grade vocabulary is injected by the pipeline
(RB1 owns it). The pipeline runs the FULL triad N times (self-consistency, RB3 Part 1) and
aggregates a median-aware modal grade + exact-agreement confidence.

Three hard constraints are injected into the prompt and enforced structurally by the
pipeline regardless of what the model says:
1. METADATA OVERRIDE — the objective facts (retraction, species/population scope) are fixed;
   the critic may not overturn them (CLAUDE.md invariant #1).
2. AXIS BOUNDARY — grade SUBSTANCE only, holding scope constant; scope over-reach is carried
   by the metadata scope axes and folded into `overall` by a swappable rollup, never by
   depressing this grade (CONTEXT_PACK §6; RB1 §D scope-capping is OVERRIDDEN).
3. IDENTITY-BLIND / ORDER-RANDOMIZED — the two argument blocks are presented without agent
   identity and in a per-sample-randomized order (RB2 §5 self-preference / position-bias
   mitigation); the critic weighs verbatim SOURCE spans, not the debaters' prose.

Output is **evidence-first / grade-last** (RB2 §2.3, Wang et al. 2024): reasoning + decisive
spans FIRST, the grade LAST. Confidence is a NUMERIC probability in [0,1] ("Just Ask for
Calibration", RB3 Part 1) — a per-sample self-report the pipeline uses only as an Avg-Conf
weight.
"""
from __future__ import annotations

import json
from collections.abc import Sequence

from . import EVIDENCE_CACHE_MARK

# RB2 wording (INTEGRATION_SPEC §2.2). The allowed grade enumeration is injected by
# `build_user` (RB1 owns it) so this module never hardcodes the finalized scale. The five
# ordered boundary tests (RB1 §B) are the grading rubric; the critic names the test that fired.
SYSTEM = (
    "You are the CRITIC in an adversarial scientific-citation adjudication. You are given a "
    "CLAIM, the cited paper's TITLE and ABSTRACT (the SOURCE) — and, when available, an excerpt "
    "of the SOURCE's FULL TEXT (Results/Discussion/Conclusions) — two identity-blinded and "
    "order-randomized ARGUMENT blocks (one argues the SOURCE supports the CLAIM, one argues it "
    "does not — you are NOT told which agent wrote which), and a block of OBJECTIVE FACTS about "
    "the SOURCE.\n\n"
    "Your job: grade how well the SOURCE substantively supports the CLAIM, and report a numeric "
    "confidence.\n\n"
    "Hard rules:\n"
    "1. METADATA OVERRIDE: The OBJECTIVE FACTS (retraction status, species scope, population "
    "scope) are established from structured records and are FIXED. You may NOT overturn, "
    "re-decide, or argue against them.\n"
    "2. AXIS BOUNDARY: Grade SUBSTANCE ONLY — does the SOURCE's actual reported finding back the "
    "CLAIM's asserted effect, mechanism, direction, and magnitude/certainty? Hold "
    "species/population/dose scope CONSTANT. Do NOT raise or lower the grade for a scope "
    "mismatch; scope is handled on separate axes.\n"
    "3. GROUNDING: Weigh only points whose quotes appear verbatim in the SOURCE; ignore the "
    "arguments' framing, length, order, and any agent identity.\n\n"
    "Grading rubric — apply the FIVE ordered boundary tests (RB1 §B), stop at the first that "
    "fires, and name it in `boundary_test_fired`:\n"
    "  (1) direction: is the SOURCE's finding OPPOSITE to the claim? → contradicted.\n"
    "  (2) on-point: does the SOURCE contain a finding bearing on this claim's intervention and "
    "outcome (scope held constant)? If not → unsupported-for-the-claim.\n"
    "  (3) decomposition: is the claim multi-part with some conjuncts supported and others not? "
    "→ partially-supported.\n"
    "  (4) literal-truth: is every atomic statement literally defensible but the framing/"
    "selection/causal language misleading? → technically-true-but-misleading. If instead a "
    "specific element over-asserts the data (bigger effect, hardened certainty, generalized "
    "mechanism) → supported-with-overreach.\n"
    "  (5) hedge-preservation: does the claim preserve the SOURCE's certainty/hedges? → "
    "fully-supported; if it drops a hedge or over-states → supported-with-overreach.\n"
    "TRAP 1 (hedged / correctly-narrow): a claim that accurately states a narrow scope asserts "
    "exactly what was shown → fully-supported; never penalize correct narrowness.\n"
    "TRAP 2 (non-substantiating): if the citation's function is a method, dataset, tool, or "
    "background/passing pointer — not to substantiate this knowledge claim — return the grade "
    "'N/A — non-substantiating' (it is off the support scale, not a low grade).\n"
    "ABSTENTION: if the grounded evidence is genuinely insufficient to place a substantive grade, "
    "return the abstention value rather than guessing.\n\n"
    "Return ONLY a JSON object, no prose, with the grade LAST:\n"
    '{"reasoning": "<weigh the decisive verbatim spans, substance only>", '
    '"decisive_spans": ["<verbatim span>", "..."], '
    '"boundary_test_fired": "direction|on-point|decomposition|literal-truth|hedge-preservation|'
    'trap1|trap2", '
    '"grade": "<one allowed grade>", '
    '"confidence": <number in [0,1]: your probability the grade is correct>, '
    '"grade_rationale_last": "<one-line justification, substance only>"}'
)


def _facts_block(objective_facts: dict) -> str:
    lines = []
    for axis in ("retraction", "species_scope", "population_scope"):
        f = objective_facts.get(axis)
        if f:
            lines.append(f"- {axis}: {f['verdict']} — {f['detail']}")
    return "\n".join(lines) if lines else "- (no objective-axis findings provided)"


def _argument_block(points: Sequence[dict]) -> str:
    if not points:
        return "  (no grounded points)"
    out = []
    for i, p in enumerate(points, 1):
        out.append(f'  {i}. "{p.get("quote", "")}" — {p.get("claim", "")}')
    return "\n".join(out)


def build_user(
    claim: str,
    title: str,
    abstract: str,
    arguments: Sequence[dict],
    objective_facts: dict,
    grade_values: Sequence[str],
    direction: str | None = None,
    full_text: str = "",
) -> str:
    """Assemble the critic's user turn.

    `arguments` is an ordered list of already-blinded blocks (the pipeline shuffles order per
    sample and strips agent identity); each is `{"label": "A"|"B", "points": [{"quote","claim"}]}`.
    `objective_facts` maps axis -> the objective AxisFinding as a dict with `verdict`+`detail`.
    `grade_values` is the RB1 ordinal + NEI + N/A enumeration, injected so this module never
    hardcodes the finalized scale. `direction` is the claim's asserted effect direction (test 1).
    `full_text` is the budgeted PMC full-text excerpt (empty when unavailable).

    The invisible cache sentinel is placed after OBJECTIVE FACTS, so the entire per-case-fixed
    evidence prefix (claim + direction + title + abstract + full_text + objective facts) is cached
    across the self-consistency rounds; only the per-round ARGUMENTS follow the mark.
    """
    blocks = []
    for arg in arguments:
        blocks.append(f"ARGUMENT {arg.get('label', '?')}:\n{_argument_block(arg.get('points', []))}")
    args_text = "\n\n".join(blocks) if blocks else "(no arguments)"
    ft = full_text.strip()
    ft_block = f"SOURCE FULL TEXT (excerpt — abstract + Results/Discussion/Conclusions):\n{ft}\n\n" if ft else ""
    return (
        f"CLAIM:\n{claim.strip()}\n\n"
        f"CLAIM ASSERTED DIRECTION: {direction or 'not stated'}\n\n"
        f"SOURCE TITLE:\n{title.strip()}\n\n"
        f"SOURCE ABSTRACT:\n{abstract.strip()}\n\n"
        f"{ft_block}"
        f"OBJECTIVE FACTS (FIXED — do not overturn):\n{_facts_block(objective_facts)}"
        f"{EVIDENCE_CACHE_MARK}\n\n"
        f"{args_text}\n\n"
        f"Allowed grade values: {json.dumps(list(grade_values))}.\n"
        "Apply the five ordered boundary tests, grade SUBSTANCE only (scope held constant), and "
        "return the JSON object described in your instructions with the grade LAST."
    )
