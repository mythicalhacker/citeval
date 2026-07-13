/**
 * App — the citeval web shell (W1-FE-SHELL). A masthead with the headline-stat strip, an
 * accessible tab bar across the five views, and the active view panel. The five view bodies are
 * minimal stubs that the W2 view sessions replace; this shell + the design system + the
 * mock-backed api client are the single hand-off. Nothing here needs a backend or a key.
 *
 * Cross-view navigation + selection is exposed to views via ShellContext (`useShell()`), so a W2
 * view session only edits its own views/*.tsx file — never this shared shell.
 */
import { useCallback, useMemo, useRef, useState } from 'react';
import type { ComponentType, KeyboardEvent } from 'react';
import { Masthead } from './components/common';
import { ShellProvider, type ShellApi, type ViewKey } from './shell/ShellContext';
import type { RunResult } from './lib/types';
import RunView from './views/RunView';
import BatchView from './views/BatchView';
import ShowcaseView from './views/ShowcaseView';
import VerdictView from './views/VerdictView';
import MethodologyView from './views/MethodologyView';

interface ViewDef {
  key: ViewKey;
  label: string;
  Component: ComponentType;
}

const VIEWS: ViewDef[] = [
  { key: 'run', label: 'Verify', Component: RunView },
  { key: 'batch', label: 'Batch', Component: BatchView },
  { key: 'showcase', label: 'Showcase', Component: ShowcaseView },
  { key: 'verdict', label: 'Verdict', Component: VerdictView },
  { key: 'methodology', label: 'Methodology', Component: MethodologyView },
];

// The single rendered tabpanel — all tabs point their aria-controls at this stable id.
const PANEL_ID = 'cv-tabpanel';

export default function App() {
  const [active, setActive] = useState(0);
  const [selection, setSelection] = useState<RunResult | null>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const focusTab = useCallback((i: number) => {
    const n = VIEWS.length;
    const idx = ((i % n) + n) % n;
    setActive(idx);
    tabRefs.current[idx]?.focus();
  }, []);

  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
      switch (e.key) {
        case 'ArrowRight':
          e.preventDefault();
          focusTab(i + 1);
          break;
        case 'ArrowLeft':
          e.preventDefault();
          focusTab(i - 1);
          break;
        case 'Home':
          e.preventDefault();
          focusTab(0);
          break;
        case 'End':
          e.preventDefault();
          focusTab(VIEWS.length - 1);
          break;
        default:
          break;
      }
    },
    [focusTab],
  );

  // The navigation + selection seam handed to views via useShell().
  const shell: ShellApi = useMemo(
    () => ({
      activeView: VIEWS[active].key,
      goTo: (view: ViewKey) => {
        const idx = VIEWS.findIndex((v) => v.key === view);
        if (idx >= 0) setActive(idx);
      },
      selection,
      select: (result: RunResult | null) => setSelection(result),
    }),
    [active, selection],
  );

  const Active = VIEWS[active].Component;
  const activeKey = VIEWS[active].key;

  return (
    <ShellProvider value={shell}>
      <div className="min-h-screen bg-page text-ink">
        <Masthead />

        <nav className="border-b border-line bg-surface" aria-label="Views">
          <div role="tablist" aria-label="citeval views" className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-2">
            {VIEWS.map((view, i) => {
              const selected = i === active;
              return (
                <button
                  key={view.key}
                  ref={(el) => {
                    tabRefs.current[i] = el;
                  }}
                  role="tab"
                  id={`tab-${view.key}`}
                  aria-selected={selected}
                  aria-controls={PANEL_ID}
                  tabIndex={selected ? 0 : -1}
                  className="cv-tab"
                  onClick={() => setActive(i)}
                  onKeyDown={(e) => onKeyDown(e, i)}
                >
                  {view.label}
                </button>
              );
            })}
          </div>
        </nav>

        {/* <main> stays the page's main landmark; the tabpanel role lives on the inner element so
            the landmark isn't overridden. */}
        <main className="mx-auto max-w-6xl">
          <div id={PANEL_ID} role="tabpanel" aria-labelledby={`tab-${activeKey}`} tabIndex={0}>
            <Active />
          </div>
        </main>
      </div>
    </ShellProvider>
  );
}
