/**
 * tokens.ts — the single source of colour truth for the citeval design system (W1-FE-SHELL).
 *
 * The **provenance** palette is 1:1 with `src/citeval/reporting.py` (`_HTML_STYLE` / `_prov_class`),
 * so a badge in the app reads identically to the same badge in the embedded `report_html`. The
 * graded **RB1 ramp**, the **off-scale** tokens, and the **gate / confidence / step / surface**
 * tokens extend that language for the interactive UI. Every colour is defined for light *and* dark.
 *
 * How theming works (no drift, no FOUC): {@link installThemeVars} emits every token as a CSS custom
 * property under `:root` plus a `@media (prefers-color-scheme: dark)` override, injected into
 * `<head>` before React renders. Components never hard-code hex — they read `var(--cv-…)` via the
 * `*Style()` helpers below, so light/dark is handled entirely by the cascade.
 */
import { RB1_GRADES } from '../lib/types';
import type { RB1Grade, ProvenanceTier } from '../lib/types';

export interface ColorPair {
  bg: string;
  fg: string;
  border?: string;
}
export interface ThemedColor {
  light: ColorPair;
  dark: ColorPair;
}

/* ============================================================================================
 * Provenance atoms — verbatim from reporting.py `_HTML_STYLE`. Dark variants are hand-tuned to
 * AA contrast against their dark backgrounds while preserving the same hue family.
 * ========================================================================================== */
export type ProvAtom =
  | 'metadata-grounded'
  | 'text-grounded'
  | 'model-inferred'
  | 'stub-not-adjudicated'
  | 'composite';

export const PROVENANCE_TOKENS: Record<ProvAtom, ThemedColor> = {
  'metadata-grounded': { light: { bg: '#e6f4ea', fg: '#137333' }, dark: { bg: '#0f2a1b', fg: '#6ee7a3' } },
  'text-grounded': { light: { bg: '#e8f0fe', fg: '#1967d2' }, dark: { bg: '#16233d', fg: '#a8c7fa' } },
  'model-inferred': { light: { bg: '#fef7e0', fg: '#99590b' }, dark: { bg: '#33280a', fg: '#f5d67e' } },
  'stub-not-adjudicated': { light: { bg: '#f1f3f4', fg: '#5f6368' }, dark: { bg: '#26292e', fg: '#b3b8bf' } },
  composite: { light: { bg: '#f3e8fd', fg: '#7b2fbe' }, dark: { bg: '#2a1b3d', fg: '#d6b3f5' } },
};

/**
 * Mirror of reporting.py `_prov_class`: key on the leading whitespace-delimited atom (composites
 * keep their dominant atom's colour); anything unrecognised falls back to `composite`.
 */
export function provAtom(provenance: string | null | undefined): ProvAtom {
  // `.trim()` first so we match Python's `str.split()` (which ignores leading whitespace) — a
  // provenance with a leading space still classifies by its dominant atom, not as 'composite'.
  const atom = (provenance ?? '').trim().split(/\s+/)[0];
  switch (atom) {
    case 'metadata-grounded':
    case 'text-grounded':
    case 'model-inferred':
    case 'stub-not-adjudicated':
      return atom;
    default:
      return 'composite';
  }
}

/* ============================================================================================
 * The graded RB1 ordinal ramp (best 0 → worst 5). New to the UI (reporting.py does not colour the
 * grades). Accessible green→red pairs (fg meets AA on its bg in both schemes).
 * ========================================================================================== */
export const GRADE_TOKENS: ThemedColor[] = [
  /* 0 fully-supported                  */ { light: { bg: '#dcfce7', fg: '#15803d' }, dark: { bg: '#0f2a1a', fg: '#4ade80' } },
  /* 1 supported-with-overreach         */ { light: { bg: '#ecfccb', fg: '#4d7c0f' }, dark: { bg: '#1c2708', fg: '#a3e635' } },
  /* 2 partially-supported              */ { light: { bg: '#fef9c3', fg: '#a16207' }, dark: { bg: '#2a2408', fg: '#facc15' } },
  /* 3 technically-true-but-misleading  */ { light: { bg: '#ffedd5', fg: '#c2410c' }, dark: { bg: '#2c1a0a', fg: '#fb923c' } },
  /* 4 unsupported-for-the-claim        */ { light: { bg: '#fee2e2', fg: '#991b1b' }, dark: { bg: '#2e1414', fg: '#f87171' } },
  /* 5 contradicted                     */ { light: { bg: '#fecaca', fg: '#7f1d1d' }, dark: { bg: '#3f1212', fg: '#fca5a5' } },
];

/** Ordinal index (0 best … 5 worst) of an RB1 grade, or -1 if the verdict is off the scale. */
export function gradeIndex(verdict: string | null | undefined): number {
  return RB1_GRADES.indexOf(verdict as RB1Grade);
}

/* ============================================================================================
 * Off-scale substantive outcomes — never on the ordinal ramp. Neutral slate with a dashed border
 * to visually signal "off the scale".
 * ========================================================================================== */
