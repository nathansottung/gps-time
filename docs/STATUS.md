# Project status

Every spec item, roadmap feature and independent-review finding, with its status and the PRs that delivered it.

**Update this file in every PR** (rule in `CLAUDE.md`):
- Move rows whose status changed.
- Add the PR link.
- Re-order the next-5 list when it changes.

Last updated: 2026-10-05 (docs/release-v1.4.0-rc.7, #53). Built from the specs, `roadmap/feature-registry.md`, `roadmap/current-scope.md` and `review/GPS-Time-Independent-Review-2026-09-27.md`, each checked against the code and tests.

## Next 5 tasks, in order

1. **chrony history semantics** (GPS-003, GPS-007): correct tracking-log columns; label ± honestly (root dispersion is not total uncertainty). Pre-release blocker.
2. **PPS history views** (CHG "Historical UI", OBS §6): backend rollups of the event history (uptime, last/longest outage, 24 h/7 d counts, availability %, total unavailable time) and the six-category state timeline.
3. **Bounded tracking log** (GPS-011, GPS-012): cap the RAM chrony tracking log with atomic rotation; resolve its path at runtime, not at import. Pre-release blocker ("Bounded persistence").
4. **Deploy scripts stop on failure** (GPS-021): check every native exit code, verify the uploaded archive's SHA-256 on the Pi before `install.sh`, no fixed `/tmp` name. **Must land before any Pi deploy** (owner, 2026-10-02). *Done in [#30](https://github.com/nathansottung/gps-time/pull/30).*

## Decisions

- **2026-10-02, location privacy, `hidden` mode:** the station drops satellite azimuth and elevation, sun/moon/sky times and sidereal time. It **keeps** satellite IDs, constellation, C/N₀ and used flags, so GNSS health stays visible. The residual (which satellites are tracked) narrows position only coarsely. Owner decision; see `api/endpoints.md` privacy notes.
- **2026-10-02, order:** administrative security before shipping `web/dist` to the Pi. Administrative security was done in #24.
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
| ADD | `specs/ADDENDUM-SKY-SOLAR-SATELLITE.md` |
| Feature A–J | `roadmap/feature-registry.md` sections |
| Scope | `roadmap/current-scope.md` |
| Web UI | the React port (`web/`, ADR-0004) |
| Review | `review/GPS-Time-Independent-Review-2026-09-27.md` |
| Repo | repository tooling, CI and releases (owner requests) |

Future, unscheduled work outside this table: `roadmap/ROADMAP-DESKTOP-FIELD-APP.md`, `roadmap/ROADMAP-SDR-RF-OBSERVATORY.md` (scoping), `roadmap/ROADMAP-WEB-UPDATES.md` (FUTURE, low priority; not before the station has run stably on v1.4.0), `roadmap/ROADMAP-OSCILLATOR-AND-MISC.md` (FUTURE; none blocks v1.4.0).

**Totals:** 373 rows: 187 done, 0 in progress, 21 next, 165 planned.

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
| OBS | §7 | Time-to-1 µs…1 s holdover estimates | planned | partial: legacy raw-ppm projection (GPS-008) |  |
| OBS | §8 | Integrity metric history + baselines | planned |  |  |
| OBS | §9 | RF interference detection | planned |  |  |
| OBS | §10 | Spoofing / position anomaly detection | planned |  |  |
| OBS | §11 | GNSS↔PPS correlation | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §12a | Generic event schema | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §12b | Fifteen event types | planned | partial: PPS_OUTAGE only | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| OBS | §13 | ±5 min forensic evidence window | planned |  |  |
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
| ADD | §1 | Earth-shadow umbra/penumbra model | planned |  |  |
| ADD | §2 | Zenith satellite-shadow metric | planned |  |  |
| ADD | §3 | Illumination sky map | planned |  |  |
| ADD | §4 | Starlink contamination indicator | planned |  |  |
| ADD | §5 | Satellite ephemeris layer | planned |  |  |
| ADD | §6 | Astrophotography darkness card | planned | partial: night/twilight times; no current state | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| ADD | §7 | Solar time (AST, MST, EoT) | planned | partial: solar noon only | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| ADD | §8 | Solar geometry list | planned | partial: rise/set/noon/twilight/daylight | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| ADD | §9 | Solar-energy estimate | planned |  |  |
| ADD | §10 | Learned sky-obstruction map | planned |  |  |
| ADD | §11 | Integrity + obstruction correlation | planned |  |  |
| ADD | §12 | Observing-conditions dashboard | planned |  |  |
| ADD | §13 | Weather-sensor interface | planned |  |  |
| ADD | §14 | All-sky camera | planned |  |  |
| ADD | §15 | SDR / radio-time layer | planned |  |  |
| ADD | §16 | Selected vs independent references | planned | partial: chrony sources table | [#10](https://github.com/nathansottung/gps-time/pull/10) |
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
| ADD | AC6 | Shadow altitude at zenith | planned |  |  |
| ADD | AC7 | 550 km satellites sunlit in field | planned |  |  |
| ADD | AC8 | When a shell is shadowed | planned |  |  |
| ADD | AC9 | Daylight gained/lost | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| ADD | AC10 | Apparent solar time | planned |  |  |
| ADD | AC11 | Obstructed sky portions | planned |  |  |
| ADD | AC12 | Is this satellite loss normal? | planned |  |  |
| ADD | AC13 | Drift to 1 s without PPS | planned | partial: legacy raw-ppm (GPS-008) |  |
| Feature A |  | GNSS/PPS-disciplined chrony NTP | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| Feature A |  | Internet NTP fallback, honest source/stratum | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| Feature A |  | NTP client IP activity | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Feature A |  | Browser RTT + clock estimate | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Feature A |  | RAM-first bounded telemetry + checkpoints | planned | partial: tracking log unbounded (GPS-011) | [#4](https://github.com/nathansottung/gps-time/pull/4) [#5](https://github.com/nathansottung/gps-time/pull/5) |
| Feature A |  | Source-loss / fallback / reacquisition timeline | next | partial: backend + event list | [#4](https://github.com/nathansottung/gps-time/pull/4) [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Feature A |  | Oscillator fractional-frequency history | planned |  |  |
| Feature A |  | Time-to-1 ms…1 s holdover estimates | planned | partial: legacy raw projection |  |
| Feature A |  | ADEV / MDEV / TDEV / TIE / MTIE | planned |  |  |
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
| Feature B |  | Learned sky-obstruction map | planned |  |  |
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
| Feature C |  | TZ / leap-second / time-scale toolbox | planned | partial: /zones |  |
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
| Feature E (SDR) |  | ADS-B 1090 adapter | planned |  |  |
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
| Feature E (SDR) |  | Fox-hunt TOA/TDoA research | planned |  |  |
| Feature F (aviation) |  | readsb/dump1090 receiver | planned |  |  |
| Feature F (aviation) |  | 978 MHz UAT receiver | planned |  |  |
| Feature F (aviation) |  | External feed adapters (optional) | planned |  |  |
| Feature F (aviation) |  | MLAT metadata/solver | planned |  |  |
| Feature F (aviation) |  | Radiosonde tracking | planned |  |  |
| Feature F (aviation) |  | Topocentric alignment engine | planned |  |  |
| Feature F (aviation) |  | Sun/Moon transit predictions (OMM+SGP4, aircraft, sondes) | planned |  |  |
| Feature F (aviation) |  | Aircraft predictions as short-term estimates | planned |  |  |
| Feature F (aviation) |  | Satellite contamination for cameras | planned |  |  |
| Feature G (network) |  | Opt-in request/accept/reject flow | planned |  |  |
| Feature G (network) |  | Private location shared with solver only | planned |  |  |
| Feature G (network) |  | Local-first raw data | planned |  |  |
| Feature G (network) |  | Station/instrument/calibration metadata | planned |  |  |
| Feature G (network) |  | Raw capture hashes/signatures | planned |  |  |
| Feature G (network) |  | Optional coordinator | planned |  |  |
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
| Scope | Pre-release | Bounded persistence | planned | partial: config/events atomic; tracking log unbounded | [#5](https://github.com/nathansottung/gps-time/pull/5) |
| Scope | Pre-release | Administrative security | done | not yet verified on a Pi | [#24](https://github.com/nathansottung/gps-time/pull/24) |
| Web UI |  | Serve web/dist at /app/; typed API client; demo adapter | done |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Web UI |  | Vitest harness + banner-guard tests | done | 26 tests; CI runs them | [#16](https://github.com/nathansottung/gps-time/pull/16) |
| Web UI |  | Ship web/dist in the Pi bundle and install.sh | done | built on the deploying machine; a UI from another version is refused; not yet run on a Pi | [#35](https://github.com/nathansottung/gps-time/pull/35) |
| Web UI |  | Legacy parity: 21 items in dashboard/web-ui-parity.md | planned |  | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Web UI |  | Timing-chain card, source-aware banner, PPS diagnostics page | done |  | [#15](https://github.com/nathansottung/gps-time/pull/15) |
| Review | GPS-001 | Stale TPV re-ingested | done |  | [#1](https://github.com/nathansottung/gps-time/pull/1) |
| Review | GPS-002 | Survey not single-writer | planned | partial | [#1](https://github.com/nathansottung/gps-time/pull/1) |
| Review | GPS-003 | History uncertainty mixes chrony columns | next |  |  |
| Review | GPS-004 | UTC reference shows browser clock | planned | partial: the `/app/` clocks show station time (measured offset applied, labeled); the legacy dashboard's clock is unchanged | [#47](https://github.com/nathansottung/gps-time/pull/47) |
| Review | GPS-005 | NMEA-only labeled GPS/PPS Stratum 1 | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| Review | GPS-006 | Sync-state edge cases | done |  | [#4](https://github.com/nathansottung/gps-time/pull/4) |
| Review | GPS-007 | ± is root dispersion only | next |  |  |
| Review | GPS-008 | Holdover from raw frequency | planned |  |  |
| Review | GPS-009 | Survey SE labeled repeatability | planned | partial: /app fixed; legacy not | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Review | GPS-010 | Fresh install fails (logsync mode) | done | not Pi-verified | [#1](https://github.com/nathansottung/gps-time/pull/1) |
| Review | GPS-011 | RAM tracking log unbounded | next |  |  |
| Review | GPS-012 | Tracking-log path fixed at import | next |  |  |
| Review | GPS-013 | SIGTERM skips flush; corrupt config reset | done |  | [#5](https://github.com/nathansottung/gps-time/pull/5) |
| Review | GPS-014 | Root service; unauthenticated GET admin | done | POST-only, admin token, unprivileged service + polkit; not yet verified on a Pi | [#24](https://github.com/nathansottung/gps-time/pull/24) |
| Review | GPS-015 | Privacy hidden leaks via sidereal/almanac | done | plus satellite az/el. Decision 2026-10-02: hidden mode keeps satellite IDs, constellation, C/N₀ and used flags (GNSS health stays visible); see Decisions | [#12](https://github.com/nathansottung/gps-time/pull/12) [#13](https://github.com/nathansottung/gps-time/pull/13) |
| Review | GPS-016 | Unescaped innerHTML in legacy view | planned |  |  |
| Review | GPS-017 | No Host/Origin check | done | Host allowlist, Origin check, JSON-only; not yet verified on a Pi | [#24](https://github.com/nathansottung/gps-time/pull/24) |
| Review | GPS-018 | Per-request fan-out; no limits | planned | partial |  |
| Review | GPS-019 | Demo not isolated from admin | done | demo admin simulated; SAMPLE DATA banner on legacy pages; not yet verified on a Pi | [#12](https://github.com/nathansottung/gps-time/pull/12) [#24](https://github.com/nathansottung/gps-time/pull/24) |
| Review | GPS-020 | Installer unpinned pip / TOFU ephemeris | planned | partial: skyfield pinned in requirements.txt and installed into a venv (`apt-get update` added); preflight for root, chrony and the service groups. Still open: hashed requirements, ephemeris trust-on-first-use, staged install | [#17](https://github.com/nathansottung/gps-time/pull/17) [#25](https://github.com/nathansottung/gps-time/pull/25) [#36](https://github.com/nathansottung/gps-time/pull/36) |
| Review | GPS-021 | Deploy scripts ignore failures | done | exit codes checked; upload SHA-256 verified on the Pi. First run against a Pi (2026-10-04) found the `-t` argument joined to user@host in `deploy-to-pi.ps1`; fixed, with an exact-argv test | [#30](https://github.com/nathansottung/gps-time/pull/30) [#40](https://github.com/nathansottung/gps-time/pull/40) |
| Review | GPS-022 | Bundle builder sweeps secrets | planned | partial: file modes |  |
| Review | GPS-023 | Third-party provenance/licenses | planned |  |  |
| Review | GPS-024 | Precise coordinates in docs | done |  |  |
| Review | GPS-025 | Doc contradictions/staleness | planned |  |  |
| Review | GPS-026 | Extension docs overclaim accuracy | planned |  |  |
| Review | GPS-027 | Quantity/unit labels | planned | legacy dashboard.js |  |
| Review | GPS-028 | Browser clock estimators biased | planned | partial: /app min-RTT | [#10](https://github.com/nathansottung/gps-time/pull/10) |
| Review | GPS-029 | Dashboard config hardening | planned |  |  |
| Review | GPS-030 | Global object target; non-portable strftime | planned | partial: server.py and astro.py strftime fixed; the shared object target remains | [#12](https://github.com/nathansottung/gps-time/pull/12) [#43](https://github.com/nathansottung/gps-time/pull/43) |
| Review | GPS-031 | No automated tests | done |  | [#1](https://github.com/nathansottung/gps-time/pull/1) |
| Review | GPS-032 | Generator assumes Pi 4 | planned |  |  |
| Repo |  | Dependabot weekly: pip, pnpm, GitHub Actions | done |  | [#17](https://github.com/nathansottung/gps-time/pull/17) |
| Repo |  | Workflow actions pinned to commit SHAs; CI guard | done |  | [#18](https://github.com/nathansottung/gps-time/pull/18) |
| Repo |  | Tag v1.4.0-rc.1 with release notes (rollback target) | done | pre-release; tag on this PR's merge commit | [#22](https://github.com/nathansottung/gps-time/pull/22) |
| Repo |  | Version from the git tag in /api and the UI footer | done | bundles carry gps_time_pi/VERSION; demo reports the real version; CI checks out tags and fails on `unknown` | [#23](https://github.com/nathansottung/gps-time/pull/23) [#26](https://github.com/nathansottung/gps-time/pull/26) |
| Repo |  | Tag v1.4.0-rc.2 with release notes | done | pre-release; tag on this PR's merge commit; rollback target v1.4.0-rc.1 | [#28](https://github.com/nathansottung/gps-time/pull/28) |
| Repo |  | actionlint in CI (invalid workflow files fail) | done |  | [#29](https://github.com/nathansottung/gps-time/pull/29) |
| Repo |  | Tag v1.4.0-rc.3 with release notes | done | pre-release; tag on this PR's merge commit; intended first Pi deploy | [#33](https://github.com/nathansottung/gps-time/pull/33) |
| Repo |  | First Pi deploy of the 1.4 line | next | checklists written (`deploy/fresh-pi-install.md` for a new Pi, `deploy/first-pi-deploy.md` for a v1.3 station); the deploy itself is the owner's step and hasn't been run | [#34](https://github.com/nathansottung/gps-time/pull/34) [#36](https://github.com/nathansottung/gps-time/pull/36) |
| Repo |  | Tag v1.4.0-rc.4 with release notes | done | pre-release; tag on this PR's merge commit; the bundle the deploy checklists target | [#37](https://github.com/nathansottung/gps-time/pull/37) |
| Repo |  | Debian 13 (Trixie, Python 3.13) support: CI matrix 3.11 + 3.13, aarch64 wheel check, installer and docs audit | done | not yet run on a Pi | [#38](https://github.com/nathansottung/gps-time/pull/38) |
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
| Repo |  | Tag v1.4.0-rc.7 with release notes | done | pre-release; tag on this PR's merge commit; the bundle the deploy checklists target | [#53](https://github.com/nathansottung/gps-time/pull/53) |
