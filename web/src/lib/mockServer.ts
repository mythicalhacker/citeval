/**
 * mockServer.ts (W0-CONTRACTS) — a self-contained, time-driven mock of the citeval API.
 *
 * It lets the ENTIRE web app build and demo with **no backend and no API key**: given a
 * `RunRequest` it emits a realistic SSE sequence (run_start → per-stage start/end → interleaved
 * model_call + debate_round across the triad's self-consistency rounds → cost_update ticks →
 * progress → run_complete) and resolves to a `RunResult`. It also mocks POST /api/batch as N
 * bounded-concurrent mock runs. Every terminal `RunResult` is a real fixture (see fixtures.ts),
 * so the verdict/showcase views render identically to the live server.
 *
 * Two clocks, decoupled on purpose: a **simulated** pipeline clock (the envelope `elapsed_ms`,
 * ETAs and cost figures reflect a real ~90 s Opus run) and a compressed **wall** clock (the
 * demo plays in a few seconds). `speed` is the compression factor; `speed: Infinity` fires the
 * whole sequence synchronously (used by tests).
 *
 * Depends only on `./types` and `./fixtures` — nothing else in the app. `api.ts` (W1-FE-SHELL)
 * wraps these functions when `VITE_USE_MOCK` is true (the default).
 */
import type {
  RunRequest, RunCreated, RunResult, RunTiming,
  BatchRequest, BatchCreated, BatchResult, BatchAggregate,
  SSEHandler, SSEFrame, SSEEnvelope, Stage, DebateRole,
  TokenUsage, PricingInfo, Health, ItemStatus, AxisFinding, SubstantiveEvidence,
} from './types';
import { STAGE_ORDER } from './types';
import { FIXTURES, FIXTURE_BY_RUN_ID, SHOWCASE_RUNS, type Fixture } from './fixtures';

/* ============================================================================================
 * Pricing (mirror of server/citeval_api/pricing.PRICING — illustrative placeholders).
 * ========================================================================================== */
export const PRICING: PricingInfo = {
  input: 15.0,
  output: 75.0,
  cache_write: 18.75,
  cache_read: 1.5,
  unit: 'usd_per_million_tokens',
  note: 'Illustrative Opus-class placeholders — CONFIRM against current Anthropic pricing.',
};

const BASE_TS = 1752451200; // 2026-07-14T00:00:00Z, seconds — deterministic envelope timestamps.

export interface MockOptions {
  /** Wall-clock compression factor. 12 ⇒ a 90 s pipeline plays in ~7.5 s. Infinity ⇒ synchronous. */
  speed?: number;
}
export const DEFAULT_SPEED = 12;
/** Bounded concurrency for the batch mock — mirror the real orchestrator's worker count so the
 *  dashboard's "true-parallel vs queued" indicator is honest. */
export const MOCK_BATCH_CONCURRENCY = 4;

/* ============================================================================================
 * In-memory registries (mirror the server's run/batch stores).
 * ========================================================================================== */
const runs = new Map<string, RunResult>();
const batches = new Map<string, BatchResult>();
let runCounter = 0;
let batchCounter = 0;

/* ============================================================================================
 * REST-verb mocks
 * ========================================================================================== */
export function getPricing(): PricingInfo {
  return PRICING;
}
export function getHealth(): Health {
  return { status: 'ok' };
}
/** GET /api/showcase — cached RunResults, no key needed. */
export function getShowcase(): RunResult[] {
  return SHOWCASE_RUNS;
}
/** GET /api/runs/{id} — the terminal RunResult (available immediately in the mock). */
export function getRun(runId: string): RunResult | undefined {
  return runs.get(runId);
}
/** GET /api/batch/{id}. */
export function getBatch(batchId: string): BatchResult | undefined {
  return batches.get(batchId);
}

/** POST /api/runs — pick the fixture the request maps to, clone it under a fresh run_id, and
 *  register it. Returns `{ run_id }`. */
export function createRun(req: RunRequest): RunCreated {
  const runId = `mock_run_${++runCounter}`;
  const fixture = matchFixture(req);
  runs.set(runId, personalize(fixture.result, runId, req));
  return { run_id: runId };
}

