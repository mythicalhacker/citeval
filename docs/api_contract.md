# citeval API contract (v1) — **authoritative**

Frozen by **W0-CONTRACTS**. Every sprint session codes against this document. It is mirrored,
type-for-type, in three places that must always agree:

| Surface | File |
|---|---|
| Python wire types (Pydantic) | `server/citeval_api/contracts.py` |
| TypeScript types | `web/src/lib/types.ts` |
| Cost model | `server/citeval_api/pricing.py` |
| Canonical JSON examples | `data/schemas/run_result.json`, `data/schemas/sse_events.json` |
| Runnable mock + fixtures | `web/src/lib/mockServer.ts`, `web/src/lib/fixtures.ts` |

> **Change control.** If any shape here changes, it changes in **all** of the above at once, and
> that is a **manager decision** — never a silent edit in one place. The two pipeline seams
> (`adjudicate(..., client=)` and `config.on_round`) are likewise frozen; a core session that must
> change either updates this file and pings `W2-RUNNER`/`W2-BATCH`/`W2-SERVER`.

The server is a thin, **read-only** surface over the `citeval` package. It never edits
`src/citeval/*`; it drives the pipeline through the injected client and the `on_round` hook, and
streams live progress, cost, and verdicts over SSE. The web app is **mock-backed by default**
(`VITE_USE_MOCK=true`), so the full UI builds and demos with no server and no API key.

---

## 1. REST routes (FastAPI, mounted at `/api`)

| # | Method | Route | Request body | Response |
|---|---|---|---|---|
| 1 | POST | `/api/runs` | `RunRequest` | `RunCreated` = `{ run_id }` |
| 2 | GET | `/api/runs/{id}/events` | — | `text/event-stream` (run SSE) |
| 3 | GET | `/api/runs/{id}` | — | `RunResult` |
| 4 | POST | `/api/batch` | `BatchRequest` | `BatchCreated` = `{ batch_id }` |
| 5 | GET | `/api/batch/{id}/events` | — | `text/event-stream` (batch SSE) |
| 6 | GET | `/api/batch/{id}` | — | `BatchResult` |
| 7 | GET | `/api/pricing` | — | `PricingInfo` |
| 8 | GET | `/api/health` | — | `{ "status": "ok" }` |
| 9 | GET | `/api/showcase` | — | `RunResult[]` (cached; no key needed) |

**The two-call run pattern:** `POST /api/runs` returns a `run_id` immediately; the client then
opens `GET /api/runs/{id}/events` (an `EventSource`) to watch the run, and/or polls
`GET /api/runs/{id}` for the final `RunResult`. Batch is symmetric.

`GET /api/showcase` serves cached `RunResult`s (the fixtures / corpus) so a judge can render real
verdicts with **no API key**. `POST` routes need a live key only when `VITE_USE_MOCK=false`.

### `RunRequest`
```jsonc
{
  "claim": "string (required) — the citing sentence, verbatim",
  "paper_ref": "string | null — a PMID (\"22088800\") or DOI (\"10.1016/...\") to resolve",
  "citation_string": "string | null — a pasted free-text reference to parse into an identifier",
  "manuscript_text": "string | null — bring-your-own full text (no NCBI lookup)",
  "mode": "pmid | doi | citation | manuscript | auto   (default \"auto\")"
}
```
Exactly one of `paper_ref` / `citation_string` / `manuscript_text` supplies the cited paper;
`mode` records (or forces) the channel. `auto` lets the server sniff the input.

### `BatchRequest`
```jsonc
{ "items": [ { "claim": "string", "paper_ref": "string | null" }, ... ] }
```

---

## 2. SSE framing

Every stream is `text/event-stream`. Each frame is one SSE event:

```
event: <event-name>
data: <JSON object>

```

The `data` object is the **envelope merged with the event's own fields**:

### Envelope (present on every frame's `data`)
| field | type | meaning |
|---|---|---|
| `run_id` | string | the run (or batch) id this frame belongs to |
| `seq` | int | monotonic, **gap-free** per stream — lets a late/replayed subscriber order + de-dup |
| `ts` | float | epoch seconds |
| `elapsed_ms` | float | ms since `run_start` |

