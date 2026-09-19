import { fileURLToPath } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Tailwind is handled by its Vite plugin; do not inherit unrelated configs
  // from a developer's parent directories.
  css: { postcss: { plugins: [] } },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // Every request uses a relative /api/... path, so it is same-origin in
    // dev (via this proxy) and in
    // production (via a host-level rewrite). CORS therefore never applies.
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
