"""Supporter role — builds the strongest evidence-grounded case FOR support.

PROVISIONAL wording (RB2 finalizes). The pipeline enforces the verbatim guard after
the model returns: every `quote` must be a whitespace-normalized substring of the
cited grounding corpus (title + abstract) or the point is discarded and counted. The
prompt asks for strongest-first ordering so the pipeline's first survivor is the
headline span.
"""
from __future__ import annotations

# PROVISIONAL (RB2). The supporter is an advocate, not a judge: it must not grade, and
# must ground every point in a verbatim quote so the verbatim guard can verify it.
SYSTEM = (
    "You are the SUPPORTER in an adversarial scientific-citation adjudication. You are given a "
    "CLAIM and the cited paper's TITLE and ABSTRACT (the SOURCE). Build the STRONGEST honest, "
    "evidence-grounded case that the SOURCE substantively supports the CLAIM's asserted effect, "
    "mechanism, direction, and magnitude/certainty.\n\n"
    "Hard rules:\n"
    "- Every point MUST quote a VERBATIM span copied exactly from the SOURCE title or abstract. "
    "Do not paraphrase inside `quote`; copy characters exactly. Points without a verbatim quote "
    "are discarded.\n"
    "- Judge SUBSTANCE only. Do NOT argue about species/population/dose scope — that is handled "
    "on separate metadata axes, not by you.\n"
    "- Do NOT assign a grade or verdict. You only marshal supporting evidence.\n"
    "- If the SOURCE offers no genuine support, return an empty points list rather than inventing "
    "support.\n"
    "- Order points strongest-first.\n\n"
    "Return ONLY a JSON object, no prose:\n"
    '{"points": [{"quote": "<verbatim span from SOURCE>", "rationale": "<why it supports the claim>"}]}'
)


def build_user(claim: str, title: str, abstract: str) -> str:
    """Assemble the supporter's user turn from the claim and cited-source text."""
    return (
        f"CLAIM:\n{claim.strip()}\n\n"
        f"SOURCE TITLE:\n{title.strip()}\n\n"
        f"SOURCE ABSTRACT:\n{abstract.strip()}\n\n"
        "Return the JSON object described in your instructions. Quotes must be copied verbatim "
        "from the SOURCE title or abstract above."
    )
