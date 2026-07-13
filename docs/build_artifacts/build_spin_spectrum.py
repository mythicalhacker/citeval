#!/usr/bin/env python3
"""Artifact 2 — the six-level "spin spectrum" explainer.

Per reviews/05_innovation.md, citeval's most original artifact is a bespoke ordinal
taxonomy for citation *spin* that the field's benchmarks don't have (SciFact / FEVER
are flat 3-way; GRADE grades evidence quality, not citation fidelity). This page lays
out all six levels, best -> worst, each with:

  * the authoritative rubric definition, parsed from the committed decider packet
    (corpus/calibration/spotcheck/decider_packet.md);
  * a REAL anchor case pulled from graded_reference_v2 / graded_reference_ext, with
    its verbatim decisive span, claim gist, grader confidence and provenance;
  * a per-level count across the whole 75-case corpus (30 calibration + 45 held-out).

The honest twist the page surfaces: level 3, `technically-true-but-misleading`, is
DEFINED but has **zero** assignments anywhere — not in either reference, not even in
the C4 model's own predictions. The reference grader never escalates a case that far,
so citeval reports an empty rung rather than manufacturing one. The nearest real case
(Ch03) is a genuine multi-part split graded partially-supported instead.

Emits docs/artifacts/spin_spectrum.html — self-contained.
"""
from __future__ import annotations

import re

import _common as C

# One real anchor per level. Levels with real graded cases point at a case id;
# level 3 is intentionally empty (see module docstring) and shows its nearest neighbour.
ANCHORS = {
    0: {"case": "Bs12", "src": "v2"},
    1: {"case": "A27", "src": "v2", "xref": ("debate_replay.html", "replay this debate")},
    2: {"case": "Ch03", "src": "v2"},
    3: {"case": None, "nearest": "A17", "nearest_src": "v2"},
    4: {"case": "A25", "src": "v2", "xref": ("climbdown.html", "the fabricated-attribution receipt")},
    5: {"case": "Bs07", "src": "ext", "xref": ("tiebreak_console.html", "an honest loss in the tiebreak")},
}

# case ids collide across the two corpora (e.g. Bs07, Ch03 are DIFFERENT papers in
# corpus_cal30 vs corpus_cal_ext), so claim text MUST be keyed by (source, case_id):
# a v2/ext grade record is paired only with the claim from its own corpus.
CLAIM_SOURCE = {"v2": "corpus_cal30.jsonl", "ext": "corpus_cal_ext.jsonl"}


def _parse_rubric(md_text: str) -> dict[str, str]:
    """Extract the '1. **grade** — definition' lines from the decider packet."""
    out = {}
    for m in re.finditer(r"^\s*\d+\.\s+\*\*([a-z\-]+)\*\*\s*[—-]+\s*(.+?)(?=\n\s*\d+\.\s+\*\*|\n\nTwo off-scale)",
                          md_text, re.S | re.M):
        grade = m.group(1).strip()
        definition = re.sub(r"\s+", " ", m.group(2)).strip()
        out[grade] = definition
    return out


