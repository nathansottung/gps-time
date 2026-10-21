# GPS Time roadmap

GPS Time turns a Raspberry Pi and a GNSS receiver into a Stratum-1 time server that shows how good its time is, and why. Science and radio work is built on top of that timing core, without becoming a dependency of it. It works offline; there is no mandatory cloud.

This page lists every specification and roadmap in the repository, by phase. Counts are rows in [`STATUS.md`](STATUS.md) on 2026-10-19; `STATUS.md` is the authoritative, per-item list and is updated in every pull request.

**Where it stands:** the latest pre-release is v1.4.0-rc.11. The stable v1.4.0 waits for a soak run on the Pi and for the remaining release blockers below.

## Status words

| Word | Meaning |
|---|---|
| **Done** | Implemented and tested. Hardware results are noted where they exist. |
| **In progress** | Some items done; others scheduled. |
| **Planned** | Written down and accepted, not scheduled. |
| **Future** | A direction. Starts only after the phases before it. |

## Phase 1 — Trustworthy time (v1.4.0)

The timing chain from satellite to NTP client, with every stage observed or marked UNKNOWN.

| Document | What it covers | Status |
|---|---|---|
| [`specs/TASK-PPS-CHAIN.md`](specs/TASK-PPS-CHAIN.md) | Backend for the GNSS → PPS → chrony chain: stages, PPS state machine, outage events | In progress (18 done, 2 planned) |
| [`specs/CHG-PPS-HEALTH-DIAGNOSTICS.md`](specs/CHG-PPS-HEALTH-DIAGNOSTICS.md) | PPS health, failure diagnostics and their web UI | In progress (79 done, 11 scheduled, 5 planned) |
| [`specs/PPS-OBSERVABILITY-AND-GNSS-INTEGRITY.md`](specs/PPS-OBSERVABILITY-AND-GNSS-INTEGRITY.md) | Pipeline stages, PPS-loss graphs, holdover, GNSS integrity | In progress (34 done, 3 scheduled, 10 planned) |
| [`review/GPS-Time-Independent-Review-2026-09-27.md`](review/GPS-Time-Independent-Review-2026-09-27.md) | Independent review of the code: 32 findings | In progress (14 closed, 2 scheduled, 16 open) |

Release blocker still open: the second soak run on the Pi. chrony history semantics and the honest error bound (review GPS-003, GPS-007) were fixed in #93.

## Phase 2 — Measurement station

What a timed, fixed station can measure and calculate on its own, offline.

| Document | What it covers | Status |
|---|---|---|
| [`specs/SPEC-TIMING-METROLOGY.md`](specs/SPEC-TIMING-METROLOGY.md) | Allan deviation, time scales, independent references; then NTS and PTP | In progress (20 done, 9 scheduled; NTS and PTP not started) |
| [`specs/ADDENDUM-SKY-SOLAR-SATELLITE.md`](specs/ADDENDUM-SKY-SOLAR-SATELLITE.md) | Earth shadow and satellite illumination, solar geometry, sky obstruction | In progress (11 done, 24 planned) |
| [`roadmap/feature-registry.md`](roadmap/feature-registry.md) | The full feature inventory, sections A–J | In progress (15 done, 1 scheduled, 92 planned) |
| [`hardware/zed-f9-dual-band.md`](hardware/zed-f9-dual-band.md) | A dual-band u-blox receiver profile (ZED-F9T or ZED-F9P): fewer outages, more satellites, raw data for PPP | Next (plan) |
| [`hardware/HARDWARE-REFERENCE-NODE.md`](hardware/HARDWARE-REFERENCE-NODE.md) | A reference parts list in four tiers (timing station, precision station, RF node, sensor add-ons), so results from different owners are comparable | Draft (part numbers are examples) |
| [`roadmap/current-scope.md`](roadmap/current-scope.md) | What the 1.4 line contains | In progress (5 done, 1 scheduled, 1 planned) |

## Phase 3 — After v1.4.0

