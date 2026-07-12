"""C5 — Reporting. Renders an auditable, source-linked report (markdown + JSON + HTML).

The metadata-grounded vs model-inferred distinction is legible at a glance: every
axis row shows its provenance, and a legend states that metadata always overrides
model on objective axes.

This module is **rendering only** — it never computes or infers a verdict. It reads
whatever C4 (the adversarial adjudication agent) produced and displays it.

## Graded `substantive_support` axis (evidence-dict convention)

`AxisFinding.evidence` is a free-form dict on the frozen contract. For the graded
`substantive_support` axis, C4 *produces* and C5 *reads* the keys blessed in
`design/research_briefs/CONTEXT_PACK.md` §6 (the C4↔C5 contract-of-record — not a
`contracts.py` change; if the keys move, only C4 and this extractor move):

    verdict     = RB1 grade (or "NOT_ENOUGH_INFO" on abstention)
    tier        = confidence tier ("high" | "medium" | "low")
    provenance  = "model-inferred"
    detail      = critic's one-line rationale
    evidence = {
        "confidence":  {"verbalized": "high|medium|low", "agreement": <0..1 float>, "n_samples": <int>},
        "calibration": {"note": "<one line from the scorer/RB3; empty until available>"},
        "supporter":   {"span": "<verbatim cited-text quote>", "point": "<why it supports>"},
        "refuter":     {"span": "<verbatim quote>", "objection": "<why it doesn't>"},
        "abstained":   <bool>,   # true <=> verdict == "NOT_ENOUGH_INFO"
    }

All keys are read defensively: a missing supporter/refuter span renders as
"no supporting span found", an empty calibration note as "not yet available".
"""
from __future__ import annotations

import html
from typing import Optional

from .contracts import AxisFinding, ClaimUnit, GroundedRecord, ScopeFrame, Verdict, to_jsonable

# --------------------------------------------------------------------------- shared copy
_OVERRIDE_NOTE = ("Metadata (grounded) always overrides model/text on objective axes — a "
                  "conflict is scored as the model being wrong, not the record.")
_STUB_NOTE = ("This is the thin-slice output. Objective axes (retraction, scope) are real and "
              "metadata-grounded; the graded substantive-support axis is produced later by the "
              "adversarial adjudication agent with calibration.")
# The substantive axis grades substance only; scope over-reach lives on the scope axes (§6).
_SCOPE_CONSTANT_NOTE = ("this axis grades *substance only, holding scope constant* "
                        "(CONTEXT_PACK §6); species/population scope over-reach is carried by the "
                        "scope axes above, not reflected in this grade.")


def _legend_items(graded: bool) -> list[tuple[str, str]]:
    """The provenance legend as (atom, description) pairs — the single source shared by
    the markdown and HTML renderers so both carry identical wording.

    When a real graded axis is present the `model-inferred` line names the graded axis;
    otherwise it keeps the thin-slice wording (byte-identical to the base report)."""
    model_inferred = (
        "a model judgement — the C3 claim-scope hint plus the graded substantive-support axis, "
        "produced by the adversarial supporter/refuter/critic agent with calibration."
        if graded else
        "a model judgement (in this slice, only the lightweight scope hint; the graded support "
        "axis is deferred)."
    )
    return [
        ("metadata-grounded", "read from a structured record (Retraction Watch, MeSH tags + tree "
                              "numbers, NCBI linkage). Authoritative."),
        ("text-grounded", "an explicit lexical marker in the claim wording."),
        ("model-inferred", model_inferred),
        ("stub-not-adjudicated", "deliberately not decided in the thin slice."),
    ]


# --------------------------------------------------------------------------- graded-axis extractors
def _graded_axis(v: Verdict) -> Optional[AxisFinding]:
    """The `substantive_support` finding iff C4 filled it with a real grade; else None
    (so the stub path renders nothing extra)."""
    for f in v.axis_findings:
        if f.axis == "substantive_support" and _is_real_grade(f):
            return f
    return None


