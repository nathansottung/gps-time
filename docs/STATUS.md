# Project status

Every spec item, roadmap feature and independent-review finding, with its status and the PRs that delivered it.

**Update this file in every PR** (rule in `CLAUDE.md`):
- Move rows whose status changed.
- Add the PR link.
- Re-order the next-5 list when it changes.

Last updated: 2026-11-04 (feat/dvb-blacklist, #157): the station's own DVB-T driver blacklist for both SDR installers; rc.3 PRs so far: #156, #157. v1.6.0-rc.2 is tagged (#155). Before that (#154): v1.6.0-rc.1 tagged from `main`, v1.5.0 skipped (owner), the outage-timing comparison recorded; the formal soak waits for the antenna move, and the first run of rc.1 is for sector data and web SDR testing; the next-5 list is unchanged. Before that: integer-ns PPS timestamps and the USB check (#153), the web SDR (#152). Built from the specs, `roadmap/feature-registry.md`, `roadmap/current-scope.md` and `review/GPS-Time-Independent-Review-2026-09-27.md`, each checked against the code and tests.

## Next 5 tasks, in order

Re-ordered 2026-10-26 (#124): item 1, the rc.11 soak run, is done (clean; v1.4.0 tagged), leaving five items. Earlier, 2026-10-21 (#114): the trained oscillator profile came in as item 6 (owner). Earlier the same day (#110): the module architecture spec came in as item 5, joined by the observation format (#111). Earlier, 2026-10-21 (#99): legacy removal step 7 was done (with 8 and 9), leaving four items. Earlier, 2026-10-19 (#98): the two done items (chrony history semantics, #93; bounded tracking log, #72) left the list, and the dual-band receiver profile came in as next (owner).

1. *Done in [#124](https://github.com/nathansottung/gps-time/pull/124): clean after 6 days 17 h; v1.4.0 tagged on the rc.11 commit (`development/raspberry-pi-deploy.md` → "Soak run of v1.4.0-rc.11").* **Soak run of v1.4.0-rc.11 on the Pi** (owner deploys; read-only check after 3 days): upgrade with `deploy/upgrade-1.4-station.md`; v1.4.0 is tagged on the rc.11 commit if three days are clean. rc.11 is tagged ([#95](https://github.com/nathansottung/gps-time/pull/95)). rc.10 was checked after 2 h 17 min and replaced (`development/raspberry-pi-deploy.md` → "First hours of v1.4.0-rc.10").
2. **Dual-band receiver profile** (ZED-F9T or ZED-F9P; owner, 2026-10-19): plan in `hardware/zed-f9-dual-band.md`. First the owner's choices (module and band variant, board, antenna and site), then profiles and docs, per-signal satellites, the `/app/` satellite views, receiver identity, and hardware validation, one PR each. Raw-data collection and PPP come after.
3. **PPS history views** (CHG "Historical UI", OBS §6): backend rollups of the event history (uptime, last/longest outage, 24 h/7 d counts, availability %, total unavailable time) and the six-category state timeline.
4. **Timing metrology, remaining** (TM §2 NTS, then §5 PTP): §1, §3, §4 and §6 are done (#55, #56, #57, #52, #58). Owner, 2026-10-04: stop before NTS and PTP and report; neither is started.
5. **Module architecture and observation format** (owner, 2026-10-21): `specs/SPEC-EXTENSIBILITY.md`, then the format part of `specs/SPEC-OBSERVATION-FORMAT-AND-TASKING.md` (`gpstime:` schema, writer, reader, validator, converters). Module safety and API stability go with the loader. Its order of work, one PR each: interfaces, manifest, schemas, `ctx` and loader with no behaviour change; `tools/new_module.py` and the guide; `source-weather`; `reference-adsb` and `reference-broadcast-towers` (both done, #134, #136); `analysis-tower-delay-check` (done on synthetic data, #137); moving optional features to modules where it simplifies them. Steps 1-2 (kit, loader, scaffolder, guide) done in #117; the observation format's writer, reader and validator in #118, converters in #122.
6. *Done in [#133](https://github.com/nathansottung/gps-time/pull/133) (fit) and [#135](https://github.com/nathansottung/gps-time/pull/135) (holdover projection, export/import, board binding, metadata). Not yet run on a Pi.* **Trained oscillator profile** (owner, 2026-10-21; `roadmap/ROADMAP-OSCILLATOR-AND-MISC.md` §1): fit the oscillator log (frequency vs temperature, aging), a modeled holdover projection beside the simple one (GPS-008), export/import as one JSON file, board binding by serial hash, metadata. With item 1 done, the list has five open items.

## v1.5.1: plan

Owner, 2026-10-26: plan v1.5.1 (UI work) to follow the v1.5.0 soak. Plan: `releases/v1.5.1-plan.md` ([#141](https://github.com/nathansottung/gps-time/pull/141)).
- **Carries:** the UI work merged after v1.5.0-rc.1 (#129, #130, #131, and the UI of #135 and #137), with the rest of `main`.
- **Gate:** only after the v1.5.0 check (scheduled 2026-10-29). If v1.5.0 isn't clean, the owner decides first.
- **Before rc.1:**
  1. *done in [#142](https://github.com/nathansottung/gps-time/pull/142)* module output in the web UI (closes the v1.5.0 known issue);
  2. *done in [#143](https://github.com/nathansottung/gps-time/pull/143)* fix the flaky timestamp match in the PPS evidence test;
  3. *done in [#144](https://github.com/nathansottung/gps-time/pull/144)* a desktop UI review of the candidate.
- **Then:** the release-notes PR and tag, the owner's deploy, and a 72 h soak with unchanged criteria.

## v1.4.0-rc.9: to do

From the rc.8 soak run (`development/raspberry-pi-deploy.md` → "Soak run of v1.4.0-rc.8"). Owner, 2026-10-19: yes to the first two; don't weaken outage detection.

1. *Done in [#72](https://github.com/nathansottung/gps-time/pull/72).* **Log flush without write amplification** (with next-5 item 3, GPS-011/012): append only new lines to the SD copy instead of copying the whole RAM log every hour; cap the RAM log and the SD copy; stop logrotate keeping rotated full copies of it.
2. *Done in [#73](https://github.com/nathansottung/gps-time/pull/73).* **Outage evidence kept on the SD card, under a size cap** (OBS §13): when an outage event opens and closes, keep a bounded window of chrony tracking, PPS state and GNSS summary around it, so the evidence survives a reboot; oldest evidence removed first when the cap is reached.
3. *Done in [#70](https://github.com/nathansottung/gps-time/pull/70).* **PPS polling off the request thread, and missed versus unread pulses told apart:** a dedicated poller thread reads the kernel PPS every second; no HTTP request ever polls; missed pulses keep being counted from the kernel's sequence number, and pulses the kernel counted but the station didn't read individually are counted separately. To settle whether the 9 % missed-pulse figure was an artifact.
4. Queued UI fixes (owner's list): sunset prominence, sunrise/sunset shifts in h/m/s, the ~3 s browser round trip, screenshot mode. The ~3 s round trip: done in [#74](https://github.com/nathansottung/gps-time/pull/74). Shifts in h/m/s: done in [#75](https://github.com/nathansottung/gps-time/pull/75). Sunset prominence: done in [#78](https://github.com/nathansottung/gps-time/pull/78). Screenshot mode: done in [#79](https://github.com/nathansottung/gps-time/pull/79).

## Legacy removal: queue (after v1.4.0)

Owner, 2026-10-19: queue the remaining parity items so the legacy pages can be retired after v1.4.0. Plan and reasons: `dashboard/legacy-removal-plan.md`; items by number: `dashboard/web-ui-parity.md`. Nothing is deployed while the Pi soaks rc.10; steps 2–4 only add to `/app/` and can be built before v1.4.0, but ship after it.

1. *Decided 2026-10-19 ([#86](https://github.com/nathansottung/gps-time/pull/86); items 2 and 21 in [#91](https://github.com/nathansottung/gps-time/pull/91)); see Decisions.* **Owner decisions** (blocks steps 5 and 9): themes incl. red night mode (1); saved layout editor and layout-driven pages, port or drop (4, 5); `custom.css` (18); `/zones` (19); throttle flags (21) and the station-wide zone override (2) as enough; dropping the 1/|ppm| holdover figure (20, needs an explicit yes per ADR-0004).
2. *Done in [#87](https://github.com/nathansottung/gps-time/pull/87).* **Almanac:** date navigation, twilight and night bars, moon details (8, 9, 10). Data already in `/api/almanac`.
3. *Done in [#88](https://github.com/nathansottung/gps-time/pull/88).* **Sky map and object lookup** (11, 12), with the object target made per-request instead of server-global (GPS-030).
4. *Done in [#89](https://github.com/nathansottung/gps-time/pull/89).* **Survey convergence and ingest counters** (14, 15); the remaining chrony detail (16).
5. *Done in [#90](https://github.com/nathansottung/gps-time/pull/90).* What the owner keeps from step 1: the red **night theme** (1), and **show/hide modules** in place of the saved-layout editor (4, 5).
6. *Done in [#94](https://github.com/nathansottung/gps-time/pull/94).* **Offset chart uncertainty band and symlog axis** (13), only after chrony history semantics (GPS-003, GPS-007; next-5 item 1).
7. *Done in [#99](https://github.com/nathansottung/gps-time/pull/99).* **Switch the front door:** `/` → `/app/`, legacy pages under `/legacy/…` with a going-away notice. First release after v1.4.0; run on the Pi.
8. *Done in [#99](https://github.com/nathansottung/gps-time/pull/99).* **Remove** the legacy pages and the code only they use, after at least one release with step 7 in use and the owner's go-ahead.
9. *Done in [#99](https://github.com/nathansottung/gps-time/pull/99).* **Close what the removal settles:** GPS-016, GPS-027, GPS-029 (if the layout model goes), the legacy halves of GPS-004 and GPS-009; ADR-0004 updated.

## Decisions

- **2026-10-26, v1.4.0 tagged:** the owner authorized on 2026-10-19 a scheduled read-only soak check that tags v1.4.0 on the rc.11 commit only if `tools/soak_check.py` reports CLEAN. It did (6 days 17 h, no outages but the installer's), so `v1.4.0` is on `cbd891c` with a GitHub release. Done in [#124](https://github.com/nathansottung/gps-time/pull/124).

- **2026-10-21, desktop app:** owner: drop Electron. A tray app runs the same Python backend, packaged per OS (e.g. PyInstaller), and opens the UI in the default browser; nothing is ported to TypeScript. Recorded in ADR-0006 and `roadmap/ROADMAP-DESKTOP-FIELD-APP.md` (Goal, shared code, open questions) in [#107](https://github.com/nathansottung/gps-time/pull/107). The roadmap stays FUTURE, not scheduled.

- **2026-10-21, M102:** owner: map M102 to NGC 5866 (Spindle Galaxy) with a note that this departs from OpenNGC (which lists it as a duplicate of M101), and restore the "Spindle" lookup. Done in [#102](https://github.com/nathansottung/gps-time/pull/102).

- **2026-10-21, sky data:** owner asked for the bundled Messier, star and constellation files to be compared with OpenNGC, the Yale BSC and d3-celestial, attributed, and regenerated where a source can't be confirmed. Done in [#101](https://github.com/nathansottung/gps-time/pull/101). M102 follows OpenNGC (a duplicate of M101), with the NGC 5866 identification in a note.

- **2026-10-21, public release preparation:** owner asked for the full checklist, a history scan, license and notices, CONTRIBUTING and a public README, and a report before the repository is made public. Done in [#100](https://github.com/nathansottung/gps-time/pull/100); the repository stays private until the owner flips it.

- **2026-10-21, legacy removal:** owner asked for removal steps 7–9 together while rc.11 soaks (no deploy). Done in [#99](https://github.com/nathansottung/gps-time/pull/99): `/` and the old page paths redirect to `/app/`; the legacy pages and the code only they used are removed. v1.4.0 (on the rc.11 commit) still has them; this is on main for the next release.

- **2026-10-19, next hardware:** owner asked for a dual-band u-blox receiver profile (ZED-F9T for timing or ZED-F9P for positioning), scoped as a plan and marked next. Plan: `hardware/zed-f9-dual-band.md`. On this Pi the GPIO timestamp spread (1.3 µs) hides the F9T's nanosecond PPS; the gain here is fewer outages and better tracking, and nanosecond timestamps need the PTP work (TM §5).

- **2026-10-19, the current station:** owner: it is a development unit (Pi 4, Uputronics MAX-M8Q, current antenna and site), and its weak C/N₀ (best about 25 dB-Hz) is an antenna and site limit. Recorded in `development/raspberry-pi-deploy.md`. The soak criteria are unchanged; a run that fails only on outages is reported, not tagged.

- **2026-10-19, release route:** owner chose rc.11 from main (with #93's release-blocker fix and the `/app/` port) over tagging v1.4.0 on rc.10. v1.4.0 goes on the rc.11 commit after three clean days. Removal step 7 stays out of rc.11.

- **2026-10-19, legacy parity items 2 and 21, and module storage:** owner decisions. **Per-browser time-zone picker (2):** dropped; the station-wide override covers it. **Throttle flags (21):** kept, decoded per condition (under-voltage, frequency capped, throttled, soft temperature limit), now and since boot; under-voltage is worth showing because it can upset timing. Done in [#91](https://github.com/nathansottung/gps-time/pull/91). **Module visibility** (Configure, #90) stays per browser.

- **2026-10-19, legacy parity (removal step 1):** owner decisions. **Themes (1):** keep dark and the red night theme; drop light. **Saved layout editor and layout-driven pages (4, 5):** replaced by show/hide modules in `/app/`; the saved-layout model (`/api/dashboard*`, `dashboard.py`, `dashboard.default.json`, `tools/promote_dashboard.py`, `-UseDemoLayout`) goes with the legacy pages (step 8). **`custom.css` (18) and `/zones` (19):** dropped. **The 1/|ppm| "projected 1 s holdover" figure (20):** dropped (the explicit yes ADR-0004 asks for). Not decided: the per-browser zone picker (2; `/app/` has the station-wide override) and individual throttle flags (21; `/app/` lists active flags); they stay as they are until the owner confirms.

- **2026-10-02, location privacy, `hidden` mode:** the station drops satellite azimuth and elevation, sun/moon/sky times and sidereal time. It **keeps** satellite IDs, constellation, C/N₀ and used flags, so GNSS health stays visible. The residual (which satellites are tracked) narrows position only coarsely. Owner decision; see `api/endpoints.md` privacy notes.
- **2026-10-02, order:** administrative security before shipping `web/dist` to the Pi. Administrative security was done in #24.
- **2026-10-19, v1.4.0 not tagged:** the rc.8 soak run (14 days) had real PPS/GNSS outages on 2026-10-17 (owner confirms; outage detection must not be weakened). chrony coasted through a 56-minute gap and was 1.7 µs off afterwards. rc.9 comes first (list above).
- **2026-10-05, legacy pages:** a removal plan is written; nothing is removed. The owner asked for a report before any deletion. Open decisions are listed in the plan (themes, the saved-layout model, `custom.css`, `/zones`, dropping the 1/ppm holdover figure).
- **2026-10-05, merged rows:** three feature-registry rows (Feature E "ADS-B 1090 adapter" and "Fox-hunt TOA/TDoA research", Feature F "MLAT metadata/solver") described the same work as three RF-spec rows. Each pair is now one row, in the RF block, with both sources named in the Area column. Owner's request.
- **2026-10-05, RF nodes and TDOA:** `specs/SPEC-RF-NODE-AND-TDOA.md` added as PLANNED. It builds on `roadmap/ROADMAP-SDR-RF-OBSERVATORY.md` and starts after v1.4.0. Nothing is scheduled; the next-5 list is unchanged.
- **2026-10-05, release:** rc.6 has run on the Pi since 2026-10-04 (PPS selected, stratum 1, about 300 ns). The owner will upgrade it to rc.8 and run that for 3 days before v1.4.0.
- **2026-10-04, timing metrology:** `specs/SPEC-TIMING-METROLOGY.md` added as NEXT. The owner asked for §1, §3, §4 and §6 to be built now, in that order, one PR each, and for work to stop before NTS (§2) and PTP (§5). Items 1–3 of the list stay pre-release blockers. The former item 4 (GPS-021) was done in [#30](https://github.com/nathansottung/gps-time/pull/30).
- **2026-10-04, next-5:** shipping `web/dist` was done in [#35](https://github.com/nathansottung/gps-time/pull/35), so the list has 4 items until the owner picks a fifth. Item 4 (GPS-021) is already done.
- **2026-10-02, deploys:** GPS-021 (deploy scripts stop on failure and verify the upload) is next-5 item 5 and must land before any Pi deploy. Owner decision.

## Legend

**Status:**

| Status | Meaning |
|---|---|
| done | Implemented and tested, or verified in the UI. A note may give a caveat. |
| in progress | Being built on an open or local branch. |
| next | Covered by one of the next-5 tasks. |
| planned | Not scheduled. "partial:" in Notes means part of it exists. |

**Areas:**

| Area | Source |
|---|---|
| CHG | `specs/CHG-PPS-HEALTH-DIAGNOSTICS.md` |
| TASK | `specs/TASK-PPS-CHAIN.md` |
| OBS | `specs/PPS-OBSERVABILITY-AND-GNSS-INTEGRITY.md` |
| TM | `specs/SPEC-TIMING-METROLOGY.md` |
| RF | `specs/SPEC-RF-NODE-AND-TDOA.md` |
| EXT | `specs/SPEC-EXTENSIBILITY.md` |
| OSC | `roadmap/ROADMAP-OSCILLATOR-AND-MISC.md` §1 |
| PPSM | `specs/SPEC-SDR-PPS-MARKER.md` (research) |
| OBSF | `specs/SPEC-OBSERVATION-FORMAT-AND-TASKING.md` |
| ADD | `specs/ADDENDUM-SKY-SOLAR-SATELLITE.md` |
| Feature A–J | `roadmap/feature-registry.md` sections |
| Scope | `roadmap/current-scope.md`; "Gap" rows: `SCOPE-REVIEW.md` §7 |
| Web UI | the React port (`web/`, ADR-0004) |
| Review | `review/GPS-Time-Independent-Review-2026-09-27.md` |
| Repo | repository tooling, CI and releases (owner requests) |
| Hardware | `hardware/` scopes and profiles (owner requests) |

Future, unscheduled work outside this table: `roadmap/ROADMAP-DESKTOP-FIELD-APP.md`, `roadmap/ROADMAP-SDR-RF-OBSERVATORY.md` (scoping), `roadmap/ROADMAP-WEB-UPDATES.md` (FUTURE, low priority; not before the station has run stably on v1.4.0), `roadmap/ROADMAP-OSCILLATOR-AND-MISC.md` (§1 oscillator profile: done, rows OSC; §4 script done; the rest FUTURE), `roadmap/ROADMAP-GEOPHYSICS-DISTRIBUTED-SCIENCE.md` (FUTURE, research; after v1.4.0 and the oscillator profile), `roadmap/ROADMAP-SENSOR-FUSION.md` (FUTURE; extends the geophysics roadmap), `specs/SPEC-COORDINATOR.md` (PLANNED; required before any multi-station feature), `specs/SPEC-RF-TASKING-AND-FM-TDOA-TRIAL.md` (OPTION, planned; extends the RF node spec), `specs/SPEC-RF-REFERENCE-SIGNALS-AND-TRUST.md` (OPTION, planned; extends the RF tasking spec), `specs/SPEC-SDR-PPS-MARKER.md` (RESEARCH; step 1 done, rows PPSM), `hardware/HARDWARE-REFERENCE-NODE.md` (DRAFT parts list). All of them, by phase, for outside readers: `ROADMAP.md`.

**Totals:** 553 rows: 334 done, 2 in progress, 33 next, 184 planned.

## Status table

| Area | Ref | Item | Status | Notes | PR |
|---|---|---|---|---|---|
| CHG | Model 1 | GNSS receiver communication stage | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Model 2 | Satellite reception stage | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Model 3 | Navigation/time solution stage | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Model 4 | PPS device exists stage | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Model 5 | Kernel PPS events stage | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Model 6 | PPS event frequency shown | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | Model 7 | Age of last PPS event shown | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | Model 8 | chrony sees PPS stage | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Model 9 | chrony PPS reach | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Model 10 | chrony accepts PPS stage | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Model 11 | chrony selected source | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Model 12 | System clock sync state | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Model 13 | Fallback source stage | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Model 14 | Failover duration | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Model | UNKNOWN / NOT OBSERVABLE, never inferred healthy | done | receiver PPS output = NOT_OBSERVABLE | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Model | Seven critical states kept distinct | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Dashboard | TIMING STATUS hierarchy on the main page | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | Banner | Banner names the sync source; no bare SYNCHRONIZED | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#10](https://github.com/nathansottung/gps-time/pull/10) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | PPS card | Dedicated PPS diagnostic card/page | done |  | [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | PPS card | Device: path, exists, metadata, GPIO, edge | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | PPS card | Live: last ts, age, rate, consecutive, missed, interval stats | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | PPS card | Label the measurement layer (Linux, not electrical) | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | PPS card | chrony: mode, reach, selected, offset, freq/skew, symbol, last sample | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#10](https://github.com/nathansottung/gps-time/pull/10) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | PPS card | No invented causal explanation | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | State machine | Ten PPS states | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Watchdog | Last event, age, interval, frequency | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Watchdog | 1.5 s / 3 s thresholds | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Watchdog | Thresholds configurable | done | env vars | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Watchdog | No 1 Hz SD writes | done | RAM ring; checkpoints | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Outage | One event per outage | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Outage | Outage evidence fields | planned | partial: median C/N₀ not accumulated | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Outage | Event stays open until recovery | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Recovery | Auto-close outage | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Recovery | Recovery fields (source, max offset, time to accept/select) | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | Recovery | Preserve for history | next | partial: last 50 kept, API shows 10 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | History | Current PPS uptime | next |  |  |
| CHG | History | Longest PPS outage | next |  |  |
| CHG | History | Outages in last 24 h | next |  |  |
| CHG | History | Outages in last 7 d | next |  |  |
| CHG | History | PPS availability % | next |  |  |
| CHG | History | Total PPS unavailable time | next |  |  |
| CHG | History | Timeline of PPS state | next |  |  |
| CHG | History | Timeline distinguishes the 6 GNSS/PPS/failover/holdover categories | next |  |  |
| CHG | History | Last PPS outage | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | History | PPS loss vs GNSS availability view | next | partial: classification column | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| CHG | Snapshot | Diagnostic snapshot content | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Snapshot | COPY DIAGNOSTICS control | done | on the PPS page; http-LAN fallback | [#10](https://github.com/nathansottung/gps-time/pull/10) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | Snapshot | DOWNLOAD DIAGNOSTICS (optional) | done |  | [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | Snapshot | No precise location in privacy mode | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Advanced | ls -l /dev/pps* equivalent | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | Advanced | ppstest equivalent | planned | partial: last event/sequence/age/rate on PPS page; no per-event listing | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | Advanced | chronyc sources/sourcestats/tracking | done | raw chronyc -n, not -v | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | Advanced | PPS kernel/dmesg information | planned |  |  |
| CHG | Advanced | No browser shell execution; read-only | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Incident | HW indicator NOT_OBSERVABLE; kernel unknown until tested | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Incident | Never claim antenna/jamming/spoofing/HW failure | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Integrity | PPS PATH ANOMALY, not jamming | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Integrity | POSSIBLE GNSS RF INTERFERENCE on mass C/N₀ collapse | planned | partial: low-confidence GNSS RECEPTION ANOMALY only | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Integrity | Multi-subsystem evidence correlation | planned | partial | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 1 | /dev/pps0 absent | done | test_01 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 2 | Present, no events | done | test_02 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 3 | Healthy 1 Hz | done | test_03 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 4 | Single missed pulse | done | test_04 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 5 | Sustained loss | done | test_05 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 6 | Recovery | done | test_06 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 7 | Visible but rejected | done | test_07 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 8 | Accepted, not selected | done | test_08 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 9 | Selected normally | done | test_09 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 10 | GNSS healthy, PPS fails | done | test_10 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 11 | GNSS and PPS fail | done | test_11 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 12 | Failover after PPS loss | done | test_12 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 13 | Return to PPS | done | test_13 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 14 | Outage created once | done | test_14 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 15 | Outage closed | done | test_15 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 16 | Duration survives restart | done | test_16 | [#6](https://github.com/nathansottung/gps-time/pull/6) |
| CHG | Test 17 | Snapshot correct | done | test_17 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 18 | Privacy: no coordinates | done | test_18 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 19 | Demo mode works | done | test_19 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Test 20 | No Stratum 1 GPS/PPS unless selected | done | test_20 | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Tests | Fixtures only; no live GNSS/Internet | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Docs | Nine required architecture topics | done | docs/architecture/timing-chain.md | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | AC1 | GNSS still received | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| CHG | AC2 | /dev/pps0 exists | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| CHG | AC3 | PPS events reach Linux | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| CHG | AC4 | Time of last PPS event | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | AC5 | chrony sees PPS | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| CHG | AC6 | chrony accepts PPS | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| CHG | AC7 | chrony selects PPS | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| CHG | AC8 | Source disciplining the clock | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| CHG | AC9 | How long in failover | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| CHG | AC10 | When the failure began | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| CHG | AC11 | Previous similar failures | next | partial: last 10 events | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| CHG | AC12 | Clock accuracy during the outage | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| CHG | AC | Never imply PPS healthy from GNSS or NTP sync | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| CHG | Operator | Capture-before-reboot procedure documented | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | Rule | Lightweight offline station | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | Rule | Minimize SD writes | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | Rule | Six provenance labels; UNKNOWN | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | Rule | Never name an unprovable cause | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | Rule | No timing-behavior change | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | Rule | Privacy in diagnostics | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | Rule | Tests need no GNSS/Internet/root | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | Rule | UI follows Guidelines.md | planned | partial: Tailwind colour classes remain in some pages | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| TASK | Rule | Branch + docs in the branch | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | T1 | pps.py sysfs ring and statistics | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | T2 | chrony parsing; NMEA stage | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | T3 | Independent chain stages | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | T4 | State machine + thresholds | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | T5 | Replace sync_state banner | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | T6 | Generic event + restart checkpoint | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | T7 | PPS PATH ANOMALY classification | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | T8 | /api/timing-chain | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | T9 | 20 tests + NMEA-stale test | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | T10 | docs/architecture/timing-chain.md | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| TASK | T11 | Demo synthetic data per state | planned | partial: no DEVICE_PRESENT_NO_EVENTS / CHRONY_ACCEPTED scenario | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §1.1 | GNSS RF reception stage | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §1.2 | Receiver/navigation stage | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §1.3 | GNSS time-solution stage | planned | partial: merged into nav stage | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §1.4 | Receiver PPS/timepulse stage | done | NOT_OBSERVABLE | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §1.5 | Kernel PPS device | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §1.6 | PPS event reception | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §1.7 | chrony PPS source | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §1.8 | chrony lock/selection | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §1.9 | System clock sync | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §1.10 | NTP service state | planned | partial: Network page; no chain stage | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| OBS | §2 | Timing health panel with per-stage values | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| OBS | §3 | Present / available / locked / selected | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §4a | Last PPS timestamp in UI | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| OBS | §4b | Seconds since last PPS in UI | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| OBS | §4c | Current PPS frequency in UI | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| OBS | §4d | Consecutive PPS events in UI | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| OBS | §4e | Interruption duration | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| OBS | §4f | Last PPS recovery time in UI | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| OBS | §4g | HEALTHY / DEGRADED / LOST | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §4h | Configurable thresholds | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §4i | No hardware-failure claim | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §5a | One persistent event per loss | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §5b | Event fields incl. median C/N₀ | planned | partial: median C/N₀ missing | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §6a | PPS-loss graph views | next |  |  |
| OBS | §6b | Graph distinguishes GNSS/PPS/rejected/selected | next |  |  |
| OBS | §7 | Time-to-1 µs…1 s holdover estimates | done | modeled: free-running (|Frequency|), trained (Skew) and profile (Skew + residual RMS + temperature over the last 24 h's range + aging) times to ±1 µs…±1 s; `/api/oscillator` → `holdover`; Timing → Overview and Oscillator. Not validated against an outage yet | [#135](https://github.com/nathansottung/gps-time/pull/135) |
| OBS | §8 | Integrity metric history + baselines | planned |  |  |
| OBS | §9 | RF interference detection | planned |  |  |
| OBS | §10 | Spoofing / position anomaly detection | planned |  |  |
| OBS | §11 | GNSS↔PPS correlation | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §12a | Generic event schema | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §12b | Fifteen event types | planned | partial: PPS_OUTAGE only | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §13 | ±5 min forensic evidence window | done | station view every 10 s and chrony's tracking lines; no kernel, gpsd or raw NMEA capture | [#73](https://github.com/nathansottung/gps-time/pull/73) |
| OBS | §14 | Multi-station event format | planned |  |  |
| OBS | §15 | Receiver upgrade-path doc | planned | partial |  |
| OBS | §16 | Immediate diagnostic doc | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §17 | Implementation constraints | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | AC1 | Satellites received? | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| OBS | AC2 | Valid GNSS time? | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| OBS | AC3 | Kernel PPS present? | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| OBS | AC4 | chrony receiving PPS? | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| OBS | AC5 | chrony selecting PPS? | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| OBS | AC6 | What disciplines the clock? | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| OBS | AC7 | When did the failure begin? | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| OBS | AC8 | Has it happened before? | next | partial: last 10 events | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| OBS | AC9 | Drift during the outage? | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| OBS | AC10 | RF anomaly vs PPS/software path? | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| ADD | §1 | Earth-shadow umbra/penumbra model | done | conical umbra and penumbra, finite Sun; geometric (no atmosphere, no refraction); needs no ephemeris. Not yet run on a Pi | [#61](https://github.com/nathansottung/gps-time/pull/61) |
| ADD | §2 | Zenith satellite-shadow metric | done | 550 km state, and the umbra and full-sunlight heights; says it is the zenith only | [#61](https://github.com/nathansottung/gps-time/pull/61) |
| ADD | §3 | Illumination sky map | done | 350 / 550 / 1200 km and custom shells; click to ask about one direction | [#61](https://github.com/nathansottung/gps-time/pull/61) |
| ADD | §4 | Starlink contamination indicator | done | geometric statements per shell, never a claim that a satellite is visible | [#61](https://github.com/nathansottung/gps-time/pull/61) |
| ADD | §5 | Satellite ephemeris layer | done | offline TLE cache filled by an operator-run fetcher (the web service never fetches); position, passes, shadow crossings, visible interval; element age shown. One satellite at a time, not a whole constellation | [#61](https://github.com/nathansottung/gps-time/pull/61) |
| ADD | §6 | Astrophotography darkness card | planned | partial: night/twilight times; no current state | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| ADD | §7 | Solar time (AST, MST, EoT) | planned | partial: solar noon only | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| ADD | §8 | Solar geometry list | planned | partial: rise/set/noon/twilight/daylight | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| ADD | §9 | Solar-energy estimate | planned |  |  |
| ADD | §10 | Learned sky-obstruction map | done | C/N₀, tracked and used per 10° × 5° cell from the GNSS collector, once a minute; capped grid on the SD card (hourly, atomic, no position); classes against the cell's elevation band; 8 sectors; polar heatmap on GNSS & Site → Sky Obstruction; off in hidden mode. Not yet run on a Pi | [#148](https://github.com/nathansottung/gps-time/pull/148) |
| ADD | §11 | Integrity + obstruction correlation | done | each satellite loss classed EXPECTED (blocked or attenuated cell), NOT EXPLAINED, SET or UNKNOWN; a sky-wide C/N₀ drop above 30° in 3+ quadrants is flagged, never with a cause. RAM only. Not tied into the timing-chain events | [#148](https://github.com/nathansottung/gps-time/pull/148) |
| ADD | §12 | Observing-conditions dashboard | planned |  |  |
| ADD | §13 | Weather-sensor interface | planned |  |  |
| ADD | §14 | All-sky camera | planned |  |  |
| ADD | §15 | SDR / radio-time layer | planned |  |  |
| ADD | §16 | Selected vs independent references | planned | partial: chrony sources table; NTP servers that don't steer the clock are compared (TM §4). Radio-time references not | [#10](https://github.com/nathansottung/gps-time/pull/10) [#57](https://github.com/nathansottung/gps-time/pull/57) |
| ADD | §17 | ADS-B / aircraft | planned |  |  |
| ADD | §18 | Distributed observations | planned | concept UI only | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| ADD | §19 | NOW page modules + customization | planned | partial | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| ADD | §20 | Provenance on every value | planned | partial: some UI tags not yet re-labeled | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| ADD | §21 | Offline core calculations | planned | partial |  |
| ADD | §22 | Station vs coordinator tiers | planned | partial |  |
| ADD | AC1 | What disciplines the clock | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| ADD | AC2 | PPS reaching Linux | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| ADD | AC3 | How long on failover | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| ADD | AC4 | GNSS behaving normally | planned | partial: no integrity baseline |  |
| ADD | AC5 | Below astronomical twilight now? | planned | partial: times only | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| ADD | AC6 | Shadow altitude at zenith | done |  | [#61](https://github.com/nathansottung/gps-time/pull/61) |
| ADD | AC7 | 550 km satellites sunlit in field | done | for a direction picked on the sky map; no camera field of view is modeled | [#61](https://github.com/nathansottung/gps-time/pull/61) |
| ADD | AC8 | When a shell is shadowed | planned | partial: the present state per shell is shown; the time at which a shell goes into shadow is not predicted | [#61](https://github.com/nathansottung/gps-time/pull/61) |
| ADD | AC9 | Daylight gained/lost | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| ADD | AC10 | Apparent solar time | planned |  |  |
| ADD | AC11 | Obstructed sky portions | done | sectors: "Expected obstruction below ~N°", "Intermittent attenuation a–b°", "Mostly clear", or not enough data | [#148](https://github.com/nathansottung/gps-time/pull/148) |
| ADD | AC12 | Is this satellite loss normal? | done | the loss table on Sky Obstruction: EXPECTED where the learned map has the direction blocked | [#148](https://github.com/nathansottung/gps-time/pull/148) |
| ADD | AC13 | Drift to 1 s without PPS | done | the ±1 s column of the holdover projection (three models, labelled modeled) | [#135](https://github.com/nathansottung/gps-time/pull/135) |
| Feature A |  | GNSS/PPS-disciplined chrony NTP | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| Feature A |  | Internet NTP fallback, honest source/stratum | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| Feature A |  | NTP client IP activity | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Feature A |  | Browser RTT + clock estimate | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Feature A |  | RAM-first bounded telemetry + checkpoints | done | tracking log capped in RAM and on SD ([#72](https://github.com/nathansottung/gps-time/pull/72)) | [#4](https://github.com/nathansottung/gps-time/pull/4) [#5](https://github.com/nathansottung/gps-time/pull/5) |
| Feature A |  | Source-loss / fallback / reacquisition timeline | next | partial: backend + event list | [#4](https://github.com/nathansottung/gps-time/pull/4) [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Feature A |  | Oscillator fractional-frequency history | done | chrony's frequency with the SoC temperature, 10-minute bins on the SD card (hourly, capped, board-bound); a straight-line slope. The trained profile (roadmap) is not built. Not yet run on a Pi | [#71](https://github.com/nathansottung/gps-time/pull/71) |
| Feature A |  | Time-to-1 ms…1 s holdover estimates | planned | partial: legacy raw projection |  |
| Feature A |  | ADEV / MDEV / TDEV / TIE / MTIE | planned | partial: ADEV, MDEV, TDEV done (TM §1); TIE and MTIE not | [#55](https://github.com/nathansottung/gps-time/pull/55) |
| Feature A |  | Error budget + light-distance | planned | partial: light-distance done | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Feature A |  | Antenna/coax/user-delay calibration | planned |  |  |
| Feature A |  | PTP / PHC / NIC timestamps | planned | research |  |
| Feature A |  | Common-view inter-station comparison | planned | research |  |
| Feature A |  | White Rabbit | planned | research |  |
| Feature A |  | 1 PPS / 10 MHz / IRIG outputs | planned | research |  |
| Feature B |  | Fresh-only GNSS collector | planned | partial: collector thread in web process | [#1](https://github.com/nathansottung/gps-time/pull/1) |
| Feature B |  | Survey sessions with accepted/rejected obs. | planned |  |  |
| Feature B |  | Time-block averaging / covariance | planned |  |  |
| Feature B |  | Accepted/locked station coordinate | planned |  |  |
| Feature B |  | Live vs candidate vs accepted position | planned | partial: live vs stored |  |
| Feature B |  | Learned sky-obstruction map | done | `architecture/sky-obstruction-map.md` | [#148](https://github.com/nathansottung/gps-time/pull/148) |
| Feature B |  | Constellation/health/orbit metadata | planned | partial: constellation only |  |
| Feature B |  | Antenna open/short diagnostics | planned |  |  |
| Feature B |  | h / H / N heights | planned | partial: N = h − H; no geoid model | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Feature B |  | EGM geoid data pack | planned |  |  |
| Feature B |  | Terrain/horizon packs | planned |  |  |
| Feature B |  | USB GNSS on Linux | planned | partial |  |
| Feature B |  | Serial NMEA/UBX abstraction | planned |  |  |
| Feature B |  | Receiver capability tiers | planned | partial | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| Feature B |  | ZED-F9T precision-timing tier | planned | future hardware |  |
| Feature B |  | ZED-F9P/RTK tier | planned | future hardware |  |
| Feature C |  | Sunrise/noon/sunset + y/t/t deltas | done | /app/: per-event shifts vs yesterday / to tomorrow in signed seconds (predicted); legacy sign fix | [#10](https://github.com/nathansottung/gps-time/pull/10) [#12](https://github.com/nathansottung/gps-time/pull/12) [#31](https://github.com/nathansottung/gps-time/pull/31) |
| Feature C |  | Daylight duration + seasonal rate | planned | partial: daily delta | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Feature C |  | Twilight + moonless darkness | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Feature C |  | Sun az/el, AST, MST, EoT | planned | partial |  |
| Feature C |  | Solar-equivalent-time calculator | planned |  |  |
| Feature C |  | Shadow direction/length | planned |  |  |
| Feature C |  | Irradiance / clear-sky energy | planned |  |  |
| Feature C |  | Tilted-surface / PV potential | planned |  |  |
| Feature C |  | Moon + planet/star visibility | done | legacy /almanac |  |
| Feature C |  | Sidereal time + meridian transit | done | privacy-aware | [#12](https://github.com/nathansottung/gps-time/pull/12) |
| Feature C |  | Equinoxes / solstices | planned |  |  |
| Feature C |  | Maidenhead / geodesic / antipode | planned |  |  |
| Feature C |  | Greyline | planned |  |  |
| Feature C |  | WMM magnetic model | planned |  |  |
| Feature C |  | TZ / leap-second / time-scale toolbox | planned | partial: /zones; time scales panel (TM §3) | [#56](https://github.com/nathansottung/gps-time/pull/56) |
| Feature C |  | Gravity/relativity calculations | planned |  |  |
| Feature C |  | Weather-derived quantities | planned |  |  |
| Feature D |  | Configurable pages / widget visibility | done | legacy /configure; /app preview only |  |
| Feature D |  | Drag/reorder/resize, saved presets | planned |  |  |
| Feature D |  | Presets (Timing, Astronomy, …) | planned | /app preview only | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Feature D |  | Expert + ELI5 presentation | planned | partial | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Feature D |  | Provenance tags | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Feature D |  | Freshness / calibration / uncertainty | planned | partial: freshness only | [#1](https://github.com/nathansottung/gps-time/pull/1) [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Feature D |  | Config export/import | done | legacy /configure |  |
| Feature D |  | Redacted diagnostic export | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) [#10](https://github.com/nathansottung/gps-time/pull/10) [#15](https://github.com/nathansottung/gps-time/pull/15) |
| Feature D |  | Themes incl. night vision | done | legacy only; /app dark only |  |
| Feature D |  | Solar-transit safety acknowledgement | planned | partial: in a Planned card | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Feature E (SDR) |  | SDR inventory by serial | planned |  |  |
| Feature E (SDR) |  | Spectrum/waterfall + RFI history | planned |  |  |
| Feature E (SDR) |  | Noise floor / occupancy | planned |  |  |
| Feature E (SDR) |  | WWV/CHU monitoring | planned |  |  |
| Feature E (SDR) |  | WSPR/FST4W reception | planned |  |  |
| Feature E (SDR) |  | UAT 978 adapter | planned |  |  |
| Feature E (SDR) |  | Radiosonde reception | planned |  |  |
| Feature E (SDR) |  | Meteor scatter | planned |  |  |
| Feature E (SDR) |  | Satellite RF + Doppler tuning | planned |  |  |
| Feature E (SDR) |  | SDR sample-clock characterization | planned |  |  |
| Feature E (SDR) |  | SDR sample-epoch characterization | planned |  |  |
| Feature E (SDR) |  | GPS-L1 software-receiver experiment | planned |  |  |
| Feature E (SDR) |  | RF group-delay profiles | planned |  |  |
| Feature E (SDR) |  | PPS/sample-marker research | planned |  |  |
| Feature E (SDR) |  | SDR timing tiers | planned |  |  |
| Feature F (aviation) |  | readsb/dump1090 receiver | in progress | `reference-adsb` reads its `aircraft.json` (#134); `GTP_SDR=1` installs Debian's readsb as `gps-time-readsb.service`, no network listeners, JSON in RAM (#145); not yet run on a Pi | [#134](https://github.com/nathansottung/gps-time/pull/134) [#145](https://github.com/nathansottung/gps-time/pull/145) |
| Feature F (aviation) |  | 978 MHz UAT receiver | in progress | `reference-adsb` reads skyaware978's `aircraft.json` (#134); `GTP_SDR=1` builds dump978-fa and skyaware978 at a pinned commit, on 127.0.0.1 only (#145); not yet built or run on a Pi | [#134](https://github.com/nathansottung/gps-time/pull/134) [#145](https://github.com/nathansottung/gps-time/pull/145) |
| Feature F (aviation) |  | External feed adapters (optional) | planned |  |  |
| Feature F (aviation) |  | Radiosonde tracking | planned |  |  |
| Feature F (aviation) |  | Topocentric alignment engine | planned |  |  |
| Feature F (aviation) |  | Sun/Moon transit predictions (OMM+SGP4, aircraft, sondes) | planned | partial: SGP4 satellite passes from TLEs (ADD §5); no Sun/Moon transits, no OMM, no aircraft or sondes | [#61](https://github.com/nathansottung/gps-time/pull/61) |
| Feature F (aviation) |  | Aircraft predictions as short-term estimates | planned |  |  |
| Feature F (aviation) |  | Satellite contamination for cameras | planned | partial: shadow-geometry summary (ADD §4); no camera field of view or exposure planning | [#61](https://github.com/nathansottung/gps-time/pull/61) |
| Feature G (network) |  | Opt-in request/accept/reject flow | planned |  |  |
| Feature G (network) |  | Private location shared with solver only | planned |  |  |
| Feature G (network) |  | Local-first raw data | planned |  |  |
| Feature G (network) |  | Station/instrument/calibration metadata | planned |  |  |
| Feature G (network) |  | Raw capture hashes/signatures | planned |  |  |
| Feature G (network) |  | Optional coordinator | planned | partial: skeleton (signed join and events, owner approval, SQLite, TrueNAS container; no processing services, no station sender) | [#127](https://github.com/nathansottung/gps-time/pull/127) |
| Feature G (network) |  | Distributed GNSS anomaly monitoring | planned |  |  |
| Feature G (network) |  | Multi-station WWV/WSPR/ionosphere | planned |  |  |
| Feature G (network) |  | Coincidence experiments | planned |  |  |
| Feature G (network) |  | Station clock-closure checks | planned |  |  |
| Feature G (network) |  | Networked lightning TOA | planned |  |  |
| Feature H (sensors) |  | Temperature/humidity/pressure | planned |  |  |
| Feature H (sensors) |  | Pyranometer | planned |  |  |
| Feature H (sensors) |  | Wind/rain/sky brightness | planned |  |  |
| Feature H (sensors) |  | Magnetometer | planned |  |  |
| Feature H (sensors) |  | Acoustic thunder timing | planned |  |  |
| Feature H (sensors) |  | Geophone/seismometry | planned |  |  |
| Feature H (sensors) |  | All-sky/optical cameras | planned |  |  |
| Feature H (sensors) |  | Power-grid frequency (isolated) | planned |  |  |
| Feature H (sensors) |  | Radiation/muon experiments | planned |  |  |
| Feature I (lightning) |  | VLF/audio-codec acquisition | planned |  |  |
| Feature I (lightning) |  | PPS/sample timing calibration | planned |  |  |
| Feature I (lightning) |  | Single-station detection | planned |  |  |
| Feature I (lightning) |  | Crossed-loop bearing | planned |  |  |
| Feature I (lightning) |  | Multi-station TOA solver | planned |  |  |
| Feature I (lightning) |  | Open protocol/hardware/solver | planned |  |  |
| Feature J (data packs) |  | Data packs: manifest, license, checksum, version, offline install | planned |  |  |
| Scope | 1.4.0-dev | Windows desktop demo | done |  | [#9](https://github.com/nathansottung/gps-time/pull/9) |
| Scope | 1.4.0-dev | Bundle build + deploy helpers | done | deploy failure handling done (GPS-021) | [#30](https://github.com/nathansottung/gps-time/pull/30) |
| Scope | Pre-release | Fresh-fix survey semantics | planned | partial: collector still in web process | [#1](https://github.com/nathansottung/gps-time/pull/1) |
| Scope | Pre-release | logsync exec-bit failure | done | not yet verified on a Pi | [#1](https://github.com/nathansottung/gps-time/pull/1) |
| Scope | Pre-release | chrony history field meaning | next |  |  |
| Scope | Pre-release | Bounded persistence | done | config and events atomic; tracking log capped in RAM and on SD ([#72](https://github.com/nathansottung/gps-time/pull/72)) | [#5](https://github.com/nathansottung/gps-time/pull/5) |
| Scope | Pre-release | Administrative security | done | not yet verified on a Pi | [#24](https://github.com/nathansottung/gps-time/pull/24) |
| Web UI |  | Serve web/dist at /app/; typed API client; demo adapter | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Web UI |  | Vitest harness + banner-guard tests | done | 26 tests; CI runs them | [#16](https://github.com/nathansottung/gps-time/pull/16) |
| Web UI |  | Ship web/dist in the Pi bundle and install.sh | done | built on the deploying machine; a UI from another version is refused; not yet run on a Pi | [#35](https://github.com/nathansottung/gps-time/pull/35) |
| Web UI |  | Legacy parity: 21 items in dashboard/web-ui-parity.md | done | closed: every item ported (#81–#94) or dropped by the owner (#86, #91) | [#10](https://github.com/nathansottung/gps-time/pull/10) [#62](https://github.com/nathansottung/gps-time/pull/62) [#81](https://github.com/nathansottung/gps-time/pull/81) [#82](https://github.com/nathansottung/gps-time/pull/82) [#99](https://github.com/nathansottung/gps-time/pull/99) |
| Web UI |  | Timing-chain card, source-aware banner, PPS diagnostics page | done |  | [#15](https://github.com/nathansottung/gps-time/pull/15) |
| Review | GPS-001 | Stale TPV re-ingested | done |  | [#1](https://github.com/nathansottung/gps-time/pull/1) |
| Review | GPS-002 | Survey not single-writer | planned | partial | [#1](https://github.com/nathansottung/gps-time/pull/1) |
| Review | GPS-003 | History uncertainty mixes chrony columns | done | named tracking.log columns; offset-SD band, never synthesized; legacy history page fixed | [#93](https://github.com/nathansottung/gps-time/pull/93) |
| Review | GPS-004 | UTC reference shows browser clock | done | the `/app/` clocks show station time (#47); the legacy clock is removed | [#47](https://github.com/nathansottung/gps-time/pull/47) [#99](https://github.com/nathansottung/gps-time/pull/99) |
| Review | GPS-005 | NMEA-only labeled GPS/PPS Stratum 1 | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| Review | GPS-006 | Sync-state edge cases | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| Review | GPS-007 | ± is root dispersion only | done | `max_error_bound_s` = \|sys\| + rootdisp + ½ rootdelay, labeled conditional; System time labeled remaining correction; light distance from the bound; both UIs | [#93](https://github.com/nathansottung/gps-time/pull/93) |
| Review | GPS-008 | Holdover from raw frequency | done | two labelled projections as the review asked (free-running; trained, skew only), plus the profile's; all modeled; the preview table is gone | [#114](https://github.com/nathansottung/gps-time/pull/114) [#135](https://github.com/nathansottung/gps-time/pull/135) |
| Review | GPS-009 | Survey SE labeled repeatability | done | `/app/` labels it SE of the mean (#10, #89); the legacy label is removed | [#10](https://github.com/nathansottung/gps-time/pull/10) [#99](https://github.com/nathansottung/gps-time/pull/99) |
| Review | GPS-010 | Fresh install fails (logsync mode) | done | not Pi-verified | [#1](https://github.com/nathansottung/gps-time/pull/1) |
| Review | GPS-011 | RAM tracking log unbounded | done | 8 MiB cap with rotation via `chronyc cyclelogs` | [#72](https://github.com/nathansottung/gps-time/pull/72) |
| Review | GPS-012 | Tracking-log path fixed at import | done | resolved on every call | [#72](https://github.com/nathansottung/gps-time/pull/72) |
| Review | GPS-013 | SIGTERM skips flush; corrupt config reset | done |  | [#5](https://github.com/nathansottung/gps-time/pull/5) |
| Review | GPS-014 | Root service; unauthenticated GET admin | done | POST-only, admin token, unprivileged service + polkit; not yet verified on a Pi | [#24](https://github.com/nathansottung/gps-time/pull/24) |
| Review | GPS-015 | Privacy hidden leaks via sidereal/almanac | done | plus satellite az/el. Decision 2026-10-02: hidden mode keeps satellite IDs, constellation, C/N₀ and used flags (GNSS health stays visible); see Decisions | [#12](https://github.com/nathansottung/gps-time/pull/12) [#13](https://github.com/nathansottung/gps-time/pull/13) |
| Review | GPS-016 | Unescaped innerHTML in legacy view | done | closed by removing the legacy view | [#99](https://github.com/nathansottung/gps-time/pull/99) |
| Review | GPS-017 | No Host/Origin check | done | Host allowlist, Origin check, JSON-only; not yet verified on a Pi | [#24](https://github.com/nathansottung/gps-time/pull/24) |
| Review | GPS-018 | Per-request fan-out; no limits | planned | partial |  |
| Review | GPS-019 | Demo not isolated from admin | done | demo admin simulated; SAMPLE DATA banner on legacy pages; not yet verified on a Pi | [#12](https://github.com/nathansottung/gps-time/pull/12) [#24](https://github.com/nathansottung/gps-time/pull/24) |
| Review | GPS-020 | Installer unpinned pip / TOFU ephemeris | planned | partial: skyfield pinned in requirements.txt and installed into a venv (`apt-get update` added); preflight for root, chrony and the service groups. Still open: hashed requirements, ephemeris trust-on-first-use, staged install | [#17](https://github.com/nathansottung/gps-time/pull/17) [#25](https://github.com/nathansottung/gps-time/pull/25) [#36](https://github.com/nathansottung/gps-time/pull/36) |
| Review | GPS-021 | Deploy scripts ignore failures | done | exit codes checked; upload SHA-256 verified on the Pi. First run against a Pi (2026-10-04) found the `-t` argument joined to user@host in `deploy-to-pi.ps1`; fixed, with an exact-argv test | [#30](https://github.com/nathansottung/gps-time/pull/30) [#40](https://github.com/nathansottung/gps-time/pull/40) |
| Review | GPS-022 | Bundle builder sweeps secrets | done | archives only git-tracked files; station state and secrets refused even without git; tests | [#100](https://github.com/nathansottung/gps-time/pull/100) |
| Review | GPS-023 | Third-party provenance/licenses | done | sources verified against OpenNGC and d3-celestial; files rebuilt by `tools/build_sky_data.py`; each keeps its license with attribution | [#100](https://github.com/nathansottung/gps-time/pull/100) [#101](https://github.com/nathansottung/gps-time/pull/101) |
| Review | GPS-024 | Precise coordinates in docs | done |  |  |
| Review | GPS-025 | Doc contradictions/staleness | planned | partial: the named stale items fixed; the maturity vocabulary mismatch remains | [#100](https://github.com/nathansottung/gps-time/pull/100) |
| Review | GPS-026 | Extension docs overclaim accuracy | done | the five overclaims rephrased as subject to characterization, pointing to `sdr/timing-model.md` | [#100](https://github.com/nathansottung/gps-time/pull/100) |
| Review | GPS-027 | Quantity/unit labels | done | the remaining labels were in the legacy `dashboard.js`, now removed | [#99](https://github.com/nathansottung/gps-time/pull/99) |
| Review | GPS-028 | Browser clock estimators biased | planned | partial: /app min-RTT | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Review | GPS-029 | Dashboard config hardening | done | closed by removing the saved-layout model (`/api/dashboard*`, `dashboard.py`) | [#99](https://github.com/nathansottung/gps-time/pull/99) |
| Review | GPS-030 | Global object target; non-portable strftime | done | strftime fixed in #12; the sky target is per request and the global is removed in #88 | [#12](https://github.com/nathansottung/gps-time/pull/12) [#88](https://github.com/nathansottung/gps-time/pull/88) [#43](https://github.com/nathansottung/gps-time/pull/43) |
| Review | GPS-031 | No automated tests | done |  | [#1](https://github.com/nathansottung/gps-time/pull/1) |
| Review | GPS-032 | Generator assumes Pi 4 | planned |  |  |
| Repo |  | Dependabot weekly: pip, pnpm, GitHub Actions | done |  | [#17](https://github.com/nathansottung/gps-time/pull/17) |
| Repo |  | Workflow actions pinned to commit SHAs; CI guard | done |  | [#18](https://github.com/nathansottung/gps-time/pull/18) |
| Repo |  | Tag v1.4.0-rc.1 with release notes (rollback target) | done | pre-release; tag on this PR's merge commit | [#22](https://github.com/nathansottung/gps-time/pull/22) |
| Repo |  | Version from the git tag in /api and the UI footer | done | bundles carry gps_time_pi/VERSION; demo reports the real version; CI checks out tags and fails on `unknown` | [#23](https://github.com/nathansottung/gps-time/pull/23) [#26](https://github.com/nathansottung/gps-time/pull/26) |
| Repo |  | Tag v1.4.0-rc.2 with release notes | done | pre-release; tag on this PR's merge commit; rollback target v1.4.0-rc.1 | [#28](https://github.com/nathansottung/gps-time/pull/28) |
| Repo |  | actionlint in CI (invalid workflow files fail) | done |  | [#29](https://github.com/nathansottung/gps-time/pull/29) |
| Repo |  | Tag v1.4.0-rc.3 with release notes | done | pre-release; tag on this PR's merge commit; intended first Pi deploy | [#33](https://github.com/nathansottung/gps-time/pull/33) |
| Repo |  | First Pi deploy of the 1.4 line | done | v1.4.0-rc.6 on 2026-10-04: PPS selected, stratum 1, offset about 300 ns (owner's report). Individual check results not recorded. Nothing merged after rc.6 has run on a Pi | [#34](https://github.com/nathansottung/gps-time/pull/34) [#36](https://github.com/nathansottung/gps-time/pull/36) [#59](https://github.com/nathansottung/gps-time/pull/59) |
| Repo |  | Tag v1.4.0-rc.4 with release notes | done | pre-release; tag on this PR's merge commit; the bundle the deploy checklists target | [#37](https://github.com/nathansottung/gps-time/pull/37) |
| Repo |  | Debian 13 (Trixie, Python 3.13) support: CI matrix 3.11 + 3.13, aarch64 wheel check, installer and docs audit | done | the tested Pi runs Debian 13 (owner, 2026-10-21); Debian 12 untested on hardware | [#38](https://github.com/nathansottung/gps-time/pull/38) |
| Repo |  | Tag v1.4.0-rc.5 with release notes | done | pre-release; tag on this PR's merge commit; the bundle the deploy checklists target | [#39](https://github.com/nathansottung/gps-time/pull/39) |
| Repo |  | Tag v1.4.0-rc.6 with release notes | done | pre-release; tag on this PR's merge commit | [#41](https://github.com/nathansottung/gps-time/pull/41) |
| Repo |  | Astronomy states why it is unavailable (API, legacy widget, install self-check) | done | found on the first Pi build; the Pi's own cause is not yet known | [#43](https://github.com/nathansottung/gps-time/pull/43) |
| Repo |  | NTP client list for the unprivileged service (helper as `_chrony`) | done | found on the first Pi build; cause from chrony's design, not yet confirmed on the Pi | [#44](https://github.com/nathansottung/gps-time/pull/44) |
| Web UI |  | Main clock in local time (zone from position or override, DST, UTC and Unix epoch, 12/24 h) | done | display only; the system stays on UTC. Big clock on the Overview shows the station's time, and says GPS/PPS only when chrony has PPS selected. Not yet seen on a Pi | [#45](https://github.com/nathansottung/gps-time/pull/45) [#47](https://github.com/nathansottung/gps-time/pull/47) |
| Web UI |  | Main clock in local time (zone from position or override, DST, UTC and Unix epoch, 12/24 h) | done | display only; the system stays on UTC. Not yet seen on a Pi | [#45](https://github.com/nathansottung/gps-time/pull/45) |
| Repo |  | chrony polling the station's own address is flagged and never counted as a reference | done | detection and reporting only; the installer now stops chrony taking servers from DHCP (#52). Not yet seen on a Pi | [#48](https://github.com/nathansottung/gps-time/pull/48) |
| Repo |  | NMEA refclock offset: measured recommendation on the PPS diagnostics page | done | report only; the operator edits chrony.conf. chrony's sign convention not yet confirmed on the hardware | [#49](https://github.com/nathansottung/gps-time/pull/49) |
| Repo |  | Legacy dashboard: satellite C/N₀ bars render (CSS display, not CSP); inline-style and CSP tests | done | fix only, no restyle | [#50](https://github.com/nathansottung/gps-time/pull/50) |
| Repo |  | Installer disables chrony's DHCP-provided NTP servers, so the station never polls itself | done | one line of `chrony.conf` commented out, original kept; `GTP_KEEP_DHCP_NTP=1` skips it. Not yet run on a Pi | [#52](https://github.com/nathansottung/gps-time/pull/52) |
| Repo |  | Tag v1.4.0-rc.7 with release notes | done | pre-release; tag on this PR's merge commit | [#53](https://github.com/nathansottung/gps-time/pull/53) |
| TM | §1 | Overlapping ADEV, MDEV and TDEV from PPS offset history | done | from kernel PPS timestamps (the samples behind chrony's PPS offset; chrony reports one only every 16 s). Not yet run on a Pi | [#55](https://github.com/nathansottung/gps-time/pull/55) |
| TM | §1 | Averaging times from 1 s to the longest span the stored data supports | done | 1 s to 2 d; needs 3 averaging times of history (4 for MDEV, TDEV) | [#55](https://github.com/nathansottung/gps-time/pull/55) |
| TM | §1 | Log–log plot with confidence bars; table of key points (1 s, 10 s, 100 s, 1000 s, 1 day) | done | bars for ADEV only; none calculated for MDEV or TDEV | [#55](https://github.com/nathansottung/gps-time/pull/55) |
| TM | §1 | Labeled calculated; states the measurement layer (Linux/chrony view of PPS) | done |  | [#55](https://github.com/nathansottung/gps-time/pull/55) |
| TM | §1 | RAM ring for recent seconds, minute summaries for long spans; no extra SD writes | done | 4 h of seconds, 14 d of minutes; lost on a service restart | [#55](https://github.com/nathansottung/gps-time/pull/55) |
| TM | §1 | Math validated against published reference data sets | done | NIST SP 1065 §12.4: 9-point and 1000-point sets | [#55](https://github.com/nathansottung/gps-time/pull/55) |
| TM | §2 | Optional chrony NTS server | next | after §1, §3, §4, §6; owner: stop and report before starting |  |
| TM | §2 | NTS certificates: local CA and public certificate options documented | next |  |  |
| TM | §2 | NTS off by default; installer flag; chrony unchanged unless the operator turns it on | next |  |  |
| TM | §2 | Dashboard shows NTS state and certificate expiry | next |  |  |
| TM | §3 | TAI | done | TAI − UTC from the leap-second table, not a constant | [#56](https://github.com/nathansottung/gps-time/pull/56) |
| TM | §3 | GPS time, GPS week number and seconds of week | done | plus the 10-bit broadcast week | [#56](https://github.com/nathansottung/gps-time/pull/56) |
| TM | §3 | Modified Julian Date and Julian Date | done | UTC-based | [#56](https://github.com/nathansottung/gps-time/pull/56) |
| TM | §3 | UTC, local time, Unix epoch, local sidereal time in one panel | done | Timing → Time Scales; sidereal time is the value at the last update and follows the privacy mode | [#56](https://github.com/nathansottung/gps-time/pull/56) |
| TM | §3 | Leap-second table source, expiry date, warning well before expiry | done | tzdata's `leap-seconds.list`; warns 60 days before; built-in list with expiry UNKNOWN when no file. Not yet run on a Pi | [#56](https://github.com/nathansottung/gps-time/pull/56) |
| TM | §3 | Next scheduled leap second, if any | done | from the table; chrony's leap status shown beside it | [#56](https://github.com/nathansottung/gps-time/pull/56) |
| TM | §3 | UT1−UTC only from a cached IERS file, labeled external with its date | done | the operator places the file; the station never fetches it | [#56](https://github.com/nathansottung/gps-time/pull/56) |
| TM | §4 | Public servers compared as `noselect` sources | done | any server chrony isn't using to set the clock counts; adding NIST/USNO as `noselect` is an installer option, **off by default** (`GTP_INDEPENDENT_REFS=1`), because it changes chrony's configuration. Not yet run on a Pi | [#57](https://github.com/nathansottung/gps-time/pull/57) |
| TM | §4 | Per-source offset and delay history, labeled external | done | RAM, 1440 points per server; delay through the chrony helper (`ntpdata`), UNKNOWN without it | [#57](https://github.com/nathansottung/gps-time/pull/57) |
| TM | §4 | Disagreement with most independent references flagged; reported as a disagreement, never a cause | done | limit 50 ms (`GTP_REF_DISAGREE_S`); needs two usable references for a majority; doesn't change the timing-chain status | [#57](https://github.com/nathansottung/gps-time/pull/57) |
| TM | §4 | Works without Internet: "no external references reachable" | done |  | [#57](https://github.com/nathansottung/gps-time/pull/57) |
| TM | §5 | PTP grandmaster (`linuxptp`) disciplined from the same PPS | next | last in the spec's order; hardware-dependent; owner: stop and report before starting |  |
| TM | §5 | Hardware-timestamping detection at runtime; "not supported on this hardware" on a Pi 4 | next |  |  |
| TM | §5 | Dashboard shows PTP state, clock class, client count | next |  |  |
| TM | §5 | PTP off by default | next |  |  |
| TM | §6 | Installer disables chrony's DHCP-provided sources | done | not yet run on a Pi | [#52](https://github.com/nathansottung/gps-time/pull/52) |
| TM | §6 | Configured and suggested NMEA offset side by side | done | PPS diagnostics page; the suggestion reads UNKNOWN with the reason when it can't be measured | [#49](https://github.com/nathansottung/gps-time/pull/49) [#58](https://github.com/nathansottung/gps-time/pull/58) |
| TM | §6 | chrony `serverstats` (packets served, dropped) as a service-health view | done | Network page; chrony counts received and dropped, not replies, so "served" is shown as received − dropped. Not yet run on a Pi | [#58](https://github.com/nathansottung/gps-time/pull/58) |
| TM | Tests | Fixture-based tests per item; §1 against known reference values; no live Internet or GNSS | next | partial: §1, §3, §4, §6 done; §2 and §5 not started | [#55](https://github.com/nathansottung/gps-time/pull/55) [#56](https://github.com/nathansottung/gps-time/pull/56) [#57](https://github.com/nathansottung/gps-time/pull/57) [#58](https://github.com/nathansottung/gps-time/pull/58) |
| Repo |  | Tag v1.4.0-rc.8 with release notes | done | pre-release; tag on this PR's merge commit | [#59](https://github.com/nathansottung/gps-time/pull/59) |
| Repo |  | Soak run of v1.4.0-rc.8 on the Pi before v1.4.0 | done | 14 days 20 h, 2026-10-04 to 2026-10-19; real PPS/GNSS outages on 2026-10-17 (about 71 min, one 56-min holdover ending +1.7 µs); v1.4.0 not tagged | [#59](https://github.com/nathansottung/gps-time/pull/59) [#69](https://github.com/nathansottung/gps-time/pull/69) |
| RF | Architecture | RF node (`rf-node/` in this repo): SDR on its own machine, chrony client of the station, SoapySDR, OpenWebRX, GNU Radio, agent | planned |  |  |
| RF | Architecture | Agent: short IQ snippets around detections, tagged with UTC, the node's chrony offset and uncertainty, and frequency reference state; sends events | planned |  |  |
| RF | Architecture | Coordinator on a stronger machine (not the station Pi): calibration and position solving; offline-capable, no cloud | planned |  |  |
| RF | Architecture | Event format shared with the station's event model | planned | the station has a generic event schema (OBS §12a) |  |
| RF | Accuracy | Limits reported with every fix: bandwidth, multipath, geometry, frequency drift | planned | meter-level results are a stretch goal, not a promise |  |
| RF + Feature E (SDR) | Phase 1 | ADS-B 1090 adapter; every RF node listens to ADS-B at 1090 MHz as the shared reference signal | planned | merged row: registry "ADS-B 1090 adapter" and the RF spec's Phase 1 |  |
| RF + Feature F (aviation) | Phase 1 | MLAT metadata/solver: the coordinator solves each node's clock offset and drift continuously | planned | merged row: registry "MLAT metadata/solver" and the RF spec's Phase 1 |  |
| RF | Phase 1 | Per node: offset, drift, residual error, calibration quality score, labeled modeled | planned |  |  |
| RF | Phase 1 | Node positions from each node's own GNSS survey, at the privacy level its owner sets | planned |  |  |
| RF + Feature E (SDR) | Phase 2 | Fox-hunt TOA/TDoA: TDOA on other signals, position estimate from three or more nodes, hyperbola line from two | planned | merged row: registry "Fox-hunt TOA/TDoA research" and the RF spec's Phase 2 |  |
| RF | Phase 2 | Error ellipse and number of nodes with every result, labeled modeled; never a point without its uncertainty | planned |  |  |
| RF | Phase 2 | Optional known beacon at a surveyed spot to check accuracy continuously | planned |  |  |
| RF | Phase 3 | Hunt mode: pick a frequency, nodes capture, live map of estimates and error ellipses | planned |  |  |
| RF | Phase 3 | History of fixes, so the estimate is seen to tighten over time | planned |  |  |
| RF | Rules | Locate only amateur transmissions, beacons, aircraft broadcasts meant to be public, and participating transmitters | planned |  |  |
| RF | Rules | No decoding or storing of private communications' content; timing and signal metadata only, except amateur signals the operator chooses to record | planned |  |  |
| RF | Rules | Never present a position as more certain than the error estimate supports | planned |  |  |
| RF | Rules | Node positions follow the station's privacy modes | planned |  |  |
| RF | Open | Open questions: which SDR and GPSDO; node discovery and authentication; offline map tiles or none | planned | to decide before Phase 1 |  |
| Web UI |  | Retire the legacy pages | done | removed after the rc.11 tag; `/` and the old paths redirect to `/app/` | [#62](https://github.com/nathansottung/gps-time/pull/62) [#99](https://github.com/nathansottung/gps-time/pull/99) |
| Repo |  | Log flush without write amplification; capped RAM log and SD copy | done | appends new lines only; RAM 8 MiB and SD 16 MiB caps, one previous file each; SD copy outside logrotate. Not yet run on a Pi | [#69](https://github.com/nathansottung/gps-time/pull/69) [#72](https://github.com/nathansottung/gps-time/pull/72) |
| Repo |  | Outage evidence kept on the SD card under a size cap | done | one file per outage: event, 10 s timeline, chrony lines ±5 min; 20 MiB / 200 files; no position. Not yet run on a Pi | [#69](https://github.com/nathansottung/gps-time/pull/69) [#73](https://github.com/nathansottung/gps-time/pull/73) |
| Repo |  | PPS polling on its own thread; missed and unread pulses counted separately | done | `pps-poller` thread; no HTTP request polls; poll statistics reported; outage detection unchanged. Whether the rc.8 run's 9 % was real absence or slow polling shows on the next run. Not yet run on a Pi | [#69](https://github.com/nathansottung/gps-time/pull/69) [#70](https://github.com/nathansottung/gps-time/pull/70) |
| Repo |  | Soak run (rc.11) before v1.4.0 | done | CLEAN (`tools/soak_check.py`, criteria of #95): rc.11 from 2026-10-19 21:20 UTC, checked 2026-10-26 after 6 days 17 h, no restart; 0 outages except the installer's at the start; 2 missed pulses, 0 unread, 0 late; round trip 19 ms idle, 31 ms under load; ADEV 1.5 × 10⁻⁶ at 1 s, 2.1 × 10⁻¹¹ at 1 day. Earlier, rc.10 was checked after 2 h 17 min (3 real PPS outages with weak GNSS signal) and replaced | [#76](https://github.com/nathansottung/gps-time/pull/76) [#80](https://github.com/nathansottung/gps-time/pull/80) [#95](https://github.com/nathansottung/gps-time/pull/95) [#124](https://github.com/nathansottung/gps-time/pull/124) |
| Web UI |  | Browser round trip of about 3 s on the Pi | done | server-side: the almanac (about 15 s of CPU, requested every 5 s by the legacy dashboard) now cached and shared; one server's history in `/api/references`; history parsed once a minute. Not yet run on a Pi | [#74](https://github.com/nathansottung/gps-time/pull/74) |
| Web UI |  | Sunrise, noon and sunset shifts shown in h/m/s | done | was signed whole seconds | [#75](https://github.com/nathansottung/gps-time/pull/75) |
| Repo |  | Tag v1.4.0-rc.9 with release notes | done | pre-release; tag on this PR's merge commit; the bundle the deploy checklists target | [#76](https://github.com/nathansottung/gps-time/pull/76) |
| Repo |  | Dependabot: setup-node 7.1.0, tzfpy 2.1.1, 11 web minor/patch updates | done | merged when green; TypeScript 7 (#65) and @types/node 26 (#64) held for the owner | [#66](https://github.com/nathansottung/gps-time/pull/66) [#67](https://github.com/nathansottung/gps-time/pull/67) [#68](https://github.com/nathansottung/gps-time/pull/68) |
| Repo |  | One-page roadmap for outside readers (`ROADMAP.md`), README vision, geophysics roadmap imported | done | every spec and roadmap by phase, with status counts from this file | [#77](https://github.com/nathansottung/gps-time/pull/77) |
| Repo |  | Public release checklist (draft) | done | `public-release-checklist.md`; nothing on it run yet except the commit-identity check; going public is the owner's step | [#77](https://github.com/nathansottung/gps-time/pull/77) |
| Web UI |  | Sunset times as large as sunrise (legacy Sun & daylight widget) | done | sunset was small print under sunrise; now its own bold line, both labeled. `/app/` already showed them at the same size | [#78](https://github.com/nathansottung/gps-time/pull/78) |
| Web UI |  | Screenshot mode: hides coordinates, heights, NTP client addresses and the hostname on screen | done | `/app/` only; header toggle labeled "display only", Alt+Shift+S, remembered per browser. A blurred mask is drawn, never the value. API, exports and the legacy pages unchanged | [#79](https://github.com/nathansottung/gps-time/pull/79) |
| Repo |  | Tag v1.4.0-rc.10 with release notes | done | pre-release; tag on this PR's merge commit; the bundle the deploy checklists target | [#80](https://github.com/nathansottung/gps-time/pull/80) |
| Web UI |  | Station actions in `/app/` Administration: flush logs, restart gpsd/chrony/web, reboot | done | legacy-removal blocker (parity #6). Confirmation step for all but the flush; shows the station's answer. Checked in the demo (simulated); not yet run on a Pi | [#81](https://github.com/nathansottung/gps-time/pull/81) |
| Web UI |  | Position survey reset in `/app/` Administration | done | legacy-removal blocker (parity #7). Shows what would be discarded; typed confirmation (RESET). Checked in the demo; not yet run on a Pi | [#82](https://github.com/nathansottung/gps-time/pull/82) |
| Repo |  | TypeScript 5.9 → 7.0 for the web type check | done | `baseUrl` removed from `web/tsconfig.json` (TS 7 dropped it; `paths` resolve from the file). Type check only: Vite builds without tsc, so the bundle is unchanged | [#65](https://github.com/nathansottung/gps-time/pull/65) |
| Repo |  | Dependabot: no major `@types/node` updates; #64 (22 → 26) closed | done | the types follow the Node the web toolchain runs on (22); raise by hand with it | [#83](https://github.com/nathansottung/gps-time/pull/83) |
| Web UI |  | Legacy removal 1: owner decisions on parity items 1, 2, 4/5, 18, 19, 20, 21 | done | 1: dark + red night, light dropped; 4/5: show/hide modules; 18, 19, 20 dropped. 2 and 21 not decided | [#84](https://github.com/nathansottung/gps-time/pull/84) [#86](https://github.com/nathansottung/gps-time/pull/86) |
| Web UI |  | Legacy removal 2: almanac date navigation, twilight/night bars, moon details (parity 8, 9, 10) | done | Sun & Astronomy → Sun & Moon: date navigation, day and night bars, moon transit altitude and time up. Demos now return both bars. Not yet run on a Pi | [#84](https://github.com/nathansottung/gps-time/pull/84) [#87](https://github.com/nathansottung/gps-time/pull/87) |
| Web UI |  | Legacy removal 3: sky map and object lookup (parity 11, 12) | done | Sky & Objects tab: sky map and object lookup; the target is a request parameter, `_LAST_TARGET` removed (GPS-030); the legacy page sends its own. Not yet run on a Pi | [#84](https://github.com/nathansottung/gps-time/pull/84) [#88](https://github.com/nathansottung/gps-time/pull/88) |
| Web UI |  | Legacy removal 4: survey convergence, ingest counters, remaining chrony detail (parity 14, 15, 16) | done | GNSS & Site → Survey (convergence, session scatter, ingest); Timing → chrony tracking card. Not yet run on a Pi | [#84](https://github.com/nathansottung/gps-time/pull/84) [#89](https://github.com/nathansottung/gps-time/pull/89) |
| Web UI |  | Legacy removal 5: the parity items the owner keeps | done | red night theme (overlay; dim tokens lifted for legibility); Configure → pages and Overview cards show/hide, per browser. Not yet run on a Pi | [#84](https://github.com/nathansottung/gps-time/pull/84) [#90](https://github.com/nathansottung/gps-time/pull/90) |
| Web UI |  | Legacy removal 6: offset chart uncertainty band and symlog axis (parity 13) | done | Timing → Overview offset history: offset-SD band, max-error bound, symlog axis; after #93. Not yet run on a Pi | [#84](https://github.com/nathansottung/gps-time/pull/84) [#94](https://github.com/nathansottung/gps-time/pull/94) |
| Web UI |  | Legacy removal 7: `/` → `/app/`, legacy pages under `/legacy/` with a notice | done | 302 to `/app/` from `/` and every old page path; no `/legacy/` transition (owner: steps 7–9 together) | [#84](https://github.com/nathansottung/gps-time/pull/84) [#99](https://github.com/nathansottung/gps-time/pull/99) |
| Web UI |  | Legacy removal 8: remove the legacy pages and their code | done | templates, static files, CSP exception, layout model, `state`/`fmt`, `units.py` removed; installer cleans upgraded stations | [#84](https://github.com/nathansottung/gps-time/pull/84) [#99](https://github.com/nathansottung/gps-time/pull/99) |
| Web UI |  | Legacy removal 9: close GPS-016, GPS-027, GPS-029, legacy halves of GPS-004/009; update ADR-0004 | done | GPS-016, GPS-027, GPS-029 and the legacy halves of GPS-004/009 closed; ADR-0004 and docs updated | [#84](https://github.com/nathansottung/gps-time/pull/84) [#99](https://github.com/nathansottung/gps-time/pull/99) |
| Web UI |  | Legacy parity items 2 (per-browser zone picker) and 21 (individual throttle flags) | done | 2 dropped (the station-wide override covers it); 21 ported: every condition now and since boot, under-voltage warned | [#86](https://github.com/nathansottung/gps-time/pull/86) [#91](https://github.com/nathansottung/gps-time/pull/91) |
| Repo |  | Dependabot: 5 web minor/patch updates (React 19.3.1, Vitest 5.0.5, lucide-react 1.58, @types/node 22.20.5) | done | merged when green, after a local check against current main | [#85](https://github.com/nathansottung/gps-time/pull/85) |
| Web UI |  | Legacy almanac sky map: E and W labels were swapped | done | east-azimuth objects were drawn on the left under a right-hand "E"; labels now match the projection (N up, E left, as seen looking up). Found while porting the map (#88) | [#92](https://github.com/nathansottung/gps-time/pull/92) |
| Repo |  | Tag v1.4.0-rc.11 with release notes | done | pre-release; tag on this PR's merge commit; the soak candidate and the commit v1.4.0 is to be tagged on | [#95](https://github.com/nathansottung/gps-time/pull/95) |
| Repo |  | `tools/soak_check.py`: read-only pre-release soak check | done | HTTP GETs only; the criteria fixed in #95; exit 0 clean / 1 not / 2 unreadable. Run against rc.10 on 2026-10-19 (not clean, as expected after 2 h) | [#96](https://github.com/nathansottung/gps-time/pull/96) |
| Repo |  | Tag v1.4.0 with release notes (stable) | done | annotated tag on the rc.11 commit `cbd891c` after the clean soak run; GitHub release (not a pre-release) with `releases/v1.4.0.md`. Work merged after #95 is not in it | [#124](https://github.com/nathansottung/gps-time/pull/124) |
| Hardware |  | Dual-band receiver: owner's choices (F9T or F9P, band variant, board, antenna, site, raw-data destination) | next | plan lists them | [#98](https://github.com/nathansottung/gps-time/pull/98) |
| Hardware |  | Dual-band receiver: `zed-f9t` / `zed-f9p` profiles in `generate_config.py` (gpsd speed) and HARDWARE-PROFILES.md | next |  | [#98](https://github.com/nathansottung/gps-time/pull/98) |
| Hardware |  | Dual-band receiver: per-signal satellites in `gps.py` (group by gnssid/svid; count satellites, not signals) | next | today a dual-band receiver would double-count used/visible and C/N₀ | [#98](https://github.com/nathansottung/gps-time/pull/98) |
| Hardware |  | Dual-band receiver: band column and C/N₀ per band in `/app/` satellite views | next |  | [#98](https://github.com/nathansottung/gps-time/pull/98) |
| Hardware |  | Dual-band receiver: receiver identity (module, firmware, protocol) from gpsd | next |  | [#98](https://github.com/nathansottung/gps-time/pull/98) |
| Hardware |  | Dual-band receiver: hardware validation and soak run (deploy log, `tools/soak_check.py`) | next | needs the hardware | [#98](https://github.com/nathansottung/gps-time/pull/98) |
| Hardware |  | Dual-band receiver: error budget with receiver PPS vs the Pi's timestamp spread; TIM-TP qErr logged as research | planned | after the profile | [#98](https://github.com/nathansottung/gps-time/pull/98) |
| Hardware |  | Dual-band receiver: F9T survey-in / fixed-mode state, read-only | planned | if gpsd exposes it | [#98](https://github.com/nathansottung/gps-time/pull/98) |
| Hardware |  | Dual-band receiver: optional raw-data collector (RAWX/SFRBX; RAM ring, 30 s chunks off the SD card, privacy as coordinates) | planned | off by default | [#98](https://github.com/nathansottung/gps-time/pull/98) |
| Hardware |  | Dual-band receiver: coordinator-tier PPP (RTKLIB / PRIDE PPP-AR, IGS products) | planned | with the geophysics roadmap Tier 2 | [#98](https://github.com/nathansottung/gps-time/pull/98) |
| Repo |  | Public release checklist run: history scan, licensing, README and CONTRIBUTING for outside readers | done | no history rewrite needed; owner steps left (dataset sources, the flip, settings) in `public-release-checklist.md` §8 | [#100](https://github.com/nathansottung/gps-time/pull/100) |
| Repo |  | Sky data provenance: Messier from OpenNGC (CC BY-SA 4.0, own file), stars and constellations from d3-celestial (BSD-3), rebuilt and checkable from source | done | stars were d3-celestial, not the Yale BSC; 3 Messier objects and 7 magnitudes replaced with OpenNGC's | [#101](https://github.com/nathansottung/gps-time/pull/101) |
| Repo |  | M102 mapped to NGC 5866 (Spindle Galaxy), marked as departing from OpenNGC; "Spindle" lookup restored | done | owner's decision; the only override in `tools/build_sky_data.py` | [#102](https://github.com/nathansottung/gps-time/pull/102) |
| Repo |  | Coordinator, RF tasking and FM TDOA trial specs, sensor roadmap and reference node parts list imported and indexed | done | owner-provided, copied verbatim; no items scheduled | [#103](https://github.com/nathansottung/gps-time/pull/103) |
| Repo |  | README screenshot: Overview page from the desktop demo in screenshot mode, location privacy rounded | done | `docs/screenshots/overview.png`; checked by eye for coordinates, heights, client addresses and hostname | [#104](https://github.com/nathansottung/gps-time/pull/104) |
| Repo |  | PPS evidence capture script (`scripts/capture-pps-evidence.sh`): read-only archive of PPS devices, sysfs, ppstest, chronyc, kernel messages, config lines, services and gpsd output | done | position removed from gpsd output in every privacy mode (`gps_time_pi/gpsd_redact.py`); ppstest only as root. Not yet run on a Pi | [#105](https://github.com/nathansottung/gps-time/pull/105) |
| Repo |  | PPS evidence capture: read-only button on the PPS diagnostics page producing the same archive | planned | `ROADMAP-OSCILLATOR-AND-MISC.md` §4 | [#105](https://github.com/nathansottung/gps-time/pull/105) |
| Repo |  | Desktop host notes merged into `ROADMAP-DESKTOP-FIELD-APP.md` (tray app serving the same backend and UI, Receivers page, source tiers with ± bounds, leap-second gate, Pi as reference) | done | roadmap stays FUTURE, not scheduled | [#106](https://github.com/nathansottung/gps-time/pull/106) |
| Repo |  | Desktop app decision: tray app running the Python backend (packaged per OS), UI in the default browser; Electron dropped | done | owner decision; ADR-0006; roadmap stays FUTURE | [#107](https://github.com/nathansottung/gps-time/pull/107) |
| Repo |  | README reworked for first-time visitors: what it is, quick start, tested vs expected hardware, planned hardware, features, measured accuracy only, docs | done | owner's order; measured figures from the rc.8 and rc.10 checks; accuracy against UTC stated as not measured | [#108](https://github.com/nathansottung/gps-time/pull/108) |
| EXT | Order 1 | Interfaces, manifest, schemas, `ctx` and the module loader, with no behaviour change to the station | done | `gps_time_pi/modkit/` (interfaces 1.0.0, manifest checks, ctx, loader and host, CLI), `schemas/` (observation, result, manifest v1); the web service doesn't use it yet | [#110](https://github.com/nathansottung/gps-time/pull/110) [#117](https://github.com/nathansottung/gps-time/pull/117) |
| EXT | Order 2 | `tools/new_module.py` and the `docs/modules/` guide | done | `tools/new_module.py` (source, reference, analysis, ui; generated tests pass as created); guide `docs/modules/` | [#110](https://github.com/nathansottung/gps-time/pull/110) [#117](https://github.com/nathansottung/gps-time/pull/117) |
| EXT | Order 3 | `source-weather` example module | next | owner, 2026-10-21 | [#110](https://github.com/nathansottung/gps-time/pull/110) |
| EXT | Order 4 | `reference-adsb` and `reference-broadcast-towers` modules | done | both experimental (#134, #136) | [#110](https://github.com/nathansottung/gps-time/pull/110) [#134](https://github.com/nathansottung/gps-time/pull/134) [#136](https://github.com/nathansottung/gps-time/pull/136) |
| EXT | Order 4a | `reference-adsb` module: aircraft on 1090 MHz (ADS-B 1090ES) and 978 MHz (UAT) from a local decoder's `aircraft.json` as self-reported references; MLAT/TIS-B/ADS-R refused; checks counted by reason; predicted delay with a 95 % bound; privacy via `ctx.site()`; synthetic fixtures | done | owner, 2026-10-26; experimental; not yet run against a live decoder; no measured arrival times yet (needs an SDR source) | [#134](https://github.com/nathansottung/gps-time/pull/134) |
| EXT | Order 4b | `reference-broadcast-towers` module: FM, ATSC and NOAA Weather Radio transmitters from an offline cache built by the operator (source, SHA-256 and dates kept; centre rounded to 0.1°); licensed only, by service and range; predicted delay with refractivity and a 95 % bound; line of sight inferred from HAAT; privacy via `ctx.site()`; synthetic fixtures | done | owner, 2026-10-26; experimental; no network permission; transmitter emission timing isn't modelled (compare differences) | [#136](https://github.com/nathansottung/gps-time/pull/136) |
| EXT | Order 4c | Real tower cache: `fetch.py` downloads the national FCC FM/TV text lists and NOAA's `ccl-data.js` (no location in any request, manifest with SHA-256); the FCC text read by position from the FCC's own key (NAD83); the NOAA list parsed; DTS and analog left out, ATSC 3.0 flagged; the licensed record wins a duplicate; real caches git-ignored | done | owner, 2026-10-26; a real cache was built and checked off the station, not deployed | [#138](https://github.com/nathansottung/gps-time/pull/138) |
| EXT | Order 5 | `analysis-tower-delay-check` module | done | research; synthetic data only: finds each tower's known waveform in a PPS-marker-timed observation file by cross-correlation and compares the delay with `reference-broadcast-towers`' prediction; absolute or common-offset mode (weighted median); verdicts inferred, never a cause; `result/1`; runs from its CLI (the host runs only sources). Waveforms replaced in #139 (row 5b). Not yet: a real capture | [#110](https://github.com/nathansottung/gps-time/pull/110) [#137](https://github.com/nathansottung/gps-time/pull/137) |
| EXT | Order 5b | Real waveforms for the tower delay check: the ATSC A/53 field sync (665 known symbols; PN511 and PN63 checked against their generators; 8-VSB model with pilot and α = 0.1152) and FM correlation (site a's capture, isolated to ±100 kHz, found in site b's); one capture per tuning; template per rate and tuning (tuner follows the sample clock); peak by windowed-sinc interpolation (the parabola was biased up to 50 ns); modes `tdoa` and `tdoa_common_offset` (emission cancels); numpy; CI runs the tests in the station venv | done | owner, 2026-10-26; research; synthetic captures only | [#139](https://github.com/nathansottung/gps-time/pull/139) |
| EXT | Order 6 | Move existing optional features (sky tools, references page) to modules where it simplifies them | next | owner, 2026-10-21 | [#110](https://github.com/nathansottung/gps-time/pull/110) |
| Repo |  | Extensibility (module architecture) spec imported; README "Where this is going" section | done | owner-provided, copied verbatim | [#110](https://github.com/nathansottung/gps-time/pull/110) |
| EXT | Safety | Module safety: off by default, own unprivileged process, declared permissions only, resource caps, never affects timing | done | own process per module as `gps-time-mod`; memory and file-size limits; CPU share, resident memory and output watched and killed over caps; storage size and write-rate caps; guard for network, devices, writes, processes, ctypes; hardened supervisor unit installed, not enabled. Open: one user per module | [#111](https://github.com/nathansottung/gps-time/pull/111) [#117](https://github.com/nathansottung/gps-time/pull/117) [#120](https://github.com/nathansottung/gps-time/pull/120) |
| EXT | API | API stability: semver for interface, manifest and schemas; loader refuses incompatible modules | done | semver `INTERFACE_VERSION` 1.0.0; manifests state `interface = "M.m"`; the loader refuses incompatible modules with the reason | [#111](https://github.com/nathansottung/gps-time/pull/111) [#117](https://github.com/nathansottung/gps-time/pull/117) |
| EXT | Receiver | Receiver profiles as `receiver` modules; existing hardware profiles move into this form | planned |  | [#111](https://github.com/nathansottung/gps-time/pull/111) |
| EXT | Licence | Data licence: code MIT; shared observations CC BY 4.0 by default, per station | planned |  | [#111](https://github.com/nathansottung/gps-time/pull/111) |
| EXT | Governance | `CODE_OF_CONDUCT.md`, `MAINTAINERS.md`, module maturity rule (experimental → supported) | planned |  | [#111](https://github.com/nathansottung/gps-time/pull/111) |
| OBSF | Order 1 | Format: `gpstime:` extension schema, writer, reader, validator | done | `gps_time_pi/obsformat.py`, `schemas/sigmf-gpstime.v1.json`; signatures wait for station keys (null, validator warns) | [#111](https://github.com/nathansottung/gps-time/pull/111) [#118](https://github.com/nathansottung/gps-time/pull/118) |
| OBSF | Order 1b | Converters to miniSEED and WAV | done | `gps_time_pi/convert.py`: WAV 16-bit with a SigMF sidecar (times exact), miniSEED 2 (record times to 1 µs, measured rate in blockette 100, gaps kept); checked against ObsPy 1.5.1 | [#118](https://github.com/nathansottung/gps-time/pull/118) [#122](https://github.com/nathansottung/gps-time/pull/122) |
| OBSF | Order 2 | Rolling buffers on the station for enabled sensors | planned | tasking part | [#111](https://github.com/nathansottung/gps-time/pull/111) |
| OBSF | Order 3 | Single-owner capture requests (Stage A) | planned | tasking part | [#111](https://github.com/nathansottung/gps-time/pull/111) |
| OBSF | Order 4 | Generic pick, correlate and locate analyses | planned |  | [#111](https://github.com/nathansottung/gps-time/pull/111) |
| OBSF | Order 5 | Trusted groups and third parties (Stages B and C) | planned | tasking part | [#111](https://github.com/nathansottung/gps-time/pull/111) |
| Repo |  | Observation format and tasking spec imported; module architecture spec updated (safety, API stability, receiver modules, data licence, governance) | done | owner-provided, copied verbatim | [#111](https://github.com/nathansottung/gps-time/pull/111) |
| Repo |  | README "Where this is going" replaced by the owner's update (aircraft as moving references; build on it as modules) | done | the module-guide link points to the spec until `docs/modules/README.md` exists | [#112](https://github.com/nathansottung/gps-time/pull/112) |
| Scope | Gap 1 | Accuracy validation plan against UTC (two independent receivers with a scope or time-interval counter, a GPSDO, or a dual-band second station with known cable delays) | planned | needed before any claim about accuracy to UTC. partial: the system clock against the receiver's PPS on a wire (#126); PPS against UTC still needs a second reference | [#113](https://github.com/nathansottung/gps-time/pull/113) [#126](https://github.com/nathansottung/gps-time/pull/126) |
| Scope | Gap 1a | Second pulse: a GPIO edge at each system-clock second, and a tool comparing it with PPS from a scope or counter CSV | done | owner, 2026-10-26; `gps_time_pi/secpulse.py` (GPIO uAPI v2, refuses the PPS line, RAM only unless `--log`), `tools/pps_compare.py` (bound without a pulse log, modeled offset with one), guide `validation/second-pulse.md`. Not yet run on the station | [#126](https://github.com/nathansottung/gps-time/pull/126) |
| Scope | Gap 2 | Antenna and cable delay calibration for dual-band hardware | planned |  | [#113](https://github.com/nathansottung/gps-time/pull/113) |
| Scope | Gap 3 | CPU clock experiment: fixed 600 vs 1500 MHz, with Stability page numbers | planned |  | [#113](https://github.com/nathansottung/gps-time/pull/113) |
| Scope | Gap 4 | Stability history persistence across restarts (minute summaries on SD) | planned |  | [#113](https://github.com/nathansottung/gps-time/pull/113) |
| Scope | Gap 5 | Kiosk full-screen clock, mobile layout, installable offline app (PWA) | planned |  | [#113](https://github.com/nathansottung/gps-time/pull/113) |
| Scope | Gap 6 | Acoustic thunder ranging as a sensor-fusion module (microphones + VLF start time + weather) | planned | extends Feature H "Acoustic thunder timing" | [#113](https://github.com/nathansottung/gps-time/pull/113) |
| Scope | Gap 7 | Network partners: contributing data to Blitzortung, Raspberry Shake, Global Meteor Network, HiSPARC | planned |  | [#113](https://github.com/nathansottung/gps-time/pull/113) |
| Scope | Gap 8 | Docs website and a prebuilt Pi image or one-line installer | planned |  | [#113](https://github.com/nathansottung/gps-time/pull/113) |
| Scope | Gap 9 | Legal and safety notes for RF receiving and data sharing | planned |  | [#113](https://github.com/nathansottung/gps-time/pull/113) |
| Repo |  | Full scope review added (`SCOPE-REVIEW.md`); its section 7 gaps added as planned rows | done | owner-provided, copied verbatim | [#113](https://github.com/nathansottung/gps-time/pull/113) |
| OSC | §1 fit | Oscillator profile: fit frequency vs temperature plus slow aging from the oscillator log; store fit quality and the data span covered | done | `gps_time_pi/oscprofile.py`: linear or quadratic in temperature, optional aging, chosen by BIC; standard errors, residual RMS, R², outliers, range and span; over the whole file (≤ 90 days); `/api/oscillator` → `profile` (modeled); Timing → Oscillator card and curve. Not yet run on a Pi | [#114](https://github.com/nathansottung/gps-time/pull/114) [#133](https://github.com/nathansottung/gps-time/pull/133) |
| OSC | §1 holdover | Oscillator profile: modeled holdover projection beside the simple one (labeled modeled; never a guarantee); closes GPS-008 | done | `oscprofile.holdover()`: three projections, all modeled, never a guarantee; extrapolation flagged; `/api/oscillator` → `holdover`; Timing → Overview and Oscillator | [#114](https://github.com/nathansottung/gps-time/pull/114) [#135](https://github.com/nathansottung/gps-time/pull/135) |
| OSC | §1 export | Oscillator profile: export/import as one JSON file, surviving a reflash | done | GET `/api/oscillator/profile` (download; profile, fit bins, metadata; no position, no raw serial); POST it back with the admin token (2 MB cap on that route); Timing → Oscillator → Profile File | [#114](https://github.com/nathansottung/gps-time/pull/114) [#135](https://github.com/nathansottung/gps-time/pull/135) |
| OSC | §1 board | Oscillator profile: board binding by serial hash on import (match: use; mismatch: warn, keep for reference, start a new profile) | done | match: bins merged into the fit, file kept next to the log; mismatch or unverifiable: kept for reference only (refitted for display, never used); checked again at every start | [#114](https://github.com/nathansottung/gps-time/pull/114) [#135](https://github.com/nathansottung/gps-time/pull/135) |
| OSC | §1 meta | Oscillator profile: record board model, receiver profile and software version in the file | done | board serial hash and model, receiver driver and firmware, software version, export time | [#114](https://github.com/nathansottung/gps-time/pull/114) [#135](https://github.com/nathansottung/gps-time/pull/135) |
| Repo |  | RF reference signals and trust spec imported; oscillator profile moved to next; scope review corrections | done | owner-provided spec, copied verbatim | [#114](https://github.com/nathansottung/gps-time/pull/114) |
| PPSM | Research 1 | Synthetic detector, sub-sample interpolation and time model (pulses, drops, drift); runs in CI with no hardware | done | module `modules/sdr-pps-marker/`; synthetic results only | [#115](https://github.com/nathansottung/gps-time/pull/115) |
| PPSM | Research 2 | Bench, one SDR: marker visibility across bands and attenuation, detection rate, sample-rate error over hours and temperature | planned | research; needs the injection build; the capture software is ready (row 2a) | [#115](https://github.com/nathansottung/gps-time/pull/115) |
| PPSM | Research 2a | Live capture software: an `rtl_tcp` client (a module may not start processes or use ctypes), one connection per dwell, the numpy detector (same markers as the reference detector), the time model, a host-clock ambiguity check, timed windows as cu8 observation files in RAM storage (newest kept); `system/gps-time-rtl-tcp.service` (installed by `GTP_SDR=1` since #145); a fake `rtl_tcp` for tests and desktop trials; storage `names()`/`delete()` in the kit | done | owner, 2026-10-26; research; tested against the fake server only; not run on hardware | [#140](https://github.com/nathansottung/gps-time/pull/140) |
| PPSM | Research 3 | Bench, two SDRs through a splitter: arrival-time difference zero within the stated uncertainty (first real timing figure) | planned | research | [#115](https://github.com/nathansottung/gps-time/pull/115) |
| PPSM | Research 4 | Scope or time-interval counter check against the PPS line | planned | research | [#115](https://github.com/nathansottung/gps-time/pull/115) |
| PPSM | Research 5 | Publish schematic, BOM, measured results; `time_source: pps_marker` with measured uncertainty | planned | research | [#115](https://github.com/nathansottung/gps-time/pull/115) |
| PPSM | MLAT 1 | One node, ADS-B: arrival times against positions reported by aircraft (consistency check) | planned | research | [#115](https://github.com/nathansottung/gps-time/pull/115) |
| PPSM | MLAT 2 | Two nodes, ADS-B TDOA: residuals against reported positions | planned | research | [#115](https://github.com/nathansottung/gps-time/pull/115) |
| PPSM | MLAT 3 | Three or more nodes: MLAT for Mode S without position; cross-check ADS-B | planned | research | [#115](https://github.com/nathansottung/gps-time/pull/115) |
| PPSM | MLAT 4 | Same timing for FM/ATSC towers, the FM two-tower trial and fox hunts | planned | research | [#115](https://github.com/nathansottung/gps-time/pull/115) |
| PPSM | MLAT 5 | Coordinator integration: solver module, error ellipses, optional feed to MLAT networks | planned | research | [#115](https://github.com/nathansottung/gps-time/pull/115) |
| PPSM | Outputs | Observation files: `time_source = pps_marker`, measured uncertainty, SDR clock error, blanked marker windows | done | `sdr_pps_marker/observation.py`; one capture per marker interval, file times match the time model to the ns | [#115](https://github.com/nathansottung/gps-time/pull/115) [#118](https://github.com/nathansottung/gps-time/pull/118) |
| PPSM | Health | Dashboard health: markers per minute, sample-rate error, dropped-sample events | done | shown on Administration → Experimental modules as the module's latest observation (labeled values, age); not on the Overview | [#118](https://github.com/nathansottung/gps-time/pull/118) [#142](https://github.com/nathansottung/gps-time/pull/142) |
| PPSM | Kit | Open-hardware marker injector board (schematic, BOM; possibly pre-assembled) | planned | only after bench results | [#115](https://github.com/nathansottung/gps-time/pull/115) |
| Repo |  | PPS timestamps as integer nanoseconds end to end: `pps.read_assert` returns int ns from the kernel's text, the monitor keeps int ns and int-ns intervals, `pps.phase_ns` finds each phase in integer arithmetic for `/api/stability` and the web SDR usage log; floats refused (`require_ns`). Before, a float of the whole timestamp stepped in about 238 ns | done | owner, 2026-11-04; API shapes unchanged | [#153](https://github.com/nathansottung/gps-time/pull/153) |
| Repo |  | Optional web SDR (`GTP_WEBSDR=1`, ADR-0009): OpenWebRX+ from its repository (key pinned) on the loopback, a password gate on the LAN port (private ranges only, fails closed, backoff), the 1090 MHz dongle shared with readsb (stopped while it runs, started again after), never enabled at boot, session limit; Start/Stop (admin token, polkit start/stop of that unit only) and the link on Radio & SDR → Devices; usage log `/api/websdr` (CPU, temperature, PPS jitter per minute, before and during, one line per session on the SD card) | done | owner, 2026-11-04; tested with stub commands and on the loopback; not yet run on a Pi | [#152](https://github.com/nathansottung/gps-time/pull/152) |
| Repo |  | Station capability record (`GET /api/capability`): station ID from the key, version, timing state, receiver, SDR roles, location only at rounded precision; opt-in sky-quality summary (`sky_quality_share`, off by default, never in hidden mode) in the record and the diagnostics export; Administration → Capability record. Not sent anywhere yet | done | owner, 2026-10-27 | [#148](https://github.com/nathansottung/gps-time/pull/148) |
| Repo |  | Soak record: the SDR load beside the criteria (`tools/soak_check.py` `[REC]` lines: each SDR unit's CPU now and since start, memory, restarts; load averages; RTL-SDRs on USB and the throttled flags; SoC temperature; chrony PPS std dev, RMS offset, ADEV and TDEV at 1 s); UNKNOWN on a station without `/api/sdr`; criteria unchanged | done | owner, 2026-10-27 | [#147](https://github.com/nathansottung/gps-time/pull/147) |
| Repo |  | The SDR modules from Administration: install.sh installs the bundled modules (all off); `GTP_SDR=1` enables the supervisor; module settings from the page (`POST /api/setting {module, config}`: manifest keys and types, 8 KiB, no positions); readiness per SDR module (UNKNOWN for the injected PPS); SDR receivers card (`/api/sdr`: units, CPU and memory from cgroups, dongles from sysfs, feed ages and counts, read only) | done | owner, 2026-10-27; not yet run on a Pi | [#146](https://github.com/nathansottung/gps-time/pull/146) |
| Repo |  | Installer: optional SDR stack (`GTP_SDR=1`): rtl-sdr with `gps-time-rtl-tcp`, readsb (1090 MHz), dump978-fa and skyaware978 (978 MHz) built at a pinned commit, a localhost drop-in for the module service; one RTL-SDR per role by serial; loopback only or no network; no position given to any decoder; `GTP_SDR=0` removes the units | done | owner, 2026-10-27; tested with stub commands (`tests/test_sdr_stack.py`); not yet run on a Pi | [#145](https://github.com/nathansottung/gps-time/pull/145) |
| Repo |  | `modules/` directory; module tests run with the station's (`tests/test_modules.py`); CI compiles `modules/` | done | first module: `sdr-pps-marker` | [#115](https://github.com/nathansottung/gps-time/pull/115) |
| Repo |  | Coordinator skeleton for TrueNAS SCALE (`coordinator/`, ADR-0008): signed join and event messages with the station key, pending until approved, replay refused, positions never stored, SQLite with retention, one container | done | owner, 2026-10-26; not yet run on TrueNAS; TLS, transport, station sender and event schema open | [#127](https://github.com/nathansottung/gps-time/pull/127) |
| Repo |  | Bench kit list (`validation/bench-kit.md`) | done | owner, 2026-10-26; examples, no prices | [#127](https://github.com/nathansottung/gps-time/pull/127) |
| Repo |  | Second-station guide (`deploy/second-station.md`): setups, build differences, comparing over NTP, second pulses and later the coordinator | done | owner, 2026-10-26; not yet done on hardware | [#127](https://github.com/nathansottung/gps-time/pull/127) |
| Repo |  | Tag v1.5.0-rc.1 (pre-release) on the merge commit of the release notes PR, with the deploy command | done | owner, 2026-10-26; `releases/v1.5.0-rc.1.md`; not yet deployed | [#128](https://github.com/nathansottung/gps-time/pull/128) |
| Repo |  | Soak run of v1.5.0-rc.1 on the Pi before v1.5.0 (owner deploys; `tools/soak_check.py --expect 1.5.0-rc.1` after three days) | done | NOT CLEAN after 3.01 days (check 2026-10-29 18:30 UTC): four PPS outages, 8,596 s in all (outages criterion), and 8,906 missed pulses (pulses criterion); the other criteria OK. v1.5.0 not tagged; skipped by the owner 2026-11-04, and v1.6.0-rc.1 cut instead (`development/raspberry-pi-deploy.md` → "Soak run of v1.5.0-rc.1", with the USB and outage-timing follow-ups) | [#128](https://github.com/nathansottung/gps-time/pull/128) [#132](https://github.com/nathansottung/gps-time/pull/132) [#149](https://github.com/nathansottung/gps-time/pull/149) |
| Repo |  | Tag v1.6.0-rc.1 (pre-release) from `main` on the merge commit of the release notes PR; v1.5.0 skipped (owner: the soak outages taken as this unit's antenna and site limit); the outage-timing comparison since 2026-10-04 in the soak record | done | owner, 2026-11-04; `releases/v1.6.0-rc.1.md`; not yet deployed | [#154](https://github.com/nathansottung/gps-time/pull/154) |
| Repo |  | DVB-T driver blacklist: `scripts/rtl-dvb-blacklist.sh`, run by `GTP_SDR=1` and `GTP_WEBSDR=1`, writes `/etc/modprobe.d/gps-time-rtl-sdr.conf` (`rtl2832_sdr`, `dvb_usb_rtl28xxu`, `rtl2832`, `rtl2830`) and unloads them now; shared modules never named; kept on removal | done | owner, 2026-11-04 (rc.3 list); the station's dongle was held by the driver | [#157](https://github.com/nathansottung/gps-time/pull/157) |
| Repo |  | Dongle roles by serial across both installers, at most 3 RTL-SDRs on a Pi 4 (`scripts/dongle-roles.sh`, refused before anything changes); `/api/sdr` roles include the web SDR and a `limit` object; the limit line on Administration → SDR receivers | done | owner, 2026-11-04 (rc.3 list) | [#159](https://github.com/nathansottung/gps-time/pull/159) |
| Repo |  | Deploy scripts pass `install.sh`'s `GTP_*` flags from the environment (`sudo env <flags> bash install.sh`): an allowlist kept equal to what `install.sh` and its scripts read (tested), values checked before anything is built or uploaded, other `GTP_*` names listed, not passed | done | owner, 2026-11-04 (rc.3 list) | [#156](https://github.com/nathansottung/gps-time/pull/156) |
| Repo |  | Pi bundle ships `modules/` (install.sh has installed them since #146); `tests/test_bundle_install.py` builds and extracts the bundle and runs its `install.sh` to the end in a temporary root (stub system commands, unknown absolute paths refused); ADR-0007 amended; tag v1.6.0-rc.2 | done | owner, 2026-11-04, after rc.1's install failed at `cp -r modules`; not yet deployed | [#155](https://github.com/nathansottung/gps-time/pull/155) |
| Repo |  | Soak run of v1.6.0 (now v1.6.0-rc.2) on the Pi before v1.6.0 (`tools/soak_check.py --expect` the deployed candidate after three days; criteria unchanged) | planned | owner, 2026-11-04: **the formal soak waits for the antenna move.** The run after this deploy is not the soak: it is for sector data (C/N₀ by sky sector) and web SDR testing, so `GTP_WEBSDR=1` may be on. The formal 72-hour run starts at a deploy after the antenna is moved, without `GTP_SDR` or `GTP_WEBSDR` | |
| Repo |  | Plan v1.5.1: the UI release after the v1.5.0 soak (scope, gates, before-rc items, checks on the Pi) | done | owner, 2026-10-26; `releases/v1.5.1-plan.md` | [#141](https://github.com/nathansottung/gps-time/pull/141) |
| Repo |  | v1.5.1 before rc.1: module output in the web UI (each enabled module's latest observation and result on Administration, from the supervisor's status file) | done | closes the v1.5.0 known issue and the PPSM Health row's "needs the module UI hook" | [#141](https://github.com/nathansottung/gps-time/pull/141) [#142](https://github.com/nathansottung/gps-time/pull/142) |
| Repo |  | v1.5.1 before rc.1: the PPS evidence test matches wall-clock timestamps against the example position's digits (flaky; failed one run of #140) | done | strip timestamps before the position check | [#141](https://github.com/nathansottung/gps-time/pull/141) [#143](https://github.com/nathansottung/gps-time/pull/143) |
| Repo |  | v1.5.1 before rc.1: desktop UI review of the candidate (demo at 360/768/1280/1920 px, both themes, screenshot mode) | done | bugs only; six fixed (stretched timeline labels, a category axis on the holdover scatter, wrapped holdover values, repeated date ticks, two stale legacy-page mentions); not changed, for the owner: night-theme legibility of green/cyan values, the server's listen queue of 5 under many browsers (GPS-018); `dashboard/ui-review-2026-10-27.md`; opt-in `test:station` | [#141](https://github.com/nathansottung/gps-time/pull/141) [#144](https://github.com/nathansottung/gps-time/pull/144) |
| Repo |  | Tag v1.5.1-rc.1 (pre-release) on the merge commit of its release-notes PR | planned | only after a clean v1.5.0 check | [#141](https://github.com/nathansottung/gps-time/pull/141) |
| Repo |  | Soak run of v1.5.1-rc.1 on the Pi before v1.5.1 (owner deploys; `tools/soak_check.py --expect 1.5.1-rc.1` after three days) | planned | criteria of #95, unchanged | [#141](https://github.com/nathansottung/gps-time/pull/141) |
| Repo |  | The soak rule written down: release candidates, the 72 h run and its validity, the check and its criteria, the decision, who does what, the record (`releases/README.md`); a test keeps its criteria table equal to the tool's | done | owner, 2026-10-26 | [#132](https://github.com/nathansottung/gps-time/pull/132) |
| Web UI |  | Responsive layout: every `/app/` page from 360 to 1920 px and at half-screen widths (drawer navigation below 1024 px, container-query grids, wrapping rows, tables and tabs scroll inside their card), page in the URL hash; Playwright layout audit in CI | done | owner, 2026-10-26; Guidelines → Layout → Narrow screens | [#129](https://github.com/nathansottung/gps-time/pull/129) |
| Web UI |  | Design pass against Guidelines.md: contrast (WCAG AA), type scale, letter-spacing, tabular figures, focus states, loading/empty/unknown states, colour tokens, radii; checked in CI (`e2e/design.spec.ts`) | done | owner, 2026-10-26; 16 deviations listed in `dashboard/design-review-2026-10-26.md`; text tokens lightened | [#130](https://github.com/nathansottung/gps-time/pull/130) |
| Web UI |  | Linear/log toggle on every time-offset and stability chart (Overview Δt, offset history, holdover, reference offset and delay, ADEV/MDEV/TDEV), remembered per chart in the browser; time ticks in ns/µs/ms/s | done | owner, 2026-10-26; symmetric log for signed offsets; τ stays logarithmic | [#131](https://github.com/nathansottung/gps-time/pull/131) |
| Repo |  | Write-up of the 2026-10-17 outages (`incidents/2026-10-17-pps-gnss-outages.md`) | done | owner, 2026-10-26; from the records made at the time; cause not established | [#127](https://github.com/nathansottung/gps-time/pull/127) |
| PPSM | Research 1b | Conservative uncertainty on short runs: 95 % upper bound on marker scatter (quadratic fit per block, chi-square) plus an interpolation floor; 95 % coverage tested over 200 seeded runs | done | owner; coverage 180/180 runs with a time (synthetic) | [#116](https://github.com/nathansottung/gps-time/pull/116) |
| EXT | Safety+ | One user per module (all modules share `gps-time-mod` today) | planned | after module isolation | [#120](https://github.com/nathansottung/gps-time/pull/120) |
| EXT | Admin | Experimental modules switch on Administration (admin token); modules stay off and are turned on one by one | done | owner, 2026-10-26; `modkit/settings.py`, `GET /api/modules`, `POST /api/setting`; switching clears `modules_enabled`; the supervisor re-reads the config; state UNKNOWN unless the supervisor reports | [#125](https://github.com/nathansottung/gps-time/pull/125) |
| OBSF | Signing | Station key pair (Ed25519) made at install; observation files signed; signatures verified in the validator (trusted list optional) | done | `gps_time_pi/station_key.py`; new dependency `cryptography` | [#121](https://github.com/nathansottung/gps-time/pull/121) |
