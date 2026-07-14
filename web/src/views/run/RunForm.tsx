/**
 * RunForm — the front door (07_uiux.md IV): a strip of one-click recorded cases (replay a real
 * adjudication with no key, IV-02 / LR-06), plus a custom claim + cited-paper form with a mode
 * selector, a Live⇄Replay toggle, a demo-speed control, inline validation (IV-04), and the reused
 * FULL / OBJECTIVE-ONLY mode banner (ES-02).
 */
import { useState } from 'react';
import type { ReactNode } from 'react';
import type { RunMode, RunRequest } from '../../lib/types';
import { FIXTURES } from '../../lib/fixtures';
import { USING_MOCK } from '../../lib/api';
import type { RunSource } from './model';
import { MODE_BANNER_FULL, MODE_BANNER_OBJECTIVE, InfoDot, PrimaryButton, GhostButton, inputClass } from './bits';

const EXAMPLE_CLAIM =
  'Resveratrol has shown promising clinical benefits as an anti-aging and anti-diabetic agent.';

const MODES: { value: RunMode; label: string; hint: string }[] = [
  { value: 'pmid', label: 'PMID', hint: 'A PubMed ID, e.g. 17086191' },
  { value: 'doi', label: 'DOI', hint: 'A DOI, e.g. 10.1016/S0140-6736(11)61590-0' },
  { value: 'citation', label: 'Citation', hint: 'Paste a free-text reference to parse' },
  { value: 'manuscript', label: 'Manuscript', hint: 'Bring your own full text — no NCBI lookup' },
  { value: 'auto', label: 'Auto', hint: 'Detect PMID vs DOI from what you paste' },
];

const SPEEDS: { value: number; label: string; hint: string }[] = [
  { value: 12, label: 'Watch', hint: 'Play the ~90 s pipeline in ~7 s' },
  { value: 48, label: 'Fast', hint: 'Compress to ~2 s' },
  { value: Infinity, label: 'Instant', hint: 'Skip straight to the verdict' },
];

export interface RunFormProps {
  onRun: (request: RunRequest, source: RunSource, speed: number) => void;
  onReset: () => void;
  busy: boolean;
}

/** Build the RunRequest for the current mode, routing the reference text to the right field. */
function buildRequest(claim: string, mode: RunMode, ref: string): RunRequest {
  const c = claim.trim();
  const r = ref.trim();
  switch (mode) {
    case 'citation':
      return { claim: c, citation_string: r, mode };
    case 'manuscript':
      return { claim: c, manuscript_text: r, mode };
    default:
      return { claim: c, paper_ref: r, mode };
  }
}

