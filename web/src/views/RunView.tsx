/**
 * RunView (W2-FE-RUN) — the flagship "Verify" surface.
 *
 * Enter a claim + the paper cited to support it (or one-click a recorded case), then watch the
 * five-stage pipeline stream live: the Stepper advances off stage frames, an adversarial debate
 * card streams in per round with a running ConfidenceGauge, the cost/ETA bar ticks, and on
 * run_complete the verdict renders inline (gate + graded scale + provenance) with a hand-off to the
 * full Verdict view. A Live⇄Replay toggle plays a recorded run with no key or network, so the whole
 * flow demos offline.
 *
 * Owns only this file + views/run/*. All streaming lives in useRunEngine; all folding in run/model;
 * cross-view hand-off goes through the W1 shell seam (useShell), never App.tsx.
 */
import { useEffect, useRef } from 'react';
import { useShell } from '../shell/ShellContext';
import type { RunRequest } from '../lib/types';
import { useRunEngine } from './run/useRunEngine';
import type { RunSource } from './run/model';
import { RunForm } from './run/RunForm';
import { PipelinePanel } from './run/PipelinePanel';
import { DebatePanel } from './run/DebatePanel';
import { VerdictPanel } from './run/VerdictPanel';
import { GhostButton } from './run/bits';

export default function RunView() {
  const { select, goTo } = useShell();
  const { state, start, cancel, reset } = useRunEngine();

  const active = state.phase !== 'idle';
  const running = state.phase === 'running';

  // Keyboard-focus management: the form unmounts when a run starts and the verdict mounts when it
  // completes, so move focus into the new content (preventScroll keeps the viewport put for sighted
  // users while assistive tech follows the flow). Keyed on phase so it fires once per transition.
  const statusRef = useRef<HTMLDivElement>(null);
  const verdictHeadingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (state.phase === 'complete') verdictHeadingRef.current?.focus({ preventScroll: true });
    else if (state.phase !== 'idle') statusRef.current?.focus({ preventScroll: true });
  }, [state.phase]);

  const onRun = (request: RunRequest, source: RunSource, speed: number) => start(request, source, speed);

  const openVerdict = () => {
    if (!state.result) return;
    select(state.result);
    goTo('verdict');
  };

  // Show the debate once adjudication is under way (or done) — before that its empty state is noise.
  const showDebate =
    state.rounds.length > 0 ||
    state.stageStatuses.adjudicate === 'active' ||
    state.stageStatuses.adjudicate === 'done' ||
    state.phase === 'complete';

  return (
    <section className="mx-auto grid max-w-4xl gap-5 px-4 py-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-ink">Verify a citation</h2>
          <p className="max-w-2xl text-sm text-ink-muted">
            Enter a scientific claim and the paper cited to support it — watch the five-stage pipeline
            stream retraction, scope, and a graded substantive-support verdict in real time.
          </p>
        </div>
        {active ? (
          running ? (
            <GhostButton type="button" size="sm" onClick={cancel}>■ Cancel</GhostButton>
          ) : (
            <GhostButton type="button" size="sm" onClick={reset}>← New verification</GhostButton>
          )
        ) : null}
      </header>

      {active ? (
        <>
          {state.request ? (
            <div ref={statusRef} tabIndex={-1} className="cv-card px-4 py-2.5 text-sm outline-none" aria-label={`Verifying: ${state.request.claim}`}>
              <span className="text-xs uppercase tracking-wide text-ink-muted">Verifying </span>
              <span className="text-ink">{truncate(state.request.claim, 140)}</span>
            </div>
          ) : null}
          <PipelinePanel state={state} />
          {showDebate ? <DebatePanel state={state} /> : null}
          {state.phase === 'complete' && state.result ? (
            <VerdictPanel result={state.result} headingRef={verdictHeadingRef} onOpenVerdict={openVerdict} onRunAnother={reset} />
          ) : null}
        </>
      ) : (
        <RunForm onRun={onRun} onReset={reset} busy={running} />
      )}
    </section>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}
