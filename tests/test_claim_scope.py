"""Unit tests for C3 claim-scope parsing (WO-C3).

No live API: the Opus path is exercised through an injected FakeClient whose
`messages.create` returns a canned response mirroring the real Anthropic SDK
shape (`response.content[0].text`). Run:

    python -m unittest tests.test_claim_scope      # from repo root
    python tests/test_claim_scope.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest
from dataclasses import fields
from types import SimpleNamespace

# Make `citeval` importable without a conftest — the package lives under src/.
_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from citeval import claim_scope as cs  # noqa: E402
from citeval.contracts import ScopeFrame  # noqa: E402

# Real eval B-cases (verbatim from data/eval/eval_set.json).
B01 = ("Resveratrol has shown promising clinical benefits as anti-aging, "
       "anti-inflammatory, anti-diabetic, anti-viral, anti-neoplastic, and anti-CVD agents.")
B04 = ("Interleukin (IL)-6, the activator of transcription (STAT) 3 signaling, and "
       "mitogen-activated protein kinase (MAPK/ERK) are linked to CC, leading to skeletal "
       "muscle wasting, cardiac dysfunction, and hypothalamic inflammation, impairing "
       "prognosis in patients with CC.")
# B05: asserts therapeutic/human relevance with NO explicit human word — the key case.
B05 = ("Therefore, it can be targeted for various therapeutic purposes; for instance, "
       "tofacitinib, a STAT3 inhibitor, can regulate microglial activation through the "
       "JAK/STAT pathway and promote the recovery of motor function after spinal cord injury30.")
IN_MICE = "Resveratrol extends lifespan in mice."
HEDGED = "Whether this mechanism holds in humans is unknown."


class FakeClient:
    """Mimics anthropic.Anthropic: `.messages.create(**kw)` -> object with a
    `.content` list of text blocks. Records the kwargs it was called with."""

    def __init__(self, payload, *, raises=None):
        self._payload = payload
        self._raises = raises
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises is not None:
            raise self._raises
        text = self._payload if isinstance(self._payload, str) else json.dumps(self._payload)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def _reply(**over):
    base = {
        "organism": None, "organism_evidence": [], "organism_provenance": "none",
        "population": None, "population_evidence": [],
        "effect": None, "dose_stated": False, "tier": "low", "rationale": "test",
    }
    base.update(over)
    return base


class ModelPathTests(unittest.TestCase):
    def test_b05_infers_human_scope_model_inferred(self):
        """Acceptance: B05 -> organism 'Humans', model-inferred, appropriate tier,
        verbatim evidence span. This is what lets species_scope flag it downstream."""
        span = "promote the recovery of motor function after spinal cord injury"
        client = FakeClient(_reply(
            organism="Humans", organism_evidence=[span],
            organism_provenance="model-inferred",
            effect="promote recovery of motor function", tier="medium",
        ))
        frame = cs.parse_claim_scope_model(B05, client=client)
        self.assertEqual(frame.organism, "Humans")
        self.assertEqual(frame.provenance, "model-inferred")
        self.assertEqual(frame.tier, "medium")  # clear relevance -> appropriate (medium) tier
        self.assertEqual(frame.organism_evidence, [span])
        # Opus 4.8 on every model call (invariant #4).
        self.assertEqual(client.calls[0]["model"], "claude-opus-4-8")

    def test_bcase_explicit_marker_text_grounded(self):
        """B-cases: organism 'Humans' with a correct verbatim evidence span."""
        client = FakeClient(_reply(
            organism="Humans", organism_evidence=["clinical benefits"],
            organism_provenance="text-grounded", effect="clinical benefits", tier="high",
        ))
        frame = cs.parse_claim_scope_model(B01, client=client)
        self.assertEqual(frame.organism, "Humans")
        self.assertEqual(frame.provenance, "text-grounded")
        self.assertEqual(frame.organism_evidence, ["clinical benefits"])

    def test_bcase_patients_organism(self):
        client = FakeClient(_reply(
            organism="Humans", organism_evidence=["patients with CC"],
            organism_provenance="text-grounded", tier="high",
        ))
        frame = cs.parse_claim_scope_model(B04, client=client)
        self.assertEqual(frame.organism, "Humans")
        self.assertEqual(frame.organism_evidence, ["patients with CC"])

    def test_population_coerced_and_evidence_required(self):
        """Model-path population is coerced to the pediatric/adult vocabulary; a
        junk value is dropped, and a valid value with no verbatim span is dropped."""
        claim = "The intervention improved outcomes in children with the condition."
        ok = cs.parse_claim_scope_model(
            claim, client=FakeClient(_reply(population="pediatric",
                                            population_evidence=["in children"])))
        self.assertEqual(ok.population, "pediatric")
        self.assertEqual(ok.population_evidence, ["in children"])
        junk = cs.parse_claim_scope_model(
            claim, client=FakeClient(_reply(population="mice-only",
                                            population_evidence=["in children"])))
        self.assertIsNone(junk.population)
        no_span = cs.parse_claim_scope_model(
            claim, client=FakeClient(_reply(population="pediatric",
                                            population_evidence=["in neonates"])))
        self.assertIsNone(no_span.population)  # span absent from claim -> not grounded
        self.assertEqual(no_span.population_evidence, [])

    def test_in_mice_not_humans(self):
        """Constructed correctly-scoped claim: organism 'Mice', NOT 'Humans'.
        `effect` (which the lexical path never sets) proves the model path ran."""
        client = FakeClient(_reply(
            organism="Mice", organism_evidence=["in mice"],
            organism_provenance="text-grounded", effect="extends lifespan", tier="high",
        ))
        frame = cs.parse_claim_scope_model(IN_MICE, client=client)
        self.assertEqual(frame.organism, "Mice")
        self.assertNotEqual(frame.organism, "Humans")
        self.assertEqual(frame.effect, "extends lifespan")

    def test_hedged_does_not_assert_human_scope(self):
        client = FakeClient(_reply(organism=None, organism_provenance="none", tier="low"))
        frame = cs.parse_claim_scope_model(HEDGED, client=client)
        self.assertIsNone(frame.organism)
        self.assertNotEqual(frame.organism, "Humans")

    def test_verbatim_guard_drops_hallucinated_span(self):
        """Spans that are not a verbatim substring of the claim are dropped;
        genuine ones survive."""
        client = FakeClient(_reply(
            organism="Humans",
            organism_evidence=["clinical benefits", "in patients with cancer"],
            organism_provenance="text-grounded", tier="medium",
        ))
        frame = cs.parse_claim_scope_model(B01, client=client)
        self.assertEqual(frame.organism_evidence, ["clinical benefits"])

    def test_invalid_tier_coerced_to_low(self):
        client = FakeClient(_reply(organism="Humans", organism_provenance="text-grounded",
                                   tier="extreme"))
        frame = cs.parse_claim_scope_model(B01, client=client)
        self.assertEqual(frame.tier, "low")

    def test_bad_organism_provenance_defaults_to_model_inferred(self):
        client = FakeClient(_reply(organism="Humans", organism_provenance="bogus", tier="medium"))
        frame = cs.parse_claim_scope_model(B01, client=client)
        self.assertEqual(frame.provenance, "model-inferred")

    def test_output_validates_against_scopeframe(self):
        client = FakeClient(_reply(organism="Humans", organism_provenance="text-grounded",
                                   organism_evidence=["clinical benefits"], tier="high"))
        frame = cs.parse_claim_scope_model(B01, client=client)
        self.assertIsInstance(frame, ScopeFrame)
        names = {f.name for f in fields(ScopeFrame)}
        self.assertEqual(names, {
            "organism", "organism_evidence", "population", "population_evidence",
            "effect", "direction", "direction_evidence", "dose_stated", "provenance", "tier",
        })
        # C3's model path emits only the three real confidence tiers (not "n/a").
        self.assertIn(frame.tier, ("high", "medium", "low"))
        self.assertIn(frame.provenance, ("text-grounded", "model-inferred"))

    def test_organism_dropped_when_no_verbatim_evidence(self):
        """Honesty rule: an asserted organism with no surviving verbatim span is
        ungrounded on the claim side -> dropped, never emitted as an over-assertion."""
        claim = "Knockdown of STAT3 reduced activation in cultured cells."
        client = FakeClient(_reply(
            organism="Humans", organism_evidence=["in patients"],  # not in the claim
            organism_provenance="text-grounded", tier="medium",
        ))
        frame = cs.parse_claim_scope_model(claim, client=client)
        self.assertIsNone(frame.organism)
        self.assertEqual(frame.organism_evidence, [])
        self.assertEqual(frame.provenance, "model-inferred")

    def test_verbatim_guard_tolerates_recased_span(self):
        """A sentence-initial capital must not cause a false drop; the stored span
        is the claim's actual (verbatim) casing."""
        claim = "Clinical benefits were observed."
        client = FakeClient(_reply(
            organism="Humans", organism_evidence=["clinical benefits"],  # lowercased echo
            organism_provenance="text-grounded", tier="medium",
        ))
        frame = cs.parse_claim_scope_model(claim, client=client)
        self.assertEqual(frame.organism, "Humans")
        self.assertEqual(frame.organism_evidence, ["Clinical benefits"])

    def test_evidence_as_bare_string_is_salvaged_not_iterated(self):
        """A string (not array) evidence must be treated as one span, not iterated
        into single characters."""
        client = FakeClient(_reply(
            organism="Mice", organism_evidence="in mice",
            organism_provenance="text-grounded", tier="high",
        ))
        frame = cs.parse_claim_scope_model(IN_MICE, client=client)
        self.assertEqual(frame.organism_evidence, ["in mice"])

    def test_organism_canonicalized_to_vocabulary(self):
        """Off-list / case-variant organism is canonicalized so _species_axis routes
        correctly (else B05-style human scope would misroute to SCOPE_UNCERTAIN)."""
        client = FakeClient(_reply(
            organism="human", organism_evidence=["clinical benefits"],
            organism_provenance="text-grounded", tier="high",
        ))
        frame = cs.parse_claim_scope_model(B01, client=client)
        self.assertEqual(frame.organism, "Humans")

    def test_dose_stated_string_false_not_truthy(self):
        """A stringified boolean must not fabricate a dose flag (invariant #3)."""
        yes = cs.parse_claim_scope_model(B01, client=FakeClient(_reply(dose_stated="false")))
        self.assertFalse(yes.dose_stated)
        real = cs.parse_claim_scope_model(B01, client=FakeClient(_reply(dose_stated=True)))
        self.assertTrue(real.dose_stated)

    def test_effect_kept_only_if_verbatim(self):
        client = FakeClient(_reply(effect="promotes neuronal survival"))  # not in claim
        frame = cs.parse_claim_scope_model("The drug promoted neurite outgrowth.", client=client)
        self.assertIsNone(frame.effect)

    def test_api_error_falls_back_to_lexical_with_warning(self):
        """A model failure degrades to lexical AND logs a warning (observable
        downgrade — no silent masquerade)."""
        client = FakeClient(None, raises=RuntimeError("network down"))
        with self.assertLogs("citeval.claim_scope", level="WARNING") as cm:
            frame = cs.parse_claim_scope_model(B01, client=client)
        self.assertEqual(frame, cs.parse_claim_scope_lexical(B01))
        self.assertTrue(any("falling back to lexical" in m for m in cm.output))

    def test_malformed_json_falls_back_to_lexical_with_warning(self):
        client = FakeClient("Sorry, I cannot produce JSON for that.")
        with self.assertLogs("citeval.claim_scope", level="WARNING"):
            frame = cs.parse_claim_scope_model(IN_MICE, client=client)
        # lexical still recovers the explicit "in mice" marker.
        self.assertEqual(frame.organism, "Mice")

    def test_json_embedded_in_prose_is_parsed(self):
        client = FakeClient('Here is the scope:\n{"organism": "Mice", '
                            '"organism_evidence": ["in mice"], "effect": "extends lifespan", '
                            '"organism_provenance": "text-grounded", "tier": "high"}\nDone.')
        # assertNoLogs proves the prose was parsed by the model path, not rescued
        # by a silent lexical fallback; `effect` (lexical never sets it) confirms it.
        with self.assertNoLogs("citeval.claim_scope", level="WARNING"):
            frame = cs.parse_claim_scope_model(IN_MICE, client=client)
        self.assertEqual(frame.organism, "Mice")
        self.assertEqual(frame.effect, "extends lifespan")


