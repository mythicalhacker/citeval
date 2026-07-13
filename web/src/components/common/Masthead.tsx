/**
 * Masthead — the app banner + the headline-stat strip. The stats are the proof points behind the
 * thesis (grounded-and-measured, not model-checks-model) and are reused by the Methodology view.
 * Numbers are the real reported results (see docs/SUBMISSION.md / design/STATUS.md); weaker figures
 * are shown honestly (scope recall is amber, not hidden).
 */
import { Stat } from './Stat';
import { USING_MOCK } from '../../lib/api';

export interface HeadlineStat {
  value: string;
  label: string;
  sub: string;
  /** 'strong' = a headline win (green); 'weak' = honestly-surfaced weakness (amber). */
  tone: 'strong' | 'weak';
}

/** The masthead / methodology headline metrics — one source, reused across views. */
export const HEADLINE_STATS: HeadlineStat[] = [
  { value: '0.90', label: 'κ (graded)', sub: 'QWK · N=27 vs. independent reference', tone: 'strong' },
  { value: '1.00', label: 'Retraction P / R', sub: 'in-domain & 45-case held-out', tone: 'strong' },
  { value: '0.71', label: 'Scope recall', sub: 'held-out · honestly labelled (pop. 0.40)', tone: 'weak' },
  { value: '0.08', label: 'ECE (recalibrated)', sub: 'LOO-CV · from 0.32 raw', tone: 'strong' },
];

function toneColor(tone: HeadlineStat['tone']): string {
  return tone === 'strong' ? 'var(--cv-conf-high-fg)' : 'var(--cv-conf-medium-fg)';
}

export interface MastheadProps {
  className?: string;
}

export function Masthead({ className = '' }: MastheadProps) {
  return (
    <header className={`border-b border-line bg-surface ${className}`}>
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-start gap-3">
          <span
            aria-hidden
            className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-lg text-lg font-black"
            style={{ background: 'var(--cv-brand)', color: 'var(--cv-brand-contrast)' }}
          >
            ✓
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-black tracking-tight text-ink">citeval</h1>
              {USING_MOCK ? (
                <span
                  className="cv-badge"
                  style={{ background: 'var(--cv-offscale-nei-bg)', color: 'var(--cv-offscale-nei-fg)', borderColor: 'var(--cv-offscale-nei-border)', borderStyle: 'dashed' }}
                  title="Every view is served by the in-process mock (mockServer.ts) — no backend, no API key."
                >
                  mock data
                </span>
              ) : null}
            </div>
            <p className="max-w-xl text-sm text-ink-muted">
              Does the cited paper actually support the claim? Grounded checks for retraction,
              species/population scope, and a graded substantive-support scale — each with a
              confidence tier and a provenance label.
            </p>
          </div>
        </div>

        <div
          className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4 lg:flex lg:gap-7"
          aria-label="Headline evaluation results"
        >
          {HEADLINE_STATS.map((s) => (
            <Stat key={s.label} value={s.value} label={s.label} sub={s.sub} accent={toneColor(s.tone)} />
          ))}
        </div>
      </div>
    </header>
  );
}

export default Masthead;
