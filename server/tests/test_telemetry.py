"""Tests for the telemetry-capturing model client (`citeval_api.telemetry`).

Stdlib `unittest` only (pytest is not installed in the eval env — see test_pricing.py). The
Anthropic client is MOCKED with a `FakeAnthropic`; no live API is touched. Run:

    python -m unittest discover -s server/tests -t server -v
    # or standalone:  python server/tests/test_telemetry.py

Acceptance matrix (WO W1-TELEMETRY):
- all four token tiers captured off `response.usage`;
- debate role tagged by fingerprinting the system prompt (supporter/refuter/critic + unknown);
- cost matches `pricing.cost_of` (per-call and rolled-up), bucketed by role;
- a fake `tools=` kwarg is forwarded to `messages.create` UNCHANGED (tool-use future-proofing).
Plus: content-block cache-control reuse, `user`->`messages` translation, `messages` passthrough,
`temperature` dropped, the per-call usage hook (incl. a raising hook), `create` returns the raw
response, and text extraction skips `tool_use` blocks.
"""
from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace

# Make `citeval` (src/) and `citeval_api` (server/) importable without installation, mirroring
# the root tests' bootstrap. MUST precede the `telemetry` import (it imports `citeval` at module
# load). server/tests/test_telemetry.py -> parent(server/tests) -> server -> repo root.
_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
for _p in (str(_ROOT / "src"), str(_ROOT / "server")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from citeval.prompts import EVIDENCE_CACHE_MARK, critic, refuter, supporter  # noqa: E402
from citeval_api import pricing, telemetry  # noqa: E402
from citeval_api.contracts import RawUsage  # noqa: E402
from citeval_api.telemetry import OPUS_MODEL, TelemetryModelClient  # noqa: E402


# ============================================================================================
# A faithful mock of the Anthropic client: `.messages.create(**kwargs) -> Message`.
# ============================================================================================
def make_usage(inp=0, out=0, cache_write=0, cache_read=0):
    """An SDK-like `response.usage` (attribute access), the shape `pricing.cost_of` consumes."""
    return SimpleNamespace(
        input_tokens=inp,
        output_tokens=out,
        cache_creation_input_tokens=cache_write,
        cache_read_input_tokens=cache_read,
    )


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_use_block(name="do_thing", tid="tu_1", inp=None):
    return SimpleNamespace(type="tool_use", name=name, id=tid, input=inp or {})


def make_message(text="ok", usage=None, content=None):
    """An SDK-like Message: `.content` (list of blocks) + `.usage`."""
    if content is None:
        content = [text_block(text)]
    return SimpleNamespace(content=content, usage=usage, stop_reason="end_turn")


class FakeMessages:
    def __init__(self, outer):
        self._outer = outer

    def create(self, **kwargs):
        self._outer.calls.append(kwargs)
        return self._outer.next_response(kwargs)


class FakeAnthropic:
    """Records every `messages.create` kwargs dict in `.calls`; returns a scripted response.

    `responses` is an optional list consumed in order; otherwise `default_response` (or a plain
    "ok" message with `default_usage`) is returned for every call."""

    def __init__(self, responses=None, default_usage=None, default_response=None):
        self.messages = FakeMessages(self)
        self.calls: list[dict] = []
        self._responses = list(responses) if responses else None
        self._default_usage = default_usage
        self._default_response = default_response

    def next_response(self, kwargs):
        if self._responses:
            return self._responses.pop(0)
        if self._default_response is not None:
            return self._default_response
        return make_message("ok", usage=self._default_usage)


# ============================================================================================
# 1. All four token tiers captured
# ============================================================================================
class TestTokenTiersCaptured(unittest.TestCase):
    def test_all_four_tiers_captured_verbatim(self):
        usage = make_usage(inp=1000, out=500, cache_write=200, cache_read=4000)
        fake = FakeAnthropic(responses=[make_message("hi", usage=usage)])
        client = TelemetryModelClient(fake)

        client.complete_with_usage(model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=100)

        self.assertEqual(len(client.usages), 1)
        rec = client.usages[0]
        self.assertIsInstance(rec, RawUsage)
        self.assertEqual(rec.input_tokens, 1000)
        self.assertEqual(rec.output_tokens, 500)
        self.assertEqual(rec.cache_creation_input_tokens, 200)
        self.assertEqual(rec.cache_read_input_tokens, 4000)

    def test_missing_usage_yields_zero_tiers_but_still_logged(self):
        fake = FakeAnthropic(responses=[make_message("hi", usage=None)])
        client = TelemetryModelClient(fake)
        text, out_tok = client.complete_with_usage(
            model=OPUS_MODEL, system=supporter.SYSTEM, user="q", max_tokens=100)
        self.assertEqual(text, "hi")
        self.assertIsNone(out_tok)
        self.assertEqual(len(client.usages), 1)
        rec = client.usages[0]
        self.assertEqual(
            (rec.input_tokens, rec.output_tokens,
             rec.cache_creation_input_tokens, rec.cache_read_input_tokens),
            (0, 0, 0, 0))
        self.assertEqual(rec.role, "supporter")  # still role-tagged

    def test_partial_and_garbage_usage_never_crashes(self):
        # Only some tiers present; a garbage tier coerces to 0 rather than raising.
        usage = SimpleNamespace(input_tokens=10, output_tokens="oops", cache_read_input_tokens=5)
        fake = FakeAnthropic(responses=[make_message("x", usage=usage)])
        client = TelemetryModelClient(fake)
        client.complete_with_usage(model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=1)
        rec = client.usages[0]
        self.assertEqual(rec.input_tokens, 10)
        self.assertEqual(rec.output_tokens, 0)                 # "oops" -> 0
        self.assertEqual(rec.cache_creation_input_tokens, 0)   # absent -> 0
        self.assertEqual(rec.cache_read_input_tokens, 5)


# ============================================================================================
# 2. Role tagging correct
# ============================================================================================
class TestRoleTagging(unittest.TestCase):
    def _client(self):
        return TelemetryModelClient(FakeAnthropic(default_usage=make_usage(inp=1, out=1)))

    def test_three_roles_tagged(self):
        client = self._client()
        for sysprompt, expected in ((supporter.SYSTEM, "supporter"),
                                    (refuter.SYSTEM, "refuter"),
                                    (critic.SYSTEM, "critic")):
            client.complete_with_usage(model=OPUS_MODEL, system=sysprompt, user="q", max_tokens=1)
        self.assertEqual([u.role for u in client.usages], ["supporter", "refuter", "critic"])

    def test_unknown_system_is_untagged(self):
        client = self._client()
        client.complete_with_usage(
            model=OPUS_MODEL, system="You are a helpful assistant.", user="q", max_tokens=1)
        self.assertIsNone(client.usages[0].role)

    def test_role_survives_appended_tool_instructions(self):
        # W1-CORE-ADJ may append tool-use guidance to a role SYSTEM; fingerprint must still match.
        augmented = refuter.SYSTEM + "\n\nWhen useful, call the `lookup` tool."
        client = self._client()
        client.complete_with_usage(model=OPUS_MODEL, system=augmented, user="q", max_tokens=1)
        self.assertEqual(client.usages[0].role, "refuter")

    def test_role_from_system_content_blocks(self):
        # A cached/structured system prompt (list of content blocks) still fingerprints.
        blocks = [{"type": "text", "text": critic.SYSTEM, "cache_control": {"type": "ephemeral"}}]
        client = self._client()
        client.complete_with_usage(model=OPUS_MODEL, system=blocks, user="q", max_tokens=1)
        self.assertEqual(client.usages[0].role, "critic")

    def test_fingerprint_role_helper_direct(self):
        self.assertEqual(telemetry.fingerprint_role(supporter.SYSTEM), "supporter")
        self.assertEqual(telemetry.fingerprint_role(refuter.SYSTEM), "refuter")
        self.assertEqual(telemetry.fingerprint_role(critic.SYSTEM), "critic")
        self.assertIsNone(telemetry.fingerprint_role(None))
        self.assertIsNone(telemetry.fingerprint_role(""))
        self.assertIsNone(telemetry.fingerprint_role("random"))


# ============================================================================================
# 3. Cost matches pricing.cost_of
# ============================================================================================
class TestCostMatchesPricing(unittest.TestCase):
    def _run_three(self):
        responses = [
            make_message("a", usage=make_usage(inp=1000, out=500, cache_write=200, cache_read=4000)),
            make_message("b", usage=make_usage(inp=800, out=300, cache_read=6000)),
            make_message("c", usage=make_usage(inp=1200, out=900, cache_write=1000)),
        ]
        fake = FakeAnthropic(responses=responses)
        client = TelemetryModelClient(fake)
        client.complete_with_usage(model=OPUS_MODEL, system=supporter.SYSTEM, user="q", max_tokens=1)
        client.complete_with_usage(model=OPUS_MODEL, system=refuter.SYSTEM, user="q", max_tokens=1)
        client.complete_with_usage(model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=1)
        return client

    def test_total_matches_sum_of_cost_of(self):
        client = self._run_three()
        expected = sum(pricing.cost_of(u) for u in client.usages)
        self.assertAlmostEqual(client.summarize().total_usd, round(expected, 6), places=9)

    def test_first_call_cost_hand_computed(self):
        # Reuses the pricing test's hand-computed reference (input 1000/output 500/write 200/
        # read 4000 = $0.06225) to prove the captured usage prices identically.
        client = self._run_three()
        self.assertAlmostEqual(pricing.cost_of(client.usages[0]), 0.06225, places=9)

    def test_per_role_buckets(self):
        client = self._run_three()
        summary = client.summarize()
        self.assertEqual(set(summary.per_role), {"supporter", "refuter", "critic"})
        self.assertEqual(summary.n_model_calls, 3)
        for role in ("supporter", "refuter", "critic"):
            self.assertEqual(summary.per_role[role].n_calls, 1)
        # Total tokens roll up across roles.
        self.assertEqual(summary.tokens.input, 1000 + 800 + 1200)
        self.assertEqual(summary.tokens.output, 500 + 300 + 900)
        self.assertEqual(summary.tokens.cache_write, 200 + 0 + 1000)
        self.assertEqual(summary.tokens.cache_read, 4000 + 6000 + 0)

    def test_summarize_equivalent_to_pricing_summarize(self):
        client = self._run_three()
        self.assertEqual(client.summarize(), pricing.summarize(client.usages))


# ============================================================================================
# 4. A fake tools= kwarg is forwarded unchanged (tool-use future-proofing)
# ============================================================================================
class TestKwargForwarding(unittest.TestCase):
    def _client(self):
        return FakeAnthropic(default_usage=make_usage(inp=1, out=1)), None

    def test_fake_tools_forwarded_unchanged(self):
        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake)
        tools = [{"name": "get_weather", "description": "fake", "input_schema": {"type": "object"}}]
        client.complete_with_usage(
            model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=64, tools=tools)
        sent = fake.calls[-1]
        self.assertIn("tools", sent)
        self.assertIs(sent["tools"], tools)  # same object, unchanged

    def test_tool_choice_and_thinking_forwarded(self):
        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake)
        tool_choice = {"type": "auto"}
        thinking = {"type": "enabled", "budget_tokens": 1024}
        client.complete_with_usage(
            model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=64,
            tools=[{"name": "t"}], tool_choice=tool_choice, thinking=thinking)
        sent = fake.calls[-1]
        self.assertIs(sent["tool_choice"], tool_choice)
        self.assertIs(sent["thinking"], thinking)

    def test_absent_optionals_not_sent_as_null(self):
        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake)
        client.complete_with_usage(model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=64)
        sent = fake.calls[-1]
        for absent in ("tools", "tool_choice", "thinking", "user", "temperature"):
            self.assertNotIn(absent, sent)

    def test_temperature_dropped(self):
        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake)
        # The seam passes temperature; opus-4-8 deprecated it, so it must not reach the wire.
        client.complete_with_usage(
            model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=64, temperature=0.2)
        self.assertNotIn("temperature", fake.calls[-1])

    def test_model_forwarded_and_defaulted(self):
        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake)
        client.complete_with_usage(model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=1)
        self.assertEqual(fake.calls[-1]["model"], OPUS_MODEL)
        # Absent model falls back to the invariant-#4 model id.
        client.create(system=critic.SYSTEM, messages=[{"role": "user", "content": "hi"}], max_tokens=1)
        self.assertEqual(fake.calls[-1]["model"], OPUS_MODEL)

    def test_explicit_model_none_falls_back_to_opus(self):
        # A programmatically-built call (e.g. a future tool-use helper) may pass model=None; it must
        # resolve to Opus (invariant #4), not be forwarded as a spurious null (400) nor dropped.
        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake)
        client.create(model=None, system=critic.SYSTEM,
                      messages=[{"role": "user", "content": "hi"}], max_tokens=1)
        self.assertEqual(fake.calls[-1]["model"], OPUS_MODEL)

    def test_system_and_max_tokens_reach_the_wire(self):
        # system + max_tokens are two of the five WO-required forwarded kwargs; assert they land on
        # messages.create verbatim (max_tokens is tied to the critic-truncation failure mode).
        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake)
        client.complete_with_usage(model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=64)
        sent = fake.calls[-1]
        self.assertEqual(sent["system"], critic.SYSTEM)
        self.assertEqual(sent["max_tokens"], 64)

    def test_system_content_blocks_forwarded_verbatim(self):
        # A cached/structured system (list of content blocks) is forwarded unchanged.
        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake)
        blocks = [{"type": "text", "text": critic.SYSTEM, "cache_control": {"type": "ephemeral"}}]
        client.complete_with_usage(model=OPUS_MODEL, system=blocks, user="q", max_tokens=1)
        self.assertIs(fake.calls[-1]["system"], blocks)


