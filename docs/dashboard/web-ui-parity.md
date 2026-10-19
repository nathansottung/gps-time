# New web UI (/app/) vs legacy dashboard: parity

The legacy pages stay until every row below is either done or explicitly dropped by the owner (ADR-0004). Status as of feat/web-dashboard, 2026-10-01.

A re-check of every row against the code on 2026-10-05, and the proposed order for retiring the legacy pages, is in [`legacy-removal-plan.md`](legacy-removal-plan.md). In short: #3 and #17 are done, #2, #16 and #21 are partly covered, the rest are open, and #6 and #7 (admin actions, survey reset) block removal.

## Legacy features the new UI lacks

| # | Feature (legacy location) | Notes |
|---|---|---|
| 1 | **Theme switching:** Light / Dark / Night (red-on-black), `?theme=`, remembered in `gtp-theme` (all pages) | **Done** (#90), as decided 2026-10-19: dark and the red night theme (header "Night", Configure → Theme, `?theme=night`); light dropped. Night is a multiplied red overlay, so only red light leaves the screen. Shares `gtp-theme` with the legacy pages. |
| 2 | **Time-zone picker** remembered in `gtp-tz` (all pages) | **Dropped 2026-10-19** (owner): the station-wide time-zone override in Administration covers it. `gtp-tz` goes with the legacy pages. |
| 3 | **Station-corrected clock:** the big clock ticks on the server time estimated from `/api` `epoch_ms` + RTT (`/legacy`) | The new header shows the browser clock. The browser-offset estimate exists (Network page) but does not drive the clock yet. |
| 4 | **Layout editor that saves** to the station: pages, per-widget visible/size, add/rename/remove page, save, restore defaults, export/import JSON (`/configure`, `POST /api/dashboard`) | **Done** (#90), as decided 2026-10-19: replaced by Configure → Pages and Overview cards (show/hide, per browser). The legacy saved-layout editor stays at `/configure` until the legacy pages go. |
| 5 | **Layout-driven pages:** `/` renders whatever `/api/dashboard` says | **Decided 2026-10-19:** not ported; `/app/` has fixed pages with modules shown or hidden (#90). |
| 6 | **Admin actions:** flush logs, restart gpsd/chrony/web, reboot (`/admin`, `/api/admin`) | **Done** (#81): Administration → Station actions, with a confirmation step for everything except the log flush. |
| 7 | **Survey reset** (`/admin`, `POST /api/setting {"reset_site": true}`) | **Done** (#82): Administration → Position survey. Shows what would be discarded; the operator types RESET to confirm. |
| 8 | **Almanac date navigation:** date picker with ←/→, "Sky at" time, Now (`/almanac`) | **Done** (#87): Sun & Astronomy → Sun & Moon, ← date → and Today (1850–2149). The "Sky at" time comes with the sky map (step 3). |
| 9 | **Twilight bar** (24 h) and **night bar:** twilight stages, moon-up strip, moonless-dark windows, total moonless astronomical darkness (`/almanac`) | **Done** (#87): "Day, midnight to midnight" and "Night, sunset to sunrise" cards: twilight stages, moon-up strip, moonless-darkness windows and total, midnight tick. |
| 10 | **Moon details:** time above horizon, transit altitude (`/almanac`) | **Done** (#87): Moon card adds transit altitude and time above the horizon; events on another day carry their date. |
| 11 | **Sky map:** stars by magnitude, constellation lines, Sun/Moon/planets, target reticle (`/almanac`) | **Done** (#88): Sun & Astronomy → Sky & Objects: stars by magnitude, constellation lines (split at the horizon), Sun, Moon and planets, the target reticle; "Sky at" time and Now. North up, east right, as the other `/app/` sky plots. |
| 12 | **Object lookup:** M-numbers, star names, planets, RA/Dec; rise/transit/set, dark and moonless windows (`/almanac`, `/api/object`) | **Done** (#88): Find an object (Messier, star names, planets, J2000 RA/Dec): rise/transit/set, circumpolar or never up, dark and moonless windows. The target is per request; the server-global target is gone (GPS-030). |
| 13 | **Offset chart uncertainty band** and symlog axis (linear within ±1 µs) (`/history`) | **Done** (#94): Timing → Overview, Time Offset History: chrony's offset, ± its offset SD where reported (never filled in), ± chrony's max-error bound (toggle), symmetric-log axis linear within ±1 µs. Uses the named tracking.log columns from #93. |
| 14 | **Survey convergence:** log-scale ± over time, bullseye scatter of session fixes with scatter/SE rings (`/history`, `/api/survey`) | **Done** (#89): GNSS & Site → Survey: standard error of the mean over time (log scale, horizontal and vertical), and this session's fixes around the mean with 1–3σ scatter rings and the mean's ring. Labeled as SE computed as if fixes were independent (GPS-009 wording). |
| 15 | **Survey ingest counters:** accepted, rejected by reason, collector running (`/api/survey` → `ingest`) | **Done** (#89): Survey ingest card: collector running, accepted and rejected this session by reason, last rejection, total accepted. |
| 16 | **chrony detail:** residual frequency, skew, update interval, PPS age (`lastrx` of the PPS source), raw `sourcestats` (`/legacy`) | **Done** (#89): Timing → Overview, "chrony tracking": frequency, residual frequency, skew, update interval, last offset, reference time. PPS sample age and raw `sourcestats` were already on PPS Diagnostics. |
| 17 | **Satellite table TDOP column and SNR bars per row** (`/legacy`) | Covered by the GNSS page, except the TDOP column. |
| 18 | **`custom.css` site override** (all legacy pages link `/static/custom.css`) | The new UI does not load it. **Dropped 2026-10-19** (owner). |
| 19 | **Time-zone table** (`/zones`) | No link or equivalent in the new UI (the route still works). **Dropped 2026-10-19** (owner); the route goes with the legacy pages. |
| 20 | **"Projected 1 s holdover" = 1 / \|ppm\|** (`/` timing_quality widget) | Deliberately not ported. It extrapolates from a single frequency value. The new UI's holdover panel is `Planned` until there is a validated model. **Dropped 2026-10-19** (owner's explicit yes, per ADR-0004). |
| 21 | **Throttle flags shown individually** (`/admin`) | **Done** (#91): Administration → Power shows every get_throttled condition (under-voltage, frequency capped, throttled, soft temperature limit), now and since boot, with the raw value; under-voltage gets a warning, because an unsteady supply can disturb timing. |

## New UI features the legacy pages lack

- Timing-chain stages, inferred classification, PPS event log with boundary and confidence (`/api/timing-chain`); diagnostic snapshot with copy (`/api/diagnostics`). Neither endpoint had a UI before.
- Source-aware banner on every page; timing-chain card on the Overview page; PPS Diagnostics page with the 12 acceptance questions, device, live PPS, chrony refclock, outage history, raw output and COPY/DOWNLOAD snapshot (feat/pps-ui).
- Browser connection statistics: RTT current/min/median/p95, jitter.
- chrony sources table with selection state on the Network page.
- Explicit UNKNOWN for every value the station cannot establish, and stale sky data hidden instead of shown as current counts.
- Screenshot mode (header toggle, Alt+Shift+S, per browser, display only): coordinates, heights, NTP client addresses and the hostname drawn as a blurred mask. The legacy pages have no equivalent; their location display follows the station's privacy mode only.

## Not parity items (unchanged routes)

`/time`, `/api/*`, `/static/*` keep working regardless of which UI is used.
