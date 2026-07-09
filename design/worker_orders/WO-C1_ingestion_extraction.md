# WO-C1 — Ingestion & claim extraction

**Owner:** Worker (Track A, independent). **Depends on:** nothing across a contract. Read
`00_INDEX.md` (shared invariants) and follow `src/citeval/` as the reference pattern.

## Objective

Build `src/citeval/ingestion.py` exposing `ingest(request) -> list[ClaimUnit]` for all three
input modes, so every downstream component receives the same normalized `ClaimUnit` list.

## Contract

- **In (one of):**
  - `{mode:"claim_pmid", claim_text, cited_identifier}`
  - `{mode:"claim_citation", claim_text, citation_string}` — resolve the citation string to a
    PMID/DOI (Crossref REST `works?query.bibliographic=` or PubMed esearch).
  - `{mode:"manuscript", pmcid|jats_path|text}` — extract `(claim, cited_identifier)` pairs from
    a citing paper.
- **Out:** `list[ClaimUnit]` (`contracts.ClaimUnit`), each with `atomic_claim`,
  `cited_identifier`, and `citing_source` provenance where known.

## Behavior

- **Compound-claim splitting:** split a sentence asserting multiple findings into atomic claims,
  preserving each one's cited identifier binding.
- **Manuscript mode:** port the proven JATS pipeline from
  `src/reference/notebook_snippets.py` — `efetch_pmc_xml_cached` (fetch raw JATS), the
  `<ref>`↔`<pub-id>` matcher (`find_rids_for_source`), the in-text `<xref rid>` sentence
  extractor (`sentences_citing`), and the display cleaner. Re-point any `host.mcp(...)` calls to
  direct NCBI E-utilities / OpenAlex REST (the snippets flag each with a TODO).
- **Verbatim guard (mandatory):** every emitted `atomic_claim` for modes b/c must be a verbatim
  substring of the citing paper's whitespace-normalized full-text body; reject otherwise.

## Deliverables

- `src/citeval/ingestion.py` with `ingest()` + helpers; reuse `contracts.py` types.
- `tests/test_ingestion.py`.

## Acceptance criteria

- Mode a: passthrough → one `ClaimUnit`.
- Mode b: resolves at least the eval-set DOIs to the correct PMID.
- Mode c: on a PMC citing paper from `eval_set.json` (use a `claim_source_pmcid`), extracts the
  known citing sentence and links it to the correct `cited_pmid` via the JATS `rid`↔`pub-id`
  match; every extracted claim passes the verbatim guard.
- Never emits a claim that fails the verbatim guard.

## Out of scope / do not touch

Grounding (C2), scope parsing (C3), `contracts.py`. Do not reintroduce the plain-text full-text
connector.
