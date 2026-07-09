"""Objective-axis adjudication — the metadata-grounded, model-free axes.

Single source of truth for the three **objective** axes (retraction, species scope,
population scope) plus the `unverifiable_axes` construction. These axes are decided
entirely by C2's structured metadata and are the mechanical enforcement of the
system's first invariant — *metadata overrides model*: a model/text-inferred claim
value never overturns a structured record; a conflict is scored as the model being
wrong (CLAUDE.md invariant #1, CONTEXT_PACK §2).

Both the thin-slice stub (`adjudicator_stub`) and the depth adversarial adjudicator
(`adjudicator`) import from here, so the objective verdicts are provably identical no
matter which adjudicator runs — and this module survives the stub's eventual
retirement. The adversarial supporter/refuter/critic pipeline reasons *only* about
the graded `substantive_support` axis; it is given these findings as fixed facts it
may not overturn.

Extracted verbatim from `adjudicator_stub.py` (behaviour-preserving refactor,
WO-C4 "Manager decisions" 2026-07-09). Do not change the objective-axis logic here
without treating it as a C2/contract-adjacent change.
"""
from __future__ import annotations

from .contracts import AxisFinding, GroundedRecord, ScopeFrame

# MeSH age-group descriptors used to decide pediatric/adult population scope.
PED_DESCRIPTORS = {"Child", "Child, Preschool", "Infant", "Infant, Newborn", "Adolescent"}
ADULT_DESCRIPTORS = {"Adult", "Aged", "Middle Aged", "Aged, 80 and over", "Young Adult"}


def retraction_axis(g: GroundedRecord) -> AxisFinding:
    """Retraction axis — decided by structured Retraction Watch + NCBI records."""
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


def species_axis(g: GroundedRecord, scope: ScopeFrame) -> AxisFinding:
    """Species-scope axis — cited-paper MeSH organism tags vs the claim's asserted organism.

    Composite provenance: metadata-grounded on the cited side, claim-side provenance
    (typically model-inferred, from C3) on the claim side. The metadata is authoritative.
    """
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


def population_axis(g: GroundedRecord, scope: ScopeFrame) -> AxisFinding:
    """Population-scope axis — cited-paper age-group MeSH vs the claim's asserted population."""
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


def build_unverifiable_axes(scope: ScopeFrame) -> dict:
    """Axes that PubMed metadata cannot verify — flagged, never fabricated (invariant #3)."""
    return {
        "dose": ("Claim states a dose; PubMed has no structured dose field, so verifying it against "
                 "the cited paper needs full-text extraction — flagged, not scored."
                 if scope.dose_stated else
                 "No dose asserted in the claim; not applicable."),
        "effect_direction": ("Whether the claim's effect direction matches the cited paper's reported "
                             "result requires reading the Results text; no structured field. Deferred "
                             "to the adjudication agent."),
    }
