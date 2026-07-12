# ext-45 held-out report — live Opus-C3 scope + independent tiebreak

Held-out out-of-sample set (`corpus_cal_ext.jsonl`, 45 cases), reported SEPARATELY from the cal30 gate.
Objective labels are metadata-grounded (triple-confirmed retraction; MeSH-derived scope). The
substantive reference (`graded_reference_ext.jsonl`) is a **single-pass blind claude-science grade**
(21/45 abstract-only) — NOT decider-adjudicated. Code: `8aa0ff6` (C4 direction-reversal fix on master).
The cal30 `gate_thresholds.json` / baseline were **not touched**.

## Part A — objective axes under LIVE Opus-C3 (`--objective-only`, C1→C2→C3, no C4)

| axis | Opus-4.8 C3 | lexical C3 |
|---|---|---|
| retraction P / R / F | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| scope precision / **recall** / spec | 0.83 / **0.294** (5/17) / 0.94 | 1.00 / **0.059** (1/17) / 1.00 |
| control specificity | 15 / 16 | 16 / 16 |
| overall objective accuracy | 32 / 45 | 29 / 45 |

**Retraction generalizes perfectly** out-of-sample (P/R/F = 1.0; retraction does not depend on C3).

**Scope recall out-of-sample = 0.294 under live Opus-C3** — 5× the lexical fallback (0.059), catching
4 species over-generalizations lexical misses (Bs01, Bs03, Bs06, Bs09) at the cost of 1 control
false-positive (precision 0.83 vs lexical 1.0). But it is still **low**: Opus-C3 misses 12/17 scope
mismatches — all 4 population cases (Bp01–04: it extracts the claim organism but not the age/population
scope → `population = NOT_ASSESSED`) and the implicit species over-generalizations where the claim states
a general biological fact with no explicit "human" marker (Bs02/04/05/07/08/10/11/12).

**Correction to the earlier read:** the previously-reported ext scope recall (~0.235) was **already the
Opus-C3 number**, not lexical — the scorecard's "lexical stub" note is a *hardcoded* string
(`scorer.py:1013`) that does not reflect the C3 path actually used. Real lexical recall is 0.059. The
in-domain cal30 scope recall of 1.0 is propped up by `regen_results._LIVE_SCOPE_OVERRIDES` on 2 cases
(Bs22/Bp01); the honest out-of-sample number is **~0.29**. This is a C3 limitation (WO-C3), independent
of the C4 direction-reversal fix.

Per-case objective verdicts: `corpus/calibration/results_ext_objective.jsonl` (c3_scope_path = opus-4.8).

## Part B — blind independent tiebreak on the 6 confident C4↔ext-ref disagreements

A single-pass Opus-4.8 grade reading ONLY the claim + the cited paper's full text, scope held constant
(§6), NOT shown C4's grade or the ext reference. Tiebreaker only — `graded_reference_ext.jsonl` unchanged.
Raw grades: `corpus/calibration/ext_tiebreak_6.json`.

| case | C4 grade | ext-ref grade | independent grade | sides with |
|---|---|---|---|---|
| Ce03 | fully-supported | unsupported-for-the-claim | N/A — non-substantiating | ext-ref (C4 over-generous) |
| A11  | supported-with-overreach | unsupported-for-the-claim | supported-with-overreach | **C4** (ext-ref harsh) |
| Bs03 | supported-with-overreach | unsupported-for-the-claim | partially-supported | **C4** (ext-ref harsh) |
| A05  | partially-supported | unsupported-for-the-claim | partially-supported | **C4** (ext-ref harsh) |
| Bp03 | unsupported-for-the-claim | partially-supported | N/A — non-substantiating | **C4** (ext-ref over-generous) |
| Bs07 | partially-supported | contradicted | contradicted | ext-ref (C4 missed it) |

**Independent tiebreaker sides with C4 on 4/6, with the ext-ref on 2/6.**

- **4/6 the ext single-pass reference was the wrong/harsh side** (A11, A05, Bs03 all graded "unsupported"
  where the paper genuinely reports overreaching/partial support; Bp03 the ext-ref was over-generous).
  This confirms the ext substantive grades are **not load-bearing** without decider adjudication.
- **2/6 are genuine C4 residual errors:**
  - **Bs07** — C4 graded partially-supported, but the paper shows **HDL *decreased*** (opposite the
    claim of increased HDL): a real contradiction the direction-reversal fix did **not** catch (it *did*
    catch the other genuine contradiction, Ce08 → contradicted). Honest limitation: the fix grounds the
    *contradicted* grade but does not guarantee catching every direction reversal.
  - **Ce03** — C4 graded fully-supported @1.0; the paper is a background/safety appraisal that does not
    substantiate the specific immunological-mechanism claim (independent: non-substantiating). C4 was
    over-confident here.

(The two N/A — non-substantiating independent verdicts are off the ordinal scale; "sides with" maps them
by direction — does the paper substantiate the claim or not.)

## Bottom line
- **Opus-C3 ext scope recall = 0.294** (5/17), vs lexical 0.059; retraction P/R/F = 1.0. Scope is the
  honest out-of-sample weak point (C3/WO-C3), not the C4 fix.
- **Tiebreak: 4/6 sided with C4, 2/6 with the ext-ref.** The single-pass ext reference is often too harsh;
  C4 has 2 residual errors (a missed contradiction Bs07, an over-generous Ce03).
