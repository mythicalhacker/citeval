/**
 * MethodologyView (STUB) — the "why trust this" view: the thesis, the non-negotiable invariants,
 * the headline results, the cost model, and the provenance legend. W1-FE-SHELL ships the stub; a
 * W2 view session replaces this body.
 */
import { StubView } from './StubView';

export default function MethodologyView() {
  return (
    <StubView
      title="Methodology"
      tagline="Grounded-and-measured, not model-checks-model: how every verdict is anchored in external structured truth, why metadata overrides the model, and what the numbers actually say."
      owner="W2 · Methodology view"
      todos={[
        'Thesis + the non-negotiable invariants (metadata overrides model; tier + provenance on every finding; unverifiable axes flagged).',
        'Headline results (reuse HEADLINE_STATS): κ, retraction P/R, scope recall, ECE — with the honest weak spots called out.',
        'Provenance legend (metadata-grounded / text-grounded / model-inferred / stub) matching reporting.py, via ProvenanceBadge.',
        'The graded RB1 scale explained with AxisScale; the off-scale outcomes (abstention, non-substantiating).',
        'Cost model from api.getPricing(): per-million-token tiers and why an Opus triad is deliberately expensive.',
      ]}
      api={['api.getPricing']}
      components={['Stat', 'HEADLINE_STATS', 'ProvenanceBadge', 'AxisScale', 'CostChip']}
    />
  );
}
