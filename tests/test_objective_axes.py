"""Objective-axis over-generalization tests (WO-C3).

Covers the two scope-narrow-source buckets the deeper C3 stances recover, and the precision
guardrails that must keep the hard-negative controls unflagged:
  * population over-generalization — adult/general claim cited to a pediatric-only OR pregnancy-only
    source (pregnancy read off `mesh_all`, since its MeSH sits outside the M01.060.* age tree);
  * species over-generalization — a broad "general" claim cited to an animal-only source;
  * the `has_humans` gate — a human/general claim cited to a human paper that ALSO carries animal
    FP-bait MeSH tags stays CONSISTENT;
  * animal-qualified claims (organism resolved to the literal animal by C3) never flag against a
    matching animal source.
These axes are the metadata-grounded core (invariant #1); they run identically under both adjudicators.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from citeval.contracts import GroundedRecord, MeshTag, RetractionInfo, ScopeFrame
from citeval.objective_axes import population_axis, species_axis

HUMANS_TREE = "B01.050.150.900.649.313.988.400.112.400.400"
MOUSE_TREE = "B01.050.150.900.649.313.992.635.505.500"


def _record(*, mesh, organism, population, has_humans):
    return GroundedRecord(
        identifier=None, title="t", abstract="a", mesh_all=list(mesh),
        organism_tags=list(organism), population_tags=list(population), sex_tags=[],
        publication_types=["Journal Article"], retraction=RetractionInfo(status="NONE_FOUND"),
        has_humans=has_humans,
    )


def animal_only():
    return _record(mesh=["Animals", "Mice"], has_humans=False,
                   organism=[MeshTag("Animals", "D000818", ["B01.050"]),
                             MeshTag("Mice", "D051379", [MOUSE_TREE])], population=[])


def human_with_animal_bait():
    """Hard-negative shape: human paper carrying FP-bait animal tags (has_humans True)."""
    return _record(mesh=["Humans", "Animals", "Mice"], has_humans=True,
                   organism=[MeshTag("Humans", "D006801", [HUMANS_TREE]),
                             MeshTag("Animals", "D000818", ["B01.050"]),
                             MeshTag("Mice", "D051379", [MOUSE_TREE])], population=[])


def pediatric_only():
    return _record(mesh=["Humans", "Child", "Adolescent"], has_humans=True,
                   organism=[MeshTag("Humans", "D006801", [HUMANS_TREE])],
                   population=[MeshTag("Child", "D002648", ["M01.060.406"]),
                               MeshTag("Adolescent", "D000293", ["M01.060.057"])])


def pregnancy_only():
    """Pregnancy MeSH lives in mesh_all, NOT population_tags (outside M01.060.*)."""
    return _record(mesh=["Humans", "Female", "Pregnancy", "Obesity"], has_humans=True,
                   organism=[MeshTag("Humans", "D006801", [HUMANS_TREE])], population=[])


def adult_human():
    return _record(mesh=["Humans", "Adult", "Middle Aged"], has_humans=True,
                   organism=[MeshTag("Humans", "D006801", [HUMANS_TREE])],
                   population=[MeshTag("Adult", "D000328", ["M01.060.116.100"]),
                               MeshTag("Middle Aged", "D008875", ["M01.060.116.630"])])


def _scope(organism=None, population=None):
    return ScopeFrame(organism=organism, organism_evidence=["x"] if organism else [],
                      population=population, population_evidence=["x"] if population else [],
                      provenance="model-inferred", tier="medium")


# --------------------------------------------------------------------------- species
class TestSpeciesOverGeneralization(unittest.TestCase):
    def test_general_claim_animal_only_source_flags(self):
        f = species_axis(animal_only(), _scope(organism="general"))
        self.assertEqual(f.verdict, "SCOPE_MISMATCH")
        self.assertIn("over-generalization", f.detail)

    def test_general_claim_human_source_consistent(self):
        f = species_axis(adult_human(), _scope(organism="general"))
        self.assertEqual(f.verdict, "SCOPE_CONSISTENT")

    def test_general_claim_human_with_animal_bait_stays_consistent(self):
        """has_humans gate: FP-bait animal tags on a human paper must NOT flag."""
        f = species_axis(human_with_animal_bait(), _scope(organism="general"))
        self.assertEqual(f.verdict, "SCOPE_CONSISTENT")

    def test_humans_claim_animal_bait_stays_consistent(self):
        f = species_axis(human_with_animal_bait(), _scope(organism="Humans"))
        self.assertEqual(f.verdict, "SCOPE_CONSISTENT")

    def test_animal_qualified_claim_matching_source_consistent(self):
        """C3 resolves 'in mice' → 'Mice'; a mouse claim on a mouse source never flags."""
        f = species_axis(animal_only(), _scope(organism="Mice"))
        self.assertEqual(f.verdict, "SCOPE_CONSISTENT")

    def test_general_claim_no_organism_metadata_not_flagged(self):
        rec = _record(mesh=["Inflammation"], organism=[], population=[], has_humans=False)
        f = species_axis(rec, _scope(organism="general"))
        self.assertEqual(f.verdict, "SCOPE_UNCERTAIN")

    def test_null_organism_unchanged(self):
        f = species_axis(animal_only(), _scope(organism=None))
        self.assertEqual(f.verdict, "CLAIM_SCOPE_UNSTATED")


# --------------------------------------------------------------------------- population
class TestPopulationOverGeneralization(unittest.TestCase):
    def test_general_claim_pediatric_only_NOT_flagged(self):
        """Precision-first: a bare 'general' human claim vs a pediatric-only source is contextually
        ambiguous (may be pediatric in its citing context) — it must NOT flag, or genuine SUPPORTED
        controls (e.g. a bronchiolitis/childhood-asthma discussion) false-positive."""
        f = population_axis(pediatric_only(), _scope(organism="Humans", population="general"))
        self.assertEqual(f.verdict, "SCOPE_CONSISTENT")

    def test_adult_claim_pediatric_only_flags(self):
        """An EXPLICIT adult over-claim vs a pediatric-only source is a genuine over-generalization."""
        f = population_axis(pediatric_only(), _scope(organism="Humans", population="adult"))
        self.assertEqual(f.verdict, "SCOPE_MISMATCH")
        self.assertIn("pediatric-only", f.detail)

    def test_general_claim_pregnancy_only_flags(self):
        f = population_axis(pregnancy_only(), _scope(organism="Humans", population="general"))
        self.assertEqual(f.verdict, "SCOPE_MISMATCH")
        self.assertIn("pregnancy-only", f.detail)
        self.assertEqual(f.evidence["cited_pregnancy_mesh"], ["Pregnancy"])

    def test_general_claim_adult_source_consistent(self):
        f = population_axis(adult_human(), _scope(organism="Humans", population="general"))
        self.assertEqual(f.verdict, "SCOPE_CONSISTENT")

    def test_animal_pregnancy_source_not_flagged_on_population(self):
        """Precision (review #3): an ANIMAL gestation study is also tagged 'Pregnancy' in mesh_all, but
        it is not a HUMAN pregnancy-only population — the population axis must not flag it (the species
        axis owns that animal mismatch). Gated on has_humans."""
        rec = _record(mesh=["Animals", "Mice", "Pregnancy"], has_humans=False,
                      organism=[MeshTag("Mice", "D051379", [MOUSE_TREE])], population=[])
        f = population_axis(rec, _scope(organism="general", population="general"))
        self.assertNotEqual(f.verdict, "SCOPE_MISMATCH")

    def test_pregnancy_source_with_adult_tag_not_flagged(self):
        """Guardrail: an adult age tag clears the pregnancy-only signal."""
        rec = _record(mesh=["Humans", "Pregnancy", "Adult"], has_humans=True,
                      organism=[MeshTag("Humans", "D006801", [HUMANS_TREE])],
                      population=[MeshTag("Adult", "D000328", ["M01.060.116.100"])])
        f = population_axis(rec, _scope(organism="Humans", population="general"))
        self.assertEqual(f.verdict, "SCOPE_CONSISTENT")

    def test_general_claim_no_age_or_pregnancy_not_assessed(self):
        rec = _record(mesh=["Humans", "Kidney"], has_humans=True,
                      organism=[MeshTag("Humans", "D006801", [HUMANS_TREE])], population=[])
        f = population_axis(rec, _scope(organism="Humans", population="general"))
        self.assertEqual(f.verdict, "NOT_ASSESSED")

    def test_pediatric_claim_adult_source_still_flags(self):
        """Mirror case retained."""
        f = population_axis(adult_human(), _scope(organism="Humans", population="pediatric"))
        self.assertEqual(f.verdict, "SCOPE_MISMATCH")

    def test_null_population_not_assessed(self):
        f = population_axis(pediatric_only(), _scope(organism="general", population=None))
        self.assertEqual(f.verdict, "NOT_ASSESSED")


if __name__ == "__main__":
    unittest.main()
