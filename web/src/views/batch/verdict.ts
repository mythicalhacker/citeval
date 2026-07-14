/**
 * verdict.ts (W2-FE-BATCH) — read-only projections of a RunResult for the grid.
 *
 * Pulls the handful of fields a batch row shows (gate, substantive grade, confidence, cost, timing)
 * out of the open `render_json` verdict, defensively — the wire shape is intentionally loose
 * (api_contract.md §7), so every access tolerates a missing sub-object. Also derives the objective
 * gate LABEL so a corpus replay can be scored against its committed gold label honestly.
 */
import type { RunResult, AxisFinding, SubstantiveEvidence } from '../../lib/types';
import { gateFiredFromOverall } from '../../components/common';
import { gradeIndex } from '../../design/tokens';

export interface VerdictSummary {
  overall: string;
  gateFired: boolean;
  /** The objective outcome bucket, mirroring the committed corpus gold vocabulary. */
  objectiveLabel: 'RETRACTED' | 'SCOPE_MISMATCH' | 'SUPPORTED';
  substantive: string;
  /** RB1 ordinal index (0 best … 5 worst), or -1 when off the scale (NEI / non-substantiating). */
  gradeIndex: number;
  tier: string;
  agreement: number | null;
  nSamples: number | null;
  abstained: boolean;
  provenance: string;
  title: string;
  citedType: string;
  citedValue: string;
  costUsd: number;
  totalMs: number;
}

function axis(result: RunResult, name: string): AxisFinding | undefined {
  return result.verdict?.verdict?.axis_findings?.find((a) => a.axis === name);
}

/** The objective gate outcome, derived the same way the pipeline gates `overall`. */
export function objectiveLabel(result: RunResult): VerdictSummary['objectiveLabel'] {
  const retraction = axis(result, 'retraction')?.verdict;
  if (retraction === 'RELIES_ON_RETRACTED' || retraction === 'CITED_PAPER_HAS_EOC') return 'RETRACTED';
  const species = axis(result, 'species_scope')?.verdict;
  const population = axis(result, 'population_scope')?.verdict;
  if (species === 'SCOPE_MISMATCH' || population === 'SCOPE_MISMATCH') return 'SCOPE_MISMATCH';
  return 'SUPPORTED';
}

export function summarize(result: RunResult): VerdictSummary {
  const v = result.verdict?.verdict;
  const overall = v?.overall ?? '';
  const sub = axis(result, 'substantive_support');
  const ev = (sub?.evidence ?? {}) as Partial<SubstantiveEvidence>;
  const sc = ev.self_consistency;
  const substantive = (sub?.verdict as string) ?? '—';
  const ident = result.verdict?.claim_unit?.cited_identifier ?? v?.cited_identifier;

  return {
    overall,
    gateFired: gateFiredFromOverall(overall),
    objectiveLabel: objectiveLabel(result),
    substantive,
    gradeIndex: gradeIndex(substantive),
    tier: (sub?.tier as string) ?? 'low',
    agreement: sc?.a_exact ?? ev.confidence?.agreement ?? null,
    nSamples: sc?.rounds_valid ?? ev.confidence?.n_samples ?? null,
    abstained: ev.abstained === true || substantive === 'NOT_ENOUGH_INFO',
    provenance: sub?.provenance ?? 'model-inferred',
    title: result.verdict?.grounded?.title ?? '',
    citedType: ident?.type ?? 'pmid',
    citedValue: ident?.value ?? '',
    costUsd: result.cost?.total_usd ?? 0,
    totalMs: result.timing?.total_ms ?? 0,
  };
}

/**
 * A single number for "most concerning first" sorting: a fired objective gate outranks every
 * clean grade; among clean rows a worse RB1 grade ranks higher; off-scale (abstain) sits lowest.
 * Higher = more concerning.
 */
export function severityRank(s: VerdictSummary | null): number {
  if (!s) return -1;
  if (s.gateFired) return 100 + (s.gradeIndex >= 0 ? s.gradeIndex : 0);
  if (s.gradeIndex >= 0) return s.gradeIndex;
  return -0.5; // NEI / non-substantiating — off the ordinal scale
}
