#!/usr/bin/env python3
"""Regenerate every citeval innovation artifact under docs/artifacts/.

Offline, deterministic, zero model calls: each builder reads committed calibration
data and bakes a self-contained HTML page. Run from anywhere:

    python docs/build_artifacts/build_all.py

Exits non-zero if any builder raises (e.g. a committed number drifts past one of the
build-time assertions), so this doubles as a lightweight regression check.
"""
from __future__ import annotations

import sys

import build_climbdown
import build_debate_replay
import build_index
import build_spin_spectrum
import build_tiebreak
import _common as C

BUILDERS = [
    ("climbdown.html", build_climbdown.build),
    ("spin_spectrum.html", build_spin_spectrum.build),
    ("tiebreak_console.html", build_tiebreak.build),
    ("debate_replay.html", build_debate_replay.build),
    ("index.html", build_index.build),
]


def main() -> int:
    print(f"repo root : {C.REPO_ROOT}")
    print(f"reading   : {C.CAL_DIR.relative_to(C.REPO_ROOT)}")
    print(f"writing   : {C.ARTIFACTS_DIR.relative_to(C.REPO_ROOT)}\n")
    total = 0
    for fn, fn_build in BUILDERS:
        out = C.write_page(fn, fn_build())
        size = out.stat().st_size
        total += size
        print(f"  ✓ {fn:22s} {size:>8,} bytes")
    print(f"\n{len(BUILDERS)} pages · {total:,} bytes · all self-contained, all from committed data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
