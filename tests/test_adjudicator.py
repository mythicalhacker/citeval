"""Unit tests for C4 — the adversarial adjudicator (RB1/RB2/RB3 integration).

Stdlib `unittest` only (pytest is not a dependency and none may be added). The model is
mocked with a `FakeClient` — NO live API is touched in CI. Run:

    python tests/test_adjudicator.py
    # or:  python -m unittest discover -s tests

Covers the WO-C4-integrate acceptance matrix: metadata-override; scope never caps the grade
(routes_to hard-filter); RB1 grades incl. `N/A — non-substantiating`; direction-reversal via
`ScopeFrame.direction`; full-triad self-consistency + median-aware vote + adjacent-vs-non-adjacent
abstention; the verbatim guard; Opus-on-every-call; §6 evidence keys; `Verdict` contract validity.
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
from citeval.prompts import (
    GRADE_VALUES,
    NON_SUBSTANTIATING,
    NOT_ENOUGH_INFO,
    VERBALIZED_CONFIDENCE,
)

# Deterministic configs (the full triad triples calls; early-stopping + N make counts vary).
SINGLE = A.AdjudicationConfig(self_consistency_rounds=1, min_valid_rounds=1,
                              adaptive_early_stopping=False)   # one triad; isolates per-round behavior
NOSTOP = A.AdjudicationConfig(adaptive_early_stopping=False)  # full N rounds, no early exit


# ----------------------------------------------------------------------------------
# Mock model client
# ----------------------------------------------------------------------------------
class FakeClient:
    """Scripts one supporter + one refuter response (repeated every round) and a cycling list
    of critic rounds. Dispatch is by the role's SYSTEM prefix. Accepts + records `temperature`.
    `str` values pass through verbatim (to exercise malformed-JSON handling); dicts are dumped."""

    def __init__(self, supporter, refuter, critic_rounds):
        self._supporter = supporter
        self._refuter = refuter
        self._critic_rounds = list(critic_rounds)
        self._ci = 0
        self.models: list[str] = []
        self.temperatures: list[float] = []
        self.roles: list[str] = []
        self.critic_user_prompts: list[str] = []
        self.refuter_user_prompts: list[str] = []

    def _emit(self, value):
        return value if isinstance(value, str) else json.dumps(value)

    def complete(self, *, model, system, user, max_tokens, temperature=1.0):
        self.models.append(model)
        self.temperatures.append(temperature)
        if system.startswith("You are the SUPPORTER"):
            self.roles.append("supporter")
            return self._emit(self._supporter)
        if system.startswith("You are the REFUTER"):
            self.roles.append("refuter")
            self.refuter_user_prompts.append(user)
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
                      effect="anti-aging clinical benefit", direction="increase",
                      direction_evidence=["clinical benefits"], provenance="model-inferred", tier="medium")


SUP_OK = {"points": [{"quote": "significantly increased their survival",
                      "rationale": "the paper reports a survival benefit"}]}
# A GRADE-routed substantive objection (over_certainty), not a scope point.
REF_OK = {"points": [{"quote": "produced changes associated with longer lifespan",
                      "objection": "association, not a demonstrated clinical benefit",
                      "distortion_type": "over_certainty", "routes_to": "grade"}]}
# A scope over-generalization → routes to the rollup, must NEVER reach the critic / the grade.
REF_SCOPE = {"points": [{"quote": "in this animal model",
                         "objection": "an animal finding generalized to human benefit",
                         "distortion_type": "over_generalization", "routes_to": "rollup_not_grade"}]}


def agree_rounds(grade="partially-supported", confidence=0.85, n=7):
    return [{"grade": grade, "confidence": confidence,
             "grade_rationale_last": f"{grade}: substance weighed"}] * n


# ----------------------------------------------------------------------------------
# Metadata override + §6 orthogonality (scope never caps the grade)
# ----------------------------------------------------------------------------------
class TestMetadataOverride(unittest.TestCase):
    def test_critic_cannot_overturn_species_fact_and_grades_substance(self):
        """Acceptance #1: animal-only record + Humans scope → species stays SCOPE_MISMATCH
        (byte-identical to the metadata computation) and the critic still grades substance."""
        g, scope = animal_only_record(), humans_scope()
        fc = FakeClient(SUP_OK, REF_OK, agree_rounds("supported-with-overreach", 0.9))
        v = A.adjudicate(g, scope, claim_text="Resveratrol has clinical anti-aging benefits in humans.",
                         client=fc)
        by = {f.axis: f for f in v.axis_findings}
        expected_species = species_axis(g, scope)
        self.assertEqual(by["species_scope"].verdict, "SCOPE_MISMATCH")
        self.assertEqual(by["species_scope"].verdict, expected_species.verdict)
        self.assertEqual(by["species_scope"].detail, expected_species.detail)
        self.assertEqual(by["species_scope"].provenance, expected_species.provenance)

        sub = by["substantive_support"]
        self.assertIn(sub.verdict, GRADE_VALUES)
        self.assertFalse(sub.evidence["abstained"])
        self.assertEqual(sub.provenance, "model-inferred")
        self.assertFalse(v.stub)
        # overall gated by the scope mismatch; the substantive grade is reported separately.
        self.assertIn("NOT SUPPORTED AS STATED", v.overall)
        self.assertIn("SPECIES SCOPE MISMATCH", v.overall)
        self.assertIn("held separately", v.overall)

    def test_objective_facts_are_injected_into_critic_prompt(self):
        g, scope = animal_only_record(), humans_scope()
        fc = FakeClient(SUP_OK, REF_OK, agree_rounds())
        A.adjudicate(g, scope, claim_text="x", client=fc)
        self.assertTrue(fc.critic_user_prompts)
        self.assertIn("SCOPE_MISMATCH", fc.critic_user_prompts[0])
        self.assertIn("FIXED", fc.critic_user_prompts[0])

    def test_scope_routed_refuter_point_never_reaches_grade(self):
        """b6: a refuter `over_generalization` (routes_to=rollup_not_grade) is hard-filtered —
        it never enters the critic prompt, never becomes the refuter headline, and is recorded
        only under refuter_scope_notes. Scope cannot depress the graded number (§6)."""
        g, scope = animal_only_record(), humans_scope()
        fc = FakeClient(SUP_OK, REF_SCOPE, agree_rounds("fully-supported", 0.9))
        v = A.adjudicate(g, scope, claim_text="x", client=fc)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        # The scope point never becomes a critic argument: its unique objection text (not a
        # source span) is absent, and the refuter argument block is empty in every prompt.
        self.assertTrue(fc.critic_user_prompts)
        for p in fc.critic_user_prompts:
            self.assertNotIn("generalized to human benefit", p)
            self.assertIn("(no grounded points)", p)
        self.assertEqual(sub.evidence["refuter"]["span"], "")           # no grade-routed objection
        self.assertEqual(len(sub.evidence["refuter_scope_notes"]), 1)   # recorded for the rollup
        self.assertEqual(sub.verdict, "fully-supported")                # grade unaffected by scope
        self.assertTrue(any("scope over-generalization" in n for n in v.notes))

    def test_scope_tag_barred_even_when_routes_to_says_grade(self):
        """Structural §6 guard: an over_generalization point is barred from the grade even if the
        (warm) model self-declares routes_to='grade' or a non-canonical rollup variant — the tag
        is an unconditional gate, not subordinate to the model's routing string."""
        g, scope = animal_only_record(), humans_scope()
        lying_scope = {"points": [{"quote": "in this animal model",
                                   "objection": "mice generalized to humans",
                                   "distortion_type": "over_generalization", "routes_to": "grade"}]}
        fc = FakeClient(SUP_OK, lying_scope, agree_rounds("fully-supported", 0.9))
        v = A.adjudicate(g, scope, claim_text="x", client=fc)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.evidence["refuter"]["span"], "")           # not a grade objection
        self.assertEqual(len(sub.evidence["refuter_scope_notes"]), 1)   # recorded on the rollup side
        for p in fc.critic_user_prompts:
            self.assertNotIn("generalized to humans", p)


