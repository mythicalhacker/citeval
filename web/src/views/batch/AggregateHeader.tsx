/**
 * AggregateHeader (W2-FE-BATCH) — the live scorecard above the grid.
 *
 * A segmented progress bar (done · failed · running · queued), a tabular-nums stat strip
 * (complete / cost / elapsed / est-remaining), the honest ConcurrencyMeter, and — when the batch
 * carries gold labels — P/R/F (if the server computed it) or a locally-computed gold-agreement over
 * the rows that produced a real verdict. In mock mode a stand-in banner states plainly which numbers
 * are illustrative, matching the integrity convention the fixtures already use.
 */
import { Stat, CostChip } from '../../components/common';
import { usd, duration, pct as fmtPct } from '../../lib/format';
import type { BatchState, DerivedCounts } from './model';
import { deriveCounts } from './model';
import { summarize } from './verdict';
import { isStandIn } from './presets';
import { ConcurrencyMeter } from './ConcurrencyMeter';

const PHASE_LABEL: Record<BatchState['phase'], string> = {
  idle: 'Ready',
  starting: 'Starting…',
  streaming: 'Running',
  complete: 'Complete',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

/** Gold-agreement over rows that produced a REAL verdict (stand-ins are excluded, honestly). */
function goldAgreement(state: BatchState): { scored: number; agree: number } {
  let scored = 0;
  let agree = 0;
  for (const it of state.items) {
    if (!it.corpus || !it.result) continue;
    if (isStandIn(it.paperRef, state.usingMock)) continue;
    scored += 1;
    if (summarize(it.result).objectiveLabel === it.corpus.gold_label) agree += 1;
  }
  return { scored, agree };
}

function StatusPill({ phase }: { phase: BatchState['phase'] }) {
  const streaming = phase === 'streaming' || phase === 'starting';
  const style =
    phase === 'complete'
      ? { background: 'var(--cv-step-done-bg)', color: 'var(--cv-step-done-fg)', borderColor: 'var(--cv-step-done-border)' }
      : phase === 'failed'
        ? { background: 'var(--cv-gate-fired-bg)', color: 'var(--cv-gate-fired-fg)', borderColor: 'var(--cv-gate-fired-border)' }
        : streaming
          ? { background: 'var(--cv-step-active-bg)', color: 'var(--cv-step-active-fg)', borderColor: 'var(--cv-step-active-border)' }
          : { background: 'var(--cv-surface-2)', color: 'var(--cv-text-muted)', borderColor: 'var(--cv-border)' };
  // `cancelled` falls through to the neutral (muted) style above — a stopped, not failed, batch.
  return (
    <span className="cv-badge" style={style}>
      {streaming ? <span aria-hidden className="cv-batch-indeterminate-dot" /> : null}
      {PHASE_LABEL[phase]}
    </span>
  );
}

export interface AggregateHeaderProps {
  state: BatchState;
  onCancel?: () => void;
}

export function AggregateHeader({ state, onCancel }: AggregateHeaderProps) {
  const counts: DerivedCounts = deriveCounts(state);
  const total = counts.total || 1;
  const seg = (n: number) => `${(100 * n) / total}%`;

  const streaming = state.phase === 'streaming' || state.phase === 'starting';
  const etaMs =
    streaming && counts.terminal > 0 && counts.terminal < total
      ? (state.elapsedMs / counts.terminal) * (total - counts.terminal)
      : null;

  // The batch ran in parallel: `elapsedMs` is wall time, `aggregate.total_ms` is the serial sum of
  // per-item durations. Their ratio is the effective parallelism — an honest speedup figure.
  const serialMs = state.aggregate?.total_ms ?? null;
  const parallelX = serialMs != null && state.elapsedMs > 0 ? serialMs / state.elapsedMs : null;
  const elapsedSub =
    etaMs != null
      ? `~${duration(etaMs)} left (est.)`
      : serialMs != null
        ? `Σ ${duration(serialMs)} serial${parallelX && parallelX >= 1.05 ? ` · ${parallelX.toFixed(1)}× parallel` : ''}`
        : 'wall clock';

  const prf = state.aggregate?.p_r_f ?? null;
  const corpusMode = state.items.some((it) => it.corpus);
  const standIns = state.items.filter((it) => isStandIn(it.paperRef, state.usingMock)).length;
  const gold = corpusMode ? goldAgreement(state) : null;

  return (
    <section className="cv-card p-4 sm:p-5" aria-label="Batch aggregate">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-bold text-ink">Aggregate</h3>
          <StatusPill phase={state.phase} />
          {state.batchId ? (
            <code className="text-xs text-ink-muted" style={{ fontFamily: 'var(--font-mono, monospace)' }}>
              {state.batchId}
            </code>
          ) : null}
        </div>
        {streaming && onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="cv-chip"
            style={{ cursor: 'pointer' }}
            aria-label="Cancel the running batch"
          >
            Cancel
          </button>
        ) : null}
      </div>

      {/* Segmented progress bar: done · error · running · queued. */}
      <div
        className="mt-3 flex h-2.5 w-full overflow-hidden rounded-full"
        style={{ background: 'var(--cv-surface-2)' }}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={counts.terminal}
        aria-label={`${counts.terminal} of ${total} items complete`}
      >
        <span style={{ width: seg(counts.done), background: 'var(--cv-step-done-border)' }} />
        <span style={{ width: seg(counts.error), background: 'var(--cv-gate-fired-fg)' }} />
        <span className="relative overflow-hidden" style={{ width: seg(counts.running), background: 'var(--cv-brand)' }}>
          {counts.running > 0 ? <span className="cv-batch-indeterminate" /> : null}
        </span>
        <span style={{ width: seg(counts.queued), background: 'transparent' }} />
      </div>

      {/* Stat strip. */}
      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat
          value={
            <span>
              {counts.terminal}
              <span className="text-ink-muted"> / {total}</span>
            </span>
          }
          label="Complete"
          sub={counts.error > 0 ? `${counts.error} failed · ${counts.running} running` : `${counts.running} running · ${counts.queued} queued`}
        />
        <Stat value={usd(state.costUsd)} label="Total cost" accent="var(--cv-brand)" sub={`${counts.done} adjudicated`} />
        <Stat value={duration(state.elapsedMs)} label="Elapsed" sub={elapsedSub} />
        <div className="flex items-end">
          <ConcurrencyMeter
            running={counts.running}
            queued={counts.queued}
            peakInFlight={state.peakInFlight}
            usingMock={state.usingMock}
          />
        </div>
      </div>

      {/* P/R/F (server-computed) or corpus gold-agreement (local, honest). */}
      {prf ? (
        <div className="mt-4 flex flex-wrap gap-4 border-t border-line pt-3">
          <Stat size="md" value={fmtPct(prf.precision * 100, 1)} label="Precision" />
          <Stat size="md" value={fmtPct(prf.recall * 100, 1)} label="Recall" />
          <Stat size="md" value={fmtPct(prf.f1 * 100, 1)} label="F1" />
          <span className="self-center text-xs text-ink-muted">vs. gold labels</span>
        </div>
      ) : corpusMode ? (
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line pt-3 text-sm">
          <span className="font-semibold text-ink">Gold agreement</span>
          {gold && gold.scored > 0 ? (
            <span className="tabular-nums text-ink">
              {gold.agree} / {gold.scored} <span className="text-ink-muted">of scored rows match committed gold</span>
            </span>
          ) : (
            <span className="text-ink-muted">no rows scored yet{state.usingMock ? ' — real verdicts need a live backend' : ''}</span>
          )}
          {standIns > 0 ? (
            <span className="text-xs text-ink-muted">· {standIns} stand-in rows excluded from scoring</span>
          ) : null}
        </div>
      ) : null}

      {/* Honest stand-in banner — shown whenever ANY mock row is a stand-in (corpus OR
          hand-entered), so a fabricated verdict is never presented without this caveat. */}
      {standIns > 0 && state.usingMock ? (
        <p className="mt-3 rounded-md border border-line px-3 py-2 text-xs text-ink-muted" style={{ background: 'var(--cv-surface-2)' }}>
          <strong className="text-ink">Illustrative {corpusMode ? 'replay' : 'verdicts'}.</strong>{' '}
          {corpusMode ? 'The claims, cited papers, and gold labels are the real committed corpus. ' : ''}
          With no NCBI/Opus access the mock renders an <em>illustrative stand-in</em> verdict &amp; cost for any
          paper it has no fixture for ({standIns} of {total} row{standIns === 1 ? '' : 's'}, marked{' '}
          <em>stand-in (mock)</em> below) — the dashboard mechanics (parallelism, aggregates, isolation) are real.
          Run with a live backend (<code style={{ fontFamily: 'var(--font-mono, monospace)' }}>VITE_USE_MOCK=false</code>) for real verdicts.
        </p>
      ) : null}

      {/* aria-live: announce only discrete completion progress (and a final summary), NOT the
          per-frame cost — otherwise a screen reader re-announces on essentially every stream frame. */}
      <span className="sr-only" aria-live="polite">
        {state.phase === 'complete' || state.phase === 'failed' || state.phase === 'cancelled'
          ? `Batch ${PHASE_LABEL[state.phase].toLowerCase()}: ${counts.done} of ${total} verified${counts.error > 0 ? `, ${counts.error} not completed` : ''}, ${usd(state.costUsd)} total.`
          : `${counts.terminal} of ${total} complete.`}
      </span>
    </section>
  );
}

export default AggregateHeader;
