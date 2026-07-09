"""C4-stub — correctly-shaped adjudication.

Objective axes (retraction, species/population scope) are computed FOR REAL from
metadata — they are legitimately objective and need no model. The graded
substantive-support axis is deliberately returned as NOT_ADJUDICATED: faking it is
exactly the failure this system exists to detect. The full adversarial
supporter/refuter/critic agent fills that axis in the depth phase, behind this same
Verdict contract.

Metadata-override is enforced: the cited-paper metadata is authoritative; a
model/text-inferred claim value never overrides it.
"""
from __future__ import annotations

from .contracts import AxisFinding, GroundedRecord, ScopeFrame, Verdict

PED_DESCRIPTORS = {"Child", "Child, Preschool", "Infant", "Infant, Newborn", "Adolescent"}
ADULT_DESCRIPTORS = {"Adult", "Aged", "Middle Aged", "Aged, 80 and over", "Young Adult"}


def _retraction_axis(g: GroundedRecord) -> AxisFinding:
    r = g.retraction
    ev = {
        "retraction_watch": {
            "present": bool(r.retraction_watch and r.retraction_watch.present),
            "record_id": r.retraction_watch.rw_record_id if r.retraction_watch else None,
            "reason": r.retraction_watch.reason if r.retraction_watch else None,
            "date": r.retraction_watch.date if r.retraction_watch else None,
        },
        "ncbi_publication_type_flag": r.ncbi_publication_type_flag,
        "ncbi_comments_corrections": [c.ref_type for c in r.comments_corrections],
        "source_agreement": r.source_agreement,
    }
    if r.status == "RETRACTED":
        return AxisFinding("retraction", "RELIES_ON_RETRACTED", "high", "metadata-grounded",
                           "Cited paper is retracted per structured records; a claim resting on it "
                           "inherits the retraction.", ev)
    if r.status == "EXPRESSION_OF_CONCERN":
        return AxisFinding("retraction", "CITED_PAPER_HAS_EOC", "high", "metadata-grounded",
                           "Cited paper carries an Expression of Concern (NCBI linkage).", ev)
    return AxisFinding("retraction", "NOT_RETRACTED", "high", "metadata-grounded",
                       "No retraction found in Retraction Watch or NCBI records.", ev)


def _species_axis(g: GroundedRecord, scope: ScopeFrame) -> AxisFinding:
    cited = [t.descriptor for t in g.organism_tags]
    cited_ev = {"cited_organism_tags": [{"descriptor": t.descriptor, "tree_numbers": t.tree_numbers}
                                        for t in g.organism_tags],
                "cited_has_humans": g.has_humans,
                "claim_organism": scope.organism,
                "claim_organism_provenance": scope.provenance,
                "claim_evidence": scope.organism_evidence}
    composite = f"metadata-grounded (cited) + {scope.provenance} (claim)"
    if scope.organism is None:
        return AxisFinding("species_scope", "CLAIM_SCOPE_UNSTATED", "low", scope.provenance,
                           "Claim does not explicitly assert an organism scope; not flaggable "
                           "without the deeper (Opus) scope parse.", cited_ev)
    if scope.organism == "Humans":
        if g.has_humans:
            return AxisFinding("species_scope", "SCOPE_CONSISTENT", "medium", composite,
                               f"Claim asserts human scope; cited paper MeSH organism scope "
                               f"includes Humans ({cited}).", cited_ev)
        return AxisFinding("species_scope", "SCOPE_MISMATCH", "medium", composite,
                           f"Claim asserts human/clinical relevance, but cited paper MeSH organism "
                           f"scope is {cited} with 'Humans' ABSENT — the human claim is not supported "
                           f"by this animal study. Metadata authoritative.", cited_ev)
    # claim asserts an animal organism
    if scope.organism in cited or (not g.has_humans and scope.organism == "Animals"):
        return AxisFinding("species_scope", "SCOPE_CONSISTENT", "medium", composite,
                           f"Claim asserts {scope.organism}; consistent with cited organism scope "
                           f"{cited}.", cited_ev)
    return AxisFinding("species_scope", "SCOPE_UNCERTAIN", "low", composite,
                       f"Claim asserts {scope.organism}; cited organism scope is {cited}. "
                       f"Relationship not determinable at slice depth.", cited_ev)


def _population_axis(g: GroundedRecord, scope: ScopeFrame) -> AxisFinding:
    cited_pop = [t.descriptor for t in g.population_tags]
    ev = {"cited_population_tags": cited_pop, "claim_population": scope.population,
          "claim_evidence": scope.population_evidence}
    if scope.population is None or not cited_pop:
        return AxisFinding("population_scope", "NOT_ASSESSED", "low", "model-inferred",
                           "No explicit population marker in the claim, or no population MeSH on the "
                           "cited paper; population axis not assessed at slice depth.", ev)
    cited_is_ped = any(d in PED_DESCRIPTORS for d in cited_pop)
    cited_is_adult = any(d in ADULT_DESCRIPTORS for d in cited_pop)
    composite = f"metadata-grounded (cited) + {scope.provenance} (claim)"
    if scope.population == "pediatric" and cited_is_adult and not cited_is_ped:
        return AxisFinding("population_scope", "SCOPE_MISMATCH", "medium", composite,
                           f"Claim asserts pediatric scope; cited population MeSH is adult-only "
                           f"({cited_pop}). Metadata authoritative.", ev)
    if scope.population == "adult" and cited_is_ped and not cited_is_adult:
        return AxisFinding("population_scope", "SCOPE_MISMATCH", "medium", composite,
                           f"Claim asserts adult scope; cited population MeSH is pediatric-only "
                           f"({cited_pop}). Metadata authoritative.", ev)
    return AxisFinding("population_scope", "SCOPE_CONSISTENT", "medium", composite,
                       f"Claim population ({scope.population}) consistent with cited "
                       f"population MeSH ({cited_pop}).", ev)


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
    findings = [_retraction_axis(g), _species_axis(g, scope),
                _population_axis(g, scope), _substantive_axis()]
    unverifiable = {
        "dose": ("Claim states a dose; PubMed has no structured dose field, so verifying it against "
                 "the cited paper needs full-text extraction — flagged, not scored."
                 if scope.dose_stated else
                 "No dose asserted in the claim; not applicable."),
        "effect_direction": ("Whether the claim's effect direction matches the cited paper's reported "
                             "result requires reading the Results text; no structured field. Deferred "
                             "to the adjudication agent."),
    }
    return Verdict(
        claim=claim_text,
        cited_identifier=g.identifier,
        overall=_overall(findings),
        axis_findings=findings,
        unverifiable_axes=unverifiable,
        stub=True,
        notes=["Cited-paper metadata is authoritative on objective axes; a model/text-inferred "
               "claim value never overrides it (metadata-override rule).",
               "Objective axes (retraction, scope) are real; substantive support is a stub."],
    )