# ----------------------------------------------------------------------------------
# Direction (ScopeFrame.direction → refuter/critic direction test)
# ----------------------------------------------------------------------------------
class TestDirection(unittest.TestCase):
    def test_direction_threaded_to_refuter_and_critic(self):
        g = human_record()
        scope = ScopeFrame(organism="Humans", direction="decrease",
                           direction_evidence=["reduced"], provenance="model-inferred", tier="medium")
        fc = FakeClient(SUP_OK, REF_OK, agree_rounds())
        A.adjudicate(g, scope, claim_text="the drug reduced mortality", client=fc)
        self.assertTrue(fc.refuter_user_prompts)
        self.assertIn("decrease", fc.refuter_user_prompts[0])
        self.assertIn("decrease", fc.critic_user_prompts[0])


# ----------------------------------------------------------------------------------
# Abstention (RB3 Part 2): adjacent-only resolves; non-adjacent multimodal abstains
# ----------------------------------------------------------------------------------
class TestAbstention(unittest.TestCase):
    def test_non_adjacent_multimodal_abstains(self):
        g, scope = human_record(), ScopeFrame(organism="Humans", provenance="model-inferred", tier="low")
        rounds = [
            {"grade": "fully-supported", "confidence": 0.6},
            {"grade": "contradicted", "confidence": 0.5},
            {"grade": "partially-supported", "confidence": 0.6},
            {"grade": "unsupported-for-the-claim", "confidence": 0.5},
            {"grade": "supported-with-overreach", "confidence": 0.6},
        ]
        cfg = A.AdjudicationConfig(self_consistency_rounds=5, adaptive_early_stopping=False)
        v = A.adjudicate(g, scope, claim_text="ambiguous", client=FakeClient(SUP_OK, REF_OK, rounds),
                         config=cfg)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.verdict, NOT_ENOUGH_INFO)
        self.assertTrue(sub.evidence["abstained"])
        self.assertTrue(sub.evidence["self_consistency"]["non_adjacent_multimodal"])
        self.assertEqual(sub.tier, "low")
        self.assertIn("INSUFFICIENT EVIDENCE", v.overall)
        self.assertTrue(any("Abstained" in n for n in v.notes))

    def test_low_agreement_with_nonadjacent_mass_abstains_via_tau(self):
        """tau_abstain must be LIVE: a split with a_exact<tau and SOME non-adjacent mass (but
        a_adj still >= adjacent_floor, so not 'multimodal') abstains. Distribution
        [2,2,2,3,3,3,5]: a_exact=3/7<0.5, a_adj=6/7>=0.7, but the index-5 vote is non-adjacent →
        NOT a pure adjacent-only split → abstain (regression for the dead-tau bug)."""
        g, scope = human_record(), ScopeFrame(organism="Humans", provenance="model-inferred", tier="low")
        rounds = ([{"grade": "partially-supported", "confidence": 0.6}] * 3
                  + [{"grade": "technically-true-but-misleading", "confidence": 0.6}] * 3
                  + [{"grade": "contradicted", "confidence": 0.6}])
        cfg = A.AdjudicationConfig(self_consistency_rounds=7, adaptive_early_stopping=False)
        supporter = {"points": [{"quote": "prolonged progression-free survival and overall survival",
                                 "rationale": "s"}]}
        v = A.adjudicate(g, scope, claim_text="x", client=FakeClient(supporter, {"points": []}, rounds),
                         config=cfg)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.verdict, NOT_ENOUGH_INFO)
        self.assertFalse(sub.evidence["self_consistency"]["non_adjacent_multimodal"])  # a_adj>=floor
        self.assertLess(sub.evidence["confidence"]["agreement"], cfg.tau_abstain)       # a_exact<tau

    def test_minority_non_substantiating_with_unparseable_rounds_does_not_promote(self):
        """The NA majority bar is ceil(rounds_run/2), NOT ceil(n_parsed/2): 3 NON_SUBSTANTIATING
        + 4 unparseable of 7 samples is a minority → abstain, not a promotion to the distinct
        NON_SUBSTANTIATING bucket (regression for the shrunken-denominator bug). The 4 truncated
        rounds each resample the critic once (WO-C4 fix), so the mock scripts extra unparseable
        responses to feed the retries; the 4 rounds still fail → counted as n_parse_failed=4."""
        g, scope = human_record(), ScopeFrame(organism="Humans", provenance="model-inferred")
        # 8 "not json" entries feed the 4 unparseable rounds' first-call + one resample each.
        rounds = [{"grade": NON_SUBSTANTIATING, "confidence": 0.7}] * 3 + ["not json"] * 8
        cfg = A.AdjudicationConfig(self_consistency_rounds=7, adaptive_early_stopping=False)
        v = A.adjudicate(g, scope, claim_text="x", client=FakeClient(SUP_OK, REF_OK, rounds), config=cfg)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.verdict, NOT_ENOUGH_INFO)          # abstained, NOT non-substantiating
        self.assertFalse(sub.evidence["non_substantiating"])
        self.assertEqual(sub.evidence["self_consistency"]["n_parse_failed"], 4)  # visible, not silent

    def test_adjacent_only_split_does_not_abstain(self):
        """A 2/2/3/3-style split (all mass within ±1 of g*) is ordinal boundary noise — resolve
        to the modal grade with moderate confidence, NEVER abstain (RB3 §3.2)."""
        g, scope = human_record(), ScopeFrame(organism="Humans", provenance="model-inferred", tier="medium")
        rounds = ([{"grade": "partially-supported", "confidence": 0.6}] * 2
                  + [{"grade": "technically-true-but-misleading", "confidence": 0.6}] * 2)
        cfg = A.AdjudicationConfig(self_consistency_rounds=4, adaptive_early_stopping=False)
        supporter = {"points": [{"quote": "prolonged progression-free survival and overall survival",
                                 "rationale": "supports"}]}
        v = A.adjudicate(g, scope, claim_text="x", client=FakeClient(supporter, {"points": []}, rounds),
                         config=cfg)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertNotEqual(sub.verdict, NOT_ENOUGH_INFO)
        self.assertFalse(sub.evidence["abstained"])
        self.assertGreaterEqual(sub.evidence["self_consistency"]["a_adj"], 0.7)

    def test_critic_self_abstains_when_majority_not_enough_info(self):
        g, scope = human_record(), ScopeFrame(organism="Humans", provenance="model-inferred")
        rounds = [{"grade": NOT_ENOUGH_INFO, "confidence": 0.2}] * 7
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


