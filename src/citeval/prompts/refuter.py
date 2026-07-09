"""Refuter role — builds the strongest evidence-grounded case AGAINST support.

PROVISIONAL wording (RB2 finalizes). The refuter hunts SUBSTANTIVE failure modes
(direction reversal, magnitude inflation, cherry-picking, unsupported mechanism). It
MAY *note* scope over-generalization, but scope is graded on the metadata scope axes,
not here — the pipeline records a noted scope objection but never lets it depress the
graded substantive number (CONTEXT_PACK §6). Same verbatim guard as the supporter.
"""
from __future__ import annotations

# Allowed failure-mode tags. `scope_overgeneralization` is *notable but not graded* here —
# it flows to `overall` via the swappable rollup, never into the substantive grade.
FAILURE_MODES: tuple[str, ...] = (
    "direction_reversal",
    "magnitude_inflation",
    "cherry_picking",
    "unsupported_mechanism",
    "certainty_overstatement",
    "scope_overgeneralization",  # NOTED ONLY — graded on the metadata scope axes, not here
    "other",
)

# PROVISIONAL (RB2).
SYSTEM = (
    "You are the REFUTER in an adversarial scientific-citation adjudication. You are given a "
    "CLAIM and the cited paper's TITLE and ABSTRACT (the SOURCE). Build the STRONGEST honest, "
    "evidence-grounded case that the SOURCE does NOT substantively support the CLAIM — hunt for "
    "direction reversal, magnitude inflation, cherry-picking, unsupported mechanism, and "
    "overstated certainty.\n\n"
    "Hard rules:\n"
    "- Every point MUST quote a VERBATIM span copied exactly from the SOURCE title or abstract. "
    "Copy characters exactly; do not paraphrase inside `quote`. Points without a verbatim quote "
    "are discarded.\n"
    "- Judge SUBSTANCE, holding scope constant. You MAY flag species/population/dose "
    "over-generalization, but ONLY tag it `scope_overgeneralization` — it is scored on separate "
    "metadata axes, so never let scope drive a substance objection.\n"
    "- Do NOT assign a grade or verdict. You only marshal refuting evidence.\n"
    "- If the SOURCE has no genuine substantive weakness, return an empty points list rather than "
    "manufacturing an objection.\n"
    "- Order points strongest-first.\n\n"
    "Return ONLY a JSON object, no prose:\n"
    '{"points": [{"quote": "<verbatim span from SOURCE>", "objection": "<why it fails to support '
    'the claim>", "failure_mode": "<one of the allowed tags>"}]}'
)


def build_user(claim: str, title: str, abstract: str) -> str:
    """Assemble the refuter's user turn from the claim and cited-source text."""
    return (
        f"CLAIM:\n{claim.strip()}\n\n"
        f"SOURCE TITLE:\n{title.strip()}\n\n"
        f"SOURCE ABSTRACT:\n{abstract.strip()}\n\n"
        f"Allowed failure_mode tags: {', '.join(FAILURE_MODES)}.\n"
        "Return the JSON object described in your instructions. Quotes must be copied verbatim "
        "from the SOURCE title or abstract above."
    )
