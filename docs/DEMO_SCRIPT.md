# citeval — a 2–3 minute demo walkthrough

*For a judge or reviewer. The whole path runs **with no API key** — the web app is mock-backed by
default and the offline proof pages need nothing at all. A key is required only to grade a brand-new
claim live.* Full writeup: [`SUBMISSION.md`](SUBMISSION.md) · headline numbers reproduce offline with
`make eval`.

**One line on what citeval is:** a referee for a single scientific citation — one claim, one cited
paper, one question: *does the paper actually support the claim?* It answers across three axes
(retraction · species/population scope · a six-level substantive-support grade), and every verdict
carries a confidence **tier** and a **provenance** label (metadata-grounded vs. model-inferred).

---

## Before you start (pick one)

```bash
# A · the live UI, mock-backed — no key, full five-view app
cd web && npm install && npm run dev          # http://localhost:5173
#   (optional, for real cached verdicts over HTTP: in another terminal,
#    cd server && pip install -r requirements.txt && python main.py)

# B · zero-build — just open a file in a browser
open web/standalone/app.html                  # the same UI, no toolchain

# C · fully static, no server, no build — the offline proof pages
open docs/showcase.html                        # four worked cases
open docs/artifacts/index.html                 # the four innovation artifacts
```

The five tabs, left to right: **Verify · Batch · Showcase · Verdict · Methodology.**

---

## The walkthrough

### 0:00 — Showcase: the headline, then what it caught  *(tab: Showcase)*

Open on the **Showcase** tab. The masthead carries the four numbers the project stands on:
**κ 0.90** (graded axis, N=27 vs. an independent reference), **retraction P/R 1.00** (in-domain *and*
on a 45-case held-out set), **scope recall** (shown honestly in amber, not hidden), and **ECE 0.08**
(recalibrated, down from 0.32 raw).

Then scroll the four worked cases — this is *what it caught*:

- **A fabricated attribution** (case A25): a sentence crediting a named researcher with a finding the
  cited paper never contained. All three independent graders returned *unsupported-for-the-claim* at
  full confidence.
- **Retracted-but-otherwise-supported** (case A02): the science checks out, but the paper is
  retracted — so **metadata overrides the model** and the citation cannot stand.
- **Right substance, wrong species** (case Bs05): a mouse study cited for a human claim — the
  species mismatch rides its own axis, so it never silently depresses the substantive grade.
- **A clean, high-confidence match** (case Ch13): human study, human claim, grade *fully-supported*.

> Say: *"Building the corpus, the retraction check overruled our own answer key — three citations we'd
> labelled clean pointed to genuinely retracted papers. That's the thesis in one moment: ground every
> objective verdict in external structured truth, and let the metadata overrule the model — even when
> the model is us."*

### 0:40 — Verify: watch one citation get graded  *(tab: Verify)*

Switch to **Verify** and run a cached case. Watch the **five-stage stepper** advance
(ingest → retraction → scope → adjudicate → report), the **adversarial debate** unfold card by card —
a *supporter* argues the paper backs the claim, a *refuter* argues it doesn't, and a *critic*
adjudicates from a verbatim decisive span — and the **cost / ETA** tick up live as the
self-consistency rounds resample.

> Say: *"The grade isn't one model's opinion — it's an order-randomized, identity-blinded triad run to
> consensus. Confidence is the triad's agreement across rounds, then recalibrated. It's deliberately
> slow and costly: this is a deep checker for the one citation that matters, not a bulk screener."*

### 1:15 — The gate padlock: metadata overrides model  *(Verify / Verdict, a retraction case)*

Open a retraction case (e.g. A02). The **gate badge** shows a **closed padlock** — a *fired* gate.
Even though the substantive triad graded the science *fully-supported*, the retraction is a structured
record, so the overall verdict is forced to **NOT SUPPORTED AS STATED — RETRACTED**. The model does not
get a vote it can use to overturn a database fact.

> Say: *"This is invariant #1, made visible: a model value never overturns a structured record. The
> padlock is that rule firing."*

### 1:45 — Batch: many citations at once  *(tab: Batch)*

Switch to **Batch**. Several papers run **in parallel**, each with its own live stepper and verdict,
and a **running aggregate cost** across the whole batch. This is the "screen a reference list" shape —
same guarantees per citation, fanned out.

### 2:15 — The honesty beats  *(Showcase / Verdict / the artifacts)*

The point of the design is that it **fails safe, not confident-wrong.** Three things to land:

1. **It abstains rather than bluff.** On cases that genuinely can't be graded (metadata-only, or a
   background citation making no substantive claim), the graded axis returns *no grade* instead of
   inventing one — coverage **0.96**, with **zero confident-but-wrong** grades in the whole set.
2. **The reference is honest about itself.** The calibration reference is an *independent AI reviewer*
   — independent of the grader (the anti-circularity property that matters), but **human spot-check is
   still pending**, and the UI/writeup say so rather than claiming a gold standard.
3. **It caught its own propped metric.** Open
   [`artifacts/climbdown.html`](artifacts/climbdown.html) (*Climb-down*): a scope score we had reported as
   a perfect **1.00** collapsed to **~0.294** on held-out data. We deleted the shortcut, lowered the
   gate to the honest number (**0.71** held-out, **0.909** in-domain), and committed the climb-down —
   twice. A grounded-and-measured system has to be willing to catch itself.

> Close: *"Three axes, every verdict tiered and provenance-stamped, grounded in external records and
> measured on data we never tuned on — including a held-out test that caught us. We're not trying to
> out-scale Scite; we're trying to be the checker you trust on the one citation that matters."*

---

## No-key / offline fallback path (if the UI won't start)

Everything above is visible with **no server, no build, no key** — the same cases, rendered from
committed data:

- [`docs/showcase.html`](showcase.html) — the four worked cases (Showcase beat).
- [`docs/artifacts/index.html`](artifacts/index.html) — the four innovation artifacts, including:
  - *Climb-down* (`climbdown.html`) — the self-caught propped metric (honesty beat #3).
  - *Spin spectrum* (`spin_spectrum.html`) — the six-level ordinal, each rung a real graded case.
  - *Blind tiebreak* (`tiebreak_console.html`) — the 4/6 held-out adjudication, losses shown.
  - *Debate replay* (`debate_replay.html`) — the adversarial triad replayed from a frozen transcript.
- Over HTTP with the server running but still **no key**: `GET /api/showcase` returns the same four
  cached verdicts as real API payloads.

Reproduce the in-domain headline numbers directly: `make eval` (offline, deterministic, < 2s).

---

*Numbers in this script trace to `make eval` and the committed calibration corpus; the honest
limitations (weak population-scope recall, small N, the not-yet-human-certified reference) are in
[`SUBMISSION.md`](SUBMISSION.md) § Honest limitations and are not glossed here.*
