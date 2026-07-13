# citeval web (`web/`) — frontend shell

**Owner of this hand-off: W1-FE-SHELL.** This is the Vite + React + TypeScript + Tailwind shell for
the citeval web app. It is **mock-backed by default**, so the whole UI installs, builds, runs, and
demos with **no backend and no API key**.

```bash
cd web
npm install
npm run dev        # http://localhost:5173 — the shell, five tabs, fully mock-backed
npm run build      # tsc --noEmit && vite build  (the DoD gate)
npm run typecheck  # tsc --noEmit
```

## What W1-FE-SHELL delivered (the single hand-off)

1. **The scaffold** — Vite/React/TS/Tailwind, strict tsconfig, `npm run build` green.
2. **`src/lib/api.ts`** — the ONE client every view uses (details below).
3. **The design system** — `src/components/common/*`, driven by `src/design/tokens.ts`.
4. **Five view stubs** — `src/views/*`, mounted by `src/App.tsx` as accessible tabs.

The W0 contract files (`src/lib/{types,mockServer,fixtures}.ts`) are **frozen** — do not edit them
here; a change is a manager decision (see `docs/api_contract.md` §Change control).

## For the W2 view sessions

- **Replace the body of your one view file** in `src/views/`. The stubs are intentionally sequential
  and independent — replacing one never conflicts with another. Keep the `export default` component.
- **`src/components/common/*` is additive-only.** Import primitives from `./components/common`; add
  new ones if needed, but do not break the existing public props (they are part of this contract).
- **Never branch on the transport.** Call `api.*` and render the result; the client already handles
  mock vs. live. Pass `{ speed }` on subscriptions to control the mock demo wall-clock.
- **Cross-view navigation goes through `useShell()`** (`src/shell/ShellContext.tsx`), never through
  `App.tsx`. To open a result in the Verdict view: `const { goTo, select } = useShell(); select(result); goTo('verdict')`.
  The Verdict view reads `useShell().selection`. This keeps every W2 change inside one `views/*.tsx`
  file, so drop-in replacements never conflict on the shared shell.
- **`src/views/StubView.tsx`** is a shared placeholder imported by the *still-stubbed* views. Leave it
  in place until the last stub is replaced — do not delete it as "unused" while other stubs rely on it.

## The api client (`src/lib/api.ts`)

One backend-agnostic surface over the frozen W0 contract (`docs/api_contract.md`). Identical return
shapes on both paths.

| Method | Contract route |
|---|---|
| `api.createRun(req)` → `RunCreated` | POST `/api/runs` |
| `api.subscribeRun(id, onEvent, {speed?})` → `RunStream` | GET `/api/runs/{id}/events` (SSE) |
| `api.getRun(id)` → `RunResult` | GET `/api/runs/{id}` |
| `api.startRun(req, onEvent, {speed?})` | POST + subscribe (convenience) |
| `api.createBatch` / `api.subscribeBatch` / `api.getBatch` / `api.startBatch` | batch equivalents |
| `api.getPricing()` / `api.getHealth()` / `api.getShowcase()` | GET `/api/{pricing,health,showcase}` |

A `RunStream` / `BatchStream` is `{ cancel(): void; done: Promise<Result> }`. `onEvent` receives a
typed `SSEFrame` (`{ event, data }`); switch on `frame.event`.

### Environment

| Var | Default | Meaning |
|---|---|---|
| `VITE_USE_MOCK` | *(unset → mock)* | Anything but `'false'` keeps the app mock-backed. Set `false` to hit the real backend. |
| `VITE_API_BASE` | `/api` | REST + SSE base path (dev-proxied to the backend in `vite.config.ts`). |
| `VITE_MOCK_SPEED` | `12` | Mock wall-clock compression; `Infinity` fires synchronously. |

## The design system (`src/components/common/`)

Import from the barrel: `import { Stepper, GateBadge, AxisScale, ... } from './components/common'`.

| Primitive | Purpose |
|---|---|
| `Masthead` (+ `HEADLINE_STATS`) | Banner + headline-stat strip (κ, retraction P/R, scope recall, ECE). |
| `Stat` | Tabular-nums headline figure + caption. |
| `Stepper` | Five-stage pipeline rail; drive `current` from `stage_start`/`stage_end`. |
| `CostChip` | USD + token/call detail (tabular-nums). |
| `ConfidenceChip` / `ConfidenceGauge` | Confidence tier + self-consistency agreement (abstain-aware). |
| `GateBadge` (+ `gateFiredFromOverall`) | Retraction/scope gate with padlock. |
| `DebateCard` | One `debate_round`: supporter/refuter stances + critic grade + agreement. |
| `ProvenanceBadge` | metadata/text/model/stub/composite — 1:1 with `reporting.py`. |
| `AxisScale` (+ `GradeBadge`) | The graded RB1 6-colour ramp + off-scale (abstention / non-substantiating). |

### Colour language (`src/design/tokens.ts`)

The **single source of colour truth**. The **provenance** palette is verbatim from
`src/citeval/reporting.py` (a badge here matches the embedded `report_html`); the graded **RB1
ramp**, **off-scale**, **gate**, **confidence**, **step**, and **surface** tokens extend it. Every
token has a light and a dark value; `installThemeVars()` (called in `main.tsx` before first paint)
emits them as CSS custom properties under `:root` + a `prefers-color-scheme: dark` block, so
theming is handled by the cascade with no drift and no flash. Components read `var(--cv-…)` via the
`*Style()` helpers — never hard-code hex.

## The five views (`src/views/`)

`run` (Verify) · `batch` · `showcase` · `verdict` · `methodology`. Each is a minimal stub that
documents, in-file, the api methods and primitives its W2 implementation will use. `App.tsx` mounts
them as an ARIA tablist (roving tabindex, arrow/Home/End keys).

## Accessibility

Tabs follow the ARIA tablist pattern; every interactive element gets a single consistent
focus-visible ring; badges/chips/gauges carry `aria-label`s; the gauge is a `role="meter"`; motion
respects `prefers-reduced-motion`.
