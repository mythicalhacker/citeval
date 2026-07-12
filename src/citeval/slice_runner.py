"""Thin vertical slice runner — wires C1 -> C2 -> C3 -> C4 -> C5.

Usage:
    python -m citeval.slice_runner --pmid 22088800 --claim "..."
    python -m citeval.slice_runner --case B01
    python -m citeval.slice_runner --demo          # A01,B01,C01 + built-in verification
    python -m citeval.slice_runner --demo --graded # graded adversarial C4 (needs ANTHROPIC_API_KEY)

C4 runs as the offline **stub** by default. The graded adversarial adjudicator is swapped in
behind a flag (`--graded` or `CITEVAL_GRADED=1`); it is the only place the two adjudicators
differ, and the graded path requires a live Opus 4.8 key. Default OFF keeps the slice/scorer
offline-green with no key.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .adjudicator import AdjudicationConfig, adjudicate
from .adjudicator_stub import adjudicate_stub
from .claim_scope import parse_claim_scope
from .contracts import CitedIdentifier, ClaimUnit
from .grounding import ground
from .reporting import render_json, render_markdown

WORKSPACE = Path(__file__).resolve().parents[2]
EVAL_PATH = WORKSPACE / "data" / "eval" / "eval_set.json"
DEFAULT_OUT = WORKSPACE / "outputs" / "slice_output"


_FALSEY = ("", "0", "false", "no", "off", "none")


def graded_enabled(flag: bool = False) -> bool:
    """Graded C4 is on when `--graded` is passed OR `CITEVAL_GRADED` is set truthy.

    Fails CLOSED (case-insensitively): unset or any common off-spelling
    (0/false/no/off/none) stays on the offline stub path. The graded path constructs a live
    Opus 4.8 client, so an intent-to-disable value must not silently enable it."""
    return bool(flag) or os.environ.get("CITEVAL_GRADED", "").strip().lower() not in _FALSEY


def recalibrate_enabled(flag: bool = False) -> bool:
    """Post-hoc RB3 recalibration is on when `--recalibrate` is passed OR `CITEVAL_RECALIBRATE` is set
    truthy. Fails CLOSED (same off-spellings as `graded_enabled`): recalibration is opt-in and never
    auto-enabled — and even when ON it still declines a missing/unfit map (see
    `recalibrate.resolve_recalibration`)."""
    return bool(flag) or os.environ.get("CITEVAL_RECALIBRATE", "").strip().lower() not in _FALSEY


def run_slice(claim_text: str, cited_pmid: str | None = None,
              cited_doi: str | None = None, *, graded: bool = False,
              client=None, config=None) -> dict:
    if cited_pmid:
        ident = CitedIdentifier("pmid", str(cited_pmid))
    elif cited_doi:
        ident = CitedIdentifier("doi", cited_doi)
    else:
        raise ValueError("Provide cited_pmid or cited_doi")
    # C1 (core): normalize -> one ClaimUnit
    unit = ClaimUnit(atomic_claim=claim_text, cited_identifier=ident)
    # C2: real grounding. Full text is only consumed by the graded adjudicator, so the offline
    # stub path skips the extra PMC round-trip entirely (keeps the no-key gate network-identical).
    g = ground(unit.cited_identifier, with_full_text=graded)
    # C3: claim scope hint (populates direction on both paths)
    scope = parse_claim_scope(unit.atomic_claim)
    # C4: adjudicate — graded adversarial pipeline behind a flag, else the offline stub.
    if graded:
        v = adjudicate(g, scope, claim_text=claim_text, client=client, config=config)
    else:
        v = adjudicate_stub(g, scope, claim_text=claim_text)
    # C5: report
    return {"unit": unit, "grounded": g, "scope": scope, "verdict": v,
            "report_md": render_markdown(unit, g, scope, v),
            "report_json": render_json(unit, g, scope, v)}


def _load_cases() -> dict:
    data = json.loads(EVAL_PATH.read_text())
    return {c["case_id"]: c for c in data["cases"]}


def _write(out_dir: Path, name: str, result: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.md").write_text(result["report_md"])
    (out_dir / f"{name}.json").write_text(json.dumps(result["report_json"], indent=2))
    return out_dir / f"{name}.md"


def _axis(v, axis):
    return next(f for f in v.axis_findings if f.axis == axis)


def _verify(case: dict, v) -> tuple[bool, str]:
    """Check the slice's objective-axis output against the eval ground truth."""
    gt = case["ground_truth_label"]
    ret, sp = _axis(v, "retraction").verdict, _axis(v, "species_scope").verdict
    if gt == "RETRACTED":
        ok = ret == "RELIES_ON_RETRACTED"
        return ok, f"expect retraction=RELIES_ON_RETRACTED -> got {ret}"
    if gt == "SCOPE_MISMATCH":
        ok = sp == "SCOPE_MISMATCH"
        return ok, f"expect species_scope=SCOPE_MISMATCH -> got {sp}"
    if gt == "SUPPORTED":
        ok = ret == "NOT_RETRACTED" and sp != "SCOPE_MISMATCH"
        return ok, f"expect not-retracted & no species mismatch -> got retraction={ret}, species={sp}"
    return False, f"unknown ground truth {gt}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pmid")
    ap.add_argument("--doi")
    ap.add_argument("--claim")
    ap.add_argument("--case", help="eval_set.json case_id (e.g. A01)")
    ap.add_argument("--demo", action="store_true", help="run A01,B01,C01 with verification")
    ap.add_argument("--graded", action="store_true",
                    help="use the graded adversarial C4 (needs ANTHROPIC_API_KEY); else the stub")
    ap.add_argument("--recalibrate", action="store_true",
                    help="apply the fitted RB3 Platt confidence map (opt-in; needs --graded; "
                         "fails closed if no fitted map). Or set CITEVAL_RECALIBRATE=1")
    ap.add_argument("--recalibration-map", dest="recalibration_map",
                    help="path to calibration_map.json (default outputs/calibration_map.json)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    out_dir = Path(args.out)
    graded = graded_enabled(args.graded)

    # RB3 post-hoc recalibration — opt-in, fails closed. Only meaningful on the graded path (the stub
    # ignores config); the resolver declines a missing/unfit map so it is never auto-enabled.
    from .recalibrate import DEFAULT_MAP_PATH, resolve_recalibration
    recal_fn, recal_note = resolve_recalibration(
        graded and recalibrate_enabled(args.recalibrate),
        args.recalibration_map or DEFAULT_MAP_PATH)
    if recal_note:
        print(recal_note)
    recal_config = AdjudicationConfig(recalibration=recal_fn) if recal_fn is not None else None

    if args.demo:
        cases = _load_cases()
        print(f"C4: {'graded (Opus 4.8)' if graded else 'stub (offline)'}")
        print(f"{'case':5} {'gt':14} {'orgs(H?)':9} {'overall':46} verify")
        print("-" * 104)
        all_ok = True
        for cid in ["A01", "B01", "C01"]:
            c = cases[cid]
            r = run_slice(c["claim_text"], cited_pmid=c["cited_pmid"], graded=graded,
                          config=recal_config)
            _write(out_dir, cid, r)
            g = r["grounded"]
            # grounding sanity: all three cases carry organism MeSH; empty means a
            # grounding regression (which would let scope verdicts pass for the wrong reason).
            grounded_ok = bool(g.organism_tags)
            ok, why = _verify(c, r["verdict"])
            if not grounded_ok:
                ok, why = False, "grounding returned EMPTY organism_tags"
            all_ok &= ok
            orgs = f"{len(g.organism_tags)}({'H' if g.has_humans else '-'})"
            print(f"{cid:5} {c['ground_truth_label']:14} {orgs:9} {r['verdict'].overall[:46]:46} "
                  f"{'PASS' if ok else 'FAIL — ' + why}")
        print("-" * 104)
        print(f"Reports written to {out_dir}")
        print("VERIFICATION:", "ALL PASS" if all_ok else "FAILURES PRESENT")
        return

    if args.case:
        c = _load_cases()[args.case]
        claim, pmid = c["claim_text"], c["cited_pmid"]
    else:
        claim, pmid = args.claim, args.pmid
    if not claim or not (pmid or args.doi):
        ap.error("provide --case, or --claim with --pmid/--doi, or --demo")
    r = run_slice(claim, cited_pmid=pmid, cited_doi=args.doi, graded=graded, config=recal_config)
    path = _write(out_dir, (args.case or pmid), r)
    print(r["report_md"])
    print(f"\n[written to {path}]")


if __name__ == "__main__":
    main()