# ----------------------------------------------------------------------------------
# N/A — non-substantiating (Trap 2): distinct from a grade and from abstention
# ----------------------------------------------------------------------------------
class TestNonSubstantiating(unittest.TestCase):
    def test_non_substantiating_majority(self):
        g, scope = human_record(), ScopeFrame(organism="Humans", provenance="model-inferred", tier="medium")
        rounds = [{"grade": NON_SUBSTANTIATING, "confidence": 0.7,
                   "grade_rationale_last": "cited for a method"}] * 7
        v = A.adjudicate(g, scope, claim_text="uses their assay", client=FakeClient(SUP_OK, REF_OK, rounds))
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.verdict, NON_SUBSTANTIATING)
        self.assertTrue(sub.evidence["non_substantiating"])
        self.assertFalse(sub.evidence["abstained"])   # NON-substantiating is NOT abstention
        # Rollup renders it distinctly from both a grade and NEI.
        self.assertIn("NON-SUBSTANTIATING CITATION", v.overall)
        self.assertNotIn("INSUFFICIENT EVIDENCE", v.overall)
        self.assertTrue(any("Non-substantiating" in n for n in v.notes))


# ----------------------------------------------------------------------------------
# Verbatim guard (per-round, isolated with SINGLE config)
# ----------------------------------------------------------------------------------
class TestVerbatimGuard(unittest.TestCase):
    def test_nonverbatim_quote_discarded_verbatim_kept(self):
        g, scope = animal_only_record(), humans_scope()
        supporter = {"points": [
            {"quote": "significantly increased their survival", "rationale": "real span (survives)"},
            {"quote": "cured all human patients of aging", "rationale": "fabricated span (discarded)"},
        ]}
        fc = FakeClient(supporter, {"points": []}, agree_rounds())
        v = A.adjudicate(g, scope, claim_text="x", client=fc, config=SINGLE)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.evidence["verbatim_guard"]["supporter_discarded"], 1)
        self.assertEqual(len(sub.evidence["supporter_points"]), 1)
        self.assertEqual(sub.evidence["supporter"]["span"], "significantly increased their survival")
        self.assertEqual(sub.evidence["supporter"]["point"], "real span (survives)")
        self.assertEqual(sub.evidence["refuter"]["span"], "")

    def test_whitespace_normalized_match_survives(self):
        g, scope = animal_only_record(), humans_scope()
        supporter = {"points": [{"quote": "significantly   increased\n their survival",
                                 "rationale": "whitespace variant"}]}
        fc = FakeClient(supporter, {"points": []}, agree_rounds())
        v = A.adjudicate(g, scope, claim_text="x", client=fc, config=SINGLE)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.evidence["verbatim_guard"]["supporter_discarded"], 0)
        self.assertEqual(len(sub.evidence["supporter_points"]), 1)

    def test_cross_field_straddle_discarded(self):
        """A span contiguous in NEITHER field (only across the title↔abstract junction) is discarded."""
        g, scope = animal_only_record(), humans_scope()
        straddle = "diet Resveratrol"
        self.assertNotIn(straddle, g.title)
        self.assertNotIn(straddle, g.abstract)
        supporter = {"points": [{"quote": straddle, "rationale": "manufactured straddle span"}]}
        fc = FakeClient(supporter, {"points": []}, agree_rounds())
        v = A.adjudicate(g, scope, claim_text="x", client=fc, config=SINGLE)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.evidence["verbatim_guard"]["supporter_discarded"], 1)
        self.assertEqual(len(sub.evidence["supporter_points"]), 0)

    def test_non_string_quote_discarded(self):
        g, scope = animal_only_record(), humans_scope()
        supporter = {"points": [
            {"quote": None, "rationale": "null quote"},
            {"quote": 42, "rationale": "numeric quote"},
            {"quote": True, "rationale": "bool quote"},
            {"quote": "significantly increased their survival", "rationale": "the one real span"},
        ]}
        fc = FakeClient(supporter, {"points": []}, agree_rounds())
        v = A.adjudicate(g, scope, claim_text="x", client=fc, config=SINGLE)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.evidence["verbatim_guard"]["supporter_discarded"], 3)
        self.assertEqual(len(sub.evidence["supporter_points"]), 1)
        self.assertIsInstance(sub.evidence["supporter"]["span"], str)


