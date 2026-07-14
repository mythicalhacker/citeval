/**
 * CasePicker — a segmented control across the four proof cases (retraction catch, species scope
 * mismatch, graded over-reach, honest abstention). When the Verdict view is opened directly (no
 * hand-off from a run / showcase / batch), this lets a judge load any cached case by id through the
 * real `api.getRun` path — so the view is never empty and every fixture is one click away.
 */
import type { Fixture } from '../../lib/fixtures';

export interface CasePickerProps {
  fixtures: Fixture[];
  activeRunId: string | null;
  onPick: (runId: string) => void;
  disabled?: boolean;
}

export function CasePicker({ fixtures, activeRunId, onPick, disabled }: CasePickerProps) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Worked examples</span>
      {/* A segmented toggle (each button swaps the whole verdict), not an ARIA tabs widget — so it
          uses role="group" + aria-pressed rather than tablist/tab, which would promise tabpanels and
          arrow-key navigation this control doesn't have. */}
      <div role="group" aria-label="Proof cases" className="flex flex-wrap gap-1.5">
        {fixtures.map((f) => {
          const active = f.run_id === activeRunId;
          return (
            <button
              key={f.run_id}
              type="button"
              aria-pressed={active}
              disabled={disabled}
              onClick={() => onPick(f.run_id)}
              title={f.caption}
              className="cv-chip max-w-[15rem] cursor-pointer flex-col items-start gap-0.5 text-left transition-colors hover:border-brand disabled:cursor-wait disabled:opacity-60"
              style={active ? { borderColor: 'var(--cv-brand)', background: 'var(--cv-surface)' } : undefined}
            >
              <span className="truncate text-xs font-semibold text-ink" style={active ? { color: 'var(--cv-brand)' } : undefined}>
                {f.title}
              </span>
              <span className="font-mono text-[0.62rem] uppercase tracking-wide text-ink-muted">{f.axisFocus}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default CasePicker;
