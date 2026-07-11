"""Prompt library for the C4 adversarial adjudicator (supporter / refuter / critic).

Prompt **wording** follows RB2; the grade **vocabulary** follows RB1 (INTEGRATION_SPEC §1).
Both live *only* here so the finalized research drops in without touching `adjudicator.py`'s
pipeline wiring: the pipeline imports `SYSTEM` strings, `build_user()` builders, and this
vocabulary by name and never inlines wording or grade boundaries.

Each role module exposes:
- `SYSTEM: str`               — the system prompt (RB2).
- `build_user(...) -> str`    — assembles the user turn from typed inputs.
"""
from __future__ import annotations

from . import critic, refuter, supporter

# --- RB1 ordinal grade scale (INTEGRATION_SPEC §1; a1) -----------------------------
# The 6-level substantive-support ordinal, index 0 (best) → 5 (worst). This ordering is
# the RB3 index convention and is canonical for ±1-adjacency and quadratic-weighted kappa
# (CONFLICT-2). grade-1 was relabeled `unsupported` → `unsupported-for-the-claim` (a1).
RB1_GRADES: tuple[str, ...] = (
    "fully-supported",
    "supported-with-overreach",
    "partially-supported",
    "technically-true-but-misleading",
    "unsupported-for-the-claim",
    "contradicted",
)

# The gradeable ordinal (alias for clarity where an *ordinal* index is required — QWK,
# ±1 adjacency, median-aware voting). NEI / N/A are NOT on this ordinal.
ORDINAL_GRADES: tuple[str, ...] = RB1_GRADES
ORDINAL_INDEX: dict[str, int] = {g: i for i, g in enumerate(ORDINAL_GRADES)}

# Abstention value (RB3 owns the firing rule).
NOT_ENOUGH_INFO = "NOT_ENOUGH_INFO"

# Trap 2 (INTEGRATION_SPEC §1.5): a method / background / passing citation is out of scope
# for support grading. Distinct from a grade and from NEI-abstention — the rollup + scorer
# treat it as non-graded (excluded from grading metrics), with its own reason.
NON_SUBSTANTIATING = "N/A — non-substantiating"

# Everything the critic may legally return as a grade (the 6 ordinal + the two non-graded
# outcomes). Values outside this set are treated as junk and dropped in aggregation.
GRADE_VALUES: tuple[str, ...] = (*RB1_GRADES, NOT_ENOUGH_INFO, NON_SUBSTANTIATING)

# The two non-graded critic outcomes (recognized, but never placed on the ordinal scale).
NON_GRADED_VALUES: tuple[str, ...] = (NOT_ENOUGH_INFO, NON_SUBSTANTIATING)

# §6 `confidence.verbalized` tier vocabulary — the categorical confidence tier C5 renders
# (reporting.py `_confidence_text`). NOTE (a2 reconciliation): the *critic's own* self-report
# is now a NUMERIC probability in [0,1] ("Just Ask for Calibration"), consumed only as an
# Avg-Conf weight (RB3 Part 1); this categorical vocab is the emitted **tier**, sourced from
# the self-consistency agreement, NOT a model self-report. Keeping it here keeps the §6
# rendering contract with C5 unchanged.
VERBALIZED_CONFIDENCE: tuple[str, ...] = ("high", "medium", "low")

__all__ = [
    "supporter",
    "refuter",
    "critic",
    "RB1_GRADES",
    "ORDINAL_GRADES",
    "ORDINAL_INDEX",
    "NOT_ENOUGH_INFO",
    "NON_SUBSTANTIATING",
    "NON_GRADED_VALUES",
    "GRADE_VALUES",
    "VERBALIZED_CONFIDENCE",
]
