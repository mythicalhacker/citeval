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
# Pregnancy is a scope-narrow study population, but its MeSH descriptors live OUTSIDE the age tree
# (M01.060.*) — "Pregnancy" sits under G08 (reproductive physiology), "Pregnant Women" under M01.975 —
# so they never reach `population_tags` (which is keyed on M01.060.* in grounding._classify). We read
# them off the authoritative `mesh_all` instead: a claim asserting a general/adult finding cited to a
# pregnancy-only study is a population over-generalization the age-tree tags alone cannot catch.
PREGNANCY_DESCRIPTORS = {
    "Pregnancy", "Pregnant Women", "Pregnancy Trimester, First", "Pregnancy Trimester, Second",
    "Pregnancy Trimester, Third", "Pregnancy, Multiple", "Peripartum Period",
}


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
    # "general" = the claim states a broad, unqualified biological/clinical finding with no organism
    # marker and no hedge (C3's over-generalization stance). It reads as implicitly organism-general;
    # the mismatch is an over-generalization of an animal-only finding. Only flag when the cited source
    # is animal-only by MeSH (organism tags present, Humans ABSENT) — the has_humans gate keeps the
    # hard-negative controls (human claim, human paper carrying animal FP-bait tags) unflagged.
    if scope.organism == "general":
        if g.has_humans:
            return AxisFinding("species_scope", "SCOPE_CONSISTENT", "medium", composite,
                               f"Claim states a general, unqualified finding; cited paper MeSH organism "
                               f"scope includes Humans ({cited}) — not an over-generalization.", cited_ev)
        if cited:  # organism tags present with Humans absent ⇒ animal-only source
            return AxisFinding("species_scope", "SCOPE_MISMATCH", "medium", composite,
                               f"Claim states a general, unqualified finding (no organism marker, no "
                               f"hedge), but the cited paper is animal-only by MeSH ({cited}, 'Humans' "
                               f"ABSENT) — an over-generalization of an animal finding. Metadata "
                               f"authoritative.", cited_ev)
        return AxisFinding("species_scope", "SCOPE_UNCERTAIN", "low", composite,
                           "Claim states a general finding; cited paper carries no organism MeSH to "
                           "compare against — not determinable from metadata.", cited_ev)
    # claim asserts an animal organism
    if scope.organism in cited or (not g.has_humans and scope.organism == "Animals"):
        return AxisFinding("species_scope", "SCOPE_CONSISTENT", "medium", composite,
                           f"Claim asserts {scope.organism}; consistent with cited organism scope "
                           f"{cited}.", cited_ev)
    return AxisFinding("species_scope", "SCOPE_UNCERTAIN", "low", composite,
                       f"Claim asserts {scope.organism}; cited organism scope is {cited}. "
                       f"Relationship not determinable at slice depth.", cited_ev)


