/**
 * StubView — the shared placeholder scaffold for the five W1-FE-SHELL view stubs.
 *
 * Each view (RunView, BatchView, ShowcaseView, VerdictView, MethodologyView) is a minimal stub:
 * title + purpose + a TODO contract naming the design-system primitives and api methods it will
 * use. A W2 view session REPLACES the body of its one view file (this scaffold is only imported by
 * still-stubbed views). Keeping the contract here means the hand-off is self-documenting.
 */
import type { ReactNode } from 'react';

export interface StubViewProps {
  title: string;
  /** One-line description of what the view is for. */
  tagline: string;
  /** The downstream session that will implement this view. */
  owner: string;
  /** What the finished view will contain / do. */
  todos: string[];
  /** `api.ts` methods the view will call. */
  api?: string[];
  /** Design-system primitives the view will compose. */
  components?: string[];
  children?: ReactNode;
}

function ChipRow({ label, items }: { label: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</span>
      {items.map((it) => (
        <code key={it} className="cv-chip text-xs" style={{ fontFamily: 'var(--font-mono, monospace)' }}>
          {it}
        </code>
      ))}
    </div>
  );
}

export function StubView({ title, tagline, owner, todos, api = [], components = [], children }: StubViewProps) {
  return (
    <section className="mx-auto max-w-3xl px-4 py-10" aria-labelledby="stub-title">
      <div className="cv-card p-6">
        <div className="mb-1 flex items-center gap-2">
          <h2 id="stub-title" className="text-2xl font-bold text-ink">
            {title}
          </h2>
          <span
            className="cv-badge"
            style={{ background: 'var(--cv-step-active-bg)', color: 'var(--cv-step-active-fg)', borderColor: 'var(--cv-step-active-border)' }}
          >
            stub
          </span>
        </div>
        <p className="text-ink-muted">{tagline}</p>

        <div className="my-4 h-px bg-line" />

        <p className="text-sm text-ink-muted">
          Planned for <span className="font-semibold text-ink">{owner}</span>. This is a
          W1-FE-SHELL placeholder — the shell, design system, and mock-backed api client are ready;
          the view body lands next.
        </p>

        <ul className="mt-4 space-y-1.5">
          {todos.map((t) => (
            <li key={t} className="flex gap-2 text-sm text-ink">
              <span aria-hidden className="mt-0.5 text-ink-muted">
                ☐
              </span>
              <span>{t}</span>
            </li>
          ))}
        </ul>

        <div className="mt-5 space-y-2">
          <ChipRow label="api" items={api} />
          <ChipRow label="design system" items={components} />
        </div>

        {children}
      </div>
    </section>
  );
}

export default StubView;
