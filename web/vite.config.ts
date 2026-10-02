import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'

// Standalone Vite config for the GPS Time web UI (served by the Pi).
// No Figma Make plugins, no site.json, no analytics or other external calls:
// the built app must work with no Internet connection.
//
// Dev/preview servers bind to loopback by default. Set GTP_WEB_HOST
// (e.g. 0.0.0.0) only to deliberately expose a dev server on the LAN.
const host = process.env.GTP_WEB_HOST || '127.0.0.1'
const port = parseInt(process.env.PORT || '5173', 10)
// Dev only: forward /api to a station or the Python demo (scripts/run-demo.ps1).
// Loopback by default; the built app is served by the station itself at /app/.
const apiTarget = process.env.GTP_API_TARGET || 'http://127.0.0.1:8080'

// UI version, read from the git tag at build time (same rule as gps_time_pi/version.py):
// GTP_VERSION overrides; otherwise `git describe`; 'unknown' without a reachable v* tag.
function uiVersion(): string {
  if (process.env.GTP_VERSION) return process.env.GTP_VERSION.replace(/^v(?=\d)/, '')
  try {
    const out = execFileSync('git', ['describe', '--tags', '--match', 'v[0-9]*', '--dirty'],
      { cwd: fileURLToPath(new URL('.', import.meta.url)), encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] })
    return out.trim().replace(/^v(?=\d)/, '') || 'unknown'
  } catch {
    return 'unknown'
  }
}

export default defineConfig(({ mode }) => ({
  base: './',
  define: { __GTP_UI_VERSION__: JSON.stringify(uiVersion()) },
  build: {
    sourcemap: mode === 'development' ? 'inline' : false,
  },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: { host, port, strictPort: true, proxy: { '/api': { target: apiTarget, changeOrigin: false } } },
  preview: { host, port },
}))
