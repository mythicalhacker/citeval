/**
 * GateBadge — the retraction / scope gate indicator. A *fired* gate (closed padlock, red) forces
 * `overall` to NOT SUPPORTED AS STATED regardless of the substantive grade; a *clear* gate (open
 * padlock, green) means no objective gate tripped. Mirrors the metadata-overrides-model invariant.
 */
import { gateStyle } from '../../design/tokens';

/** True when the run's `overall` string reports a fired objective gate. */
export function gateFiredFromOverall(overall: string | null | undefined): boolean {
  return /NOT SUPPORTED AS STATED/i.test(overall ?? '');
}

function Padlock({ closed }: { closed: boolean }) {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden focusable="false">
      <rect x="4" y="10.5" width="16" height="10" rx="2" fill="currentColor" />
      {closed ? (
        <path d="M8 10.5V7a4 4 0 0 1 8 0v3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      ) : (
        <path d="M8 10.5V7a4 4 0 0 1 7.5-1.9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      )}
    </svg>
  );
}

export interface GateBadgeProps {
  /** Whether an objective gate fired. */
  fired: boolean;
  /** Override the label text. Defaults describe the gate outcome. */
  label?: string;
  /** Hover/assistive description (e.g. the retraction reason). */
  title?: string;
  className?: string;
}

export function GateBadge({ fired, label, title, className = '' }: GateBadgeProps) {
  const text = label ?? (fired ? 'NOT SUPPORTED AS STATED' : 'No gate tripped');
  return (
    <span
      className={`cv-badge ${className}`}
      style={gateStyle(fired ? 'fired' : 'clear')}
      title={title}
      aria-label={`Objective gate ${fired ? 'fired' : 'clear'}: ${text}`}
    >
      <Padlock closed={fired} />
      {text}
    </span>
  );
}

export default GateBadge;
