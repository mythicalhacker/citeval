/**
 * BatchView (STUB) — run many claims at once with a live, honestly-bounded-concurrency dashboard
 * and an aggregate scorecard. W1-FE-SHELL ships the stub; a W2 view session replaces this body.
 */
import { StubView } from './StubView';

export default function BatchView() {
  return (
    <StubView
      title="Batch dashboard"
      tagline="Submit a list of claim + paper pairs and watch them verify in parallel — with a true-parallel-vs-queued indicator that reflects the real worker count, plus aggregate cost and (when gold-labelled) P/R/F."
      owner="W2 · Batch view"
      todos={[
        'Editor for BatchRequest.items (paste / add rows); submit via api.startBatch(...).',
        'Item grid driven by item_update frames: queued → running → done / error, one row per item.',
        'Honest concurrency: show how many items are truly in-flight vs queued (mock uses MOCK_BATCH_CONCURRENCY).',
        'Aggregate footer from batch_progress / batch_complete: total cost (CostChip), elapsed, and P/R/F when aggregate.p_r_f is present.',
        'Per-item drill-in that opens the Verdict view for that RunResult (useShell().select(item) + goTo("verdict")).',
      ]}
      api={['api.startBatch', 'api.subscribeBatch', 'api.getBatch']}
      components={['Stepper', 'CostChip', 'GateBadge', 'GradeBadge', 'Stat']}
    />
  );
}
