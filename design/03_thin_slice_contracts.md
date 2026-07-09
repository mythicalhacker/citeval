# Thin Vertical Slice — Component Contracts

The slice proves the spine: `claim + one PMID` → **C1-core** → **C2 grounding** → **C4-stub** → **C5 report**, runnable end-to-end. Its job is to surface integration/contract problems on day one and give every later component a working interface to attach to. Contracts below are the frozen interfaces; depth is layered behind them without changing them.

Verified feasibility (this environment): NCBI efetch returns MeSH `DescriptorName` + `UI`; `id.nlm.nih.gov/mesh/{UI}.json` returns authoritative tree numbers (organism = tree `B*`; age/population = tree `M01.060*`); Retraction Watch parquet resolves by `orig_pmid`.

## Invariants enforced structurally by every component (the scar tissue)

1. **Metadata overrides model.** On objective axes (retraction, species/population scope) the cited-paper metadata is authoritative. A model/text-inferred claim value never overrides a structured record; a conflict is reported as the model being wrong, not the metadata.
2. **Every axis finding carries `tier` + `provenance`.** Provenance is one of `metadata-grounded`, `text-grounded`, `model-inferred`, or a composite (e.g. `metadata-grounded (cited) + text-grounded (claim)`), plus `stub-not-adjudicated` for the axis the slice deliberately does not fake.
3. **Unverifiable axes are flagged, never fabricated.** Dose and effect-direction have no structured field → emitted under `unverifiable_axes` with the reason.
4. **The stub does not fake the hard axis.** Objective axes (retraction, species scope) are computed for real from metadata — they are legitimately objective. The graded substantive-support axis returns `NOT_ADJUDICATED (stub)`; it is only produced by the adversarial adjudication agent in the depth phase.

## C1 — Ingestion core (slice mode)

- **In:** `claim_text: str`, `cited_identifier: {type: "pmid"|"doi", value: str}`
- **Out:** `list[ClaimUnit]` where `ClaimUnit = {atomic_claim, cited_identifier, citing_source?}`
- Slice behavior: normalize + passthrough (one claim → one unit). Compound-claim splitting and manuscript/BYO-paper modes are layered later behind the same output contract.

## C2 — Resolution & grounding  (real; `grounded.json` shape)

- **In:** `cited_identifier`
- **Out:** `GroundedRecord`:
  - `identifier, title, abstract, mesh_all[]`
  - `organism_tags[]`, `population_tags[]`, `sex_tags[]` — each `{descriptor, ui, tree_numbers[], major_topic}`; split **keyed on tree numbers** (organism `B*`, population `M01.060*`), not text inference
  - `has_humans: bool`
  - `retraction: {status, retraction_watch{present,rw_record_id,reason,date}, ncbi_publication_type_flag, comments_corrections[], source_agreement, provenance="metadata-grounded"}` — **dual-sourced**: Retraction Watch registry (primary; carries reason+date) cross-checked against NCBI efetch `PublicationType` + `CommentsCorrections` RefType. Disagreement is recorded, not hidden.
  - `provenance{}` — field-level source labels; `grounding_errors[]`
- MCP-exposable later behind this exact function signature.

## C3-lite — Claim scope hint (slice placeholder for C3)

- **In:** `atomic_claim`
- **Out:** `ScopeFrame = {organism, organism_evidence[], population, population_evidence[], effect, dose_stated, provenance, tier}`
- Slice behavior: **explicit lexical markers only** (`humans/patients/clinical` → organism=Humans, provenance=`text-grounded`; `in mice/rats` → animal, `text-grounded`; otherwise `model-inferred`, low tier). The full model-based scope frame (Opus) replaces this behind the same contract in the depth phase.

## C4-stub — Adjudication (correctly-shaped, objective axes real)

- **In:** `GroundedRecord`, `ScopeFrame`
- **Out:** `Verdict = {claim, cited_identifier, overall, axis_findings[], unverifiable_axes{}, stub: true, notes[]}` where `AxisFinding = {axis, verdict, tier, provenance, detail, evidence{}}`
- Axes: `retraction` (real, metadata-grounded), `species_scope` (real; cited-side metadata-grounded, claim-side per ScopeFrame provenance; **metadata authoritative**), `population_scope` (real if determinable, else flagged), `substantive_support` (`NOT_ADJUDICATED (stub)`).

## C5 — Reporting (auditable)

- **In:** `Verdict` (+ `GroundedRecord`, `ClaimUnit` for context)
- **Out:** markdown report + machine JSON. Per-axis table shows verdict, confidence, **provenance label**, and basis (quoted claim span / MeSH tags+tree numbers / RW record + NCBI linkage). A provenance legend makes metadata-grounded vs model-inferred legible at a glance. Grounding appendix carries the raw structured evidence.

## Slice verification (built-in)

Run on `eval_set.json` cases A01 (retracted), B01 (species mismatch), C01 (supported control). Assert: A→retraction axis fires RETRACTED; B→species_scope fires SCOPE_MISMATCH; C→no objective-axis problem. Confirms the metadata-override, provenance labelling, and unverifiable-flagging behave before any depth is added.
