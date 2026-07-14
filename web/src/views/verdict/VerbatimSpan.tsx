/**
 * VerbatimSpan (VV-05) — one adversarial span rendered as a blockquote with a "verbatim-guard ✓"
 * micro-badge. The badge ties the visual directly to CLAUDE.md invariant #5: any stored quote must
 * be a verified verbatim substring of the source's whitespace-normalised full text. A tooltip
 * explains the check in one sentence.
 */
import type { SpanEvidence, VerbatimGuard } from './model';

export interface VerbatimSpanProps {
  role: 'supporter' | 'refuter';
  span: SpanEvidence;
  /** The run-level verbatim guard summary (discards + grounding corpus), if present. */
  guard?: VerbatimGuard | null;
}

const ROLE_META = {
  supporter: {
    label: 'Supporter — best supporting span',
    color: 'var(--cv-conf-high-fg)',
    glossKey: 'point' as const,
  },
  refuter: {
    label: 'Refuter — strongest objection',
    color: 'var(--cv-gate-fired-fg)',
    glossKey: 'objection' as const,
  },
};

const GUARD_TITLE =
  'Verbatim guard: this quote was verified to be a character-for-character substring of the cited '
  + "paper's whitespace-normalised full text — never paraphrased or invented (CLAUDE.md invariant #5).";

export function VerbatimSpan({ role, span, guard }: VerbatimSpanProps) {
  const meta = ROLE_META[role];
  const quote = (span.span ?? '').trim();
  const gloss = (span[meta.glossKey] ?? '').trim();
  const discarded = role === 'supporter' ? guard?.supporter_discarded : guard?.refuter_discarded;

  return (
    <div className="grid gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className="inline-flex items-center gap-1.5 text-[0.72rem] font-bold uppercase tracking-wide"
          style={{ color: meta.color }}
        >
          <span aria-hidden className="h-2 w-2 rounded-full" style={{ background: meta.color }} />
          {meta.label}
        </span>
        {quote ? (
          <span
            className="cv-badge"
            style={{
              background: 'var(--cv-conf-high-bg)',
              color: 'var(--cv-conf-high-fg)',
            }}
            title={GUARD_TITLE}
          >
            <span aria-hidden>✓</span> verbatim-guard
          </span>
        ) : null}
      </div>

      {quote ? (
        <blockquote
          className="border-l-4 pl-3 pr-2 py-1.5 text-sm italic"
          style={{ borderColor: meta.color, background: 'var(--cv-surface-2)', color: 'var(--cv-text)' }}
        >
          “{quote}”
        </blockquote>
      ) : (
        <p className="text-sm italic text-ink-muted">
          ({role === 'supporter' ? 'no supporting span found' : 'no objection span found'})
        </p>
      )}

      {gloss ? <p className="text-sm text-ink-muted">{gloss}</p> : null}

      {discarded && discarded > 0 ? (
        <p className="text-xs text-ink-muted">
          {discarded} candidate {discarded === 1 ? 'span' : 'spans'} discarded by the verbatim guard
          (not a substring of the source).
        </p>
      ) : null}
    </div>
  );
}

export default VerbatimSpan;