# ----------------------------------------------------------------------------------
# Controls, gates, invariants, contract
# ----------------------------------------------------------------------------------
class TestSupportedControl(unittest.TestCase):
    def test_human_supported_case_not_force_flagged(self):
        g = human_record()
        scope = ScopeFrame(organism="Humans", organism_evidence=["patients with advanced melanoma"],
                           population="adult", effect="progression-free survival benefit",
                           direction="increase", provenance="model-inferred", tier="high")
        supporter = {"points": [{"quote": "prolonged progression-free survival and overall survival",
                                 "rationale": "directly supports the survival-benefit claim"}]}
        fc = FakeClient(supporter, {"points": []}, agree_rounds("fully-supported", 0.9))
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
        fc = FakeClient(supporter, {"points": []}, agree_rounds("fully-supported", 0.9))
        v = A.adjudicate(g, scope, claim_text="x", client=fc)
        by = {f.axis: f for f in v.axis_findings}
        self.assertEqual(by["retraction"].verdict, "RELIES_ON_RETRACTED")
        self.assertIn("RETRACTED PAPER", v.overall)
        self.assertEqual(by["substantive_support"].verdict, "fully-supported")
        self.assertIn("held separately", v.overall)


class TestInvariantsAndContract(unittest.TestCase):
    def test_opus_on_every_model_call_full_triad(self):
        g, scope = animal_only_record(), humans_scope()
        fc = FakeClient(SUP_OK, REF_OK, agree_rounds())
        A.adjudicate(g, scope, claim_text="x", client=fc, config=NOSTOP)
        self.assertEqual(set(fc.models), {A.OPUS_MODEL})
        self.assertEqual(A.OPUS_MODEL, "claude-opus-4-8")
        # Full triad, no early-stop: N each of supporter / refuter / critic.
        n = NOSTOP.self_consistency_rounds
        self.assertEqual(len(fc.models), 3 * n)
        self.assertEqual(fc.roles.count("supporter"), n)
        self.assertEqual(fc.roles.count("refuter"), n)
        self.assertEqual(fc.roles.count("critic"), n)

    def test_advocates_warm_critic_cool(self):
        g, scope = animal_only_record(), humans_scope()
        fc = FakeClient(SUP_OK, REF_OK, agree_rounds())
        A.adjudicate(g, scope, claim_text="x", client=fc, config=SINGLE)
        temp_by_role = dict(zip(fc.roles, fc.temperatures))
        self.assertGreater(temp_by_role["supporter"], temp_by_role["critic"])
        self.assertEqual(temp_by_role["critic"], SINGLE.critic_temperature)

    def test_adaptive_early_stopping_reduces_calls_when_unanimous(self):
        g, scope = animal_only_record(), humans_scope()
        fc = FakeClient(SUP_OK, REF_OK, agree_rounds("partially-supported", 0.9))
        A.adjudicate(g, scope, claim_text="x", client=fc)  # default: early-stopping ON
        # Unanimous → stops at the min floor rather than running all N.
        self.assertEqual(fc.roles.count("critic"), A.MIN_VALID_ROUNDS)
        self.assertLess(fc.roles.count("critic"), A.SELF_CONSISTENCY_ROUNDS)

    def test_early_stopping_requires_majority_of_configured_n(self):
        """g*-preservation is structural: with N raised (12) but min_valid_rounds left at 4, a
        4-round unanimous prefix must NOT stop early — the remaining 8 rounds could still flip the
        median-aware g*. Stop only once a strict majority of N is in (rounds_run > N/2)."""
        g, scope = animal_only_record(), humans_scope()
        cfg = A.AdjudicationConfig(self_consistency_rounds=12, min_valid_rounds=4)
        fc = FakeClient(SUP_OK, REF_OK, agree_rounds("partially-supported", 0.9, n=12))
        A.adjudicate(g, scope, claim_text="x", client=fc, config=cfg)
        # Unanimous → stops at the first strict majority (ceil(12/2)+1 = 7), not at the floor of 4.
        self.assertEqual(fc.roles.count("critic"), 7)

    def test_default_client_not_constructed_when_injected(self):
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
        v = A.adjudicate(g, scope, claim_text="claim text",
                         client=FakeClient(SUP_OK, REF_OK, agree_rounds()))
        self.assertIsInstance(v, Verdict)
        self.assertEqual(v.claim, "claim text")
        self.assertEqual(v.cited_identifier, g.identifier)
        self.assertFalse(v.stub)
        axes = [f.axis for f in v.axis_findings]
        self.assertEqual(set(axes),
                         {"retraction", "species_scope", "population_scope", "substantive_support"})
        for f in v.axis_findings:
            self.assertIsInstance(f, AxisFinding)
        # §6 headline evidence keys + shapes that C5 (reporting.py) reads — UNCHANGED.
        ev = {f.axis: f for f in v.axis_findings}["substantive_support"].evidence
        for key in ("confidence", "calibration", "supporter", "refuter", "abstained"):
            self.assertIn(key, ev)
        self.assertEqual(set(ev["confidence"]), {"verbalized", "agreement", "n_samples"})
        self.assertIn(ev["confidence"]["verbalized"], VERBALIZED_CONFIDENCE)      # tier, high|medium|low
        self.assertIsInstance(ev["confidence"]["agreement"], (int, float))        # numeric (C5 formats .2f)
        self.assertIn("note", ev["calibration"])
        self.assertEqual(set(ev["supporter"]), {"span", "point"})
        self.assertEqual(set(ev["refuter"]), {"span", "objection"})
        self.assertEqual(ev["supporter"]["point"], SUP_OK["points"][0]["rationale"])
        self.assertEqual(ev["refuter"]["objection"], REF_OK["points"][0]["objection"])
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

    def test_recalibration_hook_fills_calibration_note(self):
        g, scope = animal_only_record(), humans_scope()
        cfg = A.AdjudicationConfig(recalibration=lambda a: a * 0.5)
        v = A.adjudicate(g, scope, claim_text="x",
                         client=FakeClient(SUP_OK, REF_OK, agree_rounds()), config=cfg)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertIn("recalibrated confidence", sub.evidence["calibration"]["note"])


