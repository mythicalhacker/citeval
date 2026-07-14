/**
 * model.ts — the RunView state machine (W2-FE-RUN).
 *
 * A single reducer folds the frozen SSE stream (api_contract.md §3) into one `RunState` that every
 * panel reads: the Stepper drives off `stageStatuses`, the debate stream off `rounds` + `gradeCounts`,
 * the cost/ETA bar off `cost` + `progress`, and the inline verdict off `result`. The reducer is pure
 * and transport-agnostic — it never knows whether a frame came from a live backend or the recorded
 * mock replay (LR-06's whole point). `useRunEngine` owns the streaming; this file owns the folding.
 */
import type {
  Stage, RunMode, RunRequest, RunResult, TokenUsage, SSEFrame,
  AxisFinding, SubstantiveEvidence,
} from '../../lib/types';
import { STAGE_ORDER } from '../../lib/types';
import type { StepState, ConfKey } from '../../design/tokens';

/** How the run was started: a live (transport-agnostic) run or a deterministic recorded replay. */
export type RunSource = 'live' | 'replay';
export type RunPhase = 'idle' | 'running' | 'complete' | 'error' | 'cancelled';

/** One adjudication round, assembled from a `debate_round` frame + the `cost_update` that follows. */
export interface RoundView {
  round: number;
  supporterStance: string;
  refuterStance: string;
  criticGrade: string;
  /** Running exact-agreement (a_exact) reported by the stream after this round. */
  agreement: number;
  /** Cumulative USD after this round (from the paired cost_update), if seen. */
  cumulativeUsd?: number;
  /** USD spent on this round's three calls (from the paired cost_update), if seen. */
  deltaUsd?: number;
  /**
   * The ~6000-token evidence block carries a prompt-cache breakpoint reused across all 21 calls
   * (adjudicator.py:_content_blocks): round 1 *writes* the cache, later rounds *read* it. Surfacing
   * that live is a free demonstration of engineering already built and otherwise invisible (LR-03).
   */
  cache: 'write' | 'hit';
}

/** A model call currently in flight — powers the live "calling supporter…" pulse under Adjudicate. */
export interface ActiveCall {
  role: 'supporter' | 'refuter' | 'critic';
  round: number;
}

export interface RunState {
  phase: RunPhase;
  source: RunSource | null;
  request: RunRequest | null;
  runId: string | null;
  mode: RunMode | null;

  /** Explicit per-stage states — fed straight to <Stepper statuses=…>. */
  stageStatuses: Partial<Record<Stage, StepState>>;
  /** One-line result per completed stage (from stage_end.summary). */
  stageSummaries: Partial<Record<Stage, string>>;
  /** Per-stage elapsed ms — live deltas while running, authoritative timing once complete. */
  stageDurations: Record<string, number>;
  /** Internal: elapsed-ms mark captured at each stage_start, to derive a duration on stage_end. */
  stageStartedAt: Partial<Record<Stage, number>>;

  activeCall: ActiveCall | null;
  rounds: RoundView[];
  /** The self-consistency distribution building up round-by-round (grade → count). */
  gradeCounts: Record<string, number>;
  /** Latest running exact-agreement (a_exact). */
  agreement: number;

  cost: { cumulativeUsd: number; tokens: TokenUsage | null };
  progress: { pct: number; estTotalMs: number; estRemainingMs: number } | null;
  /** Envelope elapsed_ms of the most recent frame — the live wall clock of the simulated pipeline. */
  elapsedMs: number;

  result: RunResult | null;
  errorStage: Stage | null;
  errorMessage: string | null;
}

export const initialRunState: RunState = {
  phase: 'idle',
  source: null,
  request: null,
  runId: null,
  mode: null,
  stageStatuses: {},
  stageSummaries: {},
  stageDurations: {},
  stageStartedAt: {},
  activeCall: null,
  rounds: [],
  gradeCounts: {},
  agreement: 0,
  cost: { cumulativeUsd: 0, tokens: null },
  progress: null,
  elapsedMs: 0,
  result: null,
  errorStage: null,
  errorMessage: null,
};

export type RunAction =
  | { type: 'start'; source: RunSource; request: RunRequest }
  | { type: 'frame'; frame: SSEFrame }
  | { type: 'stream_failed'; message: string }
  | { type: 'cancel' }
  | { type: 'reset' };

/** A phase from which no further stream frame should change the outcome. */
export function isTerminal(phase: RunPhase): boolean {
  return phase === 'complete' || phase === 'error' || phase === 'cancelled';
}

