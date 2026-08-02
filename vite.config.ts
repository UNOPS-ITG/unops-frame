import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 4200,
    // The backend runs on 8000 behind oauth2-proxy in the full local stack.
    // Proxying keeps the browser on one origin so cookies and IAP headers
    // behave the way they do in a deployed environment.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // The public form surface must never pull in the grid: it is unauthenticated,
    // has to work on a poor connection, and PRD 11's licensing analysis assumed
    // the grid stays out of externally-facing bundles. Enforced by a fitness test.
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
    },
  },
})
