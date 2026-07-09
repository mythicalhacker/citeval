"""Thin vertical slice runner — wires C1 -> C2 -> C3-lite -> C4-stub -> C5.

Usage:
    python -m citeval.slice_runner --pmid 22088800 --claim "..."
    python -m citeval.slice_runner --case B01
    python -m citeval.slice_runner --demo          # A01,B01,C01 + built-in verification
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adjudicator_stub import adjudicate_stub
from .claim_scope import parse_claim_scope
from .contracts import CitedIdentifier, ClaimUnit
from .grounding import ground
from .reporting import render_json, render_markdown

WORKSPACE = Path(__file__).resolve().parents[2]
EVAL_PATH = WORKSPACE / "data" / "eval" / "eval_set.json"
DEFAULT_OUT = WORKSPACE / "outputs" / "slice_output"


def run_slice(claim_text: str, cited_pmid: str | None = None,
              cited_doi: str | None = None) -> dict:
    if cited_pmid:
        ident = CitedIdentifier("pmid", str(cited_pmid))
    elif cited_doi:
        ident = CitedIdentifier("doi", cited_doi)
    else:
        raise ValueError("Provide cited_pmid or cited_doi")
    # C1 (core): normalize -> one ClaimUnit
    unit = ClaimUnit(atomic_claim=claim_text, cited_identifier=ident)
    # C2: real grounding
    g = ground(unit.cited_identifier)
    # C3-lite: claim scope hint
    scope = parse_claim_scope(unit.atomic_claim)
    # C4-stub: adjudicate
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
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    out_dir = Path(args.out)

    if args.demo:
        cases = _load_cases()
        print(f"{'case':5} {'gt':14} {'orgs(H?)':9} {'overall':46} verify")
        print("-" * 104)
        all_ok = True
        for cid in ["A01", "B01", "C01"]:
            c = cases[cid]
            r = run_slice(c["claim_text"], cited_pmid=c["cited_pmid"])
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
    r = run_slice(claim, cited_pmid=pmid, cited_doi=args.doi)
    path = _write(out_dir, (args.case or pmid), r)
    print(r["report_md"])
    print(f"\n[written to {path}]")


if __name__ == "__main__":
    main()
