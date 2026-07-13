/**
 * DebateCard — one round of the adversarial triad (supporter vs refuter, adjudicated by the
 * critic). Renders the two opposing stances, the critic's ordinal grade for the round, and the
 * running self-consistency agreement. Shapes match the `debate_round` SSE event.
 */
import { GradeBadge } from './AxisScale';
import { ratio } from '../../lib/format';

export interface DebateCardProps {
  round: number;
  supporterStance: string;
  refuterStance: string;
  criticGrade: string;
  /** Running exact-agreement (a_exact) after this round, 0–1. */
  agreement: number;
  className?: string;
}

function Lane({ role, color, text }: { role: string; color: string; text: string }) {
  return (
    <div className="flex gap-2">
      <span className="mt-1 h-2 w-2 shrink-0 rounded-full" style={{ background: color }} aria-hidden />
      <div>
        <div className="text-[0.7rem] font-bold uppercase tracking-wide" style={{ color }}>
          {role}
        </div>
        <p className="text-sm text-ink">{text}</p>
      </div>
    </div>
  );
}

export function DebateCard({ round, supporterStance, refuterStance, criticGrade, agreement, className = '' }: DebateCardProps) {
  return (
    <article className={`cv-card p-3 ${className}`} aria-label={`Debate round ${round}`}>
      <header className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs font-bold uppercase tracking-wide text-ink-muted">Round {round}</span>
        <span className="flex items-center gap-2">
          <span className="text-xs tabular-nums text-ink-muted" title="running exact agreement (a_exact)">
            agreement {ratio(agreement)}
          </span>
          <GradeBadge verdict={criticGrade} />
        </span>
      </header>
      <div className="grid gap-2.5">
        <Lane role="Supporter" color="var(--cv-conf-high-fg)" text={supporterStance} />
        <Lane role="Refuter" color="var(--cv-gate-fired-fg)" text={refuterStance} />
      </div>
    </article>
  );
}

export default DebateCard;
