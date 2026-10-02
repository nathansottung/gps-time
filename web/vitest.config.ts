import { defineConfig } from 'vitest/config'
import { fileURLToPath } from 'node:url'

// Unit tests for pure UI logic (no DOM, no network). Run: corepack pnpm run test
export default defineConfig({
  define: { __GTP_UI_VERSION__: JSON.stringify('9.8.7') },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