def build() -> str:
    packet = (C.CAL_DIR / "spotcheck" / "decider_packet.md").read_text()
    rubric = _parse_rubric(packet)
    for g, _ in C.SEVERITY:
        assert g in rubric, f"rubric definition for {g!r} not found in decider_packet.md"

    v2 = {r["case_id"]: r for r in C.read_jsonl(C.CAL_DIR / "graded_reference_v2.jsonl")}
    ext = {r["case_id"]: r for r in C.read_jsonl(C.CAL_DIR / "graded_reference_ext.jsonl")}
    ref_by_src = {"v2": v2, "ext": ext}

    # claim lookup keyed by (source, case_id) — NOT merged, because ids collide across
    # the two corpora (Bs07 is a lipid study in ext but a PDAC paper in cal30).
    claims_by_src = {
        src: {r["case_id"]: (r.get("claim_text_verbatim") or r.get("claim_text") or "")
              for r in C.read_jsonl(C.CAL_DIR / fn)}
        for src, fn in CLAIM_SOURCE.items()
    }

    # per-level counts across the full 75-case corpus (30 + 45)
    counts = [0] * 6
    for store in (v2, ext):
        for r in store.values():
            g = r["substantive_grade"]
            if g in C.SEV_INDEX:
                counts[C.SEV_INDEX[g]] += 1
    total_graded = sum(counts)
    assert counts[3] == 0, "level-3 unexpectedly populated"
    maxc = max(counts) or 1

    b = []
    b.append(C.hero(
        "Innovation · the most original artifact",
        'The spin spectrum: <span style="color:var(--accent)">six ordered ways</span> a real paper '
        'can fail a citation',
        'SciFact, FEVER and MultiVerS grade citations three flat ways (supports / refutes / not '
        'enough info). GRADE grades how good the <i>evidence</i> is, not whether the citation is '
        'honest. citeval grades <b>citation fidelity</b> on a six-level ordinal — and holds scope '
        'constant so “wrong species” never contaminates “wrong substance.”',
        kicker='Definitions parsed from <b>decider_packet.md</b>; every anchor case and count read '
               'from <b>graded_reference_v2</b> + <b>graded_reference_ext</b> at build time.'))

    # The one rule
    b.append('<div class="callout"><b>The rule that makes the axis clean.</b> Grade <b>substance '
             'only</b>. A mouse-only or retracted paper can still be <i>fully-supported</i> on '
             'substance if its finding backs the claim — species, population, dose and retraction are '
             'scored on <a href="climbdown.html">separate axes</a>. That structural separation is why '
             'a “spin” grade means one thing and one thing only.</div>')

    # distribution strip
    n_offscale = 75 - total_graded
    b.append(f'<div class="card"><h2>Where the cases land — {total_graded} of 75 on the ladder</h2>')
    b.append(f'<p class="sec-note">The 30-case calibration set and the 45-case held-out set carry 75 '
             f'graded cases; {total_graded} land on the ordinal ladder and {n_offscale} are off-scale '
             '(NOT_ENOUGH_INFO or non-substantiating). The shape is the discipline: the mass sits near '
             '“supported,” the harshest grades are rare, and one rung is empty on purpose.</p>')
    for i, (grade, var) in enumerate(C.SEVERITY):
        pct = counts[i] / maxc * 100
        empty = ' style="opacity:.55"' if counts[i] == 0 else ""
        note = ' &larr; defined, never assigned' if counts[i] == 0 else ""
        b.append(f'<div class="bar-row"{empty}><div class="rl mono" style="font-size:12px">'
                 f'{i} · {C.esc(grade)}</div>'
                 f'<div class="bar-track"><div class="bar-fill" '
                 f'style="width:{max(pct,1.5):.1f}%;background:var(--{var})"></div></div>'
                 f'<div class="rv tnums">{counts[i]}{note}</div></div>')
    b.append('</div>')

    # the ladder — one card per level
    b.append('<div class="card"><h2>The ladder, best → worst</h2>'
             '<p class="sec-note">First boundary test that fires wins. Each rung shows the rubric '
             'definition and a real anchor case you can verify against the cited paper.</p></div>')

    for i, (grade, var) in enumerate(C.SEVERITY):
        a = ANCHORS[i]
        b.append(f'<div class="card" style="border-left:5px solid var(--{var})">')
        b.append(f'<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">'
                 f'<span class="badge" style="background:var(--{var});color:#fff;font-size:15px;'
                 f'padding:5px 12px;font-weight:800">{i}</span>'
                 f'<h2 style="font-size:19px;margin:0">{C.esc(grade)}</h2>'
                 f'<span class="badge b-neu">{counts[i]} case'
                 f'{"" if counts[i]==1 else "s"} in corpus</span></div>')
        b.append(f'<p class="sec-note" style="margin-top:10px"><b>Rubric:</b> {C.esc(rubric[grade])}</p>')

        if a["case"] is None:
            # level 3 — the honest empty rung
            near = ref_by_src[a["nearest_src"]][a["nearest"]]
            assert C.SEV_INDEX.get(near["substantive_grade"]) == i - 1, \
                "level-3 nearest case must sit exactly one rung up (partially-supported)"
            b.append('<div class="callout warn" style="margin-bottom:0"><b>Deliberately empty.</b> '
                     'Zero of 30 calibration cases, zero of 45 held-out cases, and zero of the C4 '
                     'model’s own predictions land here. Pure “literally-true-but-misleading” framing '
                     'is the hardest call to make blind, and the independent grader never escalates a '
                     'case this far. citeval reports the empty rung rather than inventing one.<br><br>'
                     f'<b>The closest any real case comes — <code>{C.esc(a["nearest"])}</code>:</b> '
                     f'{C.esc(near["rationale"])} '
                     'That has the flavour of this level — a claim that sounds precise and defensible — '
                     f'but the decider placed it one rung up at '
                     f'{C.grade_badge(near["substantive_grade"])}, not the harshest '
                     'literally-true-but-misleading reading.</div>')
        else:
            rec = ref_by_src[a["src"]][a["case"]]
            claim = claims_by_src[a["src"]].get(a["case"], "")
            xref = ""
            if "xref" in a:
                href, txt = a["xref"]
                xref = f' &middot; <a href="{href}">{C.esc(txt)} &rarr;</a>'
            b.append('<table class="dt" style="margin-top:6px"><tbody>')
            b.append(f'<tr><th style="width:118px">Anchor</th><td><code>{C.esc(a["case"])}</code> '
                     f'<span class="badge b-neu">grader confidence: {C.esc(rec["grader_confidence"])}</span>'
                     f'{xref}</td></tr>')
            if claim:
                b.append(f'<tr><th>The claim</th><td style="color:var(--ink-2)">'
                         f'“{C.esc(claim.strip())}”</td></tr>')
            b.append(f'<tr><th>Why this rung</th><td>{C.esc(rec["rationale"])}</td></tr>')
            if rec.get("decisive_span"):
                b.append('<tr><th>Decisive span<br><span class="prov">verbatim from the cited '
                         f'paper</span></th><td><div class="span">{C.esc(rec["decisive_span"])}'
                         '</div></td></tr>')
            b.append(f'<tr><th>Provenance</th><td class="prov">{C.esc(rec["grade_provenance"])} &middot; '
                     f'graded_reference_{a["src"]}.jsonl</td></tr>')
            b.append('</tbody></table>')
        b.append('</div>')

    # off-scale
    b.append('<div class="card"><h2>Two off-scale outcomes (never on the ladder)</h2>'
             '<div class="grid2">'
             '<div class="tile"><div class="lab">N/A — non-substantiating</div>'
             '<div class="sub" style="margin-top:8px">The citation is a method, dataset, tool, or '
             'background pointer — not evidence for a knowledge claim. It is <b>not</b> a bad grade; '
             'it is “this isn’t the kind of citation we grade.” Two independent verdicts in the '
             '<a href="tiebreak_console.html">held-out tiebreak</a> are exactly this.</div></div>'
             '<div class="tile"><div class="lab">NOT_ENOUGH_INFO</div>'
             '<div class="sub" style="margin-top:8px">The available text is genuinely insufficient to '
             'place a grade — an honest abstention, distinct from any grade. It weights confidence, it '
             'doesn’t fake one.</div></div>'
             '</div></div>')

    b.append('<hr class="rule"><p class="small">Six ordered rungs plus two honest off-ramps, holding '
             'scope constant — a resolution the field’s flat 3-way benchmarks can’t express, and the '
             'reason citeval can tell <i>overreach</i> from <i>contradiction</i> instead of lumping '
             'both under “refutes.”</p>')

    return C.page("spin", "The six-level spin spectrum", "".join(b))


if __name__ == "__main__":
    out = C.write_page("spin_spectrum.html", build())
    print(f"wrote {out}  ({out.stat().st_size:,} bytes)")
