/**
 * AxisTable (VV-02) — the per-axis findings table: retraction / species_scope / population_scope /
 * substantive_support, each with its verdict, confidence tier, and a provenance badge. A typographic
 * upgrade of reporting.py `_axis_table_html`, carrying the same five columns so the app table reads
 * identically to the embedded report. Objective-axis verdicts are colour-cued by outcome; the
 * substantive row shows the RB1 GradeBadge (off-scale for abstention).
 */
import type { AxisFinding, VerdictCore } from '../../lib/types';
import { GradeBadge, ProvenanceBadge } from '../../components/common';
import { confStyle, gateStyle, type TokenStyle } from '../../design/tokens';
import { orderedAxes, AXIS_LABEL, confKeyOf } from './model';

/** Colour an objective-axis verdict by outcome: a fired gate reads red, a clear pass green, an
 *  un-assessed axis stays neutral slate. */
function objectiveVerdictStyle(verdict: string): TokenStyle {
  switch (verdict) {
    case 'RELIES_ON_RETRACTED':
    case 'CITED_PAPER_HAS_EOC':
    case 'SCOPE_MISMATCH':
      return gateStyle('fired');
    case 'NOT_RETRACTED':
    case 'SCOPE_CONSISTENT':
      return gateStyle('clear');
    default:
      return { background: 'var(--cv-offscale-nei-bg)', color: 'var(--cv-offscale-nei-fg)', borderColor: 'var(--cv-offscale-nei-border)' };
  }
}

function VerdictCell({ finding }: { finding: AxisFinding }) {
  if (finding.axis === 'substantive_support') return <GradeBadge verdict={finding.verdict} />;
  return (
    <span className="cv-badge" style={objectiveVerdictStyle(finding.verdict)}>
      {finding.verdict}
    </span>
  );
}

function TierPill({ finding }: { finding: AxisFinding }) {
  const key = confKeyOf(finding);
  const label = key === 'abstain' ? 'abstain' : (finding.tier || 'n/a');
  return (
    <span className="cv-badge" style={confStyle(key)}>
      <span className="uppercase tracking-wide">{label}</span>
    </span>
  );
}

export interface AxisTableProps {
  verdict: VerdictCore;
}

export function AxisTable({ verdict }: AxisTableProps) {
  const rows = orderedAxes(verdict);
  return (
    <section aria-labelledby="axes-heading">
      <h3 id="axes-heading" className="mb-3 text-lg font-bold text-ink">
        Per-axis findings
      </h3>
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">
            Per-axis verdicts with confidence tier and provenance for retraction, species scope,
            population scope, and substantive support.
          </caption>
          <thead>
            <tr className="bg-surface-2 text-left">
              <th scope="col" className="px-3 py-2 font-semibold text-ink">Axis</th>
              <th scope="col" className="px-3 py-2 font-semibold text-ink">Verdict</th>
              <th scope="col" className="px-3 py-2 font-semibold text-ink">Confidence</th>
              <th scope="col" className="px-3 py-2 font-semibold text-ink">Provenance</th>
              <th scope="col" className="px-3 py-2 font-semibold text-ink">Basis</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr key={f.axis} className="border-t border-line align-top">
                <th scope="row" className="whitespace-nowrap px-3 py-2 text-left font-medium text-ink">
                  {AXIS_LABEL[f.axis] ?? f.axis}
                </th>
                <td className="px-3 py-2"><VerdictCell finding={f} /></td>
                <td className="px-3 py-2"><TierPill finding={f} /></td>
                <td className="px-3 py-2">
                  <ProvenanceBadge provenance={f.provenance} short />
                </td>
                <td className="px-3 py-2 text-ink-muted">{f.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default AxisTable;
