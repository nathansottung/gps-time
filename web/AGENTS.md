# GPS Time web UI

React 19 + Vite 8 + Tailwind CSS v4 + TypeScript. Originally generated in Figma Make; this copy builds standalone and is being ported to become the Raspberry Pi station UI.

**All UI work must follow [`guidelines/Guidelines.md`](guidelines/Guidelines.md) exactly.** Repository-wide rules live in [`../docs/README.md`](../docs/README.md).

## Commands

Toolchain is pinned in `.mise.toml` (Node 22) and `package.json` `packageManager` (pnpm). With corepack:

```sh
corepack pnpm install --frozen-lockfile   # install-time network only
corepack pnpm run dev                     # http://127.0.0.1:5173 (loopback only)
corepack pnpm run typecheck
corepack pnpm run test                    # Vitest: src/**/*.test.ts (Node environment, no DOM)
corepack pnpm run build                   # output: dist/
```

The dev server is not started for you. It binds to 127.0.0.1 by default; set `GTP_WEB_HOST=0.0.0.0` only to deliberately expose it on a LAN. `PORT` overrides the port. It proxies `/api` to `GTP_API_TARGET` (default `http://127.0.0.1:8080`, the desktop demo from `scripts/run-demo.ps1`). Open `http://127.0.0.1:5173/?source=demo` to use the client-side demo adapter with no backend.

The built app is served by the station at `/app/` (`gps_time_pi/server.py`, ADR-0004).

## Offline-first

The built app must make no network requests to third parties at runtime: no CDNs, web fonts, analytics or external scripts. Fonts are bundled from `@fontsource` (weights 300–600; 700 is not shipped).

## Project structure

- `src/main.tsx` — React entrypoint; imports `src/index.css` and mounts `src/App.tsx`
- `src/App.tsx` — app shell (header, sidebar, page routing)
- `src/pages/` — one component per page
- `src/components/ui.tsx` — design-system components (Card, MetricRow, StatusBadge, ProvenanceTag, MaturityBadge, DemoBanner, …)
- `src/components/charts.tsx` — Recharts/SVG chart components
- `src/lib/units.ts` — scientific formatting helpers (e.g. `fmtSci` for Δf/f as ×10⁻ⁿ)
- `src/api/types.ts` — types for the station HTTP API (reference: `../docs/api/`)
- `src/api/client.ts` — `StationApi` interface, `httpApi()` client, `/api/ping` clock estimate
- `src/api/demo.ts` — demo adapter: synthetic payloads in the API's shapes (always shown with the demo banner)
- `src/api/previews.ts` — synthetic previews for features with no endpoint yet; rendered only through `<Planned>` with demo data
- `src/api/station.tsx` — data-source selection (`?source=demo|live`, `VITE_GTP_SOURCE`), `StationProvider`, polling hooks
- `src/api/view.ts` — maps API payloads onto component shapes (no invented values)
- `src/components/planned.tsx` — `<Planned>` (preview under demo, "not available" live) and `ApiErrorNote`
- `src/index.css` — font imports, Tailwind import, design tokens and utility classes
- `vite.config.ts` — standalone Vite config (React, Tailwind, `@` alias for `src`); defines `__GTP_UI_VERSION__` from `git describe` at build time (`GTP_VERSION` overrides)
- `vitest.config.ts` — unit tests for pure logic (`src/**/*.test.ts`); keep logic that needs tests out of components (e.g. `src/lib/banner.ts`)
- `src/lib/banner.ts` — banner guards: never a bare SYNCHRONIZED; GPS/PPS with a non-PPS selected source shows UNKNOWN (tested in `banner.test.ts`)
- `src/lib/version.ts` — `UI_VERSION` (build-time tag) and `versionLine()` for the footer: one version when UI and station match, both when they differ, "unknown" rather than a guess (tested in `version.test.ts`)
- `src/lib/stability.ts` — Stability tab logic: chart rows, confidence-bar distances, decade ticks, ×10⁻ⁿ and TDEV labels (tested in `stability.test.ts`); the panel is `src/components/stability.tsx`
- `src/lib/oscillator.ts` — Oscillator tab logic: chart points, PPS-only scatter, fit line, slope and size labels (tested in `oscillator.test.ts`); the panel is `src/components/oscillator.tsx`
- `src/lib/shadow.ts` — Earth Shadow and Satellites tabs: sky-map segments and SVG paths, click-to-direction, shadow-state labels, element-age labels (tested in `shadow.test.ts`); the panels are in `src/components/shadow.tsx`
- `src/lib/ntpservice.ts` — NTP service card labels and rates (Network page, `/api/ntp-service`), and `nmeaCompare()` for the configured/suggested NMEA offsets shown side by side on the PPS page (tested in `ntpservice.test.ts`)
- `src/lib/references.ts` — References tab logic: verdict and comparison variants (a disagreement is a warning, never an error), signed offsets, history series (tested in `references.test.ts`); the panel is `src/components/references.tsx`
- `src/lib/timescales.ts` — Time Scales tab logic: TAI, GPS time/week/seconds of week, MJD/JD from a station instant and the station's TAI − UTC (never an assumed offset), leap-table labels (tested in `timescales.test.ts`); the panel is `src/components/timescales.tsx`
- `src/lib/localtime.ts` — main-clock local time: zone choice (station override, zone from station position, else the browser's), offset, DST, UTC and Unix epoch, and the 12/24-hour preference in `localStorage` (tested in `localtime.test.ts`)
- `src/components/clock.tsx` — the big Overview clock and the header clock: station time (`useStationTime`), local zone, UTC beneath; `clockDiscipline()` in `lib/banner.ts` decides whether it may say GPS/PPS
- `src/api/auth.ts` — admin token store (sessionStorage, guarded; never in the URL) used for state-changing requests (tested in `auth.test.ts`)

## Data and labeling

Every value carries one of six provenance labels: observed, calculated, modeled, predicted, inferred, external. Use UNKNOWN rather than guessing when origin or state can't be established. Demo data must never look like real measurements: no fallback from a failed live request to demo data, and preview content only inside `<Planned>` or behind an explicit `isDemo` check. `null` from the API means UNKNOWN (`MetricRow` renders it). Demo location is the US Naval Observatory (38.9217, −77.0669); never commit a real station's coordinates.
