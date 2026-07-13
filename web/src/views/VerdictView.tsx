/**
 * VerdictView (STUB) — the full verdict renderer for a single RunResult: the gated overall, the
 * per-axis findings, the graded substantive-support block, grounding evidence, and the verbatim
 * report_html. W1-FE-SHELL ships the stub; a W2 view session replaces this body.
 */
import { StubView } from './StubView';

export default function VerdictView() {
  return (
    <StubView
      title="Verdict"
      tagline="A complete, provenance-stamped verdict for one citation: the objective gates, the six-level substantive grade held separately, the adversarial trace, and the structured grounding evidence."
      owner="W2 · Verdict view"
      todos={[
        'Read the handed-off RunResult from useShell().selection (from a run, showcase pick, or batch item) — or fetch by id via api.getRun(id).',
        'Header: the gated overall (GateBadge) with the substantive grade shown alongside, held separately (AxisScale).',
        'Per-axis table: retraction / species_scope / population_scope / substantive_support, each with tier + ProvenanceBadge.',
        'Graded block: ConfidenceGauge + the supporter/refuter spans + self_consistency detail (rounds, a_exact, distribution).',
        'Grounding evidence: MeSH organism/population tags, retraction record, unverifiable axes flagged (never fabricated).',
        'Offer the verbatim report_html (e.g. in a sandboxed iframe) as the downloadable artifact.',
      ]}
      api={['api.getRun']}
      components={['GateBadge', 'AxisScale', 'GradeBadge', 'ConfidenceGauge', 'ProvenanceBadge', 'CostChip']}
    />
  );
}