def _is_real_grade(f: AxisFinding) -> bool:
    return f.provenance != "stub-not-adjudicated" and f.verdict not in ("", "NOT_ADJUDICATED")


def _abstained(f: AxisFinding) -> bool:
    return bool((f.evidence or {}).get("abstained")) or f.verdict == "NOT_ENOUGH_INFO"


def _confidence_text(f: AxisFinding) -> str:
    """Human-readable confidence line: the tier plus whatever RB3 signals are present
    (self-consistency agreement across N samples, verbalized confidence)."""
    conf = (f.evidence or {}).get("confidence") or {}
    bits: list[str] = []
    agreement = conf.get("agreement")
    if agreement is not None:
        agr = f"self-consistency agreement {agreement:.2f}" if isinstance(agreement, (int, float)) \
            else f"self-consistency agreement {agreement}"
        n = conf.get("n_samples")
        if n is not None:
            agr += f" across {n} samples"
        bits.append(agr)
    verbalized = conf.get("verbalized")
    if verbalized:
        bits.append(f"verbalized {verbalized}")
    tier = f.tier or "n/a"
    return f"{tier} — {'; '.join(bits)}" if bits else tier


def _calibration_text(f: AxisFinding) -> str:
    note = ((f.evidence or {}).get("calibration") or {}).get("note") or ""
    return note.strip() or "not yet available — populated by the scorer/RB3 once the corpus is scored."


def _span(f: AxisFinding, role: str, gloss_key: str) -> tuple[str, str]:
    """(quoted-span, one-line gloss) for the supporter/refuter, read defensively."""
    block = (f.evidence or {}).get(role) or {}
    span = (block.get("span") or "").replace("\n", " ").strip()
    gloss = (block.get(gloss_key) or "").replace("\n", " ").strip()
    return span, gloss


def _grade_label(f: AxisFinding) -> str:
    if _abstained(f):
        return "NOT_ENOUGH_INFO — the agent abstained; recorded as an abstention, not scored as wrong."
    return f.verdict


# --------------------------------------------------------------------------- markdown fragments
def _tags(tags) -> str:
    return ", ".join(f"{t.descriptor} [{';'.join(t.tree_numbers) or 'no-tree'}]" for t in tags)


def _axis_table_md(v: Verdict) -> list[str]:
    L = ["| Axis | Verdict | Confidence | Provenance | Basis |",
         "|---|---|---|---|---|"]
    for f in v.axis_findings:
        L.append(f"| {f.axis} | **{f.verdict}** | {f.tier} | {f.provenance} | "
                 f"{f.detail.replace(chr(10), ' ')} |")
    return L


def _graded_section_md(v: Verdict) -> list[str]:
    """The graded substantive-support block — returns [] when no real grade is present
    (so the stub path is byte-identical)."""
    f = _graded_axis(v)
    if f is None:
        return []
    L = ["## Substantive support (graded)", ""]
    L.append(f"- **Grade (RB1 scale):** {_grade_label(f)}")
    L.append(f"- **Confidence:** {_confidence_text(f)}")
    L.append(f"- **Calibration:** {_calibration_text(f)}")
    L.append(f"- **Provenance:** {f.provenance} — {_SCOPE_CONSTANT_NOTE}")
    if f.detail:
        L.append(f"- **Rationale:** {f.detail.replace(chr(10), ' ')}")
    L += ["", "**Adversarial trace.**", ""]
    for role, label, gloss_key, empty in (
        ("supporter", "Supporter — best supporting span", "point", "no supporting span found"),
        ("refuter", "Refuter — strongest objection", "objection", "no objection span found"),
    ):
        span, gloss = _span(f, role, gloss_key)
        L.append(f"- _{label}:_")
        if span:
            L.append(f"  > {span}")
            if gloss:
                L.append(f"  {gloss}")
        else:
            L.append(f"  _({empty})_")
    L.append("")
    return L