# ============================================================================================
# 5. Content-block cache-control reuse + user->messages translation
# ============================================================================================
class TestContentBlocksAndForwarding(unittest.TestCase):
    def test_user_split_into_cache_marked_blocks(self):
        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake)
        evidence = "TITLE\n\nABSTRACT big reusable evidence"
        tail = "Return the JSON."
        user = f"{evidence}{EVIDENCE_CACHE_MARK}\n\n{tail}"
        client.complete_with_usage(model=OPUS_MODEL, system=critic.SYSTEM, user=user, max_tokens=1)

        sent = fake.calls[-1]
        self.assertNotIn("user", sent)            # user was translated away
        self.assertIn("messages", sent)
        content = sent["messages"][0]["content"]
        self.assertEqual(sent["messages"][0]["role"], "user")
        # Prefix block carries the cache_control breakpoint; sentinel is stripped (model never sees it).
        self.assertEqual(content[0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(content[0]["text"], evidence)
        self.assertNotIn(EVIDENCE_CACHE_MARK, content[0]["text"])
        self.assertEqual(content[1]["text"], f"\n\n{tail}")

    def test_user_without_sentinel_is_single_plain_block(self):
        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake)
        client.complete_with_usage(model=OPUS_MODEL, system=critic.SYSTEM, user="plain", max_tokens=1)
        content = fake.calls[-1]["messages"][0]["content"]
        self.assertEqual(content, [{"type": "text", "text": "plain"}])

    def test_explicit_messages_passthrough_for_tool_use(self):
        # The tool-use path passes a full `messages` list directly; `user` is not used.
        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake)
        messages = [
            {"role": "user", "content": "start"},
            {"role": "assistant", "content": [tool_use_block()]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu_1", "content": "42"}]},
        ]
        client.create(model=OPUS_MODEL, system=critic.SYSTEM, messages=messages,
                      max_tokens=1, tools=[{"name": "t"}])
        sent = fake.calls[-1]
        self.assertIs(sent["messages"], messages)  # forwarded unchanged
        self.assertNotIn("user", sent)

    def test_messages_wins_over_user_when_both_supplied(self):
        # The documented precedence: an explicit `messages` is NOT clobbered by a stray `user`
        # (guards the tool-use loop against the user->messages translation firing spuriously).
        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake)
        messages = [{"role": "user", "content": "the real conversation"}]
        client.create(model=OPUS_MODEL, system=critic.SYSTEM, user="stray text",
                      messages=messages, max_tokens=1)
        sent = fake.calls[-1]
        self.assertIs(sent["messages"], messages)          # untouched
        self.assertNotIn("user", sent)                     # user was NOT translated in
        self.assertEqual(sent["messages"][0]["content"], "the real conversation")


