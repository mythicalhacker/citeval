# Full Component Contracts (parallel-build backbone)

Extends the thin-slice contracts (`03_thin_slice_contracts.md`) to every component and mode.
These are the frozen interfaces the parallel Claude Code workers build against; the shared
types live in `src/citeval/contracts.py`. **Rule: a worker may change anything behind a
contract, nothing across one.** Fuzzy interfaces are the failure mode of parallel builds.

## Cross-cutting invariants (every component enforces)

- **Metadata overrides model** on objective axes (retraction, species/population scope). A
  model/text value never overturns a structured record; conflicts are recorded as the model
  being wrong.
- **Every axis finding carries `tier` + `provenance`.** Provenance atoms: `metadata-grounded`,
  `text-grounded`, `model-inferred`, `stub-not-adjudicated`; composites allowed.
- **Unverifiable axes are flagged, never fabricated.**
- **Opus 4.8 on every model call** (C3, C4, any labeler). No downgrades.
- **Verbatim guard** on every extracted claim (C1/C6a): a stored claim must be a verbatim
  substring of the citing paper's whitespace-normalized full text.
- **Raw JATS XML from EFetch** for citation-context extraction — never the plain-text connector.

---

## C1 — Ingestion & claim extraction

- **In (3 modes):** (a) `{claim_text, cited_identifier}`; (b) `{claim_text, citation_string}`
  (resolve the citation to an identifier via Crossref/PubMed); (c) `{manuscript_text | section}`
  → extract `(claim, cited_identifier)` pairs.
- **Out:** `list[ClaimUnit]` = `{atomic_claim, cited_identifier, citing_source?}`.
- **Behavior:** split compound claims into atomic assertions; for mode (c), port the proven
  JATS pipeline from `src/reference/notebook_snippets.py` (`efetch_pmc_xml_cached`,
  `find_rids_for_source`, `sentences_citing`, verbatim guard) to pull each citing sentence and
  its cited `rid`→PMID/DOI. Mode (c) is also the **bring-your-own-paper** live path.
- **Depends on:** nothing (independent track). **Parallel:** Track A.
- **Edge/verify:** compound-claim splitting must not drop the cited-id binding; every emitted
  atomic_claim passes the verbatim guard against its source (modes b/c).

## C2 — Resolution & grounding  ✅ built in slice

- **In:** `cited_identifier` (pmid|doi). **Out:** `GroundedRecord`.
- **Behavior (implemented):** efetch db=pubmed → abstract/MeSH/pub-types/CommentsCorrections;
  organism vs population split keyed on MeSH tree number (organism `B*`, population `M01.060*`)
  via batched `efetch db=mesh`; retraction = Retraction Watch registry × NCBI cross-check;
  failure-safe MeSH cache. **DOI→PMID** via esearch.
- **To finish for production:** expose `ground()` as an **MCP server** (the reuse path);
  optional NCBI Taxonomy normalization of organism tags; api_key/email/rate-limit already
  parameterized via env.
- **Depends on:** nothing. **Parallel:** Track B (mostly done).

## C3 — Claim scope parsing (replaces C3-lite)

- **In:** `atomic_claim`. **Out:** `ScopeFrame` = `{organism, organism_evidence[], population,
  population_evidence[], effect, direction, dose_stated, provenance, tier}`.
- **Behavior:** Opus parse producing the asserted scope **plus the lexical evidence span for
  each field**; provenance `model-inferred` (or `text-grounded` where an explicit marker
  exists). **C3 decides nothing on objective axes** — it only states what the claim asserts;
  C4 compares that against C2's authoritative metadata.
- **Depends on:** nothing (claim-side only). **Parallel:** Track C. Behind the same `ScopeFrame`
  contract the slice's lexical version already satisfies.
- **Verify:** on eval B-cases, organism=Humans with the correct evidence span; must **not**
  over-assert scope the wording doesn't support (the §6.1 hedged-citation trap).

## C4 — Adjudication (intellectual core)

- **In:** `GroundedRecord` + `ScopeFrame`. **Out:** `Verdict` (per-axis findings + graded
  substantive axis + confidence + provenance).
- **Behavior:** adversarial **supporter/refuter/critic** per **RB2**; substantive-support graded
  on the **RB1** scale; confidence + abstention per **RB3**. Objective axes are passed in as
  **fixed metadata facts the agents may not overturn** (metadata-override). Every support/refute
  point cites a verbatim span of the cited source.
- **Depends on:** contracts of C2 + C3 (not internals) → **built against mocks, integrated on
  landing**; consumes RB1/RB2/RB3 research outputs. **Parallel:** Track D (mock-first).
- **Verify:** refuter surfaces scope mismatch on B-cases; critic defers to metadata; controls
  pass unflagged; high-confidence verdicts more accurate than low (RB3 metric).

## C5 — Reporting

- **In:** `Verdict` (+ `GroundedRecord`, `ClaimUnit`). **Out:** markdown + machine JSON
  (slice format already implemented), extended with: the graded substantive verdict + its
  confidence and calibration note, and a live BYO-paper rendering. Grounded-vs-inferred legible
  at a glance (implemented).
- **Depends on:** C4 output contract. **Parallel:** Track A/parallel.

## C6 — Evaluation harness & corpus (the spine)

### C6a — Corpus generator (long-running, day 1)

- **In:** cited-source seeds + the C1 extraction pipeline. **Out:** two-tier corpus.
  - **Objective-axis tier (large, cheap):** retraction + species/population labels straight from
    structured metadata (Retraction Watch, MeSH tree). Scale to hundreds via OpenAlex
    (`filter=cites:`) + PMCID filter + JATS extraction + verbatim guard (~44% yield, ~72%
    ref-match from pilot — not a constraint).
  - **Graded-substantive tier:** claim-deviation labels produced by the C4 agent (no human
    annotators); a human sample validates calibration (RB3), not the whole corpus.
- **Fix the known eval-set defects (brief §6) here:** (1) separate genuine over-generalization
  from hedged/correct citation; (2) include **hard negatives** (human claim citing a human study
  that mentions animals; messy-tag but supported); (3) enforce **source diversity** (no >~20%
  one source); (4) populate the **population axis** (Infant/Child vs Adult) — currently absent;
  (5) Category-A claims must **depend on the retracted finding**, not cite it in passing.
- **Depends on:** C1 extraction only. **Parallel:** Track E (independent, starts first).

### C6b — Scorer

- **In:** full pipeline + corpus. **Out:** per-class & per-axis metrics: precision/recall on
  retraction and scope, **specificity on the hard-negative controls**, and a **calibration
  metric per RB3** on the graded axis (not just accuracy). Reliability view + selective
  risk–coverage where applicable.
- **Depends on:** all components + corpus. **Convergence point** — the proof of correctness.

---

## Frozen vs. changeable

**Frozen:** `contracts.py` type shapes; the axis names; provenance/tier presence;
metadata-override; the `ground()` signature. **Changeable behind contracts:** C3's parser
internals, C4's agent internals/prompts, C6a's selection heuristics, report styling.
Workers own the inside; the manager owns the seams.