/** All stages strictly before `stage` in canonical order — used to backfill "done" defensively. */
function earlierStages(stage: Stage): Stage[] {
  const i = STAGE_ORDER.indexOf(stage);
  return i <= 0 ? [] : STAGE_ORDER.slice(0, i);
}

export function runReducer(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case 'reset':
      return initialRunState;

    case 'start':
      return {
        ...initialRunState,
        phase: 'running',
        source: action.source,
        request: action.request,
        mode: action.request.mode ?? null,
        // Seed the first stage as active immediately so the Stepper animates before the first frame.
        stageStatuses: { ingest: 'active' },
      };

    case 'stream_failed':
      // A transport-level failure with no application `error` frame (e.g. a dead backend on the
      // live path). Only escalate if we weren't already terminal.
      if (isTerminal(state.phase)) return state;
      return { ...state, phase: 'error', errorMessage: action.message, activeCall: null };

    case 'cancel':
      // User cancelled an in-flight run. Move to a terminal phase (keeping whatever streamed so far
      // visible) so the view stops signalling active work and offers a "new run" affordance.
      if (state.phase !== 'running') return state;
      return { ...state, phase: 'cancelled', activeCall: null };

    case 'frame':
      return reduceFrame(state, action.frame);

    default:
      return state;
  }
}

function reduceFrame(state: RunState, frame: SSEFrame): RunState {
  // Every frame carries the envelope; keep the live clock + run id in sync on all of them. The clock
  // is monotonic: a synthetic transport-error frame carries elapsed_ms:0 (api.ts), and `?? ` would
  // NOT fall through on a numeric 0 — Math.max keeps the last real elapsed instead of snapping to 0.
  const base: RunState = {
    ...state,
    elapsedMs: Math.max(state.elapsedMs, frame.data.elapsed_ms ?? state.elapsedMs),
    runId: frame.data.run_id || state.runId,
  };

  switch (frame.event) {
    case 'run_start':
      return { ...base, phase: 'running', mode: frame.data.mode ?? base.mode };

    case 'stage_start': {
      const stage = frame.data.stage;
      const statuses = { ...base.stageStatuses };
      for (const s of earlierStages(stage)) if (statuses[s] !== 'error') statuses[s] = 'done';
      if (statuses[stage] !== 'error') statuses[stage] = 'active';
      return {
        ...base,
        stageStatuses: statuses,
        stageStartedAt: { ...base.stageStartedAt, [stage]: base.elapsedMs },
      };
    }

    case 'stage_end': {
      const stage = frame.data.stage;
      const started = base.stageStartedAt[stage] ?? base.elapsedMs;
      return {
        ...base,
        stageStatuses: { ...base.stageStatuses, [stage]: 'done' },
        stageSummaries: { ...base.stageSummaries, [stage]: frame.data.summary },
        stageDurations: { ...base.stageDurations, [stage]: Math.max(base.elapsedMs - started, 0) },
      };
    }

    case 'model_call': {
      const activeCall: ActiveCall | null =
        frame.data.phase === 'start' ? { role: frame.data.role, round: frame.data.round } : null;
      return { ...base, activeCall };
    }

    case 'debate_round': {
      const d = frame.data;
      const round: RoundView = {
        round: d.round,
        supporterStance: d.supporter_stance,
        refuterStance: d.refuter_stance,
        criticGrade: d.critic_grade,
        agreement: d.agreement,
        cache: d.round <= 1 ? 'write' : 'hit',
      };
      return {
        ...base,
        rounds: [...base.rounds, round],
        agreement: d.agreement,
        gradeCounts: { ...base.gradeCounts, [d.critic_grade]: (base.gradeCounts[d.critic_grade] ?? 0) + 1 },
      };
    }

    case 'cost_update': {
      const d = frame.data;
      // Attach this round's cost to the most recent round card (cost_update trails its debate_round).
      const rounds = base.rounds.slice();
      const last = rounds[rounds.length - 1];
      if (last) rounds[rounds.length - 1] = { ...last, cumulativeUsd: d.cumulative_usd, deltaUsd: d.delta_usd };
      return { ...base, rounds, cost: { cumulativeUsd: d.cumulative_usd, tokens: d.tokens } };
    }

    case 'progress':
      return {
        ...base,
        progress: { pct: frame.data.pct, estTotalMs: frame.data.est_total_ms, estRemainingMs: frame.data.est_remaining_ms },
      };

    case 'run_complete': {
      const result = frame.data.result;
      const statuses: Partial<Record<Stage, StepState>> = {};
      for (const s of STAGE_ORDER) statuses[s] = base.stageStatuses[s] === 'error' ? 'error' : 'done';
      const sub = substantiveEvidence(result);
      return {
        ...base,
        phase: isTerminal(base.phase) ? base.phase : 'complete',
        result,
        stageStatuses: statuses,
        // Authoritative per-stage timing wins over the live estimates.
        stageDurations: { ...base.stageDurations, ...result.timing.per_stage_ms },
        cost: { cumulativeUsd: result.cost.total_usd, tokens: result.cost.tokens },
        agreement: sub?.self_consistency?.a_exact ?? sub?.confidence?.agreement ?? base.agreement,
        progress: { pct: 100, estTotalMs: result.timing.est_total_ms, estRemainingMs: 0 },
        activeCall: null,
      };
    }

    case 'error': {
      const statuses = { ...base.stageStatuses };
      // A transport-drop error frame (api.ts) carries no `stage`; fall back to whatever stage was
      // mid-flight so we never leave a stage rendering as 'active'/aria-current on a failed run.
      const active = STAGE_ORDER.find((s) => base.stageStatuses[s] === 'active') ?? null;
      const stage = frame.data.stage ?? active;
      if (stage) statuses[stage] = 'error';
      return { ...base, phase: 'error', errorStage: stage, errorMessage: frame.data.message, activeCall: null, stageStatuses: statuses };
    }

    default:
      return base;
  }
}

