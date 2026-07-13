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

## Run the live server (Wave 2+, needs the full deps + an Anthropic key)

```bash
pip install -r server/requirements.txt
uvicorn citeval_api.app:app --reload      # once W2-SERVER lands server/citeval_api/app.py
# or:  python server/main.py
```

The web app is **mock-backed by default** (`VITE_USE_MOCK=true`), so the UI runs with no server
and no key; flip to `false` to hit this API. See `web/` and `docs/api_contract.md` §Showcase.