# ============================================================================================
# 6. create() returns the raw response; text extraction skips tool_use blocks
# ============================================================================================
class TestRawResponseAndText(unittest.TestCase):
    def test_create_returns_raw_sdk_response(self):
        resp = make_message("hello", usage=make_usage(inp=5, out=7))
        fake = FakeAnthropic(responses=[resp])
        client = TelemetryModelClient(fake)
        got = client.create(model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=1)
        self.assertIs(got, resp)  # tool-use loop reads tool_use blocks off this
        self.assertEqual(len(client.usages), 1)

    def test_text_extraction_joins_text_skips_tool_use(self):
        content = [text_block("part1 "), tool_use_block(), text_block("part2")]
        fake = FakeAnthropic(responses=[make_message(content=content, usage=make_usage(out=9))])
        client = TelemetryModelClient(fake)
        text, out_tok = client.complete_with_usage(
            model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=1)
        self.assertEqual(text, "part1 part2")
        self.assertEqual(out_tok, 9)

    def test_complete_returns_plain_text(self):
        fake = FakeAnthropic(responses=[make_message("just text", usage=make_usage(out=3))])
        client = TelemetryModelClient(fake)
        self.assertEqual(
            client.complete(model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=1),
            "just text")


# ============================================================================================
# 7. The per-call usage hook (streaming)
# ============================================================================================
class TestUsageHook(unittest.TestCase):
    def test_hook_receives_each_call_usage(self):
        seen: list[RawUsage] = []
        fake = FakeAnthropic(responses=[
            make_message("a", usage=make_usage(inp=10, out=20)),
            make_message("b", usage=make_usage(inp=30, out=40)),
        ])
        client = TelemetryModelClient(fake, on_usage=seen.append)
        client.complete_with_usage(model=OPUS_MODEL, system=supporter.SYSTEM, user="q", max_tokens=1)
        client.complete_with_usage(model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=1)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen, client.usages)             # hook payload == what was logged
        self.assertEqual(seen[0].role, "supporter")
        self.assertEqual(seen[1].input_tokens, 30)
        # A hook consumer can price directly.
        self.assertAlmostEqual(pricing.cost_of(seen[1]), pricing.cost_of(client.usages[1]), places=12)

    def test_hook_settable_after_construction(self):
        seen: list[RawUsage] = []
        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake)
        client.on_usage = seen.append
        client.complete_with_usage(model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=1)
        self.assertEqual(len(seen), 1)

    def test_raising_hook_is_swallowed_but_warned(self):
        def boom(_usage):
            raise RuntimeError("event bus down")

        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake, on_usage=boom)
        # Must not propagate — telemetry can't crash a paid model call — but must surface a warning
        # so a persistently dead hook is not invisible (assertLogs also captures the noise).
        with self.assertLogs("citeval_api.telemetry", level="WARNING") as cm:
            text = client.complete(model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=1)
        self.assertEqual(text, "ok")
        self.assertEqual(len(client.usages), 1)  # still logged despite the hook blowing up
        self.assertTrue(any("on_usage hook raised" in line for line in cm.output))

    def test_hook_fires_after_append(self):
        # The documented ordering: the just-recorded usage is already in the log when the hook runs
        # (so an in-hook cumulative read via `usages`/`summarize()` sees the current call).
        observed: list[int] = []
        fake = FakeAnthropic(responses=[
            make_message("a", usage=make_usage(inp=1, out=1)),
            make_message("b", usage=make_usage(inp=1, out=1)),
        ])
        client = TelemetryModelClient(fake)
        client.on_usage = lambda _u: observed.append(len(client.usages))
        client.complete_with_usage(model=OPUS_MODEL, system=supporter.SYSTEM, user="q", max_tokens=1)
        client.complete_with_usage(model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=1)
        self.assertEqual(observed, [1, 2])


