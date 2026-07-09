# Claude Code Worker Orders — dispatch index

Each work-order is **self-contained** and builds against the frozen contracts in
`src/citeval/contracts.py`. A worker owns everything *behind* its contract and must not change
anything *across* one. Follow the thin slice (`src/citeval/`) as the reference pattern — it
already implements C2/C5 and the invariants.

## Ownership map

| Track | Component | Owner | Status |
|---|---|---|---|
| A | C1 Ingestion & extraction | **Worker** (WO-C1) | ready to dispatch |
| C | C3 Claim scope parser (Opus) | **Worker** (WO-C3) | ready to dispatch |
| — | C5 Reporting (extend) | **Worker** (WO-C5) | ready to dispatch |
| D | C4 Adjudication | **Worker** (WO-C4) | mock-first; finalize when RB1–3 land |
| E | C6a Corpus generator (harvest) | **Worker — Claude Science** (WO-C6a) | ready to dispatch |
| — | C6b Scorer | **Manager (me)** | built |
| B | C2 Grounding | **Manager (me)** | built; MCP-exposure pending |

Dispatch WO-C1, WO-C3, WO-C5, and WO-C6a immediately (independent, share only data contracts);
WO-C6a runs in **Claude Science**, which has the PubMed/OpenAlex connectors natively. WO-C4 runs
in parallel against mocked C2/C3 outputs and integrates when they land. I own the corpus *design*
(the WO-C6a rubric), the scorer (built), and integration — the scaled harvest runs in the Claude
Science session and comes back here to be scored.

## Shared invariants (every worker enforces — non-negotiable)

1. **Metadata overrides model** on objective axes (retraction, species/population scope).
2. **Every axis finding carries `tier` + `provenance`**; unverifiable axes flagged, not fabricated.
3. **Opus 4.8 on every model call.** No cheaper/faster model anywhere.
4. **Verbatim guard**: any stored claim must be a verbatim substring of the citing paper's
   whitespace-normalized full text.
5. **Raw JATS XML from EFetch** for citation context — never the plain-text connector (it strips
   `<xref>` markers).
6. Do **not** edit `contracts.py`, other components' internals, or the `ground()` signature.

## Definition of done (every worker)

- Implements the stated contract exactly (types from `contracts.py`).
- Unit tests pass, including the component's acceptance criteria below.
- Runs against the 17-case `eval_set.json` where applicable and reproduces the expected behavior.
- No cross-contract changes; integrates without touching the seam.

## Integration

Workers land their module under `src/citeval/`. I integrate against the live C2 grounding + the
corpus, then run the scorer (C6b). The scorer is the convergence point and the proof.
