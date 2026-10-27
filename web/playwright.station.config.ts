import { defineConfig, devices } from '@playwright/test'

// Opt-in browser checks against a running station's own server (not part of `test:e2e`, not in CI):
// the built UI as the station serves it at /app/, with the station's API, not the client-side demo
// adapter. Start the desktop demo first (scripts/run-demo.ps1, port 8080), or point GTP_STATION_URL
// at a station. Read only: it never sends a POST. Run: corepack pnpm run test:station
export default defineConfig({
  testDir: 'e2e-station',
  fullyParallel: true,
  // the station's HTTP server keeps a short listen queue; many browsers at once get refused connections
  workers: Number(process.env.GTP_STATION_WORKERS || 1),
  reporter: 'list',
  use: {
    baseURL: process.env.GTP_STATION_URL || 'http://127.0.0.1:8080/app/',
    ...devices['Desktop Chrome'],
    reducedMotion: 'reduce',
  },
  projects: [{ name: 'chromium' }],
})