export type OffScaleKind = 'nei' | 'nonsub';
export const OFFSCALE_TOKENS: Record<OffScaleKind, ThemedColor> = {
  // NOT_ENOUGH_INFO — the panel abstained; recorded, never scored as wrong.
  nei: { light: { bg: '#f1f5f9', fg: '#475569', border: '#cbd5e1' }, dark: { bg: '#1e293b', fg: '#cbd5e1', border: '#475569' } },
  // N/A — non-substantiating.
  nonsub: { light: { bg: '#f8fafc', fg: '#64748b', border: '#e2e8f0' }, dark: { bg: '#18202c', fg: '#94a3b8', border: '#334155' } },
};

/** Classify a substantive verdict string into a scale bucket. */
export type SubstantiveBucket = { kind: 'grade'; index: number } | { kind: 'offscale'; off: OffScaleKind };
export function classifySubstantive(verdict: string | null | undefined): SubstantiveBucket {
  const gi = gradeIndex(verdict);
  if (gi >= 0) return { kind: 'grade', index: gi };
  if (verdict === 'NOT_ENOUGH_INFO') return { kind: 'offscale', off: 'nei' };
  return { kind: 'offscale', off: 'nonsub' };
}

/* ============================================================================================
 * Gate tokens — the retraction / scope gate that forces `overall` to NOT SUPPORTED AS STATED.
 * A fired gate is a closed padlock (red); a clear gate is an open padlock (green).
 * ========================================================================================== */
export type GateState = 'fired' | 'clear';
export const GATE_TOKENS: Record<GateState, ThemedColor> = {
  fired: { light: { bg: '#fee2e2', fg: '#991b1b', border: '#fca5a5' }, dark: { bg: '#2e1414', fg: '#fca5a5', border: '#7f1d1d' } },
  clear: { light: { bg: '#e6f4ea', fg: '#137333', border: '#a7e3bf' }, dark: { bg: '#0f2a1b', fg: '#6ee7a3', border: '#1e5c39' } },
};

/* ============================================================================================
 * Confidence tiers (high / medium / low) + abstain, for ConfidenceChip / ConfidenceGauge.
 * ========================================================================================== */
export type ConfKey = ProvenanceTier | 'abstain';
export const CONFIDENCE_TOKENS: Record<ConfKey, ThemedColor> = {
  high: { light: { bg: '#e6f4ea', fg: '#137333' }, dark: { bg: '#0f2a1b', fg: '#6ee7a3' } },
  medium: { light: { bg: '#fef7e0', fg: '#99590b' }, dark: { bg: '#33280a', fg: '#f5d67e' } },
  low: { light: { bg: '#ffedd5', fg: '#c2410c' }, dark: { bg: '#2c1a0a', fg: '#fb923c' } },
  abstain: { light: { bg: '#f1f5f9', fg: '#475569' }, dark: { bg: '#1e293b', fg: '#cbd5e1' } },
};

/* ============================================================================================
 * Stepper stage states.
 * ========================================================================================== */
export type StepState = 'pending' | 'active' | 'done' | 'error';
export const STEP_TOKENS: Record<StepState, ThemedColor> = {
  pending: { light: { bg: '#f1f3f4', fg: '#5f6368', border: '#d5d9dd' }, dark: { bg: '#22262e', fg: '#9aa1ab', border: '#333a44' } },
  active: { light: { bg: '#e8ecff', fg: '#3730a3', border: '#4f46e5' }, dark: { bg: '#1e2140', fg: '#c7cbff', border: '#818cf8' } },
  done: { light: { bg: '#e6f4ea', fg: '#137333', border: '#a7e3bf' }, dark: { bg: '#0f2a1b', fg: '#6ee7a3', border: '#1e5c39' } },
  error: { light: { bg: '#fee2e2', fg: '#991b1b', border: '#fca5a5' }, dark: { bg: '#2e1414', fg: '#fca5a5', border: '#7f1d1d' } },
};

/* ============================================================================================
 * Surface + brand tokens (single hex pair, referenced by Tailwind theme + base CSS).
 * Dark surfaces match reporting.py's report_html (#16181c / #1b1e24) for visual continuity.
 * ========================================================================================== */
export const SURFACE_TOKENS: Record<string, ThemedColor> = {
  bg: { light: { bg: '#f7f8fa', fg: '#1a1a1a' }, dark: { bg: '#16181c', fg: '#e6e6e6' } },
  surface: { light: { bg: '#ffffff', fg: '#1a1a1a' }, dark: { bg: '#1b1e24', fg: '#e6e6e6' } },
  'surface-2': { light: { bg: '#f6f8fa', fg: '#1a1a1a' }, dark: { bg: '#22262e', fg: '#e6e6e6' } },
  border: { light: { bg: '#e5e7eb', fg: '#e5e7eb' }, dark: { bg: '#2a2f37', fg: '#2a2f37' } },
  text: { light: { bg: '#1a1a1a', fg: '#1a1a1a' }, dark: { bg: '#e6e6e6', fg: '#e6e6e6' } },
  'text-muted': { light: { bg: '#5b6270', fg: '#5b6270' }, dark: { bg: '#a1a7b0', fg: '#a1a7b0' } },
  brand: { light: { bg: '#4f46e5', fg: '#4f46e5' }, dark: { bg: '#818cf8', fg: '#818cf8' } },
  'brand-contrast': { light: { bg: '#ffffff', fg: '#ffffff' }, dark: { bg: '#0b0d12', fg: '#0b0d12' } },
  ring: { light: { bg: '#4f46e5', fg: '#4f46e5' }, dark: { bg: '#818cf8', fg: '#818cf8' } },
};

