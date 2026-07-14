/**
 * ExportBar (VV-06) — the download / share strip. Every format the pipeline already produces, offered
 * verbatim where possible:
 *   • HTML → the exact `report_html` from reporting.render_html (self-contained, dark-mode aware);
 *   • JSON → the exact `render_json` verdict object (the frozen wire shape);
 *   • Markdown → a faithful client-side reconstruction (reporting.render_markdown has no JS twin).
 * Plus a copy-permalink (the run_id is the cached-case key) and a compact cost / latency readout —
 * the adversarial triad on Opus is deliberately expensive, so we surface the bill honestly.
 */
import { useState } from 'react';
import type { ReactNode } from 'react';
import type { RunResult } from '../../lib/types';
import { CostChip } from '../../components/common';
import { duration } from '../../lib/format';
import { toMarkdown } from './model';

function download(filename: string, mime: string, text: string): void {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Revoke on the next tick so the click has flushed.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function Btn({ onClick, children, title }: { onClick: () => void; children: ReactNode; title?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className="cv-chip cursor-pointer transition-colors hover:border-brand"
    >
      {children}
    </button>
  );
}

export interface ExportBarProps {
  result: RunResult;
}

export function ExportBar({ result }: ExportBarProps) {
  const [copied, setCopied] = useState(false);
  const id = result.run_id;

  const copyPermalink = async () => {
    // No Clipboard API (insecure context / unsupported) — don't show a false "Copied" confirmation.
    if (!navigator.clipboard?.writeText) return;
    const url = `${window.location.origin}${window.location.pathname}?run=${encodeURIComponent(id)}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // Write rejected (permission) — leave the button unconfirmed; never throw out of an export.
    }
  };

  return (
    <section
      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-surface-2 px-4 py-3"
      aria-label="Export and share"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Export</span>
        <Btn onClick={() => download(`citeval-${id}.html`, 'text/html', result.report_html)} title="The verbatim report_html document">
          HTML
        </Btn>
        <Btn onClick={() => download(`citeval-${id}.md`, 'text/markdown', toMarkdown(result.verdict))} title="Markdown reconstruction of the verdict">
          Markdown
        </Btn>
        <Btn onClick={() => download(`citeval-${id}.json`, 'application/json', JSON.stringify(result.verdict, null, 2))} title="The frozen render_json verdict object">
          JSON
        </Btn>
        <Btn onClick={copyPermalink} title="Copy a shareable link to this cached case">
          {copied ? '✓ Copied' : 'Copy link'}
        </Btn>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <CostChip usd={result.cost.total_usd} nCalls={result.cost.n_model_calls} tokens={result.cost.tokens} label="Total" size="sm" />
        <span className="cv-chip tabular-nums text-xs" title="Total wall-clock for this run">
          <span className="text-ink-muted">latency</span>
          <span className="font-semibold text-ink">{duration(result.timing.total_ms)}</span>
        </span>
      </div>
    </section>
  );
}

export default ExportBar;
