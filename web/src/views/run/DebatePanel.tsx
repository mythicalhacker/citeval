/**
 * DebatePanel — the live adversarial adjudication (07_uiux.md LR-02). Once Adjudicate starts, a
 * DebateCard streams in per round (supporter vs refuter, the critic's grade, running agreement); a
 * ConfidenceGauge tracks the self-consistency agreement (a_exact) tinted by tier; and a grade-tally
 * strip makes the self-consistency vote *visible as it builds* instead of only reported after the
 * fact. A header tooltip un-masks the identity-blinding the model runs under (a trust signal).
 */
import { useEffect, useRef } from 'react';
import { DebateCard, ConfidenceGauge } from '../../components/common';
import { classifySubstantive, gradeStyle, offscaleStyle } from '../../design/tokens';
import { usd } from '../../lib/format';
import type { RunState } from './model';
import { liveTier, confidenceRead } from './model';
import { CacheBadge, InfoDot } from './bits';

const BLINDING_NOTE =
  'The model sees these as anonymized “Speaker A” / “Speaker B” to prevent position bias — de-anonymized here only for readability.';

export function DebatePanel({ state }: { state: RunState }) {
  const { rounds, phase, gradeCounts, agreement, result } = state;
  const bottomRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to the newest round as it streams (honours prefers-reduced-motion).
  useEffect(() => {
    if (!bottomRef.current) return;
    const reduce = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    bottomRef.current.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'nearest' });
  }, [rounds.length]);

  const done = phase === 'complete';
  const read = done
    ? confidenceRead(result)
    : { tier: liveTier(agreement), agreement, nSamples: rounds.length || undefined, abstained: false };

  const totalVotes = Object.values(gradeCounts).reduce((a, b) => a + b, 0);

  return (
    <section className="cv-card p-4 sm:p-5" aria-labelledby="cv-debate-title">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h3 id="cv-debate-title" className="flex items-center text-sm font-bold uppercase tracking-wide text-ink">
          Adversarial adjudication
          <InfoDot label={BLINDING_NOTE} />
        </h3>
        <span className="text-xs text-ink-muted tabular-nums">
          {totalVotes > 0 ? `${totalVotes} round${totalVotes === 1 ? '' : 's'} · agreement ${agreement.toFixed(2)}` : 'waiting for round 1…'}
        </span>
      </header>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_13rem] lg:items-start">
        {/* Round-by-round transcript. */}
        <div className="grid max-h-[26rem] gap-3 overflow-y-auto pr-1" role="log" aria-label="Debate rounds" aria-live="polite">
          {rounds.length === 0 ? (
            <p className="rounded-lg border border-dashed border-line px-3 py-6 text-center text-sm text-ink-muted">
              The supporter / refuter / critic panel begins once grounding is done.
            </p>
          ) : (
            rounds.map((r) => (
              <div key={r.round} className="grid gap-1">
                <DebateCard
                  round={r.round}
                  supporterStance={r.supporterStance}
                  refuterStance={r.refuterStance}
                  criticGrade={r.criticGrade}
                  agreement={r.agreement}
                />
                <div className="flex items-center justify-end gap-2 pr-1 text-xs text-ink-muted tabular-nums">
                  <CacheBadge state={r.cache} />
                  {r.deltaUsd != null ? <span title="cost of this round’s 3 Opus calls">{usd(r.deltaUsd)} this round</span> : null}
                </div>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>

        {/* Confidence + the self-consistency distribution, building live. */}
        <aside className="grid justify-items-center gap-3 lg:sticky lg:top-4">
          <ConfidenceGauge
            agreement={read.agreement}
            tier={read.tier}
            nSamples={read.nSamples}
            abstained={read.abstained}
            size={128}
          />
          <div className="w-full">
            <div className="mb-1 flex items-center justify-between text-[0.7rem] uppercase tracking-wide text-ink-muted">
              <span>Grade distribution</span>
              <span className="tabular-nums">{totalVotes}×</span>
            </div>
            <GradeTally counts={gradeCounts} total={totalVotes} />
          </div>
          {done ? (
            <p className="text-center text-[0.7rem] leading-relaxed text-ink-muted">
              {read.abstained
                ? 'Non-adjacent multimodal vote → the panel ABSTAINS rather than guess (recorded, never scored wrong).'
                : 'Self-consistency across resampled rounds — the confidence tier is earned, not asserted.'}
            </p>
          ) : null}
        </aside>
      </div>
    </section>
  );
}

/** A stacked bar of the running grade distribution — each segment coloured on the RB1 ramp. */
function GradeTally({ counts, total }: { counts: Record<string, number>; total: number }) {
  const entries = Object.entries(counts).sort((a, b) => {
    const ca = classifySubstantive(a[0]);
    const cb = classifySubstantive(b[0]);
    const ia = ca.kind === 'grade' ? ca.index : 99;
    const ib = cb.kind === 'grade' ? cb.index : 99;
    return ia - ib;
  });
  if (total === 0) {
    return <div className="h-3 w-full rounded-full" style={{ background: 'var(--cv-surface-2)' }} aria-hidden />;
  }
  return (
    <div>
      <div
        className="flex h-3 w-full overflow-hidden rounded-full border border-line"
        role="img"
        aria-label={`Grade distribution: ${entries.map(([g, n]) => `${g} ${n}`).join(', ')}`}
      >
        {entries.map(([grade, n]) => {
          const b = classifySubstantive(grade);
          const style = b.kind === 'grade' ? gradeStyle(b.index) : offscaleStyle(b.off);
          return (
            <span
              key={grade}
              title={`${grade}: ${n}`}
              style={{ width: `${(n / total) * 100}%`, background: style.background }}
            />
          );
        })}
      </div>
      <ul className="mt-1.5 grid gap-0.5">
        {entries.map(([grade, n]) => {
          const b = classifySubstantive(grade);
          const style = b.kind === 'grade' ? gradeStyle(b.index) : offscaleStyle(b.off);
          return (
            <li key={grade} className="flex items-center gap-1.5 text-[0.7rem]">
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: style.background, border: `1px solid ${style.color}` }} aria-hidden />
              <span className="min-w-0 flex-1 truncate text-ink-muted" title={grade}>{grade}</span>
              <span className="tabular-nums font-semibold text-ink">{n}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default DebatePanel;
