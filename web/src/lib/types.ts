/**
 * FROZEN wire types for the citeval web app (W0-CONTRACTS).
 *
 * 1:1 TypeScript mirror of `server/citeval_api/contracts.py`, plus the `render_json` verdict
 * sub-shapes that come from the FROZEN `src/citeval/contracts.py`. This file is the FE's single
 * source of truth — every view, `api.ts`, `mockServer.ts`, and `fixtures.ts` import from here.
 *
 * If a shape changes it changes here AND in `contracts.py` AND in `docs/api_contract.md`
 * (manager decision — see api_contract.md §Change control). Canonical JSON examples:
 * `data/schemas/run_result.json` and `data/schemas/sse_events.json`.
 */

/* ============================================================================================
 * Enumerations
 * ========================================================================================== */
export type RunMode = 'pmid' | 'doi' | 'citation' | 'manuscript' | 'auto';

/** The five pipeline stages, in canonical order (stepper + ETA depend on this order). */
export type Stage = 'ingest' | 'ground_retraction' | 'ground_scope' | 'adjudicate' | 'report';
export const STAGE_ORDER: readonly Stage[] = [
  'ingest', 'ground_retraction', 'ground_scope', 'adjudicate', 'report',
] as const;

/** The three adversarial debate roles (all Opus 4.8 — CLAUDE.md invariant #4). */
export type DebateRole = 'supporter' | 'refuter' | 'critic';
/** Alias matching the Python contract's `Role` name (server/citeval_api/contracts.py) so the
 *  three-way mirror is name-for-name; identical values. */
export type Role = DebateRole;

export type Phase = 'start' | 'end';

export type ItemStatus = 'queued' | 'running' | 'done' | 'error';

/* ---- axis verdict vocabularies (produced by citeval.objective_axes / the adjudicator) ----- */
export type RetractionVerdict =
  | 'RELIES_ON_RETRACTED' | 'CITED_PAPER_HAS_EOC' | 'NOT_RETRACTED';
export type ScopeVerdict = 'SCOPE_MISMATCH' | 'SCOPE_CONSISTENT' | 'NOT_ASSESSED';
export type ProvenanceTier = 'high' | 'medium' | 'low';

/** The RB1 ordinal substantive-support scale, best (0) → worst (5). */
export const RB1_GRADES = [
  'fully-supported',
  'supported-with-overreach',
  'partially-supported',
  'technically-true-but-misleading',
  'unsupported-for-the-claim',
  'contradicted',
] as const;
export type RB1Grade = (typeof RB1_GRADES)[number];
/** Non-graded substantive outcomes (never on the ordinal scale). */
export type SubstantiveOutcome = RB1Grade | 'NOT_ENOUGH_INFO' | 'N/A — non-substantiating';

/* ============================================================================================
 * REST request/response bodies
 * ========================================================================================== */
export interface RunRequest {
  claim: string;
  /** A PMID ("22088800") or DOI ("10.1016/...") to resolve. */
  paper_ref?: string | null;
  /** A pasted free-text reference to parse into an identifier. */
  citation_string?: string | null;
  /** Bring-your-own full text (no NCBI lookup). */
  manuscript_text?: string | null;
  mode?: RunMode;
}

export interface BatchItem {
  claim: string;
  paper_ref?: string | null;
}

export interface BatchRequest {
  items: BatchItem[];
}

export interface RunCreated { run_id: string; }
export interface BatchCreated { batch_id: string; }
export interface Health { status: 'ok'; }

/* ============================================================================================
 * Cost / telemetry
 * ========================================================================================== */

/** Mirrors the Anthropic SDK `response.usage` (what `pricing.cost_of` consumes). */
export interface RawUsage {
  input_tokens: number;
  output_tokens: number;
  cache_creation_input_tokens: number;
  cache_read_input_tokens: number;
  role?: DebateRole | null;
}

/** Friendly four-tier roll-up used on `cost_update` and inside `TelemetrySummary`. */
export interface TokenUsage {
  input: number;
  output: number;
  cache_read: number;
  cache_write: number;
}

export interface RoleCost {
  usd: number;
  n_calls: number;
  tokens: TokenUsage;
}

export interface TelemetrySummary {
  total_usd: number;
  /** Keyed by debate role (plus "unknown" for untagged calls). */
  per_role: Record<string, RoleCost>;
  tokens: TokenUsage;
  n_model_calls: number;
}