def _legend_md(graded: bool) -> list[str]:
    L = ["## Provenance legend", ""]
    for atom, desc in _legend_items(graded):
        L.append(f"- **{atom}** — {desc}")
    L += ["", f"_{_OVERRIDE_NOTE}_"]
    return L


# --------------------------------------------------------------------------- markdown (full report)
def render_markdown(claim_unit: ClaimUnit, g: GroundedRecord, scope: ScopeFrame, v: Verdict) -> str:
    ci = g.identifier
    L: list[str] = []
    L += ["# Citation verification report", ""]
    L += [f"**Claim.** {v.claim}", ""]
    L += [f"**Cited paper.** {g.title}  ", f"PMID {ci.value}", ""]
    L += [f"## Overall: {v.overall}", ""]

    L += ["## Per-axis findings", ""]
    L += _axis_table_md(v)
    L.append("")

    # Graded substantive-support axis (additive: empty on the stub path).
    L += _graded_section_md(v)

    L += ["## Axes flagged unverifiable (not fabricated)", ""]
    for k, val in v.unverifiable_axes.items():
        L.append(f"- **{k}** — {val}")
    L.append("")

    L += ["## Grounding evidence (structured, metadata-grounded)", ""]
    r = g.retraction
    L.append(f"- **Retraction status:** {r.status} (source agreement: {r.source_agreement})")
    if r.retraction_watch and r.retraction_watch.present:
        rw = r.retraction_watch
        L.append(f"  - Retraction Watch record {rw.rw_record_id}: {rw.reason} (date {rw.date})")
    for c in r.comments_corrections:
        L.append(f"  - NCBI {c.ref_type}: PMID {c.pmid} — {c.source}")
    if r.ncbi_publication_type_flag:
        L.append("  - NCBI PublicationType flag: 'Retracted Publication' present")
    L.append(f"- **Organism MeSH (tree B\\*):** {_tags(g.organism_tags) or '(none)'} | "
             f"Humans present: {g.has_humans}")
    L.append(f"- **Population MeSH (tree M01.060\\*):** {_tags(g.population_tags) or '(none)'}")
    L.append(f"- **Sex check-tags:** {', '.join(t.descriptor for t in g.sex_tags) or '(none)'}")
    L.append("")

    L += ["## Claim scope parse (C3-lite — explicit lexical markers)", ""]
    L.append(f"- Asserted organism: **{scope.organism}** "
             f"(provenance: {scope.provenance}, tier: {scope.tier}); "
             f"evidence: {scope.organism_evidence or '(none)'}")
    L.append(f"- Asserted population: {scope.population or '(none)'}; "
             f"evidence: {scope.population_evidence or '(none)'}")
    L.append(f"- Dose stated in claim: {scope.dose_stated}")
    L.append("")

    L += _legend_md(_graded_axis(v) is not None)
    if v.stub:
        L += ["", f"> {_STUB_NOTE}"]
    return "\n".join(L) + "\n"


def render_json(claim_unit: ClaimUnit, g: GroundedRecord, scope: ScopeFrame, v: Verdict) -> dict:
    return {
        "claim_unit": to_jsonable(claim_unit),
        "grounded": to_jsonable(g),
        "claim_scope": to_jsonable(scope),
        "verdict": to_jsonable(v),
    }


# --------------------------------------------------------------------------- BYO-paper (markdown)
def render_byo_markdown(claim_unit: ClaimUnit, g: GroundedRecord, scope: ScopeFrame,
                        v: Verdict) -> str:
    """Bring-your-own-paper view (markdown): a compact top summary (claim, cited paper,
    overall), the per-axis table, the graded block when present, and the provenance
    legend. Carries the same information as `render_byo_html`."""
    ci = g.identifier
    L: list[str] = ["# Citation check — bring-your-own-paper", ""]
    L += [f"**Claim.** {v.claim}  "]
    L += [f"**Cited paper.** {g.title} (PMID {ci.value})  "]
    L += [f"**Overall.** {v.overall}", ""]

    L += ["## Per-axis findings", ""]
    L += _axis_table_md(v)
    L.append("")

    L += _graded_section_md(v)

    L += _legend_md(_graded_axis(v) is not None)
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- HTML helpers
def _esc(s: object) -> str:
    return html.escape("" if s is None else str(s))


