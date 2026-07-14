/**
 * model.ts (W2-FE-BATCH) — the batch dashboard's state machine.
 *
 * A pure reducer over the four batch-stream events (batch_start, item_update, batch_progress,
 * batch_complete — see docs/api_contract.md §4) plus the per-item RunResult that the view fetches
 * lazily on completion. Kept side-effect-free so the whole live dashboard is deterministic and
 * unit-checkable; the `useBatchRun` hook owns the api wiring that feeds it.
 *
 * Concurrency is read HONESTLY from the stream: `peakInFlight` is the largest number of items
 * observed in the `running` state at once — the real worker count, not a hard-coded guess.
 */
import type { RunResult, BatchResult, BatchAggregate, ItemStatus } from '../../lib/types';
import type { CorpusCase } from './corpus';

/** One planned batch item before it hits the wire (what the composer emits). */
export interface PlannedItem {
  claim: string;
  paperRef: string | null;
  /** Committed corpus provenance, when this item came from a corpus replay. */
  corpus: CorpusCase | null;
}

/** Live per-item state, indexed by submission order. */
export interface ItemState {
  index: number;
  claim: string;
  paperRef: string | null;
  corpus: CorpusCase | null;
  /** The run id assigned by the server once the item starts (from item_update). */
  runId: string | null;
  status: ItemStatus;
  /** The terminal RunResult — fetched via api.getRun when the item reports `done`. */
  result: RunResult | null;
  /** Populated only if the item reports `error` (per-item failure isolation). */
  error: string | null;
  /** Simulated stream elapsed (ms) when the item started / finished — for per-item duration. */
  startElapsedMs: number | null;
  endElapsedMs: number | null;
}

export type BatchPhase = 'idle' | 'starting' | 'streaming' | 'complete' | 'failed' | 'cancelled';

export interface BatchState {
  phase: BatchPhase;
  batchId: string | null;
  items: ItemState[];
  /** Total item count (from the request, confirmed by batch_start). */
  total: number;
  /** `done` as last reported by batch_progress (authoritative live figure). */
  progressDone: number;
  /** Live cumulative cost (batch_progress → batch_complete aggregate). */
  costUsd: number;
  /** Live elapsed (ms) of the batch clock. */
  elapsedMs: number;
  /** Largest number of items seen `running` simultaneously — the honest parallelism ceiling. */
  peakInFlight: number;
  aggregate: BatchAggregate | null;
  /** A batch-level (not per-item) failure — e.g. the stream never opened. */
  error: string | null;
  /** Whether this batch ran against the mock (drives the stand-in honesty banner). */
  usingMock: boolean;
  /** Bumped by the hook per run so late async results from a superseded batch are ignored. */
  generation: number;
}

export const initialState: BatchState = {
  phase: 'idle',
  batchId: null,
  items: [],
  total: 0,
  progressDone: 0,
  costUsd: 0,
  elapsedMs: 0,
  peakInFlight: 0,
  aggregate: null,
  error: null,
  usingMock: true,
  generation: 0,
};

export type Action =
  | { type: 'RESET' }
  | { type: 'START'; items: PlannedItem[]; usingMock: boolean; generation: number }
  | { type: 'BATCH_ID'; batchId: string }
  | { type: 'BATCH_START'; n: number }
  | { type: 'ITEM_UPDATE'; index: number; runId: string; status: ItemStatus; elapsedMs: number }
  | { type: 'ITEM_RESULT'; index: number; result: RunResult }
  | { type: 'BATCH_PROGRESS'; done: number; total: number; costUsd: number; elapsedMs: number }
  | { type: 'BATCH_COMPLETE'; result: BatchResult; wallElapsedMs: number }
  | { type: 'STREAM_ERROR'; message: string }
  | { type: 'CANCEL' };

function plannedToItem(p: PlannedItem, index: number): ItemState {
  return {
    index,
    claim: p.claim,
    paperRef: p.paperRef,
    corpus: p.corpus,
    runId: null,
    status: 'queued',
    result: null,
    error: null,
    startElapsedMs: null,
    endElapsedMs: null,
  };
}

/** Count items currently in the `running` state — the live in-flight worker occupancy. */
export function inFlightCount(items: ItemState[]): number {
  let n = 0;
  for (const it of items) if (it.status === 'running') n += 1;
  return n;
}

