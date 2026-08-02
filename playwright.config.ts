import { defineConfig, devices } from '@playwright/test'
import { ports } from './config/ports.mjs'

/**
 * Browser-level checks. Two suites live here and they answer different
 * questions: `tools/perf` proves the canvas grid actually paints and stays
 * responsive, which no jsdom test can; `tools/e2e` will hold journeys once
 * there are journeys.
 *
 * The web server is started by the config rather than assumed, so `npm run
 * perf` works from a clean checkout and a developer never debugs a connection
 * refused that means "you forgot to start vite".
 */
export default defineConfig({
  testDir: './tools',
  testMatch: /.*\.spec\.ts/,
  // Serial by default: the perf assertions measure wall-clock, and parallel
  // workers on one machine contend for exactly the resource being measured.
  workers: 1,
  fullyParallel: false,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: `http://localhost:${ports.frontend}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npx vite --port ${ports.frontend} --strictPort`,
    url: `http://localhost:${ports.frontend}`,
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
