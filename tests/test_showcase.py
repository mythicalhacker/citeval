"""Tests for the offline showcase gallery (`docs/build_showcase.py`).

Proves the page builds from the CACHED cal30 results with NO network (any HTTP call raises) and
NO API key, that the four story cases carry the expected per-axis verdicts, and that the rendered
HTML is a self-contained document. Runs under pytest or standalone
(`python tests/test_showcase.py`).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests/ — for the cache-seed helper

# Import the docs builder by path (it is not an installed module).
_spec = importlib.util.spec_from_file_location("build_showcase", _ROOT / "docs" / "build_showcase.py")
build_showcase = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_showcase)

import citeval.grounding as grounding  # noqa: E402
from _ncbi_cache_fixture import seed_ncbi_cache  # noqa: E402

# build_cards() drives the real grounding path for the four showcase papers. Warm its cache from
# committed fixtures so the build is hermetic with no network and no warm dev cache (e.g. a fresh
# CI checkout, where src/citeval/.cache/ is gitignored and absent). The tests that assert offline
# behaviour make any network call raise; this seeding is pure local file I/O, no network.
seed_ncbi_cache()


def _axis(verdict, axis):
    return next(f for f in verdict.axis_findings if f.axis == axis)


def _no_network():
    """Context: make ANY network fetch raise, so a build that succeeds is provably offline."""
    orig = grounding._get

    def boom(*a, **k):
        raise AssertionError(f"network access attempted: {str(a)[:80]}")

    grounding._get = boom
    return orig


def _restore(orig):
    grounding._get = orig


# --------------------------------------------------------------------------- offline build
def test_cards_build_offline_no_network():
    orig = _no_network()
    try:
        cards = build_showcase.build_cards()
    finally:
        _restore(orig)
    assert [c["case_id"] for c in cards] == ["A25", "A02", "Bs05", "Ch13"]


def test_each_card_has_required_pieces():
    cards = {c["case_id"]: c for c in build_showcase.build_cards()}
    for cid, c in cards.items():
        assert c["claim"].strip(), f"{cid}: empty claim"
        assert c["cited"]["title"].strip() and c["cited"]["pmid"], f"{cid}: missing cited paper"
        axes = {f.axis for f in c["verdict"].axis_findings}
        assert axes == {"retraction", "species_scope", "population_scope", "substantive_support"}, cid
        assert c["decisive"]["span"].strip(), f"{cid}: missing decisive span"
        # substantive axis carries a confidence tier + model-inferred provenance
        sub = _axis(c["verdict"], "substantive_support")
        assert sub.tier in ("high", "medium", "low") and sub.provenance == "model-inferred", cid


def test_story_verdicts_are_correct():
    """The four cases must land on the verdicts the narrative promises."""
    cards = {c["case_id"]: c for c in build_showcase.build_cards()}

    # A25 — over-reach: substantive unsupported (also retracted)
    v = cards["A25"]["verdict"]
    assert _axis(v, "substantive_support").verdict == "unsupported-for-the-claim"
    assert _axis(v, "retraction").verdict == "RELIES_ON_RETRACTED"

    # A02 — retraction caught, substance actually fine
    v = cards["A02"]["verdict"]
    assert _axis(v, "retraction").verdict == "RELIES_ON_RETRACTED"
    assert _axis(v, "substantive_support").verdict == "fully-supported"
    assert "NOT SUPPORTED AS STATED" in v.overall and "RETRACTED" in v.overall

    # Bs05 — species mismatch, substance held constant (still fully-supported)
    v = cards["Bs05"]["verdict"]
    assert _axis(v, "species_scope").verdict == "SCOPE_MISMATCH"
    assert _axis(v, "substantive_support").verdict == "fully-supported"
    assert "SPECIES SCOPE MISMATCH" in v.overall

    # Ch13 — clean graded support at high confidence
    v = cards["Ch13"]["verdict"]
    assert _axis(v, "retraction").verdict == "NOT_RETRACTED"
    assert _axis(v, "species_scope").verdict == "SCOPE_CONSISTENT"
    sub = _axis(v, "substantive_support")
    assert sub.verdict == "fully-supported" and sub.tier == "high"


def test_html_is_selfcontained_and_offline():
    orig = _no_network()
    try:
        html = build_showcase.build_showcase_html()
    finally:
        _restore(orig)
    assert html.startswith("<!doctype html>") and "</html>" in html and "<style>" in html
    # self-contained: no external assets fetched
    assert "http://" not in html and "https://" not in html and "src=" not in html
    # all four cases present
    for cid in ("A25", "A02", "Bs05", "Ch13"):
        assert cid in html, cid
    # the provenance story is legible: both grounded and model-inferred axes are labelled
    for needle in ("metadata-grounded", "model-inferred", "RELIES_ON_RETRACTED",
                   "SCOPE_MISMATCH", "SCOPE_CONSISTENT", "unsupported-for-the-claim",
                   "fully-supported", "Key evidence span"):
        assert needle in html, needle


def test_substantive_basis_is_system_sourced_not_reference():
    """The model-inferred substantive row's Basis must be the SYSTEM's own agreement rationale, not
    the independent reference grader's text (which is attributed separately). Guards the
    provenance-misattribution fix — e.g. A25's reference rationale 'Abstract only, so confidence is
    low' must never appear under the model-inferred badge beside a 'high' tier."""
    cards = {c["case_id"]: c for c in build_showcase.build_cards()}
    sub = _axis(cards["A25"]["verdict"], "substantive_support")
    assert "self-consistency agreement" in sub.detail, "substantive Basis is not system-sourced"
    assert "confidence is low" not in sub.detail, "reference-grader text leaked into model Basis"
    # and it is nowhere on the rendered page (no visible high-vs-low contradiction)
    html = build_showcase.build_showcase_html()
    assert "confidence is low" not in html
    # the reference span is present but explicitly attributed to the reference, not the system
    assert "independent reference grading" in html


def test_html_escapes_dynamic_content():
    """Corpus-derived text is escaped by C5, and unicode round-trips."""
    html = build_showcase.build_showcase_html()
    assert "<script" not in html.lower()          # no injected/authored script tags at all
    assert "α" in html                            # α-synuclein (Ch13 claim) round-trips as unicode
    # a card built from a claim containing a literal '<' would escape it — inject one and confirm
    card = build_showcase.build_cards()[0]
    card["claim"] = "effect of A <b>and</b> B on outcome"
    page = build_showcase.reporting.render_showcase_page([card])
    assert "<b>and</b>" not in page and "&lt;b&gt;and&lt;/b&gt;" in page


# --------------------------------------------------------------------------- unittest discovery
def load_tests(loader, standard_tests, pattern):
    """`unittest discover` hook. This module is pytest-style (plain ``test_*`` functions, no
    ``unittest.TestCase``), so ``discover`` would otherwise collect **0** here even though every
    test passes. Wrap each module-level ``test_*`` callable in a ``FunctionTestCase`` so it runs
    under ``make test``. The standalone ``_run_all`` runner and pytest collection are unaffected."""
    import unittest
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            standard_tests.addTest(unittest.FunctionTestCase(fn))
    return standard_tests


# --------------------------------------------------------------------------- standalone runner
def _run_all() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
