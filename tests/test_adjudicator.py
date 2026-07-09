"""Unit tests for C4 — the adversarial adjudicator (mock stage).

Stdlib `unittest` only (pytest is not a dependency and none may be added). The model is
mocked with a `FakeClient` — NO live API is touched in CI. Run:

    python tests/test_adjudicator.py
    # or:  python -m unittest discover -s tests

Covers the WO-C4 acceptance matrix: metadata-override (the critic may not overturn an
objective fact), abstention on an ambiguous fixture, the verbatim-quote guard, a
supported control that is not force-flagged, the Opus-on-every-call invariant, and
`Verdict` contract validity.
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

# Make the `citeval` package importable without installation.
_SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from citeval import adjudicator as A
from citeval.contracts import (
    AxisFinding,
    CitedIdentifier,
    GroundedRecord,
    MeshTag,
    RetractionInfo,
    RetractionWatchHit,
    ScopeFrame,
    Verdict,
    to_jsonable,
)
from citeval.objective_axes import species_axis
from citeval.prompts import GRADE_VALUES, NOT_ENOUGH_INFO, VERBALIZED_CONFIDENCE


# ----------------------------------------------------------------------------------
# Mock model client
# ----------------------------------------------------------------------------------
class FakeClient:
    """Scripts one response per role and records every (model) requested and the exact
    prompts seen. Dispatch is by the role's SYSTEM prefix. `raw=True` values are returned
    verbatim (to exercise malformed-JSON handling); dicts are json.dumps'd."""

    def __init__(self, supporter, refuter, critic_rounds):
        self._supporter = supporter
        self._refuter = refuter
        self._critic_rounds = list(critic_rounds)
        self._ci = 0
        self.models: list[str] = []
        self.critic_user_prompts: list[str] = []
        self.roles: list[str] = []

    def _emit(self, value):
        # Honor the real client's `complete -> str` contract: dicts are serialized;
        # plain strings pass through verbatim (to exercise malformed-JSON handling).
        return value if isinstance(value, str) else json.dumps(value)

    def complete(self, *, model, system, user, max_tokens):
        self.models.append(model)
        if system.startswith("You are the SUPPORTER"):
            self.roles.append("supporter")
            return self._emit(self._supporter)
        if system.startswith("You are the REFUTER"):
            self.roles.append("refuter")
            return self._emit(self._refuter)
        if system.startswith("You are the CRITIC"):
            self.roles.append("critic")
            self.critic_user_prompts.append(user)
            value = self._critic_rounds[self._ci % len(self._critic_rounds)]
            self._ci += 1
            return self._emit(value)
        raise AssertionError(f"unexpected system prompt: {system[:40]!r}")


# ----------------------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------------------
def animal_only_record() -> GroundedRecord:
    """Mouse study; MeSH Animals/Mice, no Humans (the B01 shape)."""
    return GroundedRecord(
        identifier=CitedIdentifier("pmid", "17086191"),
        title="Resveratrol improves health and survival of mice on a high-calorie diet",
        abstract=("Resveratrol shifted the physiology of mice on a high-calorie diet toward that of "
                  "mice on a standard diet and significantly increased their survival. Resveratrol "
                  "produced changes associated with longer lifespan in this animal model."),
        mesh_all=["Animals", "Mice", "Resveratrol"],
        organism_tags=[MeshTag("Animals", "D000818", ["B01"]),
                       MeshTag("Mice", "D051379", ["B01.050.150.900.649.313.988.400.112.400.580"])],
        population_tags=[], sex_tags=[], publication_types=["Journal Article"],
        retraction=RetractionInfo(status="NONE_FOUND"), has_humans=False,
    )


def human_record() -> GroundedRecord:
    """Human melanoma trial; Humans + adult tags (the C01 shape)."""
    return GroundedRecord(
        identifier=CitedIdentifier("pmid", "25891173"),
        title="Pembrolizumab versus Ipilimumab in Advanced Melanoma",
        abstract=("In this randomized trial in patients with advanced melanoma, pembrolizumab "
                  "prolonged progression-free survival and overall survival compared with "
                  "ipilimumab, with less high-grade toxicity."),
        mesh_all=["Humans", "Melanoma", "Adult"],
        organism_tags=[MeshTag("Humans", "D006801", ["B01.050.150.900.649.313.988.400.112.400.400"])],
        population_tags=[MeshTag("Adult", "D000328", ["M01.060.116.100"])],
        sex_tags=[], publication_types=["Randomized Controlled Trial"],
        retraction=RetractionInfo(status="NONE_FOUND"), has_humans=True,
    )


