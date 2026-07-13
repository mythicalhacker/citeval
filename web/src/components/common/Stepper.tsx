/**
 * Stepper — the five-stage pipeline progress rail: ingest → ground_retraction → ground_scope →
 * adjudicate → report (STAGE_ORDER). State per stage is either derived from the active `current`
 * stage (earlier = done, later = pending) or passed explicitly via `statuses`; a stage can be
 * marked errored. Renders as an accessible ordered list with `aria-current="step"`.
 */
import { STAGE_ORDER } from '../../lib/types';
import type { Stage } from '../../lib/types';
import { stepStyle, type StepState } from '../../design/tokens';
import { duration } from '../../lib/format';

const STAGE_LABEL: Record<Stage, string> = {
  ingest: 'Ingest',
  ground_retraction: 'Retraction',
  ground_scope: 'Scope',
  adjudicate: 'Adjudicate',
  report: 'Report',
};

// State is otherwise conveyed only by colour + an aria-hidden glyph; this text makes done/error/
// pending perceivable to assistive tech (WCAG 1.4.1 / 1.1.1).
const STATE_LABEL: Record<StepState, string> = {
  pending: 'not started',
  active: 'in progress',
  done: 'completed',
  error: 'failed',
};

export interface StepperProps {
  stages?: readonly Stage[];
  /** Active stage; earlier stages render done, later render pending (unless `statuses` overrides). */
  current?: Stage | null;
  /** Explicit per-stage states — wins over `current`. */
  statuses?: Partial<Record<Stage, StepState>>;
  /** A stage that errored. */
  errorStage?: Stage | null;
  /** Per-stage durations (ms), keyed by Stage — shown under completed stages. */
  timing?: Record<string, number>;
  orientation?: 'horizontal' | 'vertical';
  className?: string;
}

function deriveState(
  stage: Stage,
  i: number,
  currentIndex: number,
  statuses: StepperProps['statuses'],
  errorStage: Stage | null | undefined,
): StepState {
  if (statuses && statuses[stage]) return statuses[stage] as StepState;
  if (errorStage === stage) return 'error';
  if (currentIndex < 0) return 'pending';
  if (i < currentIndex) return 'done';
  if (i === currentIndex) return 'active';
  return 'pending';
}

function Glyph({ state, index }: { state: StepState; index: number }) {
  if (state === 'done') return <span aria-hidden>✓</span>;
  if (state === 'error') return <span aria-hidden>✕</span>;
  return <span aria-hidden>{index + 1}</span>;
}

export function Stepper({
  stages = STAGE_ORDER,
  current = null,
  statuses,
  errorStage = null,
  timing,
  orientation = 'horizontal',
  className = '',
}: StepperProps) {
  const currentIndex = current ? stages.indexOf(current) : -1;
  const horizontal = orientation === 'horizontal';

  return (
    <ol
      className={`flex ${horizontal ? 'flex-row items-start' : 'flex-col'} gap-1 ${className}`}
      aria-label="Pipeline progress"
    >
      {stages.map((stage, i) => {
        const state = deriveState(stage, i, currentIndex, statuses, errorStage);
        const ms = timing?.[stage];
        const showTiming = ms != null && (state === 'done' || state === 'active');
        return (
          <li
            key={stage}
            className={`flex ${horizontal ? 'flex-1 flex-col items-center text-center' : 'flex-row items-center gap-3'}`}
            aria-current={state === 'active' ? 'step' : undefined}
          >
            <div className={`flex items-center ${horizontal ? 'w-full justify-center' : ''}`}>
              {horizontal && i > 0 ? (
                <span
                  aria-hidden
                  className="h-0.5 flex-1"
                  style={{ background: i <= currentIndex ? 'var(--cv-step-done-border)' : 'var(--cv-border)' }}
                />
              ) : null}
              <span
                className="grid h-7 w-7 shrink-0 place-items-center rounded-full border text-xs font-bold"
                style={stepStyle(state)}
              >
                <Glyph state={state} index={i} />
              </span>
              {horizontal && i < stages.length - 1 ? (
                <span
                  aria-hidden
                  className="h-0.5 flex-1"
                  style={{ background: i < currentIndex ? 'var(--cv-step-done-border)' : 'var(--cv-border)' }}
                />
              ) : null}
            </div>
            <div className={horizontal ? 'mt-1' : ''}>
              <div
                className="text-xs font-semibold"
                style={{ color: state === 'pending' ? 'var(--cv-text-muted)' : 'var(--cv-text)' }}
              >
                {STAGE_LABEL[stage]}
                <span className="sr-only"> — {STATE_LABEL[state]}</span>
              </div>
              {showTiming ? <div className="text-[0.7rem] tabular-nums text-ink-muted">{duration(ms)}</div> : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export default Stepper;
