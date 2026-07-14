/**
 * BatchComposer (W2-FE-BATCH) — the batch input surface.
 *
 * Two ways in: one-click REPLAYS (the 4 proof cases, scaled ×2/×3, or the committed calibration
 * corpora) that submit immediately, and a hand editor (add / paste / edit rows of claim + cited
 * paper) for arbitrary batches. Prefilled with the four proof presets so "Run" works on first load.
 * Playback speed is offered for the mock demo (a live backend streams in real time and ignores it).
 */
import { useMemo, useState } from 'react';
import { FIXTURES } from '../../lib/fixtures';
import type { PlannedItem } from './model';
import { REPLAYS, SPEED_OPTIONS, DEFAULT_SPEED } from './presets';

interface EditRow {
  id: number;
  claim: string;
  paperRef: string;
}

let ROW_ID = 0;
function makeRow(claim = '', paperRef = ''): EditRow {
  ROW_ID += 1;
  return { id: ROW_ID, claim, paperRef };
}

/** Parse pasted lines: "claim <TAB|`|`> paper_ref", or a trailing PMID / DOI, else claim-only. */
function parsePaste(text: string): EditRow[] {
  const rows: EditRow[] = [];
  for (const raw of text.split('\n')) {
    const line = raw.trim();
    if (!line) continue;
    let claim = line;
    let ref = '';
    if (line.includes('\t')) {
      const [c, r] = line.split('\t');
      claim = c.trim();
      ref = (r ?? '').trim();
    } else if (line.includes(' | ')) {
      const [c, r] = line.split(' | ');
      claim = c.trim();
      ref = (r ?? '').trim();
    } else {
      const m = line.match(/\b(10\.\d{4,}\/\S+|\d{5,9})\s*$/);
      if (m) {
        ref = m[1];
        claim = line.slice(0, m.index).trim();
      }
    }
    if (claim) rows.push(makeRow(claim, ref));
  }
  return rows;
}

export interface BatchComposerProps {
  onRun: (items: PlannedItem[], opts: { speed: number }) => void;
  disabled: boolean;
  usingMock: boolean;
}

