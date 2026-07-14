/**
 * PipelinePanel — the live run header (07_uiux.md LR-01 / LR-03 / LR-04). The five-stage Stepper
 * driven off stage_start/stage_end, a progress + honest ETA-range bar, the running cost chip, each
 * completed stage's one-line summary, the model call currently in flight, and any error surfaced on
 * its failing stage. An aria-live region narrates the same thing for assistive tech.
 */
import { Stepper, CostChip } from '../../components/common';
import { duration } from '../../lib/format';
import type { RunState } from './model';
import { etaRange, clockMs } from './model';
import { PulseDot } from './bits';

const STAGE_LABEL: Record<string, string> = {
  ingest: 'Ingest',
  ground_retraction: 'Retraction',
  ground_scope: 'Scope',
  adjudicate: 'Adjudicate',
  report: 'Report',
};
const ROLE_LABEL: Record<string, string> = { supporter: 'supporter', refuter: 'refuter', critic: 'critic' };

export function PipelinePanel({ state }: { state: RunState }) {
  const { phase, source, stageStatuses, stageSummaries, stageDurations, errorStage, errorMessage } = state;
  const running = phase === 'running';
  const pct = state.progress?.pct ?? (phase === 'complete' ? 100 : 0);

  // The single most-informative live status line — also the aria-live announcement.
  let live = '';
  if (state.activeCall) {
    live = `Calling ${ROLE_LABEL[state.activeCall.role]} — round ${state.activeCall.round}…`;
  } else {
    const active = (Object.keys(stageStatuses) as (keyof typeof stageStatuses)[]).find((s) => stageStatuses[s] === 'active');
    if (active) live = `${STAGE_LABEL[active] ?? active} in progress…`;
  }
  if (phase === 'complete') live = 'Run complete — verdict below.';
  if (phase === 'cancelled') live = 'Run cancelled.';
  if (phase === 'error') live = errorMessage ? `Run failed: ${errorMessage}` : 'Run failed.';

  const nCalls = state.rounds.length * 3;

  return (
    <section className="cv-card p-4 sm:p-5" aria-labelledby="cv-pipeline-title">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex items-center gap-2">
          <h3 id="cv-pipeline-title" className="text-sm font-bold uppercase tracking-wide text-ink">Pipeline</h3>
          {source ? (
            <span
              className="cv-badge"
              style={{ background: 'var(--cv-surface-2)', color: 'var(--cv-text-muted)', borderColor: 'var(--cv-border)' }}
              title={source === 'replay' ? 'Replaying a recorded run — offline, deterministic' : 'Live run (mock-backed by default)'}
            >
              {source === 'replay' ? '▶ replay' : '● live'}
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-2 tabular-nums">
          <CostChip usd={state.cost.cumulativeUsd} tokens={state.cost.tokens} nCalls={nCalls || undefined} label="cost" size="sm" />
          <span className="cv-chip text-xs" title="Elapsed pipeline time (simulated)">
            <span className="text-ink-muted">elapsed</span>
            <span className="font-bold text-ink">{clockMs(state.elapsedMs)}</span>
          </span>
        </div>
      </header>

      <Stepper statuses={stageStatuses} errorStage={errorStage} timing={stageDurations} />

      {/* Progress + honest ETA range (LR-04). Hidden once terminal. */}
      {running ? (
        <div className="mt-4">
          <div className="mb-1 flex items-center justify-between text-xs text-ink-muted">
            <span className="flex items-center gap-1.5">
              <PulseDot />
              <span aria-hidden>{live}</span>
            </span>
            <span className="tabular-nums">
              {pct.toFixed(0)}% · {etaRange(state.progress?.estRemainingMs ?? 0)}
            </span>
          </div>
          <div
            className="h-2 overflow-hidden rounded-full"
            style={{ background: 'var(--cv-surface-2)' }}
            role="progressbar"
            aria-label="Run progress"
            aria-valuenow={Math.round(pct)}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="h-full rounded-full transition-[width] duration-300"
              style={{ width: `${Math.max(2, Math.min(100, pct))}%`, background: 'var(--cv-brand)' }}
            />
          </div>
        </div>
      ) : null}

      {/* Completed-stage one-line summaries. */}
      {Object.keys(stageSummaries).length > 0 ? (
        <ul className="mt-4 grid gap-1.5">
          {(Object.keys(stageSummaries) as (keyof typeof stageSummaries)[])
            .filter((s) => stageStatuses[s] === 'done')
            .map((s) => (
              <li key={s} className="flex gap-2 text-xs">
                <span className="mt-0.5 shrink-0 font-semibold" style={{ color: 'var(--cv-conf-high-fg)' }} aria-hidden>
                  ✓
                </span>
                <span className="min-w-0">
                  <span className="font-semibold text-ink">{STAGE_LABEL[s] ?? s}</span>
                  {stageDurations[s] != null ? (
                    <span className="tabular-nums text-ink-muted"> · {duration(stageDurations[s])}</span>
                  ) : null}
                  <span className="text-ink-muted"> — {stageSummaries[s]}</span>
                </span>
              </li>
            ))}
        </ul>
      ) : null}

      {phase === 'error' && errorMessage ? (
        <div
          className="mt-4 rounded-lg border px-3 py-2 text-sm"
          role="alert"
          style={{ background: 'var(--cv-gate-fired-bg)', color: 'var(--cv-gate-fired-fg)', borderColor: 'var(--cv-gate-fired-border)' }}
        >
          <strong>{errorStage ? `${STAGE_LABEL[errorStage] ?? errorStage} failed` : 'Run failed'}.</strong> {errorMessage}
        </div>
      ) : null}

      {/* One polite live region for assistive tech — mirrors the visible status. */}
      <p className="sr-only" aria-live="polite">
        {live}
      </p>
    </section>
  );
}

export default PipelinePanel;
