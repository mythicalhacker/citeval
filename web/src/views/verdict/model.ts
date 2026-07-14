/**
 * verdict/model.ts — pure, JSX-free helpers for the Verdict view (W2-FE-VERDICT).
 *
 * These mirror the read-only semantics of `src/citeval/reporting.py`: the objective-gate rollup,
 * the graded substantive-support axis extraction, the confidence/calibration copy, and a faithful
 * Markdown reconstruction for the export bar. They read the FROZEN `RenderJson` shape defensively
 * (evidence is an open dict; several axis sub-keys live outside the typed `SubstantiveEvidence`
 * subset), so a slightly different backend payload never throws in the renderer.
 */
import type {
  RunResult, RenderJson, VerdictCore, AxisFinding, MeshTag, GroundedRecord, ScopeFrame,
} from '../../lib/types';
import type { ConfKey } from '../../design/tokens';
import { gateFiredFromOverall } from '../../components/common';

/* ------------------------------------------------------------------ axis ordering / extraction -- */

/** Canonical axis order — the stepper/report read the axes in this sequence. */
export const AXIS_ORDER = [
  'retraction', 'species_scope', 'population_scope', 'substantive_support',
] as const;

/** Human labels for the four axes (title-cased, matching the report). */
export const AXIS_LABEL: Record<string, string> = {
  retraction: 'Retraction',
  species_scope: 'Species scope',
  population_scope: 'Population scope',
  substantive_support: 'Substantive support',
};

/** The axis findings in canonical order; any unrecognised axes are appended in payload order. */
export function orderedAxes(v: VerdictCore): AxisFinding[] {
  const rank = (a: AxisFinding) => {
    const i = (AXIS_ORDER as readonly string[]).indexOf(a.axis);
    return i < 0 ? AXIS_ORDER.length : i;
  };
  return [...v.axis_findings].sort((a, b) => rank(a) - rank(b));
}

/** The `substantive_support` finding, if the adjudicator filled it with a real grade (always so in
 *  the four fixtures; `null` on a bare stub). Mirrors reporting.py `_graded_axis` + `_is_real_grade`. */
export function substantiveAxis(v: VerdictCore): AxisFinding | null {
  for (const f of v.axis_findings) {
    if (f.axis !== 'substantive_support') continue;
    if (f.provenance !== 'stub-not-adjudicated' && f.verdict !== '' && f.verdict !== 'NOT_ADJUDICATED') {
      return f;
    }
  }
  return null;
}

/* ------------------------------------------------------------------------- gate / abstention ---- */

/** True when an objective gate (retraction / scope mismatch) fired and forced `overall` to NOT
 *  SUPPORTED AS STATED — the metadata-overrides-model invariant made visible. Reads the `overall`
 *  string first (mirrors reporting), with an axis-verdict fallback so a reworded rollup still gates. */
/** The objective-axis verdicts that trip the gate — retraction, expression-of-concern, or a scope
 *  mismatch (all first-class FROZEN RetractionVerdict / ScopeVerdict values). */
const GATE_VERDICTS = new Set(['RELIES_ON_RETRACTED', 'CITED_PAPER_HAS_EOC', 'SCOPE_MISMATCH']);

export function gateFired(v: VerdictCore): boolean {
  if (gateFiredFromOverall(v.overall)) return true;
  return v.axis_findings.some((f) => GATE_VERDICTS.has(f.verdict));
}

/** The axis that tripped the gate (for the one-line reason), or null when clear. Retraction/EOC
 *  win over scope so the reason names the strongest objective failure first. */
export function gateReasonAxis(v: VerdictCore): AxisFinding | null {
  return (
    v.axis_findings.find((f) => f.verdict === 'RELIES_ON_RETRACTED' || f.verdict === 'CITED_PAPER_HAS_EOC') ??
    v.axis_findings.find((f) => f.verdict === 'SCOPE_MISMATCH') ??
    null
  );
}

/** Mirrors reporting.py `_abstained`: an explicit `abstained` flag or the NEI verdict. */
export function isAbstained(f: AxisFinding | null): boolean {
  if (!f) return false;
  return Boolean((f.evidence as { abstained?: boolean } | undefined)?.abstained)
    || f.verdict === 'NOT_ENOUGH_INFO';
}

/** The three verdict "moods" that shape the hero: a fired objective gate, an honest abstention, or
 *  a clean graded verdict that `overall` tracks directly. */
export type VerdictMood = 'gated' | 'abstained' | 'graded';
export function verdictMood(v: VerdictCore): VerdictMood {
  if (gateFired(v)) return 'gated';
  if (isAbstained(substantiveAxis(v))) return 'abstained';
  return 'graded';
}

/* --------------------------------------------------------------------- confidence tier mapping -- */

/** Map an axis tier string to a confidence-token key; abstention overrides to the neutral slate. */
export function confKeyOf(f: AxisFinding | null): ConfKey {
  if (isAbstained(f)) return 'abstain';
  switch (f?.tier) {
    case 'high':
    case 'medium':
    case 'low':
      return f.tier;
    default:
      return 'medium';
  }
}

