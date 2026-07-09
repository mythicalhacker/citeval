"""C4-stub — correctly-shaped adjudication.

Objective axes (retraction, species/population scope) are computed FOR REAL from
metadata — they are legitimately objective and need no model. The graded
substantive-support axis is deliberately returned as NOT_ADJUDICATED: faking it is
exactly the failure this system exists to detect. The full adversarial
supporter/refuter/critic agent fills that axis in the depth phase, behind this same
Verdict contract.

Metadata-override is enforced: the cited-paper metadata is authoritative; a
model/text-inferred claim value never overrides it. The objective-axis logic now
lives in `objective_axes.py` (shared single source of truth); this module keeps only
the stub-specific substantive placeholder and rollup so the offline slice stays green.
"""
from __future__ import annotations

from .contracts import AxisFinding, GroundedRecord, ScopeFrame, Verdict
from .objective_axes import (
    build_unverifiable_axes,
    population_axis,
    retraction_axis,
    species_axis,
)


def _substantive_axis() -> AxisFinding:
    return AxisFinding("substantive_support", "NOT_ADJUDICATED", "n/a", "stub-not-adjudicated",
                       "Graded claim-support (fully-supported ... contradicted) is inherently a "
                       "judgement and is produced only by the adversarial supporter/refuter/critic "
                       "agent with its calibration mechanism (component 4, depth phase). The slice "
                       "does not fake it.")


def _overall(findings: list[AxisFinding]) -> str:
    by = {f.axis: f for f in findings}
    parts = []
    if by["retraction"].verdict == "RELIES_ON_RETRACTED":
        parts.append("CITATION RELIES ON A RETRACTED PAPER")
    elif by["retraction"].verdict == "CITED_PAPER_HAS_EOC":
        parts.append("CITED PAPER HAS AN EXPRESSION OF CONCERN")
    if by["species_scope"].verdict == "SCOPE_MISMATCH":
        parts.append("CLAIM NOT SUPPORTED (species scope mismatch)")
    if by.get("population_scope") and by["population_scope"].verdict == "SCOPE_MISMATCH":
        parts.append("CLAIM NOT SUPPORTED (population scope mismatch)")
    if not parts:
        return ("NO OBJECTIVE-AXIS PROBLEM DETECTED — substantive support not yet "
                "adjudicated (stub)")
    return " + ".join(parts)


def adjudicate_stub(g: GroundedRecord, scope: ScopeFrame, claim_text: str = "") -> Verdict:
    findings = [retraction_axis(g), species_axis(g, scope),
                population_axis(g, scope), _substantive_axis()]
    return Verdict(
        claim=claim_text,
        cited_identifier=g.identifier,
        overall=_overall(findings),
        axis_findings=findings,
        unverifiable_axes=build_unverifiable_axes(scope),
        stub=True,
        notes=["Cited-paper metadata is authoritative on objective axes; a model/text-inferred "
               "claim value never overrides it (metadata-override rule).",
               "Objective axes (retraction, scope) are real; substantive support is a stub."],
    )
