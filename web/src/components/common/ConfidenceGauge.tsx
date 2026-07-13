/**
 * ConfidenceGauge — a semicircular meter of self-consistency agreement (a_exact), tinted by the
 * confidence tier. Abstention renders as a neutral dashed arc with an "ABST" readout rather than a
 * misleading number. Companion to ConfidenceChip for the live/verdict views.
 */
import { confStyle, type ConfKey } from '../../design/tokens';
import { ratio } from '../../lib/format';

export interface ConfidenceGaugeProps {
  /** Self-consistency exact agreement (a_exact), 0–1. */
  agreement: number;
  tier?: ConfKey;
  nSamples?: number;
  abstained?: boolean;
  /** Diameter in px (the SVG scales to it). */
  size?: number;
  showLabel?: boolean;
  className?: string;
}

// Upper semicircle, radius 40 centred at (50,50); pathLength normalised to 100 for easy dashing.
const ARC = 'M 10 50 A 40 40 0 0 1 90 50';

export function ConfidenceGauge({
  agreement,
  tier = 'medium',
  nSamples,
  abstained = false,
  size = 96,
  showLabel = true,
  className = '',
}: ConfidenceGaugeProps) {
  const key: ConfKey = abstained ? 'abstain' : tier;
  const stroke = confStyle(key).color;
  const clamped = Math.min(Math.max(agreement, 0), 1);
  const label = abstained ? 'abstained' : tier;

  // role="meter" requires aria-valuenow; when the panel abstained there is no meaningful value, so
  // present the gauge as a labelled image instead of an under-specified meter.
  const ariaProps = abstained
    ? ({ role: 'img', 'aria-label': 'Self-consistency agreement: abstained' } as const)
    : ({
        role: 'meter',
        'aria-valuemin': 0,
        'aria-valuemax': 1,
        'aria-valuenow': clamped,
        'aria-valuetext': `agreement ${ratio(clamped)}, ${label} confidence`,
        'aria-label': 'Self-consistency agreement gauge',
      } as const);

  return (
    <div className={`inline-flex flex-col items-center ${className}`}>
      <svg width={size} height={size * 0.62} viewBox="0 0 100 62" {...ariaProps}>
        <path d={ARC} pathLength={100} fill="none" stroke="var(--cv-border)" strokeWidth={9} strokeLinecap="round" />
        {!abstained ? (
          <path
            d={ARC}
            pathLength={100}
            fill="none"
            stroke={stroke}
            strokeWidth={9}
            strokeLinecap="round"
            strokeDasharray={`${clamped * 100} 100`}
          />
        ) : (
          <path d={ARC} pathLength={100} fill="none" stroke={stroke} strokeWidth={9} strokeLinecap="round" strokeDasharray="4 6" opacity={0.7} />
        )}
        <text x="50" y="46" textAnchor="middle" className="tabular-nums" style={{ fill: 'var(--cv-text)', fontSize: '19px', fontWeight: 700 }}>
          {abstained ? 'ABST' : ratio(clamped)}
        </text>
      </svg>
      {showLabel ? (
        <span className="mt-0.5 text-xs font-semibold" style={{ color: stroke }}>
          {label}
          {nSamples != null ? <span className="font-normal text-ink-muted"> · {nSamples}×</span> : null}
        </span>
      ) : null}
    </div>
  );
}

export default ConfidenceGauge;
