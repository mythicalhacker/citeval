/**
 * useRunEngine — owns the run lifecycle: fire a run, pump its SSE frames into `runReducer`, and
 * clean up on cancel / unmount / re-run.
 *
 * Dual-mode (LR-06), both key-free and offline-safe for the demo:
 *   • `replay` → drives the recorded fixture stream through the W0 mock directly, so it plays the
 *     full debate with NO backend and NO API key regardless of `VITE_USE_MOCK`. The fixture *is* the
 *     recorded event log; the mock *is* the replay engine.
 *   • `live` → goes through the one backend-agnostic `api.startRun` (mock by default, real FastAPI
 *     when `VITE_USE_MOCK=false`). The reducer can't tell the two apart — that's the contract.
 */
import { useCallback, useEffect, useReducer, useRef } from 'react';
import type { RunRequest, SSEFrame } from '../../lib/types';
import { api } from '../../lib/api';
import { runMock, DEFAULT_SPEED } from '../../lib/mockServer';
import { runReducer, initialRunState, type RunSource } from './model';

export interface UseRunEngine {
  state: ReturnType<typeof runReducer>;
  /** Start a run; cancels any in-flight run first. */
  start: (request: RunRequest, source: RunSource, speed?: number) => void;
  /** Cancel the in-flight run (leaves whatever was streamed so far on screen). */
  cancel: () => void;
  /** Clear everything back to the empty form state. */
  reset: () => void;
}

export function useRunEngine(): UseRunEngine {
  const [state, dispatch] = useReducer(runReducer, initialRunState);

  const cancelRef = useRef<(() => void) | null>(null);
  const mountedRef = useRef(true);
  // Monotonic token so a late frame or settle from a superseded/cancelled run is ignored.
  const tokenRef = useRef(0);

  const teardown = useCallback(() => {
    cancelRef.current?.();
    cancelRef.current = null;
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      teardown();
    };
  }, [teardown]);

  const start = useCallback<UseRunEngine['start']>((request, source, speed) => {
    teardown();
    const token = ++tokenRef.current;
    dispatch({ type: 'reset' });
    dispatch({ type: 'start', source, request });

    const onEvent = (frame: SSEFrame) => {
      if (!mountedRef.current || token !== tokenRef.current) return;
      dispatch({ type: 'frame', frame });
    };
    const onFailed = (err: unknown) => {
      if (!mountedRef.current || token !== tokenRef.current) return;
      dispatch({ type: 'stream_failed', message: err instanceof Error ? err.message : String(err) });
    };
    const s = speed ?? DEFAULT_SPEED;

    if (source === 'replay') {
      const handle = runMock(request, onEvent, { speed: s });
      cancelRef.current = handle.cancel;
      handle.done.catch(onFailed);
      return;
    }

    // Live path: POST then subscribe. The subscribe handle only exists after the POST resolves, so
    // if the run is cancelled/superseded in that window, cancel the stream the moment it appears.
    let cancelled = false;
    cancelRef.current = () => {
      cancelled = true;
    };
    api
      .startRun(request, onEvent, s != null ? { speed: s } : undefined)
      .then(({ stream }) => {
        if (cancelled || token !== tokenRef.current) {
          stream.cancel();
          return;
        }
        cancelRef.current = stream.cancel;
        stream.done.catch(onFailed);
      })
      .catch(onFailed);
  }, [teardown]);

  const cancel = useCallback(() => {
    tokenRef.current++; // supersede: ignore any further frames from the cancelled stream
    teardown();
    dispatch({ type: 'cancel' }); // leave 'running' so the view stops signalling active work
  }, [teardown]);

  const reset = useCallback(() => {
    tokenRef.current++;
    teardown();
    dispatch({ type: 'reset' });
  }, [teardown]);

  return { state, start, cancel, reset };
}
