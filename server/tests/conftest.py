"""pytest bootstrap (mirrors server/tests/__init__.py for the unittest path).

Ensures `server/` is importable as the root for `citeval_api` before any test collection,
so `from citeval_api import ...` works under pytest from any rootdir.
"""
import sys
from pathlib import Path

_SERVER_DIR = str(Path(__file__).resolve().parent.parent)
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)
