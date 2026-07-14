/**
 * bits.tsx — small shared presentational primitives for the Run view (W2-FE-RUN).
 * Anything reused by more than one run panel lives here so the panels stay focused.
 */
import type { ButtonHTMLAttributes, ReactNode } from 'react';

/* ---- form primitives (defined here so we never touch the W1-owned index.css) ----------------- */
/** Shared field styling for <input>/<textarea>/<select>. Focus ring is global (index.css). */
export const inputClass =
  'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink ' +
  'placeholder:text-ink-muted disabled:cursor-not-allowed disabled:opacity-60';

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { size?: 'sm' | 'md' };

/** The brand-filled primary action. */
export function PrimaryButton({ className = '', size = 'md', style, ...props }: BtnProps) {
  const pad = size === 'sm' ? 'px-3 py-1 text-sm' : 'px-4 py-2 text-sm';
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-semibold transition-opacity disabled:cursor-not-allowed disabled:opacity-50 ${pad} ${className}`}
      style={{ background: 'var(--cv-brand)', color: 'var(--cv-brand-contrast)', ...style }}
    />
  );
}

/** A bordered, low-emphasis secondary action. */
export function GhostButton({ className = '', size = 'md', ...props }: BtnProps) {
  const pad = size === 'sm' ? 'px-3 py-1 text-sm' : 'px-4 py-2 text-sm';
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg border border-line font-semibold text-ink-muted hover:text-ink disabled:cursor-not-allowed disabled:opacity-50 ${pad} ${className}`}
    />
  );
}

/* ---- mode banner copy: verbatim from src/citeval/demo.py (_BANNER_FULL / _BANNER_OBJECTIVE) ----
 * Reused, not reinvented (07_uiux.md ES-02 / IV-04) so the web app and the CLI say the same thing. */
export const MODE_BANNER_FULL =
  'Mode: FULL — graded adversarial adjudication (Opus 4.8). All four axes are live: the ' +
  'substantive-support grade comes from a supporter/refuter/critic panel with a self-consistency ' +
  'confidence.';
export const MODE_BANNER_OBJECTIVE =
  'Mode: OBJECTIVE-ONLY — no ANTHROPIC_API_KEY. Retraction + species/population scope are computed ' +
  'for real from structured records; the graded substantive-support axis is deferred (not faked). ' +
  'Set ANTHROPIC_API_KEY or pass --graded to enable it.';

/** A titled card section — the shared shell for every run panel. */
export function Panel({
  title, subtitle, aside, children, className = '', labelledBy,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
  labelledBy?: string;
}) {
  return (
    <section className={`cv-card p-4 sm:p-5 ${className}`} aria-labelledby={labelledBy}>
      <header className="mb-3 flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div>
          <h3 id={labelledBy} className="text-sm font-bold uppercase tracking-wide text-ink">{title}</h3>
          {subtitle ? <p className="mt-0.5 text-xs text-ink-muted">{subtitle}</p> : null}
        </div>
        {aside ? <div className="flex flex-wrap items-center gap-2">{aside}</div> : null}
      </header>
      {children}
    </section>
  );
}

/**
 * The per-round prompt-cache indicator (LR-03). Round 1 writes the shared ~6000-token evidence
 * block into the cache; every later round reads it — the adjudicator's cache breakpoint made visible.
 */
export function CacheBadge({ state }: { state: 'write' | 'hit' }) {
  const hit = state === 'hit';
  const style = hit
    ? { background: 'var(--cv-conf-high-bg)', color: 'var(--cv-conf-high-fg)' }
    : { background: 'var(--cv-conf-medium-bg)', color: 'var(--cv-conf-medium-fg)' };
  return (
    <span
      className="cv-badge"
      style={style}
      title={
        hit
          ? 'Prompt-cache HIT — this round reused the cached ~6000-token evidence block (cheap).'
          : 'Prompt-cache WRITE — round 1 loads the shared evidence block into the cache once.'
      }
    >
      {hit ? '⚡ cache hit' : '⌁ cache write'}
    </span>
  );
}

/** A tiny superscript info affordance whose explanation is available on hover + to assistive tech. */
export function InfoDot({ label }: { label: string }) {
  return (
    <span
      tabIndex={0}
      role="note"
      aria-label={label}
      title={label}
      className="ml-1 inline-grid h-4 w-4 cursor-help place-items-center rounded-full border border-line text-[0.6rem] font-bold text-ink-muted align-middle"
    >
      i
    </span>
  );
}

/** A subtle live pulse dot — pauses under prefers-reduced-motion (handled globally in index.css). */
export function PulseDot({ color = 'var(--cv-brand)' }: { color?: string }) {
  return (
    <span className="relative inline-flex h-2 w-2" aria-hidden>
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60" style={{ background: color }} />
      <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: color }} />
    </span>
  );
}
