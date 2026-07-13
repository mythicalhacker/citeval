#!/usr/bin/env python3
"""Artifact 3 — the blind held-out tiebreak console.

reviews/05_innovation.md flags the "sided with citeval 4/6" claim as real data but
under-explained: 2 of the 6 independent verdicts are a *third* answer
(N/A — non-substantiating) rather than a clean agreement, so the 4/6 tally rests on
an interpretive call the submission doesn't fully spell out. This console spells it
out — it is the honest version of that scoreboard.

For each of the 6 disagreements (read verbatim from corpus/calibration/ext_tiebreak_6.json):
  citeval's C4 grade  vs  an external reference grade  vs  a BLIND independent third read.

The independent read is scored against a single stated rule and the result is made
countable three ways:
  * strict  — exact agreement with citeval only            -> 2/6
  * full    — nearest-on-ordinal + skeptical-N/A resolved  -> 4/6  (the claim)
  * losses  — cases where the independent read sides away   -> 2/6 (shown, not hidden)

The two honest losses (Ce03, Bs07) and the two interpretive wins (Bs03, Bp03) are
labelled as such. A toggle lets a viewer watch the headline number move between the
strict floor and the full tally, so the interpretive delta is explicit.

Emits docs/artifacts/tiebreak_console.html — self-contained.
"""
from __future__ import annotations

import _common as C


def is_na(g: str) -> bool:
    return g.strip().upper().startswith("N/A")


def sev_idx(g: str):
    return C.SEV_INDEX.get(g.strip())


def classify(c4: str, ext: str, ind: str) -> dict:
    """Score the blind independent read against citeval vs the external reference.

    Rule (stated on the page): on the 6-level ordinal, the independent read 'sides
    with' whichever verdict it is closer to. An off-scale 'N/A — non-substantiating'
    read means 'the paper does not back this claim', which sides with the MORE
    SKEPTICAL (higher-ordinal) of the two graded verdicts.
    """
    ci, ei = sev_idx(c4), sev_idx(ext)
    if is_na(ind):
        # side with the more skeptical graded verdict
        side = "citeval" if ci > ei else "external"
        exact = False
        d_cite = d_ext = None
        rule = "skeptical-N/A"
    else:
        ii = sev_idx(ind)
        d_cite, d_ext = abs(ii - ci), abs(ii - ei)
        side = "citeval" if d_cite < d_ext else ("external" if d_ext < d_cite else "tie")
        exact = (ii == ci)
        rule = "exact" if exact else "nearest-ordinal"
    if side == "citeval":
        kind = "clean-win" if exact else "interp-win"
    else:
        kind = "loss"
    return {"side": side, "kind": kind, "exact": exact, "rule": rule,
            "d_cite": d_cite, "d_ext": d_ext}


LADDER_LABELS = ["FS", "SwO", "PS", "TTM", "UFC", "CON"]  # short forms of the 6 levels
KIND_LABEL = {
    "clean-win": ("clean win", "b-good"),
    "interp-win": ("interpretive win", "b-accent"),
    "loss": ("honest loss", "b-crit"),
}


def mini_ladder(c4, ext, ind) -> str:
    """A 6-cell ordinal strip with markers for the three verdicts."""
    ci, ei = sev_idx(c4), sev_idx(ext)
    ii = None if is_na(ind) else sev_idx(ind)
    cells = []
    for k in range(6):
        marks = []
        if k == ci:
            marks.append('<span class="mk mk-c" title="citeval">C</span>')
        if k == ei:
            marks.append('<span class="mk mk-e" title="external ref">E</span>')
        if ii is not None and k == ii:
            marks.append('<span class="mk mk-i" title="independent">I</span>')
        cells.append(f'<div class="lcell" style="border-color:var(--{C.SEVERITY[k][1]})">'
                     f'<span class="lnum">{k}</span><span class="llab">{LADDER_LABELS[k]}</span>'
                     f'<div class="lmk">{"".join(marks)}</div></div>')
    na = ('<div class="lcell lcell-na"><span class="lnum">—</span><span class="llab">N/A</span>'
          '<div class="lmk"><span class="mk mk-i" title="independent">I</span></div></div>'
          if ii is None else "")
    return f'<div class="ladder">{"".join(cells)}{na}</div>'


