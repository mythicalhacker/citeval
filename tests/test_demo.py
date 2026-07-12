"""Tests for the bring-your-own-paper CLI (`citeval.demo`).

Exercises the rendering seam on a MOCK graded verdict — no API key, no network — plus the
graded-vs-stub mode resolution and the HTML writer. Runs under pytest or standalone
(`python tests/test_demo.py`).
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from citeval.contracts import (  # noqa: E402
    AxisFinding, CitedIdentifier, ClaimUnit, GroundedRecord, MeshTag, RetractionInfo,
    RetractionWatchHit, ScopeFrame, Verdict,
)
from citeval import demo  # noqa: E402

# --------------------------------------------------------------------------- fixtures
CLAIM = ("Resveratrol has shown promising clinical benefits as an anti-aging and "
         "anti-inflammatory agent in patients.")
PMID = "17086191"
_SUP_SPAN = "resveratrol reduced markers of inflammation in treated mice"
_REF_SPAN = "these effects were observed in a murine model"
_REF_OBJ = "the magnitude and clinical certainty asserted outrun a single mouse study"


def _claim_unit() -> ClaimUnit:
    return ClaimUnit(atomic_claim=CLAIM, cited_identifier=CitedIdentifier("pmid", PMID))


def _grounded() -> GroundedRecord:
    return GroundedRecord(
        identifier=CitedIdentifier("pmid", PMID),
        title="Resveratrol improves health and survival of mice on a high-calorie diet.",
        abstract="A mouse study of resveratrol.",
        mesh_all=["Animals", "Mice"],
        organism_tags=[MeshTag("Animals", "D000818", ["B01"]),
                       MeshTag("Mice", "D051379", ["B01.050"])],
        population_tags=[], sex_tags=[],
        publication_types=["Journal Article"],
        retraction=RetractionInfo(status="NONE_FOUND",
                                  retraction_watch=RetractionWatchHit(present=False),
                                  source_agreement="none"),
        has_humans=False, provenance={"source": "efetch"}, grounding_errors=[],
    )


def _scope() -> ScopeFrame:
    return ScopeFrame(organism="Humans", organism_evidence=["patients", "clinical"],
                      population=None, effect="anti-inflammatory benefit",
                      dose_stated=False, provenance="text-grounded", tier="medium")


def _graded_verdict() -> Verdict:
    findings = [
        AxisFinding("retraction", "NOT_RETRACTED", "high", "metadata-grounded",
                    "No retraction found.", {"source_agreement": "none"}),
        AxisFinding("species_scope", "SCOPE_MISMATCH", "medium",
                    "metadata-grounded (cited) + text-grounded (claim)",
                    "Claim asserts human relevance, cited paper is animal-only.", {}),
        AxisFinding("population_scope", "NOT_ASSESSED", "low", "model-inferred", "n/a", {}),
        AxisFinding("substantive_support", "supported-with-overreach", "high", "model-inferred",
                    "reports an anti-inflammatory effect but only in mice.",
                    {"confidence": {"verbalized": "high", "agreement": 0.86, "n_samples": 5},
                     "calibration": {"note": ""},
                     "supporter": {"span": _SUP_SPAN, "point": "does report an anti-inflammatory effect"},
                     "refuter": {"span": _REF_SPAN, "objection": _REF_OBJ},
                     "abstained": False}),
    ]
    return Verdict(claim=CLAIM, cited_identifier=CitedIdentifier("pmid", PMID),
                   overall="CLAIM NOT SUPPORTED (species scope mismatch)",
                   axis_findings=findings, stub=False)


def _result() -> dict:
    return demo.build_result(_claim_unit(), _grounded(), _scope(), _graded_verdict())


# --------------------------------------------------------------------------- mode resolution
def test_mode_auto_uses_key_presence():
    assert demo.resolve_mode(has_key=True)[0] is True
    assert demo.resolve_mode(has_key=False)[0] is False


def test_mode_stub_forces_objective_even_with_key():
    graded, banner = demo.resolve_mode(stub_flag=True, has_key=True)
    assert graded is False
    assert "OBJECTIVE-ONLY" in banner


def test_mode_graded_forces_full_and_warns_without_key():
    graded, banner = demo.resolve_mode(graded_flag=True, has_key=False)
    assert graded is True
    assert "ANTHROPIC_API_KEY is not set" in banner


def test_mode_full_banner_with_key():
    graded, banner = demo.resolve_mode(graded_flag=True, has_key=True)
    assert graded is True
    assert "FULL" in banner and "ANTHROPIC_API_KEY is not set" not in banner


# --------------------------------------------------------------------------- rendering seam
def test_terminal_renders_complete_report_on_mock_verdict():
    """The core acceptance: the terminal render carries retraction, species scope, the graded
    substantive axis with its confidence tier + provenance, and the supporter/refuter quotes."""
    out = demo.render_terminal(_result(), banner="Mode: FULL — test")
    for needle in (
        CLAIM, "PMID 17086191", "Mode: FULL — test",
        "NOT_RETRACTED", "SCOPE_MISMATCH",                       # objective axes
        "supported-with-overreach",                             # graded grade
        "self-consistency agreement 0.86 across 5 samples",     # confidence tier detail
        "model-inferred",                                       # graded provenance
        f"> {_SUP_SPAN}", f"> {_REF_SPAN}",                     # supporting/refuting quotes
    ):
        assert needle in out, f"missing from terminal render: {needle!r}"


def test_terminal_summary_lists_every_axis():
    out = demo.render_terminal(_result())
    assert "SUMMARY" in out
    for axis in ("retraction", "species_scope", "population_scope", "substantive_support"):
        assert axis in out


def test_build_result_carries_md_html_json():
    r = _result()
    assert set(r) >= {"unit", "grounded", "scope", "verdict", "report_md", "report_html", "report_json"}
    assert r["report_html"].startswith("<!doctype html>")
    assert "supported-with-overreach" in r["report_md"]


def test_write_html_is_selfcontained():
    with tempfile.TemporaryDirectory() as d:
        p = demo.write_html(_result(), Path(d) / "sub" / "report.html")   # nested dir auto-created
        assert p.exists()
        html = p.read_text()
        assert html.startswith("<!doctype html>") and "</html>" in html
        assert "http://" not in html and "https://" not in html and "src=" not in html
        assert _SUP_SPAN in html


def test_run_wraps_pipeline_output():
    """`run` wraps whatever the pipeline returns into the render bundle — patched so it never
    touches the network or a key."""
    unit, g, sc, v = _claim_unit(), _grounded(), _scope(), _graded_verdict()

    def fake_run_slice(claim_text, cited_pmid=None, cited_doi=None, *, graded=False,
                       client=None, config=None):
        assert claim_text == CLAIM and cited_pmid == PMID
        return {"unit": unit, "grounded": g, "scope": sc, "verdict": v}

    orig = demo.run_slice
    demo.run_slice = fake_run_slice
    try:
        r = demo.run(CLAIM, pmid=PMID, graded=True)
    finally:
        demo.run_slice = orig
    assert r["verdict"] is v
    assert "supported-with-overreach" in r["report_md"]


# --------------------------------------------------------------------------- main() entry point
_CACHED_CLAIM = ("increased mitochondrial oxidative stress in human nigral DA neurons triggers a "
                 "dopamine-dependent toxic cascade leading to lysosomal dysfunction")
_CACHED_PMID = "28882997"   # cached in src/citeval/.cache — objective-only run is fully offline


def _no_network():
    """Make any NCBI fetch raise, so a passing end-to-end run is provably offline."""
    import citeval.grounding as grounding
    orig = grounding._get
    grounding._get = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError(f"network access attempted: {str(a)[:80]}"))
    return grounding, orig


def test_main_end_to_end_prints_full_report_offline():
    """The DONE deliverable: `--claim ... --pmid ...` prints a full report. --stub keeps it
    objective-only so it needs no key; network is disabled to prove it runs from cache."""
    grounding, orig = _no_network()
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = demo.main(["--claim", _CACHED_CLAIM, "--pmid", _CACHED_PMID, "--stub"])
    finally:
        grounding._get = orig
    out = buf.getvalue()
    assert rc == 0
    assert "Citation verification report" in out          # the full C5 report rendered
    assert "NOT_RETRACTED" in out and "species_scope" in out
    assert "OBJECTIVE-ONLY" in out                         # honest mode banner
    assert "SUMMARY" in out


def test_main_writes_html_offline():
    grounding, orig = _no_network()
    try:
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "report.html"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = demo.main(["--claim", _CACHED_CLAIM, "--pmid", _CACHED_PMID, "--stub",
                                "--html", str(target)])
            assert rc == 0 and target.exists()
            assert target.read_text().startswith("<!doctype html>")
            assert "HTML report written" in buf.getvalue()
    finally:
        grounding._get = orig


def test_main_pipeline_error_returns_1():
    """A pipeline failure surfaces as a clean exit code 1 + stderr message, not a traceback."""
    orig = demo.run
    demo.run = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            rc = demo.main(["--claim", "x", "--pmid", "999", "--stub"])
    finally:
        demo.run = orig
    assert rc == 1 and "error:" in err.getvalue()


def test_main_html_write_failure_returns_1():
    """A bad --html target (parent is a file) is caught: exit 1, not an uncaught OSError."""
    grounding, orig = _no_network()
    try:
        with tempfile.TemporaryDirectory() as d:
            blocker = Path(d) / "afile"
            blocker.write_text("x")                    # a regular file …
            bad = blocker / "report.html"              # … used as a directory → write fails
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                rc = demo.main(["--claim", _CACHED_CLAIM, "--pmid", _CACHED_PMID, "--stub",
                                "--html", str(bad)])
            assert rc == 1 and "could not write HTML" in err.getvalue()
    finally:
        grounding._get = orig


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