# ----------------------------------------------------------------------------------
# Full text (WO-C4 full-text grounding: guard segment, agent evidence, depth label, caching)
# ----------------------------------------------------------------------------------
def _record_with_full_text(body: str) -> GroundedRecord:
    g = animal_only_record()
    g.full_text = body
    return g


class TestFullText(unittest.TestCase):
    def test_verbatim_guard_accepts_body_quote(self):
        """A quote present ONLY in the full-text body (not title/abstract) survives the guard, and
        the depth label reflects that full text was used."""
        body = ("Abstract recap. RESULTS Resveratrol extended median lifespan by 31 percent in the "
                "treated cohort. DISCUSSION The effect was dose-dependent.")
        g = _record_with_full_text(body)
        supporter = {"points": [{"quote": "extended median lifespan by 31 percent",
                                 "rationale": "the body reports a lifespan effect"}]}
        fc = FakeClient(supporter, {"points": []}, agree_rounds())
        v = A.adjudicate(g, humans_scope(), claim_text="x", client=fc, config=SINGLE)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.evidence["verbatim_guard"]["supporter_discarded"], 0)
        self.assertEqual(sub.evidence["supporter"]["span"], "extended median lifespan by 31 percent")
        self.assertEqual(sub.evidence["verbatim_guard"]["grounding_corpus"], "title+abstract+fulltext")

    def test_depth_label_abstract_only_when_no_full_text(self):
        g = animal_only_record()   # full_text == ""
        fc = FakeClient(SUP_OK, REF_OK, agree_rounds())
        v = A.adjudicate(g, humans_scope(), claim_text="x", client=fc, config=SINGLE)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.evidence["verbatim_guard"]["grounding_corpus"],
                         "title+abstract (full text unavailable)")

    def test_full_text_cross_section_straddle_discarded(self):
        """A quote spanning two full-text SECTIONS (two real but non-contiguous fragments) is
        discarded — each budgeted section is its own guard segment, so the abstract↔body /
        section↔section junction cannot be straddled (mirrors the title↔abstract straddle guard)."""
        g = _record_with_full_text("Abstract part one sentence.\n\nRESULTS Body part two sentence here.")
        straddle = "one sentence. RESULTS Body part two"       # spans the section junction
        within = "Body part two sentence here"                 # wholly inside the Results section
        supporter = {"points": [{"quote": straddle, "rationale": "straddle (must be discarded)"},
                                 {"quote": within, "rationale": "within one section (survives)"}]}
        fc = FakeClient(supporter, {"points": []}, agree_rounds())
        v = A.adjudicate(g, humans_scope(), claim_text="x", client=fc, config=SINGLE)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.evidence["verbatim_guard"]["supporter_discarded"], 1)
        self.assertEqual(len(sub.evidence["supporter_points"]), 1)
        self.assertEqual(sub.evidence["supporter"]["span"], within)

    def test_full_text_threaded_into_refuter_and_critic_prompts(self):
        g = _record_with_full_text("The body mentions UNIQUEBODYTOKEN exactly once.")
        fc = FakeClient(SUP_OK, REF_OK, agree_rounds())
        A.adjudicate(g, humans_scope(), claim_text="x", client=fc, config=SINGLE)
        self.assertIn("UNIQUEBODYTOKEN", fc.refuter_user_prompts[0])
        self.assertIn("UNIQUEBODYTOKEN", fc.critic_user_prompts[0])
        self.assertIn("SOURCE FULL TEXT", fc.critic_user_prompts[0])

    def test_build_user_identical_shape_when_no_full_text(self):
        """Behaviour identical when full_text=='': no SOURCE FULL TEXT section on any builder."""
        from citeval.prompts import critic, refuter, supporter
        self.assertNotIn("SOURCE FULL TEXT", supporter.build_user("c", "t", "a", ""))
        self.assertIn("SOURCE FULL TEXT", supporter.build_user("c", "t", "a", "BODY"))
        self.assertNotIn("SOURCE FULL TEXT", refuter.build_user("c", "t", "a", "increase", ""))
        self.assertIn("SOURCE FULL TEXT", refuter.build_user("c", "t", "a", "increase", "BODY"))
        base = critic.build_user("c", "t", "a", [], {}, ["fully-supported"], "increase", "")
        self.assertNotIn("SOURCE FULL TEXT", base)
        self.assertIn("SOURCE FULL TEXT",
                      critic.build_user("c", "t", "a", [], {}, ["fully-supported"], "increase", "BODY"))