/** POST /api/batch — register N runs (one per item) and a placeholder BatchResult. */
export function createBatch(req: BatchRequest): BatchCreated {
  const batchId = `mock_batch_${++batchCounter}`;
  const items: RunResult[] = req.items.map((item) => {
    const { run_id } = createRun({ claim: item.claim, paper_ref: item.paper_ref ?? null, mode: 'auto' });
    return runs.get(run_id)!;
  });
  batches.set(batchId, { batch_id: batchId, items, aggregate: aggregateOf(items) });
  return { batch_id: batchId };
}

/* ============================================================================================
 * SSE-stream mocks
 * ========================================================================================== */
export interface StreamHandle<T> {
  cancel: () => void;
  done: Promise<T>;
}

/** GET /api/runs/{id}/events — schedule the full SSE sequence for a run created by `createRun`. */
export function subscribeRun(runId: string, onEvent: SSEHandler, opts: MockOptions = {}): StreamHandle<RunResult> {
  const result = runs.get(runId);
  if (!result) {
    return failedHandle(runId, onEvent, `unknown run_id ${runId}`, opts);
  }
  const speed = opts.speed ?? DEFAULT_SPEED;
  const frames = buildRunFrames(runId, result);
  return schedule(frames, onEvent, speed, result);
}

/** GET /api/batch/{id}/events — N concurrent (bounded) mock runs with live aggregates. */
export function subscribeBatch(batchId: string, onEvent: SSEHandler, opts: MockOptions = {}): StreamHandle<BatchResult> {
  const batch = batches.get(batchId);
  if (!batch) {
    const p = Promise.reject(new Error(`unknown batch_id ${batchId}`));
    p.catch(() => {});
    return { cancel: () => {}, done: p };
  }
  const speed = opts.speed ?? DEFAULT_SPEED;
  const timers: ReturnType<typeof setTimeout>[] = [];
  const n = batch.items.length;
  let seq = 0;
  const startWall = nowMs();
  const emit = (event: SSEFrame['event'], data: Record<string, unknown>, simMs: number) => {
    const env = envelope(batchId, seq++, simMs);
    onEvent({ event, data: { ...env, ...data } } as SSEFrame);
  };

  emit('batch_start', { n }, 0);

  // Simulate bounded-concurrency scheduling: each item occupies a worker slot; item i starts when
  // a slot frees. We approximate with a per-item simulated start offset by lane.
  const perItemSimMs = 40000; // ~40 s simulated per item
  let done = 0;
  let costAcc = 0;
  const startFrames: Array<{ at: number; fn: () => void }> = [];
  batch.items.forEach((item, index) => {
    const lane = index % MOCK_BATCH_CONCURRENCY;
    const wave = Math.floor(index / MOCK_BATCH_CONCURRENCY);
    const startSim = wave * perItemSimMs + lane * 400;
    const endSim = startSim + perItemSimMs;
    startFrames.push({ at: startSim, fn: () => emit('item_update', { index, run_id: item.run_id, status: 'running' satisfies ItemStatus }, startSim) });
    startFrames.push({
      at: endSim,
      fn: () => {
        done += 1;
        costAcc += item.cost.total_usd;
        emit('item_update', { index, run_id: item.run_id, status: 'done' satisfies ItemStatus }, endSim);
        emit('batch_progress', { done, total: n, cost_usd: round(costAcc, 4), elapsed_ms: endSim }, endSim);
      },
    });
  });
  const lastSim = Math.max(...startFrames.map((f) => f.at), 0) + 200;
  startFrames.push({ at: lastSim, fn: () => emit('batch_complete', { result: batch }, lastSim) });
  startFrames.sort((a, b) => a.at - b.at);

  let resolve!: (r: BatchResult) => void;
  const donePromise = new Promise<BatchResult>((res) => { resolve = res; });
  if (speed === Infinity) {
    for (const f of startFrames) f.fn();
    resolve(batch);
    return { cancel: () => {}, done: donePromise };
  }
  for (const f of startFrames) {
    timers.push(setTimeout(() => {
      f.fn();
      if (f.at === lastSim) resolve(batch);
    }, f.at / speed));
  }
  void startWall;
  return { cancel: () => timers.forEach(clearTimeout), done: donePromise };
}

