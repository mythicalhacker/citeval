/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** When `'false'`, the api client hits the real FastAPI backend; anything else (incl. unset)
   *  keeps the app mock-backed. See `src/lib/api.ts`. */
  readonly VITE_USE_MOCK?: string;
  /** Base path for REST + SSE routes. Defaults to `/api` (proxied to the backend in dev). */
  readonly VITE_API_BASE?: string;
  /** Optional mock wall-clock compression factor (default 12; `Infinity` fires synchronously). */
  readonly VITE_MOCK_SPEED?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
