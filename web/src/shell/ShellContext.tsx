/**
 * ShellContext — the W1-owned navigation + cross-view selection seam.
 *
 * Several views need to hand off to each other: Showcase / Batch pick a RunResult and open the
 * Verdict view; the Run view opens its result in the Verdict view. Rather than have each W2 view
 * session wire that into the shared App.tsx (which would make their drop-in replacements conflict),
 * the shell provides this one stable seam. A view calls `useShell()` and uses `goTo(viewKey)` +
 * `select(result)` — all cross-view plumbing stays inside App.tsx.
 *
 * This is part of the W1-FE-SHELL hand-off contract: the shape here is stable; W2 consumes it.
 */
import { createContext, useContext } from 'react';
import type { ReactNode } from 'react';
import type { RunResult } from '../lib/types';

/** The five view keys, matching the tabs in App.tsx. */
export type ViewKey = 'run' | 'batch' | 'showcase' | 'verdict' | 'methodology';

export interface ShellApi {
  /** The currently-active view. */
  activeView: ViewKey;
  /** Switch the active view (e.g. `goTo('verdict')`). */
  goTo(view: ViewKey): void;
  /** A RunResult handed between views — e.g. Showcase/Batch → Verdict. `null` when nothing picked. */
  selection: RunResult | null;
  /** Set (or clear) the handed-off RunResult. Typically paired with `goTo('verdict')`. */
  select(result: RunResult | null): void;
}

const ShellContext = createContext<ShellApi | null>(null);

export function ShellProvider({ value, children }: { value: ShellApi; children: ReactNode }) {
  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>;
}

/** Access the shell navigation + selection seam. Must be called from within the App shell. */
export function useShell(): ShellApi {
  const ctx = useContext(ShellContext);
  if (!ctx) throw new Error('useShell must be used within the App shell (ShellProvider).');
  return ctx;
}
