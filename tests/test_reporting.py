"""Snapshot / regression tests for C5 reporting (extended).

Covers the graded `substantive_support` rendering (RB1 grade + RB3 confidence +
calibration note + quoted supporter/refuter spans), the HTML report, and the
BYO-paper view — plus the invariant that the pre-existing stub path is unchanged.

Runs under pytest *or* standalone (`python tests/test_reporting.py`), so it needs no
test-runner dependency. The package is imported from ../src.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from citeval.contracts import (  # noqa: E402
    AxisFinding, CitedIdentifier, ClaimUnit, GroundedRecord, MeshTag, RetractionInfo,
    RetractionWatchHit, ScopeFrame, Verdict,
)
from citeval import reporting  # noqa: E402

# --------------------------------------------------------------------------- fixtures
CLAIM = ("Resveratrol has shown promising clinical benefits as an anti-aging and "
         "anti-inflammatory agent in patients.")
PMID = "17086191"

_SUPPORTER_SPAN = "resveratrol reduced markers of inflammation in treated mice"
_SUPPORTER_POINT = "the cited paper does report an anti-inflammatory effect"
_REFUTER_SPAN = "these effects were observed in a murine model"
_REFUTER_OBJECTION = "the magnitude and clinical certainty asserted outrun a single mouse study"
_CALIBRATION = "high-confidence verdicts are empirically 91% accurate on the corpus (n=42)."
_RATIONALE = ("The paper reports an anti-inflammatory effect but only in mice; the claim's asserted "
              "clinical benefit overstates certainty and generality.")


def _claim_unit() -> ClaimUnit:
    return ClaimUnit(atomic_claim=CLAIM, cited_identifier=CitedIdentifier("pmid", PMID))


def _grounded(has_humans: bool = False) -> GroundedRecord:
    return GroundedRecord(
        identifier=CitedIdentifier("pmid", PMID),
        title="Resveratrol improves health and survival of mice on a high-calorie diet.",
        abstract="A mouse study of resveratrol.",
        mesh_all=["Animals", "Mice", "Stilbenes"],
        organism_tags=[MeshTag("Animals", "D000818", ["B01"]),
                       MeshTag("Mice", "D051379", ["B01.050.150.900.649.313.988.400.112.400.560"])],
        population_tags=[],
        sex_tags=[MeshTag("Male", "D008297", [])],
        publication_types=["Journal Article"],
        retraction=RetractionInfo(status="NONE_FOUND",
                                  retraction_watch=RetractionWatchHit(present=False),
                                  source_agreement="none"),
        has_humans=has_humans,
        provenance={"source": "efetch"},
        grounding_errors=[],
    )


def _scope() -> ScopeFrame:
    return ScopeFrame(organism="Humans", organism_evidence=["patients", "clinical"],
                      population=None, effect="anti-inflammatory benefit",
                      dose_stated=False, provenance="text-grounded", tier="medium")


def _objective_findings() -> list[AxisFinding]:
    return [
        AxisFinding("retraction", "NOT_RETRACTED", "high", "metadata-grounded",
                    "No retraction found in Retraction Watch or NCBI records.",
                    {"source_agreement": "none"}),
        AxisFinding("species_scope", "SCOPE_MISMATCH", "medium",
                    "metadata-grounded (cited) + text-grounded (claim)",
                    "Claim asserts human/clinical relevance, but cited paper MeSH organism scope is "
                    "['Animals', 'Mice'] with 'Humans' ABSENT. Metadata authoritative.",
                    {"cited_has_humans": False, "claim_organism": "Humans"}),
        AxisFinding("population_scope", "NOT_ASSESSED", "low", "model-inferred",
                    "No explicit population marker in the claim, or no population MeSH on the cited "
                    "paper; population axis not assessed at slice depth.", {}),
    ]


def _graded_finding() -> AxisFinding:
    """A real graded substantive_support axis (RB1 grade + RB3 confidence), per the
    CONTEXT_PACK §6 evidence-dict convention."""
    return AxisFinding(
        axis="substantive_support",
        verdict="supported-with-overreach",
        tier="high",
        provenance="model-inferred",
        detail=_RATIONALE,
        evidence={
            "confidence": {"verbalized": "high", "agreement": 0.86, "n_samples": 5},
            "calibration": {"note": _CALIBRATION},
            "supporter": {"span": _SUPPORTER_SPAN, "point": _SUPPORTER_POINT},
            "refuter": {"span": _REFUTER_SPAN, "objection": _REFUTER_OBJECTION},
            "abstained": False,
        },
    )


def _unverifiable() -> dict:
    return {
        "dose": "No dose asserted in the claim; not applicable.",
        "effect_direction": "Whether the claim's effect direction matches the cited paper's reported "
                            "result requires reading the Results text; no structured field.",
    }


def graded_verdict() -> Verdict:
    return Verdict(
        claim=CLAIM,
        cited_identifier=CitedIdentifier("pmid", PMID),
        overall="CLAIM NOT SUPPORTED (species scope mismatch)",
        axis_findings=_objective_findings() + [_graded_finding()],
        unverifiable_axes=_unverifiable(),
        stub=False,
        notes=["Cited-paper metadata is authoritative on objective axes."],
    )


def stub_verdict() -> Verdict:
    """A thin-slice Verdict — substantive_support not adjudicated (mirrors adjudicator_stub)."""
    sub = AxisFinding("substantive_support", "NOT_ADJUDICATED", "n/a", "stub-not-adjudicated",
                      "Graded claim-support is produced only by the adversarial agent.", {})
    return Verdict(
        claim=CLAIM,
        cited_identifier=CitedIdentifier("pmid", PMID),
        overall="CLAIM NOT SUPPORTED (species scope mismatch)",
        axis_findings=_objective_findings() + [sub],
        unverifiable_axes=_unverifiable(),
        stub=True,
        notes=[],
    )


# The graded markdown block, as a golden snapshot (asserted to appear verbatim).
EXPECTED_GRADED_MD = "\n".join([
    "## Substantive support (graded)",
    "",
    "- **Grade (RB1 scale):** supported-with-overreach",
    "- **Confidence:** high — self-consistency agreement 0.86 across 5 samples; verbalized high",
    f"- **Calibration:** {_CALIBRATION}",
    "- **Provenance:** model-inferred — this axis grades *substance only, holding scope constant* "
    "(CONTEXT_PACK §6); species/population scope over-reach is carried by the scope axes above, "
    "not reflected in this grade.",
    f"- **Rationale:** {_RATIONALE}",
    "",
    "**Adversarial trace.**",
    "",
    "- _Supporter — best supporting span:_",
    f"  > {_SUPPORTER_SPAN}",
    f"  {_SUPPORTER_POINT}",
    "- _Refuter — strongest objection:_",
    f"  > {_REFUTER_SPAN}",
    f"  {_REFUTER_OBJECTION}",
])


# --------------------------------------------------------------------------- tests
def test_graded_markdown_block_snapshot():
    """The graded axis renders grade + confidence + calibration + quoted spans (golden)."""
    md = reporting.render_markdown(_claim_unit(), _grounded(), _scope(), graded_verdict())
    assert EXPECTED_GRADED_MD in md, "graded markdown block did not match the golden snapshot"


def test_graded_markdown_has_all_required_pieces():
    """Acceptance: grade, confidence, quoted supporter/refuter spans, calibration note."""
    md = reporting.render_markdown(_claim_unit(), _grounded(), _scope(), graded_verdict())
    for needle in ("supported-with-overreach", "self-consistency agreement 0.86 across 5 samples",
                   _CALIBRATION, f"> {_SUPPORTER_SPAN}", f"> {_REFUTER_SPAN}"):
        assert needle in md, f"missing from markdown: {needle!r}"


def test_html_and_markdown_carry_the_same_information():
    """Acceptance: HTML and markdown carry the same substantive information."""
    cu, g, sc, v = _claim_unit(), _grounded(), _scope(), graded_verdict()
    md = reporting.render_markdown(cu, g, sc, v)
    ht = reporting.render_html(cu, g, sc, v)
    parity = [
        "supported-with-overreach",
        "self-consistency agreement 0.86 across 5 samples",
        _CALIBRATION, _SUPPORTER_SPAN, _SUPPORTER_POINT, _REFUTER_SPAN, _REFUTER_OBJECTION,
        # objective axes stay metadata-grounded; unverifiable axes still listed
        "metadata-grounded", "SCOPE_MISMATCH", "NOT_RETRACTED", "dose", "effect_direction",
        # scope-held-constant note is present in both
        "holding scope constant",
    ]
    for needle in parity:
        assert needle in md, f"missing from markdown: {needle!r}"
        assert needle in ht, f"missing from HTML: {needle!r}"


def test_objective_axes_render_metadata_grounded():
    md = reporting.render_markdown(_claim_unit(), _grounded(), _scope(), graded_verdict())
    # the retraction/species rows must show their metadata-grounded provenance
    assert "| retraction | **NOT_RETRACTED** | high | metadata-grounded |" in md
    assert "metadata-grounded (cited) + text-grounded (claim)" in md


def test_unverifiable_axes_still_listed():
    cu, g, sc, v = _claim_unit(), _grounded(), _scope(), graded_verdict()
    md = reporting.render_markdown(cu, g, sc, v)
    ht = reporting.render_html(cu, g, sc, v)
    for doc in (md, ht):
        assert "Axes flagged unverifiable" in doc
        assert "dose" in doc and "effect_direction" in doc


def test_html_is_selfcontained_and_escaped():
    """HTML is a standalone document with no external assets, and dynamic content is escaped."""
    cu = _claim_unit()
    g, sc = _grounded(), _scope()
    v = graded_verdict()
    v.claim = "Effect of X <script>alert('xss')</script> & Y on patients"
    ht = reporting.render_html(cu, g, sc, v)
    assert ht.startswith("<!doctype html>")
    assert "</html>" in ht and "<style>" in ht
    assert "http://" not in ht and "https://" not in ht and "src=" not in ht  # no external assets
    assert "<script>alert" not in ht                # not injected raw
    assert "&lt;script&gt;" in ht and "&amp; Y" in ht  # escaped


def test_stub_path_unchanged_no_graded_section():
    """Regression guard: a stub Verdict renders NO graded section and keeps the thin-slice
    legend wording + stub note (the pre-existing behaviour is additive-only)."""
    md = reporting.render_markdown(_claim_unit(), _grounded(), _scope(), stub_verdict())
    assert "## Substantive support (graded)" not in md
    assert "the graded support axis is deferred" in md          # original legend wording
    assert "This is the thin-slice output." in md               # stub note present
    # the substantive row still appears in the per-axis table as not-adjudicated
    assert "| substantive_support | **NOT_ADJUDICATED** | n/a | stub-not-adjudicated |" in md


def test_graded_present_updates_legend_wording():
    md = reporting.render_markdown(_claim_unit(), _grounded(), _scope(), graded_verdict())
    assert "the graded support axis is deferred" not in md
    assert "graded substantive-support axis, produced by the adversarial" in md


def test_abstention_renders_as_abstained_not_wrong():
    v = graded_verdict()
    sub = v.axis_findings[-1]
    sub.verdict = "NOT_ENOUGH_INFO"
    sub.evidence["abstained"] = True
    md = reporting.render_markdown(_claim_unit(), _grounded(), _scope(), v)
    ht = reporting.render_html(_claim_unit(), _grounded(), _scope(), v)
    for doc in (md, ht):
        assert "NOT_ENOUGH_INFO" in doc
        assert "the agent abstained" in doc and "not scored as wrong" in doc


def test_missing_spans_and_calibration_degrade_gracefully():
    """Defensive reading of the evidence dict: absent spans / empty calibration note."""
    v = graded_verdict()
    sub = v.axis_findings[-1]
    sub.evidence = {"confidence": {"verbalized": "low"}, "calibration": {"note": ""}}
    md = reporting.render_markdown(_claim_unit(), _grounded(), _scope(), v)
    assert "(no supporting span found)" in md
    assert "(no objection span found)" in md
    assert "not yet available" in md
    # still shows the grade + tier even with sparse evidence
    assert "supported-with-overreach" in md


def test_byo_markdown_compact_summary_then_table():
    """BYO markdown: compact top summary (claim, cited paper, overall) then the per-axis table."""
    cu, g, sc, v = _claim_unit(), _grounded(), _scope(), graded_verdict()
    md = reporting.render_byo_markdown(cu, g, sc, v)
    assert md.startswith("# Citation check — bring-your-own-paper")
    assert f"**Cited paper.** {g.title} (PMID {PMID})  " in md
    assert "**Overall.** CLAIM NOT SUPPORTED (species scope mismatch)" in md
    assert "| Axis | Verdict | Confidence | Provenance | Basis |" in md
    assert EXPECTED_GRADED_MD in md          # graded block carried into BYO too
    assert "Provenance legend" in md         # legend kept


def test_byo_html_parity_with_byo_markdown():
    cu, g, sc, v = _claim_unit(), _grounded(), _scope(), graded_verdict()
    md = reporting.render_byo_markdown(cu, g, sc, v)
    ht = reporting.render_byo_html(cu, g, sc, v)
    assert ht.startswith("<!doctype html>")
    for needle in ("Citation check", "supported-with-overreach", _CALIBRATION,
                   _SUPPORTER_SPAN, _REFUTER_SPAN, "Provenance legend"):
        assert needle in md, f"missing from BYO markdown: {needle!r}"
        assert needle in ht, f"missing from BYO HTML: {needle!r}"


def test_render_json_unchanged_and_carries_graded_evidence():
    """render_json behaviour is unchanged and already carries the full graded evidence."""
    cu, g, sc, v = _claim_unit(), _grounded(), _scope(), graded_verdict()
    out = reporting.render_json(cu, g, sc, v)
    assert set(out) == {"claim_unit", "grounded", "claim_scope", "verdict"}
    findings = out["verdict"]["axis_findings"]
    sub = next(f for f in findings if f["axis"] == "substantive_support")
    assert sub["verdict"] == "supported-with-overreach"
    assert sub["evidence"]["calibration"]["note"] == _CALIBRATION
    assert sub["evidence"]["supporter"]["span"] == _SUPPORTER_SPAN


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