export function BatchComposer({ onRun, disabled, usingMock }: BatchComposerProps) {
  const [rows, setRows] = useState<EditRow[]>(() =>
    FIXTURES.map((f) => makeRow(f.preset.claim, f.preset.paper_ref)),
  );
  const [speed, setSpeed] = useState<number>(DEFAULT_SPEED);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState('');

  const validRows = useMemo(() => rows.filter((r) => r.claim.trim().length > 0), [rows]);

  const speedOpts = useMemo(() => ({ speed }), [speed]);

  const runEditor = () => {
    const items: PlannedItem[] = validRows.map((r) => ({
      claim: r.claim.trim(),
      paperRef: r.paperRef.trim() || null,
      corpus: null,
    }));
    if (items.length) onRun(items, speedOpts);
  };

  const runReplay = (build: () => PlannedItem[]) => onRun(build(), speedOpts);

  const update = (id: number, patch: Partial<EditRow>) =>
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  const remove = (id: number) => setRows((rs) => rs.filter((r) => r.id !== id));
  const addRow = () => setRows((rs) => [...rs, makeRow()]);
  const applyPaste = () => {
    const parsed = parsePaste(pasteText);
    if (parsed.length) {
      setRows((rs) => [...rs.filter((r) => r.claim.trim()), ...parsed]);
      setPasteText('');
      setPasteOpen(false);
    }
  };

  return (
    <section className="cv-card p-4 sm:p-5" aria-label="Compose a batch">
      {/* Quick replays */}
      <div>
        <h3 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">One-click replay</h3>
        <div className="mt-2 flex flex-wrap gap-2">
          {REPLAYS.map((r) => (
            <button
              key={r.key}
              type="button"
              disabled={disabled}
              onClick={() => runReplay(r.build)}
              className="cv-chip flex-col items-start gap-0.5 text-left"
              style={{
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: disabled ? 0.5 : 1,
                borderColor: r.corpus ? 'var(--cv-border)' : 'var(--cv-brand)',
                paddingTop: '0.4rem',
                paddingBottom: '0.4rem',
              }}
              title={r.detail}
            >
              <span className="font-bold text-ink">{r.label}</span>
              <span className="text-[0.7rem] font-normal text-ink-muted">{r.detail}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="my-4 h-px bg-line" />

      {/* Hand editor */}
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Build your own</h3>
        <div className="flex items-center gap-2">
          <button type="button" className="cv-chip" style={{ cursor: 'pointer' }} onClick={() => setPasteOpen((o) => !o)} aria-expanded={pasteOpen}>
            Paste rows
          </button>
          <button type="button" className="cv-chip" style={{ cursor: 'pointer' }} onClick={addRow}>
            + Add row
          </button>
        </div>
      </div>

      {pasteOpen ? (
        <div className="mt-2">
          <label className="text-xs text-ink-muted" htmlFor="cv-paste">
            One item per line — <code style={{ fontFamily: 'var(--font-mono, monospace)' }}>claim{'	'}PMID</code>, {' '}
            <code style={{ fontFamily: 'var(--font-mono, monospace)' }}>claim | PMID</code>, or a trailing PMID/DOI.
          </label>
          <textarea
            id="cv-paste"
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            rows={4}
            className="mt-1 w-full rounded-md border px-2 py-1 text-sm"
            style={{ background: 'var(--cv-surface)', borderColor: 'var(--cv-border)', color: 'var(--cv-text)' }}
            placeholder={'Resveratrol has clinical benefits… | 17086191'}
          />
          <div className="mt-1 flex justify-end">
            <button type="button" className="cv-chip" style={{ cursor: 'pointer' }} onClick={applyPaste}>
              Parse &amp; append
            </button>
          </div>
        </div>
      ) : null}

      <ul className="mt-3 space-y-2">
        {rows.map((r, i) => (
          <li key={r.id} className="flex flex-col gap-1 sm:flex-row sm:items-start">
            <span className="pt-2 text-xs tabular-nums text-ink-muted sm:w-6">{i + 1}</span>
            <textarea
              value={r.claim}
              onChange={(e) => update(r.id, { claim: e.target.value })}
              rows={2}
              placeholder="Atomic claim…"
              aria-label={`Claim for item ${i + 1}`}
              className="flex-1 rounded-md border px-2 py-1 text-sm"
              style={{ background: 'var(--cv-surface)', borderColor: 'var(--cv-border)', color: 'var(--cv-text)' }}
            />
            <input
              value={r.paperRef}
              onChange={(e) => update(r.id, { paperRef: e.target.value })}
              placeholder="PMID / DOI"
              aria-label={`Cited paper for item ${i + 1}`}
              className="rounded-md border px-2 py-1 text-sm tabular-nums sm:w-40"
              style={{ background: 'var(--cv-surface)', borderColor: 'var(--cv-border)', color: 'var(--cv-text)' }}
            />
            <button
              type="button"
              onClick={() => remove(r.id)}
              aria-label={`Remove item ${i + 1}`}
              className="cv-chip self-start"
              style={{ cursor: 'pointer' }}
            >
              ✕
            </button>
          </li>
        ))}
      </ul>

      {/* Run bar */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {usingMock ? (
            <label className="flex items-center gap-1.5 text-sm text-ink-muted">
              Speed
              <select
                value={String(speed)}
                onChange={(e) => setSpeed(Number(e.target.value))}
                className="rounded-md border px-2 py-1 text-sm"
                style={{ background: 'var(--cv-surface)', borderColor: 'var(--cv-border)', color: 'var(--cv-text)' }}
                aria-label="Demo playback speed"
              >
                {SPEED_OPTIONS.map((o) => (
                  <option key={o.label} value={String(o.value)}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <span className="text-sm text-ink-muted">Live backend — streams in real time.</span>
          )}
        </div>
        <button
          type="button"
          onClick={runEditor}
          disabled={disabled || validRows.length === 0}
          className="rounded-md px-4 py-2 text-sm font-bold"
          style={{
            cursor: disabled || validRows.length === 0 ? 'not-allowed' : 'pointer',
            background: 'var(--cv-brand)',
            color: 'var(--cv-brand-contrast)',
            opacity: disabled || validRows.length === 0 ? 0.5 : 1,
          }}
        >
          Run batch ({validRows.length})
        </button>
      </div>
    </section>
  );
}

export default BatchComposer;
