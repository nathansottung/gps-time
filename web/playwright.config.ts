import { defineConfig, devices } from '@playwright/test'

// Browser tests of the built UI (e2e/*.spec.ts), run against `vite preview` with the
// client-side demo adapter (?source=demo): no station, no network beyond loopback.
// Run: corepack pnpm run build && corepack pnpm run test:e2e
const port = 4173

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: true,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${port}/`,
    ...devices['Desktop Chrome'],
    // Fixed clock-independent rendering is not needed: the audit checks layout, not values.
    reducedMotion: 'reduce',
  },
  projects: [{ name: 'chromium' }],
  webServer: {
    command: `corepack pnpm exec vite preview --host 127.0.0.1 --port ${port} --strictPort`,
    url: `http://127.0.0.1:${port}/`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
})
