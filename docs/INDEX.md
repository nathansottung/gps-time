# GPS Time documentation index

Start with [`README.md`](README.md). It defines the repo documentation contract and non-negotiable architecture rules.

**For outside readers:** [`ROADMAP.md`](ROADMAP.md). Every spec and roadmap by phase, with status, on one page.

**Where things stand:** [`STATUS.md`](STATUS.md). Every spec item, roadmap feature and review finding, with its status and PR links, plus the next 5 tasks. It is updated in every PR.

## Specifications (owner-provided, imported 2026-10-01)
- `specs/CHG-PPS-HEALTH-DIAGNOSTICS.md` — REQUIRED change: PPS health, failure diagnostics, timing-chain observability, 20 required tests
- `specs/PPS-OBSERVABILITY-AND-GNSS-INTEGRITY.md` — timing-pipeline stages, PPS-loss events and graphs, holdover projections, GNSS integrity/interference/spoofing monitoring
- `specs/ADDENDUM-SKY-SOLAR-SATELLITE.md` — roadmap addendum: Earth shadow and satellite illumination, solar time and geometry, sky obstruction, observing conditions, provenance
- `specs/SPEC-RF-NODE-AND-TDOA.md` — PLANNED, starts after v1.4.0: separate RF nodes synced to a station, MLAT calibration from ADS-B, distributed TDOA, fox hunts; accuracy model, rules and limits
- `specs/SPEC-TIMING-METROLOGY.md` — NEXT: stability analysis (ADEV/MDEV/TDEV), time scales panel, independent references, smaller items; then NTS, then PTP output
- `specs/TASK-PPS-CHAIN.md` — implementation task for the PPS timing-chain backend (branch `feat/pps-chain`)
- `specs/SPEC-EXTENSIBILITY.md` — NEXT (owner-provided, imported 2026-10-21, updated the same day): module architecture for every future feature (source, reference, analysis, UI and receiver modules; manifest, interfaces, data contracts, tooling, module safety, API stability, data licence, governance, first example modules, order of work)
- `specs/SPEC-OBSERVATION-FORMAT-AND-TASKING.md` — NEXT for the format, PLANNED for tasking (owner-provided, imported 2026-10-21): SigMF-based observation format with a `gpstime:` extension, export to miniSEED/RINEX/WAV, capture requests across stations (scheduled and look-back), signal-independent pick/correlate/locate
- `specs/SPEC-COORDINATOR.md` — PLANNED (owner-provided, imported 2026-10-21); required before any multi-station feature: the optional coordinator tier (roles, node keys and sign-up, transport, data formats, storage, processing services, privacy, deployment)
- `specs/SPEC-RF-TASKING-AND-FM-TDOA-TRIAL.md` — OPTION, planned (owner-provided, imported 2026-10-21); extends `SPEC-RF-NODE-AND-TDOA.md`: capability registry, capture-task protocol, stages of access, rules, and a first FM broadcast TDOA trial

## Architecture
- `architecture/system-overview.md`
- `architecture/compute-tiers.md`
- `architecture/observation-model.md`
- `architecture/timing-core-boundaries.md`
- `architecture/earth-shadow-and-satellites.md` — umbra/penumbra model, zenith shadow height, illumination sky map, contamination summary, satellites from an offline TLE cache; limits, privacy, validation
- `architecture/independent-references.md` — comparing the station with NTP servers that don't steer it: which servers count, the agree/disagree rule, delay through the helper, the optional `noselect` installer step
- `architecture/oscillator-log.md` — temperature with chrony's frequency in 10-minute bins: storage on the SD card (hourly, capped, board-bound), the slope it reports, what the oscillator profile still needs
- `architecture/stability-analysis.md` — ADEV/MDEV/TDEV: what is measured, confidence bars, RAM storage, validation against NIST SP 1065
- `architecture/timing-chain.md` — GNSS → PPS → chrony stages, PPS state machine, status banner, outage events, `/api/timing-chain`

## Roadmap
- `roadmap/current-scope.md`
- `roadmap/feature-registry.md` — canonical comprehensive feature inventory
- `roadmap/ROADMAP-DESKTOP-FIELD-APP.md` — FUTURE, not scheduled: cross-platform desktop field / ham-radio app (laptop + GNSS receiver as an off-grid time source); starts only after the Pi station specs are complete
- `roadmap/ROADMAP-SDR-RF-OBSERVATORY.md` — SCOPING, not scheduled: SDR and RF observatory (hardware tiers, GNU Radio/SoapySDR, candidate observations, grid frequency); Pi timing work and the first Pi deploy come first. Earlier SDR notes: `sdr/overview.md`, `sdr/timing-model.md`
- `roadmap/ROADMAP-WEB-UPDATES.md` — FUTURE, low priority: software updates and config upload from the web UI (LAN only, signed releases, separate privileged installer, automatic rollback); not before the station has run stably on v1.4.0
- `roadmap/ROADMAP-OSCILLATOR-AND-MISC.md` — FUTURE, none blocks v1.4.0: trained oscillator profile (board-bound, export/import), networked SDR, assisted network deploys, PPS evidence capture script, smaller items (DHCP self-source, NMEA offset calibration, bundle split, downstream NTP)
- `roadmap/ROADMAP-GEOPHYSICS-DISTRIBUTED-SCIENCE.md` — FUTURE, research; after v1.4.0 and the oscillator profile: a network of timed stations measuring geophysical effects (interference maps, site stability; Earth tides, ionosphere, water vapor with dual-frequency receivers), and what no tier can measure
- `roadmap/ROADMAP-SENSOR-FUSION.md` — FUTURE (owner-provided, imported 2026-10-21); extends the geophysics roadmap: optional sensors on timed nodes ranked by science value per cost, the timing each needs, cross-sensor events, what is not feasible
- legacy planning: `PROJECT-SCOPE.md`, `NEXT-ITERATION.md`, `ideas-ledger.md`

