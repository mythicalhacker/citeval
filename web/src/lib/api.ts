/**
 * api.ts (W1-FE-SHELL) — the ONE client every view talks to.
 *
 * It presents a single, backend-agnostic surface over the frozen W0 API contract
 * (`docs/api_contract.md`). When `VITE_USE_MOCK` is anything other than the string `'false'`
 * (the default — unset counts as mock), every call is served by the in-process time-driven
 * `mockServer.ts`, so the whole app builds, runs, and demos with **no backend and no API key**.
 * Flip `VITE_USE_MOCK=false` and the identical methods hit the FastAPI server over
 * `fetch` (REST) and `EventSource` (SSE) at `VITE_API_BASE` (default `/api`). Return shapes are
 * identical on both paths, so views never branch on the transport.
 */
import type {
  RunRequest, RunCreated, RunResult,
  BatchRequest, BatchCreated, BatchResult,
  PricingInfo, Health, SSEHandler, SSEFrame, SSEEventName,
} from './types';
import { RUN_EVENT_NAMES, BATCH_EVENT_NAMES } from './types';
import * as mock from './mockServer';
import type { StreamHandle } from './mockServer';

export type { StreamHandle } from './mockServer';
export type RunStream = StreamHandle<RunResult>;
export type BatchStream = StreamHandle<BatchResult>;

/** Options for a subscription. `speed` compresses the mock demo wall-clock and is ignored by the
 *  real backend (which streams in real time). */
export interface SubscribeOptions {
  speed?: number;
}

/* ---- environment ------------------------------------------------------------------------- */
export const USING_MOCK: boolean = import.meta.env.VITE_USE_MOCK !== 'false';
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api';
const MOCK_SPEED: number | undefined = parseSpeed(import.meta.env.VITE_MOCK_SPEED);

function parseSpeed(raw: string | undefined): number | undefined {
  if (raw == null) return undefined;
  if (raw === 'Infinity') return Infinity;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : undefined;
}
function mockOpts(opts?: SubscribeOptions): mock.MockOptions {
  const speed = opts?.speed ?? MOCK_SPEED;
  return speed == null ? {} : { speed };
}

/* ============================================================================================
 * Public surface
 * ========================================================================================== */
export interface CitevalApi {
  readonly usingMock: boolean;
  readonly apiBase: string;

  // REST
  createRun(req: RunRequest): Promise<RunCreated>;
  getRun(id: string): Promise<RunResult>;
  createBatch(req: BatchRequest): Promise<BatchCreated>;
  getBatch(id: string): Promise<BatchResult>;
  getPricing(): Promise<PricingInfo>;
  getHealth(): Promise<Health>;
  getShowcase(): Promise<RunResult[]>;

  // SSE (synchronous — returns a handle whose `done` resolves at the terminal frame)
  subscribeRun(id: string, onEvent: SSEHandler, opts?: SubscribeOptions): RunStream;
  subscribeBatch(id: string, onEvent: SSEHandler, opts?: SubscribeOptions): BatchStream;

  // Convenience: POST + subscribe in one call (the two-call run pattern, wrapped).
  startRun(req: RunRequest, onEvent: SSEHandler, opts?: SubscribeOptions): Promise<{ runId: string; stream: RunStream }>;
  startBatch(req: BatchRequest, onEvent: SSEHandler, opts?: SubscribeOptions): Promise<{ batchId: string; stream: BatchStream }>;
}

/* ============================================================================================
 * REST — fetch helper for the live path
 * ========================================================================================== */