class TestPromptCaching(unittest.TestCase):
    def test_content_blocks_marks_evidence_prefix_and_strips_sentinel(self):
        from citeval.prompts import EVIDENCE_CACHE_MARK
        user = "EVIDENCE PREFIX" + EVIDENCE_CACHE_MARK + "VARIABLE TAIL"
        blocks = A._content_blocks(user)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["text"], "EVIDENCE PREFIX")
        self.assertEqual(blocks[0]["cache_control"], {"type": "ephemeral"})
        self.assertNotIn(EVIDENCE_CACHE_MARK, blocks[0]["text"])   # sentinel stripped
        self.assertEqual(blocks[1]["text"], "VARIABLE TAIL")
        self.assertNotIn("cache_control", blocks[1])

    def test_content_blocks_single_block_without_sentinel(self):
        self.assertEqual(A._content_blocks("no mark"), [{"type": "text", "text": "no mark"}])

    def test_builders_embed_the_cache_sentinel(self):
        from citeval.prompts import EVIDENCE_CACHE_MARK, critic, refuter, supporter
        self.assertIn(EVIDENCE_CACHE_MARK, supporter.build_user("c", "t", "a"))
        self.assertIn(EVIDENCE_CACHE_MARK, refuter.build_user("c", "t", "a", "increase"))
        self.assertIn(EVIDENCE_CACHE_MARK,
                      critic.build_user("c", "t", "a", [], {}, ["fully-supported"]))


class TestRoundHook(unittest.TestCase):
    def test_on_round_called_once_per_round(self):
        seen: list[int] = []
        cfg = A.AdjudicationConfig(self_consistency_rounds=3, min_valid_rounds=1,
                                   adaptive_early_stopping=False,
                                   on_round=lambda rn, cr, ot: seen.append(rn))
        A.adjudicate(animal_only_record(), humans_scope(), claim_text="x",
                     client=FakeClient(SUP_OK, REF_OK, agree_rounds(n=3)), config=cfg)
        self.assertEqual(seen, [1, 2, 3])

    def test_raising_hook_never_crashes_adjudication(self):
        def _boom(rn, cr, ot):
            raise RuntimeError("hook should be swallowed")
        cfg = A.AdjudicationConfig(self_consistency_rounds=1, min_valid_rounds=1,
                                   adaptive_early_stopping=False, on_round=_boom)
        v = A.adjudicate(animal_only_record(), humans_scope(), claim_text="x",
                         client=FakeClient(SUP_OK, REF_OK, agree_rounds(n=1)), config=cfg)
        self.assertFalse(v.stub)


