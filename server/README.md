# `citeval_api` — HTTP/SSE server for the citation-verification pipeline

A thin, **read-only** web surface over the `citeval` package. It never edits `src/citeval/*`;
it drives the pipeline through the two seams that already exist — the injected
`adjudicate(..., client=)` and the `config.on_round(...)` hook — and streams live progress,
cost, and verdicts over Server-Sent Events.

> **Authoritative interface:** [`docs/api_contract.md`](../docs/api_contract.md). This README is
> orientation; the contract file is the source of truth every session codes against.

## What W0-CONTRACTS shipped (frozen)

| File | What it is |
|---|---|
| `citeval_api/contracts.py` | Pydantic wire types — `RunRequest`, `BatchRequest`, `RunResult`, `BatchResult`, `TelemetrySummary`, and one model per SSE event. **Pure types**; no I/O, no `citeval` import. |
| `citeval_api/pricing.py` | The cost model: `PRICING` rate card, `cost_of(usage) -> float`, `summarize(usages) -> TelemetrySummary`. |
| `tests/test_pricing.py` | Costing tests (hand-computed reference). |

Mirrored 1:1 in `web/src/lib/types.ts` (TypeScript) and described in `docs/api_contract.md`.
The canonical JSON examples live in `data/schemas/run_result.json` and `data/schemas/sse_events.json`.

## What later sprint sessions add (their own files — no collisions)

`telemetry.py` (W1-TELEMETRY) · `events.py` + `progress.py` (W1-EVENTS) · `runner.py`
(W2-RUNNER) · `batch.py` (W2-BATCH) · `app.py` + `../main.py` (W2-SERVER).

## The two frozen pipeline seams (do not change silently)

1. **Injected client** — `citeval.adjudicator.adjudicate(g, scope, claim_text, *, client=, config=)`.
   The client exposes `complete_with_usage(*, model, system, user, max_tokens, temperature)
   -> (text, output_tokens)` (with a `complete(...) -> str` fallback). W1-TELEMETRY's
   `TelemetryModelClient` implements it, wraps the real Anthropic client, and forwards **all**
   kwargs transparently (so it keeps working if tool-use lands).
2. **`config.on_round(round_index, critic_round, critic_output_tokens)`** — one call per
   self-consistency round. W2-RUNNER turns each into `debate_round` + `model_call` SSE events.

## Run the tests (stdlib — no pytest needed)

`pytest` is **not** installed in the eval environment; the W0 tests are `unittest.TestCase` and
run on the stdlib (only `pydantic` is required, and it is present):

```bash
python -m unittest discover -s server/tests -t server -v
```

They also run under pytest if you install it (`pip install -r server/requirements.txt`):

```bash
pytest server/tests
```

## Run the live server (W2-SERVER — `app.py` + `main.py`)

```bash
pip install -r server/requirements.txt
python server/main.py                     # 127.0.0.1:8000 (HOST/PORT/RELOAD via env)
# or, from inside server/:  uvicorn citeval_api.app:app --reload
```

An **Anthropic key is needed only to start a new run** (`POST /api/runs`, live path). The key-free
routes work immediately: `GET /api/health`, `GET /api/pricing`, and **`GET /api/showcase`** — which
serves the four cached, fully-populated `RunResult`s (retraction catch, species-scope mismatch,
graded over-reach, abstention) so a judge renders real verdicts with **no key**. Those are loaded
from `citeval_api/data/showcase_runs.json`, generated from the FE `SHOWCASE_RUNS` fixtures by:

```bash
python server/tools/gen_showcase.py        # regenerate after web/src/lib/fixtures.ts changes
```

If a built SPA exists at `web/dist`, it is served at `/` (with an index fallback for client-side
routes); `/api` always takes precedence. In dev the web app is **mock-backed by default**
(`VITE_USE_MOCK=true`) and runs with no server and no key; flip to `false` (CORS is pre-configured
for the Vite dev origin) to hit this API. Batch routes are guarded: if `citeval_api.batch`
(W2-BATCH) has not merged, `POST /api/batch` returns `503` and every run route still works.

Run the app's own end-to-end tests (offline; skips cleanly if FastAPI is not installed):

```bash
python -m unittest discover -s server/tests -t server -v   # includes test_app.py
```
