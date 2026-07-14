"""End-to-end tests for the FastAPI app (`citeval_api.app`, W2-SERVER).

Drives the frozen API contract (`docs/api_contract.md`) against a FastAPI ``TestClient`` — the
DoD flow **POST /api/runs → GET /api/runs/{id}/events (SSE) → GET /api/runs/{id}** plus the
key-free meta routes (``/api/pricing``, ``/api/showcase``, ``/api/health``) and the 404 / batch-guard
edges. No live API key and no network are touched:

- The MODEL is an in-process ``FakeAnthropic`` (scripted supporter/refuter/critic JSON per triad
  turn, role-selected by fingerprinting the system prompt) injected via
  ``create_app(model_client_factory=…)`` — the same seam W1-TELEMETRY / W2-RUNNER tests use.
- GROUNDING runs the REAL offline ``citeval.grounding.ground()``: the committed NCBI cache fixtures
  are seeded and full-text fetch is stubbed to the honest-empty value (no PMC round-trip).

Stdlib ``unittest`` only (pytest is NOT installed in the eval env — see server/README.md). The
whole module **skips cleanly** when FastAPI/Starlette are absent (a stdlib-only checkout that never
ran ``pip install -r server/requirements.txt``), so ``unittest discover -s server/tests`` stays green
there while running fully here.

Run:
    python -m unittest discover -s server/tests -t server -v
    # or standalone:  python server/tests/test_app.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
import unittest
from types import SimpleNamespace

# Make `citeval` (src/), `citeval_api` (server/), and the root `tests/` helpers importable without
# installation. MUST precede any `citeval*` import.
_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
for _p in (str(_ROOT / "src"), str(_ROOT / "server"), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# FastAPI is a Wave-2 dependency; skip the whole module gracefully if it (or the TestClient's httpx)
# is not installed, so a stdlib-only `unittest discover` over server/tests still passes.
try:
    from fastapi.testclient import TestClient  # noqa: E402
    _HAS_FASTAPI = True
    _SKIP_REASON = ""
except Exception as exc:  # noqa: BLE001
    TestClient = None  # type: ignore[assignment,misc]
    _HAS_FASTAPI = False
    _SKIP_REASON = f"FastAPI/TestClient unavailable ({type(exc).__name__}: {exc})"

from _ncbi_cache_fixture import seed_ncbi_cache  # noqa: E402  (root tests/ helper)
from citeval import grounding  # noqa: E402
from citeval.contracts import CitedIdentifier  # noqa: E402
from citeval_api.telemetry import fingerprint_role  # noqa: E402

# A vendored PMID (committed under tests/fixtures/ncbi_cache/efetch_pubmed) so grounding is offline.
PMID = "28882997"
CLAIM = ("In human dopaminergic neurons, oxidized dopamine accumulation drives lysosomal "
         "dysfunction.")
GRADE = "supported-with-overreach"


# ============================================================================================
# In-process Anthropic fake (mirrors test_runner's) — role-appropriate JSON per triad turn.
# ============================================================================================
def _usage(inp=1200, out=300, cache_write=0, cache_read=800):
    return SimpleNamespace(input_tokens=inp, output_tokens=out,
                           cache_creation_input_tokens=cache_write,
                           cache_read_input_tokens=cache_read)


def _message(text):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)],
                           usage=_usage(), stop_reason="end_turn")


class _FakeMessages:
    def __init__(self, outer):
        self._outer = outer

    def create(self, **kwargs):
        self._outer.calls.append(kwargs)
        return self._outer.respond(kwargs)


class FakeAnthropic:
    """Returns role-appropriate JSON per triad turn (supporter/refuter quote a verbatim run of the
    grounded abstract; the critic returns a consistent ordinal grade), so the run adjudicates to a
    real GRADED verdict entirely offline."""

    def __init__(self, quote: str):
        self.calls: list[dict] = []
        self._quote = quote
        self.messages = _FakeMessages(self)

    def respond(self, kwargs):
        role = fingerprint_role(kwargs.get("system"))
        if role == "supporter":
            body = {"points": [{"quote": self._quote,
                                "rationale": "the source states this substantive finding",
                                "point": "directly supports the claim"}]}
        elif role == "refuter":
            body = {"points": [{"quote": self._quote,
                                "objection": "the certainty asserted outruns a single study",
                                "routes_to": "grade", "failure_mode": "overreach"}]}
        elif role == "critic":
            body = {"reasoning": "weighs the decisive verbatim spans, substance only",
                    "decisive_spans": [self._quote],
                    "boundary_test_fired": "on-point",
                    "grade": GRADE, "confidence": 0.9,
                    "grade_rationale_last": "supported but with mild over-reach"}
        else:  # pragma: no cover
            body = {}
        return _message(json.dumps(body))


# ============================================================================================
# SSE wire parsing.
# ============================================================================================
def _parse_sse(raw_lines) -> list[tuple[str, dict]]:
    """Parse an SSE byte/line stream into ``[(event, data_dict), …]`` frames."""
    frames: list[tuple[str, dict]] = []
    event: str | None = None
    data_buf: list[str] = []
    for line in raw_lines:
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        line = line.rstrip("\n").rstrip("\r")
        if line == "":
            if event is not None and data_buf:
                frames.append((event, json.loads("\n".join(data_buf))))
            event, data_buf = None, []
            continue
        if line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_buf.append(line[len("data:"):].lstrip())
    if event is not None and data_buf:  # a final frame with no trailing blank line
        frames.append((event, json.loads("\n".join(data_buf))))
    return frames


@unittest.skipUnless(_HAS_FASTAPI, _SKIP_REASON)
class AppEndToEndTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_ncbi_cache()
        cls._orig_fetch = grounding.fetch_full_text
        grounding.fetch_full_text = lambda pmid, abstract, errors=None: ("", "")
        g = grounding.ground(CitedIdentifier("pmid", PMID), with_full_text=True)
        assert g.abstract, "vendored fixture must carry an abstract to quote from"
        cls.quote = " ".join(g.abstract.split()[2:12])

    @classmethod
    def tearDownClass(cls):
        grounding.fetch_full_text = cls._orig_fetch

    def _make_client(self) -> TestClient:
        # Import here so module import (and the skip decorator) never require citeval_api.app,
        # which pulls FastAPI — the skip must win on a stdlib-only checkout.
        from citeval_api.app import create_app
        from citeval_api.events import EventBus
        from citeval_api.progress import Benchmarks

        app = create_app(
            bus=EventBus(),                                   # isolated bus per app
            benchmarks=Benchmarks(),
            model_client_factory=lambda: FakeAnthropic(self.quote),
            serve_web=False,                                  # no static mount in tests
        )
        return TestClient(app)

    def _get_run_until_ready(self, client, run_id, tries=100):
        """Poll GET /api/runs/{id}: 409 while the background task is finalizing, then 200. Each
        request pumps the app's event loop, so the run's result assignment lands within a few tries."""
        last = None
        for _ in range(tries):
            resp = client.get(f"/api/runs/{run_id}")
            if resp.status_code != 409:
                return resp
            last = resp
            time.sleep(0.02)
        return last

    # -- the DoD flow: POST /runs -> GET /events (SSE) -> GET /runs/{id} ----------------------
    def test_run_lifecycle_post_stream_get(self):
        with self._make_client() as client:
            # 1) POST /api/runs -> RunCreated{run_id}
            resp = client.post("/api/runs",
                               json={"claim": CLAIM, "paper_ref": PMID, "mode": "pmid"})
            self.assertEqual(resp.status_code, 200, resp.text)
            run_id = resp.json()["run_id"]
            self.assertTrue(run_id.startswith("run_"))

            # 2) GET /api/runs/{id}/events -> the full ordered SSE stream (buffered replay makes
            #    this robust to the create->subscribe race).
            with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
                self.assertEqual(stream.status_code, 200)
                self.assertTrue(stream.headers["content-type"].startswith("text/event-stream"))
                frames = _parse_sse(stream.iter_lines())

            names = [e for e, _ in frames]
            self.assertEqual(names[0], "run_start")
            self.assertEqual(names[-1], "run_complete")
            self.assertNotIn("error", names)

            # envelope: gap-free seq from 0, run_id stamped on every frame.
            seqs = [d["seq"] for _, d in frames]
            self.assertEqual(seqs, list(range(len(frames))))
            self.assertTrue(all(d["run_id"] == run_id for _, d in frames))

            # all five stages bracketed, in canonical order.
            stages = ["ingest", "ground_retraction", "ground_scope", "adjudicate", "report"]
            self.assertEqual([d["stage"] for e, d in frames if e == "stage_start"], stages)
            self.assertEqual([d["stage"] for e, d in frames if e == "stage_end"], stages)

            # the live-debate frames are present.
            self.assertTrue(any(e == "model_call" for e in names))
            self.assertTrue(any(e == "debate_round" for e in names))
            self.assertTrue(any(e == "cost_update" for e in names))
            self.assertTrue(any(e == "progress" for e in names))

            # run_complete carries a RunResult for this id.
            complete = frames[-1][1]
            self.assertEqual(complete["result"]["run_id"], run_id)

            # 3) GET /api/runs/{id} -> the final RunResult.
            got = self._get_run_until_ready(client, run_id)
            self.assertEqual(got.status_code, 200, got.text)
            result = got.json()
            self.assertEqual(result["run_id"], run_id)
            self.assertEqual(set(result["verdict"]),
                             {"claim_unit", "grounded", "claim_scope", "verdict"})
            axes = {a["axis"] for a in result["verdict"]["verdict"]["axis_findings"]}
            self.assertEqual(
                axes, {"retraction", "species_scope", "population_scope", "substantive_support"})
            self.assertEqual(set(result["timing"]["per_stage_ms"]), set(stages))
            self.assertGreater(result["cost"]["total_usd"], 0.0)
            self.assertIn("<html", result["report_html"].lower())

            # the SSE result and the GET result agree.
            self.assertEqual(result["run_id"], complete["result"]["run_id"])

    # -- meta routes --------------------------------------------------------------------------
    def test_pricing(self):
        from citeval_api import pricing
        with self._make_client() as client:
            resp = client.get("/api/pricing")
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertEqual(body["unit"], "usd_per_million_tokens")
            for tier in ("input", "output", "cache_write", "cache_read"):
                self.assertEqual(body[tier], pricing.PRICING[tier])
            self.assertTrue(body["note"])

    def test_health(self):
        with self._make_client() as client:
            resp = client.get("/api/health")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json(), {"status": "ok"})

    def test_showcase_serves_valid_runresults_without_a_key(self):
        with self._make_client() as client:
            resp = client.get("/api/showcase")
            self.assertEqual(resp.status_code, 200)
            runs = resp.json()
            self.assertIsInstance(runs, list)
            self.assertGreaterEqual(len(runs), 1)
            for rr in runs:
                self.assertTrue(rr["run_id"])
                self.assertEqual(set(rr["verdict"]),
                                 {"claim_unit", "grounded", "claim_scope", "verdict"})
                self.assertIn("<html", rr["report_html"].lower())

    # -- edges: unknown ids + the batch guard -------------------------------------------------
    def test_unknown_run_id_404(self):
        with self._make_client() as client:
            self.assertEqual(client.get("/api/runs/does_not_exist").status_code, 404)
            self.assertEqual(client.get("/api/runs/does_not_exist/events").status_code, 404)

    def test_batch_guard_when_w2_batch_absent(self):
        # W2-BATCH may not be merged in this tree; POST /api/batch must degrade to 503 (never 500)
        # so runs keep working. If batch HAS merged, a 2xx is equally acceptable.
        with self._make_client() as client:
            resp = client.post("/api/batch",
                               json={"items": [{"claim": CLAIM, "paper_ref": PMID}]})
            self.assertIn(resp.status_code, (200, 503), resp.text)
            self.assertEqual(client.get("/api/batch/does_not_exist").status_code, 404)

    # -- retention cap: completed runs are evicted so memory stays bounded --------------------
    def test_completed_runs_are_evicted_past_the_cap(self):
        from citeval_api.app import create_app
        from citeval_api.events import EventBus

        bus = EventBus()
        app = create_app(
            bus=bus, model_client_factory=lambda: FakeAnthropic(self.quote),
            serve_web=False, max_retained=2,
        )
        state = app.state.citeval
        with TestClient(app) as client:
            ids = []
            for _ in range(4):
                r = client.post("/api/runs",
                               json={"claim": CLAIM, "paper_ref": PMID, "mode": "pmid"})
                rid = r.json()["run_id"]
                self.assertEqual(self._get_run_until_ready(client, rid).status_code, 200)
                ids.append(rid)
            # With a cap of 2, at most 2 completed runs (plus any in-flight) are retained; the
            # oldest completed runs were evicted and their bus streams discarded.
            self.assertLessEqual(len(state.runs), 3)
            self.assertNotIn(ids[0], state.runs)
            self.assertNotIn(ids[0], bus)
            self.assertEqual(client.get(f"/api/runs/{ids[0]}").status_code, 404)
            self.assertEqual(client.get(f"/api/runs/{ids[-1]}").status_code, 200)  # newest kept


def _get_until_ready(client, path, tries=100):
    """Poll a GET that returns 409 while its background task finalizes, then its terminal code."""
    last = None
    for _ in range(tries):
        resp = client.get(path)
        if resp.status_code != 409:
            return resp
        last = resp
        time.sleep(0.02)
    return last


@unittest.skipUnless(_HAS_FASTAPI, _SKIP_REASON)
class BatchGuardTest(unittest.TestCase):
    """W2-BATCH is not merged in this tree, so inject a fake ``_batch_entry`` to exercise the guarded
    batch routes and lock in the forward-compat invariants: a SYNC entrypoint is offloaded (never
    blocks the loop) and its stream is sealed, and a FAILING entrypoint that publishes nothing still
    records a 500 and leaves a SEALED stream (so a later subscriber never hangs)."""

    def _client(self, entry):
        from citeval_api import app as app_mod
        from citeval_api.events import EventBus
        from citeval_api.progress import Benchmarks

        self._app_mod = app_mod
        self._saved_entry = app_mod._batch_entry
        app_mod._batch_entry = entry            # create_batch reads this module global at call time
        bus = EventBus()
        app = app_mod.create_app(bus=bus, benchmarks=Benchmarks(), serve_web=False)
        return TestClient(app), bus

    def tearDown(self):
        if getattr(self, "_app_mod", None) is not None:
            self._app_mod._batch_entry = self._saved_entry

    def test_sync_batch_entry_is_offloaded_and_sealed(self):
        from citeval_api.contracts import BatchAggregate, BatchResult

        def fake_ok(req, *, batch_id, bus, **kw):
            bus.publish(batch_id, "batch_start", None, n=len(req.items))
            result = BatchResult(batch_id=batch_id, items=[],
                                 aggregate=BatchAggregate(n=len(req.items)))
            bus.publish(batch_id, "batch_complete", {"result": result.model_dump()})
            return result                        # SYNC return: the adapter must offload, not block

        client, bus = self._client(fake_ok)
        with client:
            resp = client.post("/api/batch",
                               json={"items": [{"claim": CLAIM, "paper_ref": PMID}]})
            self.assertEqual(resp.status_code, 200, resp.text)
            batch_id = resp.json()["batch_id"]
            self.assertTrue(batch_id.startswith("batch_"))
            got = _get_until_ready(client, f"/api/batch/{batch_id}")
            self.assertEqual(got.status_code, 200, got.text)
            self.assertEqual(got.json()["batch_id"], batch_id)
            self.assertTrue(bus.stream(batch_id, create=False).is_done)  # sealed

    def test_failing_batch_entry_records_500_and_seals_stream(self):
        def fake_boom(req, **kw):
            raise RuntimeError("boom in batch entrypoint")   # fails BEFORE publishing anything

        client, bus = self._client(fake_boom)
        with client:
            resp = client.post("/api/batch", json={"items": []})
            self.assertEqual(resp.status_code, 200, resp.text)
            batch_id = resp.json()["batch_id"]
            got = _get_until_ready(client, f"/api/batch/{batch_id}")
            self.assertEqual(got.status_code, 500, got.text)          # error surfaced
            # The stream must exist AND be sealed even though the entry published nothing — a late
            # subscriber must not hang on a lazily-created, never-closed stream.
            stream = bus.stream(batch_id, create=False)
            self.assertIsNotNone(stream)
            self.assertTrue(stream.is_done)


if __name__ == "__main__":
    unittest.main(verbosity=2)
