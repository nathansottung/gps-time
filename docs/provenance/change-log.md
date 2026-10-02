# Development change log

## 2026-09-18 — desktop/demo + roadmap consolidation scaffold

- added configuration-driven multi-page dashboard
- added Windows/Linux demo runner with sample timing/GNSS/solar/NTP-client data
- added `/configure` widget visibility/size editor with gated writes
- added browser HTTP RTT and browser-clock estimate endpoint
- retained legacy instrument page at `/legacy`
- added repo/Pi bundle builder and SCP/SSH deployment helpers
- expanded `/docs/` contract, feature registry, timing/scientific vocabulary and SDR roadmap
- copied professional dashboard concept image into `docs/mockups/` (removed from the repository 2026-10-01; kept locally by the owner)

This change does **not** claim the earlier source-review blockers are resolved.

## 2026-09-27 — CHG-001 + CHG-002 foundation correction (candidate)

- CHG-001: GNSS sampling moved to a background collector thread; `snapshot()` is read-only; survey samples require a fresh, valid, strictly newer receiver epoch; stale fixes are reported with age instead of as live; rejection reasons counted; survey statistics split into fresh-gated vs legacy samples. Existing survey data preserved and marked legacy, not reset.
- CHG-002: logsync units and admin flush invoke the script via `/bin/bash`; `install.sh` sets script permissions; bundle builder writes explicit file modes. Corrects the deployment runbook's earlier claim.
- Added the repository's first automated tests (`tests/`, stdlib `unittest`) and a CI step.
- Details, root causes, limitations: `CHG-001-002-foundation-correction.md`.

Resolves review findings GPS-001 and GPS-010. GPS-002 is partly resolved: collection is now independent of request traffic but not of the web process. Other review findings remain open.

## 2026-10-01 — publication redaction (owner-approved)

- Replaced precise station-like coordinates in docs and the demo fixture with the US Naval Observatory example (38.9217, -77.0669, 92 m MSL; ellipsoidal height ~59 m). A second "moved site" example uses the Washington Monument (38.8895, -77.0353).
- Generalized deployment-specific details: "workstation", "home router", "indoor window antenna", "mid-Atlantic" latitude; removed antenna warranty notes.
- Removed `docs/mockups/professional-dashboard-concept.png` from the repository (kept locally by the owner; provenance unrecorded).
- Values were redacted before the first git commit so they never enter repository history.

## 2026-10-01 — web UI prototype import

- Imported `web/` from `figma-web-prototype.zip` (Figma Make React 19 + Vite + Tailwind v4 prototype, 24 files) unchanged, including `web/guidelines/Guidelines.md`, the UI guidelines referenced by the project rules.
- Root `.gitignore` now excludes `web/node_modules/` and `web/dist/`.
- The prototype uses synthetic demo data and is not yet connected to `gps_time_pi`. Known import-time limitations: `web/vite.config.ts` imports `.figma/make/site.json`, which is not in the archive (builds outside Figma Make will fail until that is addressed); `web/src/index.css` loads Google Fonts over the network (conflicts with offline-first); `web/.gitattributes` declares Git LFS rules.


## 2026-10-01 — web UI made standalone; owner decisions applied

Owner decisions: the React app in `web/` will be ported to become the Pi UI (the CHG-001 edits to the legacy `gps_time_pi` pages stay as they are, no restyle); six provenance labels (observed, calculated, modeled, predicted, inferred, external); fonts self-hosted, weight 700 dropped.

- `web/` builds standalone: Figma Make plugins, `.figma/make/site.json` and the Google Analytics hook removed from `vite.config.ts`; dev/preview bind to 127.0.0.1:5173 (`GTP_WEB_HOST` opts into LAN exposure); Git LFS `.gitattributes` removed.
- Fonts bundled from `@fontsource/inter` and `@fontsource/jetbrains-mono` 5.3.0 (SIL OFL-1.1), weights 300–600; `b`/`strong` mapped to 600. The built UI makes no third-party runtime requests.
- Demo station moved to the US Naval Observatory (38.9217, −77.0669); geoid undulation sign fixed (H = 92 m, N = −33 m, h = 59 m).
- Fractional frequency offset shown as ×10⁻ⁿ (`fmtSci`); drift rates in s⁻¹.
- `ProvenanceType`, design tokens and `Guidelines.md` extended to the six labels; `docs/README.md` rule 2 updated.
- New CI workflow `.github/workflows/web.yml`: frozen-lockfile install, type-check, build, offline and font-weight guards.

The 2026-10-01 import entry's known limitations about `site.json`, Google Fonts and Git LFS are resolved by this entry.