def _prov_class(provenance: str) -> str:
    """CSS class for a provenance badge, keyed on the leading atom (composites keep the
    dominant atom's colour)."""
    atom = (provenance or "").split()[0] if provenance else ""
    return {
        "metadata-grounded": "prov-meta",
        "text-grounded": "prov-text",
        "model-inferred": "prov-model",
        "stub-not-adjudicated": "prov-stub",
    }.get(atom, "prov-composite")


def _prov_badge(provenance: str) -> str:
    return f'<span class="badge {_prov_class(provenance)}">{_esc(provenance)}</span>'


_HTML_STYLE = """
:root { color-scheme: light dark; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial,
       sans-serif; line-height: 1.5; color: #1a1a1a; background: #fff;
       margin: 0 auto; max-width: 62rem; padding: 2rem; }
h1 { font-size: 1.6rem; margin: 0 0 1rem; }
h2 { font-size: 1.15rem; margin: 2rem 0 .5rem; border-bottom: 1px solid #e5e5e5; padding-bottom: .25rem; }
.overall { font-weight: 700; padding: .55rem .8rem; background: #f6f8fa;
           border-left: 4px solid #444; border-radius: .25rem; }
.tablewrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: .9rem; }
th, td { border: 1px solid #e2e2e2; padding: .4rem .55rem; text-align: left; vertical-align: top; }
th { background: #f6f8fa; }
.badge { display: inline-block; padding: .08rem .45rem; border-radius: .6rem; font-size: .76rem;
         font-weight: 600; white-space: nowrap; }
.prov-meta { background: #e6f4ea; color: #137333; }
.prov-text { background: #e8f0fe; color: #1967d2; }
.prov-model { background: #fef7e0; color: #99590b; }
.prov-stub { background: #f1f3f4; color: #5f6368; }
.prov-composite { background: #f3e8fd; color: #7b2fbe; }
.graded { background: #fbfbfd; border: 1px solid #e5e5e5; border-radius: .5rem; padding: 1rem 1.2rem; }
.graded dl { display: grid; grid-template-columns: max-content 1fr; gap: .3rem .8rem; margin: 0; }
.graded dt { font-weight: 600; }
.graded dd { margin: 0; }
blockquote { margin: .35rem 0; padding: .4rem .8rem; border-left: 3px solid #bbb;
             background: #fafafa; color: #333; }
.gloss { color: #555; font-size: .9rem; }
.legend dt { font-weight: 600; }
.override { font-style: italic; color: #444; }
.stubnote { border-left: 3px solid #bbb; padding: .4rem .8rem; color: #555; background: #fafafa; }
@media (prefers-color-scheme: dark) {
  body { color: #e6e6e6; background: #16181c; }
  h2 { border-bottom-color: #333; }
  .overall { background: #22262e; border-left-color: #888; }
  th { background: #22262e; } th, td { border-color: #333; }
  .graded { background: #1b1e24; border-color: #333; }
  blockquote, .stubnote { background: #1b1e24; border-left-color: #555; color: #cfcfcf; }
  .gloss, .override { color: #b3b3b3; }
}
""".strip()


