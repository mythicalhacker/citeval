"""The eval GATE (req #3) — compare an offline scorecard to versioned, tracked thresholds and
decide PASS/FAIL. PURE: takes a scorecard dict (from `scorer.score_from_predictions`) + a
`gate_thresholds.json`; no model, no network, no key.

Two kinds of check, both feeding the exit code:
  1. **Threshold floors/ceilings** — each metric vs a hard `{min}` / `{max}` bar (seeded from the
     cal30 baseline WITH margin). A miss is a breach.
  2. **Zero objective regressions** — every objective axis (retraction/scope P·R·specificity,
     control specificity) must hold at or above its BASELINE. A drop below baseline is a breach even
     when it still clears the floor (the strict guard the work-order asks for).

GAPS additionally surface (visible, but a breach only when noted): coverage drop, recal-LOO ECE
rise, and confident-wrong cases (high a_exact but grade ≠ reference) — a NEW confident-wrong case
(absent from the baseline set) is a breach; a known one is reported, not fatal.

    from citeval import gate
    gr = gate.evaluate_gate(res, gate.load_thresholds())
    print(gate.render_gate(gr))
    sys.exit(gr.exit_code)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .prompts import ORDINAL_INDEX

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_THRESHOLDS_PATH = WORKSPACE / "corpus" / "calibration" / "gate_thresholds.json"

_EPS = 1e-9  # float-noise tolerance: 8/10 must read as == the stored 0.8 baseline, not a regression.

# The objective axes that must never regress below baseline ("zero objective regressions").
OBJECTIVE_METRICS = ("retraction_precision", "retraction_recall", "retraction_specificity",
                     "scope_precision", "scope_recall", "scope_specificity", "control_specificity")


# ---------------------------------------------------------------------------------------------------
def load_thresholds(path: str | Path = DEFAULT_THRESHOLDS_PATH) -> dict:
    """Load the versioned thresholds file. Raises (loudly) if absent/corrupt — a missing gate config
    is an operator error, not something to silently pass."""
    return json.loads(Path(path).read_text())


def extract_metrics(res: dict) -> dict:
    """Flatten the scorecard dict into the gate's metric namespace (name -> value or None)."""
    rp, rr, rs = res["retraction"]["prf"]
    sp, sr, ss = res["scope"]["prf"]
    clean, nctrl = res.get("control_specificity", (0, 0))
    cal = res.get("calibration") or {}
    recal = res.get("recal") or {}
    return {
        "retraction_precision": rp, "retraction_recall": rr, "retraction_specificity": rs,
        "scope_precision": sp, "scope_recall": sr, "scope_specificity": ss,
        "control_specificity": (clean / nctrl) if nctrl else None,
        "graded_exact": cal.get("accuracy_exact"),
        "graded_adjacent": cal.get("accuracy_adjacent"),
        "qwk": cal.get("qwk"),
        "coverage": cal.get("coverage"),
        "recal_loo_ece": recal.get("loo_ece"),
        "auroc": recal.get("auroc"),
    }


def confident_wrong_cases(res: dict, tau: float) -> list[dict]:
    """GRADED cases the model was CONFIDENT on (a_exact ≥ tau) yet got WRONG (grade ≠ ordinal
    reference). These are the calibration danger cases — surfaced every run."""
    out = []
    for r in res.get("graded_records", []):
        conf = r.get("confidence")
        ref = r.get("ref_grade")
        if (r.get("status") == "GRADED" and isinstance(conf, (int, float)) and conf >= tau
                and ref in ORDINAL_INDEX and r.get("grade") != ref):
            out.append({"case_id": r.get("case_id"), "grade": r.get("grade"),
                        "ref_grade": ref, "confidence": conf})
    return sorted(out, key=lambda d: (-(d["confidence"] or 0), d["case_id"] or ""))


@dataclass
class Check:
    metric: str
    value: float | None
    bound: float
    op: str          # "min" (value ≥ bound) or "max" (value ≤ bound)
    passed: bool
    note: str = ""


@dataclass
class Gap:
    kind: str
    detail: str
    breach: bool


@dataclass
class GateResult:
    checks: list[Check]
    gaps: list[Gap]
    confident_wrong: list[dict]
    metrics: dict
    reference_version: str = ""
    thresholds_version: str = ""
    breaches: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.breaches

    @property
    def exit_code(self) -> int:
        return 0 if self.passed else 1


def _cmp(value: float | None, bound: float, op: str) -> bool:
    if value is None:
        return False                      # a metric we cannot compute cannot pass (fail closed)
    return value >= bound - _EPS if op == "min" else value <= bound + _EPS


