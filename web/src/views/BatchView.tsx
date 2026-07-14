/**
 * BatchView (W2-FE-BATCH) — the parallel multi-paper dashboard.
 *
 * Submit a list of claim + cited-paper pairs (hand-entered, pasted, or a one-click replay of the
 * committed proof cases / calibration corpora) and watch them verify in parallel: a live aggregate
 * scorecard (done/total, running cost, elapsed, ETA), an HONEST concurrency indicator read straight
 * off the stream, and a sortable/filterable grid where each row streams queued → running → done /
 * failed, then drills into the full Verdict view. Per-item failures are isolated — one item's error
 * never stops the batch.
 *
 * Owns only this file + views/batch/*. Talks to the backend solely through the W1 api client and to
 * the shell solely through useShell() — so it drops in without touching App.tsx or the contracts.
 */
import { useEffect } from 'react';
import { useShell } from '../shell/ShellContext';
import { installBatchStyles } from './batch/styles';
import { useBatchRun } from './batch/useBatchRun';
import type { ItemState, PlannedItem } from './batch/model';
import { BatchComposer } from './batch/BatchComposer';
import { AggregateHeader } from './batch/AggregateHeader';
import { ItemGrid } from './batch/ItemGrid';

export default function BatchView() {
  const { goTo, select } = useShell();
  const { state, start, cancel } = useBatchRun();

  useEffect(() => {
    installBatchStyles();
  }, []);

  const run = (items: PlannedItem[], opts: { speed: number }) => {
    const speed = Number.isFinite(opts.speed) ? opts.speed : undefined;
    start(items, speed != null ? { speed } : { speed: Infinity });
  };

  const openVerdict = (item: ItemState) => {
    if (!item.result) return;
    select(item.result);
    goTo('verdict');
  };

  const streaming = state.phase === 'streaming' || state.phase === 'starting';
  const hasBatch = state.items.length > 0;

  return (
    <section className="mx-auto max-w-6xl px-4 py-6" aria-labelledby="batch-title">
      <header className="mb-4">
        <h2 id="batch-title" className="text-2xl font-bold text-ink">
          Batch dashboard
        </h2>
        <p className="mt-1 max-w-3xl text-ink-muted">
          Verify many citations in parallel. Watch a live aggregate scorecard and a true-parallel-vs-queued
          indicator that reflects the real worker count — then drill into any row for its full verdict.
        </p>
      </header>

      <BatchComposer onRun={run} disabled={streaming} usingMock={state.usingMock} />

      {state.phase === 'failed' && state.error ? (
        <p
          className="mt-4 rounded-md border px-3 py-2 text-sm"
          role="alert"
          style={{ background: 'var(--cv-gate-fired-bg)', color: 'var(--cv-gate-fired-fg)', borderColor: 'var(--cv-gate-fired-border)' }}
        >
          Batch failed to start: {state.error}
        </p>
      ) : null}

      {hasBatch ? (
        <div className="mt-4">
          <AggregateHeader state={state} onCancel={cancel} />
          <ItemGrid items={state.items} usingMock={state.usingMock} onOpen={openVerdict} />
        </div>
      ) : null}
    </section>
  );
}