/* ---------------------------------------------------------------------- typed evidence readers --- */

export interface ConfidenceEvidence {
  verbalized?: string;
  agreement?: number;
  n_samples?: number;
}
export interface SpanEvidence {
  span?: string;
  point?: string;
  objection?: string;
}
export interface VerbatimGuard {
  supporter_discarded?: number;
  refuter_discarded?: number;
  grounding_corpus?: string;
}
export interface SelfConsistency {
  rounds_configured?: number;
  rounds_run?: number;
  rounds_valid?: number;
  a_exact?: number;
  a_adj?: number;
  conf_hybrid?: number;
  non_adjacent_multimodal?: boolean;
  ordinal_distribution?: Record<string, number>;
  n_nei?: number;
  n_non_substantiating?: number;
  n_parse_failed?: number;
  tau_abstain?: number;
  adjacent_floor?: number;
}

function ev(f: AxisFinding): Record<string, unknown> {
  return (f.evidence ?? {}) as Record<string, unknown>;
}
export function confidenceOf(f: AxisFinding): ConfidenceEvidence {
  return (ev(f).confidence ?? {}) as ConfidenceEvidence;
}
export function calibrationNoteOf(f: AxisFinding): string {
  const note = ((ev(f).calibration ?? {}) as { note?: string }).note ?? '';
  return note.trim();
}
/** A span block, whitespace-normalised to match reporting.py `_span` (collapse newlines + strip),
 *  so a multiline span never breaks a markdown blockquote or renders as an empty quote. */
export function spanOf(f: AxisFinding, role: 'supporter' | 'refuter'): SpanEvidence {
  const raw = (ev(f)[role] ?? {}) as SpanEvidence;
  const clean = (s?: string) => (s ?? '').replace(/\n/g, ' ').trim() || undefined;
  return { span: clean(raw.span), point: clean(raw.point), objection: clean(raw.objection) };
}
export function verbatimGuardOf(f: AxisFinding): VerbatimGuard | null {
  const g = ev(f).verbatim_guard;
  return g ? (g as VerbatimGuard) : null;
}
export function selfConsistencyOf(f: AxisFinding): SelfConsistency | null {
  const sc = ev(f).self_consistency;
  return sc ? (sc as SelfConsistency) : null;
}

/** Confidence line matching reporting.py `_confidence_text`: "tier — self-consistency agreement
 *  0.71 across 7 samples; verbalized medium". */
export function confidenceLine(f: AxisFinding): string {
  const c = confidenceOf(f);
  const bits: string[] = [];
  if (typeof c.agreement === 'number') {
    let agr = `self-consistency agreement ${c.agreement.toFixed(2)}`;
    if (c.n_samples != null) agr += ` across ${c.n_samples} samples`;
    bits.push(agr);
  }
  if (c.verbalized) bits.push(`verbalized ${c.verbalized}`);
  const tier = f.tier || 'n/a';
  return bits.length ? `${tier} — ${bits.join('; ')}` : tier;
}

/* --------------------------------------------------------------------- cited-paper convenience -- */

export function citedPmidLabel(g: GroundedRecord): string {
  const id = g.identifier;
  return `${id.type.toUpperCase()} ${id.value}`;
}

/* ------------------------------------------------------------------------- Markdown export ------- */

const OVERRIDE_NOTE =
  'Metadata (grounded) always overrides model/text on objective axes — a conflict is scored as '
  + 'the model being wrong, not the record.';
// Mirrors reporting.py `_SCOPE_CONSTANT_NOTE` verbatim (asterisks included) for export parity.
const SCOPE_CONSTANT_NOTE =
  'this axis grades *substance only, holding scope constant* (CONTEXT_PACK §6); species/population '
  + 'scope over-reach is carried by the scope axes above, not reflected in this grade.';
const STUB_NOTE =
  'This is the thin-slice output. Objective axes (retraction, scope) are real and metadata-grounded; '
  + 'the graded substantive-support axis is produced later by the adversarial adjudication agent with calibration.';

/** Python-`str(bool)` casing ('True'/'False') so the exported Markdown matches reporting.py. */
function pyBool(b: boolean): string {
  return b ? 'True' : 'False';
}
/** Python-`repr(list[str])` — `['a', 'b']` — matching reporting.py's f-string interpolation. */
function pyList(items: string[]): string {
  return `[${items.map((e) => `'${e}'`).join(', ')}]`;
}

function tagsMd(tags: MeshTag[]): string {
  if (!tags.length) return '(none)';
  return tags.map((t) => `${t.descriptor} [${t.tree_numbers.join(';') || 'no-tree'}]`).join(', ');
}

/**
 * A faithful Markdown reconstruction of the verdict — mirrors reporting.py `render_markdown` in
 * structure and copy (header, per-axis table, graded block, unverifiable axes, grounding, claim
 * scope, provenance legend). Used by the export bar; the HTML/JSON exports are the verbatim
 * `report_html` / `render_json`, so this is the one derived-on-the-client format.
 */
