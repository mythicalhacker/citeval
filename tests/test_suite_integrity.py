"""Meta-guard: no test module may silently drop out of `unittest discover`.

Why this exists. Three modules — ``test_demo``, ``test_reporting``, ``test_showcase`` — were
written pytest-style (plain module-level ``test_*`` functions with a homegrown runner and no
``unittest.TestCase``). ``python -m unittest discover`` (the sanctioned ``make test`` runner)
therefore collected **ZERO** tests from each of them, while every one passed when the file was
run standalone. ~32 tests — including a curated judgment check — were invisible to CI. They now
carry a ``load_tests()`` hook that registers their functions.

These assertions are the tripwire for that exact class of rot: if a module regresses to the
pytest-style pattern, or a ``load_tests`` hook is deleted, or a whole module otherwise stops
being collected, the suite goes **red** instead of silently shrinking. All checks use ``>=`` so
adding tests never trips them — only a drop does.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_TESTS_DIR))                    # import sibling test_*.py by bare name
sys.path.insert(0, str(_TESTS_DIR.parent / "src"))    # the citeval package the tests import

# The three modules that were the silent zero-collectors. This session owns them exclusively, so
# these floors are stable; each is pinned at its current count so removing the load_tests hook
# (which drops the module to 0) trips this immediately. Bump only when tests are intentionally
# removed from these files.
_MIN_PER_NAMED_MODULE = {
    "test_demo": 13,
    "test_reporting": 13,
    "test_showcase": 6,
}

# Coarse whole-suite backstop. `make test` collected 234 before this work and 279 after (the 32
# previously-invisible tests, plus this session's new judgment/integrity tests). The per-module
# checks above are what actually catch a module dropping out — a vanished module collects 0 and
# trips test_every_test_module_collects_at_least_one deterministically — so this floor is only a
# secondary net against broad silent shrinkage. It sits below 279 with headroom so normal
# cross-session churn never makes it flaky, while still tripping if even the smallest substantial
# non-owned module (test_grounding, 15 tests) drops out: 279 - 15 = 264 < 265.
_MIN_TOTAL = 265


def _iter_test_module_names():
    for path in sorted(_TESTS_DIR.glob("test_*.py")):
        yield path.stem


class SuiteIntegrityTests(unittest.TestCase):
    """Structural guards on `unittest discover` collection — no assertions on behaviour."""

    def test_every_test_module_collects_at_least_one(self):
        """Every ``tests/test_*.py`` must yield >=1 test under the default loader. A module that
        collects 0 is almost always the pytest-style-without-TestCase bug this file exists to catch."""
        loader = unittest.TestLoader()
        empty = []
        for name in _iter_test_module_names():
            module = __import__(name)
            if loader.loadTestsFromModule(module).countTestCases() < 1:
                empty.append(name)
        self.assertEqual(
            empty, [],
            f"test module(s) collect 0 tests under `unittest discover` — likely pytest-style "
            f"``test_*`` functions with no unittest.TestCase and no load_tests() hook: {empty}")

    def test_previously_silent_modules_meet_minimum_counts(self):
        """The three restored modules must stay at/above their known counts, so removing a
        load_tests hook (dropping the module to 0) fails loudly rather than silently."""
        loader = unittest.TestLoader()
        for name, minimum in sorted(_MIN_PER_NAMED_MODULE.items()):
            module = __import__(name)
            n = loader.loadTestsFromModule(module).countTestCases()
            self.assertGreaterEqual(
                n, minimum,
                f"{name} collects {n} tests, expected >= {minimum}: the load_tests() hook that "
                f"exposes its pytest-style functions to `make test` may have been removed or broken.")

    def test_full_suite_meets_floor(self):
        """The whole discovered suite must not fall below the floor — a backstop against any
        single module silently dropping out of collection."""
        total = unittest.TestLoader().discover(str(_TESTS_DIR), pattern="test_*.py").countTestCases()
        self.assertGreaterEqual(
            total, _MIN_TOTAL,
            f"`unittest discover` collected {total} tests, below the floor {_MIN_TOTAL}; a whole "
            f"module may have silently dropped out of collection.")


if __name__ == "__main__":
    unittest.main()
