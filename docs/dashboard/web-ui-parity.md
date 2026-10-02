# New web UI (/app/) vs legacy dashboard: parity

The legacy pages stay until every row below is either done or explicitly dropped by the owner (ADR-0004). Status as of feat/web-dashboard, 2026-10-01.

## Legacy features the new UI lacks

| # | Feature (legacy location) | Notes |
|---|---|---|
| 1 | **Theme switching:** Light / Dark / Night (red-on-black), `?theme=`, remembered in `gtp-theme` (all pages) | The new UI is dark only. Night mode matters for observing. |
| 2 | **Time-zone picker** remembered in `gtp-tz` (all pages) | The new UI always uses the browser's zone. |
| 3 | **Station-corrected clock:** the big clock ticks on the server time estimated from `/api` `epoch_ms` + RTT (`/legacy`) | The new header shows the browser clock. The browser-offset estimate exists (Network page) but does not drive the clock yet. |
| 4 | **Layout editor that saves** to the station: pages, per-widget visible/size, add/rename/remove page, save, restore defaults, export/import JSON (`/configure`, `POST /api/dashboard`) | The new Configure page is a non-saving preview with a different widget model. The client already has `dashboard()`, `saveDashboard()` and `resetDashboard()`. |
| 5 | **Layout-driven pages:** `/` renders whatever `/api/dashboard` says | New pages have a fixed layout. |
| 6 | **Admin actions:** flush logs, restart gpsd/chrony/web, reboot (`/admin`, `/api/admin`) | Deferred until the API has authentication (independent review, admin security). |
| 7 | **Survey reset** (`/admin`, `/api/setting?reset_site=1`) | Destructive; same reason as #6. |
| 8 | **Almanac date navigation:** date picker with ←/→, "Sky at" time, Now (`/almanac`) | The new UI shows today only. |
| 9 | **Twilight bar** (24 h) and **night bar:** twilight stages, moon-up strip, moonless-dark windows, total moonless astronomical darkness (`/almanac`) | Data is already in `/api/almanac` → `sun.bar`, `night`. |
| 10 | **Moon details:** time above horizon, transit altitude (`/almanac`) | Data in `moon.up_s`, `moon.transit_alt`. |
| 11 | **Sky map:** stars by magnitude, constellation lines, Sun/Moon/planets, target reticle (`/almanac`) | Data in `/api/almanac` → `sky`. |
| 12 | **Object lookup:** M-numbers, star names, planets, RA/Dec; rise/transit/set, dark and moonless windows (`/almanac`, `/api/object`) | Not in the client yet. Note that `/api/object` sets a server-global target shared by all clients. |
| 13 | **Offset chart uncertainty band** and symlog axis (linear within ±1 µs) (`/history`) | The new chart plots the offset only (`err_s` is unused) on a linear axis with automatic ns/µs/ms units. |
| 14 | **Survey convergence:** log-scale ± over time, bullseye scatter of session fixes with scatter/SE rings (`/history`, `/api/survey`) | The new UI shows the current survey statistics only. |
| 15 | **Survey ingest counters:** accepted, rejected by reason, collector running (`/api/survey` → `ingest`) | Not shown. |
| 16 | **chrony detail:** residual frequency, skew, update interval, PPS age (`lastrx` of the PPS source), raw `sourcestats` (`/legacy`) | Partly covered by the Timing Chain tab and the Network sources table. |
| 17 | **Satellite table TDOP column and SNR bars per row** (`/legacy`) | Covered by the GNSS page, except the TDOP column. |
| 18 | **`custom.css` site override** (all legacy pages link `/static/custom.css`) | The new UI does not load it. |
| 19 | **Time-zone table** (`/zones`) | No link or equivalent in the new UI (the route still works). |
| 20 | **"Projected 1 s holdover" = 1 / \|ppm\|** (`/` timing_quality widget) | Deliberately not ported. It extrapolates from a single frequency value. The new UI's holdover panel is `Planned` until there is a validated model. |
| 21 | **Throttle flags shown individually** (`/admin`) | The new Admin page lists active flags only. |

## New UI features the legacy pages lack

- Timing-chain stages, inferred classification, PPS event log with boundary and confidence (`/api/timing-chain`); diagnostic snapshot with copy (`/api/diagnostics`). Neither endpoint had a UI before.
- Source-aware banner on every page; timing-chain card on the Overview page; PPS Diagnostics page with the 12 acceptance questions, device, live PPS, chrony refclock, outage history, raw output and COPY/DOWNLOAD snapshot (feat/pps-ui).
- Browser connection statistics: RTT current/min/median/p95, jitter.
- chrony sources table with selection state on the Network page.
- Explicit UNKNOWN for every value the station cannot establish, and stale sky data hidden instead of shown as current counts.

## Not parity items (unchanged routes)

`/time`, `/api/*`, `/static/*` keep working regardless of which UI is used.
