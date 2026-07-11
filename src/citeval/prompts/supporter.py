"""Supporter role — builds the strongest evidence-grounded case FOR support.

RB2 wording (INTEGRATION_SPEC §2.1). The pipeline enforces the verbatim guard after the
model returns: every `quote` must be a whitespace-normalized substring of the cited
grounding corpus (title + abstract) or the point is discarded and counted. The prompt
asks for strongest-first ordering so the pipeline's first survivor is the headline span.

The supporter must keep `quote` + `rationale` on every point (the §6 headline reads them).
`claim_component` is an optional RB2 add (which asserted element the point substantiates).
Trap 1 / Trap 2 awareness (INTEGRATION_SPEC §1.5) is stated so the supporter does not
manufacture support for a hedged/correctly-narrow claim or a passing/method citation.
"""
from __future__ import annotations

from . import EVIDENCE_CACHE_MARK

# RB2 (INTEGRATION_SPEC §2.1). The supporter is an advocate, not a judge: it must not grade,
# and must ground every point in a verbatim quote so the verbatim guard can verify it.
SYSTEM = (
    "You are the SUPPORTER in an adversarial scientific-citation adjudication. You are given a "
    "CLAIM and the cited paper's TITLE and ABSTRACT (the SOURCE), and — when available — an "
    "excerpt of the SOURCE's FULL TEXT (Results/Discussion/Conclusions). Build the STRONGEST "
    "honest, evidence-grounded case that the SOURCE substantively supports the CLAIM's asserted "
    "effect, mechanism, direction, and magnitude/certainty.\n\n"
    "Hard rules:\n"
    "- Every point MUST quote a VERBATIM span copied exactly from the SOURCE title, abstract, or "
    "full-text excerpt. Do not paraphrase inside `quote`; copy characters exactly. Points without "
    "a verbatim quote are discarded.\n"
    "- Judge SUBSTANCE only. Do NOT argue about species/population/dose scope — that is handled "
    "on separate metadata axes, not by you. A claim that correctly states a narrow scope "
    "(\"in mice\", \"whether this holds in humans is unknown\") asserts exactly what was shown; "
    "do not treat that narrowness as weakness.\n"
    "- If the CLAIM merely cites the SOURCE for a method, dataset, tool, or background pointer "
    "(not to substantiate a knowledge claim), say so in a point's rationale — such a citation is "
    "not substantiated on the support scale.\n"
    "- Do NOT assign a grade or verdict. You only marshal supporting evidence.\n"
    "- If the SOURCE offers no genuine support, return an empty points list rather than inventing "
    "support.\n"
    "- Order points strongest-first.\n\n"
    "Return ONLY a JSON object, no prose:\n"
    '{"points": [{"quote": "<verbatim span from SOURCE>", "rationale": "<why it supports the '
    'claim>", "claim_component": "<the asserted element it substantiates, optional>"}]}'
)


def build_user(claim: str, title: str, abstract: str, full_text: str = "") -> str:
    """Assemble the supporter's user turn from the claim and cited-source text.

    `full_text` is the budgeted PMC full-text excerpt (empty when unavailable). When present it is
    added as a clearly delimited evidence segment; when empty the turn is the abstract-only turn,
    byte-for-byte except for the invisible cache sentinel. The sentinel closes the reusable evidence
    block (title + abstract + full_text) so the real client caches it across rounds."""
    ft = full_text.strip()
    ft_block = f"\n\nSOURCE FULL TEXT (excerpt — abstract + Results/Discussion/Conclusions):\n{ft}" if ft else ""
    source_span = "title, abstract, or full-text excerpt" if ft else "title or abstract"
    return (
        f"CLAIM:\n{claim.strip()}\n\n"
        f"SOURCE TITLE:\n{title.strip()}\n\n"
        f"SOURCE ABSTRACT:\n{abstract.strip()}"
        f"{ft_block}"
        f"{EVIDENCE_CACHE_MARK}\n\n"
        f"Return the JSON object described in your instructions. Quotes must be copied verbatim "
        f"from the SOURCE {source_span} above."
    )
