/**
 * presets.ts (W2-FE-BATCH) — the one-click batches the composer offers.
 *
 * Two honest replay families:
 *  • PROOF — the four committed proof fixtures (real verdicts baked from the real pipeline),
 *    repeatable ×N so you can watch true concurrency roll across several waves.
 *  • CORPUS — the committed calibration corpora (corpus_cal30 / corpus_cal_ext), replayed with
 *    their real claims, cited papers, and GOLD labels. Against the mock the per-item verdict/cost
 *    for a paper with no fixture is an ILLUSTRATIVE stand-in (see corpus.ts / the dashboard banner);
 *    against a live backend every row is real.
 */
import { FIXTURES } from '../../lib/fixtures';
import type { PlannedItem } from './model';
import { CORPUS_CAL30, CORPUS_EXT, CORPUS_ALL, type CorpusCase } from './corpus';

/** The cited paper refs the mock has real fixtures for — everything else renders as a stand-in. */
export const FIXTURE_REFS: ReadonlySet<string> = new Set(FIXTURES.map((f) => f.preset.paper_ref));

/** True when (in mock mode) this paper would render as an illustrative stand-in rather than a
 *  real verdict — i.e. the mock has no committed fixture for it. */
export function isStandIn(paperRef: string | null, usingMock: boolean): boolean {
  if (!usingMock) return false;
  return !paperRef || !FIXTURE_REFS.has(paperRef);
}

/** The four proof fixtures as batch items, optionally repeated to scale up the wave count. */
export function proofItems(repeat = 1): PlannedItem[] {
  const out: PlannedItem[] = [];
  for (let r = 0; r < repeat; r += 1) {
    for (const f of FIXTURES) {
      out.push({ claim: f.preset.claim, paperRef: f.preset.paper_ref, corpus: null });
    }
  }
  return out;
}

/** A corpus case → a batch item (prefer the PMID; fall back to the DOI the mock can sniff). */
function corpusToItem(c: CorpusCase): PlannedItem {
  return { claim: c.claim, paperRef: c.cited_pmid ?? c.cited_doi ?? null, corpus: c };
}

export function corpusItems(which: 'cal30' | 'ext' | 'all'): PlannedItem[] {
  const src = which === 'cal30' ? CORPUS_CAL30 : which === 'ext' ? CORPUS_EXT : CORPUS_ALL;
  return src.map(corpusToItem);
}

export interface ReplaySpec {
  key: string;
  label: string;
  /** Short line shown under the button. */
  detail: string;
  /** Whether these items carry committed gold labels (enables the gold-agreement readout). */
  corpus: boolean;
  build(): PlannedItem[];
}

export const REPLAYS: ReplaySpec[] = [
  {
    key: 'proof-8',
    label: 'Demo batch · 8',
    detail: 'The 4 proof cases ×2 — two full concurrency waves, real verdicts.',
    corpus: false,
    build: () => proofItems(2),
  },
  {
    key: 'proof-4',
    label: 'Proof set · 4',
    detail: 'Retraction · scope · graded over-reach · abstention — one of each.',
    corpus: false,
    build: () => proofItems(1),
  },
  {
    key: 'proof-12',
    label: 'Stress · 12',
    detail: 'The 4 proof cases ×3 — three waves against the worker pool.',
    corpus: false,
    build: () => proofItems(3),
  },
  {
    key: 'corpus-30',
    label: 'Corpus · cal30',
    detail: '30-case calibration corpus, with committed gold labels.',
    corpus: true,
    build: () => corpusItems('cal30'),
  },
  {
    key: 'corpus-ext',
    label: 'Corpus · ext',
    detail: '45-case held-out extension corpus.',
    corpus: true,
    build: () => corpusItems('ext'),
  },
  {
    key: 'corpus-all',
    label: 'Corpus · all 75',
    detail: 'Both corpora — the full committed replay set.',
    corpus: true,
    build: () => corpusItems('all'),
  },
];

/** Demo playback speeds (mock only — a live backend streams in real time and ignores this). */
export interface SpeedOption {
  label: string;
  value: number;
}
export const SPEED_OPTIONS: SpeedOption[] = [
  { label: 'Slow', value: 6 },
  { label: 'Normal', value: 12 },
  { label: 'Fast', value: 30 },
  { label: 'Instant', value: Infinity },
];
export const DEFAULT_SPEED = 12;
