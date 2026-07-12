"""C4 confidence recalibration (RB3) — fit a post-hoc `a_exact -> P(correct)` Platt map.

PURE OFFLINE. Reads the graded predictions + the decider-corrected reference from disk and fits a
2-parameter logistic (Platt) map by maximum likelihood. NO model calls, NO network, NO key.

The graded axis's confidence (`a_exact`, the exact modal agreement over the self-consistency rounds)
DISCRIMINATES correctness (AUROC ~0.75) but is OVERCONFIDENT in absolute terms (raw ECE ~0.33). Platt
scaling is MONOTONIC, so it fixes ABSOLUTE calibration (ECE) ONLY: it never changes the emitted grade
and leaves discrimination (AUROC / exact-match accuracy) unchanged. Both are printed before/after to
PROVE recalibration did not touch discrimination. It does NOT fix substantive grading errors (a
confident wrong grade stays a wrong grade) — out of scope.

    python -m citeval.recalibrate \\
        --predictions outputs/scorecard/graded_predictions.jsonl \\
        --reference   corpus/calibration/graded_reference_v2.jsonl

Prints RAW vs in-sample vs leave-one-out-CV ECE (+ reliability), the AUROC-unchanged check, and the
per-`a_exact`-value accuracy table beside the fitted curve; writes `outputs/calibration_map.json`.

Wire into a LIVE graded run (opt-in, fails closed) via `load_calibration_map(path)`, whose return
value is exactly what `AdjudicationConfig.recalibration` expects. `a_exact` is a probability-scalar in
[0, 1], so this is Platt scaling on the scalar itself — NOT temperature-on-logits.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Callable, Optional, Sequence

from .prompts import ORDINAL_GRADES

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_PREDICTIONS = WORKSPACE / "outputs" / "scorecard" / "graded_predictions.jsonl"
DEFAULT_REFERENCE = WORKSPACE / "corpus" / "calibration" / "graded_reference_v2.jsonl"
DEFAULT_MAP_PATH = WORKSPACE / "outputs" / "calibration_map.json"

# The reference is the DESIGNATED TRUTH (human / decider-corrected), never model-generated — the
# whole point of an external reference is to avoid the model grading its own homework. Only grades on
# the 0-5 ordinal are fittable; NEI / N/A references are non-graded and excluded.
_ORDINAL = frozenset(ORDINAL_GRADES)
# A reference file may name its grade column differently depending on who authored it; accept the
# common spellings so a hand-authored or pipeline-emitted reference joins without a schema fixup.
_REF_GRADE_KEYS = ("grade", "ref_grade", "reference_grade", "substantive_grade", "gold_grade")


# ---------------------------------------------------------------------------------------------------
# The fail-closed identity map
# ---------------------------------------------------------------------------------------------------
def _identity(x: float) -> float:
    return x


# A *named singleton*: `load_calibration_map` returns this exact object when no fitted map is
# available, so a caller can detect "no real map" via `fn is IDENTITY` and decline to attach it —
# recalibration is NEVER auto-enabled on a missing/unfit map.
IDENTITY: Callable[[float], float] = _identity


def sigmoid(z: float) -> float:
    """Numerically stable logistic 1/(1+e^-z)."""
    if z >= 0.0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _softplus(z: float) -> float:
    """log(1 + e^z), overflow-safe (the per-example log-loss building block)."""
    if z > 35.0:
        return z
    if z < -35.0:
        return 0.0
    return math.log1p(math.exp(z))


# ---------------------------------------------------------------------------------------------------
# Data loading + join
# ---------------------------------------------------------------------------------------------------
def load_jsonl(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_reference(path: str | Path) -> dict[str, str]:
    """case_id -> reference grade. Schema-tolerant on the grade column (see `_REF_GRADE_KEYS`)."""
    ref: dict[str, str] = {}
    for r in load_jsonl(path):
        cid = r.get("case_id")
        if cid is None:
            continue
        grade = next((r[k] for k in _REF_GRADE_KEYS if r.get(k)), None)
        if grade is not None:
            ref[cid] = grade
    return ref


def build_dataset(predictions: Sequence[dict], reference: dict[str, str]) -> list[tuple[str, float, int]]:
    """Join predictions -> reference on `case_id`. Keep rows that are a GRADED prediction carrying a
    usable `a_exact` confidence AND whose reference grade is on the 0-5 ordinal. `correct` is the
    EXACT-match label used to fit calibration: `correct = (C4 grade == reference grade)`.

    Excluded (correctly, as non-graded — never counted against calibration): ABSTAINED (NEI),
    NON_SUBSTANTIATING (N/A), infra ERROR rows, and any case with no ordinal reference grade."""
    out: list[tuple[str, float, int]] = []
    for p in predictions:
        if p.get("status") != "GRADED":
            continue
        cid = p.get("case_id")
        conf = p.get("confidence")
        pred_grade = p.get("grade")
        ref_grade = reference.get(cid)
        if conf is None or ref_grade is None or ref_grade not in _ORDINAL:
            continue
        out.append((cid, float(conf), 1 if pred_grade == ref_grade else 0))
    return out


# ---------------------------------------------------------------------------------------------------
# Platt scaling — 2-parameter logistic fit by MLE (pure Newton; no scipy)
# ---------------------------------------------------------------------------------------------------
def fit_platt(xs: Sequence[float], ys: Sequence[int], *, max_iter: int = 200,
              tol: float = 1e-12) -> tuple[float, float]:
    """Fit `P(correct) = sigmoid(A*x + B)` on `(x = a_exact, y = correct)` by maximum likelihood.

    Uses Platt / Lin-Lin-Weng target smoothing — the perfectly-1/0 targets are pulled slightly inward
    to `(n_pos+1)/(n_pos+2)` and `1/(n_neg+2)` — so the fit stays finite even under (near-)separation,
    which is exactly the small-N regime this is used in. The smoothed negative log-likelihood is
    convex in `(A, B)`, so Newton with a halving line-search converges globally. Returns `(A, B)`.
    """
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    n_pos = sum(ys)
    n_neg = n - n_pos
    hi = (n_pos + 1.0) / (n_pos + 2.0)
    lo = 1.0 / (n_neg + 2.0)
    t = [hi if y == 1 else lo for y in ys]

    def nll(a: float, b: float) -> float:
        s = 0.0
        for x, ti in zip(xs, t):
            z = a * x + b
            # -[t*log p + (1-t)*log(1-p)] with p=sigmoid(z); softplus form is overflow-safe.
            s += ti * _softplus(-z) + (1.0 - ti) * _softplus(z)
        return s

    a, b = 0.0, 0.0
    prev = nll(a, b)
    for _ in range(max_iter):
        g_a = g_b = h_aa = h_ab = h_bb = 0.0
        for x, ti in zip(xs, t):
            p = sigmoid(a * x + b)
            d = p - ti
            w = p * (1.0 - p)
            g_a += d * x
            g_b += d
            h_aa += w * x * x
            h_ab += w * x
            h_bb += w
        h_aa += 1e-10  # condition the Hessian so a degenerate (all-equal-x) fold stays invertible
        h_bb += 1e-10
        det = h_aa * h_bb - h_ab * h_ab
        if abs(det) < 1e-300:
            break
        step_a = (h_bb * g_a - h_ab * g_b) / det
        step_b = (h_aa * g_b - h_ab * g_a) / det
        step = 1.0
        na, nb, cur = a, b, prev
        while step > 1e-12:
            na, nb = a - step * step_a, b - step * step_b
            cur = nll(na, nb)
            if cur <= prev:  # convex ⇒ any decrease is progress
                break
            step *= 0.5
        if prev - cur < tol:
            a, b = na, nb
            break
        a, b, prev = na, nb, cur
    return a, b


def platt_map(a: float, b: float) -> Callable[[float], float]:
    """The fitted map as a callable, clamped to [0, 1] — the shape `recalibration` expects."""
    def _m(x: float) -> float:
        return min(1.0, max(0.0, sigmoid(a * x + b)))
    return _m


def loo_predictions(xs: Sequence[float], ys: Sequence[int]) -> list[float]:
    """Leave-one-out calibrated confidence for each case: refit Platt on the other N-1 cases and
    predict the held-out case. Honest at small N — uses all data with no train/test split."""
    n = len(xs)
    preds: list[float] = []
    for i in range(n):
        xs_i = list(xs[:i]) + list(xs[i + 1:])
        ys_i = list(ys[:i]) + list(ys[i + 1:])
        a, b = fit_platt(xs_i, ys_i)
        preds.append(platt_map(a, b)(xs[i]))
    return preds


# ---------------------------------------------------------------------------------------------------
# Metrics — ECE (binned by distinct a_exact value) + AUROC
# ---------------------------------------------------------------------------------------------------
def ece_and_reliability(bin_keys: Sequence[float], confs: Sequence[float],
                        corrects: Sequence[int]) -> tuple[float, list[dict]]:
    """Expected Calibration Error + a reliability table, binned by `bin_keys` (one bin per distinct
    key). We bin by the RAW `a_exact` value — the natural bins for a discrete agreement score, and the
    convention that yields the ~0.33 raw ECE cited in the brief. Using the same bins (same cases, same
    per-bin accuracy) across raw / in-sample / LOO makes the three ECEs directly comparable: only the
    confidence column moves. ECE = Σ (n_bin/N) · |mean_conf_bin − accuracy_bin|."""
    idx: dict[float, list[int]] = defaultdict(list)
    for i, k in enumerate(bin_keys):
        idx[k].append(i)
    n_total = len(confs)
    rows: list[dict] = []
    ece = 0.0
    for k in sorted(idx):
        js = idx[k]
        n = len(js)
        acc = sum(corrects[j] for j in js) / n
        mean_conf = sum(confs[j] for j in js) / n
        gap = abs(mean_conf - acc)
        ece += (n / n_total) * gap
        rows.append({"a_exact": k, "n": n, "conf": mean_conf, "acc": acc, "gap": gap})
    return ece, rows


def auroc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Tie-aware AUROC via the rank-sum (Mann-Whitney) identity — O(n log n). Ties get 0.5 credit.
    A strictly-monotone transform of `scores` leaves the rank order (hence AUROC) IDENTICAL, which is
    the invariance we assert to prove recalibration did not change discrimination."""
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # 1-based, tie-averaged
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    sum_pos = sum(ranks[i] for i in range(len(scores)) if labels[i] == 1)
    return (sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


# ---------------------------------------------------------------------------------------------------
# Map persistence + fail-closed loader (the production wiring seam)
# ---------------------------------------------------------------------------------------------------
def _code_version() -> str:
    """Reuse the scorer's git stamp (sha[+dirty] / 'unknown'); imported lazily to keep this a leaf."""
    try:
        from .scorer import code_version
        return code_version()
    except Exception:
        return "unknown"


def write_calibration_map(path: str | Path, a: float, b: float, n_fit: int, *,
                          reference: str = "graded_reference_v2", fit_on: str = "exact-correct",
                          version: Optional[str] = None, on_date: Optional[str] = None) -> dict:
    payload = {
        "method": "platt",
        "A": a,
        "B": b,
        "n_fit": n_fit,
        "reference": reference,
        "fit_on": fit_on,
        "code_version": version if version is not None else _code_version(),
        "date": on_date or date.today().isoformat(),
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def load_calibration_map(path: str | Path = DEFAULT_MAP_PATH) -> Callable[[float], float]:
    """Return the fitted `a_exact -> P(correct)` map from `path`, or `IDENTITY` (the fail-closed
    default) when the file is absent / unreadable / not a fitted Platt map. NEVER raises. The returned
    callable is exactly what `AdjudicationConfig.recalibration` expects. `fn is IDENTITY` signals no
    real map was loaded, so a live run can decline to auto-enable recalibration on a missing/unfit
    map (see the `--recalibrate` wiring in scorer / slice_runner)."""
    try:
        payload = json.loads(Path(path).read_text())
        if payload.get("method") != "platt":
            return IDENTITY
        a = float(payload["A"])
        b = float(payload["B"])
    except Exception:
        return IDENTITY
    # Fail closed on a degenerate/corrupt fit: a non-finite param (json.loads accepts NaN/Infinity),
    # or A <= 0 — which would make the map strictly DECREASING, reversing the confidence↔correctness
    # relationship and breaking the monotone-INCREASING guarantee (higher agreement ⇒ higher P). A
    # valid recalibration map must have finite params and A > 0; anything else ⇒ no recalibration.
    if not (math.isfinite(a) and math.isfinite(b) and a > 0.0):
        return IDENTITY
    return platt_map(a, b)


def resolve_recalibration(enabled: bool, map_path: str | Path = DEFAULT_MAP_PATH
                          ) -> tuple[Optional[Callable[[float], float]], str]:
    """Centralized, fail-closed opt-in for a LIVE graded run. Returns `(recalibration_fn_or_None,
    note)`:

    - `enabled=False` (default)             -> `(None, "")`         : recalibration OFF, note empty.
    - enabled but no fitted map at `map_path` -> `(None, <warning>)` : NEVER auto-enable on a
      missing/unfit map — run WITHOUT recalibration and say so.
    - enabled and a real Platt map loads    -> `(fn, <on-note>)`    : attach the fitted map.

    The caller attaches `fn` to `AdjudicationConfig.recalibration` (identity/None ⇒ empty
    `evidence.calibration.note`; a real fn ⇒ the calibrated confidence is written to that note)."""
    if not enabled:
        return None, ""
    fn = load_calibration_map(map_path)
    if fn is IDENTITY:
        return None, (f"[recalibrate] requested but no fitted Platt map at {map_path} — running "
                      "WITHOUT recalibration (fails closed; run `python -m citeval.recalibrate` first)")
    return fn, f"[recalibrate] ON — applying fitted map from {map_path}"


# ---------------------------------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------------------------------
def _fmt_reliability(rows: Sequence[dict], conf_label: str) -> list[str]:
    out = [f"  {'a_exact':>8}  {'n':>3}  {conf_label:>10}  {'accuracy':>8}  {'|gap|':>6}"]
    for r in rows:
        out.append(f"  {r['a_exact']:>8.4f}  {r['n']:>3d}  {r['conf']:>10.4f}  "
                   f"{r['acc']:>8.4f}  {r['gap']:>6.4f}")
    return out


def fit_report(dataset: Sequence[tuple[str, float, int]], *, reference_name: str,
               version: str) -> tuple[str, dict]:
    """Fit Platt on the joined dataset and render the full offline report. Returns (text, summary)."""
    xs = [d[1] for d in dataset]
    ys = [d[2] for d in dataset]
    n = len(dataset)

    a, b = fit_platt(xs, ys)
    fn = platt_map(a, b)
    insample = [fn(x) for x in xs]
    loo = loo_predictions(xs, ys)

    keys = [round(x, 6) for x in xs]
    raw_ece, raw_rel = ece_and_reliability(keys, xs, ys)
    ins_ece, ins_rel = ece_and_reliability(keys, insample, ys)
    loo_ece, loo_rel = ece_and_reliability(keys, loo, ys)

    auroc_raw = auroc(xs, ys)
    auroc_recal = auroc(insample, ys)
    exact_acc = sum(ys) / n
    auroc_unchanged = math.isclose(auroc_raw, auroc_recal, rel_tol=0.0, abs_tol=1e-12)

    # Per-a_exact-value table: empirical accuracy beside the fitted curve, so the fit is inspectable.
    per_value: dict[float, list[int]] = defaultdict(list)
    per_value_loo: dict[float, list[float]] = defaultdict(list)
    for (x, y), lp in zip(zip(xs, ys), loo):
        per_value[round(x, 6)].append(y)
        per_value_loo[round(x, 6)].append(lp)

    L: list[str] = []
    L.append("=" * 84)
    L.append("C4 CONFIDENCE RECALIBRATION — Platt fit  P(correct) = sigmoid(A·a_exact + B)")
    L.append("=" * 84)
    L.append(f"code_version : {version}")
    L.append(f"reference    : {reference_name} (decider-corrected; human truth, not model-generated)")
    L.append(f"fit_on       : exact-correct   (correct = C4 grade == reference grade, EXACT)")
    L.append(f"n_fit        : {n} graded cases with an ordinal reference grade")
    L.append(f"fitted params: A = {a:.6f}   B = {b:.6f}")
    L.append("")
    if a > 0.0:
        L.append("Monotonicity: A > 0 ⇒ the map is strictly increasing, so it CANNOT change the")
        L.append("emitted grade and CANNOT change discrimination — it only rescales confidence.")
    else:
        L.append(f"WARNING: A = {a:.6f} ≤ 0 ⇒ the fit is NON-increasing (degenerate on this data). "
                 "load_calibration_map REFUSES such a map (fails closed → identity); do NOT ship it.")
    L.append("")
    L.append("-" * 84)
    L.append("[1] RAW calibration (confidence = a_exact, as emitted today)")
    L.append(f"    ECE = {raw_ece:.4f}")
    L.extend(_fmt_reliability(raw_rel, "mean_conf"))
    L.append("")
    L.append("-" * 84)
    L.append("[2] RECALIBRATED — in-sample (confidence = Platt(a_exact), fit on ALL n)")
    L.append(f"    ECE = {ins_ece:.4f}   (in-sample OVERSTATES calibration at small n — see [3])")
    L.extend(_fmt_reliability(ins_rel, "cal_conf"))
    L.append("")
    L.append("-" * 84)
    L.append("[3] RECALIBRATED — leave-one-out CV  <<< HEADLINE (honest) number")
    L.append(f"    ECE = {loo_ece:.4f}   (each case scored by a Platt map refit WITHOUT it)")
    L.extend(_fmt_reliability(loo_rel, "loo_conf"))
    L.append("")
    L.append("-" * 84)
    L.append("[4] DISCRIMINATION unchanged (proof the monotonic map did not touch ranking / grades)")
    L.append(f"    AUROC  raw = {auroc_raw:.6f}   recalibrated = {auroc_recal:.6f}   "
             f"{'IDENTICAL ✓' if auroc_unchanged else 'CHANGED ✗ (unexpected!)'}")
    L.append(f"    exact-match grade accuracy = {exact_acc:.4f}  (UNCHANGED — recalibration never")
    L.append("      touches the grade; it only rescales the confidence attached to it)")
    L.append("")
    L.append("-" * 84)
    L.append("[5] Per-a_exact-value fit (empirical accuracy beside the fitted curve)")
    L.append(f"  {'a_exact':>8}  {'n':>3}  {'emp_acc':>8}  {'fitted_P':>8}  {'mean_LOO_P':>10}")
    for k in sorted(per_value):
        yy = per_value[k]
        emp = sum(yy) / len(yy)
        L.append(f"  {k:>8.4f}  {len(yy):>3d}  {emp:>8.4f}  {fn(k):>8.4f}  "
                 f"{sum(per_value_loo[k]) / len(per_value_loo[k]):>10.4f}")
    L.append("=" * 84)

    summary = {
        "A": a, "B": b, "n_fit": n,
        "raw_ece": raw_ece, "insample_ece": ins_ece, "loo_ece": loo_ece,
        "auroc_raw": auroc_raw, "auroc_recal": auroc_recal, "auroc_unchanged": auroc_unchanged,
        "exact_accuracy": exact_acc,
    }
    return "\n".join(L), summary


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Fit a Platt a_exact->P(correct) recalibration map from graded predictions + a "
                    "decider-corrected reference. PURE OFFLINE — no model calls, no key, no network.")
    ap.add_argument("--predictions", default=str(DEFAULT_PREDICTIONS),
                    help="graded_predictions.jsonl (a_exact confidence + C4 grade per case)")
    ap.add_argument("--reference", default=str(DEFAULT_REFERENCE),
                    help="decider-corrected reference jsonl keyed by case_id (the designated truth)")
    ap.add_argument("--out", default=str(DEFAULT_MAP_PATH), help="where to write calibration_map.json")
    ap.add_argument("--reference-name", default="graded_reference_v2",
                    help="reference label stamped into the map")
    args = ap.parse_args()

    version = _code_version()
    print(f"[recalibrate] code_version {version} — OFFLINE (no model calls / no key / no network)")

    predictions = load_jsonl(args.predictions)
    reference = load_reference(args.reference)
    dataset = build_dataset(predictions, reference)
    if not dataset:
        print("[recalibrate] no GRADED prediction joined to an ordinal reference grade — nothing to "
              "fit. Check --predictions / --reference.")
        return

    text, summary = fit_report(dataset, reference_name=args.reference_name, version=version)
    print(text)
    payload = write_calibration_map(args.out, summary["A"], summary["B"], summary["n_fit"],
                                    reference=args.reference_name, version=version)
    print(f"\n[calibration map written] {args.out}")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
