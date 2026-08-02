import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
// Ports come from config/ports.json (env-overridable) rather than literals, so
// Frame never collides with the sibling projects that own the estate defaults.
import { ports } from './config/ports.mjs'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: ports.frontend,
    // Fail rather than silently sliding to the next free port: a tool that
    // then talks to whatever else is listening is worse than a clear error.
    strictPort: true,
    proxy: {
      // Same-origin so cookies and IAP headers behave as they do deployed.
      '/api': {
        target: `http://localhost:${ports.backend}`,
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: ports.frontend,
    strictPort: true,
  },
  build: {
    // The public form surface must never pull in the grid: it is
    // unauthenticated, has to work on a poor connection, and PRD 11's licensing
    // analysis assumed the grid stays out of externally-facing bundles.
    // Enforced by a fitness test once that entry point exists.
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
    },
  },
})
