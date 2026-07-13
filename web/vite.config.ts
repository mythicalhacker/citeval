import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The web app is mock-backed by default (VITE_USE_MOCK=true), so `dev` and `build` need no
// backend. When VITE_USE_MOCK=false the api client hits the FastAPI server (server/citeval_api,
// Wave 2) through this dev proxy. Point it elsewhere by editing the target below.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Only exercised when VITE_USE_MOCK=false; harmless (no requests) in the default mock mode.
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
