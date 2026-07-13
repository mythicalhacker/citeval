/**
 * format.ts — small, pure display formatters shared across the design system and views.
 * Deliberately dependency-free (no Intl locale surprises in CI); tabular-nums does the alignment.
 */

/** USD with cents-to-sub-cent precision: $1.05, $0.0623, $12.40. */
export function usd(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—';
  const abs = Math.abs(n);
  const dp = abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6;
  // Sign goes before the glyph: "-$1.05", not "$-1.05".
  return `${n < 0 ? '-' : ''}$${abs.toFixed(dp)}`;
}

/** Milliseconds as a human duration: 910 ms, 1.48 s, 1 m 28 s. */
export function duration(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return '—';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const s = ms / 1000;
  if (s < 60) {
    const dp = s < 10 ? 2 : 1;
    // Guard the rollover: a value that rounds up to 60.0 s falls through to the minute form.
    if (Number(s.toFixed(dp)) < 60) return `${s.toFixed(dp)} s`;
  }
  // Derive minutes + seconds from ONE rounded total so the carry is consistent (never "1 m 60 s").
  const totalSec = Math.round(s);
  const m = Math.floor(totalSec / 60);
  const rem = totalSec % 60;
  return `${m} m ${rem.toString().padStart(2, '0')} s`;
}

/** Compact token counts: 42, 5.6k, 1.2M. */
export function compact(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—';
  const abs = Math.abs(n);
  if (abs < 1000) return String(Math.round(n));
  if (abs < 1_000_000) return `${(n / 1000).toFixed(abs < 10_000 ? 1 : 0)}k`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}

/** A 0–100 percentage: 42% or 42.5%. */
export function pct(n: number | null | undefined, dp = 0): string {
  if (n == null || Number.isNaN(n)) return '—';
  return `${n.toFixed(dp)}%`;
}

/** A 0–1 ratio rendered as a fixed-decimal figure: 0.90, 1.00. */
export function ratio(n: number | null | undefined, dp = 2): string {
  if (n == null || Number.isNaN(n)) return '—';
  return n.toFixed(dp);
}

/** Title-case a kebab/underscore token for display: `species_scope` → "Species scope". */
export function humanize(s: string): string {
  const t = s.replace(/[_-]+/g, ' ').trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}
