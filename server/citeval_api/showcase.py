"""Cached ``RunResult``s for ``GET /api/showcase`` — the no-API-key gallery (W2-SERVER).

A judge can open the app with **no Anthropic key** and still render real, fully-populated verdicts:
this module loads a small corpus of pre-computed :class:`~citeval_api.contracts.RunResult`s off disk
(so nothing here touches NCBI, the model, or a key) and the server returns them verbatim.

Source of truth, in order of preference:

1. ``server/citeval_api/data/showcase_runs.json`` — the four canonical fixtures (retraction catch,
   species-scope mismatch, graded over-reach, abstention), generated from the FE ``SHOWCASE_RUNS``
   (``web/src/lib/fixtures.ts``) by ``server/tools/gen_showcase.py``. This is the primary feed.
2. ``data/schemas/run_result.json`` — the canonical W0 example (its ``RunResult`` plus the
   ``BatchResult.items``). A robust fallback so the route never 500s even if (1) is absent.

Every candidate is validated through the frozen ``RunResult`` model; a malformed entry is skipped,
never crashing the server. The result is parsed once and cached (the corpus is static).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .contracts import RunResult

# server/citeval_api/showcase.py -> parents[2] == repo root.
_ROOT = Path(__file__).resolve().parents[2]
_PRIMARY = Path(__file__).resolve().parent / "data" / "showcase_runs.json"
_FALLBACK = _ROOT / "data" / "schemas" / "run_result.json"


def _coerce(obj: Any) -> RunResult | None:
    """Validate one candidate dict into a :class:`RunResult`, or ``None`` if it is malformed."""
    if not isinstance(obj, dict):
        return None
    try:
        return RunResult(**obj)
    except Exception:  # noqa: BLE001 — a bad fixture must never take the route down
        return None


def _from_primary() -> list[RunResult]:
    if not _PRIMARY.exists():
        return []
    try:
        data = json.loads(_PRIMARY.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(data, list):
        return []
    return [rr for rr in (_coerce(x) for x in data) if rr is not None]


def _from_fallback() -> list[RunResult]:
    """The W0 schema doc carries one ``RunResult`` example and a ``BatchResult`` whose ``items`` are
    also RunResults — enough for a non-empty gallery if the generated corpus is missing."""
    if not _FALLBACK.exists():
        return []
    try:
        doc = json.loads(_FALLBACK.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    candidates: list[Any] = []
    if isinstance(doc, dict):
        if "RunResult" in doc:
            candidates.append(doc["RunResult"])
        batch = doc.get("BatchResult")
        if isinstance(batch, dict) and isinstance(batch.get("items"), list):
            candidates.extend(batch["items"])
    seen: set[str] = set()
    out: list[RunResult] = []
    for rr in (_coerce(x) for x in candidates):
        if rr is not None and rr.run_id not in seen:
            seen.add(rr.run_id)
            out.append(rr)
    return out


@lru_cache(maxsize=1)
def showcase_runs() -> tuple[RunResult, ...]:
    """The cached showcase corpus (parsed once). Primary feed, falling back to the W0 schema doc."""
    runs = _from_primary() or _from_fallback()
    return tuple(runs)


def load_showcase() -> list[RunResult]:
    """A fresh list of the showcase :class:`RunResult`s for ``GET /api/showcase``."""
    return list(showcase_runs())


__all__ = ["load_showcase", "showcase_runs"]
