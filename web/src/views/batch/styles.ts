/**
 * styles.ts (W2-FE-BATCH) — the batch view's own keyframes, injected once into <head>.
 *
 * The shared index.css is W1-owned and off-limits to a view session, so the two animations the
 * dashboard needs (an indeterminate "running" bar and a one-shot "just finished" flash) live here,
 * namespaced `cv-batch-*` to avoid any collision. The global `prefers-reduced-motion` rule in
 * index.css already neutralises these for users who ask for reduced motion.
 */
const STYLE_ID = 'cv-batch-styles';

const CSS = `
@keyframes cvBatchIndeterminate {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(300%); }
}
@keyframes cvBatchFlash {
  0%   { box-shadow: inset 0 0 0 9999px color-mix(in srgb, var(--cv-step-done-bg) 65%, transparent); }
  100% { box-shadow: inset 0 0 0 9999px transparent; }
}
@keyframes cvBatchPulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.35; transform: scale(0.72); }
}
.cv-batch-indeterminate-dot {
  display: inline-block;
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 9999px;
  background: currentColor;
  animation: cvBatchPulse 1.1s ease-in-out infinite;
}
.cv-batch-indeterminate {
  position: absolute;
  inset: 0;
  width: 40%;
  border-radius: 9999px;
  background: var(--cv-brand);
  opacity: 0.85;
  animation: cvBatchIndeterminate 1.15s ease-in-out infinite;
}
.cv-batch-flash {
  animation: cvBatchFlash 0.9s ease-out 1;
}
`;

let injected = false;

/** Inject the batch keyframes once. Safe to call on every mount. */
export function installBatchStyles(): void {
  if (injected || typeof document === 'undefined') return;
  if (document.getElementById(STYLE_ID)) {
    injected = true;
    return;
  }
  const el = document.createElement('style');
  el.id = STYLE_ID;
  el.textContent = CSS;
  document.head.appendChild(el);
  injected = true;
}
