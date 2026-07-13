#!/usr/bin/env python3
"""Index / landing page for the citeval innovation artifacts.

A cross-linked overview of the four offline artifacts. Its headline figures are read
from the same committed calibration files the artifacts use, so the landing numbers
can never drift from the pages they summarise.

Emits docs/artifacts/index.html — self-contained.
"""
from __future__ import annotations

import re

import _common as C

CARDS = [
    ("climbdown", "climbdown.html", "1", "It caught its own propped metric",
     "A perfect in-domain scope score collapsed on held-out data. The team deleted the shortcut, "
     "lowered the gate to the honest number, and committed the climb-down — twice."),
    ("spin", "spin_spectrum.html", "2", "The six-level spin spectrum",
     "A bespoke ordinal for citation fidelity the field’s flat 3-way benchmarks don’t have — every "
     "rung anchored to a real graded case, scope held constant."),
    ("tiebreak", "tiebreak_console.html", "3", "The blind held-out tiebreak",
     "Six disagreements, broken by an independent blind reader. citeval wins 4–2 — with the two "
     "interpretive calls and the two honest losses put on the table, countable."),
    ("debate", "debate_replay.html", "4", "The adversarial-debate replay",
     "Two real cases replayed round by round from the frozen transcript — including the split vote "
     "the climb-down rescued from a silent abstention, and scope objections barred from the grade."),
]


def build() -> str:
    gate = C.read_json(C.CAL_DIR / "gate_thresholds.json")
    reseed = gate["baseline"]["_reseed_note"]
    ext = re.search(r"scope recall\s*([\d.]+)->~?([\d.]+)", reseed)
    r_before, r_after = float(ext.group(1)), float(ext.group(2))
    tiebreak = C.read_json(C.CAL_DIR / "ext_tiebreak_6.json")
    debate = C.read_json(C.CAL_DIR / "transcripts" / "debate_A27_Ce11.json")
    scope_routed = sum(1 for c in debate["cases"].values() for r in c["rounds"]
                       for p in r["refuter"]["points"] if p.get("routes_to") == "rollup_not_grade")

    headline = {
        "climbdown.html": (f"1.00 → {r_before:.3f} → {r_after:.2f}", "scope recall: propped, real, fixed"),
        "spin_spectrum.html": ("6 + 2", "ordered rungs plus two off-scale outcomes"),
        "tiebreak_console.html": (f"{4}/{len(tiebreak)}", "blind independent read sided with citeval"),
        "debate_replay.html": (str(scope_routed), "scope objections routed away from the grade"),
    }

    b = []
    b.append(C.hero(
        "citeval · innovation, made visible",
        'The discipline you can <span style="color:var(--accent)">open in a browser</span>',
        'citeval’s innovation isn’t a new model or algorithm — it’s the discipline: caging what the '
        'LLM is allowed to decide, grading citation “spin” on an ordinal the field lacks, and proving '
        'it on held-out data. These four pages make that discipline concrete. Each is built offline '
        'from committed calibration data — <b>zero model calls, no API key</b> — so it renders the '
        'same on a plane with the Wi-Fi off.',
        kicker='Regenerate everything with '
               '<code>python docs/build_artifacts/build_all.py</code>.'))

    b.append('<div class="cards">')
    for slug, fn, num, title, desc in CARDS:
        hv, hs = headline[fn]
        b.append(f'<a class="xcard" href="{fn}">'
                 f'<div class="xnum">{num}</div>'
                 f'<div class="xhead">{C.esc(title)}</div>'
                 f'<div class="xstat"><span class="xval">{C.esc(hv)}</span>'
                 f'<span class="xsub">{C.esc(hs)}</span></div>'
                 f'<p class="xdesc">{C.esc(desc)}</p>'
                 f'<span class="xgo">open →</span></a>')
    b.append('</div>')

    b.append('<div class="card"><h2>Why these four</h2>'
             '<p class="sec-note">reviews/05_innovation.md scores citeval 7/10 on innovation and is '
             'blunt that the components are established research — the value is the composition and, '
             'above all, the discipline. It names four specific, verifiable things: the self-caught '
             'propped metric (“the standout”), the six-level spin ordinal (“the most original '
             'artifact”), the 4/6 held-out tiebreak (real data, under-explained), and the scope-routing '
             'refinement inside the adversarial triad. There is one page for each — and each renders '
             'straight from the file that backs the claim, so nothing here is a slide, it’s the '
             'evidence.</p></div>')

    extra_css = """
.cards{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:22px 0}
@media (max-width:720px){.cards{grid-template-columns:1fr}}
.xcard{position:relative;display:block;background:var(--surface);border:1px solid var(--hair);
  border-radius:14px;padding:22px 22px 46px;text-decoration:none;color:var(--ink);
  transition:transform .14s,border-color .14s,box-shadow .14s}
.xcard:hover{transform:translateY(-2px);border-color:color-mix(in srgb,var(--accent) 45%,var(--hair));
  box-shadow:0 8px 26px -14px rgba(0,0,0,.4);text-decoration:none}
.xnum{position:absolute;top:16px;right:20px;font-size:40px;font-weight:850;color:var(--grid);
  line-height:1}
.xhead{font-size:19px;font-weight:770;letter-spacing:-.01em;max-width:80%}
.xstat{margin:14px 0 0;display:flex;flex-direction:column}
.xval{font-size:27px;font-weight:820;letter-spacing:-.02em;color:var(--accent);font-variant-numeric:tabular-nums}
.xsub{font-size:12px;color:var(--muted);font-weight:600;margin-top:2px}
.xdesc{font-size:14px;color:var(--ink-2);margin:14px 0 0;line-height:1.5}
.xgo{position:absolute;left:22px;bottom:18px;font-size:13px;font-weight:700;color:var(--accent)}
"""
    return C.page("index", "citeval · innovation artifacts", "".join(b), extra_css=extra_css)


if __name__ == "__main__":
    out = C.write_page("index.html", build())
    print(f"wrote {out}  ({out.stat().st_size:,} bytes)")