# ----------------------------------------------------------------------------------
# Critic truncation resilience (WO-C4 fix): grade-last JSON must fit the output cap, a
# truncated round is VISIBLE as n_parse_failed (not a silent abstention), and a lone None
# critic round is resampled once before being counted invalid.
# ----------------------------------------------------------------------------------
# A truncated evidence-first/grade-last response: valid-looking JSON that stops before the
# closing brace (exactly what a 500-token cap produced), so _parse_json returns None.
TRUNCATED_CRITIC = ('{"reasoning": "the source reports a benefit bearing on the claim", '
                    '"decisive_spans": ["significantly increased their survival"], '
                    '"boundary_test_fired": "hedge-preservation", "grade": "partially-supported"')


class TestTruncationResilience(unittest.TestCase):
    def test_token_caps_fit_grade_last_json(self):
        """Root-cause guard: the critic cap must fit the evidence-first/grade-last JSON PAST its
        closing brace, and advocates must not truncate mid-quote when citing full text. Raised to a
        safely NON-clipping 4000 (WO-C4 §3) so measured usage.output_tokens reflects the real
        output length, not the cap. The config defaults mirror the module constants."""
        self.assertGreaterEqual(A.MAX_TOKENS_CRITIC, 4000)
        self.assertGreaterEqual(A.MAX_TOKENS_ADVOCATE, 1200)
        self.assertEqual(A.AdjudicationConfig().max_tokens_critic, A.MAX_TOKENS_CRITIC)
        self.assertEqual(A.AdjudicationConfig().max_tokens_advocate, A.MAX_TOKENS_ADVOCATE)

    def test_truncated_critic_counted_as_parse_failed_not_dropped(self):
        """A critic that truncates every round (incl. the resample) parses to None and must be
        COUNTED as n_parse_failed — the bug that hid a 500-token truncation behind a clean
        ABSTAINED with n_samples=0 and no signal that the model actually replied."""
        g, scope = human_record(), ScopeFrame(organism="Humans", provenance="model-inferred")
        cfg = A.AdjudicationConfig(self_consistency_rounds=3, min_valid_rounds=1,
                                   adaptive_early_stopping=False)
        fc = FakeClient(SUP_OK, REF_OK, [TRUNCATED_CRITIC])   # every critic call truncates
        v = A.adjudicate(g, scope, claim_text="x", client=fc, config=cfg)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        sc = sub.evidence["self_consistency"]
        self.assertEqual(sc["n_parse_failed"], 3)                       # all 3 rounds failed to parse
        self.assertEqual(sub.evidence["confidence"]["n_samples"], 0)    # no valid ordinal rounds
        self.assertEqual(sub.verdict, NOT_ENOUGH_INFO)                  # abstains, but the reason is legible
        self.assertEqual(fc.roles.count("critic"), 6)                  # 3 rounds × (1 call + 1 resample)
        self.assertTrue(any("parse failure" in n or "unparseable" in n for n in v.notes))

    def test_none_critic_round_resampled_once_and_can_recover(self):
        """A critic round that returns None is resampled ONCE at the same settings; if the resample
        parses (a transient truncation clearing), the round is GRADED — coverage is restored rather
        than lost to a single bad draw. One round, script [truncated, valid] → 2 critic calls."""
        g = human_record()
        scope = ScopeFrame(organism="Humans", direction="increase", provenance="model-inferred", tier="high")
        supporter = {"points": [{"quote": "prolonged progression-free survival and overall survival",
                                 "rationale": "supports the survival-benefit claim"}]}
        valid = {"grade": "fully-supported", "confidence": 0.9, "grade_rationale_last": "clear support"}
        cfg = A.AdjudicationConfig(self_consistency_rounds=1, min_valid_rounds=1,
                                   adaptive_early_stopping=False)
        fc = FakeClient(supporter, {"points": []}, [TRUNCATED_CRITIC, valid])
        v = A.adjudicate(g, scope, claim_text="x", client=fc, config=cfg)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.verdict, "fully-supported")               # recovered → graded, not abstained
        self.assertFalse(sub.evidence["abstained"])
        self.assertEqual(fc.roles.count("critic"), 2)                  # first (None) + exactly one resample
        self.assertEqual(sub.evidence["self_consistency"]["n_parse_failed"], 0)   # round parsed on retry
        self.assertEqual(sub.evidence["self_consistency"]["rounds_valid"], 1)

    def test_resample_is_at_most_once_per_round(self):
        """The retry is bounded: a round whose first call AND resample both truncate is NOT retried
        again (at most one resample per round) — 2 rounds → exactly 4 critic calls, both fail."""
        g, scope = human_record(), ScopeFrame(organism="Humans", provenance="model-inferred")
        cfg = A.AdjudicationConfig(self_consistency_rounds=2, min_valid_rounds=1,
                                   adaptive_early_stopping=False)
        fc = FakeClient(SUP_OK, REF_OK, [TRUNCATED_CRITIC])
        A.adjudicate(g, scope, claim_text="x", client=fc, config=cfg)
        self.assertEqual(fc.roles.count("critic"), 4)                  # 2 rounds × (1 + 1), never more

    def test_unhashable_critic_grade_is_counted_not_fatal(self):
        """A critic that emits well-formed JSON with an UNHASHABLE grade ({"grade": []} / {"grade":
        {}}) must NOT crash the case at the `grade in ORDINAL_INDEX` hash lookup (that would abort all
        four axes). It falls through to n_parse_failed and the case abstains legibly. Default config
        keeps early-stopping ON, so the `_unanimous_ordinal` hash lookup is exercised too."""
        g, scope = human_record(), ScopeFrame(organism="Humans", provenance="model-inferred")
        fc = FakeClient(SUP_OK, REF_OK, [{"grade": []}, {"grade": {}}])   # unhashable grade values
        v = A.adjudicate(g, scope, claim_text="x", client=fc)             # default cfg: early-stopping ON
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.verdict, NOT_ENOUGH_INFO)
        self.assertEqual(sub.evidence["confidence"]["n_samples"], 0)      # no valid ordinal rounds
        self.assertGreater(sub.evidence["self_consistency"]["n_parse_failed"], 0)   # counted, not crashed


