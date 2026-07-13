"""Seed the on-disk NCBI grounding cache from committed fixtures.

`test_demo` (offline end-to-end) and `test_showcase` (offline gallery build) drive the
real C2 grounding path, which reads raw NCBI EFetch XML + a MeSH tree-number cache from
`src/citeval/.cache/`. That directory is **gitignored** (see `.gitignore`), so on a fresh
checkout — e.g. CI, or any worktree that has never run a live pipeline — it is absent, and
those tests would either hit the network or fail the `_no_network` guard. `unittest discover`
did not collect them before (they were pytest-style module functions), so this never mattered;
once they are collected under `make test`, they must be hermetic.

This helper warms the cache from vendored fixtures under `fixtures/ncbi_cache/`: the exact
raw EFetch db=pubmed XML for the four calibration papers those tests touch (PMIDs
28772265 / 28882997 / 29895198 / 31175044) plus the MeSH tree-number cache. It mirrors the
repo's existing decision to commit `src/citeval/data/rw_index_*.json` so every worktree is
runtime-green offline without a build dep (see `.gitignore`). The XML is frozen public NCBI
data, so the offline verdicts the tests assert are deterministic.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ncbi_cache"


def seed_ncbi_cache() -> None:
    """Copy vendored EFetch XML + MeSH cache into the live grounding cache dir and refresh
    grounding's in-memory MeSH map. Copies only files that are MISSING — never clobbers a
    warm dev cache — and is safe to call repeatedly (idempotent)."""
    from citeval import grounding  # imported here so the helper has no import-time side effect

    # 1) raw efetch db=pubmed XML, keyed by PMID (grounding reads these instead of fetching).
    src_ef = _FIXTURE / "efetch_pubmed"
    grounding._EFETCH_DIR.mkdir(parents=True, exist_ok=True)
    for xml in sorted(src_ef.glob("*.xml")):
        dst = grounding._EFETCH_DIR / xml.name
        if not dst.exists():
            shutil.copyfile(xml, dst)

    # 2) MeSH tree-number cache. grounding binds `_mesh_cache` at IMPORT time (before this
    #    seed runs), so writing the file alone is not enough — refresh the in-memory dict too,
    #    which is what `_prefetch_trees` consults to decide whether a network lookup is needed.
    mesh_fx = _FIXTURE / "mesh_tree.json"
    if mesh_fx.exists():
        data = json.loads(mesh_fx.read_text())
        grounding._CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if not grounding._MESH_CACHE.exists():
            grounding._MESH_CACHE.write_text(json.dumps(data))
        grounding._mesh_cache.update(data)