/** Convenience: POST + subscribe in one call (used by mock-only callers and tests). */
export function runMock(req: RunRequest, onEvent: SSEHandler, opts: MockOptions = {}): StreamHandle<RunResult> & { runId: string } {
  const { run_id } = createRun(req);
  const handle = subscribeRun(run_id, onEvent, opts);
  return { runId: run_id, ...handle };
}
export function batchMock(req: BatchRequest, onEvent: SSEHandler, opts: MockOptions = {}): StreamHandle<BatchResult> & { batchId: string } {
  const { batch_id } = createBatch(req);
  const handle = subscribeBatch(batch_id, onEvent, opts);
  return { batchId: batch_id, ...handle };
}

/* ============================================================================================
 * Frame construction — the heart of the mock.
 * ========================================================================================== */
interface PlannedFrame {
  simMs: number;
  event: SSEFrame['event'];
  data: Record<string, unknown>;
}

function buildRunFrames(runId: string, result: RunResult): PlannedFrame[] {
  const frames: PlannedFrame[] = [];
  const per = result.timing.per_stage_ms;
  const totalSim = result.timing.total_ms;
  const estTotal = result.timing.est_total_ms || totalSim;
  const sub = substantiveEvidence(result);
  const roundGrades = expandRoundGrades(result);
  const nRounds = roundGrades.length;
  const totalCalls = nRounds * 3;
  const costPerCall = totalCalls > 0 ? result.cost.total_usd / totalCalls : 0;
  const tokensPerCall = perCallTokens(result, totalCalls);

  let sim = 0;
  frames.push({ simMs: 0, event: 'run_start', data: { mode: paperMode(result), paper_ref: paperRef(result) } });

  let costAcc = 0;
  let modalCount = 0;
  const modalGrade = modeOf(roundGrades);

  for (const stage of STAGE_ORDER) {
    const dur = per[stage] ?? 500;
    frames.push({ simMs: sim, event: 'stage_start', data: { stage } });

    if (stage === 'adjudicate' && nRounds > 0) {
      const roundDur = dur / nRounds;
      for (let r = 0; r < nRounds; r++) {
        const roundStart = sim + r * roundDur;
        const roles: DebateRole[] = ['supporter', 'refuter', 'critic'];
        roles.forEach((role, ri) => {
          const at = roundStart + (ri / 3) * roundDur * 0.8;
          frames.push({ simMs: at, event: 'model_call', data: { role, round: r + 1, phase: 'start' } });
          const endAt = at + (roundDur * 0.8) / 3;
          costAcc += costPerCall;
          frames.push({
            simMs: endAt,
            event: 'model_call',
            data: { role, round: r + 1, phase: 'end', usage: tokensPerCall, cost_usd: round(costPerCall, 6) },
          });
        });
        const grade = roundGrades[r];
        if (grade === modalGrade) modalCount += 1;
        const agreement = round(modalCount / (r + 1), 4);
        frames.push({
          simMs: roundStart + roundDur * 0.85,
          event: 'debate_round',
          data: {
            round: r + 1,
            supporter_stance: sub?.supporter?.point || 'The cited text supports the claim.',
            refuter_stance: sub?.refuter?.objection || 'The claim over-reaches the cited finding.',
            critic_grade: grade,
            agreement,
          },
        });
        frames.push({
          simMs: roundStart + roundDur * 0.9,
          event: 'cost_update',
          data: {
            cumulative_usd: round(costAcc, 6),
            delta_usd: round(costPerCall * 3, 6),
            tokens: cumulativeTokens(tokensPerCall, (r + 1) * 3),
          },
        });
        const pct = 100 * (sim + (r + 1) * roundDur) / totalSim;
        frames.push({
          simMs: roundStart + roundDur * 0.95,
          event: 'progress',
          data: {
            pct: round(clamp(pct, 0, 99), 1),
            est_total_ms: estTotal,
            est_remaining_ms: round(Math.max(estTotal - (sim + (r + 1) * roundDur), 0), 0),
          },
        });
      }
    }

    sim += dur;
    frames.push({ simMs: sim, event: 'stage_end', data: { stage, summary: stageSummary(stage, result) } });
    // A coarse progress tick at every stage boundary (covers the non-adjudicate stages too).
    frames.push({
      simMs: sim,
      event: 'progress',
      data: {
        pct: round(clamp((100 * sim) / totalSim, 0, 99), 1),
        est_total_ms: estTotal,
        est_remaining_ms: round(Math.max(estTotal - sim, 0), 0),
      },
    });
  }

  frames.push({ simMs: sim + 5, event: 'run_complete', data: { result } });
  frames.sort((a, b) => a.simMs - b.simMs);
  return frames.map((f) => ({ ...f, data: f.data }));
}