def evaluate_gate(res: dict, thresholds: dict) -> GateResult:
    """Compare a scorecard `res` to `thresholds`; return a GateResult (checks + gaps + breaches)."""
    metrics = extract_metrics(res)
    baseline = thresholds.get("baseline", {})
    tau = thresholds.get("confident_wrong_tau", 0.85)
    breaches: list[str] = []

    # 1) Threshold floors / ceilings.
    checks: list[Check] = []
    for metric, spec in thresholds.get("thresholds", {}).items():
        op = "min" if "min" in spec else "max"
        bound = spec.get("min", spec.get("max"))
        val = metrics.get(metric)
        ok = _cmp(val, bound, op)
        checks.append(Check(metric, val, bound, op, ok, note=spec.get("_note", "")))
        if not ok:
            shown = "n/a" if val is None else f"{val:.4f}"
            breaches.append(f"threshold: {metric}={shown} fails {'≥' if op == 'min' else '≤'} {bound}")

    gaps: list[Gap] = []

    # 2) Zero objective regressions (below baseline == breach, even if it clears the floor).
    regressions = []
    for metric in OBJECTIVE_METRICS:
        base = baseline.get(metric)
        val = metrics.get(metric)
        if base is None:
            continue
        if val is None or val < base - _EPS:
            shown = "n/a" if val is None else f"{val:.4f}"
            regressions.append(f"{metric}: baseline {base:.4f} → now {shown}")
    if regressions:
        for r in regressions:
            gaps.append(Gap("objective-regression", r, breach=True))
        breaches.append(f"objective regression(s): {len(regressions)}")
    else:
        gaps.append(Gap("objective-regression", "none — all objective axes hold at/above baseline",
                        breach=False))

    # 3) Coverage drop (listed always; breach only when the threshold floor was actually missed —
    #    the floor has margin below baseline precisely so an expected small drop is not fatal).
    cov, cov_base = metrics.get("coverage"), baseline.get("coverage")
    if cov is not None and cov_base is not None:
        dropped = cov < cov_base - _EPS
        gaps.append(Gap("coverage", f"coverage {cov:.4f} vs baseline {cov_base:.4f}"
                        + (" — DROP" if dropped else " — no drop"), breach=False))

    # 4) Recal-LOO ECE rise (same policy: listed; the ≤ threshold check owns the breach).
    ece, ece_base = metrics.get("recal_loo_ece"), baseline.get("recal_loo_ece")
    if ece is not None and ece_base is not None:
        rose = ece > ece_base + _EPS
        gaps.append(Gap("ece", f"recal-LOO ECE {ece:.4f} vs baseline {ece_base:.4f}"
                        + (" — RISE" if rose else " — no rise"), breach=False))

    # 5) Confident-wrong cases; a NEW one (not in the baseline set) is a breach.
    cw = confident_wrong_cases(res, tau)
    baseline_cw = set(baseline.get("confident_wrong_case_ids", []))
    new_cw = [c for c in cw if c["case_id"] not in baseline_cw]
    if cw:
        detail = ", ".join(f"{c['case_id']}[{c['grade']}≠{c['ref_grade']}@{c['confidence']:.2f}]"
                           for c in cw)
        gaps.append(Gap("confident-wrong", f"a_exact≥{tau}: {detail}  "
                        f"({len(cw)} total, {len(new_cw)} new vs baseline)", breach=bool(new_cw)))
    else:
        gaps.append(Gap("confident-wrong", f"none at a_exact≥{tau}", breach=False))
    if new_cw:
        breaches.append(f"new confident-wrong case(s): {', '.join(c['case_id'] for c in new_cw)}")

    return GateResult(checks=checks, gaps=gaps, confident_wrong=cw, metrics=metrics,
                      reference_version=thresholds.get("reference_version", ""),
                      thresholds_version=str(thresholds.get("thresholds_version", "")),
                      breaches=breaches)


# ---------------------------------------------------------------------------------------------------
def _fv(x) -> str:
    return "  n/a " if x is None else f"{x:6.4f}"


def render_gate(gr: GateResult) -> str:
    L: list[str] = []
    L.append("=" * 72)
    L.append("EVAL GATE  —  offline, deterministic  (metric | value | threshold | status)")
    L.append(f"reference: {gr.reference_version or '?'}   thresholds: v{gr.thresholds_version or '?'}")
    L.append("=" * 72)
    L.append(f"{'metric':<24}{'value':>9}   {'threshold':<12}{'status'}")
    L.append("-" * 72)
    for c in gr.checks:
        thr = f"{'≥' if c.op == 'min' else '≤'} {c.bound:g}"
        L.append(f"{c.metric:<24}{_fv(c.value):>9}   {thr:<12}{'PASS' if c.passed else 'FAIL'}")
    # AUROC is reported but ungated (no threshold in the work-order).
    if gr.metrics.get("auroc") is not None:
        L.append(f"{'auroc':<24}{_fv(gr.metrics['auroc']):>9}   {'(info)':<12}—")
    L.append("")
    L.append("GAPS")
    for g in gr.gaps:
        mark = "✗" if g.breach else "·"
        L.append(f"  [{mark}] {g.kind}: {g.detail}")
    L.append("")
    if gr.passed:
        L.append(f"GATE: PASS  (0 breaches)")
    else:
        L.append(f"GATE: FAIL  ({len(gr.breaches)} breach(es))")
        for b in gr.breaches:
            L.append(f"   ✗ {b}")
    L.append("=" * 72)
    return "\n".join(L) + "\n"
