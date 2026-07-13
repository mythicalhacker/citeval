/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  // Theme signal is the system preference; the design tokens (src/design/tokens.ts) also emit a
  // `prefers-color-scheme: dark` block, so utilities and tokens stay in lockstep.
  darkMode: 'media',
  theme: {
    extend: {
      // Surface / brand tokens are driven by the CSS custom properties injected from tokens.ts,
      // so Tailwind utilities (bg-surface, text-ink, …) and inline token styles share one source.
      colors: {
        page: 'var(--cv-bg)',
        surface: 'var(--cv-surface)',
        'surface-2': 'var(--cv-surface-2)',
        line: 'var(--cv-border)',
        ink: 'var(--cv-text)',
        'ink-muted': 'var(--cv-text-muted)',
        brand: 'var(--cv-brand)',
        'brand-contrast': 'var(--cv-brand-contrast)',
      },
      fontFamily: {
        sans: [
          '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Helvetica',
          'Arial', 'sans-serif',
        ],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      borderRadius: {
        card: '0.625rem',
      },
    },
  },
  plugins: [],
};
