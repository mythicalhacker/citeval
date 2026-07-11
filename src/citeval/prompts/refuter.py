"""Refuter role — builds the strongest evidence-grounded case AGAINST support.

RB2 wording (INTEGRATION_SPEC §2.1/§2.2). The refuter hunts SUBSTANTIVE distortion
(direction reversal, magnitude inflation, cherry-picking, mechanism mismatch, overstated
certainty, no evidence for support). It MAY *note* scope over-generalization, but scope is
graded on the metadata scope axes, not here — so every point declares a **`routes_to`**:
`grade` (a substantive objection the critic may weigh) or `rollup_not_grade` (scope
over-generalization, carried by `overall` only). The pipeline **hard-filters
`rollup_not_grade` points before the critic sees them** (adjudicator b6), so scope can
never depress the graded number (CONTEXT_PACK §6). Same verbatim guard as the supporter.
"""
from __future__ import annotations

from typing import Optional

# RB2 distortion taxonomy (INTEGRATION_SPEC §2.1). `over_generalization` is *notable but
# not graded* — it routes to `overall` via the swappable rollup, never into the grade.
DISTORTION_TYPES: tuple[str, ...] = (
    "direction_reversal",
    "magnitude_inflation",
    "cherry_picking",
    "mechanism_mismatch",
    "over_certainty",
    "over_generalization",       # ⇒ routes_to="rollup_not_grade" (scope; graded on metadata axes)
    "no_evidence_for_support",
)

# Where a refuter point is allowed to act. `rollup_not_grade` points are recorded but never
# reach the critic / the vote (the pipeline enforces this structurally, not by wording).
ROUTES: tuple[str, ...] = ("grade", "rollup_not_grade")

# Overall pressure the refuter's grade-routed evidence puts on support (C01 fabrication canary:
# strong pressure on a clean control signals a manufactured objection).
GRADE_PRESSURE: tuple[str, ...] = ("none", "mild", "strong")

# RB2 (INTEGRATION_SPEC §2.1).
SYSTEM = (
    "You are the REFUTER in an adversarial scientific-citation adjudication. You are given a "
    "CLAIM and the cited paper's TITLE and ABSTRACT (the SOURCE), and the effect DIRECTION the "
    "claim asserts. Build the STRONGEST honest, evidence-grounded case that the SOURCE does NOT "
    "substantively support the CLAIM.\n\n"
    "Hard rules:\n"
    "- Every point MUST quote a VERBATIM span copied exactly from the SOURCE title or abstract. "
    "Copy characters exactly; do not paraphrase inside `quote`. Points without a verbatim quote "
    "are discarded.\n"
    "- DIRECTION-REVERSAL PROBE: if the SOURCE's reported finding runs OPPOSITE to the claimed "
    "direction, that is the strongest objection — tag it `direction_reversal`.\n"
    "- Judge SUBSTANCE, holding scope constant. You MAY flag species/population/dose "
    "over-generalization, but ONLY as `over_generalization` with `routes_to`=\"rollup_not_grade\" — "
    "it is scored on separate metadata axes, so never let scope drive a substantive objection.\n"
    "- Every point sets `routes_to`: \"grade\" for a substantive objection, or \"rollup_not_grade\" "
    "for scope over-generalization. Only \"grade\" points can affect the support grade.\n"
    "- Do NOT assign a grade or verdict. You only marshal refuting evidence.\n"
    "- If the SOURCE has no genuine substantive weakness, return an empty points list rather than "
    "manufacturing an objection.\n"
    "- Order points strongest-first.\n\n"
    "Return ONLY a JSON object, no prose:\n"
    '{"points": [{"quote": "<verbatim span from SOURCE>", "objection": "<why it fails to support '
    'the claim>", "distortion_type": "<one of the allowed tags>", "routes_to": "grade | '
    'rollup_not_grade", "targets_support_point": <int index or null>}], '
    '"most_severe_distortion": "<tag or null>", "refuter_grade_pressure": "none | mild | strong"}'
)


def build_user(claim: str, title: str, abstract: str, direction: Optional[str] = None) -> str:
    """Assemble the refuter's user turn from the claim, cited-source text, and the claim's
    asserted effect `direction` (from `ScopeFrame.direction`; used for the direction-reversal
    probe). `direction` is None when C3 could not ground one."""
    dir_line = direction if direction else "not stated"
    return (
        f"CLAIM:\n{claim.strip()}\n\n"
        f"CLAIM ASSERTED DIRECTION: {dir_line}\n\n"
        f"SOURCE TITLE:\n{title.strip()}\n\n"
        f"SOURCE ABSTRACT:\n{abstract.strip()}\n\n"
        f"Allowed distortion_type tags: {', '.join(DISTORTION_TYPES)}.\n"
        f"Allowed routes_to values: {', '.join(ROUTES)}.\n"
        "Return the JSON object described in your instructions. Quotes must be copied verbatim "
        "from the SOURCE title or abstract above."
    )