def _graded_section_html(v: Verdict) -> list[str]:
    f = _graded_axis(v)
    if f is None:
        return []
    rows = [
        ("Grade (RB1 scale)", _esc(_grade_label(f))),
        ("Confidence", _esc(_confidence_text(f))),
        ("Calibration", _esc(_calibration_text(f))),
        ("Provenance", f"{_prov_badge(f.provenance)} — grades substance only, holding scope "
                       "constant (CONTEXT_PACK §6); scope over-reach is on the scope axes above."),
    ]
    if f.detail:
        rows.append(("Rationale", _esc(f.detail.replace("\n", " "))))
    H = ['<section class="graded">', "<h2>Substantive support (graded)</h2>", "<dl>"]
    for term, desc in rows:
        H.append(f"<dt>{_esc(term)}</dt><dd>{desc}</dd>")
    H.append("</dl>")
    H.append("<p><strong>Adversarial trace.</strong></p>")
    for role, label, gloss_key, empty in (
        ("supporter", "Supporter — best supporting span", "point", "no supporting span found"),
        ("refuter", "Refuter — strongest objection", "objection", "no objection span found"),
    ):
        span, gloss = _span(f, role, gloss_key)
        H.append(f'<p class="gloss">{_esc(label)}:</p>')
        if span:
            H.append(f"<blockquote>{_esc(span)}</blockquote>")
            if gloss:
                H.append(f'<p class="gloss">{_esc(gloss)}</p>')
        else:
            H.append(f'<p class="gloss"><em>({_esc(empty)})</em></p>')
    H.append("</section>")
    return H


def _axis_table_html(v: Verdict) -> list[str]:
    H = ['<div class="tablewrap"><table>',
         "<thead><tr><th>Axis</th><th>Verdict</th><th>Confidence</th>"
         "<th>Provenance</th><th>Basis</th></tr></thead>", "<tbody>"]
    for f in v.axis_findings:
        H.append(f"<tr><td>{_esc(f.axis)}</td><td><strong>{_esc(f.verdict)}</strong></td>"
                 f"<td>{_esc(f.tier)}</td><td>{_prov_badge(f.provenance)}</td>"
                 f"<td>{_esc(f.detail.replace(chr(10), ' '))}</td></tr>")
    H += ["</tbody></table></div>"]
    return H


def _legend_html(graded: bool) -> list[str]:
    H = ["<h2>Provenance legend</h2>", '<dl class="legend">']
    for atom, desc in _legend_items(graded):
        H.append(f"<dt>{_esc(atom)}</dt><dd>{_esc(desc)}</dd>")
    H += ["</dl>", f'<p class="override">{_esc(_OVERRIDE_NOTE)}</p>']
    return H


def _doc_html(title: str, body: list[str]) -> str:
    return "\n".join([
        "<!doctype html>",
        '<html lang="en"><head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_esc(title)}</title>",
        f"<style>{_HTML_STYLE}</style>",
        "</head><body>",
        *body,
        "</body></html>",
        "",
    ])


