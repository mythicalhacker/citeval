"""Prompt library for the C4 adversarial adjudicator (supporter / refuter / critic).

Prompt **wording** is PROVISIONAL — RB2 finalizes it. The grade **vocabulary** is
PROVISIONAL — RB1 finalizes it (see CONTEXT_PACK §3). Both live *only* here so the
research drops in without touching `adjudicator.py`'s pipeline wiring: the pipeline
imports `SYSTEM` strings, `build_user()` builders, and this vocabulary by name and
never inlines wording or grade boundaries.

Each role module exposes:
- `SYSTEM: str`               — the system prompt (PROVISIONAL, RB2).
- `build_user(...) -> str`    — assembles the user turn from typed inputs.
"""
from __future__ import annotations

from . import critic, refuter, supporter

# --- RB1 grade scale (PROVISIONAL — RB1 finalizes; keep swappable) -----------------
# The 6-level substantive-support ordinal, worst→best-separated as an ordered tuple so
# adjacent-tolerant (±1) scoring downstream has a defined order. CONTEXT_PACK §3.
RB1_GRADES: tuple[str, ...] = (
    "fully-supported",
    "supported-with-overreach",
    "partially-supported",
    "technically-true-but-misleading",
    "unsupported",
    "contradicted",
)

# Abstention value (RB3 defines exactly when it fires; the interface lands now).
NOT_ENOUGH_INFO = "NOT_ENOUGH_INFO"

# Everything the critic may legally return as a grade.
GRADE_VALUES: tuple[str, ...] = (*RB1_GRADES, NOT_ENOUGH_INFO)

# Verbalized-confidence vocabulary the critic self-reports (recalibrated by RB3).
VERBALIZED_CONFIDENCE: tuple[str, ...] = ("high", "medium", "low")

__all__ = [
    "supporter",
    "refuter",
    "critic",
    "RB1_GRADES",
    "NOT_ENOUGH_INFO",
    "GRADE_VALUES",
    "VERBALIZED_CONFIDENCE",
]