async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { accept: 'application/json' } });
  if (!res.ok) throw new ApiError(res.status, `GET ${path} → ${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}
async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', accept: 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, `POST ${path} → ${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

/* ============================================================================================
 * SSE — EventSource helper for the live path
 * ========================================================================================== */
/** Pull a string `message` field out of an unknown SSE `error` payload, if present. */
function messageOf(data: unknown): string | undefined {
  if (data && typeof data === 'object' && 'message' in data) {
    const m = (data as Record<string, unknown>).message;
    if (typeof m === 'string') return m;
  }
  return undefined;
}

function subscribeSSE<T>(
  path: string,
  eventNames: readonly SSEEventName[],
  terminalEvent: SSEEventName,
  extractResult: (frame: SSEFrame) => T,
  onEvent: SSEHandler,
): StreamHandle<T> {
  const es = new EventSource(`${API_BASE}${path}`);
  let settled = false;
  let resolve!: (r: T) => void;
  let reject!: (e: Error) => void;
  const done = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  for (const name of eventNames) {
    es.addEventListener(name, (ev) => {
      // Guard the `error` name collision: EventSource fires a type-"error" event for *transport*
      // failures too; those are plain Events with no `.data`, handled by `onerror` below.
      const msg = ev as MessageEvent;
      if (typeof msg.data !== 'string') return;
      let data: unknown;
      try {
        data = JSON.parse(msg.data);
      } catch {
        return;
      }
      onEvent({ event: name, data } as SSEFrame);
      // An application `error` frame is terminal — the runner closes the stream right after it
      // (api_contract.md §3). Settle `done` NOW with the real message so the imminent transport
      // close (handled by onerror) is treated as an expected end, not a fresh generic failure.
      if (name === 'error') {
        settled = true;
        reject(new Error(messageOf(data) ?? `stream error on ${path}`));
        es.close();
        return;
      }
      if (name === terminalEvent) {
        settled = true;
        resolve(extractResult({ event: name, data } as SSEFrame));
        es.close();
      }
    });
  }

  es.onerror = () => {
    // A transport error *after* the stream settled (server closed the stream) is expected — ignore.
    if (settled) {
      es.close();
      return;
    }
    // Otherwise it's a real connection failure; report once and stop reconnecting.
    settled = true;
    const err = new Error(`SSE connection error on ${path}`);
    onEvent({ event: 'error', data: { run_id: '', seq: 0, ts: 0, elapsed_ms: 0, message: err.message } } as SSEFrame);
    reject(err);
    es.close();
  };

  done.catch(() => {});
  return { cancel: () => es.close(), done };
}

/* ============================================================================================
 * The client
 * ========================================================================================== */
export const api: CitevalApi = {
  usingMock: USING_MOCK,
  apiBase: API_BASE,

  // ---- REST -------------------------------------------------------------------------------
  createRun(req) {
    if (USING_MOCK) return Promise.resolve(mock.createRun(req));
    return postJson<RunCreated>('/runs', req);
  },
  getRun(id) {
    if (USING_MOCK) {
      const r = mock.getRun(id);
      return r ? Promise.resolve(r) : Promise.reject(new ApiError(404, `unknown run_id ${id}`));
    }
    return getJson<RunResult>(`/runs/${encodeURIComponent(id)}`);
  },
  createBatch(req) {
    if (USING_MOCK) return Promise.resolve(mock.createBatch(req));
    return postJson<BatchCreated>('/batch', req);
  },
  getBatch(id) {
    if (USING_MOCK) {
      const b = mock.getBatch(id);
      return b ? Promise.resolve(b) : Promise.reject(new ApiError(404, `unknown batch_id ${id}`));
    }
    return getJson<BatchResult>(`/batch/${encodeURIComponent(id)}`);
  },
  getPricing() {
    if (USING_MOCK) return Promise.resolve(mock.getPricing());
    return getJson<PricingInfo>('/pricing');
  },
  getHealth() {
    if (USING_MOCK) return Promise.resolve(mock.getHealth());
    return getJson<Health>('/health');
  },
  getShowcase() {
    if (USING_MOCK) return Promise.resolve(mock.getShowcase());
    return getJson<RunResult[]>('/showcase');
  },

  // ---- SSE --------------------------------------------------------------------------------
  subscribeRun(id, onEvent, opts) {
    if (USING_MOCK) return mock.subscribeRun(id, onEvent, mockOpts(opts));
    return subscribeSSE<RunResult>(
      `/runs/${encodeURIComponent(id)}/events`,
      RUN_EVENT_NAMES,
      'run_complete',
      (f) => (f as Extract<SSEFrame, { event: 'run_complete' }>).data.result,
      onEvent,
    );
  },
  subscribeBatch(id, onEvent, opts) {
    if (USING_MOCK) return mock.subscribeBatch(id, onEvent, mockOpts(opts));
    return subscribeSSE<BatchResult>(
      `/batch/${encodeURIComponent(id)}/events`,
      BATCH_EVENT_NAMES,
      'batch_complete',
      (f) => (f as Extract<SSEFrame, { event: 'batch_complete' }>).data.result,
      onEvent,
    );
  },

  // ---- convenience (create + subscribe) ---------------------------------------------------
  async startRun(req, onEvent, opts) {
    const { run_id } = await this.createRun(req);
    return { runId: run_id, stream: this.subscribeRun(run_id, onEvent, opts) };
  },
  async startBatch(req, onEvent, opts) {
    const { batch_id } = await this.createBatch(req);
    return { batchId: batch_id, stream: this.subscribeBatch(batch_id, onEvent, opts) };
  },
};

export default api;