# ----------------------------------------------------------------------------------
# Cap-from-data (WO-C4 §3): the critic's SDK usage.output_tokens is captured per round so the
# real output-length distribution can set the production cap; a mock without usage degrades to None.
# ----------------------------------------------------------------------------------
class UsageClient:
    """Model client exposing `complete_with_usage` (like the real SDK) — returns (text, out_tok).
    The critic responses cycle by call count so a resample can serve a different (value, out_tok)."""

    def __init__(self, supporter, refuter, critic_pairs):
        self._s, self._r = supporter, refuter
        self._pairs = list(critic_pairs)   # [(value, out_tok), ...]
        self._i = 0

    def complete_with_usage(self, *, model, system, user, max_tokens, temperature=1.0):
        if system.startswith("You are the SUPPORTER"):
            return json.dumps(self._s), 40
        if system.startswith("You are the REFUTER"):
            return json.dumps(self._r), 40
        value, out_tok = self._pairs[self._i % len(self._pairs)]
        self._i += 1
        text = value if isinstance(value, str) else json.dumps(value)
        return text, out_tok


class TestOutputTokenCapture(unittest.TestCase):
    def test_critic_output_tokens_captured_per_round(self):
        """usage.output_tokens is recorded per round in evidence.self_consistency.output_tokens."""
        g = human_record()
        scope = ScopeFrame(organism="Humans", provenance="model-inferred", tier="high")
        graded = {"grade": "fully-supported", "confidence": 0.9, "grade_rationale_last": "ok"}
        client = UsageClient(SUP_OK, REF_OK, [(graded, 347)])
        cfg = A.AdjudicationConfig(self_consistency_rounds=3, min_valid_rounds=1,
                                   adaptive_early_stopping=False)
        v = A.adjudicate(g, scope, claim_text="x", client=client, config=cfg)
        sc = {f.axis: f for f in v.axis_findings}["substantive_support"].evidence["self_consistency"]
        self.assertEqual(sc["output_tokens"], [347, 347, 347])

    def test_resample_captures_the_kept_responses_usage(self):
        """When round 1's first critic draw truncates (None) and the resample parses, the stored
        out_tok is the RESAMPLE's — the usage reflects the response we actually kept, not the draw
        we threw away."""
        g = human_record()
        scope = ScopeFrame(organism="Humans", direction="increase", provenance="model-inferred", tier="high")
        supporter = {"points": [{"quote": "prolonged progression-free survival and overall survival",
                                 "rationale": "supports"}]}
        valid = {"grade": "fully-supported", "confidence": 0.9, "grade_rationale_last": "ok"}
        client = UsageClient(supporter, {"points": []}, [(TRUNCATED_CRITIC, 10), (valid, 99)])
        cfg = A.AdjudicationConfig(self_consistency_rounds=1, min_valid_rounds=1,
                                   adaptive_early_stopping=False)
        v = A.adjudicate(g, scope, claim_text="x", client=client, config=cfg)
        sub = {f.axis: f for f in v.axis_findings}["substantive_support"]
        self.assertEqual(sub.verdict, "fully-supported")                 # recovered on the resample
        self.assertEqual(sub.evidence["self_consistency"]["output_tokens"], [99])

    def test_mock_without_usage_degrades_to_none(self):
        """A mock client that only implements complete()->str (no usage) must not crash: the captured
        output_tokens degrade to None per round (guard for mock clients without usage, WO-C4 §3)."""
        g, scope = human_record(), ScopeFrame(organism="Humans", provenance="model-inferred", tier="high")
        cfg = A.AdjudicationConfig(self_consistency_rounds=2, min_valid_rounds=1,
                                   adaptive_early_stopping=False)
        v = A.adjudicate(g, scope, claim_text="x",
                         client=FakeClient(SUP_OK, REF_OK, agree_rounds(n=2)), config=cfg)
        sc = {f.axis: f for f in v.axis_findings}["substantive_support"].evidence["self_consistency"]
        self.assertEqual(sc["output_tokens"], [None, None])

    def test_complete_backcompat_still_returns_str(self):
        """The real client keeps a text-only complete()->str seam delegating to complete_with_usage,
        so existing str-only callers/mocks are unaffected."""
        self.assertTrue(hasattr(A.AnthropicModelClient, "complete"))
        self.assertTrue(hasattr(A.AnthropicModelClient, "complete_with_usage"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