| Document | What it covers | Status |
|---|---|---|
| [`specs/SPEC-EXTENSIBILITY.md`](specs/SPEC-EXTENSIBILITY.md) | How every future feature is added: modules (source, reference, analysis, UI, receiver) with a manifest, typed interfaces, versioned schemas, fixtures and tests; module safety, API stability, data licence, governance; the timing core untouched | Next |
| [`specs/SPEC-OBSERVATION-FORMAT-AND-TASKING.md`](specs/SPEC-OBSERVATION-FORMAT-AND-TASKING.md) | One file format for any timed measurement (SigMF with a `gpstime:` extension), capture requests across stations (scheduled and look-back), and analyses that work on any signal type | Next (format); planned (capture requests) |
| [`roadmap/ROADMAP-OSCILLATOR-AND-MISC.md`](roadmap/ROADMAP-OSCILLATOR-AND-MISC.md) | Trained oscillator profile, networked SDR, assisted deploys, evidence capture | Oscillator profile: next (the oscillator log it needs is done). Evidence capture script: done. The rest: future |
| [`roadmap/ROADMAP-WEB-UPDATES.md`](roadmap/ROADMAP-WEB-UPDATES.md) | Software updates and config upload from the web UI, LAN only | Future, low priority |
| [`roadmap/ROADMAP-DESKTOP-FIELD-APP.md`](roadmap/ROADMAP-DESKTOP-FIELD-APP.md) | A laptop and a GNSS receiver as an off-grid time source for ham digital modes | Future |

## Phase 4 — Radio and the coordinator

| Document | What it covers | Status |
|---|---|---|
| [`specs/SPEC-COORDINATOR.md`](specs/SPEC-COORDINATOR.md) | The optional coordinator tier a small group runs on its own hardware: node sign-up and keys, transport, data formats, storage, processing services, privacy | Planned; required before any multi-station feature |
| [`roadmap/ROADMAP-SDR-RF-OBSERVATORY.md`](roadmap/ROADMAP-SDR-RF-OBSERVATORY.md) | Timestamped, frequency-calibrated SDR observations | Planned (scoping) |
| [`specs/SPEC-RF-NODE-AND-TDOA.md`](specs/SPEC-RF-NODE-AND-TDOA.md) | RF nodes synced to a station, MLAT calibration, TDOA, fox hunts | Planned (19 items) |
| [`specs/SPEC-RF-TASKING-AND-FM-TDOA-TRIAL.md`](specs/SPEC-RF-TASKING-AND-FM-TDOA-TRIAL.md) | Nodes asking other nodes to capture the same signal at the same moment (capability registry, signed capture tasks, owner control), and a first FM broadcast TDOA trial | Planned (option, in stages) |
| [`specs/SPEC-RF-REFERENCE-SIGNALS-AND-TRUST.md`](specs/SPEC-RF-REFERENCE-SIGNALS-AND-TRUST.md) | A catalog of signals with known or self-reported transmitter positions (ATSC, FM, NOAA, ADS-B, AIS, radiosondes, WWV, AM, LTE sync) for calibrating nodes, and a trusted cluster that new nodes join by passing checks against references and peers | Planned (option, in stages) |

## Phase 5 — Geophysics and distributed science

| Document | What it covers | Status |
|---|---|---|
| [`roadmap/ROADMAP-GEOPHYSICS-DISTRIBUTED-SCIENCE.md`](roadmap/ROADMAP-GEOPHYSICS-DISTRIBUTED-SCIENCE.md) | A network of timed stations measuring real effects: interference maps and site stability now; Earth tides, ionosphere and water vapor with dual-frequency receivers. Includes what cannot be measured at any tier | Future, research |
| [`roadmap/ROADMAP-SENSOR-FUSION.md`](roadmap/ROADMAP-SENSOR-FUSION.md) | Optional sensors on timed nodes (seismic, infrasound, VLF lightning, muons, all-sky camera, magnetometer), the timing each needs, and events seen by several sensors | Future |

## What GPS Time will not claim

- A cause the evidence can't establish (jamming, spoofing, interference, antenna failure). It reports what it observes.
- Health for a stage it can't observe. That stage shows UNKNOWN.
- Statistical repeatability as absolute accuracy, or the host clock's accuracy as the accuracy of an SDR sample or a network packet.
- Earth's gravity field or mass from clock comparisons (see Phase 5).

## More

- Design rules for contributors: [`README.md`](README.md) (the documentation contract).
- Every document: [`INDEX.md`](INDEX.md).
- Everything discussed, against what is built, specced or missing: [`SCOPE-REVIEW.md`](SCOPE-REVIEW.md).
- Releases: [`releases/`](releases/).
