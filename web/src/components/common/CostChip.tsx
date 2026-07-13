/**
 * CostChip — a tabular-nums USD chip with optional token / model-call detail. Used for the live
 * cost meter, per-role costs, and batch totals. Cost is a first-class citizen of the thesis
 * (an adversarial triad on Opus is deliberately expensive — so we surface the bill honestly).
 */
import type { TokenUsage } from '../../lib/types';
import { usd, compact } from '../../lib/format';

export interface CostChipProps {
  usd: number;
  tokens?: TokenUsage | null;
  nCalls?: number;
  /** Leading label, e.g. "Total" or a role name. */
  label?: string;
  size?: 'sm' | 'md';
  className?: string;
}

export function CostChip({ usd: amount, tokens, nCalls, label, size = 'md', className = '' }: CostChipProps) {
  const tokenTitle = tokens
    ? `in ${tokens.input} · out ${tokens.output} · cache r ${tokens.cache_read} / w ${tokens.cache_write}`
    : undefined;
  const detail: string[] = [];
  if (nCalls != null) detail.push(`${nCalls} call${nCalls === 1 ? '' : 's'}`);
  if (tokens) detail.push(`${compact(tokens.input + tokens.output)} tok`);

  return (
    <span
      className={`cv-chip tabular-nums ${size === 'sm' ? 'text-xs' : ''} ${className}`}
      title={tokenTitle}
      aria-label={`Cost ${usd(amount)}${label ? ` (${label})` : ''}${detail.length ? `, ${detail.join(', ')}` : ''}`}
    >
      {label ? <span className="font-normal text-ink-muted">{label}</span> : null}
      <span className="font-bold" style={{ color: 'var(--cv-brand)' }}>{usd(amount)}</span>
      {detail.length ? <span className="font-normal text-ink-muted">{detail.join(' · ')}</span> : null}
    </span>
  );
}

export default CostChip;