# --------------------------------------------------------------------------- HTML (full report)
def render_html(claim_unit: ClaimUnit, g: GroundedRecord, scope: ScopeFrame, v: Verdict) -> str:
    """Self-contained HTML report (no external assets, all dynamic content escaped).

    Carries the same information as `render_markdown`: header, per-axis table, the graded
    substantive-support block when present, grounding evidence, claim-scope parse, and the
    provenance legend with the metadata-override note."""
    ci = g.identifier
    r = g.retraction
    graded = _graded_axis(v) is not None
    B: list[str] = ["<main>"]
    B.append("<h1>Citation verification report</h1>")
    B.append(f"<p><strong>Claim.</strong> {_esc(v.claim)}</p>")
    B.append(f"<p><strong>Cited paper.</strong> {_esc(g.title)}<br>PMID {_esc(ci.value)}</p>")
    B.append(f'<p class="overall">Overall: {_esc(v.overall)}</p>')

    B.append("<h2>Per-axis findings</h2>")
    B += _axis_table_html(v)

    B += _graded_section_html(v)

    B.append("<h2>Axes flagged unverifiable (not fabricated)</h2>")
    B.append("<ul>")
    for k, val in v.unverifiable_axes.items():
        B.append(f"<li><strong>{_esc(k)}</strong> — {_esc(val)}</li>")
    B.append("</ul>")

    B.append("<h2>Grounding evidence (structured, metadata-grounded)</h2>")
    B.append("<ul>")
    B.append(f"<li><strong>Retraction status:</strong> {_esc(r.status)} "
             f"(source agreement: {_esc(r.source_agreement)})")
    sub: list[str] = []
    if r.retraction_watch and r.retraction_watch.present:
        rw = r.retraction_watch
        sub.append(f"<li>Retraction Watch record {_esc(rw.rw_record_id)}: {_esc(rw.reason)} "
                   f"(date {_esc(rw.date)})</li>")
    for c in r.comments_corrections:
        sub.append(f"<li>NCBI {_esc(c.ref_type)}: PMID {_esc(c.pmid)} — {_esc(c.source)}</li>")
    if r.ncbi_publication_type_flag:
        sub.append("<li>NCBI PublicationType flag: 'Retracted Publication' present</li>")
    if sub:
        B.append("<ul>" + "".join(sub) + "</ul>")
    B.append("</li>")
    B.append(f"<li><strong>Organism MeSH (tree B*):</strong> {_esc(_tags(g.organism_tags) or '(none)')} "
             f"| Humans present: {_esc(g.has_humans)}</li>")
    B.append(f"<li><strong>Population MeSH (tree M01.060*):</strong> "
             f"{_esc(_tags(g.population_tags) or '(none)')}</li>")
    B.append(f"<li><strong>Sex check-tags:</strong> "
             f"{_esc(', '.join(t.descriptor for t in g.sex_tags) or '(none)')}</li>")
    B.append("</ul>")

    B.append("<h2>Claim scope parse (C3-lite — explicit lexical markers)</h2>")
    B.append("<ul>")
    B.append(f"<li>Asserted organism: <strong>{_esc(scope.organism)}</strong> "
             f"(provenance: {_esc(scope.provenance)}, tier: {_esc(scope.tier)}); "
             f"evidence: {_esc(scope.organism_evidence or '(none)')}</li>")
    B.append(f"<li>Asserted population: {_esc(scope.population or '(none)')}; "
             f"evidence: {_esc(scope.population_evidence or '(none)')}</li>")
    B.append(f"<li>Dose stated in claim: {_esc(scope.dose_stated)}</li>")
    B.append("</ul>")

    B += _legend_html(graded)
    if v.stub:
        B.append(f'<p class="stubnote">{_esc(_STUB_NOTE)}</p>')
    B.append("</main>")
    return _doc_html(f"Citation verification report — PMID {ci.value}", B)


# --------------------------------------------------------------------------- BYO-paper (HTML)
def render_byo_html(claim_unit: ClaimUnit, g: GroundedRecord, scope: ScopeFrame, v: Verdict) -> str:
    """Bring-your-own-paper view (HTML): a compact top summary, the per-axis table, the
    graded block when present, and the provenance legend. Same information as
    `render_byo_markdown`."""
    ci = g.identifier
    graded = _graded_axis(v) is not None
    B: list[str] = ["<main>"]
    B.append("<h1>Citation check — bring-your-own-paper</h1>")
    B.append(f"<p><strong>Claim.</strong> {_esc(v.claim)}</p>")
    B.append(f"<p><strong>Cited paper.</strong> {_esc(g.title)} (PMID {_esc(ci.value)})</p>")
    B.append(f'<p class="overall">Overall: {_esc(v.overall)}</p>')

    B.append("<h2>Per-axis findings</h2>")
    B += _axis_table_html(v)

    B += _graded_section_html(v)

    B += _legend_html(graded)
    B.append("</main>")
    return _doc_html(f"Citation check — PMID {ci.value}", B)


