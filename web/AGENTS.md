# GPS Time web UI

React 19 + Vite 8 + Tailwind CSS v4 + TypeScript. Originally generated in Figma Make; this copy builds standalone and is the Raspberry Pi station UI (the legacy server-rendered pages were removed after v1.4.0).

**All UI work must follow [`guidelines/Guidelines.md`](guidelines/Guidelines.md) exactly.** Repository-wide rules live in [`../docs/README.md`](../docs/README.md).

## Commands

Toolchain is pinned in `.mise.toml` (Node 22) and `package.json` `packageManager` (pnpm). With corepack:

```sh
corepack pnpm install --frozen-lockfile   # install-time network only
corepack pnpm run dev                     # http://127.0.0.1:5173 (loopback only)
corepack pnpm run typecheck
corepack pnpm run test                    # Vitest: src/**/*.test.ts (Node environment, no DOM)
corepack pnpm run build                   # output: dist/
corepack pnpm exec playwright install chromium   # once: the browser for the e2e tests
corepack pnpm run test:e2e                # Playwright (e2e/*.spec.ts) against `vite preview` of dist/, demo data
corepack pnpm run test:station            # opt-in: e2e-station/ against a running station (default: the desktop demo on :8080; GTP_STATION_URL)
```

The dev server is not started for you. It binds to 127.0.0.1 by default; set `GTP_WEB_HOST=0.0.0.0` only to deliberately expose it on a LAN. `PORT` overrides the port. It proxies `/api` to `GTP_API_TARGET` (default `http://127.0.0.1:8080`, the desktop demo from `scripts/run-demo.ps1`). Open `http://127.0.0.1:5173/?source=demo` to use the client-side demo adapter with no backend.

The built app is served by the station at `/app/` (`gps_time_pi/server.py`, ADR-0004); `/` and the retired legacy page paths redirect there with a 302.

## Offline-first

The built app must make no network requests to third parties at runtime: no CDNs, web fonts, analytics or external scripts. Fonts are bundled from `@fontsource` (weights 300–600; 700 is not shipped).

## Project structure