## Science
- `science/quantity-registry.md`
- `science/timing-metrology.md`
- existing: `GNSS-SURVEY-AND-INSTALLATION.md`, `almanac-design-scope.md`

## SDR / RF
- `sdr/overview.md`
- `sdr/timing-model.md`
- existing: `open-lightning-network.md`, `platform-extensions.md`

## Dashboard
- `dashboard/README.md`
- professional concept image: kept outside the repository (provenance unrecorded; not distributed)

## Web prototype
- `../web/` — the station UI (React/Vite), served at `/app/` (`/` redirects there) and wired to the API through a typed client (`web/src/api/`). The legacy pages were removed after v1.4.0 (#99).
- `dashboard/web-ui-parity.md` — CLOSED: every legacy feature ported to `/app/` or dropped by the owner, with the PRs
- `dashboard/legacy-removal-plan.md` — DONE (#99): what the legacy pages were, the code that existed only for them, the order followed, rollback
- `../web/guidelines/Guidelines.md` — UI guidelines all project UI must follow

## API
- `api/README.md` — station HTTP API conventions and index
- `api/endpoints.md` — every route: parameters, responses, side effects, privacy notes

## Development
- `development/windows-demo.md`
- `deploy/fresh-pi-install.md` — checklist for a newly flashed Raspberry Pi OS Lite: SSH key, packages, UART/PPS configuration, deploy, reboot, chrony refclocks, checks
- `deploy/upgrade-1.4-station.md` — checklist for upgrading a station that already runs a 1.4 release candidate (rc.8, rc.9 or rc.10 → rc.11): what changes, the deploy command, checks, the soak run before v1.4.0
- `deploy/first-pi-deploy.md` — checklist for the first Pi deploy of the 1.4 line (v1.3 → v1.4.0-rc.3): SSH key, backups, deploy command, checks, rollback
- `development/raspberry-pi-deploy.md`
- `development/new-machine.md` — setting up a new development machine (clone, identity, line endings, Python, pnpm, tests)
- `../gps_time_pi/data/README.md` — the bundled sky data: source, version and license per file, how it is rebuilt (`tools/build_sky_data.py`)
- `../THIRD_PARTY_NOTICES.md` — third-party software and data: what is bundled, shipped, installed and downloaded, and under which license
- `public-release-checklist.md` — RUN 2026-10-21: what was checked before the repository goes public (history scan, release blockers, licensing, outside-reader docs, GitHub settings), the result of each, and the owner's remaining steps
- existing: `DEVELOPMENT.md`, `GITHUB-PUBLISHING.md`, `deployment-runbook.md`

## Hardware
- `hardware/README.md`
- `hardware/zed-f9-dual-band.md` — PLAN, next: a dual-band u-blox receiver profile (ZED-F9T timing or ZED-F9P positioning): what it improves on a Pi and what it can't, wiring, PPS, receiver configuration, gpsd/chrony, raw data for PPP, the changes in order
- `HARDWARE-PROFILES.md`

## Licensing / decisions / provenance
- `licensing/open-source-policy.md`
- `decisions/` (ADR-0004: web UI served at `/app/`, legacy pages retired 2026-10-21; ADR-0005: admin token, POST-only state changes, Host/Origin checks, unprivileged service; ADR-0006: desktop app is a tray app running the Python backend, not Electron)
- `provenance/change-log.md`

## Source review
- `review/source-review-2026-09-07.md`
- `review/review-evidence-2026-09-07.zip`
- `review/GPS-Time-Independent-Review-2026-09-27.md` — independent whole-repository review of the 2026-09-18 archive

## Releases
- `releases/v1.4.0-rc.11.md` — chrony history semantics fixed (GPS-003/007), the legacy pages' features in `/app/`, TypeScript 7; the soak candidate, and the commit v1.4.0 is to be tagged on (pre-release)
- `releases/v1.4.0-rc.10.md` — sunset as prominent as sunrise, screenshot mode, outside-reader docs (roadmap page, public release checklist); web UI only over rc.9 (pre-release)
- `releases/v1.4.0-rc.9.md` — fixes from the rc.8 soak run (log flush with caps, outage evidence on SD, PPS poller thread, browser round trip), oscillator log, Earth shadow and satellites (pre-release)
- `releases/v1.4.0-rc.8.md` — timing metrology: stability analysis, time scales, independent references, NTP service counters (pre-release)
- `releases/v1.4.0-rc.7.md` — fixes from the first Pi build, local-time clock, self-source handling, installer disables DHCP NTP servers (pre-release)
- `releases/v1.4.0-rc.6.md` — Windows deploy script fix (ssh `-t`) (pre-release)
- `releases/v1.4.0-rc.5.md` — Debian 13 / Python 3.13 tested in CI (pre-release)
- `releases/v1.4.0-rc.4.md` — the bundle ships the web UI, installer preflight (pre-release)
- `releases/v1.4.0-rc.3.md` — deploy scripts stop on failure, sun shifts (pre-release)
- `releases/v1.4.0-rc.2.md` — admin security, venv installer, version reporting (pre-release)
- `releases/v1.4.0-rc.1.md` — first tagged version (pre-release); rollback target for rc.2

## Change records
- `provenance/change-log.md`
- `provenance/CHG-001-002-foundation-correction.md` — GNSS fresh-epoch gating; fresh-install logging repair
