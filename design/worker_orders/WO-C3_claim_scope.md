# WO-C3 — Claim scope parser (Opus)

**Owner:** Worker (Track C, independent). Read `00_INDEX.md`. Replaces the slice's lexical
`claim_scope.py` **behind the same `ScopeFrame` contract**.

## Objective

Upgrade `src/citeval/claim_scope.py` so `parse_claim_scope(atomic_claim) -> ScopeFrame` uses an
**Opus 4.8** call to extract the claim's asserted scope with an evidence span per field.

## Contract

- **In:** `atomic_claim: str`. **Out:** `contracts.ScopeFrame` =
  `{organism, organism_evidence[], population, population_evidence[], effect, dose_stated,
  provenance, tier}`. (`direction` is **deferred** — not in the frozen contract yet; do not add it.)
- `provenance` = `text-grounded` where an explicit marker exists, else `model-inferred`; `tier`
  reflects confidence.

## Behavior + hard rules

- The parser states **only what the claim asserts** — it must **not** decide any objective axis
  or compare against the cited paper (that is C4's job against C2's metadata).
- **Do not over-assert scope the wording doesn't support** (the §6.1 trap): a claim that says
  "in mice" → organism `Mice`, NOT `Humans`; a hedged claim ("whether this holds in humans is
  unknown") → do not assert `Humans` as the claim's scope.
- **Infer implicit asserted scope, not just explicit markers:** a claim asserting therapeutic /
  clinical relevance ("promote the recovery of motor function", "can be targeted for therapeutic
  purposes") implies human/clinical scope even without the words "human"/"patient" (the **B05**
  case) → emit `organism="Humans"` with `model-inferred` provenance and a confidence tier. This is
  in tension with the no-over-assert rule and the boundary is a judgement: a mechanism-only
  description with no relevance claim gets no human scope; when genuinely unsure, **lower the tier
  rather than force the call**. (This is what lets the metadata-grounded `species_scope` axis catch
  B05 downstream — see CONTEXT_PACK §6.)
- Every populated field carries its verbatim evidence span from the claim.
- Keep the lexical implementation as a no-API fallback (`parse_claim_scope_lexical`) selected when
  `ANTHROPIC_API_KEY` is absent, so the pipeline still runs offline.

## Deliverables

- Updated `src/citeval/claim_scope.py` (Opus path + lexical fallback), Opus 4.8 model id.
- `tests/test_claim_scope.py` with fixtures (no live API in CI: mock the model response).

## Acceptance criteria

- On eval B-cases: `organism == "Humans"` with a correct evidence span.
- On a constructed correctly-scoped claim ("resveratrol extends lifespan **in mice**"):
  `organism == "Mice"`, not `Humans`.
- On a hedged claim: does not assert human scope.
- On **B05** (claim asserts "promote the recovery of motor function after spinal cord injury" with
  no explicit human word): `organism == "Humans"` with `model-inferred` provenance + an appropriate
  tier, so `species_scope` flags the mismatch downstream.
- Output validates against `ScopeFrame`; provenance/tier populated.

## Out of scope / do not touch

Grounding, adjudication, `contracts.py`. No objective-axis decisions here.
