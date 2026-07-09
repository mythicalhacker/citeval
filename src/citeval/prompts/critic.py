"""Critic role — maps the grounded supporter/refuter exchange to an RB1 grade + confidence.

PROVISIONAL wording (RB2 finalizes); grade vocabulary is injected by the pipeline
(RB1 finalizes it). The critic is run N times over the SAME fixed grounded evidence
(self-consistency, CONTEXT_PACK §7); the pipeline aggregates modal grade + agreement.

Two hard constraints are injected into the prompt and enforced structurally by the
pipeline regardless of what the model says:
1. METADATA OVERRIDE — the objective facts (retraction, species/population scope) are
   fixed; the critic may not overturn them (CLAUDE.md invariant #1).
2. AXIS BOUNDARY — grade SUBSTANCE only, holding scope constant; scope over-reach is
   carried by the metadata scope axes and folded into `overall` by a swappable rollup,
   never by depressing this grade (CONTEXT_PACK §6).
"""
from __future__ import annotations

import json
from collections.abc import Sequence

# PROVISIONAL (RB2). The concrete allowed grade/confidence enumerations are injected by
# `build_user` so RB1's finalized scale slots in without editing this wording.
SYSTEM = (
    "You are the CRITIC in an adversarial scientific-citation adjudication. You are given a "
    "CLAIM, the cited paper's TITLE and ABSTRACT (the SOURCE), the SUPPORTER's grounded points, "
    "the REFUTER's grounded points, and a block of OBJECTIVE FACTS about the SOURCE.\n\n"
    "Your job: grade how well the SOURCE substantively supports the CLAIM, and report your "
    "confidence.\n\n"
    "Hard rules:\n"
    "1. METADATA OVERRIDE: The OBJECTIVE FACTS (retraction status, species scope, population "
    "scope) are established from structured records and are FIXED. You may NOT overturn, "
    "re-decide, or argue against them. Treat them as ground truth.\n"
    "2. AXIS BOUNDARY: Grade SUBSTANCE ONLY — does the SOURCE's actual reported finding back the "
    "CLAIM's asserted effect, mechanism, direction, and magnitude/certainty? Hold "
    "species/population/dose scope CONSTANT. Do NOT raise or lower the grade because of a scope "
    "mismatch; scope is handled on separate axes. A scope objection from the refuter is context, "
    "not a reason to downgrade substance.\n"
    "3. GROUNDING: Weigh only points backed by verbatim SOURCE quotes.\n"
    "4. ABSTENTION: If the grounded evidence is genuinely insufficient to place a substantive "
    "grade, return the abstention value rather than guessing.\n\n"
    "Return ONLY a JSON object, no prose:\n"
    '{"grade": "<one allowed grade>", "confidence": "<allowed confidence>", '
    '"rationale": "<one-line justification, substance only>"}'
)


def _facts_block(objective_facts: dict) -> str:
    lines = []
    for axis in ("retraction", "species_scope", "population_scope"):
        f = objective_facts.get(axis)
        if f:
            lines.append(f"- {axis}: {f['verdict']} — {f['detail']}")
    return "\n".join(lines) if lines else "- (no objective-axis findings provided)"


def _points_block(points: Sequence[dict], quote_key: str, reason_key: str) -> str:
    if not points:
        return "  (none survived the verbatim guard)"
    out = []
    for i, p in enumerate(points, 1):
        out.append(f'  {i}. "{p.get(quote_key, "")}" — {p.get(reason_key, "")}')
    return "\n".join(out)


def build_user(
    claim: str,
    title: str,
    abstract: str,
    supporter_points: Sequence[dict],
    refuter_points: Sequence[dict],
    objective_facts: dict,
    grade_values: Sequence[str],
    confidence_values: Sequence[str],
) -> str:
    """Assemble the critic's user turn.

    `objective_facts` maps axis name -> the objective AxisFinding as a dict with at least
    `verdict` and `detail`. `grade_values` / `confidence_values` are the RB1/RB3-owned
    enumerations, injected here so this module never hardcodes the finalized scale.
    """
    return (
        f"CLAIM:\n{claim.strip()}\n\n"
        f"SOURCE TITLE:\n{title.strip()}\n\n"
        f"SOURCE ABSTRACT:\n{abstract.strip()}\n\n"
        f"OBJECTIVE FACTS (FIXED — do not overturn):\n{_facts_block(objective_facts)}\n\n"
        f"SUPPORTER POINTS (verbatim-grounded):\n"
        f"{_points_block(supporter_points, 'quote', 'rationale')}\n\n"
        f"REFUTER POINTS (verbatim-grounded):\n"
        f"{_points_block(refuter_points, 'quote', 'objection')}\n\n"
        f"Allowed grade values: {json.dumps(list(grade_values))}.\n"
        f"Allowed confidence values: {json.dumps(list(confidence_values))}.\n"
        "Grade SUBSTANCE only, holding scope constant, and return the JSON object described in "
        "your instructions."
    )
