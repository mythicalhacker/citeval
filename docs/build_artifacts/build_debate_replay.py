#!/usr/bin/env python3
"""Artifact 4 — the adversarial-debate replay.

Renders the committed W0 fixture corpus/calibration/transcripts/debate_A27_Ce11.json
into a standalone page: the supporter / refuter / critic triad, replayed round by
round for two REAL calibration cases, with the current-code aggregation outcome.

Why these two cases earn a page (per reviews/05_innovation.md):
  * A27 — a RETRACTED paper cited for a mechanism over-reach. The triad reaches a
    UNANIMOUS supported-with-overreach in 4 rounds and early-stops. It shows the
    scope/retraction axes held constant: the substantive grade is computed on its
    own merits while the retraction axis gates `overall` separately.
  * Ce11 — an obesity/allergy over-reach whose 7-round vote is an adjacent-only
    split (4 supported-with-overreach / 3 partially-supported). Its PRE-REGRADE
    snapshot ABSTAINED (NOT_ENOUGH_INFO); replaying the SAME committed rounds through
    the fixed aggregation now grades it correctly at an honest LOW tier. This is the
    confident-wrong tail the climb-down (commit 8aa0ff6) cleared — cross-linked.

The verified mechanism the review singles out is made visible: refuter objections
that argue SCOPE carry routes_to="rollup_not_grade" and are structurally prevented
from moving the substantive grade. Those points are flagged in the transcript.

Emits docs/artifacts/debate_replay.html — self-contained.
"""
from __future__ import annotations

import _common as C

GT_BADGE = {
    "RETRACTED": ("b-crit", "retracted source"),
    "SUPPORTED": ("b-good", "supported (control)"),
    "SCOPE_MISMATCH": ("b-warn", "scope mismatch"),
}
DISTORTION_LABEL = {
    "mechanism_mismatch": "mechanism mismatch",
    "cherry_picking": "cherry-picking",
    "direction_reversal": "direction reversal",
    "over_certainty": "over-certainty",
    "over_generalization": "over-generalization",
    "no_evidence_for_support": "no evidence",
}


def conf_bar(conf: float, var: str) -> str:
    return (f'<div class="cbar"><div class="cbar-f" style="width:{conf*100:.0f}%;'
            f'background:var(--{var})"></div></div>')


