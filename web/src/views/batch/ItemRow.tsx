/**
 * ItemRow (W2-FE-BATCH) — one paper's live row in the grid.
 *
 * Shows submission order, the claim + cited paper, a per-item progress state (queued → an
 * indeterminate running bar → done/failed), and — once the item's RunResult has been fetched — its
 * gate, substantive grade, confidence, cost and timing, with a drill-in to the Verdict view. A
 * failed item renders in isolation (red) and never blocks its neighbours. In a mock corpus replay,
 * a stand-in verdict is dimmed and badged so it is never mistaken for a real one; the committed gold
 * label is shown alongside as the honest reference.
 */
import type { CSSProperties } from 'react';
import { CostChip, GateBadge, GradeBadge, ConfidenceChip } from '../../components/common';
import type { ConfKey } from '../../design/tokens';
import { duration } from '../../lib/format';
import type { ItemState } from './model';
import { summarize } from './verdict';
import { isStandIn } from './presets';

const CLAMP_2: CSSProperties = {
  display: '-webkit-box',
  WebkitLineClamp: 2,
  WebkitBoxOrient: 'vertical',
  overflow: 'hidden',
};

const STATUS_STYLE: Record<ItemState['status'], { bg: string; fg: string; border: string; label: string }> = {
  queued: { bg: 'var(--cv-step-pending-bg)', fg: 'var(--cv-step-pending-fg)', border: 'var(--cv-step-pending-border)', label: 'Queued' },
  running: { bg: 'var(--cv-step-active-bg)', fg: 'var(--cv-step-active-fg)', border: 'var(--cv-step-active-border)', label: 'Running' },
  done: { bg: 'var(--cv-step-done-bg)', fg: 'var(--cv-step-done-fg)', border: 'var(--cv-step-done-border)', label: 'Done' },
  error: { bg: 'var(--cv-step-error-bg)', fg: 'var(--cv-step-error-fg)', border: 'var(--cv-step-error-border)', label: 'Failed' },
};

const GOLD_STYLE: Record<string, CSSProperties> = {
  RETRACTED: { background: 'var(--cv-gate-fired-bg)', color: 'var(--cv-gate-fired-fg)' },
  SCOPE_MISMATCH: { background: 'var(--cv-conf-low-bg)', color: 'var(--cv-conf-low-fg)' },
  SUPPORTED: { background: 'var(--cv-gate-clear-bg)', color: 'var(--cv-gate-clear-fg)' },
};

function StatusBadge({ status }: { status: ItemState['status'] }) {
  const s = STATUS_STYLE[status];
  return (
    <span className="cv-badge" style={{ background: s.bg, color: s.fg, borderColor: s.border }}>
      {status === 'running' ? <span aria-hidden className="cv-batch-indeterminate-dot" /> : null}
      {s.label}
    </span>
  );
}

/** The thin per-item progress track (the batch stream gives no per-item %, so `running` is an
 *  honest indeterminate animation, not a fake percentage). */
function ProgressTrack({ status }: { status: ItemState['status'] }) {
  if (status === 'queued') {
    return <div className="mt-1 h-1 w-full rounded-full" style={{ background: 'var(--cv-surface-2)' }} />;
  }
  if (status === 'running') {
    return (
      <div className="relative mt-1 h-1 w-full overflow-hidden rounded-full" style={{ background: 'var(--cv-surface-2)' }}>
        <span className="cv-batch-indeterminate" />
      </div>
    );
  }
  const color = status === 'error' ? 'var(--cv-gate-fired-fg)' : 'var(--cv-step-done-border)';
  return <div className="mt-1 h-1 w-full rounded-full" style={{ background: color }} />;
}

export interface ItemRowProps {
  item: ItemState;
  usingMock: boolean;
  onOpen: (item: ItemState) => void;
}