def retracted_record() -> GroundedRecord:
    g = human_record()
    g.retraction = RetractionInfo(
        status="RETRACTED",
        retraction_watch=RetractionWatchHit(present=True, rw_record_id="RW123",
                                             reason="Data concerns", date="2019-01-01"),
        source_agreement="agree",
    )
    return g


def humans_scope() -> ScopeFrame:
    return ScopeFrame(organism="Humans", organism_evidence=["clinical benefits in patients"],
                      effect="anti-aging clinical benefit", provenance="model-inferred", tier="medium")


SUP_OK = {"points": [{"quote": "significantly increased their survival",
                      "rationale": "the paper reports a survival benefit"}]}
REF_OK = {"points": [{"quote": "in this animal model",
                      "objection": "the reported benefit is animal-only",
                      "failure_mode": "scope_overgeneralization"}]}


def agree_rounds(grade="partially-supported", confidence="high", n=5):
    return [{"grade": grade, "confidence": confidence, "rationale": f"{grade}: substance weighed"}] * n


# ----------------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------------
class TestMetadataOverride(unittest.TestCase):
    def test_critic_cannot_overturn_species_fact_and_grades_substance(self):
        """Acceptance #1: animal-only record + Humans scope → species stays SCOPE_MISMATCH
        (byte-identical to the metadata computation) and the critic still returns a graded
        substantive verdict + confidence."""
        g, scope = animal_only_record(), humans_scope()
        # A critic that TRIES to wave away the animal-only concern must not change the objective axis.
        fc = FakeClient(SUP_OK, REF_OK, agree_rounds("supported-with-overreach", "high"))
        v = A.adjudicate(g, scope, claim_text="Resveratrol has clinical anti-aging benefits in humans.",
                         client=fc)

        by = {f.axis: f for f in v.axis_findings}
        # Objective species axis is exactly what the shared metadata logic produces — unoverturnable.
        expected_species = species_axis(g, scope)
        self.assertEqual(by["species_scope"].verdict, "SCOPE_MISMATCH")
        self.assertEqual(by["species_scope"].verdict, expected_species.verdict)
        self.assertEqual(by["species_scope"].detail, expected_species.detail)
        self.assertEqual(by["species_scope"].provenance, expected_species.provenance)

        sub = by["substantive_support"]
        self.assertIn(sub.verdict, GRADE_VALUES)
        self.assertNotEqual(sub.verdict, "NOT_ADJUDICATED")
        self.assertFalse(sub.evidence["abstained"])
        self.assertIn(sub.tier, ("high", "medium", "low"))
        self.assertEqual(sub.provenance, "model-inferred")
        self.assertFalse(v.stub)
        # overall is gated to not-supported by the scope mismatch, grade reported separately.
        self.assertIn("NOT SUPPORTED AS STATED", v.overall)
        self.assertIn("SPECIES SCOPE MISMATCH", v.overall)

    def test_objective_facts_are_injected_into_critic_prompt(self):
        g, scope = animal_only_record(), humans_scope()
        fc = FakeClient(SUP_OK, REF_OK, agree_rounds())
        A.adjudicate(g, scope, claim_text="x", client=fc)
        # The fixed species verdict reaches the critic as a stated fact it must not overturn.
        self.assertTrue(fc.critic_user_prompts)
        self.assertIn("SCOPE_MISMATCH", fc.critic_user_prompts[0])
        self.assertIn("FIXED", fc.critic_user_prompts[0])