/** GET /api/pricing — USD per MILLION tokens (illustrative placeholders; see pricing.py CONFIRM). */
export interface PricingInfo {
  input: number;
  output: number;
  cache_write: number;
  cache_read: number;
  unit: 'usd_per_million_tokens';
  note: string;
}

/* ============================================================================================
 * The verdict — a verbatim `citeval.reporting.render_json` object.
 * These sub-shapes mirror the FROZEN `src/citeval/contracts.py`; see data/schemas/grounded.json.
 * ========================================================================================== */
export interface CitedIdentifier {
  type: 'pmid' | 'doi';
  value: string;
}

export interface ClaimUnit {
  atomic_claim: string;
  cited_identifier: CitedIdentifier;
  citing_source?: Record<string, unknown> | null;
}

export interface MeshTag {
  descriptor: string;
  ui: string;
  tree_numbers: string[];
  major_topic: boolean;
}

export interface RetractionWatchHit {
  present: boolean;
  rw_record_id?: string | null;
  reason?: string | null;
  date?: string | null;
}

export interface CommentsCorrection {
  ref_type: string;
  pmid?: string | null;
  source?: string | null;
}

export interface RetractionInfo {
  status: 'RETRACTED' | 'EXPRESSION_OF_CONCERN' | 'NONE_FOUND';
  retraction_watch?: RetractionWatchHit | null;
  ncbi_publication_type_flag: boolean;
  comments_corrections: CommentsCorrection[];
  source_agreement: string;
  provenance: string;
}

export interface GroundedRecord {
  identifier: CitedIdentifier;
  title: string;
  abstract: string;
  mesh_all: string[];
  organism_tags: MeshTag[];
  population_tags: MeshTag[];
  sex_tags: MeshTag[];
  publication_types: string[];
  retraction: RetractionInfo;
  has_humans: boolean;
  provenance: Record<string, unknown>;
  grounding_errors: string[];
  full_text: string;
  full_text_provenance: string;
}

export interface ScopeFrame {
  organism: string | null;
  organism_evidence: string[];
  population: string | null;
  population_evidence: string[];
  effect: string | null;
  direction: string | null;
  direction_evidence: string[];
  dose_stated: boolean;
  provenance: string;
  tier: ProvenanceTier | string;
}

/**
 * One axis finding. `provenance` is a composite-friendly string; canonical atoms:
 * "metadata-grounded" | "text-grounded" | "model-inferred" | "stub-not-adjudicated".
 * `evidence` is an open dict; for `substantive_support` it carries the CONTEXT_PACK §6 keys
 * (see SubstantiveEvidence below), read defensively by the renderer.
 */
export interface AxisFinding {
  axis: 'retraction' | 'species_scope' | 'population_scope' | 'substantive_support' | string;
  verdict: RetractionVerdict | ScopeVerdict | SubstantiveOutcome | string;
  tier: ProvenanceTier | string;
  provenance: string;
  detail: string;
  evidence: Record<string, unknown> & Partial<SubstantiveEvidence>;
}

/** The CONTEXT_PACK §6 evidence shape on the graded `substantive_support` axis (a subset of
 *  keys the renderer reads; richer keys exist and are ignored by C5). */
export interface SubstantiveEvidence {
  confidence: { verbalized: string; agreement: number; n_samples: number };
  calibration: { note: string };
  supporter: { span: string; point: string };
  refuter: { span: string; objection: string };
  abstained: boolean;
  self_consistency?: {
    rounds_configured: number;
    rounds_run: number;
    rounds_valid: number;
    a_exact: number;
    a_adj: number;
    conf_hybrid?: number;
    non_adjacent_multimodal: boolean;
    ordinal_distribution: Record<string, number>;
    n_nei: number;
    n_non_substantiating: number;
    n_parse_failed: number;
    /** Ordinal index of the modal grade (0=best…5=worst), or null when none was placed. */
    grade_ordinal?: number | null;
    output_tokens: (number | null)[];
    tau_abstain?: number;
    adjacent_floor?: number;
  };
}

export interface VerdictCore {
  claim: string;
  cited_identifier: CitedIdentifier;
  overall: string;
  axis_findings: AxisFinding[];
  unverifiable_axes: Record<string, string>;
  stub: boolean;
  notes: string[];
}