- `src/main.tsx` — React entrypoint; imports `src/index.css` and mounts `src/App.tsx`
- `src/App.tsx` — app shell (header, sidebar, page routing)
- `src/pages/` — one component per page
- `src/components/ui.tsx` — design-system components (Card, MetricRow, StatusBadge, ProvenanceTag, MaturityBadge, DemoBanner, …); `Loading`, `LoadingNote`, `EmptyNote` and `<Card pending>` for loading and empty states (Guidelines → Loading, empty and unknown)
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
- `src/lib/oscillator.ts` — Oscillator tab logic: chart points, PPS-only scatter, fit line, slope and size labels, the fitted profile (`profileAt`, `profileCurve` over the covered temperatures only, `fmtTerm` as Δf/f ×10⁻ⁿ with ppm in brackets), the holdover table (`holdoverTimes`, `fmtHoldTime`, `fmtThreshold`, `holdoverRows`), date ticks for the time charts (`dayTicks`), and the profile file (`bindingFor`, `demoImport`, `importOutcome`, `exportFilename`) (tested in `oscillator.test.ts`); the panel is `src/components/oscillator.tsx`, which also exports `HoldoverPanel` for Timing → Overview
- `src/lib/shadow.ts` — Earth Shadow and Satellites tabs: sky-map segments and SVG paths, click-to-direction, shadow-state labels, element-age labels (tested in `shadow.test.ts`); the panels are in `src/components/shadow.tsx`
- `src/lib/ntpservice.ts` — NTP service card labels and rates (Network page, `/api/ntp-service`), and `nmeaCompare()` for the configured/suggested NMEA offsets shown side by side on the PPS page (tested in `ntpservice.test.ts`)
- `src/lib/references.ts` — References tab logic: verdict and comparison variants (a disagreement is a warning, never an error), signed offsets, history series (tested in `references.test.ts`); the panel is `src/components/references.tsx`
- `src/lib/timescales.ts` — Time Scales tab logic: TAI, GPS time/week/seconds of week, MJD/JD from a station instant and the station's TAI − UTC (never an assumed offset), leap-table labels (tested in `timescales.test.ts`); the panel is `src/components/timescales.tsx`
- `src/lib/localtime.ts` — main-clock local time: zone choice (station override, zone from station position, else the browser's), offset, DST, UTC and Unix epoch, and the 12/24-hour preference in `localStorage` (tested in `localtime.test.ts`)
- `src/lib/screenshot.ts` — screenshot mode: per-browser setting in `localStorage` (guarded), the Alt+Shift+S shortcut, `maskText()` (digits → 0, letters → x; the real value is never drawn) (tested in `screenshot.test.ts`); `src/components/screenshot.tsx` has the header toggle and `<Sensitive>`, and `MetricRow` takes `sensitive`
- `src/components/clock.tsx` — the big Overview clock and the header clock: station time (`useStationTime`), local zone, UTC beneath; `clockDiscipline()` in `lib/banner.ts` decides whether it may say GPS/PPS
- `src/lib/admin.ts` — Administration → Station actions: one entry per `/api/admin` action (label, effect, confirmation text; everything but the log flush asks first) and `actionOutcome()`, the line shown afterwards (the station's answer; no answer may still mean it ran) (tested in `admin.test.ts`)
- `src/lib/modules.ts` — Administration → Experimental modules (`/api/modules`, `POST /api/setting`): row status from what the supervisor reports (UNKNOWN when it doesn't), which toggles may be used, permission and outcome lines, the station's switch rules for the demo adapter, and a module's latest output (`fmtModuleValue`, `outputLines`, `outputHeading`; the rows under each module) (tested in `modules.test.ts`; the card in a browser: `e2e/modules.spec.ts`). `Toggle` takes `disabled`
- `src/lib/survey.ts` — Administration → Position survey: the typed confirmation (`RESET`), what a reset would discard from the station's counts (UNKNOWN when not reported), and the outcome line (tested in `survey.test.ts`)
- `src/lib/almanac.ts` — Sun & Moon tab: date navigation within the ephemeris range (calendar arithmetic at noon UTC), the 24 h day bar and the night bar laid out from `/api/almanac` (`sun.bar`, `night`) without computing any astronomy, times that fall on another day labeled with it (tested in `almanac.test.ts`); the cards are `src/components/almanac.tsx`; sky colors are the `--sky-*` tokens
- `src/lib/sky.ts` — Sky & Objects tab: sky-map layout from `/api/almanac` → `sky` (stars by magnitude, constellation lines split at the horizon, bodies, target or "below"; projection from `lib/shadow.ts`), the `at=` value, and the object card's rows in the legacy order (tested in `sky.test.ts`); the cards are `src/components/sky.tsx`. `api.object()` returns `{error: 'unparsed'}` instead of throwing (tested in `src/api/object.test.ts`)
- `src/lib/survey.ts` also lays out GNSS & Site → Survey: the convergence series (log axis; zero or missing values are gaps), the session bullseye (north up, east right, 3σ fills the plot), rejected-fix rows and small-metre formatting (tested in `survey.test.ts`); the cards are `src/components/survey.tsx`
- `src/lib/prefs.ts` — per-browser display preferences: the theme (dark or red night; `gtp-theme`; `?theme=`) and the shown modules (`gtp-modules`: hidden pages and Overview cards, sanitized so Overview, Configure and Administration can't be hidden) (tested in `prefs.test.ts`); `src/components/prefs.tsx` has the stores, the header Night toggle and the night overlay; Configure is the modules page
- `src/lib/throttle.ts` — Administration → Power: the station's decoded get_throttled flags as one row per condition (now, since boot), and whether under-voltage occurred (tested in `throttle.test.ts`)
- `src/lib/offset.ts` — Timing → offset history: symmetric-log axis (linear within ±1 µs), rows from `/api/history` with the ± offset-SD band only where chrony reported it and the ± max-error bound, domain and decade ticks (tested in `offset.test.ts`); the chart is `OffsetHistoryChart` in `src/components/charts.tsx`
- `src/lib/timeaxis.ts` — value axes for time-offset and stability charts: `fmtTime` (ns/µs/ms/s per tick), `fmtDurationTick` (log duration axes), nice linear ticks, the symmetric-log zone chosen from the data, log decades (tested in `timeaxis.test.ts`); `ScaleToggle` and `TimeSeriesChart` are in `src/components/charts.tsx`, the remembered scale per chart in `src/lib/prefs.ts` (`gtp-chart-scales`) and `useChartScale` in `src/components/prefs.tsx`
- `src/lib/route.ts` — the page in the URL hash (`#timing`, `#admin`): reloads, bookmarks and Back keep it (tested in `route.test.ts`)
- `e2e-station/` — opt-in browser checks against a station's own server (`playwright.station.config.ts`, `test:station`; not in CI): layout at 360–1920 px, design at 1280 px, no console errors, screenshot mode never shows the demo position, night-theme layout, full-height screenshots to `test-results/station-shots` for a look by eye. Read only. Used for `../docs/dashboard/ui-review-2026-10-27.md`
- `e2e/` — browser tests (Playwright, Chromium): `responsive.spec.ts` audits every page and tab at 360–1920 px and half-screen widths with `layout-audit.ts` (sideways scroll, past the right edge, clipped text, text over text); `navigation.spec.ts` covers the drawer below 1024 px and hash navigation; `design.spec.ts` runs `design-audit.ts` on every page and tab (contrast WCAG AA, type scale, weights, tabular figures), tabs through every page for a visible focus ring, and checks that values show loading (not UNKNOWN) before the station answers; `scale.spec.ts` switches every linear/log toggle, checks the tick labels carry ns/µs/ms/s (×10⁻ⁿ for ADEV/MDEV), and that the choice survives a reload. Layout rules: Guidelines → Layout → Narrow screens
- `src/api/auth.ts` — admin token store (sessionStorage, guarded; never in the URL) used for state-changing requests (tested in `auth.test.ts`)

## Data and labeling

Every value carries one of six provenance labels: observed, calculated, modeled, predicted, inferred, external. Use UNKNOWN rather than guessing when origin or state can't be established. Demo data must never look like real measurements: no fallback from a failed live request to demo data, and preview content only inside `<Planned>` or behind an explicit `isDemo` check. `null` from the API means UNKNOWN (`MetricRow` renders it). Demo location is the US Naval Observatory (38.9217, −77.0669); never commit a real station's coordinates.