/* ============================================================================================
 * Derived-value helpers (pure) — shared by the panels so the reducer stays lean.
 * ========================================================================================== */

/** The graded substantive-support axis finding, if present. */
export function substantiveAxis(result: RunResult | null): AxisFinding | undefined {
  return result?.verdict.verdict.axis_findings.find((a) => a.axis === 'substantive_support');
}

/** The CONTEXT_PACK §6 evidence on the substantive axis (confidence, self-consistency, spans). */
export function substantiveEvidence(result: RunResult | null): Partial<SubstantiveEvidence> | undefined {
  return substantiveAxis(result)?.evidence as Partial<SubstantiveEvidence> | undefined;
}

/**
 * A *display* confidence tier from the running agreement, for the live gauge before the real tier
 * lands with run_complete. Thresholds mirror the adjudicator's trust floors (τ_abstain 0.5, adjacent
 * floor 0.7) coarsely; the authoritative tier replaces this the moment the result arrives.
 */
export function liveTier(agreement: number): ConfKey {
  if (agreement >= 0.75) return 'high';
  if (agreement >= 0.5) return 'medium';
  return 'low';
}

/** The authoritative confidence read for the completed run's gauge/chip. */
export interface ConfidenceRead {
  tier: ConfKey;
  agreement: number;
  nSamples?: number;
  abstained: boolean;
}
/** Narrow an arbitrary string to a confidence tier, or undefined if it isn't one. */
function asTier(s: string | undefined): ConfKey | undefined {
  return s === 'high' || s === 'medium' || s === 'low' ? s : undefined;
}

export function confidenceRead(result: RunResult | null): ConfidenceRead {
  const ev = substantiveEvidence(result);
  const sc = ev?.self_consistency;
  const conf = ev?.confidence;
  const abstained = ev?.abstained === true;
  // `verbalized` is a free string on the wire; only trust it if it's a real tier, else derive one
  // from agreement so a stray value can never flow into confStyle()/ConfidenceGauge as invalid.
  const tier = asTier(conf?.verbalized) ?? liveTier(sc?.a_exact ?? conf?.agreement ?? 0);
  return {
    tier: abstained ? 'abstain' : tier,
    agreement: sc?.a_exact ?? conf?.agreement ?? 0,
    nSamples: conf?.n_samples ?? sc?.rounds_valid,
    abstained,
  };
}

/** True when the run's `overall` reports a fired objective gate (retraction / scope). */
export function gateFired(result: RunResult | null): boolean {
  return /NOT SUPPORTED AS STATED/i.test(result?.verdict.verdict.overall ?? '');
}

/** Human ETA range string, e.g. "0:12–0:31 left". Widen ±40% to read as an honest estimate. */
export function etaRange(remainingMs: number): string {
  if (remainingMs <= 0) return 'wrapping up…';
  const lo = remainingMs * 0.75;
  const hi = remainingMs * 1.25;
  return `${clockMs(lo)}–${clockMs(hi)} left`;
}

/** m:ss from ms. */
export function clockMs(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}
