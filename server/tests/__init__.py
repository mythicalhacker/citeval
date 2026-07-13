"""Test package for the citeval API server.

Runnable with the STDLIB — no pytest required (pytest is not installed in the eval env, so the
tests are written as `unittest.TestCase`; they also run under pytest if it is present):

    python -m unittest discover -s server/tests -t server

Importing this package puts the `server/` directory on `sys.path` so `import citeval_api`
resolves regardless of the current working directory or the runner (unittest or pytest).
"""
import sys
from pathlib import Path

# server/tests/__init__.py -> parent is server/tests -> parent.parent is server/
_SERVER_DIR = str(Path(__file__).resolve().parent.parent)
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)