Buffered replay (W1-EVENTS): a subscriber that connects slightly late still receives the whole
run from `seq: 0`. A completed stream ends after `run_complete` / `batch_complete` (plus a
transport close).

---

## 3. Run-stream events

Stages, in canonical order: **`ingest` → `ground_retraction` → `ground_scope` → `adjudicate` → `report`**.
Debate roles: **`supporter` | `refuter` | `critic`** (all Opus 4.8).

| event | fields (beyond the envelope) |
|---|---|
| `run_start` | `mode: RunMode`, `paper_ref?: string` |
| `stage_start` | `stage: Stage` |
| `stage_end` | `stage: Stage`, `summary: string` |
| `model_call` | `role: Role`, `round: int`, `phase: "start" \| "end"`, `usage?: TokenUsage`, `cost_usd?: float` |
| `debate_round` | `round: int`, `supporter_stance: string`, `refuter_stance: string`, `critic_grade: string`, `agreement: float` |
| `cost_update` | `cumulative_usd: float`, `delta_usd: float`, `tokens: TokenUsage` |
| `progress` | `pct: float (0–100)`, `est_total_ms: float`, `est_remaining_ms: float` |
| `run_complete` | `result: RunResult` |
| `error` | `stage?: Stage`, `message: string` |

Notes:
- `model_call` is emitted **twice** per role turn: `phase:"start"` before the call, `phase:"end"`
  after — `usage` and `cost_usd` are populated on `end` only.
- `debate_round` comes from `config.on_round`; `agreement` is the running exact-agreement
  (`a_exact`) after that round, and `critic_grade` is that round's ordinal grade.
- `progress`: `adjudicate` dominates and scales with round count; the estimator (W1-EVENTS) seeds
  sensible per-stage benchmarks and refines them from `stage_end` durations.

**Canonical ordering of one run** (early-stopping may shorten the `adjudicate` rounds):
```
run_start
stage_start(ingest) … stage_end(ingest) … progress
stage_start(ground_retraction) … stage_end(ground_retraction) … progress
stage_start(ground_scope) … stage_end(ground_scope) … progress
stage_start(adjudicate)
  [ per round r = 1..N (≤7):
      model_call(supporter,r,start) model_call(supporter,r,end)
      model_call(refuter,r,start)   model_call(refuter,r,end)
      model_call(critic,r,start)    model_call(critic,r,end)
      debate_round(r) cost_update progress ]
stage_end(adjudicate) … progress
stage_start(report) … stage_end(report) … progress
run_complete
```
`error` may appear at any point (carrying the failing `stage`); the runner then closes the stream.

---

## 4. Batch-stream events

Adds the following to the run events above (a batch stream carries only these four):

| event | fields (beyond the envelope) |
|---|---|
| `batch_start` | `n: int` |
| `item_update` | `index: int`, `run_id: string`, `status: "queued" \| "running" \| "done" \| "error"` |
| `batch_progress` | `done: int`, `total: int`, `cost_usd: float`, `elapsed_ms: float` |
| `batch_complete` | `result: BatchResult` |

Per-item failure is isolated (W2-BATCH): one item's `error` emits its `item_update{status:"error"}`
but never kills the batch. Concurrency is bounded by the orchestrator's worker count (default ~4) —
the dashboard's "true-parallel vs queued" indicator reflects the **real** worker count, not a fake.

---

## 5. Cost / telemetry

### `PRICING` — `GET /api/pricing` → `PricingInfo`
USD **per million tokens**, four tiers. **Illustrative Opus-class placeholders** — see the
`CONFIRM` comment in `pricing.py`; the manager swaps the confirmed rate card in Wave 3.
```jsonc
{ "input": 15.0, "output": 75.0, "cache_write": 18.75, "cache_read": 1.50,
  "unit": "usd_per_million_tokens", "note": "Illustrative … CONFIRM against current Anthropic pricing." }
```