def population_axis(g: GroundedRecord, scope: ScopeFrame) -> AxisFinding:
    """Population-scope axis — cited-paper age/pregnancy MeSH vs the claim's asserted population.

    Cited-side scope-narrow signals (deterministic, authoritative):
      * pediatric-only — an M01.060.* pediatric age tag present, no adult age tag (`population_tags`).
      * pregnancy-only — a pregnancy descriptor in `mesh_all` (they sit outside the age tree, so they
        are read here, not from `population_tags`), with neither an adult nor a pediatric age tag.
    A claim asserting "adult" or the broad "general" stance cited to either is a population
    over-generalization. A claim explicitly scoped to children ("pediatric") cited to an adult-only
    source is the mirror case (retained)."""
    cited_pop = [t.descriptor for t in g.population_tags]
    cited_is_ped = any(d in PED_DESCRIPTORS for d in cited_pop)
    cited_is_adult = any(d in ADULT_DESCRIPTORS for d in cited_pop)
    cited_preg = [d for d in g.mesh_all if d in PREGNANCY_DESCRIPTORS]
    cited_is_pregnancy = bool(cited_preg)
    ev = {"cited_population_tags": cited_pop, "cited_pregnancy_mesh": cited_preg,
          "claim_population": scope.population, "claim_evidence": scope.population_evidence}
    composite = f"metadata-grounded (cited) + {scope.provenance} (claim)"

    if scope.population is None:
        return AxisFinding("population_scope", "NOT_ASSESSED", "low", "model-inferred",
                           "No explicit or implicit population scope in the claim; population axis "
                           "not assessed.", ev)

    # Claim explicitly scoped to children, cited to an adult-only source (mirror case, retained).
    if scope.population == "pediatric":
        if cited_is_adult and not cited_is_ped:
            return AxisFinding("population_scope", "SCOPE_MISMATCH", "medium", composite,
                               f"Claim asserts pediatric scope; cited population MeSH is adult-only "
                               f"({cited_pop}). Metadata authoritative.", ev)
        if cited_pop:
            return AxisFinding("population_scope", "SCOPE_CONSISTENT", "medium", composite,
                               f"Claim population (pediatric) consistent with cited population MeSH "
                               f"({cited_pop}).", ev)
        return AxisFinding("population_scope", "NOT_ASSESSED", "low", "model-inferred",
                           "Claim asserts pediatric scope but the cited paper carries no age MeSH to "
                           "compare against; not assessed.", ev)

    # Claim asserts adult or the broad "general" stance; flag against a scope-narrow source.
    # Guardrail: an adult age tag on the source clears every over-generalization case.
    if scope.population in ("adult", "general"):
        stance = "adult" if scope.population == "adult" else "general (broad, unqualified)"
        # Pregnancy-only source: an unambiguously narrow study population (pregnancy MeSH is specific
        # and rare) — flag BOTH the explicit "adult" and the broad "general" stance; FP risk is minimal.
        # Gated on has_humans (mirroring species_axis): an ANIMAL gestation/reproduction paper is also
        # tagged "Pregnancy" in mesh_all, but it is not a human pregnancy-only population — the species
        # axis owns that mismatch, and flagging it here would be a false human-population over-generalization.
        if cited_is_pregnancy and g.has_humans and not cited_is_adult and not cited_is_ped:
            return AxisFinding("population_scope", "SCOPE_MISMATCH", "medium", composite,
                               f"Claim asserts {stance} scope; cited paper is a human pregnancy-only "
                               f"population ({cited_preg}) with no adult/pediatric age tag — an "
                               f"over-generalization to a broader population. Metadata authoritative.", ev)
        # Pediatric-only source: flag ONLY an EXPLICIT adult over-claim. A bare "general" human claim
        # is NOT flagged here — general-sounding claims are frequently pediatric in their citing context
        # (a bronchiolitis / childhood-asthma discussion), a distinction invisible to a claim-only scope
        # parse; flagging them false-positives genuine SUPPORTED controls. Precision-first (WO-C3 FIX 3):
        # "general" vs a pediatric-only source stays CONSISTENT, trading recall on a genuinely ambiguous
        # pattern for a clean specificity floor.
        if scope.population == "adult" and cited_is_ped and not cited_is_adult:
            return AxisFinding("population_scope", "SCOPE_MISMATCH", "medium", composite,
                               f"Claim asserts adult scope; cited population MeSH is pediatric-only "
                               f"({cited_pop}) — an over-generalization to a broader population. "
                               f"Metadata authoritative.", ev)
        if cited_pop or cited_is_pregnancy:
            return AxisFinding("population_scope", "SCOPE_CONSISTENT", "medium", composite,
                               f"Claim population ({scope.population}) consistent with (or not "
                               f"narrowable against) cited population MeSH ({cited_pop or cited_preg}).", ev)
        return AxisFinding("population_scope", "NOT_ASSESSED", "low", "model-inferred",
                           "Claim asserts a broad population but the cited paper carries no "
                           "scope-narrowing age/pregnancy MeSH; nothing to flag.", ev)

    return AxisFinding("population_scope", "NOT_ASSESSED", "low", "model-inferred",
                       f"Claim population ({scope.population}) not comparable to cited population "
                       f"MeSH ({cited_pop}); not assessed.", ev)


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