/** The full `render_json` output — `RunResult.verdict`. */
export interface RenderJson {
  claim_unit: ClaimUnit;
  grounded: GroundedRecord;
  claim_scope: ScopeFrame;
  verdict: VerdictCore;
}

/* ============================================================================================
 * RunResult / BatchResult
 * ========================================================================================== */
export interface RunTiming {
  /** Keyed by Stage. */
  per_stage_ms: Record<string, number>;
  total_ms: number;
  est_total_ms: number;
}

export interface RunResult {
  run_id: string;
  verdict: RenderJson;
  timing: RunTiming;
  cost: TelemetrySummary;
  /** Verbatim `citeval.reporting.render_html` document. */
  report_html: string;
}

export interface BatchAggregate {
  /** Present only when items carry gold labels; otherwise null (hide the P/R/F header). */
  p_r_f?: { precision: number; recall: number; f1: number } | null;
  total_cost_usd: number;
  total_ms: number;
  n: number;
}

export interface BatchResult {
  batch_id: string;
  items: RunResult[];
  aggregate: BatchAggregate;
}

/* ============================================================================================
 * SSE — envelope + one payload type per event.
 * The transport ships each frame as `event: <name>` + `data: <envelope merged with the fields
 * below>`. So each *Data type below already includes the envelope fields.
 * ========================================================================================== */
export interface SSEEnvelope {
  run_id: string;
  /** Monotonic, gap-free per stream — lets a late/replayed subscriber order + de-dup. */
  seq: number;
  ts: number;        // epoch seconds
  elapsed_ms: number; // ms since run_start
}

export type RunStartData = SSEEnvelope & { mode: RunMode; paper_ref?: string | null };
export type StageStartData = SSEEnvelope & { stage: Stage };
export type StageEndData = SSEEnvelope & { stage: Stage; summary: string };
export type ModelCallData = SSEEnvelope & {
  role: DebateRole; round: number; phase: Phase;
  usage?: TokenUsage | null; cost_usd?: number | null;
};
export type DebateRoundData = SSEEnvelope & {
  round: number;
  supporter_stance: string;
  refuter_stance: string;
  critic_grade: string;
  /** Running exact-agreement (a_exact) after this round. */
  agreement: number;
};
export type CostUpdateData = SSEEnvelope & {
  cumulative_usd: number; delta_usd: number; tokens: TokenUsage;
};
export type ProgressData = SSEEnvelope & {
  pct: number; est_total_ms: number; est_remaining_ms: number;
};
export type RunCompleteData = SSEEnvelope & { result: RunResult };
export type ErrorData = SSEEnvelope & { stage?: Stage | null; message: string };

/* ---- batch-stream events ------------------------------------------------------------------ */
export type BatchStartData = SSEEnvelope & { n: number };
export type ItemUpdateData = SSEEnvelope & { index: number; run_id: string; status: ItemStatus };
export type BatchProgressData = SSEEnvelope & {
  done: number; total: number; cost_usd: number; elapsed_ms: number;
};
export type BatchCompleteData = SSEEnvelope & { result: BatchResult };

/** Name → payload map for both streams. */
export interface SSEEventMap {
  run_start: RunStartData;
  stage_start: StageStartData;
  stage_end: StageEndData;
  model_call: ModelCallData;
  debate_round: DebateRoundData;
  cost_update: CostUpdateData;
  progress: ProgressData;
  run_complete: RunCompleteData;
  error: ErrorData;
  // batch
  batch_start: BatchStartData;
  item_update: ItemUpdateData;
  batch_progress: BatchProgressData;
  batch_complete: BatchCompleteData;
}

export type SSEEventName = keyof SSEEventMap;

/** A single decoded SSE frame — discriminated on `event`. This is what `api.ts` / `mockServer.ts`
 *  hand to subscribers. */
export type SSEFrame = {
  [K in SSEEventName]: { event: K; data: SSEEventMap[K] };
}[SSEEventName];

/** Callback a subscriber registers with the api client / mock server. */
export type SSEHandler = (frame: SSEFrame) => void;

export const RUN_EVENT_NAMES: readonly SSEEventName[] = [
  'run_start', 'stage_start', 'model_call', 'debate_round', 'cost_update',
  'progress', 'stage_end', 'run_complete', 'error',
] as const;

export const BATCH_EVENT_NAMES: readonly SSEEventName[] = [
  'batch_start', 'item_update', 'batch_progress', 'batch_complete',
] as const;
