"""uvicorn entrypoint for the citeval API server (W2-SERVER).

Run either way:

    python server/main.py                      # runs uvicorn with this file's app
    uvicorn citeval_api.app:app --reload       # from inside server/ (PYTHONPATH=server)
    uvicorn main:app --app-dir server          # equivalent, from the repo root

`server/` (for the `citeval_api` package) and `src/` (for the read-only `citeval` package the
runner imports) are put on `sys.path` here so `python server/main.py` works from a fresh checkout
with no install step — mirroring how the unit tests bootstrap their paths.

Config via env: `HOST` (default 127.0.0.1), `PORT` (default 8000), `RELOAD` (truthy → autoreload).
Set `NCBI_EMAIL` / `NCBI_API_KEY` for higher NCBI limits and `ANTHROPIC_API_KEY` for live runs;
neither is needed for `GET /api/showcase` (cached, no key) or the offline unit tests.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # server/
_ROOT = _HERE.parent                             # repo root
for _p in (_HERE, _ROOT / "src"):
    _s = str(_p)
    if _p.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)

from citeval_api.app import create_app  # noqa: E402  (after the sys.path bootstrap)

# Module-level app so `uvicorn main:app` / `uvicorn server.main:app` resolve it.
app = create_app()


def _truthy(val: str | None) -> bool:
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    reload = _truthy(os.environ.get("RELOAD"))
    # With reload, uvicorn re-imports by string target (it spawns a worker) — point it at this module.
    target = "main:app" if reload else app
    uvicorn.run(target, host=host, port=port, reload=reload, app_dir=str(_HERE))


if __name__ == "__main__":
    main()