Still open in `web/`:
- Existing tags not yet re-labeled with the new set (e.g. sun times and holdover projections should be `predicted`).
- Tailwind colour classes (`text-slate-*`, `bg-cyan-400`, …) in `GNSS.tsx`, `RadioSDR.tsx`, `Secondary.tsx` and `Timing.tsx`, which the guidelines forbid.
- The demo holdover figures are internally inconsistent: "1 s error in ~1.4 days" doesn't follow from the stated 8.4 × 10⁻⁹ s⁻¹ drift.
- The app isn't yet served by `gps_time_pi`.

## 2026-10-01 — specifications imported

- Added four owner-provided specifications under `docs/specs/` from `gps-time-specs.zip` (SHA-256 `6cf9f938…75ec53`), unchanged: `CHG-PPS-HEALTH-DIAGNOSTICS.md`, `PPS-OBSERVABILITY-AND-GNSS-INTEGRITY.md`, `ADDENDUM-SKY-SOLAR-SATELLITE.md`, `TASK-PPS-CHAIN.md`.
- Indexed in `docs/INDEX.md`. Scanned before commit: no secrets, credentials, personal identifiers or coordinates.
- These are requirements, not implemented behavior; implementation status is tracked in the roadmap and change records.

## 2026-10-01 — PPS timing chain backend (feat/pps-chain)

Implements `specs/CHG-PPS-HEALTH-DIAGNOSTICS.md` per `specs/TASK-PPS-CHAIN.md`, backend only. Architecture: `architecture/timing-chain.md`.

- `gps_time_pi/pps.py`: kernel PPS observation from `/sys/class/pps/pps0/assert` (RAM ring; age, rate, consecutive/missed pulses, interval statistics), labeled as Linux-observed, not electrical jitter.
- `gps_time_pi/chrony.py`: pure parsers for `chronyc -n sources/sourcestats/tracking`; read-only `chrony.conf` refclock identification (PPS, NMEA, `lock`); all chronyc calls use `-n`.
- `gps_time_pi/timing_chain.py`: independent stages, PPS state machine, evidence-based classification (`PPS PATH ANOMALY`, never interference), new status banner replacing `sync_state()` (no GPS/PPS Stratum 1 unless chrony selects PPS), one `PPS_OUTAGE` event per outage with a small checkpoint that survives restarts, diagnostic snapshot honoring privacy mode.
- `gps_time_pi/labels.py`: the six provenance labels.
- New read-only endpoints `/api/timing-chain` and `/api/diagnostics`; `/api` gains `timing_status`. Demo mode serves synthetic scenarios through the real pipeline.
- Tests: `tests/test_timing_chain.py` (the 20 spec tests, the NMEA-stale case, chrony-unknown, parsers) with `tests/fixtures/chrony/`.
- No change to chrony, gpsd or PPS configuration or behavior.

## 2026-10-01 — survey/config persistence hardening (fix/survey-persistence)

Root cause (reported 2026-10-01, review GPS-013): survey updates are written at most every 15 min; the only exit flush was `atexit`, which Python skips on SIGTERM (`systemctl stop/restart`, reboot), so each restart lost up to 15 min of survey; an unreadable `config.json` was silently treated as empty and then overwritten by the next save, erasing the survey; writes were not fsynced.

- SIGTERM handler (installed by `server.main()`) flushes cached config/survey before exiting.
- Saves write a temp file, fsync it, rename atomically, then fsync the directory (POSIX).
- An unreadable or non-object `config.json` is moved to `config.json.corrupt-<UTC>` with its bytes intact; it is never overwritten.
- Each save keeps the previous good file as `config.json.prev` (same atomic method; a corrupt file never becomes the checkpoint). Loading falls back to it when `config.json` is missing or corrupt.
- `/api/survey` → `persistence` reports where the config was loaded from, any file set aside, and the last write time/error.
- Tests: `tests/test_config_persistence.py` (real SIGTERM delivery runs on POSIX/CI; skipped on Windows).
- Unchanged: the 15-minute batching interval, so an unexpected power loss can still lose up to 15 minutes of survey samples.

## 2026-10-01 — PPS boot rule: ACQUIRING instead of an outage (fix/pps-boot-acquiring)

- Replaces the 300 s startup grace. Until PPS is first selected after a boot, the timing chain reports `ACQUIRING · PPS NOT YET SELECTED SINCE BOOT` and opens no outage.
- If PPS is not selected within 30 min of boot (`GTP_PPS_ACQUIRE_WINDOW_S`), one `PPS_OUTAGE` opens, backdated to boot time (`start_bound: "boot"`).
- Boot time comes from `/proc/uptime`. The kernel `boot_id` and "PPS selected this boot" are checkpointed once per boot, so web-service restarts within a boot are handled.
- If the service starts more than 30 min after boot, or boot time is unknown, nothing is backdated.
- `UNSYNCHRONIZED` and `GPS_PPS` are never masked by ACQUIRING. `/api` applies the same overlay when the collector is running.
- Demo scenario `acquiring` added. Tests: `tests/test_pps_boot.py`.