### `cost_of(usage) -> float`
Prices one Anthropic `response.usage` (or a dict / `RawUsage`). Reads the SDK object **verbatim**
(attribute access), so W1-TELEMETRY forwards it unmodified:
```
cost = ( input_tokens            * PRICING.input
       + output_tokens           * PRICING.output
       + cache_creation_input_tokens * PRICING.cache_write
       + cache_read_input_tokens     * PRICING.cache_read ) / 1_000_000
```
Missing/`None`/garbage tiers price as 0; negatives can never credit the bill. Worked example:
`{input 1000, output 500, cache_creation 200, cache_read 4000}` → **0.06225** USD.

### `summarize(usages) -> TelemetrySummary`
Rolls a run's per-call usages (each optionally role-tagged via `usage.role`) into:
```jsonc
{
  "total_usd": 1.0538,
  "per_role": { "supporter": RoleCost, "refuter": RoleCost, "critic": RoleCost },
  "tokens":   { "input": 0, "output": 0, "cache_read": 0, "cache_write": 0 },  // TokenUsage
  "n_model_calls": 21
}
// RoleCost = { "usd": float, "n_calls": int, "tokens": TokenUsage }
```

### Two token shapes (on purpose)
- **`RawUsage`** mirrors the SDK `response.usage`: `input_tokens`, `output_tokens`,
  `cache_creation_input_tokens`, `cache_read_input_tokens` (+ a `role` tag added by telemetry).
  This is what `cost_of` consumes.
- **`TokenUsage`** is the friendly four-tier roll-up carried on `cost_update` and in
  `TelemetrySummary`: `input`, `output`, `cache_read`, `cache_write`.

---

## 6. `RunResult` / `BatchResult`

```jsonc
// RunResult — GET /api/runs/{id}; payload of run_complete
{
  "run_id": "string",
  "verdict": { /* verbatim citeval.reporting.render_json — see §7 */ },
  "timing":  { "per_stage_ms": { "ingest": 910.0, "ground_retraction": 1480.0,
                                 "ground_scope": 1210.0, "adjudicate": 84800.0, "report": 60.0 },
               "total_ms": 88460.0, "est_total_ms": 93767.6 },
  "cost":    { /* TelemetrySummary — see §5 */ },
  "report_html": "string — verbatim citeval.reporting.render_html document"
}
```
```jsonc
// BatchResult — GET /api/batch/{id}; payload of batch_complete
{
  "batch_id": "string",
  "items": [ RunResult, ... ],
  "aggregate": {
    "p_r_f": { "precision": 1.0, "recall": 1.0, "f1": 1.0 } | null,  // null unless items are gold-labelled
    "total_cost_usd": 2.08, "total_ms": 168000.0, "n": 2
  }
}
```
Full worked examples: **`data/schemas/run_result.json`**.

---

## 7. `RunResult.verdict` — the `render_json` shape

`verdict` is the **verbatim** output of `citeval.reporting.render_json`. It is intentionally an
**open object** on the wire — its sub-shapes live in the FROZEN `src/citeval/contracts.py` and must
**not** be re-typed/forked by the server (that would create a second, drifting source of truth).
The TS `RenderJson` interface in `types.ts` mirrors it for the FE; `data/schemas/grounded.json`
documents the `grounded` sub-shape.

```jsonc
{
  "claim_unit":  { "atomic_claim", "cited_identifier": {"type":"pmid|doi","value"}, "citing_source"? },
  "grounded":    { "identifier", "title", "abstract", "mesh_all", "organism_tags": [MeshTag],
                   "population_tags": [MeshTag], "sex_tags": [MeshTag], "publication_types",
                   "retraction": { "status": "RETRACTED|EXPRESSION_OF_CONCERN|NONE_FOUND",
                                   "retraction_watch": {"present","rw_record_id","reason","date"},
                                   "ncbi_publication_type_flag", "comments_corrections",
                                   "source_agreement", "provenance" },
                   "has_humans", "provenance", "grounding_errors",
                   "full_text", "full_text_provenance" },
  "claim_scope": { "organism", "organism_evidence", "population", "population_evidence",
                   "effect", "direction", "direction_evidence", "dose_stated",
                   "provenance", "tier" },
  "verdict":     { "claim", "cited_identifier", "overall",
                   "axis_findings": [ AxisFinding ], "unverifiable_axes", "stub", "notes" }
}
// MeshTag   = { "descriptor", "ui", "tree_numbers": [string], "major_topic": bool }
// AxisFinding = { "axis", "verdict", "tier", "provenance", "detail", "evidence": {} }
```

