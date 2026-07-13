"""citeval_api — the HTTP/SSE surface over the read-only `citeval` pipeline.

W0-CONTRACTS ships the FROZEN pieces of this package: `contracts` (Pydantic wire types) and
`pricing` (the cost model). Later sprint sessions add, in their own files, `telemetry`
(W1-TELEMETRY), `events`/`progress` (W1-EVENTS), `runner` (W2-RUNNER), `batch` (W2-BATCH), and
`app`/main (W2-SERVER). Nothing here edits `src/citeval/*`; it imports the pipeline read-only
through the two existing seams (`adjudicate(..., client=)` and `config.on_round`).

The authoritative interface description is `docs/api_contract.md`.
"""

__all__: list[str] = []