# ============================================================================================
# 8. Log lifecycle
# ============================================================================================
class TestLogLifecycle(unittest.TestCase):
    def test_usages_is_a_copy(self):
        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake)
        client.complete_with_usage(model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=1)
        snapshot = client.usages
        snapshot.clear()
        self.assertEqual(len(client.usages), 1)  # internal log untouched (structural)

    def test_usages_entries_are_isolated_copies(self):
        # Mutating a RETURNED entry (RawUsage is a mutable model) must not corrupt the log/bill.
        fake = FakeAnthropic(default_usage=make_usage(inp=1000, out=500))
        client = TelemetryModelClient(fake)
        client.complete_with_usage(model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=1)
        before = client.summarize().total_usd
        client.usages[0].output_tokens = 10 ** 9   # tamper with the snapshot
        self.assertEqual(client.usages[0].output_tokens, 500)     # log entry unchanged
        self.assertEqual(client.summarize().total_usd, before)    # bill unchanged

    def test_reset_clears_log(self):
        fake = FakeAnthropic(default_usage=make_usage(inp=1, out=1))
        client = TelemetryModelClient(fake)
        client.complete_with_usage(model=OPUS_MODEL, system=critic.SYSTEM, user="q", max_tokens=1)
        self.assertEqual(len(client.usages), 1)
        client.reset()
        self.assertEqual(client.usages, [])
        self.assertEqual(client.summarize().total_usd, 0.0)

    def test_empty_summary(self):
        client = TelemetryModelClient(FakeAnthropic())
        summary = client.summarize()
        self.assertEqual(summary.total_usd, 0.0)
        self.assertEqual(summary.n_model_calls, 0)
        self.assertEqual(summary.per_role, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