**Axis vocabulary** (produced by `citeval.objective_axes` + the adjudicator):
- `retraction.verdict`: `RELIES_ON_RETRACTED` · `CITED_PAPER_HAS_EOC` · `NOT_RETRACTED`
- `species_scope.verdict` / `population_scope.verdict`: `SCOPE_MISMATCH` · `SCOPE_CONSISTENT` · `NOT_ASSESSED`
- `substantive_support.verdict`: the RB1 ordinal — `fully-supported` · `supported-with-overreach` ·
  `partially-supported` · `technically-true-but-misleading` · `unsupported-for-the-claim` ·
  `contradicted` — plus the two non-graded outcomes `NOT_ENOUGH_INFO` (abstention) and
  `N/A — non-substantiating`.
- `provenance` atoms (composite-friendly string): `metadata-grounded` · `text-grounded` ·
  `model-inferred` · `stub-not-adjudicated`.

The `substantive_support` finding's `evidence` carries the CONTEXT_PACK §6 keys the renderer reads
(`confidence{verbalized,agreement,n_samples}`, `calibration{note}`, `supporter{span,point}`,
`refuter{span,objection}`, `abstained`) plus richer keys (`self_consistency{...}`) the renderer
ignores. See `types.ts` `SubstantiveEvidence`.

> **Invariant (metadata overrides model):** on the objective axes (retraction, species/population
> scope), a structured record is authoritative — a model value can never overturn it, and a
> conflict is scored as the model being wrong. `overall` gates to *NOT SUPPORTED AS STATED* when a
> retraction or scope gate fires, while the substantive grade is reported **alongside**, held
> separately (never silently depressed).

---

## 8. The two pipeline seams (frozen)

1. **Injected client** — `citeval.adjudicator.adjudicate(g, scope, claim_text, *, client=, config=)`.
   The client exposes
   `complete_with_usage(*, model, system, user, max_tokens, temperature) -> (text, output_tokens)`
   (with a `complete(...) -> str` fallback). W1-TELEMETRY's `TelemetryModelClient` implements it,
   wraps the real Anthropic client, and **forwards all kwargs transparently** (so it keeps working
   if tool-use / `thinking` land). The model is always Opus 4.8 (CLAUDE.md invariant #4).
2. **`config.on_round(round_index, critic_round, critic_output_tokens)`** — one call per
   self-consistency round with the round's critic result + usage. W2-RUNNER turns each into a
   `debate_round` (+ `model_call`) SSE event.

---

## 9. Mock, fixtures, and debate transcripts

- **`web/src/lib/mockServer.ts`** — a time-driven mock of every route + SSE stream. `api.ts`
  (W1-FE-SHELL) routes to it when `VITE_USE_MOCK` is true (default). `speed` compresses the demo
  wall-clock while the envelope `elapsed_ms`/ETAs/cost reflect a real ~90 s run.
- **`web/src/lib/fixtures.ts`** — four fully-populated `RunResult` fixtures (retraction catch,
  species scope mismatch, graded over-reach, abstention), each `verdict` produced by the **real**
  pipeline contracts. `SHOWCASE_RUNS` backs `GET /api/showcase`; `FIXTURES[].preset` gives
  one-click demo inputs.
- **`corpus/calibration/transcripts/debate_A27_Ce11.json`** — viz-ready adversarial-debate
  transcripts for two real cases (A27, Ce11): per-round supporter/refuter/critic text, evolving
  grade, running agreement, per-round critic usage, a compact SSE `debate_events` log, and a
  `replay` block with the reproducible current-code aggregation outcome. Raw per-round dumps are
  committed alongside under `transcripts/A27/` and `transcripts/Ce11/`.