# --------------------------------------------------------------------------- showcase (offline gallery)
# An offline, no-key gallery of worked examples: each card shows the claim, the cited paper, the
# per-axis verdicts (reusing `_axis_table_html`), the graded substantive-support summary, and the
# decisive verbatim span. This is rendering-only, like the rest of C5 — the caller (docs/build_showcase.py)
# assembles each card's `Verdict` from CACHED corpus results and hands it here to render.
#
# A card is a plain dict (kept off the frozen contract deliberately) with keys:
#   case_id        str  — corpus case id (e.g. "A25")
#   story_title    str  — the one-line "why this case matters" headline
#   story_caption  str  — 1–2 sentence explanation of what the system caught
#   axis_focus     str  — which axis is the hero of this card ("retraction" | "species_scope" | ...)
#   claim          str  — the citing sentence (verbatim)
#   citing_source  str  — provenance of the citing paper (e.g. "PMC6854371"), optional
#   cited          dict — {"title", "journal", "pmid", "doi"} of the cited paper
#   verdict        Verdict — the assembled per-axis verdict (rendered via _axis_table_html)
#   decisive       dict — {"span": <verbatim quote>, "source": <label>}, optional
#   reference      dict — {"grade": <ref grade>, "note": <one line>}, optional (agreement-with-reference)
_SHOWCASE_STYLE = """
.intro { background: #f6f8fa; border: 1px solid #e5e5e5; border-radius: .6rem; padding: 1rem 1.25rem;
         margin: 0 0 1.5rem; }
.intro p { margin: .4rem 0; }
.legendgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); gap: .3rem .9rem;
              margin: .5rem 0 0; font-size: .88rem; }
.legendgrid b { font-weight: 600; }
.case { border: 1px solid #e2e2e2; border-radius: .6rem; padding: 1.1rem 1.3rem; margin: 0 0 1.4rem;
        background: #fff; }
.case-head { display: flex; align-items: baseline; gap: .6rem; flex-wrap: wrap; }
.case-id { font-weight: 700; font-size: .8rem; letter-spacing: .04em; color: #fff; background: #444;
           padding: .12rem .5rem; border-radius: .5rem; }
.case-head h2 { margin: 0; border: none; padding: 0; font-size: 1.12rem; }
.axis-tag { font-size: .72rem; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
            color: #5f6368; }
.story { color: #333; margin: .5rem 0 1rem; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 1.2rem; align-items: start; }
@media (max-width: 52rem) { .cols { grid-template-columns: 1fr; } }
.lbl { font-size: .72rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em;
       color: #5f6368; margin: .8rem 0 .25rem; }
.col > .lbl:first-child { margin-top: 0; }
.claim { font-size: .95rem; }
.cited .ct { font-weight: 600; }
.cited .meta, .src { color: #5f6368; font-size: .82rem; }
.graded-mini { margin-top: 1rem; padding-top: .8rem; border-top: 1px dashed #ddd; }
.graded-mini p { margin: .3rem 0; }
.refnote { color: #137333; font-size: .84rem; }
@media (prefers-color-scheme: dark) {
  .intro { background: #22262e; border-color: #333; }
  .case { background: #16181c; border-color: #333; }
  .case-id { background: #666; }
  .story { color: #cfcfcf; }
  .graded-mini { border-top-color: #333; }
  .cited .meta, .src, .axis-tag { color: #9aa0a6; }
  .refnote { color: #6ee7a0; }
}
""".strip()


def _showcase_intro_html() -> list[str]:
    """The reading guide shown once at the top of the gallery (light provenance legend)."""
    H = ['<section class="intro">']
    H.append("<p><strong>citeval</strong> checks whether the paper cited to support a scientific "
             "claim actually supports it — catching <em>retraction</em>, <em>species/population "
             "scope mismatch</em>, and graded <em>substantive over-reach</em>. Every verdict carries "
             "a confidence tier and a provenance label.</p>")
    H.append("<p>These four cases are drawn verbatim from the 30-case calibration corpus and rendered "
             "from <strong>cached results</strong> — no API key is needed to view this page. "
             "Objective axes (retraction, scope) are read from structured records and are "
             "authoritative; the substantive-support grade is model-inferred by an adversarial "
             "supporter/refuter/critic panel with a self-consistency confidence.</p>")
    H.append('<div class="legendgrid">')
    for atom, desc in _legend_items(graded=True):
        H.append(f"<div>{_prov_badge(atom)} {_esc(desc)}</div>")
    H.append("</div>")
    H.append(f'<p class="override">{_esc(_OVERRIDE_NOTE)}</p>')
    H.append("</section>")
    return H