class TestAbstention(unittest.TestCase):
    def test_ambiguous_low_agreement_abstains(self):
        """Acceptance #2: critic rounds disagree (agreement < threshold) → NOT_ENOUGH_INFO."""
        g, scope = human_record(), ScopeFrame(organism="Humans", provenance="model-inferred", tier="low")
        disagreeing = [
            {"grade": "fully-supported", "confidence": "medium", "rationale": "a"},
            {"grade": "contradicted", "confidence": "low", "rationale": "b"},
            {"grade": "partially-supported", "confidence": "medium", "rationale": "c"},
            {"grade": "unsupported", "confidence": "low", "rationale": "d"},
            {"grade": "supported-with-overreach", "confidence": "medium", "rationale": "e"},
        ]
        fc = FakeClient(SUP_OK, REF_OK, disagreeing)
        v = A.adjudicate(g, scope, claim_text="ambiguous claim", client=fc)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.verdict, NOT_ENOUGH_INFO)
        self.assertTrue(sub.evidence["abstained"])
        self.assertEqual(sub.tier, "low")
        self.assertIn("INSUFFICIENT EVIDENCE", v.overall)
        self.assertTrue(any("Abstained" in n for n in v.notes))

    def test_critic_self_abstains_when_all_rounds_say_not_enough_info(self):
        g, scope = human_record(), ScopeFrame(organism="Humans", provenance="model-inferred")
        rounds = [{"grade": NOT_ENOUGH_INFO, "confidence": "low", "rationale": "unclear"}] * 5
        v = A.adjudicate(g, scope, claim_text="x", client=FakeClient(SUP_OK, REF_OK, rounds))
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.verdict, NOT_ENOUGH_INFO)
        self.assertTrue(sub.evidence["abstained"])

    def test_unparseable_critic_output_abstains(self):
        g, scope = human_record(), ScopeFrame(organism="Humans", provenance="model-inferred")
        fc = FakeClient(SUP_OK, REF_OK, ["not json at all", "still not json"])
        v = A.adjudicate(g, scope, claim_text="x", client=fc)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.verdict, NOT_ENOUGH_INFO)
        self.assertEqual(sub.evidence["confidence"]["n_samples"], 0)


class TestVerbatimGuard(unittest.TestCase):
    def test_nonverbatim_quote_discarded_verbatim_kept(self):
        g, scope = animal_only_record(), humans_scope()
        supporter = {"points": [
            {"quote": "significantly increased their survival", "rationale": "real span (survives)"},
            {"quote": "cured all human patients of aging", "rationale": "fabricated span (discarded)"},
        ]}
        fc = FakeClient(supporter, {"points": []}, agree_rounds())
        v = A.adjudicate(g, scope, claim_text="x", client=fc)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.evidence["verbatim_guard"]["supporter_discarded"], 1)
        self.assertEqual(len(sub.evidence["supporter_points"]), 1)
        self.assertEqual(sub.evidence["supporter"]["span"], "significantly increased their survival")
        # A fabricated refuter quote leaves no refuter headline span.
        self.assertEqual(sub.evidence["refuter"]["span"], "")

    def test_whitespace_normalized_match_survives(self):
        g, scope = animal_only_record(), humans_scope()
        # Same span but with collapsed/expanded whitespace — must still match after normalization.
        supporter = {"points": [{"quote": "significantly   increased\n their survival",
                                 "rationale": "whitespace variant"}]}
        fc = FakeClient(supporter, {"points": []}, agree_rounds())
        v = A.adjudicate(g, scope, claim_text="x", client=fc)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.evidence["verbatim_guard"]["supporter_discarded"], 0)
        self.assertEqual(len(sub.evidence["supporter_points"]), 1)


class TestSupportedControl(unittest.TestCase):
    def test_human_supported_case_not_force_flagged(self):
        """C01-like: human record + human scope + favorable rounds → graded supported,
        overall tracks the substantive grade (no forced objection)."""
        g = human_record()
        scope = ScopeFrame(organism="Humans", organism_evidence=["patients with advanced melanoma"],
                           population="adult", effect="progression-free survival benefit",
                           provenance="model-inferred", tier="high")
        supporter = {"points": [{"quote": "prolonged progression-free survival and overall survival",
                                 "rationale": "directly supports the survival-benefit claim"}]}
        fc = FakeClient(supporter, {"points": []}, agree_rounds("fully-supported", "high"))
        v = A.adjudicate(g, scope, claim_text="Pembrolizumab confers a survival benefit over ipilimumab.",
                         client=fc)
        by = {f.axis: f for f in v.axis_findings}
        self.assertEqual(by["species_scope"].verdict, "SCOPE_CONSISTENT")
        self.assertEqual(by["substantive_support"].verdict, "fully-supported")
        self.assertFalse(by["substantive_support"].evidence["abstained"])
        self.assertEqual(v.overall, "SUBSTANTIVE SUPPORT: fully-supported")