def render_case(cid: str, case: dict) -> str:
    cfg = case["config"]
    cited = case["cited"]
    rep = case["replay"]
    fr = case["frozen_prediction"]
    gt_cls, gt_txt = GT_BADGE.get(case["ground_truth_label"], ("b-neu", case["ground_truth_label"]))
    critic_cost = sum((r["usage"].get("critic_output_cost_usd") or 0) for r in case["rounds"])
    n_scope_routed = sum(1 for r in case["rounds"] for p in r["refuter"]["points"]
                         if p.get("routes_to") == "rollup_not_grade")

    o = [f'<section class="casewrap" id="case-{cid}" data-case="{cid}">']

    # ---- header ----
    o.append('<div class="card">')
    o.append(f'<div class="caseh"><code class="cid">{cid}</code>'
             f'<span class="badge {gt_cls}">{C.esc(gt_txt)}</span>'
             f'<span class="badge b-neu">evidence: {C.esc(case["evidence_depth"])}</span>'
             f'<span class="badge b-neu">{cfg["rounds_run"]} rounds'
             f'{" · early-stopped" if cfg["early_stopped"] else " · ran full"}</span></div>')
    o.append(f'<p class="claimq" style="margin-top:14px"><span class="ql">Claim under test</span>'
             f'“{C.esc(case["claim"].strip())}”</p>')
    doi = cited.get("doi")
    doi_l = (f' · doi <a href="https://doi.org/{C.esc(doi)}">{C.esc(doi)}</a>') if doi else ""
    o.append(f'<p class="citedp"><span class="ql">Cited paper</span>'
             f'<i>{C.esc(cited["title"])}</i> — {C.esc(cited["journal"])} · '
             f'pmid <a href="https://pubmed.ncbi.nlm.nih.gov/{C.esc(cited["pmid"])}/">'
             f'{C.esc(cited["pmid"])}</a>{doi_l}</p>')
    if case.get("retraction_note"):
        o.append(f'<div class="callout crit" style="margin:14px 0 0"><b>Retraction axis (separate):</b> '
                 f'{C.esc(case["retraction_note"])}</div>')
    # config strip
    o.append('<div class="cfgstrip">'
             f'<span><b>{C.esc(cfg["model"])}</b> on every call</span>'
             f'<span>advocate temp {cfg["advocate_temperature"]}</span>'
             f'<span>critic temp {cfg["critic_temperature"]}</span>'
             f'<span>self-consistency ×{cfg["self_consistency_rounds"]}</span></div>')
    if cfg.get("early_stop_reason"):
        o.append(f'<p class="small" style="margin-top:8px"><b>Early stop:</b> '
                 f'{C.esc(cfg["early_stop_reason"])}</p>')
    o.append('</div>')

    # ---- verdict-evolution rail ----
    o.append('<div class="card"><h3 style="margin-top:0">How the critic’s vote evolved</h3>'
             '<div class="rail">')
    for r in case["rounds"]:
        g = r["critic_grade"]
        var = C.SEV_VAR.get(g, "muted")
        o.append(f'<a class="railcell" href="#r-{cid}-{r["round"]}" '
                 f'style="border-top-color:var(--{var})">'
                 f'<span class="rr">R{r["round"]}</span>'
                 f'<span class="rg" style="color:var(--{var})">{C.esc(g)}</span>'
                 f'<span class="rc tnums">conf {r["critic_confidence"]:.2f} · '
                 f'agree {r["agreement"]:.2f}</span></a>')
    o.append('</div><p class="small" style="margin-top:10px">'
             + ("Flat and unanimous — every round the same grade, so the run early-stops."
                if cfg["early_stopped"] else
                "It oscillates: an adjacent-only split the aggregation has to resolve — which is "
                "exactly why the honest tier lands LOW.")
             + '</p></div>')

    # ---- rounds ----
    for r in case["rounds"]:
        crit = r["critic"]
        g = crit["grade"]
        var = C.SEV_VAR.get(g, "muted")
        o.append(f'<div class="card round" id="r-{cid}-{r["round"]}" style="border-left:5px solid var(--{var})">')
        o.append(f'<div class="roundh"><span class="rnum">Round {r["round"]}</span>'
                 f'{C.grade_badge(g)}'
                 f'<span class="badge b-neu">critic confidence {crit["confidence"]:.2f}</span>'
                 f'<span class="badge b-neu">boundary test: {C.esc(crit["boundary_test_fired"])}</span>'
                 f'<span class="badge {"b-crit" if r["refuter"]["refuter_grade_pressure"]=="strong" else "b-warn"}">'
                 f'refuter pressure: {C.esc(r["refuter"]["refuter_grade_pressure"])}</span></div>')

        # critic payload (always visible)
        o.append('<div class="critic">')
        o.append(f'<div class="rolek">Critic — the grader</div>')
        o.append(f'<p class="crit-reason">{C.esc(crit["reasoning"])}</p>')
        if crit.get("grade_rationale_last"):
            o.append(f'<p class="small"><b>Boundary call:</b> {C.esc(crit["grade_rationale_last"])}</p>')
        for sp in crit.get("decisive_spans", []):
            txt = sp if isinstance(sp, str) else (sp.get("quote") or sp.get("text") or str(sp))
            o.append(f'<div class="span">{C.esc(txt)}</div>')
        o.append('</div>')

        # supporter / refuter (collapsible, complete)
        sp_pts = r["supporter"]["points"]
        rf_pts = r["refuter"]["points"]
        o.append(f'<details class="adv sup"><summary><span class="rolek sup-k">Supporter</span> '
                 f'{len(sp_pts)} point{"" if len(sp_pts)==1 else "s"} for the claim</summary>')
        for p in sp_pts:
            o.append(f'<div class="pt"><div class="span">{C.esc(p.get("quote",""))}</div>'
                     f'<p class="pt-r">{C.esc(p.get("rationale",""))}</p>'
                     + (f'<p class="pt-c">↳ maps to: {C.esc(p["claim_component"])}</p>'
                        if p.get("claim_component") else "") + '</div>')
        o.append('</details>')

        o.append(f'<details class="adv ref"><summary><span class="rolek ref-k">Refuter</span> '
                 f'{len(rf_pts)} objection{"" if len(rf_pts)==1 else "s"} · most severe: '
                 f'{C.esc(DISTORTION_LABEL.get(r["refuter"]["most_severe_distortion"], r["refuter"]["most_severe_distortion"]))}'
                 '</summary>')
        for p in rf_pts:
            scope_routed = p.get("routes_to") == "rollup_not_grade"
            route_badge = (f'<span class="badge b-accent" title="scope objection — routed to the '
                           f'rollup, structurally barred from moving the grade">scope → rollup, '
                           f'not grade</span>' if scope_routed
                           else f'<span class="badge b-neu">routes to: {C.esc(p.get("routes_to",""))}</span>')
            o.append(f'<div class="pt{" scoped" if scope_routed else ""}">'
                     f'<div class="span">{C.esc(p.get("quote",""))}</div>'
                     f'<p class="pt-r">{C.esc(p.get("objection",""))}</p>'
                     f'<div class="pt-b"><span class="badge b-crit">'
                     f'{C.esc(DISTORTION_LABEL.get(p.get("distortion_type"), p.get("distortion_type","")))}'
                     f'</span>{route_badge}</div></div>')
        o.append('</details>')
        o.append('</div>')  # round

    # ---- aggregation finale ----
    o.append('<div class="card agg">')
    o.append('<h3 style="margin-top:0">Aggregation — the same committed rounds, current code</h3>')
    dist = rep["ordinal_distribution"]
    dmax = max(dist.values())
    for g in [x for x, _ in C.SEVERITY if x in dist]:
        var = C.SEV_VAR[g]
        o.append(f'<div class="bar-row"><div class="rl">{C.esc(g)}</div>'
                 f'<div class="bar-track"><div class="bar-fill" '
                 f'style="width:{dist[g]/dmax*100:.0f}%;background:var(--{var})"></div></div>'
                 f'<div class="rv tnums">{dist[g]} / {rep["n_valid"]}</div></div>')
    o.append('<div class="grid3" style="margin-top:14px">')
    o.append(C.tile("Replay verdict", "", ""))  # placeholder replaced below
    o[-1] = (f'<div class="tile"><div class="lab">Replay verdict</div>'
             f'<div style="margin-top:8px">{C.grade_badge(rep["verdict"])}</div>'
             f'<div class="sub">tier <b>{C.esc(rep["tier"])}</b> · a_exact '
             f'{rep["a_exact"]:.2f} · a_adj {rep["a_adj"]:.2f}</div></div>')
    o.append(C.tile("Independent reference", "", ""))
    o[-1] = (f'<div class="tile"><div class="lab">Independent reference</div>'
             f'<div style="margin-top:8px">{C.grade_badge(fr["ref_grade"])}</div>'
             f'<div class="sub">the blind decider grade this run is scored against</div></div>')
    o.append(C.tile("Scope objections routed away", str(n_scope_routed),
                    "refuter points that argued scope — barred from the grade",
                    "var(--accent)"))
    o.append('</div>')

    # then / now
    frozen_abstained = fr["status"] == "ABSTAINED"
    if frozen_abstained:
        o.append('<div class="callout crit" style="margin-bottom:0"><b>Then → now, the receipt.</b> '
                 f'The <b>pre-regrade</b> prediction <b>ABSTAINED</b> here — '
                 f'{C.grade_badge(fr["grade"])} at confidence {fr["confidence"]:.2f} under code '
                 f'<code>{C.esc(fr["code_version"])}</code>. Replaying the <i>same</i> committed rounds '
                 f'through the fixed aggregation now grades {C.grade_badge(rep["verdict"])}, matching '
                 f'the reference — at an honest <b>{C.esc(rep["tier"])}</b> tier that doesn’t hide the '
                 f'4–3 split. This is the confident-wrong tail the '
                 f'<a href="climbdown.html">climb-down</a> cleared, one case deep.</div>')
    else:
        o.append('<div class="callout" style="margin-bottom:0"><b>Then → now.</b> '
                 f'The frozen prediction was {C.grade_badge(fr["grade"])} at confidence '
                 f'{fr["confidence"]:.2f}; replaying the committed rounds reproduces '
                 f'{C.grade_badge(rep["verdict"])} at <b>{C.esc(rep["tier"])}</b> tier — matching the '
                 f'reference. A clean, reproducible case: the '
                 f'<a href="spin_spectrum.html">supported-with-overreach anchor</a>, on a paper that '
                 f'also happens to be retracted (a separate axis).</div>')
    o.append(f'<p class="prov" style="margin-top:14px">Logged Opus-4.8 critic spend for this case: '
             f'<b>${critic_cost:.4f}</b> across {len(case["rounds"])} rounds '
             f'(critic tokens only were captured; advocate counts were not). '
             f'Source: transcripts/debate_A27_Ce11.json → cases.{cid}.</p>')
    o.append('</div>')  # agg card
    o.append('</section>')
    return "".join(o)