function schedule(frames: PlannedFrame[], onEvent: SSEHandler, speed: number, result: RunResult): StreamHandle<RunResult> {
  const runId = result.run_id;
  const timers: ReturnType<typeof setTimeout>[] = [];
  let seq = 0;
  let resolve!: (r: RunResult) => void;
  const done = new Promise<RunResult>((res) => { resolve = res; });

  const fire = (f: PlannedFrame) => {
    const env = envelope(runId, seq++, f.simMs);
    onEvent({ event: f.event, data: { ...env, ...f.data } } as SSEFrame);
    if (f.event === 'run_complete') resolve(result);
  };

  if (speed === Infinity) {
    for (const f of frames) fire(f);
    return { cancel: () => {}, done };
  }
  for (const f of frames) {
    timers.push(setTimeout(() => fire(f), f.simMs / speed));
  }
  return { cancel: () => timers.forEach(clearTimeout), done };
}

function failedHandle(runId: string, onEvent: SSEHandler, message: string, opts: MockOptions): StreamHandle<RunResult> {
  const speed = opts.speed ?? DEFAULT_SPEED;
  const fire = () => onEvent({ event: 'error', data: { ...envelope(runId, 0, 0), stage: 'ingest', message } } as SSEFrame);
  const p = Promise.reject(new Error(message));
  p.catch(() => {});
  if (speed === Infinity) { fire(); return { cancel: () => {}, done: p }; }
  const t = setTimeout(fire, 0);
  return { cancel: () => clearTimeout(t), done: p };
}

/* ============================================================================================
 * Helpers
 * ========================================================================================== */
function envelope(runId: string, seq: number, simMs: number): SSEEnvelope {
  return { run_id: runId, seq, ts: round(BASE_TS + simMs / 1000, 3), elapsed_ms: round(simMs, 0) };
}

/** Map a request to the fixture it should demo. PMID/DOI match wins; otherwise round-robin a
 *  default so an arbitrary claim still animates a full run. */
function matchFixture(req: RunRequest): Fixture {
  const ref = (req.paper_ref || '').trim();
  const byRef = FIXTURES.find((f) => f.preset.paper_ref === ref);
  if (byRef) return byRef;
  // default: the graded-overreach case (a clean, ungated substantive grade).
  return FIXTURES.find((f) => f.key === 'graded_overreach') ?? FIXTURES[0];
}

/** Clone a fixture result under a new run_id and (when the caller typed their own claim/ref)
 *  swap the claim + identifier so the verdict view reflects their input. */
function personalize(base: RunResult, runId: string, req: RunRequest): RunResult {
  const clone: RunResult = JSON.parse(JSON.stringify(base));
  clone.run_id = runId;
  const typedClaim = (req.claim || '').trim();
  const matchedFixture = FIXTURES.some((f) => f.preset.paper_ref === (req.paper_ref || '').trim());
  if (typedClaim && !matchedFixture) {
    clone.verdict.claim_unit.atomic_claim = typedClaim;
    clone.verdict.verdict.claim = typedClaim;
  }
  const ref = (req.paper_ref || '').trim();
  if (ref && !matchedFixture) {
    const type = /^10\.\d/.test(ref) ? 'doi' : 'pmid';
    clone.verdict.claim_unit.cited_identifier = { type, value: ref };
    clone.verdict.verdict.cited_identifier = { type, value: ref };
    clone.verdict.grounded.identifier = { type, value: ref };
  }
  return clone;
}

function substantiveEvidence(result: RunResult): Partial<SubstantiveEvidence> | undefined {
  const f = result.verdict.verdict.axis_findings.find((a: AxisFinding) => a.axis === 'substantive_support');
  return f?.evidence as Partial<SubstantiveEvidence> | undefined;
}