def render_showcase_card(card: dict) -> list[str]:
    """One gallery card (list of HTML lines). Rendering-only; see the module note for the card
    shape. Reuses the shared per-axis table + provenance badges so a card row is byte-consistent
    with the full report."""
    v: Verdict = card["verdict"]
    graded = _graded_axis(v)
    cd = card.get("cited") or {}
    H = ['<article class="case">']
    H.append('<div class="case-head">'
             f'<span class="case-id">{_esc(card.get("case_id", ""))}</span>'
             f'<h2>{_esc(card.get("story_title", ""))}</h2>'
             + (f'<span class="axis-tag">{_esc(card["axis_focus"].replace("_", " "))}</span>'
                if card.get("axis_focus") else "")
             + "</div>")
    if card.get("story_caption"):
        H.append(f'<p class="story">{_esc(card["story_caption"])}</p>')

    H.append('<div class="cols">')
    # left column: claim + cited paper
    H.append('<div class="col">')
    H.append('<p class="lbl">Claim (verbatim)</p>')
    H.append(f'<blockquote class="claim">{_esc(card.get("claim", ""))}</blockquote>')
    if card.get("citing_source"):
        H.append(f'<p class="src">— as cited in {_esc(card["citing_source"])}</p>')
    H.append('<p class="lbl">Cited paper</p>')
    doi = cd.get("doi")
    meta = " · ".join(x for x in [
        _esc(cd.get("journal", "")).strip(),
        f'PMID {_esc(cd.get("pmid", ""))}',
        (f"DOI {_esc(doi)}" if doi else ""),
    ] if x)
    H.append(f'<p class="cited"><span class="ct">{_esc(cd.get("title", ""))}</span><br>'
             f'<span class="meta">{meta}</span></p>')
    H.append("</div>")

    # right column: overall + per-axis table
    H.append('<div class="col">')
    H.append(f'<p class="overall">Overall: {_esc(v.overall)}</p>')
    H += _axis_table_html(v)
    H.append("</div>")
    H.append("</div>")  # .cols

    # graded substantive summary + decisive span
    if graded is not None:
        H.append('<div class="graded-mini">')
        H.append("<p><strong>Substantive support:</strong> "
                 f"{_esc(_grade_label(graded))} &nbsp;·&nbsp; "
                 f"<strong>Confidence:</strong> {_esc(_confidence_text(graded))} "
                 f"&nbsp;·&nbsp; {_prov_badge(graded.provenance)}</p>")
        dec = card.get("decisive") or {}
        if dec.get("span"):
            src = dec.get("source") or "cited paper"
            H.append(f'<p class="lbl">Key evidence span — {_esc(src)}</p>')
            H.append(f"<blockquote>{_esc(dec['span'])}</blockquote>")
        ref = card.get("reference") or {}
        if ref.get("note"):
            H.append(f'<p class="refnote">{_esc(ref["note"])}</p>')
        H.append("</div>")
    H.append("</article>")
    return H


def render_showcase_page(cards: list[dict], *, title: str = "citeval — worked examples") -> str:
    """Self-contained HTML gallery (no external assets; all dynamic content escaped) of the given
    cards. Carries the same information a full report would per case, in a compact card form."""
    B: list[str] = ["<main>"]
    B.append(f"<h1>{_esc(title)}</h1>")
    B += _showcase_intro_html()
    for card in cards:
        B += render_showcase_card(card)
    B.append("</main>")
    return "\n".join([
        "<!doctype html>",
        '<html lang="en"><head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_esc(title)}</title>",
        f"<style>{_HTML_STYLE}\n{_SHOWCASE_STYLE}</style>",
        "</head><body>",
        *B,
        "</body></html>",
        "",
    ])
