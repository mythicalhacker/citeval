"""Judgment-level regression fence for the adversarial adjudicator.

The other 56 adjudicator tests verify *orchestration* — that the triad is called in order,
that usage is captured, that a mock client is threaded correctly. **None of them pins the
JUDGMENT**: the mapping from real, model-shaped triad output to the emitted grade. That mapping
— the self-consistency aggregation, the abstain/non-substantiating gates, the scope-routing
hard-filter, the direction-reversal guard, the verbatim guard — is where a refactor can silently
change a verdict, and today it is proven only by the full corpus + eval gate (which need grades,
and in CI would need a network).

This file closes that gap **hermetically**. A live model grade cannot be unit-tested
deterministically, but the *mapping* can: we drive the REAL public `adjudicate()` with realistic,
verbatim-correct supporter/refuter/critic responses through a replay client, and assert the grade
it emits. Each test pins one judgment-critical behaviour the reviewer called out as untested. If a
future change to `_aggregate_rounds` / `_decide_outcome` / `_routes_to_grade` / the verbatim guard
alters how genuine model output becomes a grade, a test here fails — with no key and no network.

Provenance note. The worker order asks this to replay W0's FROZEN real transcripts committed under
`corpus/calibration/transcripts/`. Those had not merged when this was built, so per the improvement
plan (reviews/improvements/01_code.md §CQ6) this uses the blessed fallback: hand-authored realistic
triads driven through the same public seam. The `_ReplayClient` below is format-agnostic — it
returns scripted text per agent role — so W0's transcripts can be replayed through the identical
client once they land; wiring that harness is a small, documented follow-up (see the bridge test at
the bottom, which detects committed transcripts and flags that the replay still needs wiring).
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from citeval.adjudicator import AdjudicationConfig, OPUS_MODEL, adjudicate  # noqa: E402
from citeval.contracts import (  # noqa: E402
    CitedIdentifier, GroundedRecord, MeshTag, RetractionInfo, RetractionWatchHit, ScopeFrame,
)
from citeval.prompts import GRADE_VALUES, critic, refuter, supporter  # noqa: E402

# --------------------------------------------------------------------------- grounding fixture
# A mouse study. Every quote asserted below is a verbatim (whitespace-normalized, case-sensitive)
# substring of this title/abstract, so it survives the verbatim guard; fabricated quotes do not.
_TITLE = "Resveratrol reduces markers of inflammation in a murine model."
_ABSTRACT = (
    "In this controlled study, resveratrol reduced markers of inflammation in treated mice. "
    "These effects were observed only in a murine model. No human participants were enrolled, "
    "and the paper reports no clinical outcomes."
)
# A distinct paper whose finding runs OPPOSITE to the claim's asserted direction (for the
# grounded-reversal case).
_REVERSAL_ABSTRACT = (
    "Contrary to expectation, resveratrol increased markers of inflammation in treated mice. "
    "The pro-inflammatory effect was dose-dependent and observed only in a murine model."
)

_SUP_QUOTE = "resveratrol reduced markers of inflammation in treated mice"
_SCOPE_QUOTE = "These effects were observed only in a murine model"
_PLAIN_OBJECTION_QUOTE = "No human participants were enrolled"
_REVERSAL_QUOTE = "resveratrol increased markers of inflammation in treated mice"
_FABRICATED_QUOTE = "resveratrol reverses aging in human patients"   # NOT in title/abstract


def _grounded(abstract: str = _ABSTRACT, *, title: str = _TITLE) -> GroundedRecord:
    return GroundedRecord(
        identifier=CitedIdentifier("pmid", "99999999"),
        title=title,
        abstract=abstract,
        mesh_all=["Animals", "Mice", "Resveratrol", "Inflammation"],
        organism_tags=[MeshTag("Animals", "D000818", ["B01"]),
                       MeshTag("Mice", "D051379", ["B01.050.150.900.649.313.988.400.112.400.560"])],
        population_tags=[],
        sex_tags=[],
        publication_types=["Journal Article"],
        retraction=RetractionInfo(status="NONE_FOUND",
                                  retraction_watch=RetractionWatchHit(present=False),
                                  source_agreement="none"),
        has_humans=False,
        provenance={"source": "fixture"},
        grounding_errors=[],
    )


# A human-relevance claim citing the mouse paper (so the scope axes have a real over-generalization
# to carry — the substantive grade must hold scope constant regardless).
_CLAIM = "Resveratrol reduces inflammation in patients."
_SCOPE = ScopeFrame(organism="Humans", organism_evidence=["patients"], effect="anti-inflammatory",
                    direction="decrease", provenance="text-grounded", tier="medium")


# --------------------------------------------------------------------------- triad JSON builders
def _sup(quote: str = _SUP_QUOTE, rationale: str = "the paper reports an anti-inflammatory effect") -> str:
    return json.dumps({"points": [{"quote": quote, "rationale": rationale}]})


def _ref(points: list[dict]) -> str:
    return json.dumps({"points": points})


def _critic(grade: str, confidence: float = 0.95,
            rationale: str = "graded from the adversarial exchange") -> str:
    return json.dumps({"grade": grade, "confidence": confidence, "grade_rationale_last": rationale})


# --------------------------------------------------------------------------- replay client
class _ReplayClient:
    """Deterministically replays scripted triad responses through the REAL adjudicate() seam.

    Dispatches on which agent SYSTEM prompt it receives (robust to the critic-resample path),
    so it exercises the real aggregation/guards with no network and no key. Supporter and refuter
    return a fixed response every round; the critic returns one scripted response per ROUND
    (clamped to the last, so a 1-element list means a unanimous vote)."""

    def __init__(self, supporter_json: str, refuter_json: str, critic_jsons: list[str]):
        self._sup = supporter_json
        self._ref = refuter_json
        self._critic = list(critic_jsons)
        self._critic_i = 0
        self.calls = {"supporter": 0, "refuter": 0, "critic": 0}
        self.models_seen: set[str] = set()

    def complete_with_usage(self, *, model, system, user, max_tokens, temperature=1.0):
        self.models_seen.add(model)
        if system == supporter.SYSTEM:
            self.calls["supporter"] += 1
            return self._sup, 20
        if system == refuter.SYSTEM:
            self.calls["refuter"] += 1
            return self._ref, 20
        if system == critic.SYSTEM:
            i = self._critic_i
            self._critic_i += 1
            self.calls["critic"] += 1
            text = self._critic[i] if i < len(self._critic) else self._critic[-1]
            return text, 60
        raise AssertionError("replay client saw a system prompt that is not supporter/refuter/critic")


def _adjudicate(client: _ReplayClient, *, grounded: GroundedRecord = None, config=None):
    return adjudicate(grounded or _grounded(), _SCOPE, _CLAIM,
                      client=client, config=config or AdjudicationConfig())


def _substantive(verdict):
    return next(f for f in verdict.axis_findings if f.axis == "substantive_support")


# =========================================================================== tests
class JudgmentMappingTests(unittest.TestCase):
    """Each test pins one judgment behaviour: genuine model-shaped output -> emitted grade."""

    def test_overreach_grade_with_scope_point_routed_to_rollup_not_grade(self):
        """The headline behaviour (CONTEXT_PACK §6). A supporter with a real supporting span and a
        refuter whose only objection is a scope over-generalization: the critic grades
        'supported-with-overreach', the grade stands at high confidence, and the scope point is
        carried in `refuter_scope_notes` (the rollup) — it never lands on `refuter_points` (the
        grade) and never depresses it."""
        client = _ReplayClient(
            _sup(),
            _ref([{"quote": _SCOPE_QUOTE, "objection": "the claim over-generalizes mice to humans",
                   "distortion_type": "over_generalization", "routes_to": "rollup_not_grade"}]),
            [_critic("supported-with-overreach")],
        )
        v = _adjudicate(client)
        sub = _substantive(v)
        self.assertEqual(sub.verdict, "supported-with-overreach")
        self.assertEqual(sub.tier, "high")               # a_exact = 1.0 >= 0.8
        self.assertFalse(sub.evidence["abstained"])
        # scope over-generalization routed to the rollup, NOT the grade
        self.assertEqual(sub.evidence["refuter_points"], [],
                         "a scope over-generalization must NOT reach the grade-routed refuter points")
        self.assertGreaterEqual(len(sub.evidence["refuter_scope_notes"]), 1,
                                "the scope over-generalization must be carried as a rollup scope note")

    def test_scope_point_does_not_abstain_when_supporter_grounds_evidence(self):
        """Even with the refuter contributing only a rollup-routed scope note (zero grade-routed
        refuter points), a grounded supporter span is enough evidence to grade — not abstain."""
        client = _ReplayClient(
            _sup(),
            _ref([{"quote": _SCOPE_QUOTE, "objection": "over-generalized",
                   "distortion_type": "over_generalization", "routes_to": "rollup_not_grade"}]),
            [_critic("fully-supported")],
        )
        sub = _substantive(_adjudicate(client))
        self.assertEqual(sub.verdict, "fully-supported")
        self.assertFalse(sub.evidence["abstained"])

    def test_contradicted_without_grounded_reversal_is_downgraded(self):
        """The direction-reversal guard. The critic votes 'contradicted' (most severe), but no
        surviving refuter point is tagged `direction_reversal`, so the reversal rests on rhetoric,
        not the source. It is downgraded one step to 'unsupported-for-the-claim', while the raw
        'contradicted' vote stays visible for audit and a guard note is emitted."""
        client = _ReplayClient(
            _sup(),
            _ref([{"quote": _PLAIN_OBJECTION_QUOTE, "objection": "the paper does not support the claim"}]),
            [_critic("contradicted")],
        )
        v = _adjudicate(client)
        sub = _substantive(v)
        self.assertEqual(sub.verdict, "unsupported-for-the-claim",
                         "an ungrounded 'contradicted' must downgrade, not stand")
        self.assertFalse(sub.evidence["abstained"])
        self.assertIn("contradicted", sub.evidence["self_consistency"]["ordinal_distribution"],
                      "the raw contradicted vote must remain visible for audit")
        self.assertTrue(any("Direction-reversal guard" in n for n in v.notes),
                        "the downgrade must be explained in the verdict notes")

    def test_contradicted_with_grounded_reversal_stands(self):
        """The complement: when a refuter `direction_reversal` point survives the verbatim guard
        (a real opposite-direction span in the source), a 'contradicted' vote is grounded and
        stands."""
        client = _ReplayClient(
            _sup(_REVERSAL_QUOTE, "the paper's own result runs opposite to the claim"),
            _ref([{"quote": _REVERSAL_QUOTE, "objection": "the source finds the OPPOSITE direction",
                   "distortion_type": "direction_reversal"}]),
            [_critic("contradicted")],
            )
        sub = _substantive(_adjudicate(client, grounded=_grounded(_REVERSAL_ABSTRACT)))
        self.assertEqual(sub.verdict, "contradicted")
        self.assertEqual(sub.tier, "high")
        self.assertFalse(sub.evidence["abstained"])

    def test_fabricated_quotes_abstain_despite_confident_critic(self):
        """The verbatim guard is load-bearing for honesty. Both advocates quote text that is NOT in
        the source, so both points are discarded; with no grounded evidence either way the system
        ABSTAINS (NOT_ENOUGH_INFO) even though the critic confidently voted 'fully-supported'. A
        confident but ungrounded grade must never be emitted."""
        client = _ReplayClient(
            _sup(_FABRICATED_QUOTE, "fabricated support"),
            _ref([{"quote": _FABRICATED_QUOTE, "objection": "fabricated objection"}]),
            [_critic("fully-supported")],
        )
        sub = _substantive(_adjudicate(client))
        self.assertEqual(sub.verdict, "NOT_ENOUGH_INFO")
        self.assertTrue(sub.evidence["abstained"])
        # every round's single fabricated supporter quote is discarded by the verbatim guard
        rounds_run = sub.evidence["self_consistency"]["rounds_run"]
        self.assertEqual(sub.evidence["verbatim_guard"]["supporter_discarded"], rounds_run)
        self.assertGreaterEqual(rounds_run, 1)

    def test_pure_adjacent_split_resolves_and_does_not_abstain(self):
        """The abstain carve-out. A dispersed vote whose exact agreement is BELOW tau_abstain (0.5)
        but is entirely within +/-1 of g* (a pure adjacent split) must resolve to g*, not abstain —
        that spread is ordinal boundary noise, not genuine disagreement."""
        votes = ["fully-supported", "fully-supported",
                 "supported-with-overreach", "supported-with-overreach", "supported-with-overreach",
                 "partially-supported", "partially-supported"]      # {0:2, 1:3, 2:2} over N=7
        client = _ReplayClient(_sup(), _ref([]), [_critic(g) for g in votes])
        sub = _substantive(_adjudicate(client))
        self.assertEqual(sub.verdict, "supported-with-overreach")   # g* = median-nearest modal
        self.assertFalse(sub.evidence["abstained"])
        sc = sub.evidence["self_consistency"]
        self.assertLess(sc["a_exact"], 0.5, "this case must exercise the a_exact < tau path")
        self.assertEqual(sc["a_adj"], 1.0, "and be saved by the pure-adjacent carve-out")

    def test_non_substantiating_majority_is_trap2_not_a_grade(self):
        """A critic majority of 'N/A — non-substantiating' (a method/background/passing citation) is
        Trap 2 — off the support scale — recorded as non-substantiating, never as a graded verdict."""
        client = _ReplayClient(_sup(), _ref([]), [_critic("N/A — non-substantiating")])
        sub = _substantive(_adjudicate(client))
        self.assertEqual(sub.verdict, "N/A — non-substantiating")
        self.assertTrue(sub.evidence["non_substantiating"])
        self.assertFalse(sub.evidence["abstained"])

    def test_clean_unanimous_support_is_high_confidence_and_early_stops(self):
        """Positive control + adaptive early-stopping. A unanimous 'fully-supported' vote grades at
        high confidence and stops after the min-valid floor (4 of 7 rounds) — the remaining rounds
        cannot change the median-aware g*."""
        client = _ReplayClient(_sup(), _ref([]), [_critic("fully-supported")])
        sub = _substantive(_adjudicate(client))
        self.assertEqual(sub.verdict, "fully-supported")
        self.assertEqual(sub.tier, "high")
        self.assertEqual(sub.evidence["self_consistency"]["rounds_run"], 4,
                         "unanimous ordinal rounds must trigger adaptive early-stopping at the floor")
        self.assertEqual(client.calls["critic"], 4)

    def test_opus_model_requested_on_every_call(self):
        """Invariant #4 is testable at the seam: every triad call must request Opus 4.8, never a
        cheaper/faster model."""
        client = _ReplayClient(_sup(), _ref([]), [_critic("fully-supported")])
        _adjudicate(client)
        self.assertEqual(client.models_seen, {OPUS_MODEL})
        self.assertGreaterEqual(client.calls["supporter"], 1)
        self.assertGreaterEqual(client.calls["refuter"], 1)
        self.assertGreaterEqual(client.calls["critic"], 1)


class CommittedTranscriptReplayTests(unittest.TestCase):
    """Bridge to W0's frozen real transcripts. It skips both while they are absent AND (honestly)
    while they are present-but-unwired, so it never falsely reports that real transcripts are being
    asserted. The hand-authored JudgmentMappingTests above are the load-bearing fence today; wiring
    the replay harness is a small, documented follow-up (see the test body) once W0 commits the
    transcripts plus each case's grounding."""

    _TRANSCRIPTS = Path(__file__).resolve().parents[1] / "corpus" / "calibration" / "transcripts"

    def test_replays_committed_transcripts_if_present(self):
        if not self._TRANSCRIPTS.is_dir():
            self.skipTest("W0 frozen transcripts (corpus/calibration/transcripts/) not committed yet")
        case_dirs = [d for d in sorted(self._TRANSCRIPTS.iterdir()) if d.is_dir()]
        # Honest bridge: this never trivially PASSES on the presence of transcripts (that would
        # falsely imply the replay is wired). When W0's fixtures land, replace this skip with the
        # real harness: for each case dir, read the role files per round, return them through
        # `_ReplayClient`, rebuild that case's GroundedRecord (needed for the verbatim guard), and
        # assert the emitted verdict equals the committed grade in graded_predictions_cal30.jsonl.
        self.skipTest(
            f"transcripts present ({len(case_dirs)} case dir(s)) — wire up the replay harness "
            f"(see this test's body) so real transcripts are asserted, not just detected"
            if case_dirs else "transcripts/ present but contains no per-case directories yet")


if __name__ == "__main__":
    unittest.main()