class TestRetractionGate(unittest.TestCase):
    def test_retracted_paper_gates_overall_but_still_grades_substance(self):
        g = retracted_record()
        scope = ScopeFrame(organism="Humans", provenance="model-inferred", tier="medium")
        supporter = {"points": [{"quote": "prolonged progression-free survival and overall survival",
                                 "rationale": "supports"}]}
        fc = FakeClient(supporter, {"points": []}, agree_rounds("fully-supported", "high"))
        v = A.adjudicate(g, scope, claim_text="x", client=fc)
        by = {f.axis: f for f in v.axis_findings}
        self.assertEqual(by["retraction"].verdict, "RELIES_ON_RETRACTED")
        self.assertIn("RETRACTED PAPER", v.overall)
        # Substance is still graded and reported separately (not silently suppressed).
        self.assertEqual(by["substantive_support"].verdict, "fully-supported")
        self.assertIn("held separately", v.overall)


class TestInvariantsAndContract(unittest.TestCase):
    def test_opus_on_every_model_call(self):
        g, scope = animal_only_record(), humans_scope()
        fc = FakeClient(SUP_OK, REF_OK, agree_rounds())
        A.adjudicate(g, scope, claim_text="x", client=fc)
        self.assertEqual(set(fc.models), {A.OPUS_MODEL})
        self.assertEqual(A.OPUS_MODEL, "claude-opus-4-8")
        # 1 supporter + 1 refuter + N critic rounds.
        self.assertEqual(len(fc.models), 2 + A.SELF_CONSISTENCY_ROUNDS)
        self.assertEqual(fc.roles.count("critic"), A.SELF_CONSISTENCY_ROUNDS)

    def test_default_client_not_constructed_when_injected(self):
        """Injecting a client must never touch the SDK (no key / no network in CI)."""
        g, scope = animal_only_record(), humans_scope()
        original = A.AnthropicModelClient
        try:
            def _boom(*a, **k):
                raise AssertionError("AnthropicModelClient must not be constructed when a client is injected")
            A.AnthropicModelClient = _boom
            v = A.adjudicate(g, scope, claim_text="x", client=FakeClient(SUP_OK, REF_OK, agree_rounds()))
            self.assertFalse(v.stub)
        finally:
            A.AnthropicModelClient = original

    def test_output_validates_against_verdict_contract(self):
        g, scope = animal_only_record(), humans_scope()
        v = A.adjudicate(g, scope, claim_text="claim text", client=FakeClient(SUP_OK, REF_OK, agree_rounds()))
        self.assertIsInstance(v, Verdict)
        self.assertEqual(v.claim, "claim text")
        self.assertEqual(v.cited_identifier, g.identifier)
        self.assertFalse(v.stub)
        axes = [f.axis for f in v.axis_findings]
        self.assertEqual(set(axes),
                         {"retraction", "species_scope", "population_scope", "substantive_support"})
        for f in v.axis_findings:
            self.assertIsInstance(f, AxisFinding)
        # §6 headline evidence keys + shapes that C5 reads.
        ev = {f.axis: f for f in v.axis_findings}["substantive_support"].evidence
        for key in ("confidence", "calibration", "supporter", "refuter", "abstained"):
            self.assertIn(key, ev)
        self.assertEqual(set(ev["confidence"]), {"verbalized", "agreement", "n_samples"})
        self.assertIn(ev["confidence"]["verbalized"], VERBALIZED_CONFIDENCE)
        self.assertIn("note", ev["calibration"])
        self.assertEqual(set(ev["supporter"]), {"span", "point"})
        self.assertEqual(set(ev["refuter"]), {"span", "objection"})
        self.assertIsInstance(ev["abstained"], bool)
        self.assertIn("dose", v.unverifiable_axes)
        # Fully JSON-serializable (drops into C5/C6 unchanged).
        round_trip = json.loads(json.dumps(to_jsonable(v)))
        self.assertEqual(round_trip["overall"], v.overall)

    def test_swappable_rollup_is_used(self):
        g, scope = animal_only_record(), humans_scope()
        cfg = A.AdjudicationConfig(rollup=lambda findings: "CUSTOM ROLLUP")
        v = A.adjudicate(g, scope, claim_text="x",
                         client=FakeClient(SUP_OK, REF_OK, agree_rounds()), config=cfg)
        self.assertEqual(v.overall, "CUSTOM ROLLUP")


if __name__ == "__main__":
    unittest.main(verbosity=2)
