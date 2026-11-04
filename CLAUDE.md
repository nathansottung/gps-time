# GPS Time — instructions for coding agents

GPS Time is a timing-first, offline-capable measurement station: GNSS → PPS → chrony → NTP on a Raspberry Pi, with science and RF layers on top. Its credibility depends on honest measurement semantics and a protected timing core. Read `docs/README.md` (documentation contract) and `docs/INDEX.md` before material changes.

## Project rules (owner-stated)

- **Station tier stays lightweight and works offline.** Heavy analysis belongs in the optional coordinator tier. There is no mandatory cloud and no runtime CDN or analytics.
- **Minimize SD-card writes:** RAM ring buffers, summarized events, atomic checkpoints. Nothing is written to disk at 1 Hz.
- **Label every value with exactly one provenance label:** observed, calculated, modeled, predicted, inferred, external. Definitions are in `web/guidelines/Guidelines.md`; code is in `gps_time_pi/labels.py`.
- **Never infer health for a stage that can't be observed** — say UNKNOWN (or NOT_OBSERVABLE).
- **Never name a cause the evidence can't establish** (jamming, spoofing, interference, antenna failure). Classifications are `inferred` and evidence-based.
- **Don't change timing behavior** (chrony config, gpsd, PPS setup) unless the task explicitly says so. Reading chrony/gpsd/sysfs is fine; writing them is not.
- **Respect location privacy mode everywhere,** including diagnostics output and derived values.
- **Tests must not need live GNSS, Internet, or root.** Use fixtures (`tests/fixtures/`, temp sysfs trees, manual clocks).
- **UI follows `web/guidelines/Guidelines.md` exactly.**
  - The React app in `web/` is the station UI, served at `/app/` (`/` redirects there). The legacy server-rendered pages were removed after v1.4.0 (#99).
  - Fonts are self-hosted (`@fontsource`, weights 300–600; 700 is not shipped).
  - Δf/f is shown as ×10⁻ⁿ (`fmtSci`).
- **One feature branch per task. Small commits. Update `docs/` in the same branch** (change log at `docs/provenance/change-log.md`; an ADR for architectural changes).

## Repository workflow

- **Commit identity:** a repo-local GitHub noreply address, never a personal email. Line-ending conversion off. See `docs/development/new-machine.md`.
- **Branches and PRs:**
  - Branch from `main`, open a PR, and merge with a **merge commit** (no squash) once CI passes. Then delete the branch locally and on GitHub.
  - Don't push, merge, or deploy without the owner's go-ahead for that step.
  - **Releases follow `docs/releases/README.md`:** rc tags on the release-notes PR's merge commit; a stable tag only on a candidate commit that passed the soak rule (72 h unchanged run, `tools/soak_check.py` once, criteria never relaxed).
  - **Update `docs/STATUS.md` in every PR:** change the status of affected rows (done / in progress / next / planned), add the PR link, add rows for new spec items or features, and re-order the next-5 list if it changed. If a PR changes no status, say so in the PR description.
- **Change-log conflicts** between branches (both appending entries): keep both, in chronological order.
- **Before committing:**
  - Scan new content for secrets, credentials, precise coordinates and personal infrastructure details.
  - The only example location is the US Naval Observatory (38.9217, −77.0669, 92 m MSL; h ≈ 59 m with N ≈ −33 m). A second example point, when needed, is the Washington Monument.
  - Never commit a real station's coordinates.
  - The dashboard mockup PNG is kept outside the repository on purpose.

## Checks (all must pass; CI runs them)

```sh
python -m compileall gps_time_pi tools tests modules coordinator
python tools/generate_config.py --help
python -m unittest discover -s tests -t . -v
cd web && corepack pnpm install --frozen-lockfile && corepack pnpm run typecheck && corepack pnpm run test && corepack pnpm run build && corepack pnpm run test:e2e
```

CI (`.github/workflows/`):
- `ci.yml` runs Python 3.11 and 3.13 on Ubuntu (the system Pythons of Debian 12 and 13), and checks that the pinned runtime dependencies have aarch64 wheels for both. Real-SIGTERM and POSIX-only tests run there and are skipped on Windows.
- `web.yml` runs Node 22 and pnpm: type-check, Vitest unit tests (`web/src/**/*.test.ts`), build, then Playwright browser tests (`web/e2e/`: every page at 360–1920 px and half-screen widths; navigation). It also fails on runtime CDN, font-host or analytics URLs, and on 700/bold weights.

## Where things are

- **Timing chain** (GNSS → PPS → chrony stages, PPS state machine, status banner, outage events, boot rule): `gps_time_pi/timing_chain.py`, `gps_time_pi/pps.py`. Architecture doc: `docs/architecture/timing-chain.md`.
- **Outage evidence on the SD card** (one file per outage event: the event, a 10 s timeline, chrony lines ±5 min; 20 MiB cap; no position): `gps_time_pi/evidence.py`, `/api/evidence`.
- **Second pulse** (validation: a GPIO edge at each system-clock second, never on the PPS line; compared with PPS from a scope or counter CSV): `gps_time_pi/secpulse.py`, `tools/pps_compare.py`. Guide: `docs/validation/second-pulse.md`.
- **PPS evidence capture** (run before rebooting in a timing incident; read-only archive; position removed from gpsd output): `scripts/capture-pps-evidence.sh`, `gps_time_pi/gpsd_redact.py`.
- **Oscillator log** (SoC temperature with chrony's frequency; 10-minute bins appended hourly to `oscillator-log.csv`, capped, board-bound by a serial hash): `gps_time_pi/oscillator.py`, `/api/oscillator`. The profile fit over the whole log (temperature, optional square and aging, BIC; modeled) and the holdover projections (GPS-008): `gps_time_pi/oscprofile.py`. Profile export/import with board binding by serial hash: `Log.export`/`import_profile`, `/api/oscillator/profile`. Architecture doc: `docs/architecture/oscillator-log.md`.
- **Learned sky-obstruction map** (addendum §10–11: C/N₀ binned by azimuth and elevation over days from the GNSS collector; a capped grid in `sky-obstruction.json`, written hourly; classes and sectors relative to the station's own sky; satellite losses EXPECTED / NOT EXPLAINED; off in hidden mode): `gps_time_pi/skymap.py`, `/api/sky-obstruction`. The capability record (no exact position; opt-in sky-quality summary, `sky_quality_share`): `gps_time_pi/capability.py`, `/api/capability`. Architecture doc: `docs/architecture/sky-obstruction-map.md`.
- **Stability analysis** (ADEV, MDEV, TDEV from kernel PPS timestamps; RAM only): `gps_time_pi/stability.py`, `/api/stability`. Architecture doc: `docs/architecture/stability-analysis.md`.
- **Earth shadow and satellites** (umbra/penumbra model needing no ephemeris; satellites from an offline TLE cache; the web service never fetches): `gps_time_pi/shadow.py`, `gps_time_pi/satellites.py`, `gps_time_pi/tle_fetch.py`, `/api/shadow`, `/api/satellites`. Architecture doc: `docs/architecture/earth-shadow-and-satellites.md`.
- **NTP service counters** (chrony `serverstats`: received, dropped, rates; RAM history): `gps_time_pi/ntpservice.py`, `/api/ntp-service`. The `_chrony` helper (`scripts/chrony-clients.sh`) publishes the socket-only chronyc reports: `clients`, `ntpdata`, `serverstats`.
- **Independent references** (the station against NTP servers that don't steer it; agree/disagree, never a cause): `gps_time_pi/references.py`, `/api/references`, optional installer step `scripts/chrony-independent-refs.sh`. Architecture doc: `docs/architecture/independent-references.md`.
- **Time scales** (TAI, GPS time, MJD/JD, leap-second table and its expiry, UT1 − UTC from a cached file only): `gps_time_pi/timescales.py`, `/api/timescales`, `web/src/lib/timescales.ts`.
- **chrony parsing:** `gps_time_pi/chrony.py`. Always `chronyc -n`. Refclocks are identified from `chrony.conf`, never by name alone.
- **Local-time display zone** (display only; the system stays on UTC): `gps_time_pi/localtime.py` (override, offline lookup with `tzfpy`, privacy rule), `web/src/lib/localtime.ts`.
- **GNSS collection and survey:** `gps_time_pi/gps.py` (background collector, fresh-epoch gating), `gps_time_pi/config.py` (persistence: SIGTERM flush, fsync, `config.json.prev`, corrupt files set aside).
- **Modules** (optional, off by default; guide `docs/modules/README.md`, ADR-0007): kit `gps_time_pi/modkit/` (interfaces, manifest, ctx, loader; `python -m gps_time_pi.modkit list|check|demo`), schemas `schemas/`, scaffolder `tools/new_module.py`, modules in `modules/<name>/`. Each module runs in its own sandboxed process (`runner.py`, `sandbox.py`) as `gps-time-mod`; on a station only under `system/gps-time-modules.service` (installed, not enabled). The web service never loads modules. Module tests run with the station's through `tests/test_modules.py`. Modules: `modules/sdr-pps-marker/` (research: the PPS-marker detector and time model; live capture from an RTL-SDR through `rtl_tcp` (`system/gps-time-rtl-tcp.service`, not installed by `install.sh`), timed windows as cu8 observation files in RAM; numpy fast path), `modules/reference-adsb/` (aircraft on 1090/978 MHz from a local decoder's `aircraft.json` as self-reported references; experimental), `modules/reference-broadcast-towers/` (FM/ATSC/NOAA transmitters from an offline cache: `fetch.py` downloads the national FCC/NOAA lists, `build_cache.py` filters them to the rounded site; a real cache is never committed; experimental), `modules/analysis-tower-delay-check/` (measured against predicted tower delays: the ATSC A/53 field sync, and FM correlation between two sites' captures; single-site and TDOA modes; numpy; research, synthetic only; runs from its CLI).
- **Observation files** (SigMF + `gpstime:`; writer, reader, validator; `python -m gps_time_pi.obsformat validate|info`): `gps_time_pi/obsformat.py`, `schemas/sigmf-gpstime.v1.json`. Converters to WAV (with a sidecar) and miniSEED 2: `gps_time_pi/convert.py` (`python -m gps_time_pi.convert wav|miniseed`). Guide: `docs/modules/observation-format.md`.
- **Station key** (Ed25519, made at install, 0600 gps-time; signs observation files; `python -m gps_time_pi.station_key generate|show|sign|verify`): `gps_time_pi/station_key.py`. Never commit a key.
- **Coordinator** (SKELETON, optional tier; never imported by the station, not in its bundle; ADR-0008): `coordinator/` (`gps_time_coordinator`: signed join/events with the station key, owner approval by CLI, SQLite; container for TrueNAS SCALE). Tests: `tests/test_coordinator.py`.
- **Optional SDR stack** (`GTP_SDR=1`: rtl_tcp, readsb, dump978-fa and skyaware978, loopback only or no network, one RTL-SDR per role by serial; never touches gpsd/chrony/PPS): `scripts/sdr-stack.sh`, `system/gps-time-{rtl-tcp,readsb,dump978,skyaware978}.service`, `system/gps-time-modules-sdr.conf`. Read-only status (`/api/sdr`, Administration → SDR receivers; units, dongles, feeds, the SDR modules' readiness): `gps_time_pi/sdr.py`, `web/src/components/sdr.tsx`. Module settings from Administration: `POST /api/setting {"module", "config"}` (`modkit/settings.py` `check_config`). Guide: `docs/deploy/sdr-stack.md`.
- **Optional web SDR** (`GTP_WEBSDR=1`: OpenWebRX+ from its maintainer's repository, key pinned by fingerprint, on 127.0.0.1:8074 only; a stdlib password gate on the LAN port, private ranges only, fails closed; shares the 1090 MHz dongle, readsb stopped while it runs (`Conflicts=`) and started again (`websdr-handoff`); never enabled at boot, started/stopped by the admin actions `websdr_start`/`websdr_stop`; a session limit; ADR-0009): `scripts/websdr.sh`, `gps_time_pi/websdr_gate.py`, `system/gps-time-websdr{,-gate}.service`. Its usage log (CPU, temperature, PPS jitter per minute in RAM, a 10-minute baseline, one summary line per session in `websdr-sessions.jsonl`): `gps_time_pi/websdr.py`, `/api/websdr`, Radio & SDR → Devices (`web/src/components/websdr.tsx`). Guide: `docs/deploy/websdr.md`.
- **Opt-in feeders** (`GTP_FEEDERS=1`: readsb's Beast on 127.0.0.1:30005 to aggregators, and PiAware with `use-gpsd no`; each off until turned on in Administration with the admin token and a typed confirmation; MLAT for PiAware only, refused in hidden mode; never a position to a Beast feeder) and the location-sharing list: `scripts/feeders.sh`, `gps_time_pi/feeders.py`, `/api/feeders`, `web/src/components/feeders.tsx`. Guide: `docs/deploy/feeders.md`.
- **Incidents** (write-ups from the records made at the time; never a cause the evidence can't establish): `docs/incidents/`. Second station: `docs/deploy/second-station.md`; bench kit: `docs/validation/bench-kit.md`.
- **Specifications** (requirements, not implemented behavior): `docs/specs/`.
- **Independent review and remaining findings:** `docs/review/GPS-Time-Independent-Review-2026-09-27.md`.
- **Admin security:** `gps_time_pi/security.py` (Host/Origin checks, token), `gps_time_pi/admin_token.py`, `gps-time-pi.service` (unprivileged), `system/50-gps-time-pi.rules` (polkit). Decision: ADR-0005.
- **HTTP API and new web UI:**
  - Reference for every route: `docs/api/`.
  - Typed client and demo adapter: `web/src/api/`.
  - The built UI is served at `/app/` (ADR-0004).
  - Legacy parity (closed) and the removal record: `docs/dashboard/web-ui-parity.md`, `docs/dashboard/legacy-removal-plan.md`.
- **Desktop demo** (no Pi, gpsd, chrony or Internet needed): `scripts/run-demo.ps1` → http://127.0.0.1:8080/. Timing-chain demo: `/api/timing-chain?scenario=<name>`.