export function ItemRow({ item, usingMock, onOpen }: ItemRowProps) {
  const summary = item.result ? summarize(item.result) : null;
  // ANY mock verdict for a paper with no fixture is a stand-in — corpus OR hand-entered. Dim and
  // badge it so a fabricated verdict is never shown as if it were real (the honesty invariant).
  const standIn = isStandIn(item.paperRef, usingMock);
  const canOpen = item.result != null;
  const paperLabel = item.paperRef ?? '—';
  // Title provenance, honestly: a corpus row shows its committed `cited_title`; a stand-in with no
  // corpus has NO real title for this paper, so show none (never print the stand-in fixture's title
  // next to the user's ref); a real verdict shows its grounded title.
  const title = item.corpus ? item.corpus.cited_title : standIn ? '' : summary?.title ?? '';

  return (
    <tr
      className="border-t border-line align-top"
      style={{ background: item.status === 'error' ? 'var(--cv-step-error-bg)' : undefined }}
    >
      {/* # */}
      <td className="px-2 py-3 text-xs tabular-nums text-ink-muted">{item.index + 1}</td>

      {/* Item: claim + paper + status */}
      <td className="px-2 py-3">
        <div className="flex items-center gap-2">
          <StatusBadge status={item.status} />
          {item.corpus ? (
            <span
              className="cv-badge"
              style={{ ...(GOLD_STYLE[item.corpus.gold_label] ?? { background: 'var(--cv-surface-2)', color: 'var(--cv-text-muted)' }) }}
              title={`Committed gold label${item.corpus.mismatch_axis ? ` · ${item.corpus.mismatch_axis} axis` : ''} (case ${item.corpus.case_id})`}
            >
              gold: {item.corpus.gold_label}
            </span>
          ) : null}
        </div>
        <p className="mt-1 max-w-xl text-sm text-ink" style={CLAMP_2} title={item.claim}>
          {item.claim}
        </p>
        <p className="mt-0.5 text-xs text-ink-muted">
          <span className="uppercase">{summary?.citedType ?? (item.paperRef && /^10\./.test(item.paperRef) ? 'doi' : 'pmid')}</span>{' '}
          <span className="tabular-nums">{paperLabel}</span>
          {title ? <span> · {title}</span> : null}
        </p>
        <ProgressTrack status={item.status} />
      </td>

      {/* Verdict */}
      <td className="px-2 py-3">
        {summary ? (
          <div className="flex flex-col items-start gap-1" style={{ opacity: standIn ? 0.55 : 1 }}>
            <div className="flex flex-wrap items-center gap-1">
              {summary.gateFired ? <GateBadge fired title={summary.overall} /> : null}
              <GradeBadge verdict={summary.substantive} />
            </div>
            <ConfidenceChip
              tier={(summary.tier as ConfKey) ?? 'low'}
              agreement={summary.agreement ?? undefined}
              nSamples={summary.nSamples ?? undefined}
              abstained={summary.abstained}
            />
            {standIn ? (
              <span className="text-[0.7rem] italic text-ink-muted" title="No fixture for this paper — an illustrative mock verdict, not a real one.">
                stand-in (mock)
              </span>
            ) : null}
          </div>
        ) : item.status === 'error' ? (
          <span className="text-sm font-semibold" style={{ color: 'var(--cv-gate-fired-fg)' }}>
            {item.error ?? 'Failed'}
          </span>
        ) : (
          <span className="text-sm text-ink-muted">{item.status === 'running' ? 'adjudicating…' : 'queued'}</span>
        )}
      </td>

      {/* Cost */}
      <td className="px-2 py-3 text-right">
        {summary ? <CostChip usd={summary.costUsd} size="sm" /> : <span className="text-sm text-ink-muted">—</span>}
      </td>

      {/* Time */}
      <td className="px-2 py-3 text-right text-sm tabular-nums text-ink-muted">
        {summary ? duration(summary.totalMs) : item.status === 'running' ? 'running…' : '—'}
      </td>

      {/* Drill-in */}
      <td className="px-2 py-3 text-right">
        <button
          type="button"
          className="cv-chip"
          style={{ cursor: canOpen ? 'pointer' : 'not-allowed', opacity: canOpen ? 1 : 0.5 }}
          disabled={!canOpen}
          onClick={() => canOpen && onOpen(item)}
          aria-label={canOpen ? `Open the verdict for item ${item.index + 1}` : `Verdict for item ${item.index + 1} not ready`}
        >
          Open →
        </button>
      </td>
    </tr>
  );
}

export default ItemRow;