def build() -> str:
    data = C.read_json(C.CAL_DIR / "transcripts" / "debate_A27_Ce11.json")
    cases = data["cases"]
    assert set(cases) >= {"A27", "Ce11"}, "expected A27 and Ce11 in the debate fixture"
    total_scope_routed = sum(1 for c in cases.values() for r in c["rounds"]
                             for p in r["refuter"]["points"] if p.get("routes_to") == "rollup_not_grade")

    b = []
    b.append(C.hero(
        "Innovation · the adversarial triad, replayed",
        'Watch the debate <span style="color:var(--accent)">grade a citation</span> — '
        'and watch scope get barred from the verdict',
        'A supporter argues the citation holds, a refuter attacks it, and a separate critic grades — '
        'run for several self-consistency rounds, then aggregated median-aware. This page replays two '
        'real committed cases exactly. Multi-agent debate isn’t new; the verified refinement is that '
        'refuter objections arguing <b>scope</b> are structurally routed away from the substantive '
        'grade.',
        kicker='Every round, quote, grade, tier and dollar figure is read from the committed W0 '
               'fixture <b>transcripts/debate_A27_Ce11.json</b> — no model was called to build this.'))

    b.append('<div class="grid3">')
    b.append(C.tile("Cases replayed", "2", "A27 (clean, early-stop) · Ce11 (contested split)"))
    b.append(C.tile("Scope objections routed away", str(total_scope_routed),
                    "refuter points that argued scope, barred from moving the grade across both debates",
                    "var(--accent)"))
    b.append(C.tile("Model", "Opus 4.8", "on every supporter, refuter and critic call — invariant #4"))
    b.append('</div>')

    b.append('<div class="callout"><b>How to read a round.</b> The <b>critic’s</b> grade and reasoning '
             'are always shown. Expand <span class="rolek sup-k" style="display:inline">Supporter</span> '
             'and <span class="rolek ref-k" style="display:inline">Refuter</span> to see the verbatim '
             'quotes each side marshalled. A refuter objection tagged '
             '<span class="badge b-accent">scope → rollup, not grade</span> is the mechanism the review '
             'singled out: it argues the paper is the wrong species/population, so it is sent to the '
             'objective rollup and <i>cannot</i> lower the substantive grade.</div>')

    # jump nav
    b.append('<div class="casejump" id="casejump">'
             '<button class="jbtn on" data-case="A27" onclick="showCase(\'A27\')">A27 · clean unanimous</button>'
             '<button class="jbtn" data-case="Ce11" onclick="showCase(\'Ce11\')">Ce11 · contested split → the fix</button>'
             '</div>')

    b.append(render_case("A27", cases["A27"]))
    b.append(render_case("Ce11", cases["Ce11"]))

    b.append('<hr class="rule"><p class="small">Two debates, fully reproducible from committed text: '
             'one the triad nails unanimously and early-stops, one it splits on and honestly grades at '
             'low confidence — the same case the <a href="climbdown.html">climb-down</a> rescued from a '
             'silent abstention. That’s “grounded-and-measured, not model-checks-model,” with the '
             'receipts.</p>')

    extra_css = """
.caseh{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.cid{font-size:16px;font-weight:800;background:var(--code-bg);padding:2px 10px;border-radius:7px}
.ql{display:block;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);
  font-weight:700;margin-bottom:3px}
.claimq{font-size:15.5px;color:var(--ink);font-style:italic;line-height:1.5}
.citedp{font-size:13px;color:var(--ink-2);margin:12px 0 0}
.cfgstrip{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.cfgstrip span{font-size:11.5px;font-family:ui-monospace,monospace;background:var(--surface-2);
  border:1px solid var(--hair);border-radius:6px;padding:4px 9px;color:var(--ink-2)}
.rail{display:flex;gap:6px;flex-wrap:wrap}
.railcell{flex:1;min-width:112px;background:var(--surface-2);border:1px solid var(--hair);
  border-top:3px solid var(--muted);border-radius:8px;padding:9px 10px;text-decoration:none}
.railcell:hover{background:var(--surface);text-decoration:none}
.rr{display:block;font-size:11px;font-weight:800;color:var(--muted)}
.rg{display:block;font-size:12px;font-weight:700;margin-top:3px;line-height:1.2}
.rc{display:block;font-size:11px;color:var(--muted);margin-top:3px}
.round{scroll-margin-top:64px}
.roundh{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.rnum{font-size:16px;font-weight:800}
.rolek{font-size:11px;letter-spacing:.05em;text-transform:uppercase;font-weight:800}
.sup-k{color:var(--pos)} .ref-k{color:var(--neg)}
.critic{background:var(--surface-2);border:1px solid var(--hair);border-radius:10px;padding:13px 15px}
.critic .rolek{color:var(--accent);margin-bottom:7px}
.crit-reason{font-size:14px;margin:0 0 4px}
.adv{margin-top:11px;border:1px solid var(--hair);border-radius:10px;overflow:hidden}
.adv summary{cursor:pointer;padding:11px 15px;font-size:13.5px;font-weight:650;color:var(--ink-2);
  list-style:none;display:flex;gap:9px;align-items:center;background:var(--surface)}
.adv summary::-webkit-details-marker{display:none}
.adv summary::before{content:"▸";color:var(--muted);font-size:12px;transition:transform .15s}
.adv[open] summary::before{transform:rotate(90deg)}
.adv.sup summary{border-left:4px solid var(--pos)}
.adv.ref summary{border-left:4px solid var(--neg)}
.pt{padding:11px 15px 3px;border-top:1px solid var(--grid)}
.pt.scoped{background:var(--accent-soft)}
.pt-r{font-size:13.5px;margin:6px 0 0;color:var(--ink)}
.pt-c{font-size:12px;color:var(--muted);margin:5px 0 0;font-family:ui-monospace,monospace}
.pt-b{display:flex;gap:6px;flex-wrap:wrap;margin:9px 0 6px}
.cfgstrip+*{margin-top:0}
.casejump{position:sticky;top:47px;z-index:10;display:flex;gap:6px;flex-wrap:wrap;
  background:color-mix(in srgb,var(--plane) 84%,transparent);backdrop-filter:blur(8px);
  padding:10px 0;margin:8px 0}
.jbtn{border:1px solid var(--hair);background:var(--surface);color:var(--ink-2);font-size:12.5px;
  font-weight:650;padding:8px 13px;border-radius:9px;cursor:pointer}
.jbtn:hover{background:var(--surface-2)}
.jbtn.on{background:var(--accent);color:#fff;border-color:transparent}
.cbar{height:6px;background:var(--surface-2);border-radius:4px;overflow:hidden;margin-top:5px}
.cbar-f{height:100%}
"""
    extra_js = """
<script>
function showCase(id){
  document.querySelectorAll('.jbtn').forEach(function(x){x.classList.toggle('on',x.dataset.case===id);});
  document.querySelectorAll('.casewrap').forEach(function(s){s.style.display=(s.dataset.case===id)?'':'none';});
  window.scrollTo({top:document.getElementById('casejump').offsetTop-80,behavior:'instant'});
}
// progressive enhancement: default HTML shows both; enable tabs only once JS runs
document.addEventListener('DOMContentLoaded',function(){showCase('A27');});
// let the evolution-rail anchors reveal a hidden case before jumping
document.querySelectorAll('.railcell').forEach(function(a){a.addEventListener('click',function(){
  var cw=a.closest('.casewrap'); if(cw&&cw.style.display==='none'){showCase(cw.dataset.case);}
});});
</script>
"""
    return C.page("debate", "Adversarial-debate replay", "".join(b),
                  extra_css=extra_css, extra_js=extra_js)


if __name__ == "__main__":
    out = C.write_page("debate_replay.html", build())
    print(f"wrote {out}  ({out.stat().st_size:,} bytes)")
