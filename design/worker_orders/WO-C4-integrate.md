# WO-C4-integrate — wire RB1–3 into C4 + the scorer (graded axis live)

**Owner:** a Claude Code session off `master` (the four components are merged; the
`ScopeFrame.direction` bump is already on master and the build is green — 69/69).
**Spec of record:** `design/research_briefs/results/INTEGRATION_SPEC.md` (the delta table (a)–(d)
plus the full RB1/RB2/RB3 reports in that directory). This work-order records the **manager
decisions** that scope/override that spec — where they conflict, these win.

## Objective
Turn C4 from the mock-first scaffold into the finalized adversarial adjudicator (RB1 grades, RB2
prompts, RB3 calibration), add the RB3 calibration metrics to the scorer, and wire the graded
`substantive_support` axis into the pipeline **behind a flag** — without regressing the green
objective-axis build.

## Manager decisions (authoritative)
1. **§6 governs over RB1 §D.** Scope stays orthogonal: `substantive_support` grades substance
   **holding scope constant**; a scope failure gates `overall` only, never caps the grade. Do NOT
   implement RB1's grade-capping (CONFLICT-1). Corpus graded labels follow §6.
2. **Outcome/surrogate overreach → fold into the substantive grade** (overreach / misleading). **No
   new objective axis** (CONFLICT-3).
3. **Passing/method citations → `N/A — non-substantiating`**, critic-judged; rollup + scorer treat
   it as non-graded (like abstention, distinct reason). No separate pre-classifier (CONFLICT-4).
4. **`ScopeFrame.direction` is in the contract now** (done). C3 populates it; C4's refuter uses it.
5. Adopt: RB1 scale (grade-1 = `unsupported-for-the-claim`, 0→5 order). RB2 refinements
   (evidence-first / grade-last critic, position-swap + identity-blinding of transcripts, **full-triad
   resampling with adaptive early-stopping**, ordinal/median vote, refuter schema + `routes_to`
   hard-filter dropping `rollup_not_grade` points). RB3 (N=7 full-triad, **exact modal-agreement**
   primary confidence, numeric [0,1] verbalized demoted to a weight, `tau_abstain` seed 0.5 then
   data-derived, tier cutoffs **data-derived** not 0.8/0.6, post-hoc temperature/Platt recalibration
   on the human sample; keep `MIN_VALID_ROUNDS` as a guard).

## Deliverables (own these; do NOT touch `contracts.py` further)
- **C4** (`adjudicator.py`, `prompts/`): RB1 grades incl. `N/A — non-substantiating`; RB2 prompt
  changes; full-triad resampling + early-stopping; ordinal vote; RB3 confidence/abstention (numeric
  verbalized, `tau` seed 0.5, data-derived tiers, recalibration hook that fills
  `evidence.calibration.note`); §6 evidence keys unchanged; still Opus 4.8 on every call.
- **C3** (`claim_scope.py`): populate `direction` + `direction_evidence` on both the model and
  lexical paths; extend `tests/test_claim_scope.py`.
- **scorer** (`scorer.py`): a graded-axis block — **Brier (exact + ±1-adjacent)**, **selective
  risk–coverage + AURC + risk@80%**, **quadratic-weighted kappa**, exact/±1 accuracy; caveated **ECE
  (3–4 equal-mass bins) + reliability diagram + AUROC**; **abstentions reduce coverage** (excluded
  from Brier/accuracy). Conformal adjacent-grade sets diagnostic-only.
- **Pipeline wiring:** swap `adjudicate()` in **behind a flag** (`CITEVAL_GRADED=1` / `--graded`),
  default OFF so the offline scorer stays the green stub path (16/17, no API key). Live graded path
  needs `ANTHROPIC_API_KEY`.

## Dependency (the calibration *numbers*, not the machinery)
Calibration metrics need a **6-level graded reference label** per case, which `eval_set.json` lacks
(it carries RETRACTED/SCOPE_MISMATCH/SUPPORTED). Build the machinery now; it reports numbers once the
**RB3 human spot-check** (~20–40 cases, single expert) supplies graded references via a
`substantive_grade` sidecar field (a corpus/eval sidecar — **not** a `contracts.py` change). Until
then the graded axis produces verdicts and calibration reports "pending reference labels."

**Post-corpus update (2026-07-09):** run the graded axis and draw the ~20–40 calibration sample from
the delivered **`corpus/corpus_objective.jsonl` (92 cases)**, not the 17-case fixture. **Exclude the
3 retraction-mislabelled cases** (`Bs14`, `Bp02`, `Bp03` — their cited papers 29206300 / 12531578 are
actually retracted per RetractionWatch × NCBI) from the substantive-grade sample; they belong to the
retraction axis, not a clean substantive grade. (See `outputs/scorecard/corpus_findings.md`.)

## Acceptance
- **No regression (offline, no key):** `python -m unittest discover -s tests` green;
  `python -m citeval.scorer` unchanged (16/17, graded PENDING via the stub).
- **Graded path (mocked client in tests):** critic emits an RB1 grade / `N/A` / `NOT_ENOUGH_INFO`;
  **scope never caps the grade**; direction-reversal detected via `ScopeFrame.direction`; full-triad
  self-consistency + abstention exercised; §6 evidence keys populated (C5 renders unchanged).
- **Scorer graded block** computes Brier/AURC/QWK on a small mocked graded-reference fixture;
  abstentions reduce coverage.
- **Plan-before-code:** post a BUILD PLAN and wait for manager go-ahead.

## Out of scope
`contracts.py` (frozen; `direction` already added), C2 grounding, other components' modules.