/** Soft format check for the reference field — a warning, never a hard block (IV-04). */
function refWarning(mode: RunMode, ref: string): string | null {
  const r = ref.trim();
  if (!r) return null;
  if (mode === 'pmid' && !/^\d+$/.test(r)) return 'A PMID is all digits — this doesn’t look like one.';
  if (mode === 'doi' && !/^10\.\d{4,}\//.test(r)) return 'A DOI starts with “10.” followed by a registrant — double-check this.';
  return null;
}

export function RunForm({ onRun, onReset, busy }: RunFormProps) {
  const [claim, setClaim] = useState('');
  const [mode, setMode] = useState<RunMode>('pmid');
  const [ref, setRef] = useState('');
  const [source, setSource] = useState<RunSource>('live');
  const [speed, setSpeed] = useState<number>(12);
  const [showErrors, setShowErrors] = useState(false);

  const refIsLong = mode === 'citation' || mode === 'manuscript';
  const refLabel =
    mode === 'citation' ? 'Reference string' : mode === 'manuscript' ? 'Manuscript full text' : 'Cited paper (PMID / DOI)';
  const modeHint = MODES.find((m) => m.value === mode)?.hint ?? '';

  const claimError = showErrors && !claim.trim() ? 'Enter the claim you want to verify.' : null;
  const refError = showErrors && !ref.trim() ? `Enter the ${refIsLong ? 'text' : 'identifier'} above.` : null;
  const warn = refWarning(mode, ref);

  const loadPreset = (fx: (typeof FIXTURES)[number], startSource?: RunSource) => {
    setClaim(fx.preset.claim);
    setMode(fx.preset.mode);
    setRef(fx.preset.paper_ref);
    setShowErrors(false);
    if (startSource) onRun(buildRequest(fx.preset.claim, fx.preset.mode, fx.preset.paper_ref), startSource, speed);
  };

  const submit = () => {
    if (!claim.trim() || !ref.trim()) {
      setShowErrors(true);
      return;
    }
    onRun(buildRequest(claim, mode, ref), source, speed);
  };

  const clear = () => {
    setClaim('');
    setRef('');
    setShowErrors(false);
    onReset();
  };

  return (
    <div className="grid gap-5">
      {/* ---- Recorded cases: zero-risk, zero-wait, no key (IV-02 / LR-06) -------------------- */}
      <RecordedCases busy={busy} onPlay={(fx) => loadPreset(fx, 'replay')} onEdit={(fx) => loadPreset(fx)} />

      {/* ---- Custom form -------------------------------------------------------------------- */}
      <div className="cv-card p-4 sm:p-5">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-sm font-bold uppercase tracking-wide text-ink">Verify your own citation</h3>
          <SourceToggle value={source} onChange={setSource} disabled={busy} />
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          className="grid gap-4"
          noValidate
        >
          <Field label="Claim" htmlFor="cv-claim" error={claimError}>
            <textarea
              id="cv-claim"
              value={claim}
              onChange={(e) => setClaim(e.target.value)}
              placeholder={EXAMPLE_CLAIM}
              rows={3}
              disabled={busy}
              aria-invalid={claimError ? true : undefined}
              className={`${inputClass} resize-y`}
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-[10rem_1fr] sm:items-start">
            <Field label="Reference type" htmlFor="cv-mode">
              <select
                id="cv-mode"
                value={mode}
                onChange={(e) => setMode(e.target.value as RunMode)}
                disabled={busy}
                className={inputClass}
              >
                {MODES.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </Field>

            <Field label={refLabel} htmlFor="cv-ref" hint={modeHint} error={refError} warning={warn}>
              {refIsLong ? (
                <textarea
                  id="cv-ref"
                  value={ref}
                  onChange={(e) => setRef(e.target.value)}
                  rows={mode === 'manuscript' ? 4 : 2}
                  disabled={busy}
                  placeholder={mode === 'manuscript' ? 'Paste the citing manuscript’s full text…' : 'Smith J, et al. Nature. 2006;444:337-42.'}
                  aria-invalid={refError ? true : undefined}
                  className={`${inputClass} resize-y font-mono`}
                />
              ) : (
                <input
                  id="cv-ref"
                  value={ref}
                  onChange={(e) => setRef(e.target.value)}
                  disabled={busy}
                  placeholder={mode === 'doi' ? '10.1016/…' : '17086191'}
                  aria-invalid={refError ? true : undefined}
                  className={`${inputClass} font-mono`}
                />
              )}
            </Field>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <label htmlFor="cv-speed" className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                Demo speed
              </label>
              <select
                id="cv-speed"
                value={String(speed)}
                onChange={(e) => setSpeed(Number(e.target.value))}
                disabled={busy}
                className={`${inputClass} w-auto`}
                title={SPEEDS.find((s) => s.value === speed)?.hint}
              >
                {SPEEDS.map((s) => (
                  <option key={s.label} value={String(s.value)}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <GhostButton type="button" onClick={clear} disabled={busy}>
                Reset
              </GhostButton>
              <PrimaryButton type="submit" disabled={busy}>
                {source === 'replay' ? '▶ Replay run' : 'Verify citation'}
              </PrimaryButton>
            </div>
          </div>
        </form>

        <ModeBanner source={source} />
      </div>
    </div>
  );
}

/* ---- Recorded-cases strip -------------------------------------------------------------------- */
function RecordedCases({
  busy, onPlay, onEdit,
}: {
  busy: boolean;
  onPlay: (fx: (typeof FIXTURES)[number]) => void;
  onEdit: (fx: (typeof FIXTURES)[number]) => void;
}) {
  return (
    <section aria-labelledby="cv-recorded" className="grid gap-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id="cv-recorded" className="text-sm font-bold uppercase tracking-wide text-ink">
          Recorded cases
        </h3>
        <span className="text-xs text-ink-muted">
          One click — no API key, no network. Plays a real recorded Opus 4.8 run, frame by frame.
        </span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {FIXTURES.map((fx) => (
          <article key={fx.key} className="cv-card flex flex-col gap-2 p-3">
            <div className="flex items-start justify-between gap-2">
              <h4 className="text-sm font-semibold text-ink">{fx.title}</h4>
              <span
                className="cv-badge shrink-0"
                style={{ background: 'var(--cv-surface-2)', color: 'var(--cv-text-muted)', borderColor: 'var(--cv-border)' }}
                title="The axis this case is designed to exercise"
              >
                {fx.axisFocus.replace(/_/g, ' ')}
              </span>
            </div>
            <p className="text-xs leading-relaxed text-ink-muted">{fx.caption}</p>
            <div className="mt-auto flex items-center gap-2 pt-1">
              <PrimaryButton type="button" size="sm" onClick={() => onPlay(fx)} disabled={busy} aria-label={`Play recorded case: ${fx.title}`}>
                ▶ Play
              </PrimaryButton>
              <GhostButton type="button" size="sm" onClick={() => onEdit(fx)} disabled={busy} aria-label={`Load into form: ${fx.title}`}>
                ✎ Load into form
              </GhostButton>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

/* ---- Source toggle (Live ⇄ Replay) -----------------------------------------------------------
 * Two aria-pressed toggle buttons in a labelled group — each is independently tabbable/clickable, so
 * the announced role matches the actual interaction (no radiogroup arrow-key pattern is implied). */
function SourceToggle({ value, onChange, disabled }: { value: RunSource; onChange: (v: RunSource) => void; disabled: boolean }) {
  return (
    <div role="group" aria-label="Run source" className="inline-flex overflow-hidden rounded-lg border border-line">
      {(['live', 'replay'] as const).map((opt) => {
        const active = value === opt;
        return (
          <button
            key={opt}
            type="button"
            aria-pressed={active}
            disabled={disabled}
            onClick={() => onChange(opt)}
            className="px-3 py-1 text-xs font-semibold capitalize"
            style={{
              background: active ? 'var(--cv-brand)' : 'transparent',
              color: active ? 'var(--cv-brand-contrast)' : 'var(--cv-text-muted)',
            }}
            title={opt === 'live' ? 'Stream a run (mock-backed by default)' : 'Deterministically replay a recorded run — always offline'}
          >
            {opt}
          </button>
        );
      })}
    </div>
  );
}

/* ---- Field wrapper --------------------------------------------------------------------------- */
function Field({
  label, htmlFor, hint, error, warning, children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  error?: string | null;
  warning?: string | null;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-1">
      <label htmlFor={htmlFor} className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
        {label}
      </label>
      {children}
      {hint && !error ? <p className="text-xs text-ink-muted">{hint}</p> : null}
      {warning && !error ? (
        <p className="text-xs" style={{ color: 'var(--cv-conf-medium-fg)' }}>
          ⚠ {warning}
        </p>
      ) : null}
      {error ? (
        <p className="text-xs" role="alert" style={{ color: 'var(--cv-gate-fired-fg)' }}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

/* ---- Mode banner (reuses demo.py copy) ------------------------------------------------------- */
function ModeBanner({ source }: { source: RunSource }) {
  // In this build there is no live key by default; runs are served by the recorded mock. Say so
  // plainly and point at the recorded cases (ES-02), and keep the exact CLI copy one click away.
  const offline = USING_MOCK || source === 'replay';
  return (
    <div className="mt-4 grid gap-2">
      <div
        className="rounded-lg border px-3 py-2 text-xs leading-relaxed"
        style={{ background: 'var(--cv-offscale-nei-bg)', color: 'var(--cv-offscale-nei-fg)', borderColor: 'var(--cv-offscale-nei-border)' }}
      >
        {offline ? (
          <>
            <strong>No API key needed.</strong> This build is served by the in-process mock — every run replays a real,
            previously-recorded Opus 4.8 adjudication frame-by-frame (the graded axis is genuine recorded output, never faked).
            <InfoDot label="Set VITE_USE_MOCK=false to point Live runs at a real FastAPI backend instead." />
          </>
        ) : (
          <>{MODE_BANNER_FULL}</>
        )}
      </div>
      <details className="text-xs text-ink-muted">
        <summary className="cursor-pointer select-none font-semibold">What FULL vs OBJECTIVE-ONLY means</summary>
        <p className="mt-1.5">{MODE_BANNER_FULL}</p>
        <p className="mt-1.5">{MODE_BANNER_OBJECTIVE}</p>
      </details>
    </div>
  );
}

export default RunForm;
