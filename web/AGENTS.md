# GPS Time web UI

React 19 + Vite 8 + Tailwind CSS v4 + TypeScript. Originally generated in Figma Make; this copy builds standalone and is being ported to become the Raspberry Pi station UI.

**All UI work must follow [`guidelines/Guidelines.md`](guidelines/Guidelines.md) exactly.** Repository-wide rules live in [`../docs/README.md`](../docs/README.md).

## Commands

Toolchain is pinned in `.mise.toml` (Node 22) and `package.json` `packageManager` (pnpm). With corepack:

```sh
corepack pnpm install --frozen-lockfile   # install-time network only
corepack pnpm run dev                     # http://127.0.0.1:5173 (loopback only)
corepack pnpm run typecheck
corepack pnpm run build                   # output: dist/
```

The dev server is not started for you. It binds to 127.0.0.1 by default; set `GTP_WEB_HOST=0.0.0.0` only to deliberately expose it on a LAN. `PORT` overrides the port.

## Offline-first

The built app must make no network requests to third parties at runtime: no CDNs, web fonts, analytics or external scripts. Fonts are bundled from `@fontsource` (weights 300–600; 700 is not shipped).

## Project structure

- `src/main.tsx` — React entrypoint; imports `src/index.css` and mounts `src/App.tsx`
- `src/App.tsx` — app shell (header, sidebar, page routing)
- `src/pages/` — one component per page
- `src/components/ui.tsx` — design-system components (Card, MetricRow, StatusBadge, ProvenanceTag, MaturityBadge, DemoBanner, …)
- `src/components/charts.tsx` — Recharts/SVG chart components
- `src/lib/units.ts` — scientific formatting helpers (e.g. `fmtSci` for Δf/f as ×10⁻ⁿ)
- `src/data/demo.ts` — synthetic demo data (must always be shown with the demo banner)
- `src/index.css` — font imports, Tailwind import, design tokens and utility classes
- `vite.config.ts` — standalone Vite config (React, Tailwind, `@` alias for `src`)

## Data and labeling

Every value carries one of six provenance labels: observed, calculated, modeled, predicted, inferred, external. Use UNKNOWN rather than guessing when origin or state can't be established. Demo data must never look like real measurements. Demo location is the US Naval Observatory (38.9217, −77.0669); never commit a real station's coordinates.
