/**
 * ItemGrid (W2-FE-BATCH) — the sortable / filterable table of batch items.
 *
 * Column headers sort (click to sort, click again to flip; `aria-sort` announces it); a status
 * segmented control, a "gated only" toggle, and a free-text search filter the rows. Sorting is
 * stable and tolerant of rows that have no verdict yet (they sort to the end), so the grid stays
 * usable while the batch is still streaming.
 */
import { useMemo, useState } from 'react';
import type { ItemState } from './model';
import { summarize, severityRank, type VerdictSummary } from './verdict';
import { ItemRow } from './ItemRow';

type SortKey = 'index' | 'status' | 'severity' | 'cost' | 'time' | 'confidence';
type SortDir = 'asc' | 'desc';
type StatusFilter = 'all' | ItemState['status'];

const STATUS_RANK: Record<ItemState['status'], number> = { running: 0, queued: 1, done: 2, error: 3 };

interface Col {
  key: SortKey;
  label: string;
  align: 'left' | 'right';
  /** Default direction when a column is first selected. */
  defaultDir: SortDir;
}
const COLS: Col[] = [
  { key: 'index', label: '#', align: 'left', defaultDir: 'asc' },
  { key: 'status', label: 'Item', align: 'left', defaultDir: 'asc' },
  { key: 'severity', label: 'Verdict', align: 'left', defaultDir: 'desc' },
  { key: 'cost', label: 'Cost', align: 'right', defaultDir: 'desc' },
  { key: 'time', label: 'Time', align: 'right', defaultDir: 'desc' },
  { key: 'confidence', label: 'Conf.', align: 'right', defaultDir: 'desc' },
];

const STATUS_TABS: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'queued', label: 'Queued' },
  { key: 'running', label: 'Running' },
  { key: 'done', label: 'Done' },
  { key: 'error', label: 'Failed' },
];

/** Sort metric for one item; `null` summaries sort last (large sentinel in whichever direction). */
function metric(item: ItemState, key: SortKey, s: VerdictSummary | null): number {
  switch (key) {
    case 'index': return item.index;
    case 'status': return STATUS_RANK[item.status];
    case 'severity': return s ? severityRank(s) : -1;
    case 'cost': return s ? s.costUsd : -1;
    case 'time': return s ? s.totalMs : -1;
    case 'confidence': return s?.agreement ?? -1;
    default: return item.index;
  }
}

function matchesQuery(item: ItemState, q: string): boolean {
  if (!q) return true;
  const hay = [
    item.claim,
    item.paperRef ?? '',
    item.corpus?.cited_title ?? '',
    item.corpus?.case_id ?? '',
    item.corpus?.category ?? '',
    item.corpus?.gold_label ?? '',
  ]
    .join(' ')
    .toLowerCase();
  return hay.includes(q.toLowerCase());
}

export interface ItemGridProps {
  items: ItemState[];
  usingMock: boolean;
  onOpen: (item: ItemState) => void;
}

export function ItemGrid({ items, usingMock, onOpen }: ItemGridProps) {
  const [sortKey, setSortKey] = useState<SortKey>('index');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [status, setStatus] = useState<StatusFilter>('all');
  const [gatedOnly, setGatedOnly] = useState(false);
  const [query, setQuery] = useState('');

  // Precompute each item's summary once for both filtering and sorting.
  const withSummary = useMemo(
    () => items.map((item) => ({ item, summary: item.result ? summarize(item.result) : null })),
    [items],
  );

  const visible = useMemo(() => {
    const filtered = withSummary.filter(({ item, summary }) => {
      if (status !== 'all' && item.status !== status) return false;
      if (gatedOnly && !summary?.gateFired) return false;
      if (!matchesQuery(item, query)) return false;
      return true;
    });
    const dir = sortDir === 'asc' ? 1 : -1;
    return filtered
      .map((row, i) => ({ ...row, i })) // capture original index for a stable sort
      .sort((a, b) => {
        const d = metric(a.item, sortKey, a.summary) - metric(b.item, sortKey, b.summary);
        return d !== 0 ? d * dir : a.i - b.i;
      })
      .map((row) => row.item);
  }, [withSummary, status, gatedOnly, query, sortKey, sortDir]);

  const onSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(COLS.find((c) => c.key === key)?.defaultDir ?? 'asc');
    }
  };

  return (
    <section className="cv-card mt-4 p-3 sm:p-4" aria-label="Batch items">
      {/* Filter bar */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-1">
          {STATUS_TABS.map((t) => {
            const selected = status === t.key;
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => setStatus(t.key)}
                aria-pressed={selected}
                className="cv-chip"
                style={{
                  cursor: 'pointer',
                  background: selected ? 'var(--cv-step-active-bg)' : 'var(--cv-surface-2)',
                  color: selected ? 'var(--cv-step-active-fg)' : 'var(--cv-text)',
                  borderColor: selected ? 'var(--cv-step-active-border)' : 'var(--cv-border)',
                }}
              >
                {t.label}
              </button>
            );
          })}
        </div>

        <button
          type="button"
          onClick={() => setGatedOnly((g) => !g)}
          aria-pressed={gatedOnly}
          className="cv-chip"
          style={{
            cursor: 'pointer',
            background: gatedOnly ? 'var(--cv-gate-fired-bg)' : 'var(--cv-surface-2)',
            color: gatedOnly ? 'var(--cv-gate-fired-fg)' : 'var(--cv-text)',
            borderColor: gatedOnly ? 'var(--cv-gate-fired-border)' : 'var(--cv-border)',
          }}
        >
          Gated only
        </button>

        <label className="ml-auto flex items-center gap-1.5 text-sm">
          <span className="sr-only">Search claims and papers</span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search claim / paper / gold…"
            className="rounded-md border px-2 py-1 text-sm"
            style={{ background: 'var(--cv-surface)', borderColor: 'var(--cv-border)', color: 'var(--cv-text)', minWidth: '12rem' }}
          />
        </label>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[44rem] border-collapse text-left">
          <caption className="sr-only">
            Batch items — sortable by column, {visible.length} of {items.length} shown.
          </caption>
          <thead>
            <tr className="text-xs uppercase tracking-wide text-ink-muted">
              {COLS.map((col) => {
                const active = sortKey === col.key;
                const ariaSort = active ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none';
                return (
                  <th
                    key={col.key}
                    scope="col"
                    aria-sort={ariaSort}
                    className={`px-2 py-2 font-semibold ${col.align === 'right' ? 'text-right' : 'text-left'}`}
                  >
                    <button
                      type="button"
                      onClick={() => onSort(col.key)}
                      className="inline-flex items-center gap-1"
                      style={{ cursor: 'pointer', color: active ? 'var(--cv-brand)' : 'inherit' }}
                    >
                      {col.label}
                      <span aria-hidden style={{ opacity: active ? 1 : 0.3 }}>
                        {active ? (sortDir === 'asc' ? '▲' : '▼') : '↕'}
                      </span>
                    </button>
                  </th>
                );
              })}
              <th scope="col" className="px-2 py-2 text-right font-semibold">
                <span className="sr-only">Open verdict</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {visible.map((item) => (
              <ItemRow key={item.index} item={item} usingMock={usingMock} onOpen={onOpen} />
            ))}
            {visible.length === 0 ? (
              <tr>
                <td colSpan={COLS.length + 1} className="px-2 py-8 text-center text-sm text-ink-muted">
                  No items match the current filter.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default ItemGrid;
