/**
 * ShowcaseView (STUB) — a curated gallery of the four proof cases (retraction catch, species scope
 * mismatch, graded over-reach, honest abstention), each renderable with no API key. W1-FE-SHELL
 * ships the stub; a W2 view session replaces this body.
 */
import { StubView } from './StubView';

export default function ShowcaseView() {
  return (
    <StubView
      title="Showcase"
      tagline="Four hand-picked cases that each demonstrate a different capability — served from cached RunResults, so a judge can render real verdicts with no backend and no key."
      owner="W2 · Showcase view"
      todos={[
        'Load cached results via api.getShowcase(); pair each with its FIXTURES[].title / caption / axisFocus.',
        'Gallery cards summarising the hero axis (GateBadge / GradeBadge / ConfidenceChip) per case.',
        'Open a case → useShell().select(result) + goTo("verdict"); or "Run this live" → seed the Run view from FIXTURES[].preset.',
        'Make the abstention case legible: NOT_ENOUGH_INFO shown as off-scale, never as a low grade.',
      ]}
      api={['api.getShowcase']}
      components={['GateBadge', 'GradeBadge', 'ConfidenceChip', 'AxisScale', 'ProvenanceBadge']}
    />
  );
}
