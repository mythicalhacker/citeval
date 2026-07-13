/**
 * Stat — the tabular-nums headline-stat type used in the masthead strip and the methodology view.
 * A big aligned figure over a small caption, with an optional sub-line and accent colour.
 */
import type { ReactNode } from 'react';

export interface StatProps {
  /** The figure — pre-formatted (e.g. "0.90", "1.00", "$1.05"). */
  value: ReactNode;
  /** Small caption under the figure. */
  label: string;
  /** Optional smaller qualifier line (e.g. "in-domain & held-out"). */
  sub?: string;
  /** CSS colour (or var) for the figure; defaults to the ink colour. */
  accent?: string;
  size?: 'md' | 'lg';
  className?: string;
}

export function Stat({ value, label, sub, accent, size = 'md', className = '' }: StatProps) {
  const valueClass = size === 'lg' ? 'text-3xl sm:text-4xl' : 'text-2xl sm:text-3xl';
  return (
    <div className={`flex flex-col gap-0.5 ${className}`}>
      <span className={`cv-stat-value ${valueClass}`} style={accent ? { color: accent } : undefined}>
        {value}
      </span>
      <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</span>
      {sub ? <span className="text-xs text-ink-muted">{sub}</span> : null}
    </div>
  );
}

export default Stat;