/** Per-round critic grades, expanded from the substantive axis's ordinal_distribution
 *  (falls back to a single round echoing the axis verdict). */
function expandRoundGrades(result: RunResult): string[] {
  const ev = substantiveEvidence(result);
  const sc = ev?.self_consistency;
  const out: string[] = [];
  if (sc?.ordinal_distribution) {
    for (const [grade, count] of Object.entries(sc.ordinal_distribution)) {
      for (let i = 0; i < (count as number); i++) out.push(grade);
    }
  }
  // account for parse-failed / NEI rounds so the round count matches rounds_run.
  const target = sc?.rounds_run ?? out.length;
  while (out.length < target) out.push('(resampled — unparsed round)');
  if (out.length === 0) {
    const verdict = result.verdict.verdict.axis_findings.find((a: AxisFinding) => a.axis === 'substantive_support')?.verdict;
    out.push(verdict || 'fully-supported');
  }
  return out;
}

function perCallTokens(result: RunResult, totalCalls: number): TokenUsage {
  const t = result.cost.tokens;
  const d = totalCalls || 1;
  return {
    input: Math.round(t.input / d),
    output: Math.round(t.output / d),
    cache_read: Math.round(t.cache_read / d),
    cache_write: Math.round(t.cache_write / d),
  };
}
function cumulativeTokens(perCall: TokenUsage, calls: number): TokenUsage {
  return {
    input: perCall.input * calls,
    output: perCall.output * calls,
    cache_read: perCall.cache_read * calls,
    cache_write: perCall.cache_write * calls,
  };
}

function aggregateOf(items: RunResult[]): BatchAggregate {
  const total_cost_usd = round(items.reduce((s, r) => s + r.cost.total_usd, 0), 6);
  const total_ms = items.reduce((s, r) => s + r.timing.total_ms, 0);
  return { p_r_f: null, total_cost_usd, total_ms, n: items.length };
}

function stageSummary(stage: Stage, result: RunResult): string {
  const g = result.verdict.grounded;
  const v = result.verdict.verdict;
  const axis = (name: string) => v.axis_findings.find((a: AxisFinding) => a.axis === name);
  switch (stage) {
    case 'ingest':
      return `Resolved ${g.identifier.type.toUpperCase()} ${g.identifier.value}; claim verbatim-verified.`;
    case 'ground_retraction': {
      const r = axis('retraction');
      return `Retraction axis: ${r?.verdict} (${g.retraction.status}, ${g.retraction.source_agreement}).`;
    }
    case 'ground_scope': {
      const s = axis('species_scope');
      return `Species scope: ${s?.verdict}. Organism MeSH: ${g.organism_tags.map((t) => t.descriptor).join(', ') || '(none)'}.`;
    }
    case 'adjudicate': {
      const sub = axis('substantive_support');
      const sc = (sub?.evidence as Partial<SubstantiveEvidence> | undefined)?.self_consistency;
      return `Adjudicated: ${sub?.verdict} (${sub?.tier} confidence${sc ? `, exact agreement ${sc.a_exact}` : ''}).`;
    }
    case 'report':
      return 'Rendered JSON + HTML report.';
    default:
      return '';
  }
}

function paperRef(result: RunResult): string {
  return result.verdict.grounded.identifier.value;
}
function paperMode(result: RunResult): RunRequest['mode'] {
  return result.verdict.grounded.identifier.type === 'doi' ? 'doi' : 'pmid';
}

function modeOf(items: string[]): string {
  const counts = new Map<string, number>();
  for (const it of items) counts.set(it, (counts.get(it) ?? 0) + 1);
  let best = items[0];
  let bestN = -1;
  for (const [k, n] of counts) if (n > bestN) { best = k; bestN = n; }
  return best;
}

function round(x: number, dp: number): number {
  const p = Math.pow(10, dp);
  return Math.round(x * p) / p;
}
function clamp(x: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, x));
}
function nowMs(): number {
  // Wall clock is only used for internal bookkeeping; kept behind a helper for testability.
  return typeof performance !== 'undefined' ? performance.now() : 0;
}

// re-export the timing type so consumers don't need a second import for a common shape.
export type { RunTiming };
