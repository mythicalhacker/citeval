"""Bring-your-own-paper CLI — the usable front door to the pipeline.

    python -m citeval.demo --claim "<text>" --pmid 28882997
    python -m citeval.demo --claim "<text>" --doi 10.1126/science.aam9080
    python -m citeval.demo --claim "<text>" --pmid 28882997 --html report.html

Runs the full C1→C5 pipeline on a single claim + the paper cited to support it and renders the
COMPLETE C5 report to the terminal: the retraction verdict, species/population scope, the graded
substantive-support axis with its confidence tier + provenance label, and the supporting/refuting
evidence quotes. `--html <path>` also writes the self-contained HTML report.

Mode is chosen automatically:
  * **FULL** — when `ANTHROPIC_API_KEY` is set (or `--graded` is passed): the graded adversarial
    supporter/refuter/critic adjudicator (Opus 4.8) fills the substantive-support axis.
  * **OBJECTIVE-ONLY** — with no key (or `--stub`): retraction + scope are computed for real from
    structured metadata; the graded substantive axis is honestly deferred, never faked.

This module is a thin, testable wrapper around `slice_runner.run_slice` + the C5 renderers. The
rendering seam (`build_result` / `render_terminal` / `write_html`) is exercised in tests on a mock
verdict with no key and no network.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from .contracts import ClaimUnit, GroundedRecord, ScopeFrame, Verdict
from .reporting import render_html, render_json, render_markdown
from .slice_runner import run_slice

_BANNER_FULL = (
    "Mode: FULL — graded adversarial adjudication (Opus 4.8). All four axes are live: the "
    "substantive-support grade comes from a supporter/refuter/critic panel with a self-consistency "
    "confidence."
)
_BANNER_OBJECTIVE = (
    "Mode: OBJECTIVE-ONLY — no ANTHROPIC_API_KEY. Retraction + species/population scope are computed "
    "for real from structured records; the graded substantive-support axis is deferred (not faked). "
    "Set ANTHROPIC_API_KEY or pass --graded to enable it."
)


def resolve_mode(*, graded_flag: bool = False, stub_flag: bool = False,
                 has_key: Optional[bool] = None) -> tuple[bool, str]:
    """Decide graded-vs-stub and the banner to print.

    `--stub` wins (force objective-only); `--graded` forces the graded path; otherwise auto: graded
    when an ANTHROPIC_API_KEY is present, else objective-only so the tool still runs with no key."""
    if has_key is None:
        has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if stub_flag:
        graded = False
    elif graded_flag:
        graded = True
    else:
        graded = has_key
    if graded and not has_key:
        banner = (_BANNER_FULL + "\n(!) --graded was requested but ANTHROPIC_API_KEY is not set; "
                  "the model calls will fail without it.")
    else:
        banner = _BANNER_FULL if graded else _BANNER_OBJECTIVE
    return graded, banner


def build_result(unit: ClaimUnit, g: GroundedRecord, scope: ScopeFrame, v: Verdict) -> dict:
    """Assemble the render bundle from an already-computed pipeline output. Pure rendering (C5),
    so tests drive it directly with a mock verdict — no key, no network."""
    return {
        "unit": unit, "grounded": g, "scope": scope, "verdict": v,
        "report_md": render_markdown(unit, g, scope, v),
        "report_html": render_html(unit, g, scope, v),
        "report_json": render_json(unit, g, scope, v),
    }


def run(claim: str, *, pmid: Optional[str] = None, doi: Optional[str] = None,
        graded: bool = False, client=None, config=None) -> dict:
    """Run the full pipeline on one claim + cited paper and return the render bundle."""
    r = run_slice(claim, cited_pmid=pmid, cited_doi=doi, graded=graded, client=client, config=config)
    return build_result(r["unit"], r["grounded"], r["scope"], r["verdict"])


def _footer(v: Verdict) -> str:
    """A compact one-look summary printed under the full report."""
    lines = ["", "─" * 72, f"SUMMARY  ·  {v.overall}"]
    for f in v.axis_findings:
        lines.append(f"  {f.axis:20} {f.verdict:28} [{f.tier} · {f.provenance}]")
    return "\n".join(lines)


def render_terminal(result: dict, *, banner: str = "") -> str:
    """The full terminal render: mode banner, the complete C5 markdown report, then the summary."""
    v: Verdict = result["verdict"]
    ci = v.cited_identifier
    head = ["=" * 72, "citeval — citation verification report",
            f"claim : {v.claim}", f"cited : {ci.type.upper()} {ci.value}"]
    if banner:
        head += ["", banner]
    head.append("=" * 72)
    return "\n".join(head) + "\n\n" + result["report_md"] + _footer(v) + "\n"


def write_html(result: dict, path: str | os.PathLike) -> Path:
    p = Path(path)
    if p.parent and not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(result["report_html"])
    return p


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m citeval.demo",
        description="Check whether the cited paper actually supports a scientific claim.")
    ap.add_argument("--claim", required=True, help="the claim sentence to check (verbatim)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pmid", help="PMID of the cited paper")
    g.add_argument("--doi", help="DOI of the cited paper")
    ap.add_argument("--html", help="also write the self-contained HTML report to this path")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--graded", action="store_true",
                      help="force the graded adversarial adjudicator (needs ANTHROPIC_API_KEY)")
    mode.add_argument("--stub", action="store_true",
                      help="force objective-only (skip the graded substantive axis)")
    args = ap.parse_args(argv)

    graded, banner = resolve_mode(graded_flag=args.graded, stub_flag=args.stub)
    try:
        result = run(args.claim, pmid=args.pmid, doi=args.doi, graded=graded)
    except Exception as exc:  # noqa: BLE001 — surface a clean CLI error, not a traceback
        print(f"error: {exc}", file=sys.stderr)
        if graded and not os.environ.get("ANTHROPIC_API_KEY"):
            print("hint: the graded path needs ANTHROPIC_API_KEY; drop --graded to run "
                  "objective-only.", file=sys.stderr)
        return 1

    print(render_terminal(result, banner=banner))
    if args.html:
        try:
            path = write_html(result, args.html)
        except OSError as exc:  # bad path / unwritable target — clean error, not a traceback
            print(f"error: could not write HTML to {args.html!r}: {exc}", file=sys.stderr)
            return 1
        print(f"[HTML report written to {path}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
