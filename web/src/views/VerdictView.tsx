/**
 * VerdictView (W2-FE-VERDICT) — the payoff screen: a complete, provenance-stamped verdict for one
 * citation. It reads the handed-off RunResult from `useShell().selection` (set by a run, a showcase
 * pick, or a batch item); when opened cold it seeds itself from a cached case via `api.getRun` (a
 * `?run=<id>` permalink, or the signature retraction case), and a CasePicker keeps every fixture —
 * retraction gate, species scope mismatch, graded over-reach, honest abstention — one click away.
 *
 * Reading order follows reviews/improvements/07_uiux.md §3.3 (VV): hero + gate → per-axis table →
 * graded ramp + confidence + decisive span → grounding evidence → the verbatim report artifact.
 * Owns only this file + views/verdict/*; the shell seam and W0 lib are consumed read-only.
 */
import { useEffect, useRef, useState } from 'react';
import type { RunResult } from '../lib/types';
import { useShell } from '../shell/ShellContext';
import { api } from '../lib/api';
import { FIXTURES } from '../lib/fixtures';
import VerdictHero from './verdict/VerdictHero';
import AxisTable from './verdict/AxisTable';
import GradedBlock from './verdict/GradedBlock';
import GroundingEvidence from './verdict/GroundingEvidence';
import ExportBar from './verdict/ExportBar';
import ReportFrame from './verdict/ReportFrame';
import CasePicker from './verdict/CasePicker';
import { substantiveAxis, citedPmidLabel } from './verdict/model';

/** The case to seed with when opened cold: any `?run=` permalink id (resolved against the catalog,
 *  then api.getRun, then the error state — so a genuine live-run link round-trips instead of being
 *  silently swapped for a fixture), else the retraction gate — the signature case the UIUX spec says
 *  to protect above all others (VV-01). */
function seedRunId(): string {
  if (typeof window !== 'undefined') {
    const param = new URLSearchParams(window.location.search).get('run');
    if (param) return param;
  }
  return FIXTURES[0]?.run_id ?? '';
}

export default function VerdictView() {
  const { selection } = useShell();
  const [shown, setShown] = useState<RunResult | null>(selection);
  const [requestedId, setRequestedId] = useState<string | null>(selection?.run_id ?? null);
  // The cached showcase catalog — the cases the CasePicker resolves against. `null` until loaded.
  const [catalog, setCatalog] = useState<RunResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Monotonic request token so an out-of-order getRun response can't clobber a newer selection.
  const reqSeq = useRef(0);

  // Load the cached catalog once: these are the fixture RunResults the mock serves with no key.
  // (The mock's getRun only knows in-session runs, so the catalog — not getRun — is what resolves
  // a cached case by id; getRun stays as the live-backend fallback for a genuine run permalink.)
  useEffect(() => {
    let alive = true;
    api.getShowcase()
      .then((rs) => { if (alive) setCatalog(rs); })
      .catch(() => { if (alive) setCatalog([]); });
    return () => { alive = false; };
  }, []);

  function loadById(id: string) {
    if (!id) return;
    setRequestedId(id);
    setError(null);
    const hit = catalog?.find((r) => r.run_id === id);
    if (hit) {
      reqSeq.current++; // cancel any in-flight fetch
      setShown(hit);
      setLoading(false);
      return;
    }
    // Not a cached case — try a genuine in-session run (real backend / this session's runs).
    const seq = ++reqSeq.current;
    setLoading(true);
    api.getRun(id)
      .then((r) => { if (seq === reqSeq.current) setShown(r); })
      .catch((e: unknown) => {
        if (seq === reqSeq.current) setError(e instanceof Error ? e.message : `Could not load run ${id}`);
      })
      .finally(() => { if (seq === reqSeq.current) setLoading(false); });
  }

  // A hand-off always wins: adopt the shell selection whenever it changes to a real result.
  useEffect(() => {
    if (selection) {
      reqSeq.current++; // cancel any in-flight getRun
      setShown(selection);
      setRequestedId(selection.run_id);
      setLoading(false);
      setError(null);
    }
  }, [selection]);

  // Cold open (no hand-off): once the catalog is in, seed from a permalink / the signature case.
  useEffect(() => {
    if (!selection && !shown && catalog) {
      const id = seedRunId();
      const hit = catalog.find((r) => r.run_id === id);
      setRequestedId(id);
      if (hit) setShown(hit);
      else if (id) loadById(id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalog, selection]);

  const activeRunId = shown?.run_id ?? requestedId;

  return (
    <div className="px-4 py-6 sm:px-6">
      <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-ink">Verdict</h1>
          <p className="mt-1 max-w-2xl text-sm text-ink-muted">
            The objective gates, the six-level substantive grade held separately, the adversarial
            trace, and the structured grounding evidence — for one citation.
          </p>
        </div>
        <CasePicker
          fixtures={FIXTURES}
          activeRunId={activeRunId}
          onPick={loadById}
          disabled={loading || catalog === null}
        />
      </div>

      {error && !shown ? (
        <div className="cv-card p-6" role="alert">
          <p className="text-sm font-semibold text-ink">Couldn’t load this verdict.</p>
          <p className="mt-1 text-sm text-ink-muted">{error}</p>
          <button
            type="button"
            className="cv-chip mt-3 cursor-pointer hover:border-brand"
            onClick={() => loadById(seedRunId())}
          >
            Retry
          </button>
        </div>
      ) : !shown ? (
        <div className="cv-card grid place-items-center p-16 text-sm text-ink-muted" aria-busy="true">
          {loading || catalog === null ? 'Loading verdict…' : 'Pick a worked example above to see a full verdict.'}
        </div>
      ) : (
        <VerdictReport result={shown} loading={loading} />
      )}
    </div>
  );
}

/** The assembled verdict for one RunResult. */
function VerdictReport({ result, loading }: { result: RunResult; loading: boolean }) {
  const graded = substantiveAxis(result.verdict.verdict);
  return (
    <article
      className="grid gap-5"
      aria-label={`Verdict for ${citedPmidLabel(result.verdict.grounded)}`}
      style={{ opacity: loading ? 0.55 : 1, transition: 'opacity 120ms' }}
    >
      <ExportBar result={result} />
      <VerdictHero result={result.verdict} />
      <AxisTable verdict={result.verdict.verdict} />
      {graded ? <GradedBlock finding={graded} /> : null}
      <GroundingEvidence result={result.verdict} />
      <ReportFrame html={result.report_html} title={`Citation verification report — ${citedPmidLabel(result.verdict.grounded)}`} />
    </article>
  );
}
