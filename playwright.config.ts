import { defineConfig, devices } from '@playwright/test'
import { ports } from './config/ports.mjs'

/**
 * Browser-level checks, in two projects because they need different things.
 *
 * **perf** proves the canvas grid actually paints and stays responsive. It runs
 * against the synthetic harness at `/`, so it needs only Vite — no backend, no
 * emulator, no seed. That is deliberate: the check that the grid renders at all
 * must not be able to fail because Firestore was not running.
 *
 * **e2e** drives the real register, so it needs the emulator, a seeded
 * workspace and the API:
 *
 *     firebase emulators:start --only firestore
 *     npm run seed
 *     npm run dev:api
 *
 * Ports come from `config/ports.json` and honour the `FRAME_PORT_*` overrides,
 * so a second checkout shifted with `FRAME_PORT_OFFSET` works without editing
 * this file.
 */
export default defineConfig({
  testDir: './tools',
  // Serial by default: the perf assertions measure wall-clock, and parallel
  // workers on one machine contend for exactly the resource being measured.
  workers: 1,
  fullyParallel: false,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: `http://localhost:${ports.frontend}`,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'perf',
      testDir: './tools/perf',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'e2e',
      testDir: './tools/e2e',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: `npx vite --port ${ports.frontend} --strictPort`,
    url: `http://localhost:${ports.frontend}`,
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
