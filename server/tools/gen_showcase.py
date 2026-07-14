"""Extract the showcase RunResults from the FE fixtures into a Python-loadable JSON corpus.

`GET /api/showcase` must serve real, fully-populated ``RunResult``s so a judge renders live
verdicts with **no API key** (api_contract §9). The canonical four fixtures — retraction catch,
species-scope mismatch, graded over-reach, abstention — are authored in TypeScript
(``web/src/lib/fixtures.ts``, the ``SHOWCASE_RUNS`` source of truth). The Python server cannot
import TS, so this generator lifts those four object literals out of the TS source and writes them,
**verbatim and in FIXTURES order**, to ``server/citeval_api/data/showcase_runs.json`` — the same
established pattern the repo uses for other cross-language generated artifacts (the committed
``rw_index_*.json`` and the vendored NCBI cache).

The TS ``FIXTURE_*`` blocks are JSON-compatible object literals (double-quoted keys/strings,
JSON scalars) modulo trailing commas, so extraction is: brace-match each ``export const FIXTURE_X:
RunResult = { … };`` block, strip trailing commas with a **string-aware** scan (never touching a
comma inside a string), and ``json.loads``. Re-run whenever the fixtures change:

    python server/tools/gen_showcase.py         # regenerates the committed JSON

Run from any cwd; paths are resolved relative to the repo root (this file's ../../.. ).
"""
from __future__ import annotations

import json
from pathlib import Path

# Repo layout: server/tools/gen_showcase.py -> parents[2] == repo root.
_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES_TS = _ROOT / "web" / "src" / "lib" / "fixtures.ts"
_OUT = _ROOT / "server" / "citeval_api" / "data" / "showcase_runs.json"

# The showcase order is FIXTURES order (fixtures.ts): retraction, scope, over-reach, abstention.
_FIXTURE_CONSTS = (
    "FIXTURE_RETRACTION",
    "FIXTURE_SCOPE_MISMATCH",
    "FIXTURE_GRADED_OVERREACH",
    "FIXTURE_ABSTENTION",
)


def _extract_object_literal(src: str, const_name: str) -> str:
    """Return the ``{ … }`` object literal assigned to ``export const <const_name> … = { … }``.

    Brace-matches from the first ``{`` after the declaration to its balancing ``}``, ignoring braces
    that occur inside strings (so a ``{`` in an abstract never throws the count off)."""
    marker = f"const {const_name}"
    at = src.find(marker)
    if at < 0:
        raise ValueError(f"{const_name} not found in {_FIXTURES_TS}")
    start = src.find("{", at)
    if start < 0:
        raise ValueError(f"no object literal after {const_name}")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(src)):
        ch = src[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[start : i + 1]
    raise ValueError(f"unbalanced braces extracting {const_name}")


def _strip_trailing_commas(literal: str) -> str:
    """Remove JS trailing commas (``,`` before a ``}``/``]``) that JSON forbids — string-aware, so a
    literal comma inside prose is never touched."""
    out: list[str] = []
    in_str = False
    esc = False
    n = len(literal)
    for i, ch in enumerate(literal):
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            continue
        if ch == ",":
            # peek to the next non-whitespace char; drop the comma if it closes a container.
            j = i + 1
            while j < n and literal[j] in " \t\r\n":
                j += 1
            if j < n and literal[j] in "}]":
                continue  # trailing comma — skip it
        out.append(ch)
    return "".join(out)


def build_showcase() -> list[dict]:
    src = _FIXTURES_TS.read_text(encoding="utf-8")
    runs: list[dict] = []
    for name in _FIXTURE_CONSTS:
        literal = _strip_trailing_commas(_extract_object_literal(src, name))
        obj = json.loads(literal)
        if not {"run_id", "verdict"} <= set(obj):  # both required keys must be present
            raise ValueError(f"{name} did not parse into a RunResult-shaped object")
        runs.append(obj)
    return runs


def main() -> None:
    runs = build_showcase()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(runs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ids = ", ".join(r["run_id"] for r in runs)
    print(f"wrote {len(runs)} showcase RunResult(s) -> {_OUT.relative_to(_ROOT)}\n  [{ids}]")


if __name__ == "__main__":
    main()