/* ============================================================================================
 * CSS-variable naming + inline-style helpers. `var(--cv-<group>-<key>-<slot>)`.
 * ========================================================================================== */
function slug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}
function v(name: string): string {
  return `var(--cv-${name})`;
}

/** A `React.CSSProperties` fragment (background/color/borderColor) referencing a token's vars. */
export interface TokenStyle {
  background: string;
  color: string;
  borderColor?: string;
}
function styleFor(group: string, key: string, hasBorder: boolean): TokenStyle {
  const base = `${group}-${key}`;
  const s: TokenStyle = { background: v(`${base}-bg`), color: v(`${base}-fg`) };
  if (hasBorder) s.borderColor = v(`${base}-border`);
  return s;
}

export function provStyle(provenance: string): TokenStyle {
  return styleFor('prov', slug(provAtom(provenance)), false);
}
export function gradeStyle(index: number): TokenStyle {
  const i = Math.min(Math.max(index, 0), GRADE_TOKENS.length - 1);
  return styleFor('grade', String(i), false);
}
export function offscaleStyle(off: OffScaleKind): TokenStyle {
  return styleFor('offscale', off, true);
}
export function gateStyle(state: GateState): TokenStyle {
  return styleFor('gate', state, true);
}
export function confStyle(tier: ConfKey): TokenStyle {
  return styleFor('conf', tier, false);
}
export function stepStyle(state: StepState): TokenStyle {
  return styleFor('step', state, true);
}

/** Resolve one raw hex for a token slot in a given scheme — for canvas/SVG gradients that can't
 *  use CSS vars (e.g. the AxisScale ramp preview, the ConfidenceGauge arc). */
export function gradeHex(index: number, scheme: 'light' | 'dark', slot: keyof ColorPair = 'fg'): string {
  const i = Math.min(Math.max(index, 0), GRADE_TOKENS.length - 1);
  return GRADE_TOKENS[i][scheme][slot] ?? GRADE_TOKENS[i][scheme].fg;
}

/* ============================================================================================
 * Theme installation — emit every token as a CSS custom property.
 * ========================================================================================== */
function collectVars(scheme: 'light' | 'dark'): Record<string, string> {
  const out: Record<string, string> = {};
  const put = (group: string, key: string, tc: ThemedColor) => {
    const base = `--cv-${group}-${slug(key)}`;
    out[`${base}-bg`] = tc[scheme].bg;
    out[`${base}-fg`] = tc[scheme].fg;
    if (tc[scheme].border) out[`${base}-border`] = tc[scheme].border as string;
  };
  for (const [k, tc] of Object.entries(PROVENANCE_TOKENS)) put('prov', k, tc);
  GRADE_TOKENS.forEach((tc, i) => put('grade', String(i), tc));
  for (const [k, tc] of Object.entries(OFFSCALE_TOKENS)) put('offscale', k, tc);
  for (const [k, tc] of Object.entries(GATE_TOKENS)) put('gate', k, tc);
  for (const [k, tc] of Object.entries(CONFIDENCE_TOKENS)) put('conf', k, tc);
  for (const [k, tc] of Object.entries(STEP_TOKENS)) put('step', k, tc);
  // Surfaces are single-value; expose the `bg` slot directly as `--cv-<name>`.
  for (const [k, tc] of Object.entries(SURFACE_TOKENS)) {
    out[`--cv-${slug(k)}`] = tc[scheme].bg;
  }
  return out;
}

function block(selector: string, vars: Record<string, string>): string {
  const body = Object.entries(vars).map(([k, val]) => `  ${k}: ${val};`).join('\n');
  return `${selector} {\n${body}\n}`;
}

/** The full injectable stylesheet: light on `:root`, dark under a media query. */
export function buildThemeCss(): string {
  const light = collectVars('light');
  const dark = collectVars('dark');
  const rootLight = { 'color-scheme': 'light dark', ...light };
  return [
    block(':root', rootLight as Record<string, string>),
    `@media (prefers-color-scheme: dark) {\n${block(':root', dark)
      .split('\n')
      .map((l) => `  ${l}`)
      .join('\n')}\n}`,
  ].join('\n\n');
}

let installed = false;
/** Inject the token stylesheet into <head> once, synchronously, before first paint. */
export function installThemeVars(): void {
  if (installed || typeof document === 'undefined') return;
  installed = true;
  const style = document.createElement('style');
  style.id = 'citeval-tokens';
  style.textContent = buildThemeCss();
  document.head.appendChild(style);
}