def build() -> str:
    rows = C.read_json(C.CAL_DIR / "ext_tiebreak_6.json")
    # claim texts (all six live in the ext corpus)
    claims = {r["case_id"]: (r.get("claim_text_verbatim") or "")
              for r in C.read_jsonl(C.CAL_DIR / "corpus_cal_ext.jsonl")}

    for r in rows:
        r["cls"] = classify(r["c4"], r["ext_ref"], r["independent"])

    n = len(rows)
    clean = [r for r in rows if r["cls"]["kind"] == "clean-win"]
    interp = [r for r in rows if r["cls"]["kind"] == "interp-win"]
    losses = [r for r in rows if r["cls"]["kind"] == "loss"]
    strict = len(clean)
    full = len(clean) + len(interp)
    assert (strict, full, len(losses)) == (2, 4, 2), \
        f"tiebreak tally drifted: strict={strict} full={full} loss={len(losses)}"

    b = []
    b.append(C.hero(
        "Innovation · the receipt behind “4/6”",
        'The blind tiebreak console — <span style="color:var(--accent)">4/6</span>, with the '
        'interpretive calls and the losses on the table',
        'Six times, citeval’s grade disagreed with an external reference. A third, <b>blind</b> '
        'reader broke each tie. citeval came out ahead 4–2 — but two of those wins need an '
        'interpretive call, and two cases are honest losses. Here is exactly how the number is built, '
        'so you can lower it to 2/6 yourself if you don’t buy the calls.',
        kicker='All six rows read verbatim from <b>ext_tiebreak_6.json</b>; claims from '
               '<b>corpus_cal_ext.jsonl</b>. The tally is computed here, not asserted.'))

    # counting-rule control + live headline
    b.append('<div class="card scorecard">')
    b.append('<div class="score-head">'
             '<div class="bignum"><span id="tallyN">4</span><span class="den">/ 6</span></div>'
             '<div class="score-copy"><div class="score-title" id="tallyTitle">'
             'sided with citeval — interpretive calls resolved</div>'
             '<div class="score-sub" id="tallySub">2 clean agreements + 2 interpretive calls · '
             '2 honest losses shown below</div></div></div>')
    b.append('<div class="seg" role="tablist">'
             '<button class="segbtn on" data-mode="full" onclick="setMode(\'full\')">'
             'Full rule → 4/6</button>'
             '<button class="segbtn" data-mode="strict" onclick="setMode(\'strict\')">'
             'Strict: exact only → 2/6</button>'
             '<button class="segbtn" data-mode="loss" onclick="setMode(\'loss\')">'
             'Against citeval → 2/6</button></div>')
    b.append('<p class="small" style="margin-top:12px"><b>The rule.</b> On the six-level ordinal the '
             'blind read “sides with” whichever verdict it lands closer to. An off-scale '
             '<code>N/A — non-substantiating</code> read means <i>the paper doesn’t back this '
             'claim</i>, so it sides with the more skeptical (higher) of the two grades. '
             '<b>Strict</b> counts only exact agreement with citeval; <b>Full</b> adds nearest-ordinal '
             'and skeptical-N/A calls.</p>')
    b.append('<div class="legend"><span><span class="mk mk-c">C</span> citeval C4</span>'
             '<span><span class="mk mk-e">E</span> external reference</span>'
             '<span><span class="mk mk-i">I</span> blind independent</span></div>')
    b.append('</div>')

    # per-case console
    for r in rows:
        cls = r["cls"]
        klab, kcls = KIND_LABEL[cls["kind"]]
        counted = cls["kind"] in ("clean-win", "interp-win")
        claim = claims.get(r["case_id"], "").strip()
        b.append(f'<div class="card caserow" data-kind="{cls["kind"]}" '
                 f'data-counted="{"1" if counted else "0"}">')
        # header line
        b.append('<div class="caseh">'
                 f'<code class="cid">{C.esc(r["case_id"])}</code>'
                 f'<span class="badge {kcls}">{C.esc(klab)}</span>'
                 f'<span class="badge b-neu">depth: {C.esc(r["depth"])}</span>'
                 f'<span class="badge b-neu">C4 self-confidence {r["c4_conf"]:.2f}</span></div>')
        if claim:
            b.append(f'<p class="claimq">“{C.esc(claim)}”</p>')
        # three verdicts
        b.append('<div class="verds">'
                 f'<div class="verd"><div class="vk">citeval C4</div>{C.grade_badge(r["c4"])}</div>'
                 f'<div class="verd"><div class="vk">external ref '
                 f'<span class="prov">{C.esc(r["ext_ref_prov"])}</span></div>'
                 f'{C.grade_badge(r["ext_ref"])}</div>'
                 f'<div class="verd"><div class="vk">blind independent</div>'
                 f'{C.grade_badge(r["independent"])}</div></div>')
        # ladder + distances
        b.append(mini_ladder(r["c4"], r["ext_ref"], r["independent"]))
        if cls["d_cite"] is not None:
            dtxt = (f'independent is <b>{cls["d_cite"]}</b> rung'
                    f'{"" if cls["d_cite"]==1 else "s"} from citeval, '
                    f'<b>{cls["d_ext"]}</b> from the external ref')
        else:
            side = "citeval’s" if cls["side"] == "citeval" else "the external ref’s"
            dtxt = f'off-scale N/A — sides with the more skeptical read, which is {side}'
        b.append(f'<p class="dist small">{dtxt} → <b>sides with '
                 f'{"citeval" if cls["side"]=="citeval" else "external"}</b> '
                 f'({C.esc(cls["rule"])}).</p>')
        # rationale
        b.append(f'<p class="sec-note" style="margin-top:8px"><b>Blind reader’s reasoning:</b> '
                 f'{C.esc(r["ind_rationale"])}</p>')
        b.append('</div>')

    # honesty footer
    b.append('<div class="card"><h2>What the 4/6 does and doesn’t say</h2>'
             '<div class="grid3">')
    b.append(C.tile("Clean agreements", f"{len(clean)}",
                    "independent matched citeval’s exact grade: "
                    + ", ".join(f'<code>{r["case_id"]}</code>' for r in clean), "var(--good-ink)"))
    b.append(C.tile("Interpretive calls", f"{len(interp)}",
                    "nearest-ordinal / skeptical-N/A leaning citeval: "
                    + ", ".join(f'<code>{r["case_id"]}</code>' for r in interp), "var(--accent)"))
    b.append(C.tile("Honest losses", f"{len(losses)}",
                    "independent sided away from citeval: "
                    + ", ".join(f'<code>{r["case_id"]}</code>' for r in losses), "var(--critical)"))
    b.append('</div>')
    b.append('<p class="small" style="margin-top:14px">Restrict to exact agreement and only three '
             'cases resolve — <code>A11</code> and <code>A05</code> match citeval, <code>Bs07</code> '
             'matches the external ref — a <b>2–1</b> citeval lead, not a wash. The point of a '
             'held-out tiebreak isn’t a perfect score — it’s that an independent reader, blind to both '
             'sides, agrees with citeval more often than not, and that the two times it doesn’t are '
             'printed right here. One of those losses, <code>Bs07</code>, is the same case anchoring '
             '<i>contradicted</i> in the <a href="spin_spectrum.html">spin spectrum</a>.</p>')
    b.append('</div>')

    extra_css = """
.scorecard{padding:24px}
.score-head{display:flex;align-items:center;gap:20px;flex-wrap:wrap}
.bignum{font-size:64px;font-weight:850;letter-spacing:-.03em;line-height:.9;color:var(--accent)}
.bignum .den{font-size:26px;color:var(--muted);font-weight:700;margin-left:6px}
.score-title{font-size:17px;font-weight:750}
.score-sub{font-size:13.5px;color:var(--ink-2);margin-top:4px}
.seg{display:inline-flex;gap:4px;margin-top:18px;background:var(--surface-2);
  border:1px solid var(--hair);border-radius:10px;padding:4px;flex-wrap:wrap}
.segbtn{border:none;background:transparent;color:var(--ink-2);font-size:12.5px;font-weight:650;
  padding:7px 12px;border-radius:7px;cursor:pointer}
.segbtn:hover{background:var(--surface)}
.segbtn.on{background:var(--accent);color:#fff}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin-top:16px;font-size:12.5px;color:var(--ink-2)}
.mk{display:inline-flex;align-items:center;justify-content:center;width:19px;height:19px;border-radius:6px;
  font-size:11px;font-weight:800;color:#fff;vertical-align:middle}
.mk-c{background:var(--accent)} .mk-e{background:var(--muted)} .mk-i{background:var(--sev5)}
.caserow{transition:opacity .18s}
.caserow.dim{opacity:.34}
.caseh{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.cid{font-size:15px;font-weight:800;background:var(--code-bg);padding:2px 9px;border-radius:7px}
.claimq{color:var(--ink-2);font-size:14.5px;margin:12px 0 4px;font-style:italic}
.verds{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:14px 0}
@media (max-width:640px){.verds{grid-template-columns:1fr}}
.verd{background:var(--surface-2);border:1px solid var(--hair);border-radius:10px;padding:11px 13px}
.vk{font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);font-weight:700;
  margin-bottom:8px}
.vk .prov{text-transform:none;letter-spacing:0;display:block;margin-top:2px}
.ladder{display:flex;gap:5px;margin:10px 0 4px;flex-wrap:wrap}
.lcell{flex:1;min-width:52px;background:var(--surface-2);border:1px solid var(--hair);
  border-top:3px solid;border-radius:8px;padding:6px 4px;text-align:center}
.lcell-na{border-top-color:var(--muted);border-style:dashed;background:transparent}
.lnum{display:block;font-size:11px;color:var(--muted);font-weight:700}
.llab{display:block;font-size:10.5px;color:var(--ink-2);font-weight:650;margin-top:1px}
.lmk{display:flex;gap:3px;justify-content:center;min-height:21px;margin-top:5px}
.dist{margin-top:6px}
"""
    extra_js = """
<script>
function setMode(m){
  document.querySelectorAll('.segbtn').forEach(function(x){x.classList.toggle('on',x.dataset.mode===m);});
  var conf={
    full:{n:4,t:'sided with citeval — interpretive calls resolved',
      s:'2 clean agreements + 2 interpretive calls · 2 honest losses shown below',keep:['clean-win','interp-win']},
    strict:{n:2,t:'exact agreement with citeval only',
      s:'the strict floor: of the 3 cases where the blind read exactly matches a reference (A11, A05 → citeval; Bs07 → external), citeval leads 2–1',keep:['clean-win']},
    loss:{n:2,t:'the independent read sided away from citeval',
      s:'the two honest losses — printed, not hidden',keep:['loss']}
  }[m];
  document.getElementById('tallyN').textContent=conf.n;
  document.getElementById('tallyTitle').textContent=conf.t;
  document.getElementById('tallySub').textContent=conf.s;
  document.querySelectorAll('.caserow').forEach(function(r){
    r.classList.toggle('dim',conf.keep.indexOf(r.dataset.kind)<0);
  });
}
</script>
"""
    return C.page("tiebreak", "Blind held-out tiebreak console", "".join(b),
                  extra_css=extra_css, extra_js=extra_js)


if __name__ == "__main__":
    out = C.write_page("tiebreak_console.html", build())
    print(f"wrote {out}  ({out.stat().st_size:,} bytes)")