export function toMarkdown(rj: RenderJson): string {
  const g = rj.grounded;
  const scope: ScopeFrame = rj.claim_scope;
  const v = rj.verdict;
  const graded = substantiveAxis(v);
  const L: string[] = [];

  L.push('# Citation verification report', '');
  L.push(`**Claim.** ${v.claim}`, '');
  L.push(`**Cited paper.** ${g.title}  `, `${citedPmidLabel(g)}`, '');
  L.push(`## Overall: ${v.overall}`, '');

  L.push('## Per-axis findings', '');
  L.push('| Axis | Verdict | Confidence | Provenance | Basis |', '|---|---|---|---|---|');
  for (const f of orderedAxes(v)) {
    L.push(`| ${f.axis} | **${f.verdict}** | ${f.tier} | ${f.provenance} | ${f.detail.replace(/\n/g, ' ')} |`);
  }
  L.push('');

  if (graded) {
    L.push('## Substantive support (graded)', '');
    const gradeLabel = isAbstained(graded)
      ? 'NOT_ENOUGH_INFO — the agent abstained; recorded as an abstention, not scored as wrong.'
      : graded.verdict;
    L.push(`- **Grade (RB1 scale):** ${gradeLabel}`);
    L.push(`- **Confidence:** ${confidenceLine(graded)}`);
    L.push(`- **Calibration:** ${calibrationNoteOf(graded) || 'not yet available — populated by the scorer/RB3 once the corpus is scored.'}`);
    L.push(`- **Provenance:** ${graded.provenance} — ${SCOPE_CONSTANT_NOTE}`);
    if (graded.detail) L.push(`- **Rationale:** ${graded.detail.replace(/\n/g, ' ')}`);
    L.push('', '**Adversarial trace.**', '');
    const sup = spanOf(graded, 'supporter');
    const ref = spanOf(graded, 'refuter');
    L.push('- _Supporter — best supporting span:_');
    if (sup.span) { L.push(`  > ${sup.span}`); if (sup.point) L.push(`  ${sup.point}`); }
    else L.push('  _(no supporting span found)_');
    L.push('- _Refuter — strongest objection:_');
    if (ref.span) { L.push(`  > ${ref.span}`); if (ref.objection) L.push(`  ${ref.objection}`); }
    else L.push('  _(no objection span found)_');
    L.push('');
  }

  L.push('## Axes flagged unverifiable (not fabricated)', '');
  for (const [k, val] of Object.entries(v.unverifiable_axes)) L.push(`- **${k}** — ${val}`);
  L.push('');

  L.push('## Grounding evidence (structured, metadata-grounded)', '');
  const r = g.retraction;
  L.push(`- **Retraction status:** ${r.status} (source agreement: ${r.source_agreement})`);
  if (r.retraction_watch?.present) {
    const rw = r.retraction_watch;
    L.push(`  - Retraction Watch record ${rw.rw_record_id}: ${rw.reason} (date ${rw.date})`);
  }
  for (const c of r.comments_corrections) L.push(`  - NCBI ${c.ref_type}: PMID ${c.pmid} — ${c.source}`);
  if (r.ncbi_publication_type_flag) L.push("  - NCBI PublicationType flag: 'Retracted Publication' present");
  L.push(`- **Organism MeSH (tree B\\*):** ${tagsMd(g.organism_tags)} | Humans present: ${pyBool(g.has_humans)}`);
  L.push(`- **Population MeSH (tree M01.060\\*):** ${tagsMd(g.population_tags)}`);
  L.push(`- **Sex check-tags:** ${g.sex_tags.map((t) => t.descriptor).join(', ') || '(none)'}`);
  L.push('');

  L.push('## Claim scope parse (C3-lite — explicit lexical markers)', '');
  L.push(`- Asserted organism: **${scope.organism}** (provenance: ${scope.provenance}, tier: ${scope.tier}); evidence: ${scope.organism_evidence.length ? pyList(scope.organism_evidence) : '(none)'}`);
  L.push(`- Asserted population: ${scope.population || '(none)'}; evidence: ${scope.population_evidence.length ? pyList(scope.population_evidence) : '(none)'}`);
  L.push(`- Dose stated in claim: ${pyBool(scope.dose_stated)}`);
  L.push('');

  // The model-inferred legend line switches on graded presence, mirroring reporting._legend_items.
  const modelInferred = graded
    ? 'a model judgement — the C3 claim-scope hint plus the graded substantive-support axis, produced by the adversarial supporter/refuter/critic agent with calibration.'
    : 'a model judgement (in this slice, only the lightweight scope hint; the graded support axis is deferred).';
  L.push('## Provenance legend', '');
  L.push('- **metadata-grounded** — read from a structured record (Retraction Watch, MeSH tags + tree numbers, NCBI linkage). Authoritative.');
  L.push('- **text-grounded** — an explicit lexical marker in the claim wording.');
  L.push(`- **model-inferred** — ${modelInferred}`);
  L.push('- **stub-not-adjudicated** — deliberately not decided in the thin slice.');
  L.push('', `_${OVERRIDE_NOTE}_`);
  if (v.stub) L.push('', `> ${STUB_NOTE}`);

  return L.join('\n') + '\n';
}