class LexicalFallbackTests(unittest.TestCase):
    def test_bcase_explicit_marker(self):
        frame = cs.parse_claim_scope_lexical(B01)
        self.assertEqual(frame.organism, "Humans")
        self.assertEqual(frame.provenance, "text-grounded")

    def test_in_mice(self):
        frame = cs.parse_claim_scope_lexical(IN_MICE)
        self.assertEqual(frame.organism, "Mice")

    def test_b05_missed_offline_documented_limitation(self):
        """Offline, the lexical stub cannot detect B05's implicit human scope —
        organism stays None, so the scorer holds at 16/17. Expected and honest."""
        frame = cs.parse_claim_scope_lexical(B05)
        self.assertIsNone(frame.organism)


class DispatchTests(unittest.TestCase):
    def test_uses_lexical_when_key_absent(self):
        import os
        saved = os.environ.pop("ANTHROPIC_API_KEY", None)
        orig_get_client = cs._get_client

        def _boom():  # the no-key path must never construct a client / touch the API
            raise AssertionError("dispatch built a client with no ANTHROPIC_API_KEY")

        cs._get_client = _boom
        try:
            frame = cs.parse_claim_scope(B05)
            self.assertEqual(frame, cs.parse_claim_scope_lexical(B05))
        finally:
            cs._get_client = orig_get_client
            if saved is not None:
                os.environ["ANTHROPIC_API_KEY"] = saved


if __name__ == "__main__":
    unittest.main(verbosity=2)