## 2026-10-01 — onboarding: CLAUDE.md and new-machine setup

- `CLAUDE.md` (repo root): the owner's project rules, repository workflow, required checks and a code map. Coding agents read it automatically, so the rules no longer live only in one machine's local agent memory.
- `docs/development/new-machine.md`: tools, `gh` sign-in, clone with `core.autocrlf=false`, repo-local GitHub noreply identity, Python and pnpm checks, demo, backup verification. The steps were verified in a fresh clone.
- Clone pitfalls found and documented:
  - Git for Windows' system config enables autocrlf, so a plain clone checked out about 150 files with CRLF endings.
  - A clone path that is too long makes `pnpm run build` fail with `ERR_PACKAGE_IMPORT_NOT_DEFINED`; the guide says to keep the repo root to about 64 characters or enable long paths.


## 2026-10-01 — setup check on a new machine (chore/setup-check)

- Followed `docs/development/new-machine.md` on a second Windows machine. The Python checks pass (78 tests, `OK (skipped=1)`), and so do the web install, typecheck and build. The demo serves `/` and the APIs.
- `.gitattributes`: `*.sh text eol=lf`, so shell scripts check out with LF even where `core.autocrlf` is on. Renormalizing the index changed no files.
- Guide fixes:
  - The guide now mentions `.gitattributes` and what it covers.
  - It explains what to do when an older Python shadows 3.11+ on PATH (`py -0p`, `py -3.x`), and notes that `run-demo.ps1` prefers plain `python`.

## 2026-10-01 — web UI served by the station and wired to the API (feat/web-dashboard)

- **Server:** `gps_time_pi/server.py` serves the built React app (`web/dist`, or `GTP_WEB_DIST`) at `/app/`.
  - `index.html` is `no-store`; hashed assets are cached immutably.
  - Traversal and NUL paths are refused.
  - Without a build, `/app/` returns 503 with the build command.
  - Legacy pages and every `/api` route are unchanged. Tests: `tests/test_web_ui.py`.
- **Web UI:** `web/src/data/demo.ts` is replaced by `web/src/api/`:
  - typed API (`types.ts`) and `StationApi` client (`client.ts`);
  - client-side demo adapter in the server's shapes (`demo.ts`);
  - previews for features with no endpoint (`previews.ts`), shown only through `<Planned>` with demo data;
  - data-source selection and polling (`station.tsx`).
  - A failed live request never falls back to demo data.
  - `MetricRow` shows `null` as UNKNOWN.
  - Vite's dev server proxies `/api` to `GTP_API_TARGET`.
- **Pages now read the station:**
  - header status, stratum and reference;
  - Δt (chrony), RMS, Δf/f, PPS state, offset history (1 h / 24 h / 7 d);
  - new Timing Chain tab: stages, inferred classification, diagnostic snapshot;
  - PPS event log, GNSS table, sky plot, position and geodesy (privacy-filtered values only);
  - sun and moon (predicted), sidereal time;
  - NTP clients and chrony sources, browser RTT and offset estimate (`/api/ping`);
  - storage, system, power, location privacy setting.
- **Honesty fixes found while wiring:**
  - Sunrise and sunset are labeled predicted.
  - With chronyc unavailable, the NTP client count is UNKNOWN instead of 0; satellite counts from a stale sky report are not shown.
  - The obstruction preview no longer names a cause.
  - The light-distance comparisons are corrected (1 s ≈ 0.78 × Earth–Moon distance).
  - Configure says it is a non-saving preview.
  - The demo outage classifications are the classifier's real strings.
- **Docs:**
  - `docs/api/README.md` and `docs/api/endpoints.md` cover every route, including side effects, the LAN-trust gaps, the ambiguous `clients: []` and the almanac privacy note;
  - ADR-0004;
  - `docs/dashboard/web-ui-parity.md` (21 legacy features still missing).
- **Not done:** `install.sh` and the deploy bundle do not ship `web/dist` yet.

## 2026-10-01 — roadmap: desktop field / ham-radio app (docs/roadmap-desktop-field-app)

- Added `docs/roadmap/ROADMAP-DESKTOP-FIELD-APP.md` (owner-provided, copied verbatim) and indexed it in `docs/INDEX.md`.
- Status FUTURE, not scheduled. Nothing is to start until the Raspberry Pi station work in `docs/specs/` is complete.
