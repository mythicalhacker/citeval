"""C5 — Reporting. Renders an auditable, source-linked report (markdown + JSON).

The metadata-grounded vs model-inferred distinction is legible at a glance: every
axis row shows its provenance, and a legend states that metadata always overrides
model on objective axes.
"""
from __future__ import annotations

from .contracts import ClaimUnit, GroundedRecord, ScopeFrame, Verdict, to_jsonable


def _tags(tags) -> str:
    return ", ".join(f"{t.descriptor} [{';'.join(t.tree_numbers) or 'no-tree'}]" for t in tags)


def render_markdown(claim_unit: ClaimUnit, g: GroundedRecord, scope: ScopeFrame, v: Verdict) -> str:
    ci = g.identifier
    L: list[str] = []
    L += ["# Citation verification report", ""]
    L += [f"**Claim.** {v.claim}", ""]
    L += [f"**Cited paper.** {g.title}  ", f"PMID {ci.value}", ""]
    L += [f"## Overall: {v.overall}", ""]

    L += ["## Per-axis findings", "",
          "| Axis | Verdict | Confidence | Provenance | Basis |",
          "|---|---|---|---|---|"]
    for f in v.axis_findings:
        L.append(f"| {f.axis} | **{f.verdict}** | {f.tier} | {f.provenance} | "
                 f"{f.detail.replace(chr(10), ' ')} |")
    L.append("")

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

    L += ["## Provenance legend", "",
          "- **metadata-grounded** — read from a structured record (Retraction Watch, MeSH tags + tree numbers, NCBI linkage). Authoritative.",
          "- **text-grounded** — an explicit lexical marker in the claim wording.",
          "- **model-inferred** — a model judgement (in this slice, only the lightweight scope hint; the graded support axis is deferred).",
          "- **stub-not-adjudicated** — deliberately not decided in the thin slice.",
          "",
          "_Metadata (grounded) always overrides model/text on objective axes — a conflict is scored as the model being wrong, not the record._"]
    if v.stub:
        L += ["", "> This is the thin-slice output. Objective axes (retraction, scope) are real and "
              "metadata-grounded; the graded substantive-support axis is produced later by the "
              "adversarial adjudication agent with calibration."]
    return "\n".join(L) + "\n"


def render_json(claim_unit: ClaimUnit, g: GroundedRecord, scope: ScopeFrame, v: Verdict) -> dict:
    return {
        "claim_unit": to_jsonable(claim_unit),
        "grounded": to_jsonable(g),
        "claim_scope": to_jsonable(scope),
        "verdict": to_jsonable(v),
    }
