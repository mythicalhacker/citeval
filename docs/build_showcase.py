"""Build `docs/showcase.html` — an offline, no-key gallery of four worked cases.

Every card is reconstructed from the CACHED 30-case calibration corpus (`corpus/calibration/`):
the objective axes (retraction, species/population scope) are recomputed offline by the real
C2/C4 metadata logic against the disk-cached NCBI EFetch XML + Retraction Watch index; the
graded substantive-support axis is read from the cached graded run (`graded_predictions_cal30.jsonl`)
with its decisive verbatim span from the full-text reference (`graded_reference.jsonl`). No API key
and no network are required to build or render this page (grounding reads only the disk cache); the
showcase test proves this by making any network call raise.

Run (from anywhere):
    python docs/build_showcase.py            # writes docs/showcase.html
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from citeval.adjudicator import (  # noqa: E402
    CONFIDENCE_HIGH_AGREEMENT, CONFIDENCE_MEDIUM_AGREEMENT, default_rollup,
)
from citeval.claim_scope import parse_claim_scope_lexical  # noqa: E402
from citeval.contracts import AxisFinding, CitedIdentifier, Verdict  # noqa: E402
from citeval.grounding import ground  # noqa: E402
from citeval.objective_axes import population_axis, retraction_axis, species_axis  # noqa: E402
from citeval import reporting  # noqa: E402

_CAL = _ROOT / "corpus" / "calibration"
_OUT = _ROOT / "docs" / "showcase.html"

# The four cases + their narrative. Order tells the story: over-reach → retraction → scope → clean.
# `axis_focus` is the axis each card is the hero of; the card still shows all four axes.
_CASES = [
    {
        "case_id": "A25", "axis_focus": "substantive_support",
        "story_title": "A finding — and an author — the cited paper never contained",
        "story_caption": (
            "The sentence credits “Chen Guanghui” with showing Mfn2 inhibits VSMC proliferation "
            "independent of mitochondrial fusion. The cited paper is about miR-214 and fibroblast "
            "differentiation in rats — it contains neither that finding nor that author. Graded "
            "unsupported-for-the-claim at high self-consistency (and the paper is also retracted)."),
    },
    {
        "case_id": "A02", "axis_focus": "retraction",
        "story_title": "The science checks out — but the paper was retracted",
        "story_caption": (
            "The GAS5 / miR-21 / SOX5 sorafenib-sensitivity claim is substantively supported by the "
            "cited paper's own results (graded fully-supported). But Retraction Watch records the "
            "paper as retracted for data/image duplication and paper-mill concerns — so the citation "
            "cannot stand. Metadata overrides the model: overall NOT SUPPORTED."),
    },
    {
        "case_id": "Bs05", "axis_focus": "species_scope",
        "story_title": "Right substance, wrong species",
        "story_caption": (
            "The paper fully supports that bacteriophages modulate the gut microbiota and the host — "
            "substance held constant, graded fully-supported. But it is a mouse study (MeSH: Animals, "
            "Mice; no “Humans”), while the claim asserts relevance to human health. That species-scope "
            "mismatch is carried on its own axis, so it never silently depresses the substantive grade."),
    },
    {
        "case_id": "Ch13", "axis_focus": "substantive_support",
        "story_title": "A clean, high-confidence match",
        "story_caption": (
            "A human iPSC-derived nigral-neuron study; the claim's mechanistic cascade matches the "
            "paper's own discussion nearly verbatim. Not retracted, species-consistent (human claim, "
            "human study), graded fully-supported at high confidence."),
    },
]


def _load_jsonl(name: str) -> dict:
    path = _CAL / name
    return {json.loads(line)["case_id"]: json.loads(line)
            for line in path.read_text().splitlines() if line.strip()}


def _tier_from_agreement(a_exact: float) -> str:
    """The C4 confidence tier from self-consistency agreement (reuses the adjudicator seeds)."""
    if a_exact >= CONFIDENCE_HIGH_AGREEMENT:
        return "high"
    if a_exact >= CONFIDENCE_MEDIUM_AGREEMENT:
        return "medium"
    return "low"


def _substantive_finding(pred: dict) -> AxisFinding:
    """The graded substantive_support axis, rebuilt purely from the SYSTEM's cached run.

    Everything here — verdict, agreement, tier, sample count, evidence depth, and the `detail`
    (the "Basis" the model-inferred row shows) — comes from `graded_predictions_cal30.jsonl`, the
    system's own output. The independent reference grader's rationale/span is NOT injected here (it
    would masquerade as the model's own reasoning under a model-inferred badge); it is rendered
    separately on the card, explicitly attributed. `verbalized` mirrors the emitted tier exactly as
    the live adjudicator does (`_build_substantive_finding`: `verbalized = tier`), so this row is
    byte-consistent with a real report."""
    grade = pred["grade"]
    a_exact = float(pred["confidence"])
    tier = _tier_from_agreement(a_exact)
    depth = pred.get("evidence_depth", "")
    conf = {"verbalized": tier, "agreement": round(a_exact, 4)}
    rounds = pred.get("output_tokens")
    n = len(rounds) if isinstance(rounds, list) and rounds else None
    if n is not None:
        conf["n_samples"] = n
    detail = (f"Adversarial supporter/refuter/critic panel graded “{grade}” with exact "
              f"self-consistency agreement {a_exact:.2f}"
              + (f" over {n} sampled rounds" if n is not None else " across the sampled rounds")
              + (f"; evidence depth: {depth}." if depth else "."))
    return AxisFinding(
        axis="substantive_support", verdict=grade, tier=tier, provenance="model-inferred",
        detail=detail,
        evidence={"confidence": conf, "calibration": {"note": ""}, "abstained": False},
    )


def _card(case: dict, corpus: dict, preds: dict, refs: dict) -> dict:
    """Assemble one render-ready card from the cached corpus, offline grounding, and the cached
    graded run. No network (grounding hits only the disk cache) and no API key."""
    cid = case["case_id"]
    c, pred, ref = corpus[cid], preds[cid], refs[cid]

    # C2 grounding (offline: disk-cached EFetch XML + RW index) → real objective axes.
    g = ground(CitedIdentifier("pmid", str(c["cited_pmid"])), with_full_text=False)
    scope = parse_claim_scope_lexical(c["claim_text"])
    findings = [
        retraction_axis(g), species_axis(g, scope), population_axis(g, scope),
        _substantive_finding(pred),
    ]
    verdict = Verdict(
        claim=c["claim_text"], cited_identifier=g.identifier,
        overall=default_rollup(findings), axis_findings=findings, stub=False,
    )

    # The decisive span + grade come from the INDEPENDENT full-text reference grading (the answer
    # key — grade_provenance "llm-fulltext-claude-science"), NOT the system. Label them as such, and
    # be honest about the depth the reference had (abstract vs full text) rather than claiming a
    # verbatim check this offline builder never performs.
    depth = pred.get("evidence_depth", "")
    depth_phrase = {"abstract": "from the abstract", "fulltext": "from full text"}.get(depth, "")
    ref_kind = "independent reference grading (Claude Science)"
    matches = pred["grade"] == ref.get("substantive_grade")
    if matches:
        note = f"Cross-check: the system's grade agrees with the {ref_kind} {depth_phrase}.".strip()
    else:
        note = (f"Cross-check: system grade “{pred['grade']}” vs {ref_kind} "
                f"“{ref.get('substantive_grade', '')}” {depth_phrase}.").strip()

    citing = c.get("claim_source_pmcid") or c.get("claim_source_pmid")
    return {
        "case_id": cid,
        "axis_focus": case["axis_focus"],
        "story_title": case["story_title"],
        "story_caption": case["story_caption"],
        "claim": c["claim_text"],
        "citing_source": str(citing) if citing else "",
        "cited": {"title": c["cited_title"], "journal": c.get("cited_journal", ""),
                  "pmid": str(c["cited_pmid"]), "doi": c.get("cited_doi", "")},
        "verdict": verdict,
        "decisive": {"span": ref.get("decisive_span", ""),
                     "source": f"quoted by the {ref_kind}"
                               + (f", {depth_phrase}" if depth_phrase else "")},
        "reference": {"grade": ref.get("substantive_grade", ""), "note": note},
    }


def build_cards() -> list[dict]:
    """The four render-ready showcase cards, reconstructed offline from cached cal30 results."""
    corpus, preds, refs = (_load_jsonl("corpus_cal30.jsonl"),
                           _load_jsonl("graded_predictions_cal30.jsonl"),
                           _load_jsonl("graded_reference.jsonl"))
    return [_card(case, corpus, preds, refs) for case in _CASES]


def build_showcase_html() -> str:
    return reporting.render_showcase_page(build_cards())


def main() -> int:
    html = build_showcase_html()
    _OUT.write_text(html)
    print(f"[showcase written to {_OUT}  ·  {len(html):,} bytes  ·  "
          f"{len(_CASES)} cases, offline/no-key]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