export function reducer(state: BatchState, action: Action): BatchState {
  switch (action.type) {
    case 'RESET':
      return { ...initialState, generation: state.generation };

    case 'START': {
      const items = action.items.map(plannedToItem);
      return {
        ...initialState,
        phase: 'starting',
        items,
        total: items.length,
        usingMock: action.usingMock,
        generation: action.generation,
      };
    }

    case 'BATCH_ID':
      return { ...state, batchId: action.batchId };

    case 'BATCH_START':
      // Confirm the total; keep whichever is larger so a partial START never under-counts.
      return { ...state, phase: 'streaming', total: Math.max(state.total, action.n) };

    case 'ITEM_UPDATE': {
      const items = state.items.map((it) => {
        if (it.index !== action.index) return it;
        const next: ItemState = { ...it, runId: action.runId, status: action.status };
        if (action.status === 'running' && next.startElapsedMs == null) {
          next.startElapsedMs = action.elapsedMs;
        }
        if (action.status === 'done' || action.status === 'error') {
          next.endElapsedMs = action.elapsedMs;
          if (action.status === 'error' && next.error == null) {
            next.error = 'The pipeline reported a failure for this item.';
          }
        }
        return next;
      });
      return { ...state, items, peakInFlight: Math.max(state.peakInFlight, inFlightCount(items)) };
    }

    case 'ITEM_RESULT': {
      const items = state.items.map((it) =>
        it.index === action.index ? { ...it, result: action.result } : it,
      );
      return { ...state, items };
    }

    case 'BATCH_PROGRESS':
      return {
        ...state,
        progressDone: action.done,
        total: Math.max(state.total, action.total),
        costUsd: action.costUsd,
        elapsedMs: action.elapsedMs,
      };

    case 'BATCH_COMPLETE': {
      const { result } = action;
      const items = state.items.map((it) => {
        // Match this row's RunResult by run_id first — BatchResult.items has no ordering or
        // completeness guarantee (api_contract §6), so positional indexing can mis-associate; the
        // positional index is only a fallback for a row that never received a run_id.
        const r =
          (it.runId ? result.items.find((x) => x.run_id === it.runId) : undefined) ??
          result.items[it.index] ??
          null;
        // A failed item stays failed and keeps NO verdict — never backfill a RunResult onto an
        // errored row (that would mask the isolated failure the dashboard exists to surface).
        if (it.status === 'error') {
          return { ...it, runId: it.runId ?? r?.run_id ?? null };
        }
        return {
          ...it,
          status: 'done' as ItemStatus,
          runId: it.runId ?? r?.run_id ?? null,
          result: it.result ?? r,
        };
      });
      return {
        ...state,
        phase: 'complete',
        items,
        aggregate: result.aggregate,
        progressDone: items.filter((it) => it.status === 'done').length,
        costUsd: result.aggregate.total_cost_usd,
        // `elapsedMs` is the batch WALL clock (parallel). `aggregate.total_ms` is the SERIAL sum of
        // per-item durations — a different, larger number kept on `aggregate`, never conflated here.
        elapsedMs: Math.max(state.elapsedMs, action.wallElapsedMs),
      };
    }

    case 'STREAM_ERROR':
      return { ...state, phase: 'failed', error: action.message };

    case 'CANCEL': {
      // Only a still-running batch can be cancelled; a completed/failed one is left untouched.
      if (state.phase !== 'streaming' && state.phase !== 'starting') return state;
      // Move every item that had not finished to a terminal state so its counts are honest and its
      // "running" animation stops. Items that already produced a verdict keep it.
      const items = state.items.map((it) =>
        it.status === 'queued' || it.status === 'running'
          ? { ...it, status: 'error' as const, error: 'Cancelled before it completed.' }
          : it,
      );
      return { ...state, phase: 'cancelled', items };
    }

    default:
      return state;
  }
}

/* ============================================================================================
 * Derived counts — one pass over items, shared by the header, the concurrency meter, and filters.
 * ========================================================================================== */
export interface DerivedCounts {
  queued: number;
  running: number;
  done: number;
  error: number;
  /** done + error — items that have reached a terminal state. */
  terminal: number;
  total: number;
  /** 0–100 completion by terminal count. */
  pct: number;
}

export function deriveCounts(state: BatchState): DerivedCounts {
  let queued = 0;
  let running = 0;
  let done = 0;
  let error = 0;
  for (const it of state.items) {
    switch (it.status) {
      case 'queued': queued += 1; break;
      case 'running': running += 1; break;
      case 'done': done += 1; break;
      case 'error': error += 1; break;
      default: break;
    }
  }
  const total = state.total || state.items.length;
  const terminal = done + error;
  const pct = total > 0 ? (100 * terminal) / total : 0;
  return { queued, running, done, error, terminal, total, pct };
}
