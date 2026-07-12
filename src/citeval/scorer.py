"""C6b — Scorer / harness (objective axes + RB3 graded-axis calibration).

Runs the pipeline over a corpus and reports per-axis + per-class metrics: retraction
detection, species/population scope detection, and specificity on controls. This is the
proof-of-correctness artifact — measured, not asserted.

The graded `substantive_support` axis (RB3) is scored when the graded C4 is run (`--graded`,
needs a key) AND a **human** graded reference label is supplied per case (the anti-circularity
guard — the reference is NEVER model-generated). The reference arrives as a `substantive_grade`
sidecar: either a per-case field or a `--graded-reference` file keyed by `case_id`. Until
references exist, the calibration block reports "pending reference labels"; offline (stub, no
key) it stays PENDING and the objective scorecard is unchanged (16/17).

    python -m citeval.scorer                              # objective scorecard over eval_set.json
    python -m citeval.scorer --corpus corpus/corpus_objective.jsonl
    python -m citeval.scorer --graded --graded-reference labels.jsonl   # live graded + calibration
    python -m citeval.scorer --graded --limit 3 -v       # 3-case smoke, per-round progress
    python -m citeval.scorer --emit-calibration-sample 30 --corpus corpus/corpus_objective.jsonl

Observability + resumability (§D). A graded run appends one JSON line per case to
`<out>/graded_predictions.jsonl` as each case completes (flushed), so `tail -f` shows cases
landing live and a Ctrl-C/crash never loses completed cases — the next run SKIPS case_ids already
present (resume) unless `--fresh`. `--limit N` scores only the first N cases (smoke). Per-case
start/finish progress prints to stderr; `-v`/`CITEVAL_PROGRESS=1` adds a line per triad round.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

from .adjudicator import AdjudicationConfig
from .prompts import NON_SUBSTANTIATING, NOT_ENOUGH_INFO, ORDINAL_GRADES, ORDINAL_INDEX
from .slice_runner import EVAL_PATH, graded_enabled, run_slice

WORKSPACE = Path(__file__).resolve().parents[2]
OUT_DIR = WORKSPACE / "outputs" / "scorecard"
# Durable, COMPLETE-verdict per-case files (one JSON line per case: objective axes + graded
# prediction + code_version) — the deterministic input for offline scoring (`--from-predictions`).
# Ephemeral / gitignored; the committed copy the gate runs against lives in corpus/calibration/.
RESULTS_DIR = WORKSPACE / "outputs" / "results"
CORPUS_OBJECTIVE = WORKSPACE / "corpus" / "corpus_objective.jsonl"

# The 3 corpus cases whose cited papers are actually retracted (per RetractionWatch × NCBI)
# but are labelled SCOPE_MISMATCH — they belong to the retraction axis, not a clean substantive
# grade, so they are excluded from the calibration sample (WO-C4-integrate post-corpus update).
RETRACTION_MISLABELS = ("Bs14", "Bp02", "Bp03")


# ==================================================================================
# Version stamp (WO-C4 §4 stale-binary guard): which code produced this scorecard / prediction.
# ==================================================================================
def _git(*args: str) -> str:
    """Run `git <args>` at the repo root; '' on any failure. cwd is pinned to WORKSPACE so the
    stamp is stable regardless of where python was launched from (e.g. `cd src`)."""
    return subprocess.run(["git", *args], cwd=WORKSPACE, capture_output=True, text=True,
                          timeout=5).stdout.strip()


def code_version() -> str:
    """Short git SHA plus a `+dirty` flag when the working tree has uncommitted changes; 'unknown'
    if git is unavailable or this is not a repo. Stamped into the scorecard header and every
    graded_predictions.jsonl line so a run is always traceable to the exact code that produced it —
    no more 'is this scorecard from the fixed binary or the old one?' ambiguity."""
    try:
        sha = _git("rev-parse", "--short", "HEAD")
        if not sha:
            return "unknown"
        return sha + ("+dirty" if _git("status", "--porcelain") else "")
    except Exception:
        return "unknown"


def git_branch() -> str:
    """Current branch name (for the `[version]` stderr line); 'unknown' if unresolvable."""
    try:
        return _git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    except Exception:
        return "unknown"


def _axis(v, axis):
    return next(f for f in v.axis_findings if f.axis == axis)


def _pred(v) -> dict:
    return {
        "retraction": _axis(v, "retraction").verdict in ("RELIES_ON_RETRACTED", "CITED_PAPER_HAS_EOC"),
        "scope": (_axis(v, "species_scope").verdict == "SCOPE_MISMATCH"
                  or _axis(v, "population_scope").verdict == "SCOPE_MISMATCH"),
    }


def _prf(tp, fp, fn, tn):
    prec = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    spec = tn / (tn + fp) if (tn + fp) else None
    return prec, rec, spec


def _fmt(x):
    return "n/a" if x is None else f"{x:.2f}"


# ==================================================================================
# Graded-axis prediction extraction (from a graded Verdict's substantive_support axis)
# ==================================================================================
def _graded_pred(v) -> dict:
    """Extract the graded prediction (grade, confidence, status) from a Verdict.

    `status`: GRADED (a real ordinal grade) / ABSTAINED (NEI) / NON_SUBSTANTIATING (Trap 2) /
    NOT_ADJUDICATED (the stub — no graded prediction). Only GRADED rows enter the calibration
    numerator; ABSTAINED + NON_SUBSTANTIATING reduce coverage (RB3 Part 2)."""
    f = _axis(v, "substantive_support")
    ev = f.evidence or {}
    conf = (ev.get("confidence") or {}).get("agreement")
    if bool(ev.get("non_substantiating")):
        status = "NON_SUBSTANTIATING"
    elif bool(ev.get("abstained")) or f.verdict == NOT_ENOUGH_INFO:
        status = "ABSTAINED"
    elif f.provenance == "stub-not-adjudicated" or f.verdict in ("", "NOT_ADJUDICATED"):
        status = "NOT_ADJUDICATED"
    else:
        status = "GRADED"
    return {"grade": f.verdict, "confidence": conf, "status": status}


# ==================================================================================
# RB3 calibration metrics — PURE functions (unit-tested directly on mocked fixtures)
# ==================================================================================
def brier(items) -> float | None:
    """Brier score: mean (conf − correct)². `items` = [(confidence, correct_bool), ...]."""
    pts = [(c, 1.0 if ok else 0.0) for c, ok in items if isinstance(c, (int, float))]
    if not pts:
        return None
    return sum((c - y) ** 2 for c, y in pts) / len(pts)


def selective_risk_coverage(items) -> dict:
    """Selective risk vs coverage (RB3 Part 3). `items` = [(confidence, correct_bool), ...].

    Sort by confidence desc; for each prefix report (coverage, selective_risk). AURC = mean
    selective risk over prefixes; also risk at ~80% coverage. Lower is better."""
    pts = [(c, bool(ok)) for c, ok in items if isinstance(c, (int, float))]
    if not pts:
        return {"aurc": None, "risk_at_80": None, "operating_points": []}
    pts.sort(key=lambda t: t[0], reverse=True)
    n = len(pts)
    ops, errors, risks = [], 0, []
    risk_at_80 = None
    for k, (_c, ok) in enumerate(pts, 1):
        if not ok:
            errors += 1
        coverage = k / n
        risk = errors / k
        risks.append(risk)
        ops.append({"coverage": round(coverage, 4), "risk": round(risk, 4)})
        if risk_at_80 is None and coverage >= 0.80:
            risk_at_80 = risk
    aurc = sum(risks) / n
    return {"aurc": aurc, "risk_at_80": risk_at_80, "operating_points": ops}


def quadratic_weighted_kappa(preds, refs, n_classes: int = len(ORDINAL_GRADES)) -> float | None:
    """QWK over the 0..n_classes-1 ordinal (wᵢⱼ = (i−j)²/(N−1)²). None if undefined."""
    pairs = [(p, r) for p, r in zip(preds, refs) if p is not None and r is not None]
    if not pairs or n_classes < 2:
        return None
    N = n_classes
    O = [[0] * N for _ in range(N)]
    prow = [0] * N
    rcol = [0] * N
    for p, r in pairs:
        O[p][r] += 1
        prow[p] += 1
        rcol[r] += 1
    total = len(pairs)
    num = den = 0.0
    for i in range(N):
        for j in range(N):
            w = (i - j) ** 2 / (N - 1) ** 2
            e = prow[i] * rcol[j] / total
            num += w * O[i][j]
            den += w * e
    if den == 0:
        return 1.0  # no expected disagreement possible ⇒ perfect by convention
    return 1.0 - num / den


def accuracy(preds, refs, adjacent: bool = False) -> float | None:
    pairs = [(p, r) for p, r in zip(preds, refs) if p is not None and r is not None]
    if not pairs:
        return None
    hits = sum(1 for p, r in pairs if (abs(p - r) <= 1 if adjacent else p == r))
    return hits / len(pairs)


def _wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (RB3 reliability diagram)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def reliability_bins(items, n_bins: int = 4) -> list[dict]:
    """Equal-mass reliability bins. `items` = [(confidence, correct_bool), ...]."""
    pts = sorted(((c, bool(ok)) for c, ok in items if isinstance(c, (int, float))),
                 key=lambda t: t[0])
    n = len(pts)
    if n == 0:
        return []
    n_bins = max(1, min(n_bins, n))
    bins = []
    for b in range(n_bins):
        lo = b * n // n_bins
        hi = (b + 1) * n // n_bins if b < n_bins - 1 else n
        chunk = pts[lo:hi]
        if not chunk:
            continue
        k = sum(1 for _c, ok in chunk if ok)
        mean_conf = sum(c for c, _ok in chunk) / len(chunk)
        acc = k / len(chunk)
        lo_ci, hi_ci = _wilson_ci(k, len(chunk))
        bins.append({"n": len(chunk), "mean_conf": round(mean_conf, 4), "accuracy": round(acc, 4),
                     "wilson_ci": [round(lo_ci, 4), round(hi_ci, 4)]})
    return bins


def ece(items, n_bins: int = 4) -> float | None:
    """Expected Calibration Error over equal-mass bins (RB3: caveated, high variance at small N)."""
    bins = reliability_bins(items, n_bins)
    if not bins:
        return None
    n = sum(b["n"] for b in bins)
    return sum(b["n"] / n * abs(b["mean_conf"] - b["accuracy"]) for b in bins)


def auroc(items) -> float | None:
    """AUROC of confidence-vs-correctness (Mann–Whitney). None if one class is empty."""
    pos = [c for c, ok in items if ok and isinstance(c, (int, float))]
    neg = [c for c, ok in items if (not ok) and isinstance(c, (int, float))]
    if not pos or not neg:
        return None
    wins = 0.0
    for cp in pos:
        for cn in neg:
            wins += 1.0 if cp > cn else (0.5 if cp == cn else 0.0)
    return wins / (len(pos) * len(neg))


def auroc_bootstrap_ci(items, n_boot: int = 1000, seed: int = 0) -> tuple[float, float] | None:
    """Bootstrap 95% CI for AUROC (seeded for reproducibility)."""
    clean = [(c, bool(ok)) for c, ok in items if isinstance(c, (int, float))]
    if len(clean) < 3:
        return None
    rng = random.Random(seed)
    vals = []
    n = len(clean)
    for _ in range(n_boot):
        sample = [clean[rng.randrange(n)] for _ in range(n)]
        a = auroc(sample)
        if a is not None:
            vals.append(a)
    if len(vals) < 2:
        return None
    vals.sort()
    lo = vals[int(0.025 * (len(vals) - 1))]
    hi = vals[int(0.975 * (len(vals) - 1))]
    return (lo, hi)


def confidence_spread(confs) -> dict:
    """Agreement-discrimination diagnostic (manager note): if the emitted confidence (a_exact)
    saturates near 1.0 for every case, it has stopped discriminating and the tier is meaningless.
    Report the spread + a degeneracy flag so a broken signal is VISIBLE (remedy: raise the critic
    temperature). This is not calibration — it is a guard that the calibration input is alive."""
    xs = [c for c in confs if isinstance(c, (int, float))]
    if not xs:
        return {"n": 0, "degenerate": None}
    mean = sum(xs) / len(xs)
    stdev = (sum((x - mean) ** 2 for x in xs) / len(xs)) ** 0.5
    hist = {"[0,0.5)": 0, "[0.5,0.7)": 0, "[0.7,0.9)": 0, "[0.9,1.0]": 0}
    for x in xs:
        if x < 0.5:
            hist["[0,0.5)"] += 1
        elif x < 0.7:
            hist["[0.5,0.7)"] += 1
        elif x < 0.9:
            hist["[0.7,0.9)"] += 1
        else:
            hist["[0.9,1.0]"] += 1
    degenerate = stdev < 0.05 or hist["[0.9,1.0]"] == len(xs)
    return {"n": len(xs), "min": round(min(xs), 4), "max": round(max(xs), 4),
            "mean": round(mean, 4), "stdev": round(stdev, 4), "histogram": hist,
            "degenerate": bool(degenerate)}


def calibrate_graded(records) -> dict:
    """Compute the RB3 graded-axis calibration block from joined prediction+reference records.

    `records` = [{case_id, grade, confidence, status, ref_grade}, ...]. Only records with a
    human `ref_grade` (a real ordinal grade) are labeled; among those, GRADED rows feed the
    metrics and ABSTAINED / NON_SUBSTANTIATING rows reduce coverage. Returns
    {"status": "pending"} when there are no reference labels yet."""
    labeled = [r for r in records if r.get("ref_grade") in ORDINAL_INDEX]
    if not labeled:
        return {"status": "pending", "n_records": len(records), "n_labeled": 0}

    graded = [r for r in labeled if r.get("status") == "GRADED" and r.get("grade") in ORDINAL_INDEX]
    non_graded = [r for r in labeled if r.get("status") in ("ABSTAINED", "NON_SUBSTANTIATING")]
    n_labeled = len(labeled)
    coverage = len(graded) / n_labeled if n_labeled else 0.0

    preds = [ORDINAL_INDEX[r["grade"]] for r in graded]
    refs = [ORDINAL_INDEX[r["ref_grade"]] for r in graded]
    exact_items = [(r["confidence"], p == q) for r, p, q in zip(graded, preds, refs)]
    adj_items = [(r["confidence"], abs(p - q) <= 1) for r, p, q in zip(graded, preds, refs)]
    n_errors = sum(1 for p, q in zip(preds, refs) if p != q)

    return {
        "status": "scored",
        "n_labeled": n_labeled,
        "n_graded": len(graded),
        "n_abstained": sum(1 for r in non_graded if r["status"] == "ABSTAINED"),
        "n_non_substantiating": sum(1 for r in non_graded if r["status"] == "NON_SUBSTANTIATING"),
        "coverage": round(coverage, 4),
        "selective_risk": round(n_errors / len(graded), 4) if graded else None,
        "brier_exact": brier(exact_items),
        "brier_adjacent": brier(adj_items),
        "accuracy_exact": accuracy(preds, refs),
        "accuracy_adjacent": accuracy(preds, refs, adjacent=True),
        "qwk": quadratic_weighted_kappa(preds, refs),
        "risk_coverage": selective_risk_coverage(exact_items),
        "ece": ece(exact_items),
        "reliability_bins": reliability_bins(exact_items),
        "auroc": auroc(exact_items),
        "auroc_ci": auroc_bootstrap_ci(exact_items),
        "adjacent_prediction_coverage": accuracy(preds, refs, adjacent=True),  # conformal, diagnostic-only
        "confidence_spread": confidence_spread([r["confidence"] for r in graded]),
    }


# ==================================================================================
# Human graded-reference sidecar (anti-circularity: NEVER model-generated)
# ==================================================================================
def load_graded_references(cases: list[dict], sidecar_path: str | None = None) -> dict:
    """Reference grades keyed by case_id, from a per-case `substantive_grade` field and/or a
    sidecar file (jsonl or json keyed by case_id, field `substantive_grade`). Only values on the
    RB1 ordinal are accepted; the scorer never fabricates a reference.

    ANTI-CIRCULARITY: the reference field is ONLY `substantive_grade` — deliberately NOT the bare
    `grade` key the scorer stores its own MODEL predictions under (`graded_records[*].grade`). The
    key-name distinction is the structural barrier that stops the tool's own output from being
    re-ingested as a human reference (CLAUDE.md: enforce structurally, not by convention)."""
    refs: dict[str, str] = {}
    for c in cases:
        g = c.get("substantive_grade")
        if isinstance(g, str) and g in ORDINAL_INDEX:
            refs[c.get("case_id", c.get("cited_pmid"))] = g
    if sidecar_path:
        p = Path(sidecar_path)
        rows: list[dict]
        if p.suffix == ".jsonl":
            rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
        else:
            raw = json.loads(p.read_text())
            rows = raw if isinstance(raw, list) else raw.get("cases", [])
        for row in rows:
            cid = row.get("case_id")
            g = row.get("substantive_grade")
            if cid and isinstance(g, str) and g in ORDINAL_INDEX:
                refs[cid] = g
    return refs


def sample_calibration_manifest(cases: list[dict], n: int = 30, seed: int = 0,
                                exclude=RETRACTION_MISLABELS) -> list[dict]:
    """Draw a stratified ~20–40 case manifest for the HUMAN spot-check (RB3 §3.4).

    Emits case_ids + claim/cited-paper context ONLY — no grades (the human assigns them).
    Stratified across `ground_truth_label` × `confidence_tier` for case-type diversity, excluding
    the retraction-mislabelled cases. Deterministic (seeded)."""
    pool = [c for c in cases if c.get("case_id") not in set(exclude)]
    strata: dict[tuple, list[dict]] = {}
    for c in pool:
        key = (c.get("ground_truth_label", "?"), c.get("confidence_tier", "?"))
        strata.setdefault(key, []).append(c)
    rng = random.Random(seed)
    for v in strata.values():
        rng.shuffle(v)
    # Round-robin across strata for an even spread until we reach n.
    order = sorted(strata)
    picked: list[dict] = []
    while len(picked) < min(n, len(pool)):
        progressed = False
        for key in order:
            if strata[key]:
                picked.append(strata[key].pop())
                progressed = True
                if len(picked) >= min(n, len(pool)):
                    break
        if not progressed:
            break
    return [{"case_id": c.get("case_id"), "cited_pmid": c.get("cited_pmid"),
             "ground_truth_label": c.get("ground_truth_label"),
             "confidence_tier": c.get("confidence_tier"),
             "claim_text": c.get("claim_text"), "cited_title": c.get("cited_title"),
             "substantive_grade": None}  # <- the human fills this in (blind to the agent)
            for c in picked]


# ==================================================================================
# Observability + resumability (WO-C4 full-text §D): incremental predictions, progress,
# --limit, resume/--fresh, coverage-by-evidence-depth
# ==================================================================================
PREDICTIONS_FILE = "graded_predictions.jsonl"


def _log(msg: str) -> None:
    """Flushed stderr progress (stdout stays the scorecard, so a pipe/tee is unaffected)."""
    print(msg, file=sys.stderr, flush=True)


def read_predictions(path: Path) -> dict:
    """Already-computed graded predictions keyed by case_id (resume). Tolerates a blank/partial
    trailing line from an interrupted run — the last flush before a crash may be incomplete."""
    done: dict[str, dict] = {}
    if not path.exists():
        return done
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue                       # skip a partial line left by a mid-write crash
        cid = row.get("case_id")
        if cid:
            done[cid] = row
    return done


def coverage_by_depth(records: list[dict]) -> dict:
    """Graded/abstained/non-substantiating split by evidence depth (WO-C4 §D item 12).

    Answers 'did full text raise coverage?' — computed over ALL graded predictions (no reference
    labels required), so it is visible even before human grades exist."""
    out: dict[str, dict] = {}
    for depth in ("fulltext", "abstract"):
        sub = [r for r in records if r.get("evidence_depth") == depth]
        n = len(sub)
        n_graded = sum(1 for r in sub if r.get("status") == "GRADED")
        out[depth] = {
            "n": n,
            "graded": n_graded,
            "abstained": sum(1 for r in sub if r.get("status") == "ABSTAINED"),
            "non_substantiating": sum(1 for r in sub if r.get("status") == "NON_SUBSTANTIATING"),
            "not_adjudicated": sum(1 for r in sub if r.get("status") == "NOT_ADJUDICATED"),
            "coverage": round(n_graded / n, 4) if n else None,
        }
    return out


def _finish_line(i: int, n: int, rec: dict, graded_so_far: int) -> str:
    conf = rec.get("confidence")
    a_exact = f"{conf:.2f}" if isinstance(conf, (int, float)) else "n/a"
    grade = rec.get("grade") if rec.get("status") == "GRADED" else rec.get("status")
    elapsed = rec.get("elapsed_s")
    el = f"{elapsed:.1f}" if isinstance(elapsed, (int, float)) else "?"
    return (f"[{i}/{n}] {rec.get('case_id')} depth={rec.get('evidence_depth')} grade={grade} "
            f"a_exact={a_exact} elapsed={el}s (graded {graded_so_far}/{i})")


def _round_grade_label(critic_round) -> str:
    """Legible per-round outcome for the -v line (WO-C4 fix): distinguish a round that FAILED TO
    PARSE (truncated/invalid JSON, or a parsed object with a missing/garbled grade) — shown as
    UNPARSED — from a genuine abstention (NEI) and a non-substantiating verdict (N/A), so a future
    truncation regression is legible at a glance instead of hiding behind a clean ABSTAIN."""
    if not isinstance(critic_round, dict):
        return "UNPARSED"                         # None: the model reply didn't parse (truncation)
    g = critic_round.get("grade")
    if isinstance(g, str) and g in ORDINAL_INDEX:  # str-guard: an unhashable grade must not TypeError
        return g                                  # a real ordinal grade
    if g == NOT_ENOUGH_INFO:
        return "NEI"                              # genuine abstention (recognized, not a parse failure)
    if g == NON_SUBSTANTIATING:
        return "N/A"                              # Trap 2 non-substantiating (recognized)
    return "UNPARSED"                             # parsed object but no recognized grade field


def _round_hook(i: int, n: int, cid: str):
    """Per-round progress callback (verbose): shows a case is alive within seconds of each round,
    and surfaces the critic's `usage.output_tokens` as `out_tok=NNN` so the real output-length
    distribution is readable live — the input to setting the production cap from data (WO-C4 §3)."""
    def _hook(round_no: int, critic_round, out_tok=None) -> None:
        tok = f" out_tok={out_tok}" if isinstance(out_tok, int) else ""
        _log(f"[{i}/{n}] {cid}   · round {round_no} grade={_round_grade_label(critic_round)}{tok}")
    return _hook


# ==================================================================================
# Aggregation — PURE. Both the live pipeline (`score`) and the offline recompute
# (`score_from_predictions`) call THIS SAME function on collected per-case rows, so the
# offline scorecard is bit-for-bit the live scorecard (no metric drift possible).
# ==================================================================================
def aggregate_metrics(rows: list[dict], graded_records: list[dict], errors: list[dict], *,
                      graded: bool, version: str) -> dict:
    """Roll per-case objective `rows` (+ graded_records when graded) up into the scorecard dict.

    `rows`   : one dict per NON-error case with keys gt / pred_retraction / pred_scope / overall
               / species_verdict / case_id (the objective axes).
    `graded_records` : one dict per non-error case with case_id / status / grade / confidence /
               ref_grade / evidence_depth (the graded substantive axis).
    `errors` : status=ERROR rows (infra/network) — excluded from every metric denominator.
    """
    # Retraction detection: positives = RETRACTED cases; negatives = the rest.
    r_tp = sum(x["gt"] == "RETRACTED" and x["pred_retraction"] for x in rows)
    r_fn = sum(x["gt"] == "RETRACTED" and not x["pred_retraction"] for x in rows)
    r_fp = sum(x["gt"] != "RETRACTED" and x["pred_retraction"] for x in rows)
    r_tn = sum(x["gt"] != "RETRACTED" and not x["pred_retraction"] for x in rows)

    # Scope detection: positives = SCOPE_MISMATCH; negatives = SUPPORTED controls.
    # A-cases excluded (their labeled axis is retraction, not scope) but reported observationally.
    s_rows = [x for x in rows if x["gt"] in ("SCOPE_MISMATCH", "SUPPORTED")]
    s_tp = sum(x["gt"] == "SCOPE_MISMATCH" and x["pred_scope"] for x in s_rows)
    s_fn = sum(x["gt"] == "SCOPE_MISMATCH" and not x["pred_scope"] for x in s_rows)
    s_fp = sum(x["gt"] == "SUPPORTED" and x["pred_scope"] for x in s_rows)
    s_tn = sum(x["gt"] == "SUPPORTED" and not x["pred_scope"] for x in s_rows)

    # Control specificity: SUPPORTED cases clean on BOTH axes.
    controls = [x for x in rows if x["gt"] == "SUPPORTED"]
    clean = sum(not x["pred_retraction"] and not x["pred_scope"] for x in controls)

    # Overall "correct finding" per case.
    def correct(x):
        if x["gt"] == "RETRACTED":
            return x["pred_retraction"]
        if x["gt"] == "SCOPE_MISMATCH":
            return x["pred_scope"]
        return not x["pred_retraction"] and not x["pred_scope"]
    n_correct = sum(correct(x) for x in rows)

    a_scope_fp = [x["case_id"] for x in rows if x["gt"] == "RETRACTED" and x["pred_scope"]]

    res = {
        "n": len(rows), "rows": rows, "graded": graded,
        "retraction": {"tp": r_tp, "fp": r_fp, "fn": r_fn, "tn": r_tn,
                       "prf": _prf(r_tp, r_fp, r_fn, r_tn)},
        "scope": {"tp": s_tp, "fp": s_fp, "fn": s_fn, "tn": s_tn,
                  "prf": _prf(s_tp, s_fp, s_fn, s_tn),
                  "missed": [x["case_id"] for x in s_rows
                             if x["gt"] == "SCOPE_MISMATCH" and not x["pred_scope"]]},
        "control_specificity": (clean, len(controls)),
        "overall_accuracy": (n_correct, len(rows)),
        "a_scope_observational": a_scope_fp,
        "code_version": version,
        "errors": errors,               # infra failures (grounding/network) — excluded from all metrics
        "n_errors": len(errors),
    }
    if graded:
        res["calibration"] = calibrate_graded(graded_records)
        res["coverage_by_depth"] = coverage_by_depth(graded_records)
        res["graded_records"] = graded_records
    return res


# The FROZEN durable-results field set (req #1). One flat JSON object per case; a strict superset of
# the incremental graded_predictions.jsonl row, so `recalibrate.build_dataset` consumes it unchanged.
DURABLE_FIELDS = ("case_id", "corpus", "code_version", "ground_truth_label", "pred_retraction",
                  "pred_scope", "retraction_verdict", "species_scope_verdict",
                  "population_scope_verdict", "overall", "status", "grade", "confidence",
                  "ref_grade", "evidence_depth", "elapsed_s")


def build_durable_rows(rows: list[dict], graded_records: list[dict], errors: list[dict], *,
                       corpus: str, version: str, gt_by_case: dict | None = None) -> list[dict]:
    """Join objective `rows` + `graded_records` (+ `errors`) by case_id into one COMPLETE-verdict
    row per case (the durable results schema). ERROR cases are emitted as a minimal status=ERROR row
    (they never completed the objective pipeline), so an offline reader can reconstruct n_errors."""
    gt_by_case = gt_by_case or {}
    obj = {x["case_id"]: x for x in rows}
    grd = {r["case_id"]: r for r in graded_records}
    out: list[dict] = []
    for cid in dict.fromkeys([*(x["case_id"] for x in rows), *(r["case_id"] for r in graded_records)]):
        o = obj.get(cid, {})
        g = grd.get(cid, {})
        out.append({
            "case_id": cid, "corpus": corpus, "code_version": version,
            "ground_truth_label": o.get("gt", gt_by_case.get(cid)),
            "pred_retraction": o.get("pred_retraction"),
            "pred_scope": o.get("pred_scope"),
            "retraction_verdict": o.get("retraction_verdict"),
            "species_scope_verdict": o.get("species_verdict"),
            "population_scope_verdict": o.get("population_verdict"),
            "overall": o.get("overall"),
            "status": g.get("status"), "grade": g.get("grade"),
            "confidence": g.get("confidence"), "ref_grade": g.get("ref_grade"),
            "evidence_depth": g.get("evidence_depth"), "elapsed_s": g.get("elapsed_s"),
        })
    for e in errors:                                   # infra failures — recorded, excluded from metrics
        out.append({"case_id": e.get("case_id"), "corpus": corpus,
                    "code_version": e.get("code_version", version), "status": "ERROR",
                    "error": e.get("error"), "elapsed_s": e.get("elapsed_s"),
                    "ground_truth_label": gt_by_case.get(e.get("case_id"))})
    return out


def score(cases: list[dict], graded: bool = False, references: dict | None = None, *,
          out_dir: str | Path | None = None, limit: int | None = None, fresh: bool = False,
          progress: bool = False, verbose: bool = False, client=None, config=None,
          version: str = "", recalibration=None, corpus_label: str = "",
          results_dir: str | Path | None = None) -> dict:
    """Score the corpus. When `graded`, per-case predictions are appended INCREMENTALLY to
    `<out_dir>/graded_predictions.jsonl` (flushed) so a Ctrl-C never loses completed cases; on the
    next run those case_ids are SKIPPED (resume) unless `fresh`. `limit` scores only the first N
    cases (smoke test). `progress`/`verbose` stream stderr progress. `client`/`config` are threaded
    to the graded adjudicator (mock injection for offline tests). `version` is the code stamp
    written into every prediction row + the scorecard header (WO-C4 §4).

    Per-case failure isolation (WO-C4 §2): a grounding/network error on ONE case is caught, logged,
    recorded as a status=ERROR prediction row (excluded from every metric denominator — an infra
    error is not an abstention), and the run CONTINUES. A single bad PMID never aborts a long run.

    `recalibration` (RB3, opt-in) is the fitted `a_exact -> P(correct)` Platt map; when supplied it is
    attached to every graded case's config so `evidence.calibration.note` carries the calibrated
    confidence. None (default) leaves the emitted confidence untouched — the map is NEVER auto-enabled
    (see `recalibrate.resolve_recalibration` / the `--recalibrate` flag)."""
    references = references or {}
    if limit is not None:
        cases = cases[:limit]
    n = len(cases)

    # Resume bookkeeping (graded + a destination file only).
    pred_path = (Path(out_dir) / PREDICTIONS_FILE) if (graded and out_dir) else None
    done: dict[str, dict] = {}
    pred_f = None
    if pred_path is not None:
        pred_path.parent.mkdir(parents=True, exist_ok=True)
        if fresh:
            pred_path.unlink(missing_ok=True)
        else:
            done = read_predictions(pred_path)
        pred_f = pred_path.open("a", encoding="utf-8")
        # A prior run may have crashed mid-write, leaving a partial newline-less last line. A bare
        # append would GLUE the next record onto it, corrupting both into one unparseable line that
        # read_predictions then drops — silently losing the recomputed case. Terminate the dangling
        # partial line first so the recomputed record lands on its own parseable line.
        if pred_path.exists() and pred_path.stat().st_size > 0:
            with pred_path.open("rb") as _tail:
                _tail.seek(-1, 2)
                needs_nl = _tail.read(1) != b"\n"
            if needs_nl:
                pred_f.write("\n")
                pred_f.flush()
        # Only NON-error rows count as "completed": a stored status=ERROR row is a prior infra
        # failure, not finished work, so it is RETRIED (not skipped) on this run.
        done_ok = {k: v for k, v in done.items() if v.get("status") != "ERROR"}
        if done_ok:
            _log(f"[resume] {len(done_ok)} completed case(s) found in {pred_path.name} — skipping "
                 "them (pass --fresh to recompute)")

    rows = []
    graded_records = []
    errors: list[dict] = []
    graded_so_far = 0
    try:
        for i, c in enumerate(cases, 1):
            cid = c.get("case_id", c["cited_pmid"])
            prior = done.get(cid) if graded else None
            resumed = bool(prior) and prior.get("status") != "ERROR"
            use_graded = graded and not resumed
            if progress:
                _log(f"[{i}/{n}] {cid} start" + (" (resumed — reuse stored prediction)" if resumed else ""))
            case_config = config
            if use_graded:
                overrides = {}
                if verbose:
                    overrides["on_round"] = _round_hook(i, n, cid)
                if recalibration is not None:   # RB3 opt-in map (fills evidence.calibration.note)
                    overrides["recalibration"] = recalibration
                if overrides:
                    case_config = replace(config or AdjudicationConfig(), **overrides)
            t0 = time.perf_counter()
            try:
                r = run_slice(c["claim_text"], cited_pmid=c["cited_pmid"], graded=use_graded,
                              client=client, config=case_config)
            except Exception as e:            # noqa: BLE001 — one bad PMID must not abort the run
                err = f"{type(e).__name__}: {e}"
                # A resumed case already holds a good graded prediction; a transient failure on its
                # cheap objective RE-run must not discard that work (nor trigger a costly re-grade),
                # so reuse the stored prediction rather than recording an ERROR.
                if resumed:
                    rec = {**prior, "ref_grade": references.get(cid, prior.get("ref_grade"))}
                    graded_records.append(rec)
                    if rec.get("status") == "GRADED":
                        graded_so_far += 1
                    _log(f"[{i}/{n}] {cid} objective re-run failed ({err}) — reusing stored prediction")
                    continue
                _log(f"[{i}/{n}] {cid} ERROR: {err} — recorded + excluded from metrics (retried next run)")
                err_rec = {"case_id": cid, "status": "ERROR", "error": err, "code_version": version,
                           "elapsed_s": round(time.perf_counter() - t0, 2)}
                if pred_f is not None:
                    pred_f.write(json.dumps(err_rec, ensure_ascii=False) + "\n")
                    pred_f.flush()            # durable so `tail -f` / the next run sees the failure
                errors.append(err_rec)
                continue
            v = r["verdict"]
            pred = _pred(v)
            rows.append({
                "case_id": cid,
                "gt": c["ground_truth_label"],
                "pred_retraction": pred["retraction"],
                "pred_scope": pred["scope"],
                "overall": v.overall,
                "species_verdict": _axis(v, "species_scope").verdict,
                # Raw per-axis verdict strings — not read by aggregate_metrics (which uses the derived
                # pred_* booleans), carried only so the durable results row records EVERY objective
                # axis verdict per the full-verdict contract (req #1).
                "population_verdict": _axis(v, "population_scope").verdict,
                "retraction_verdict": _axis(v, "retraction").verdict,
            })
            if graded:
                if resumed:
                    # Re-attach the current reference (a sidecar may have been supplied since).
                    rec = {**prior, "ref_grade": references.get(cid, prior.get("ref_grade"))}
                else:
                    gp = _graded_pred(v)
                    depth = "fulltext" if r["grounded"].full_text else "abstract"
                    sub_ev = _axis(v, "substantive_support").evidence or {}
                    out_toks = (sub_ev.get("self_consistency") or {}).get("output_tokens")
                    rec = {"case_id": cid, "status": gp["status"], "grade": gp["grade"],
                           "confidence": gp["confidence"], "ref_grade": references.get(cid),
                           "evidence_depth": depth, "output_tokens": out_toks,
                           "code_version": version,
                           "elapsed_s": round(time.perf_counter() - t0, 2)}
                    if pred_f is not None:
                        pred_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        pred_f.flush()     # a crash after this line never loses this case
                graded_records.append(rec)
                if rec.get("status") == "GRADED":
                    graded_so_far += 1
                if progress:
                    _log(_finish_line(i, n, rec, graded_so_far))
    finally:
        if pred_f is not None:
            pred_f.close()

    # Durable, COMPLETE-verdict per-case results file (req #1) — the deterministic input for offline
    # scoring. Written ONCE, after all cases complete (crash-safety for resume is already handled by
    # the incremental graded_predictions.jsonl above); this file adds the objective axes + gt so the
    # ENTIRE scorecard is recomputable offline with no pipeline/NCBI/key. Emitted only for a NAMED
    # corpus (every real run via main() supplies one); an unlabeled ad-hoc score() call skips it.
    if graded and corpus_label:
        gt_by_case = {c.get("case_id", c.get("cited_pmid")): c.get("ground_truth_label") for c in cases}
        durable = build_durable_rows(rows, graded_records, errors, corpus=corpus_label,
                                     version=version, gt_by_case=gt_by_case)
        rdir = Path(results_dir) if results_dir is not None else RESULTS_DIR
        rdir.mkdir(parents=True, exist_ok=True)
        fname = f"{corpus_label or 'corpus'}_{version or 'unknown'}.jsonl".replace("/", "_")
        (rdir / fname).write_text(
            "\n".join(json.dumps(d, ensure_ascii=False) for d in durable) + "\n")
        _log(f"[results] {len(durable)} full-verdict row(s) → {rdir / fname} (offline-scoring input)")

    return aggregate_metrics(rows, graded_records, errors, graded=graded, version=version)


# ==================================================================================
# OFFLINE scoring (req #2) — recompute the ENTIRE scorecard from a durable results file.
# PURE: no pipeline, no NCBI, no ANTHROPIC_API_KEY, no network. Deterministic, <1s.
# ==================================================================================
def load_reference_grades(path: str | Path) -> dict[str, str]:
    """case_id -> ordinal reference grade, from a `--graded-reference` sidecar (jsonl or json).
    Schema-tolerant on the grade column (`substantive_grade` / `grade` / `ref_grade` / …) — see
    `recalibrate._REF_GRADE_KEYS`. Only grades on the RB1 ordinal are kept; the scorer never
    fabricates a reference (anti-circularity: this file is the HUMAN/decider truth)."""
    from .recalibrate import _REF_GRADE_KEYS
    p = Path(path)
    if p.suffix == ".jsonl":
        rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    else:
        raw = json.loads(p.read_text())
        rows = raw if isinstance(raw, list) else raw.get("cases", raw.get("rows", []))
    refs: dict[str, str] = {}
    for r in rows:
        cid = r.get("case_id")
        grade = next((r[k] for k in _REF_GRADE_KEYS if r.get(k)), None)
        if cid and isinstance(grade, str) and grade in ORDINAL_INDEX:
            refs[cid] = grade
    return refs


def compute_recal_block(graded_records: list[dict], references: dict[str, str]) -> dict:
    """The honest recalibrated-LOO ECE block (req #2), computed via `recalibrate.py` on the SAME
    join it uses live: GRADED predictions with an ordinal reference grade. Returns raw vs LOO ECE
    (the LOO number is the headline the gate reads), plus the discrimination invariants (AUROC /
    exact-accuracy) so a reviewer can confirm the offline number matches `python -m citeval.recalibrate`."""
    from . import recalibrate as R
    ds = R.build_dataset(graded_records, references)
    if not ds:
        return {"status": "pending", "n_fit": 0, "raw_ece": None, "loo_ece": None,
                "auroc": None, "exact_accuracy": None}
    xs = [d[1] for d in ds]
    ys = [d[2] for d in ds]
    keys = [round(x, 6) for x in xs]
    raw_ece, _ = R.ece_and_reliability(keys, xs, ys)
    loo = R.loo_predictions(xs, ys)
    loo_ece, _ = R.ece_and_reliability(keys, loo, ys)
    return {"status": "scored", "n_fit": len(ds), "raw_ece": raw_ece, "loo_ece": loo_ece,
            "auroc": R.auroc(xs, ys), "exact_accuracy": sum(ys) / len(ys)}


def score_from_predictions(results_rows: list[dict], references: dict[str, str] | None = None, *,
                           version: str = "") -> dict:
    """Recompute the full scorecard dict PURELY from durable results rows (req #2). Reconstructs the
    exact `rows` / `graded_records` / `errors` the live `score()` built, re-attaches the AUTHORITATIVE
    reference grade (the `--graded-reference` file wins over the row's baked snapshot), and calls the
    SAME `aggregate_metrics` — so the numbers are identical to the live scorecard. Adds a `recal`
    block (recalibrated-LOO ECE). No model, no network, no key."""
    references = references or {}
    rows: list[dict] = []
    graded_records: list[dict] = []
    errors: list[dict] = []
    for r in results_rows:
        cid = r.get("case_id")
        if r.get("status") == "ERROR":
            errors.append({"case_id": cid, "status": "ERROR", "error": r.get("error"),
                           "code_version": r.get("code_version", version),
                           "elapsed_s": r.get("elapsed_s")})
            continue
        # Objective axes present? The live `score()` EXCLUDES a case whose objective pipeline did not
        # complete (a resumed graded case whose cheap objective RE-run raised) from `rows` — the
        # objective metric denominators — while KEEPING its stored graded prediction (it lands in
        # graded_records only). Such a durable row carries a null pred_retraction. `pred_retraction is
        # not None` is THE signal the objective pipeline ran (live always has a ground_truth_label
        # alongside it), so gate on that alone to mirror the live inclusion exactly — skip `rows`,
        # still record the graded prediction — instead of re-admitting the case as a clean negative
        # (bool(None) == False).
        if r.get("pred_retraction") is not None:
            rows.append({
                "case_id": cid, "gt": r.get("ground_truth_label"),
                "pred_retraction": bool(r.get("pred_retraction")),
                "pred_scope": bool(r.get("pred_scope")),
                "overall": r.get("overall") or "",
                "species_verdict": r.get("species_scope_verdict") or "",
            })
        graded_records.append({
            "case_id": cid, "status": r.get("status"), "grade": r.get("grade"),
            "confidence": r.get("confidence"),
            "ref_grade": references.get(cid, r.get("ref_grade")),   # authoritative reference wins
            "evidence_depth": r.get("evidence_depth"),
        })
    res = aggregate_metrics(rows, graded_records, errors, graded=True, version=version)
    # The recal block MUST score the graded axis against the SAME effective reference the calibration
    # block used — `graded_records[*].ref_grade` (authoritative `--graded-reference`, else the baked
    # snapshot) — NOT the raw `references` dict. Otherwise `--from-predictions` WITHOUT a
    # `--graded-reference` would score calibration against the baked ref while the recal block went
    # 'pending' (references empty), and the two blocks would disagree. Deriving the recal reference
    # from graded_records keeps them identical in every invocation.
    effective_refs = {gr["case_id"]: gr["ref_grade"] for gr in graded_records
                      if gr.get("ref_grade") in ORDINAL_INDEX}
    res["recal"] = compute_recal_block(graded_records, effective_refs)
    return res


def _fmt_metric(x):
    return "PENDING" if x is None else f"{x:.3f}"


def render_calibration(cal: dict) -> list[str]:
    """The graded substantive-support calibration block (RB3 Part 3)."""
    L = ["## Substantive-support calibration (graded axis, RB3)", ""]
    if cal.get("status") == "pending":
        L += [f"- **Graded-axis calibration:** pending reference labels — {cal.get('n_records', 0)} "
              "graded prediction(s) produced, but no HUMAN `substantive_grade` reference supplied "
              "yet (anti-circularity: the reference is never model-generated). Provide a "
              "`--graded-reference` sidecar to score.", ""]
        return L
    rc = cal.get("risk_coverage", {})
    cs = cal.get("confidence_spread", {})
    L += [
        f"- **Coverage:** {cal['coverage']:.2f} ({cal['n_graded']} graded / {cal['n_labeled']} "
        f"labeled; {cal['n_abstained']} abstained + {cal['n_non_substantiating']} non-substantiating "
        "excluded from grading metrics).",
        f"- **Selective risk** (errors/graded): {_fmt_metric(cal['selective_risk'])}",
        f"- **Brier** — exact {_fmt_metric(cal['brier_exact'])} · ±1-adjacent "
        f"{_fmt_metric(cal['brier_adjacent'])}",
        f"- **Accuracy** — exact {_fmt_metric(cal['accuracy_exact'])} · ±1-adjacent "
        f"{_fmt_metric(cal['accuracy_adjacent'])}",
        f"- **Quadratic-weighted kappa (QWK):** {_fmt_metric(cal['qwk'])}",
        f"- **AURC:** {_fmt_metric(rc.get('aurc'))} · **risk@80% coverage:** "
        f"{_fmt_metric(rc.get('risk_at_80'))}",
        f"- **ECE** (4 equal-mass bins; _rough at small N — high variance_): {_fmt_metric(cal['ece'])}",
        f"- **AUROC** (conf vs correctness): {_fmt_metric(cal['auroc'])}"
        + (f" (95% CI {cal['auroc_ci'][0]:.2f}–{cal['auroc_ci'][1]:.2f})" if cal.get("auroc_ci") else ""),
        f"- **Conformal ±1 prediction-set coverage** (_diagnostic only; split-conformal unreliable "
        f"at N={cal['n_graded']}, ~1000 needed_): {_fmt_metric(cal['adjacent_prediction_coverage'])}",
        "",
    ]
    # Agreement-discrimination diagnostic (manager note): confidence must actually discriminate.
    if cs.get("n"):
        warn = "  ⚠️ **confidence appears degenerate/saturated — raise the critic temperature**" \
               if cs.get("degenerate") else ""
        L += [
            f"- **Confidence discrimination:** a_exact spread mean {cs['mean']:.2f} ± {cs['stdev']:.2f} "
            f"(range {cs['min']:.2f}–{cs['max']:.2f}); histogram {cs['histogram']}." + warn,
            "  _If confidence saturates near 1.0 for every case it has stopped discriminating; the "
            "human spot-check (top tier measurably more accurate than bottom) is the ultimate test._",
            "",
        ]
    if cal.get("reliability_bins"):
        L += ["**Reliability diagram** (equal-mass bins; Wilson 95% CIs, bin counts):", "",
              "| bin | n | mean conf | accuracy | Wilson CI |", "|---|---|---|---|---|"]
        for b in cal["reliability_bins"]:
            L.append(f"| · | {b['n']} | {b['mean_conf']:.2f} | {b['accuracy']:.2f} | "
                     f"[{b['wilson_ci'][0]:.2f}, {b['wilson_ci'][1]:.2f}] |")
        L.append("")
    return L


def render_recal(recal: dict) -> list[str]:
    """The recalibrated-LOO ECE block (req #2) — the honest absolute-calibration number the gate
    reads, computed offline via recalibrate.py's Platt LOO-CV. Only shown on the offline path."""
    L = ["## Recalibrated calibration (offline Platt LOO-CV, via recalibrate.py)", ""]
    if recal.get("status") != "scored":
        L += ["- **Recal-LOO ECE:** pending — no GRADED prediction joined to an ordinal reference.", ""]
        return L
    L += [
        f"- **Recal-LOO ECE (headline):** {_fmt_metric(recal.get('loo_ece'))}  "
        f"(raw ECE {_fmt_metric(recal.get('raw_ece'))} → leave-one-out Platt)",
        f"- **AUROC (unchanged by monotone recal):** {_fmt_metric(recal.get('auroc'))} · "
        f"**exact-match accuracy:** {_fmt_metric(recal.get('exact_accuracy'))}  "
        f"(n_fit={recal.get('n_fit')})",
        "",
    ]
    return L


def render_coverage_by_depth(cbd: dict) -> list[str]:
    """Coverage split by grounding depth (WO-C4 §D item 12): does full text lift graded coverage?"""
    L = ["## Coverage by evidence depth (did full text raise coverage?)", "",
         "| depth | n | graded | abstained | non-subst. | coverage |",
         "|---|---|---|---|---|---|"]
    for label, key in (("full text", "fulltext"), ("abstract-only", "abstract")):
        d = cbd.get(key, {})
        L.append(f"| {label} | {d.get('n', 0)} | {d.get('graded', 0)} | {d.get('abstained', 0)} | "
                 f"{d.get('non_substantiating', 0)} | {_fmt(d.get('coverage'))} |")
    L += ["", "_Coverage = graded / (graded + abstained + non-substantiating), per depth. Higher "
          "coverage on full-text cases is the signal that adversarial full text reduced abstention._", ""]
    return L


def render_scorecard(res: dict) -> str:
    rp, rr, rs = res["retraction"]["prf"]
    sp, sr, ss = res["scope"]["prf"]
    clean, nctrl = res["control_specificity"]
    ncorr, ntot = res["overall_accuracy"]
    graded = res.get("graded")
    c4_label = "C4 graded (adversarial, Opus 4.8)" if graded else "C4-stub"
    cal = res.get("calibration") or {}
    if not graded:
        graded_line = "**PENDING** (adversarial adjudicator not run — pass --graded)"
    elif cal.get("status") == "pending":
        graded_line = "**pending reference labels** (graded predictions produced; no human reference yet)"
    else:
        graded_line = f"**SCORED** (coverage {cal.get('coverage', 0):.2f}, see calibration block below)"
    ver = res.get("code_version") or ""
    ver_line = f"Code version: `{ver}`. " if ver else ""
    L = ["# Scorecard — objective axes + graded calibration (measured)", "",
         f"{ver_line}Corpus: {res['n']} cases. Pipeline: C2 grounding (real) + C3 scope "
         f"+ {c4_label}. Graded substantive axis: {graded_line}.", "",
         "## Per-axis metrics", "",
         "| Axis | Precision | Recall | Specificity | TP/FP/FN/TN |",
         "|---|---|---|---|---|",
         f"| Retraction detection | {_fmt(rp)} | {_fmt(rr)} | {_fmt(rs)} | "
         f"{res['retraction']['tp']}/{res['retraction']['fp']}/{res['retraction']['fn']}/{res['retraction']['tn']} |",
         f"| Species/population scope | {_fmt(sp)} | {_fmt(sr)} | {_fmt(ss)} | "
         f"{res['scope']['tp']}/{res['scope']['fp']}/{res['scope']['fn']}/{res['scope']['tn']} |",
         "",
         f"- **Control specificity** (SUPPORTED cases clean on both axes): {clean}/{nctrl}",
         f"- **Overall correct finding**: {ncorr}/{ntot}",
         f"- **Errors**: {res.get('n_errors', 0)}"
         + (f" (grounding/network — excluded from all metrics, will retry next run: "
            f"{', '.join(e['case_id'] for e in res.get('errors', []))})"
            if res.get("n_errors") else " (no grounding/network failures)"),
         f"- **Graded-axis calibration**: {graded_line}", ""]
    if res["scope"]["missed"]:
        L += [f"- **Scope misses (C3-lite limitation, motivates Opus C3 / WO-C3):** "
              f"{', '.join(res['scope']['missed'])} — claim asserts human relevance without an "
              "explicit lexical marker, so the lexical stub cannot detect it.", ""]
    if res["a_scope_observational"]:
        L += [f"- _Observational:_ retracted-case(s) also flagged species mismatch "
              f"({', '.join(res['a_scope_observational'])}) — the cited paper is genuinely "
              "animal-only; not counted in scope metrics.", ""]
    if graded:
        L += render_coverage_by_depth(res.get("coverage_by_depth") or {})
        L += render_calibration(cal)
        if res.get("recal"):
            L += render_recal(res["recal"])
    L += ["## Per-case", "", "| case | gt | retraction? | scope? | overall |",
          "|---|---|---|---|---|"]
    for x in res["rows"]:
        L.append(f"| {x['case_id']} | {x['gt']} | {'Y' if x['pred_retraction'] else '·'} | "
                 f"{'Y' if x['pred_scope'] else '·'} | {x['overall'][:46]} |")
    L += ["", "_Retraction + scope labels are metadata-grounded; this scorecard measures the "
          "objective axes. The graded substantive axis is calibrated against a HUMAN "
          "`substantive_grade` reference (never model-generated) per RB3._"]
    return "\n".join(L) + "\n"


def _load_corpus(path: Path) -> list[dict]:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return json.loads(path.read_text())["cases"]


def _corpus_label(path: Path) -> str:
    """Short label for the durable-results filename: `corpus_cal30.jsonl` -> `cal30`,
    `eval_set.json` -> `eval_set`."""
    stem = Path(path).stem
    return stem[len("corpus_"):] if stem.startswith("corpus_") else stem


def _load_results(path: str | Path) -> list[dict]:
    """Read a durable results file (jsonl) OR a scorecard.json (for convenience). Returns the flat
    per-case rows."""
    p = Path(path)
    if p.suffix == ".jsonl":
        return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    raw = json.loads(p.read_text())
    return raw if isinstance(raw, list) else raw.get("results", raw.get("rows", []))


def _run_offline(args, version: str) -> None:
    """OFFLINE recompute (+ optional gate) from a durable results file. Deterministic, no network/key.
    Exits nonzero on a gate breach so CI / `make eval` fails loudly."""
    results = _load_results(args.from_predictions)
    references = load_reference_grades(args.graded_reference) if args.graded_reference else {}
    res = score_from_predictions(results, references, version=version)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scorecard.md").write_text(render_scorecard(res))
    (out / "scorecard.json").write_text(json.dumps(
        {k: v for k, v in res.items() if k != "rows"} | {"rows": res["rows"]}, indent=2))
    print(render_scorecard(res))

    if not args.gate:
        print(f"[offline scorecard from {args.from_predictions} — no gate; pass --gate to enforce]")
        return

    from .gate import DEFAULT_THRESHOLDS_PATH, evaluate_gate, load_thresholds, render_gate
    thresholds = load_thresholds(args.gate_thresholds or DEFAULT_THRESHOLDS_PATH)
    gr = evaluate_gate(res, thresholds)
    print(render_gate(gr))
    sys.exit(gr.exit_code)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", help="path to a corpus json/jsonl; defaults to eval_set.json")
    ap.add_argument("--graded", action="store_true",
                    help="run the graded adversarial C4 (needs ANTHROPIC_API_KEY) + calibration")
    ap.add_argument("--graded-reference", dest="graded_reference",
                    help="human substantive_grade sidecar (jsonl/json keyed by case_id)")
    ap.add_argument("--recalibrate", action="store_true",
                    help="apply the fitted RB3 Platt confidence map (opt-in; fails closed if no "
                         "fitted map exists). Or set CITEVAL_RECALIBRATE=1")
    ap.add_argument("--recalibration-map", dest="recalibration_map",
                    help="path to calibration_map.json (default outputs/calibration_map.json)")
    ap.add_argument("--emit-calibration-sample", dest="emit_sample", nargs="?", type=int,
                    const=30, help="write a stratified N-case (default 30) human spot-check manifest")
    ap.add_argument("--limit", type=int, help="score only the first N cases (smoke test)")
    ap.add_argument("--fresh", action="store_true",
                    help="ignore any existing graded_predictions.jsonl and recompute from scratch")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="also print a line per triad round (or set CITEVAL_PROGRESS=1)")
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--from-predictions", dest="from_predictions",
                    help="OFFLINE: recompute the ENTIRE scorecard from a durable results jsonl "
                         "(objective axes + graded prediction per case). No pipeline / NCBI / key.")
    ap.add_argument("--gate", action="store_true",
                    help="after --from-predictions, compare to corpus/calibration/gate_thresholds.json "
                         "and exit nonzero on any breach (regression / floor / confident-wrong).")
    ap.add_argument("--gate-thresholds", dest="gate_thresholds",
                    help="path to gate_thresholds.json (default corpus/calibration/gate_thresholds.json)")
    args = ap.parse_args()

    # Stale-binary guard (WO-C4 §4): the very FIRST stderr line names the exact code producing this
    # run, so a scorecard is never mistaken for the output of a different/older binary.
    version = code_version()
    _log(f"[version] {version} {git_branch()}")

    # OFFLINE fast path (req #2/#3): recompute + optionally gate PURELY from a durable results file.
    # No corpus load, no pipeline, no NCBI, no ANTHROPIC_API_KEY. This is the loop we run every change.
    if args.from_predictions:
        _run_offline(args, version)
        return
    if args.gate:
        # The gate is an OFFLINE check (req #3): it grades a durable results file, not a live run.
        _log("[gate] --gate applies to the offline --from-predictions path and is IGNORED on a live "
             "run. Run `make eval` (or `python -m citeval.scorer --from-predictions <results.jsonl> "
             "--graded-reference <ref.jsonl> --gate`).")

    corpus_path = Path(args.corpus) if args.corpus else EVAL_PATH
    cases = _load_corpus(corpus_path)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # Emit-only mode: draw the human spot-check manifest (no grading, no model calls).
    if args.emit_sample is not None:
        manifest = sample_calibration_manifest(cases, n=args.emit_sample)
        (out / "calibration_sample.jsonl").write_text(
            "\n".join(json.dumps(m, ensure_ascii=False) for m in manifest) + "\n")
        print(f"[calibration sample] {len(manifest)} cases → {out}/calibration_sample.jsonl "
              f"(excluded {', '.join(RETRACTION_MISLABELS)}); a human fills `substantive_grade` "
              "blind to the agent.")
        return

    graded = graded_enabled(args.graded)
    references = load_graded_references(cases, args.graded_reference)
    verbose = args.verbose or os.environ.get("CITEVAL_PROGRESS", "").strip().lower() not in ("", "0", "false", "no", "off", "none")

    # RB3 post-hoc recalibration — opt-in, fails closed. Only applies to the graded path; the resolver
    # declines a missing/unfit map so the emitted confidence is never silently rescaled by a bad map.
    from .recalibrate import DEFAULT_MAP_PATH, resolve_recalibration
    from .slice_runner import recalibrate_enabled
    recal_fn, recal_note = resolve_recalibration(
        graded and recalibrate_enabled(args.recalibrate),
        args.recalibration_map or DEFAULT_MAP_PATH)
    if recal_note:
        _log(recal_note)

    res = score(cases, graded=graded, references=references, out_dir=out, limit=args.limit,
                fresh=args.fresh, progress=graded, verbose=verbose, version=version,
                recalibration=recal_fn, corpus_label=_corpus_label(corpus_path))
    (out / "scorecard.md").write_text(render_scorecard(res))
    (out / "scorecard.json").write_text(json.dumps(
        {k: v for k, v in res.items() if k != "rows"} | {"rows": res["rows"]}, indent=2))
    print(render_scorecard(res))
    print(f"[written to {out}/scorecard.md]")


if __name__ == "__main__":
    main()
