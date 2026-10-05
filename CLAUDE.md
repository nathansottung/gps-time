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
  - The React app in `web/` is being ported to become the Pi UI; the old `gps_time_pi` dashboard is not restyled.
  - Fonts are self-hosted (`@fontsource`, weights 300–600; 700 is not shipped).
  - Δf/f is shown as ×10⁻ⁿ (`fmtSci`).
- **One feature branch per task. Small commits. Update `docs/` in the same branch** (change log at `docs/provenance/change-log.md`; an ADR for architectural changes).

## Repository workflow

- **Commit identity:** a repo-local GitHub noreply address, never a personal email. Line-ending conversion off. See `docs/development/new-machine.md`.
- **Branches and PRs:**
  - Branch from `main`, open a PR, and merge with a **merge commit** (no squash) once CI passes. Then delete the branch locally and on GitHub.
  - Don't push, merge, or deploy without the owner's go-ahead for that step.
  - **Update `docs/STATUS.md` in every PR:** change the status of affected rows (done / in progress / next / planned), add the PR link, add rows for new spec items or features, and re-order the next-5 list if it changed. If a PR changes no status, say so in the PR description.
- **Change-log conflicts** between branches (both appending entries): keep both, in chronological order.
- **Before committing:**
  - Scan new content for secrets, credentials, precise coordinates and personal infrastructure details.
  - The only example location is the US Naval Observatory (38.9217, −77.0669, 92 m MSL; h ≈ 59 m with N ≈ −33 m). A second example point, when needed, is the Washington Monument.
  - Never commit a real station's coordinates.
  - The dashboard mockup PNG is kept outside the repository on purpose.

## Checks (all must pass; CI runs them)

```sh
python -m compileall gps_time_pi tools tests
python tools/generate_config.py --help
python -m unittest discover -s tests -t . -v
cd web && corepack pnpm install --frozen-lockfile && corepack pnpm run typecheck && corepack pnpm run test && corepack pnpm run build
```

CI (`.github/workflows/`):
- `ci.yml` runs Python 3.11 and 3.13 on Ubuntu (the system Pythons of Debian 12 and 13), and checks that the pinned runtime dependencies have aarch64 wheels for both. Real-SIGTERM and POSIX-only tests run there and are skipped on Windows.
- `web.yml` runs Node 22 and pnpm: type-check, Vitest unit tests (`web/src/**/*.test.ts`), build. It also fails on runtime CDN, font-host or analytics URLs, and on 700/bold weights.

## Where things are

- **Timing chain** (GNSS → PPS → chrony stages, PPS state machine, status banner, outage events, boot rule): `gps_time_pi/timing_chain.py`, `gps_time_pi/pps.py`. Architecture doc: `docs/architecture/timing-chain.md`.
- **Stability analysis** (ADEV, MDEV, TDEV from kernel PPS timestamps; RAM only): `gps_time_pi/stability.py`, `/api/stability`. Architecture doc: `docs/architecture/stability-analysis.md`.
- **Earth shadow and satellites** (umbra/penumbra model needing no ephemeris; satellites from an offline TLE cache; the web service never fetches): `gps_time_pi/shadow.py`, `gps_time_pi/satellites.py`, `gps_time_pi/tle_fetch.py`, `/api/shadow`, `/api/satellites`. Architecture doc: `docs/architecture/earth-shadow-and-satellites.md`.
- **NTP service counters** (chrony `serverstats`: received, dropped, rates; RAM history): `gps_time_pi/ntpservice.py`, `/api/ntp-service`. The `_chrony` helper (`scripts/chrony-clients.sh`) publishes the socket-only chronyc reports: `clients`, `ntpdata`, `serverstats`.
- **Independent references** (the station against NTP servers that don't steer it; agree/disagree, never a cause): `gps_time_pi/references.py`, `/api/references`, optional installer step `scripts/chrony-independent-refs.sh`. Architecture doc: `docs/architecture/independent-references.md`.
- **Time scales** (TAI, GPS time, MJD/JD, leap-second table and its expiry, UT1 − UTC from a cached file only): `gps_time_pi/timescales.py`, `/api/timescales`, `web/src/lib/timescales.ts`.
- **chrony parsing:** `gps_time_pi/chrony.py`. Always `chronyc -n`. Refclocks are identified from `chrony.conf`, never by name alone.
- **Local-time display zone** (display only; the system stays on UTC): `gps_time_pi/localtime.py` (override, offline lookup with `tzfpy`, privacy rule), `web/src/lib/localtime.ts`.
- **GNSS collection and survey:** `gps_time_pi/gps.py` (background collector, fresh-epoch gating), `gps_time_pi/config.py` (persistence: SIGTERM flush, fsync, `config.json.prev`, corrupt files set aside).
- **Specifications** (requirements, not implemented behavior): `docs/specs/`.
- **Independent review and remaining findings:** `docs/review/GPS-Time-Independent-Review-2026-09-27.md`.
- **Admin security:** `gps_time_pi/security.py` (Host/Origin checks, token), `gps_time_pi/admin_token.py`, `gps-time-pi.service` (unprivileged), `system/50-gps-time-pi.rules` (polkit). Decision: ADR-0005.
- **HTTP API and new web UI:**
  - Reference for every route: `docs/api/`.
  - Typed client and demo adapter: `web/src/api/`.
  - The built UI is served at `/app/` (ADR-0004).
  - Legacy feature gaps: `docs/dashboard/web-ui-parity.md`.
- **Desktop demo** (no Pi, gpsd, chrony or Internet needed): `scripts/run-demo.ps1` → http://127.0.0.1:8080/. Timing-chain demo: `/api/timing-chain?scenario=<name>`.
