/**
 * useBatchRun (W2-FE-BATCH) — the seam between the api client and the batch reducer.
 *
 * `start(items, opts)` POSTs the batch and subscribes to its stream in one call (api.startBatch),
 * translating each frame into a reducer action. When an item reports `done` it lazily fetches that
 * item's RunResult (api.getRun) so the row can show its verdict and drill into the Verdict view the
 * moment it finishes — without waiting for the whole batch to complete. Every async continuation is
 * fenced by a monotonic `generation` so a superseded or unmounted run can never write stale state.
 */
import { useCallback, useEffect, useReducer, useRef } from 'react';
import { api } from '../../lib/api';
import type { BatchStream } from '../../lib/api';
import type { BatchRequest, SSEFrame } from '../../lib/types';
import { reducer, initialState, type PlannedItem } from './model';

export interface StartOptions {
  speed?: number;
}

export function useBatchRun() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const streamRef = useRef<BatchStream | null>(null);
  const genRef = useRef(0);

  // Stop the live stream + fence stale async, WITHOUT touching reducer state (used by unmount).
  const teardown = useCallback(() => {
    streamRef.current?.cancel();
    streamRef.current = null;
    // Bump the generation so any in-flight getRun promises resolve into a no-op.
    genRef.current += 1;
  }, []);

  // User-initiated cancel: tear down AND move the reducer to a terminal `cancelled` state so the
  // UI stops showing "Running" and re-enables the composer.
  const cancel = useCallback(() => {
    teardown();
    dispatch({ type: 'CANCEL' });
  }, [teardown]);

  const start = useCallback((planned: PlannedItem[], opts?: StartOptions) => {
    // Tear down any prior run and claim a fresh generation.
    streamRef.current?.cancel();
    streamRef.current = null;
    const generation = (genRef.current += 1);

    dispatch({ type: 'START', items: planned, usingMock: api.usingMock, generation });

    const req: BatchRequest = {
      items: planned.map((p) => ({ claim: p.claim, paper_ref: p.paperRef })),
    };

    const onFrame = (frame: SSEFrame) => {
      if (genRef.current !== generation) return;
      switch (frame.event) {
        case 'batch_start':
          dispatch({ type: 'BATCH_START', n: frame.data.n });
          break;
        case 'item_update': {
          const d = frame.data;
          dispatch({
            type: 'ITEM_UPDATE',
            index: d.index,
            runId: d.run_id,
            status: d.status,
            elapsedMs: d.elapsed_ms,
          });
          // On completion, fetch the item's RunResult so the row can show its verdict + drill in.
          if (d.status === 'done') {
            api
              .getRun(d.run_id)
              .then((result) => {
                if (genRef.current !== generation) return;
                dispatch({ type: 'ITEM_RESULT', index: d.index, result });
              })
              .catch(() => {
                /* leave the row without a result — the drill-in stays disabled, honestly. */
              });
          }
          break;
        }
        case 'batch_progress': {
          const d = frame.data;
          dispatch({
            type: 'BATCH_PROGRESS',
            done: d.done,
            total: d.total,
            costUsd: d.cost_usd,
            elapsedMs: d.elapsed_ms,
          });
          break;
        }
        case 'batch_complete':
          dispatch({ type: 'BATCH_COMPLETE', result: frame.data.result, wallElapsedMs: frame.data.elapsed_ms });
          break;
        default:
          // Run-stream events never appear on a batch stream (api_contract §4).
          break;
      }
    };

    api
      .startBatch(req, onFrame, opts)
      .then(({ batchId, stream }) => {
        if (genRef.current !== generation) {
          stream.cancel();
          return;
        }
        streamRef.current = stream;
        dispatch({ type: 'BATCH_ID', batchId });
        stream.done.catch(() => {
          /* a settled/errored stream is surfaced through frames; swallow the rejection. */
        });
      })
      .catch((err: unknown) => {
        if (genRef.current !== generation) return;
        const message = err instanceof Error ? err.message : String(err);
        dispatch({ type: 'STREAM_ERROR', message });
      });
  }, []);

  // Cancel the live stream on unmount so timers don't fire into a dead component. Use `teardown`
  // (not `cancel`) so we don't dispatch into an unmounting reducer.
  useEffect(() => () => teardown(), [teardown]);

  return { state, start, cancel };
}
