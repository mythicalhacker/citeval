/**
 * ConfidenceChip — a compact tier pill (high / medium / low / abstained) with the self-consistency
 * agreement and sample count. The honest-confidence story in one glance.
 */
import { confStyle, type ConfKey } from '../../design/tokens';
import { ratio } from '../../lib/format';

export interface ConfidenceChipProps {
  tier: ConfKey;
  /** Self-consistency exact agreement (a_exact), 0–1. */
  agreement?: number;
  nSamples?: number;
  abstained?: boolean;
  className?: string;
}

export function ConfidenceChip({ tier, agreement, nSamples, abstained, className = '' }: ConfidenceChipProps) {
  const key: ConfKey = abstained ? 'abstain' : tier;
  const label = abstained ? 'abstained' : tier;
  const detail =
    agreement != null
      ? `agreement ${ratio(agreement)}${nSamples != null ? ` · ${nSamples} samples` : ''}`
      : nSamples != null
        ? `${nSamples} samples`
        : '';
  return (
    <span
      className={`cv-badge ${className}`}
      style={confStyle(key)}
      aria-label={`Confidence: ${label}${detail ? `, ${detail}` : ''}`}
    >
      <span className="font-bold uppercase tracking-wide">{label}</span>
      {detail ? <span className="font-normal opacity-90">{detail}</span> : null}
    </span>
  );
}

export default ConfidenceChip;
