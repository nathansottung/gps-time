import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath } from 'node:url'

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

export default defineConfig(({ mode }) => ({
  base: './',
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
