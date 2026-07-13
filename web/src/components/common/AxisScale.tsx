/**
 * AxisScale — the graded RB1 ordinal ramp (best 0 → worst 5) with a marker at the current grade,
 * plus honest handling of the two off-scale outcomes (NOT_ENOUGH_INFO abstention, N/A —
 * non-substantiating). This is the visual home of the graded-scale 6-colour ramp.
 *
 * `GradeBadge` (also exported) is the compact single-grade pill used inside tables / debate cards.
 */
import { RB1_GRADES } from '../../lib/types';
import {
  GRADE_TOKENS, classifySubstantive, gradeStyle, offscaleStyle, type OffScaleKind,
} from '../../design/tokens';

const OFFSCALE_LABEL: Record<OffScaleKind, string> = {
  nei: 'NOT_ENOUGH_INFO',
  nonsub: 'N/A — non-substantiating',
};
const OFFSCALE_GLOSS: Record<OffScaleKind, string> = {
  nei: 'The panel abstained — recorded as an abstention, never scored as wrong.',
  nonsub: 'The citation is non-substantiating; the ordinal support scale does not apply.',
};

/* -------------------------------------------------------------------------- GradeBadge --------- */
export interface GradeBadgeProps {
  verdict: string;
  className?: string;
}

export function GradeBadge({ verdict, className = '' }: GradeBadgeProps) {
  const b = classifySubstantive(verdict);
  const style = b.kind === 'grade' ? gradeStyle(b.index) : offscaleStyle(b.off);
  const dashed = b.kind === 'offscale';
  return (
    <span
      className={`cv-badge ${className}`}
      style={{ ...style, borderStyle: dashed ? 'dashed' : undefined }}
      aria-label={`Substantive support grade: ${verdict}`}
    >
      {b.kind === 'grade' ? `${b.index}· ${verdict}` : OFFSCALE_LABEL[b.off]}
    </span>
  );
}

/* -------------------------------------------------------------------------- AxisScale ---------- */
export interface AxisScaleProps {
  /** The substantive_support verdict (an RB1 grade or an off-scale outcome). */
  verdict: string;
  /** Show the grade name + best/worst endpoints under the ramp. */
  showLabels?: boolean;
  className?: string;
}

export function AxisScale({ verdict, showLabels = true, className = '' }: AxisScaleProps) {
  const bucket = classifySubstantive(verdict);
  const activeIndex = bucket.kind === 'grade' ? bucket.index : -1;
  const offscale = bucket.kind === 'offscale';

  const ariaLabel = offscale
    ? `Substantive support: ${OFFSCALE_LABEL[bucket.off]} — off the RB1 ordinal scale. ${OFFSCALE_GLOSS[bucket.off]}`
    : `Substantive support: ${verdict} — grade ${activeIndex} of ${RB1_GRADES.length - 1} on the RB1 scale, best (0) to worst (5).`;

  return (
    <div className={className}>
      <div
        className="flex items-stretch gap-0.5"
        role="img"
        aria-label={ariaLabel}
        style={{ opacity: offscale ? 0.4 : 1 }}
      >
        {GRADE_TOKENS.map((_, i) => {
          const active = i === activeIndex;
          const first = i === 0;
          const last = i === GRADE_TOKENS.length - 1;
          return (
            <div
              key={i}
              className="relative h-6 flex-1"
              style={{
                ...gradeStyle(i),
                opacity: active || offscale ? 1 : 0.5,
                borderTopLeftRadius: first ? 6 : 0,
                borderBottomLeftRadius: first ? 6 : 0,
                borderTopRightRadius: last ? 6 : 0,
                borderBottomRightRadius: last ? 6 : 0,
                boxShadow: active ? 'inset 0 0 0 2px var(--cv-text)' : undefined,
              }}
            >
              {active ? (
                <span
                  aria-hidden
                  className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-[0.7rem] font-bold"
                  style={{ color: 'var(--cv-text)' }}
                >
                  {i}
                </span>
              ) : null}
            </div>
          );
        })}
      </div>

      {showLabels ? (
        <div className="mt-1.5 flex items-center justify-between gap-2">
          <span className="text-[0.7rem] text-ink-muted">supported (0)</span>
          <span className="text-xs font-semibold text-ink">
            {offscale ? (
              <span title={OFFSCALE_GLOSS[bucket.off]}>{OFFSCALE_LABEL[bucket.off]} · off scale</span>
            ) : (
              verdict
            )}
          </span>
          <span className="text-[0.7rem] text-ink-muted">contradicted (5)</span>
        </div>
      ) : null}
    </div>
  );
}

export default AxisScale;
