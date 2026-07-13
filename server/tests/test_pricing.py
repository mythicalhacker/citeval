"""Tests for the cost model (`citeval_api.pricing`).

Written as `unittest.TestCase` so they run under the stdlib (pytest is not installed in the
eval env). Run:  python -m unittest discover -s server/tests -t server -v
"""
import unittest
from types import SimpleNamespace

from citeval_api import pricing
from citeval_api.contracts import TelemetrySummary


class TestCostOf(unittest.TestCase):
    # Hand-computed reference. With PRICING = {input 15.0, output 75.0, cache_write 18.75,
    # cache_read 1.50} USD per MILLION tokens and this usage:
    #   input 1000, output 500, cache_creation 200, cache_read 4000
    # cost = (1000*15.0 + 500*75.0 + 200*18.75 + 4000*1.50) / 1e6
    #      = (15000 + 37500 + 3750 + 6000) / 1e6
    #      = 62250 / 1e6 = 0.06225
    EXPECTED = 0.06225

    def _usage_dict(self):
        return {
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_creation_input_tokens": 200,
            "cache_read_input_tokens": 4000,
        }

    def test_hand_computed_from_dict(self):
        self.assertAlmostEqual(pricing.cost_of(self._usage_dict()), self.EXPECTED, places=9)

    def test_hand_computed_from_sdk_like_object(self):
        # W1-TELEMETRY forwards the SDK `response.usage` verbatim (attribute access) — cost_of
        # must price it identically to the dict form.
        usage = SimpleNamespace(**self._usage_dict())
        self.assertAlmostEqual(pricing.cost_of(usage), self.EXPECTED, places=9)

    def test_pricing_table_shape(self):
        self.assertEqual(set(pricing.PRICING), {"input", "output", "cache_write", "cache_read"})
        for v in pricing.PRICING.values():
            self.assertIsInstance(v, float)

    def test_missing_tiers_price_as_zero(self):
        # A partial usage (only input) must not crash and must price only what is present.
        self.assertAlmostEqual(pricing.cost_of({"input_tokens": 2_000_000}), 30.0, places=9)

    def test_none_and_garbage_are_safe(self):
        self.assertEqual(pricing.cost_of(None), 0.0)
        self.assertEqual(pricing.cost_of({}), 0.0)
        # Non-numeric token counts coerce to 0 rather than raising.
        self.assertEqual(pricing.cost_of({"input_tokens": "oops"}), 0.0)

    def test_negative_counts_cannot_credit_the_bill(self):
        self.assertEqual(pricing.cost_of({"input_tokens": -5000}), 0.0)


class TestSummarize(unittest.TestCase):
    def setUp(self):
        # supporter: cost = (1000*15 + 200*75 + 0 + 5000*1.5)/1e6 = 37500/1e6 = 0.0375
        # critic:    cost = (500*15 + 600*75 + 100*18.75 + 3000*1.5)/1e6 = 58875/1e6 = 0.058875
        self.supporter = {
            "input_tokens": 1000, "output_tokens": 200,
            "cache_creation_input_tokens": 0, "cache_read_input_tokens": 5000,
            "role": "supporter",
        }
        self.critic = {
            "input_tokens": 500, "output_tokens": 600,
            "cache_creation_input_tokens": 100, "cache_read_input_tokens": 3000,
            "role": "critic",
        }
        self.summary = pricing.summarize([self.supporter, self.critic])

    def test_returns_telemetry_summary(self):
        self.assertIsInstance(self.summary, TelemetrySummary)

    def test_total_cost_is_sum_of_parts(self):
        self.assertAlmostEqual(self.summary.total_usd, 0.0375 + 0.058875, places=9)

    def test_n_model_calls(self):
        self.assertEqual(self.summary.n_model_calls, 2)

    def test_aggregate_tokens(self):
        t = self.summary.tokens
        self.assertEqual((t.input, t.output, t.cache_read, t.cache_write), (1500, 800, 8000, 100))

    def test_per_role_breakdown(self):
        self.assertEqual(set(self.summary.per_role), {"supporter", "critic"})
        sup = self.summary.per_role["supporter"]
        self.assertAlmostEqual(sup.usd, 0.0375, places=9)
        self.assertEqual(sup.n_calls, 1)
        self.assertEqual((sup.tokens.input, sup.tokens.cache_read), (1000, 5000))
        crit = self.summary.per_role["critic"]
        self.assertAlmostEqual(crit.usd, 0.058875, places=9)

    def test_untagged_usage_bucketed_as_unknown(self):
        s = pricing.summarize([{"input_tokens": 1000}])  # no role
        self.assertIn("unknown", s.per_role)
        self.assertEqual(s.per_role["unknown"].n_calls, 1)

    def test_empty_is_zeroed(self):
        s = pricing.summarize([])
        self.assertEqual(s.total_usd, 0.0)
        self.assertEqual(s.n_model_calls, 0)
        self.assertEqual(s.per_role, {})


if __name__ == "__main__":
    unittest.main()
