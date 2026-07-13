/**
 * RunView (STUB) — the flagship: enter a claim + cited paper, watch the pipeline verify it live,
 * and read the verdict. W1-FE-SHELL ships the stub; a W2 view session replaces this body.
 */
import { StubView } from './StubView';

export default function RunView() {
  return (
    <StubView
      title="Verify a citation"
      tagline="Enter a scientific claim and the paper cited to support it — watch the five-stage pipeline stream retraction, scope, and a graded substantive-support verdict in real time."
      owner="W2 · Run view"
      todos={[
        'Input form: claim + paper_ref / citation_string / manuscript_text, with a mode selector and one-click presets from FIXTURES.',
        'On submit, call api.startRun(...) and drive the Stepper from stage_start / stage_end frames.',
        'Live adjudication: render a DebateCard per debate_round; track running agreement on a ConfidenceGauge.',
        'Live cost + ETA: CostChip from cost_update, progress bar from progress frames.',
        'On run_complete, render the verdict inline (GateBadge, AxisScale, ProvenanceBadge) or hand off via useShell().select(result) + goTo("verdict").',
        'Error handling: surface an error frame on the failing stage of the Stepper.',
      ]}
      api={['api.startRun', 'api.subscribeRun', 'api.getRun', 'api.getPricing']}
      components={['Stepper', 'DebateCard', 'ConfidenceGauge', 'CostChip', 'GateBadge', 'AxisScale', 'ProvenanceBadge']}
    />
  );
}
