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

## 2026-10-01 — location privacy for almanac, object lookup and sidereal time (fix/location-privacy)

Root cause: `/api/almanac` and `/api/object` computed sunrise and sunset, solar noon, day length, moon and object rise/set, and the sky map from the exact site in every privacy mode. `/api` → `sidereal` did the same. Each is a function of the position: solar noon and LST give longitude, day length gives latitude. So `hidden` mode still revealed the station's location, and `rounded` mode revealed more than ~11 km.

- `config.privacy_site()` returns the site astronomy may use, with the same rounding as `displayed_location()`:
  - exact → unchanged;
  - rounded → 1 decimal, MSL altitude to 10 m, no ellipsoidal height;
  - hidden → none.
- **hidden:** `/api/almanac` and `/api/object` return `available: false` with the privacy reason and compute nothing. Object lookup no longer sets the shared sky-map target. `/api` → `sidereal` is null.
- **rounded:** everything is computed only from the rounded site.
- Responses carry `location_display`.
- Demo mode follows the same rules. `/api` → `location` in demo mode now applies the privacy mode; it used to always report exact.
- Replaced the glibc-only `%-I`/`%-d` time formatting in both endpoints. Output on the Pi is unchanged.
- Web UI:
  - The demo adapter mirrors hidden mode.
  - The sun panels note when times are computed for the rounded site.
  - The hidden-mode reason is shown where the almanac would be.
- Tests: `tests/test_location_privacy.py`, 15 tests. The astronomy layer is replaced by recorders, so no Skyfield is needed. 11 of the first 13 fail against the previous server.
- Remaining, documented in `docs/api/endpoints.md`: `/api` → `gps.sats` azimuth and elevation are not filtered. With a public GNSS almanac they roughly constrain the position.

## 2026-10-02 — hidden mode drops satellite azimuth/elevation (fix/hidden-sat-angles)

- `/api` → `gps.sats`: in `hidden` privacy mode, `el` and `az` are null. With a public GNSS almanac and the response time, they constrain the receiver's position. `exact` and `rounded` keep them. IDs, constellation, C/N₀ and used flags are kept in every mode. Helper: `config.privacy_sats()`. It applies to the live and demo paths.
- Legacy `dashboard.js` satellite widget shows "–" for a null angle instead of "null°". Display change only.
- Web UI: in hidden mode the sky plots say why they are empty; the demo adapter mirrors the rule.
- Tests: 6 more in `tests/test_location_privacy.py` (now 20). Correction to the previous entry: that PR added 14 tests, not 15.
- Docs: `docs/api/endpoints.md` privacy notes. The residual (which satellites are tracked) is documented.
- Roadmap: `ROADMAP-DESKTOP-FIELD-APP.md` accuracy table now labels the NMEA-only path `inferred`; `estimated` was not one of the six provenance labels.

## 2026-10-02 — project status table (docs/status)

- `docs/STATUS.md` has one table of every spec item (CHG, TASK, OBS, ADD), roadmap feature (registry A–J, current scope), web-UI port item and independent-review finding: 351 rows. Each row has a status (done / in progress / next / planned) and PR links, and the file lists the next 5 tasks in order.
- Statuses come from an inventory checked against the code and tests on 2026-10-02. Items that are partly built are "planned" or "next" with a "partial:" note.
- `CLAUDE.md`: new rule to update `docs/STATUS.md` in every PR. `docs/INDEX.md` links it.

## 2026-10-02 — PPS UI: source-aware banner, timing-chain card, PPS diagnostics page (feat/pps-ui)

- **Banner** (`web/src/components/timing.tsx`, every page and the header chip). Built only from `/api/timing-chain`:
  - always names the sync source;
  - shows PPS outage duration and start;
  - shows `INCONSISTENT REPORT` instead of GPS/PPS if chrony's selected source isn't PPS;
  - never shows a bare `SYNCHRONIZED`.
- **Header** stratum/reference now come from the timing chain. They no longer mix in `/api`'s separate snapshot (which showed STRATUM 1 while chrony was unknown).
- **Timing-chain card** first on the Overview: GNSS → PPS device → PPS signal → chrony PPS → system clock, per the CHG "Dashboard Requirement" hierarchy.
- **PPS Diagnostics page:**
  - answers to the 12 CHG acceptance questions;
  - device, live PPS (measurement layer labeled), chrony refclock;
  - outage events with recovery details;
  - stages, raw `chronyc -n` output;
  - COPY DIAGNOSTICS (with a fallback for plain-http LAN stations) and DOWNLOAD (local .txt).
  - The Timing page's Timing Chain tab now points there.
- **Demo:**
  - demo scenarios are selectable app-wide (`?scenario=`);
  - the client-side demo adapter gained a `network_failover` scenario and full PPS/chrony/recovery fields in the server's shapes;
  - chrony's `+0ns` sample at reach 0 is shown as "no samples".
- **Verified in the browser:**
  - all 10 server demo scenarios: the banner names a source in each; the header shows UNKNOWN stratum when chrony is unknown;
  - the client-side failover scenario;
  - COPY (fallback path) and DOWNLOAD (file intercepted and checked, not saved).
- Docs: `docs/architecture/timing-chain.md` "Web UI" section; parity list; `STATUS.md` rows marked "implemented on feat/pps-ui; awaiting review".
- **Not done:** PPS state timeline and history views (next-5 task 5); per-event `ppstest` listing; kernel/dmesg info. The web app has no unit-test harness, so the banner guards are verified in the browser only.
- Owner review approved. `STATUS.md` rows are now done with #15.
  - Decision recorded: hidden mode keeps satellite IDs, constellation, C/N₀ and used flags.
  - Next-5 reordered: Vitest harness, then administrative security **before** shipping `web/dist`, so a Pi never serves an unauthenticated reboot through the new UI.

## 2026-10-02 — web unit tests: Vitest harness (chore/vitest)

- `vitest` 5.0.3 (dev dependency) with `pnpm run test` and `web/vitest.config.ts` (Node environment, no DOM, no network). `web.yml` runs it after type-check, and the `CLAUDE.md` checks include it.
- The banner logic moved, unchanged, to the pure `web/src/lib/banner.ts`.
- 26 tests:
  - banner guards: never a bare SYNCHRONIZED; GPS/PPS with a non-PPS selected source shows UNKNOWN (CHG test 20); outage text; every demo scenario names a source;
  - formatting conventions: chrony slow/fast sign, units, null → UNKNOWN, Δf/f superscripts.
  - Disabling the inconsistent-report guard fails the test-20 case.
- `STATUS.md`: next-5 now starts with administrative security. Bounded tracking log (GPS-011/012) is fifth.

## 2026-10-02 — Dependabot (#17)

- `.github/dependabot.yml`: weekly update PRs for pip (repo root), pnpm (`web/`, minor and patch updates grouped) and GitHub Actions. Dependabot only opens PRs; they go through CI and owner review like any other change.
- New `requirements.txt` pins the station's only pip dependency, `skyfield==1.55`. `install.sh` installs from it and the Pi bundle ships it (packaging test added). Before this, `install.sh` installed whatever skyfield was latest (part of GPS-020; the trust-on-first-use ephemeris download is still open).

## 2026-10-02 — workflow actions pinned to commit SHAs (#18)

- `ci.yml` and `web.yml` reference `actions/checkout`, `actions/setup-python` and `actions/setup-node` by full commit SHA, with the release as a trailing comment: checkout v4.4.0, setup-python v5.6.0, setup-node v4.4.0. These are the newest releases of the majors already in use; no major upgrade in this change. A moved or re-pointed tag can no longer change what CI runs.
- `ci.yml` gains a guard step that fails if any `uses:` line isn't pinned to a 40-character SHA.
- Dependabot (GitHub Actions ecosystem) updates SHA pins and their version comments.

## 2026-10-02 — first tag: v1.4.0-rc.1 (#22)

- Release notes `docs/releases/v1.4.0-rc.1.md`, summarized from this change log (2026-09-18 to #18), with known open issues and rollback steps. Indexed in `docs/INDEX.md`; `docs/README.md` notes the tag.
- The annotated tag `v1.4.0-rc.1` goes on this PR's merge commit, with a GitHub pre-release using the same notes. It is the first tag in the repository.
- Version choice (owner, 2026-10-02): continue the existing 1.x numbering. The code identified as `1.4.0-dev` and the historical deployment was v1.3.0, so `v0.5.0` would have gone backwards. Release candidate because the pre-release blockers, including administrative security, are still open.

## 2026-10-02 — version read from the git tag (#23)

- `gps_time_pi/version.py` replaces the hard-coded `__version__ = "1.4.0-dev"`. It is resolved once, at import, in this order:
  - `gps_time_pi/VERSION`;
  - `git describe --tags --match "v[0-9]*" --dirty` in a checkout;
  - otherwise `unknown`.
  - The leading `v` is dropped. Examples: `1.4.0-rc.1`, `1.4.0-rc.1-3-gabc1234`, `-dirty`. This adds the commit ID the independent review found missing from version reporting.
- `/api` → `versions.app` uses it. Demo mode reports the real app version instead of `"demo"` (both the server and the client-side adapter).
- `tools/build_bundles.py` writes `gps_time_pi/VERSION` into the Pi tar and the development zip, because an installed station has no `.git`. A stray copy on disk is never archived, and `.gitignore` excludes it.
- Web UI: `vite.config.ts` injects `__GTP_UI_VERSION__` at build time from `git describe` (`GTP_VERSION` overrides it).
  - The footer shows one version when the UI and station versions match.
  - It shows both when they differ, e.g. a `web/dist` built from another commit.
  - It says "unknown" rather than guessing.
  - Pure helper: `web/src/lib/version.ts`.
- Tests: `tests/test_version.py` (resolution order, a temporary git repo with a tag, the demo version, `VERSION` in both archives) and `web/src/lib/version.test.ts` (5 tests). Checked in the demo: `/api` and the footer show `1.4.0-rc.1-dirty` on the working tree.
- CI checks out shallow clones without tags, so builds there report `unknown`. That's expected.
- README, START-HERE, `docs/README.md`, `docs/api/endpoints.md` and the Pi deploy guide are updated.

## 2026-10-02 — administrative security: GPS-014, GPS-017, GPS-019 (#24)

- **Request checks** (`gps_time_pi/security.py`, `server.Handler`):
  - **Every request:** `Host` must be on the allowlist (IP literal, localhost, this hostname(.local), or `GTP_ALLOWED_HOSTS`), else 403. This blocks DNS rebinding.
  - **State changes** (`/api/admin`, `/api/setting`, `/api/dashboard`, `/api/dashboard/reset`) are POST-only (GET → 405) and `application/json`-only (→ 415).
  - **Origin** must be same-origin or listed in `GTP_ALLOWED_ORIGINS` (→ 403).
  - The body is read, within a 256 kB bound, before any refusal. Previously an early refusal could reset the client's connection.
- **Admin token:**
  - Required as `Authorization: Bearer` for state changes outside demo mode.
  - Only its SHA-256 is stored (`admin-token.sha256` next to `config.json`, 0640). No file means admin is disabled.
  - `python3 -m gps_time_pi.admin_token` creates or rotates it; `install.sh` creates one on first install.
  - `GET /api/auth` reports the state without secrets.
  - `GTP_ALLOW_CONFIG_WRITE` and the loopback exception are removed.
- **Demo isolation:** `POST /api/admin` is simulated and never runs anything. Legacy pages show a SAMPLE DATA banner in demo mode (`app.js`).
- **Unprivileged service:**
  - `gps-time-pi.service` runs as `gps-time` with `CAP_NET_BIND_SERVICE` only, `NoNewPrivileges`, `ProtectSystem=strict` and `ProtectClock=yes`, so it can never set the clock.
  - Admin actions are fixed `systemctl` argv lists with no shell. Log flush now starts the root oneshot unit.
  - The polkit rule `system/50-gps-time-pi.rules` allows exactly those actions.
  - `install.sh` creates the user, installs the rule, and makes `/opt/gps-time-pi` `root:gps-time 1775`.
- **`/api` → `clients`** is `null` when `chronyc clients` fails or is refused, no longer an ambiguous `[]`. The UIs show UNKNOWN or "unavailable".
- **Clients:**
  - Legacy `/admin` and `/configure` send POST + JSON + token (prompt; `static/admin-auth.js`).
  - New UI: the client uses POST + Bearer; Admin access card; token kept per tab in `sessionStorage`.
- **Also fixed:** legacy templates and `custom.css` are read as UTF-8. On Windows they were decoded as cp1252, so "—" showed as "â€”".
- **Tests:**
  - `tests/test_admin_auth.py`, 24, over HTTP: methods, content types, token states, Origin, Host, demo isolation, fixed argv, service/polkit/installer static checks;
  - a UTF-8 template test;
  - `web/src/api/auth.test.ts`, 7: POST + JSON + Bearer, never in the URL; per-tab storage; 401 reason.
- **Not verified on a Pi:** systemd hardening, polkit rule, `_chrony` socket access, vcgencmd under `video`. ADR-0005 lists them.
- **Hardening before the push (owner checklist):**
  1. The token is 32 random bytes from `secrets`, compared with `hmac.compare_digest`.
  2. Security headers on every response. Legacy pages allow only their own inline scripts, by hash. The Vite build no longer inlines fonts as `data:` URIs, which the CSP blocked; CI guards it.
  3. Failed token attempts are logged to the journal without the token, with a per-IP exponential backoff (429). `/api/auth` guesses count.
  4. `install.sh` shows the token on `/dev/tty` only (`--tty-only`); without a terminal, none is created. The deploy scripts open a remote terminal only when interactive.
  5. Rollback drop-in `system/gps-time-pi-root-rollback.conf` (root service, new code), plus the full-release rollback, documented in the Pi deploy guide. A test keeps it in sync with the unit.
  - 13 more tests in `tests/test_admin_auth.py` (37). In the browser, the new UI (all pages) and all 7 legacy pages load with zero CSP violations.
- Rebased on main after #17, #18, #22 and #23. Merged as #24. STATUS: GPS-014, GPS-017, GPS-019 and "Administrative security" are done (not yet verified on a Pi). The next-5 list moves up and has 4 items until the owner picks a fifth.
- Fix found on the first push: the new `web.yml` step name `CSP guard (no inlined data: fonts …)` contained `: ` in an unquoted YAML value. GitHub rejected the whole workflow ("workflow file issue", 0 jobs), so the web checks didn't run. The name is now quoted. PyYAML parses `web.yml`, `ci.yml` and `dependabot.yml`.

## 2026-10-02 — installer uses a venv (#25)

- Root cause: `install.sh` ran `pip3 install --break-system-packages`. That overrides Debian Bookworm's PEP 668 block on system pip, and it can conflict with apt-managed Python packages (review GPS-020).
- Now:
  - `install.sh` runs `apt-get update` and installs `python3-venv`;
  - it creates `/opt/gps-time-pi/venv`, and recreates it if its interpreter no longer runs;
  - it installs `requirements.txt` with the venv's pip.
- `gps-time-pi.service` runs `/opt/gps-time-pi/venv/bin/python`. Hardening and the root-rollback drop-in are unchanged.
- No timing change: chrony, gpsd and PPS configuration are untouched.
- Tests: 2 more in `tests/test_packaging.py`. They check there's no system pip or `--break-system-packages`, that the venv is created and used, and the service ExecStart.
- Not verified on a Pi. Existing stations pick it up on the next `install.sh` run. The old system-wide skyfield is left in place (removal is in the Pi deploy guide).
- Still open for GPS-020: hash-pinned requirements, which need hashes for piwheels' ARM wheels too; the pinned DE440s checksum; and a staged install.

## 2026-10-02 — CI reports the version (#26)

- `ci.yml` and `web.yml` check out with `fetch-depth: 0`, so tags are present and `git describe` works. This resolves the #23 note that CI builds reported `unknown`.
- New steps print the version and fail if no `v*` tag is reachable: `gps_time_pi.__version__` in `ci.yml`, and `git describe` before the web build. A shallow checkout can't silently bring back `unknown`.
- No STATUS row changes except the note on the version row.

## 2026-10-02 — web/AGENTS.md lists version.ts and auth.ts (#27)

- `web/AGENTS.md` project structure now lists `src/lib/version.ts` (from #23) and `src/api/auth.ts` (from #24), plus the `__GTP_UI_VERSION__` define in `vite.config.ts`. Docs only; no status change.

## 2026-10-02 — v1.4.0-rc.2 (#28)

- Release notes in `docs/releases/v1.4.0-rc.2.md`, covering #19–#21 and #23–#28, with upgrade notes (admin token on the first interactive deploy, `GTP_ALLOWED_HOSTS`), known open issues and two-level rollback. v1.4.0-rc.1 is the Level 2 target.
- The annotated tag `v1.4.0-rc.2` goes on this PR's merge commit, with a GitHub pre-release using the same notes.
- Indexed in `docs/INDEX.md`. README, START-HERE, `docs/README.md` and the Pi deploy guide's Level 2 rollback name the tags.

## 2026-10-02 — actionlint in CI (#29)

- Why: in #24, an invalid `web.yml` made GitHub skip every web check (a "workflow file issue" run with 0 jobs), while the PR page still looked green from the Python checks.
- `ci.yml` has a new `workflows` job. It downloads actionlint 1.7.12 for linux_amd64, checks it against a SHA-256 pinned in the workflow (taken from the release's checksums file), and lints every file in `.github/workflows/`. On the runner, actionlint also runs shellcheck on `run:` scripts.
- Checked locally: the current workflows pass. The `web.yml` from #24's first push fails with `could not parse as YAML`.
- Limits:
  - An invalid `ci.yml` can't lint itself. GitHub shows that as a failed run with no jobs.
  - Dependabot doesn't update the actionlint pin; the version and checksum are bumped by hand, together.

## 2026-10-02 — deploy scripts stop on failure (#30), GPS-021

- Root cause: Windows PowerShell 5.1's `$ErrorActionPreference = 'Stop'` doesn't stop on a native command's non-zero exit. `deploy-to-pi.ps1` carried on after a failed `python tools/build_bundles.py` and uploaded whatever old archive was in `dist/`. Neither script checked the archive on the Pi before running `sudo bash install.sh`, and both uploaded to a fixed `/tmp` name.
- `deploy-to-pi.ps1` runs every python/scp/ssh call through `Invoke-Native`, which throws when `$LASTEXITCODE` is non-zero. `deploy-to-pi.sh` already used `set -euo pipefail`.
- Both scripts now:
  - delete any old archive before building and fail if the build produced none;
  - upload into a fresh `~/gps-time-deploy` (mode 0700) instead of `/tmp`;
  - check the archive's SHA-256 on the Pi (`sha256sum -c`) before extracting and running `install.sh`.
- The bash script also uses `shasum` on macOS and is safe with an empty array under bash 3.2.
- Tests: `tests/test_deploy_scripts.py` (static checks, plus fake python3/ssh/scp/sudo on PATH):
  - the bash script on POSIX/CI: success, failed build, build without an archive, corrupted upload, failed upload;
  - the PowerShell script on Windows: success with the right checksum, failed build, failed upload.
  - All 7 tests that run on Windows fail against the previous scripts.
- `STATUS.md`: GPS-021 is next-5 item 5 (owner: must land before any Pi deploy) and done. Not yet run against a real Pi.

## 2026-10-02 — sun shifts per day (#31)

- **`/app/` Sun & Daylight card** (also on the Sun & Astronomy page): a "Shift per day" table, labeled `predicted`.
  - Rows: sunrise, solar noon, sunset and daylight length. Columns: the change vs yesterday and to tomorrow.
  - Values are signed whole seconds with a real minus (e.g. `+57 s`, `−126 s`).
  - An event's shift is (later instant − earlier instant − 86 400 s), so a DST switch isn't counted as a solar shift. If the UTC offset differs between the days, a note says the hour is excluded.
  - A missing event (polar day or night) shows "—", never 0.
  - Daylight uses the server's `delta_yesterday` / `delta_tomorrow`.
  - Logic in `web/src/lib/sun.ts`.
- **`/api/almanac`:** `neighbors.{yesterday,tomorrow}` gains `noon`. Both demos (server and client-side adapter) carry yesterday's and tomorrow's noon, consistent with their daylight deltas.
- **Legacy dashboard (`static/dashboard.js`) Sun & daylight widget:**
  - "change vs yesterday" used `Math.abs(...)`, which dropped the minus sign: a shortening day read "182.8 s" instead of "−182.8 s".
  - A missing value showed as 0.
  - Both changes now use `signedSeconds()`, which gives `+`/`−` (U+2212) and "–" when unknown. Fix only; no restyle.
- **Tests:**
  - `web/src/lib/sun.test.ts` (10): shift sign and value, null handling, DST exclusion, the clock-change flag, demo consistency, formatting.
  - `web/src/lib/legacy-dashboard.test.ts` (3): it evaluates the legacy helper from the file and fails to load against the previous `dashboard.js`.
- **Checked in the demo:** the `/app/` table reads sunrise +57/+57 s, solar noon −35/−34 s, sunset −126/−125 s, daylight −183/−182 s. The legacy widget reads "−182.8 s change vs yesterday". No console errors.

## 2026-10-04 — roadmap: SDR and RF observatory (#32)

- Added `docs/roadmap/ROADMAP-SDR-RF-OBSERVATORY.md` (owner-provided, copied verbatim; SHA-256 `fbb9dd26…`) and indexed it in `docs/INDEX.md`.
- Status SCOPING, not scheduled. Pi timing work and the first Pi deploy come first. No rows added to `STATUS.md`; it's listed there as unscheduled work outside the table.

## 2026-10-04 — v1.4.0-rc.3 (#33)

- Release notes in `docs/releases/v1.4.0-rc.3.md`, covering #29–#33: deploy scripts (GPS-021), sun shifts, actionlint, the SDR roadmap. They also state what `install.sh` does to chrony on every run (it restarts it) and that nothing in the 1.4 line has run on a Pi yet.
- The annotated tag `v1.4.0-rc.3` goes on this PR's merge commit, with a GitHub pre-release using the same notes.
- Indexed in `docs/INDEX.md`; README and START-HERE name the version.

## 2026-10-04 — first Pi deploy checklist (#34)

- `docs/deploy/first-pi-deploy.md`: a step-by-step checklist for upgrading a v1.3 station to v1.4.0-rc.3.
  - SSH key setup from Windows.
  - Read-only pre-flight on the Pi: OS and polkit version, the `_chrony` and `video` groups, disk, Internet, current timing state.
  - Backups: the whole `/opt/gps-time-pi`, `config.json`, `chrony.conf`, system configuration and the before-state, copied off the Pi to a folder outside the repository.
  - The interactive deploy command, from the tag, and what it should print.
  - Checks afterward: service user, polkit (one allowed and one refused action), timing chain, token, web pages, survey.
  - Rollback: timing configuration check, Level 1 drop-in, Level 2 restore of the v1.3 backup.
- It states what the deploy does to the station: `install.sh` restarts chrony, and `/app/` returns 503 until the built UI is copied by hand (optional step) or shipped in the bundle.
- Written from the code and docs. No command in it has been run against a Pi; the deploy itself is the owner's step.
- `STATUS.md`: new row "First Pi deploy of the 1.4 line" (next).

## 2026-10-04 — the Pi bundle ships the web UI (#35)

- The Pi archive now carries the built UI as `gps-time/web/dist`, and `install.sh` installs it to `/opt/gps-time-pi/web/dist`, removing the previous copy first. `/app/` works on a station without Node. Before, a station returned 503 there.
- `tools/build_bundles.py`:
  - stops if `web/dist` isn't built, or if it was built from another version than the checkout. The Vite build now writes `dist/version.txt` for that check.
  - `--without-web` builds a bundle with no UI.
  - The development zip no longer sweeps in `web/node_modules` (part of GPS-022). The bundle tests run faster for it.
- `deploy-to-pi.ps1` and `deploy-to-pi.sh` build the UI (`corepack pnpm install --frozen-lockfile`, `pnpm run build`) before the bundle. A failed UI build stops the deploy. The deploying machine needs Node 22 with corepack.
- `install.sh` changes only by the copy step. It still edits `chrony.conf` and restarts chrony as before.
- Tests:
  - `tests/test_packaging.py`: the tar ships the UI with 0644/root members, version match and mismatch, an unbuilt UI, `main()` stopping without one, the installer's copy order, no `node_modules` in the zip.
  - `tests/test_deploy_scripts.py`: the UI is built before the bundle, and a failed UI build stops both scripts.
- Checked locally: a real bundle extracted to a temp directory serves `/app/` (200) and `/app/version.txt`, and `/api` reports the version from the `VERSION` file with no git present. Not yet run on a Pi.
- Docs: Pi deploy guide, first-deploy checklist (`/app/` now expected to work; the manual copy step is gone), ADR-0004 update, `STATUS.md` (row done; next-5 moves up).

## 2026-10-04 — fresh Pi install checklist; installer preflight (#36)

- `docs/deploy/fresh-pi-install.md`: a checklist for a newly flashed Raspberry Pi OS Lite, ending with a station on v1.4.0-rc.4.
  - Steps: SSH key; packages (chrony, gpsd, pps-tools); UART and PPS configuration from `tools/generate_config.py`; deploy; reboot; hardware checks (`cgps`, `ppstest`); chrony refclocks; station checks.
  - The chrony GPS/PPS refclock lines are added **after** the reboot. chrony exits at startup if `/dev/pps0` doesn't exist, and `install.sh` restarts chrony, so adding them before the reboot would abort the install.
  - The example hostname is `gpstime.local`; the user name is a placeholder, per the rule on personal infrastructure details.
  - It flags that Python 3.13 (Raspberry Pi OS on Debian 13) isn't covered by CI, which runs 3.11.
  - Written from the code and the hardware docs. No command in it has been run against a Pi.
- `install.sh` starts with a preflight. Before changing anything, it stops if it isn't run as root, chrony isn't installed, `/etc/chrony/chrony.conf` is missing, or the `_chrony` or `video` group doesn't exist. It warns if gpsd is missing. Before, a fresh Pi without chrony failed partway through, after the venv and the application were already copied. Part of GPS-020.
- `generated/` (the output of `tools/generate_config.py`) is now in `.gitignore` and left out of the development zip. It holds the LAN subnet.
- `first-pi-deploy.md` targets v1.4.0-rc.4 and mentions the preflight.
- Tests: 2 more in `tests/test_packaging.py`: the preflight comes before any change, and (POSIX) it stops with "Nothing was changed" when chrony is missing.

## 2026-10-04 — v1.4.0-rc.4 (#37)

- Release notes in `docs/releases/v1.4.0-rc.4.md`, covering #34–#37: the bundle ships the web UI, the installer preflight, the two deploy checklists.
- The annotated tag `v1.4.0-rc.4` goes on this PR's merge commit, with a GitHub pre-release using the same notes.
- Indexed in `docs/INDEX.md`; README and START-HERE name the version.

## 2026-10-04 — Debian 13 (Trixie) and Python 3.13 (#38)

The station Pi runs Raspberry Pi OS on Debian 13 with Python 3.13. Until now CI ran 3.11 only.

- **CI:** `ci.yml` runs the Python job on 3.11 and 3.13. Two new steps on each:
  - install `requirements.txt` into a venv, as `install.sh` does, and import skyfield and numpy;
  - `pip download --only-binary=:all:` for cp311/cp313 on manylinux aarch64, so a pin without a Pi wheel fails CI.
- **Checked locally on Python 3.13.15:** the 187 tests pass with no deprecation warnings. `skyfield==1.55` resolves to numpy 2.5.3, sgp4 2.27, jplephem 2.24 and certifi, all with cp313 (or abi3 or pure-Python) aarch64 wheels, and they import and build a timescale. Only skyfield is pinned; the others float (hash-pinning is still open under GPS-020). The full almanac path needs the JPL ephemeris and wasn't run.
- **`install.sh`:**
  - It no longer forces `/etc/polkit-1/rules.d` to mode 0755 when the directory exists. Debian's polkitd package owns it.
  - The preflight warns if polkit (`pkaction`) isn't installed; the admin actions need it.
  - Nothing else in it is release-specific: the chrony path, the `_chrony` and `video` groups, `python3-venv` and the unit's options are the same on Debian 12 and 13.
- **Docs:**
  - `fresh-pi-install.md`: states both supported releases, installs `polkitd` and `python3-venv` explicitly, verifies the serial console is off (with a manual fallback if `raspi-config` lacks the option), and checks that chrony writes the RAM tracking log.
  - `first-pi-deploy.md`: accepts `bookworm` or `trixie`.
  - Both checklists target v1.4.0-rc.5. `CLAUDE.md` names the CI Python versions.
- Tests: 2 more in `tests/test_packaging.py` (the polkit directory, the polkit warning).
- Not yet run on a Pi.

## 2026-10-04 — v1.4.0-rc.5 (#39)

- Release notes in `docs/releases/v1.4.0-rc.5.md`: Debian 13 and Python 3.13 tested in CI, the aarch64 wheel check, the polkit directory fix.
- `fresh-pi-install.md` gains an almanac check. The almanac with the real ephemeris isn't covered by the tests on Python 3.13, so the checklist verifies it on the station.
- The annotated tag `v1.4.0-rc.5` goes on this PR's merge commit, with a GitHub pre-release using the same notes.
- Indexed in `docs/INDEX.md`; README and START-HERE name the version.

## 2026-10-04 — deploy-to-pi.ps1: ssh `-t` joined to user@host (#40)

- Reported by the owner on the first run against a Pi: the install step failed with ssh's `Bad configuration option: ...`. The build, the first ssh call and the upload had succeeded; `install.sh` never ran, so nothing was installed.
- Root cause: `$TtyOpt = if (...) { @() } else { @('-t') }`. A PowerShell `if` expression unwraps a one-element array to the string `-t`, and `'-t' + @($Remote, $RemoteCmd)` is then string concatenation. ssh received one argument, `-tuser@host set -e; ...`, and read it as a run of flags (`-t -n -s -o ...`).
- It only happened with an interactive terminal. The tests ran with redirected output, where the option list was empty and the bug couldn't show. The #30 change log said the PowerShell script was tested; that covered the redirected path only.
- Fix: the argument list is built element by element (`List[string]`).
- `GTP_DEPLOY_TTY=1` or `0` overrides the terminal detection in both scripts, so the tests can run the terminal path.
- Tests: `test_exact_ssh_argv` for both scripts, with and without `-t`. The fake ssh records the exact argv (on Windows through the real interpreter, which parses the command line by the same rules as ssh.exe). The tests assert the prepare call and the install call element by element. With the old line put back, the PowerShell test fails with `['-tpi@pi.example set -e; ...']`.
- Not yet re-run against the Pi.

## 2026-10-04 — v1.4.0-rc.6 (#41)

- Release notes in `docs/releases/v1.4.0-rc.6.md`: the `deploy-to-pi.ps1` ssh argument fix (#40). The station software is unchanged from rc.5.
- Both deploy checklists target v1.4.0-rc.6. The fresh-install checklist says which part has now run against a Pi (build and upload only).
- The annotated tag `v1.4.0-rc.6` goes on this PR's merge commit, with a GitHub pre-release using the same notes.

## 2026-10-04 — roadmap: web-based updates and config upload (#42)

- Added `docs/roadmap/ROADMAP-WEB-UPDATES.md` (owner-provided, copied verbatim; SHA-256 `98023c1c…`) and indexed it in `docs/INDEX.md`.
- Status FUTURE, low priority: not before the station has run stably on v1.4.0. `STATUS.md` lists it as unscheduled work outside the table, with that label. No rows added.

## 2026-10-04 — astronomy says why it is unavailable (#43)

Reported from the first Pi build: the legacy dashboard showed "Astronomy data unavailable." with no reason.

- **What was checked.** With the real DE440s ephemeris, on Python 3.13.15 with numpy 2.5.3 and skyfield 1.55 (the versions the Pi resolves), all nine astronomy functions compute: solar day, daylight deltas, lunar day, night, sky snapshot with and without a target, object report for a planet and a star, sidereal time. So the code path isn't the Pi's cause. **The Pi's own cause isn't known yet**; it needs the station's answer from `/api/almanac`, which now states it.
- **Defect found: the reason was thrown away.** The widget printed the same sentence for three different cases: the station's `reason`, a server exception (returned as `{"error": ...}`), and no answer at all.
  - Legacy widget: shows the reason, the error, or "the station did not answer /api/almanac".
  - `/api/almanac` and `/api/object`: a calculation that raises now answers `{available: false, reason: "Astronomy calculation failed (...)"}`, and the traceback goes to the journal.
  - `/api` gains `astro_reason`.
- **Ephemeris reasons are told apart** (`astro.ephemeris_problem`): missing, not readable by the service user, empty or truncated. Before, an unreadable file was reported as missing.
- **`install.sh`:**
  - makes the code, the venv, the web UI and the ephemeris world-readable (`chmod -R a+rX`), whatever root's umask was. The state directory and the token file are not touched.
  - ends with a self-check that imports the astronomy layer **as `gps-time`** and prints `Astronomy: available` or the reason.
- **Also fixed while testing:**
  - `astro.night` used the glibc-only `%-d` (GPS-030), which failed on Windows. Linux output is unchanged.
  - `requirements.txt` caps `numpy<2.7`: skyfield 1.55 assigns `ndarray.dtype`, which NumPy 2.5 deprecates. It still works on 2.5.3, as a warning.
- **What astronomy needs at runtime, all offline:**
  - `de440s.bsp` (Sun, Moon, Earth and planets, 1849–2150; the code enforces 1850–2149);
  - the time scales bundled inside the skyfield package (leap seconds and ΔT, as of that skyfield release);
  - the star and constellation JSON files in `gps_time_pi/data/`;
  - the system time-zone database;
  - the station's position.
- Tests: `tests/test_astro_status.py` (11, two of them POSIX-only for unreadable files) and `web/src/lib/legacy-almanac.test.ts` (5).

## 2026-10-04 — NTP client list for the unprivileged service (#44)

Reported from the first Pi build: "Client list unavailable (chronyc clients not readable)".

- **Cause.** chronyd answers `clients` only over its Unix socket; over UDP it replies "501 Not authorised". To use the socket, chronyc must create its own reply socket inside `/run/chrony`. The web service can't: its unit's `ProtectSystem=strict` makes `/run` read-only for it, and the directory belongs to `_chrony`. The `_chrony` supplementary group added in #24 never granted this. v1.3 ran as root, so it worked there. This is derived from how chrony works; it has not been confirmed on the Pi yet (`sudo -u gps-time chronyc -n clients` should print the 501 message).
- **Not done: giving the web service the socket.** It controls chronyd, including stepping the clock.
- **Fix:** `gps-time-pi-chrony-clients.service` runs as `_chrony` (never root), follows chrony's lifecycle, and runs `scripts/chrony-clients.sh`.
  - The script runs the fixed command `chronyc -n clients` every 15 s and takes no input.
  - It writes the output atomically to `/run/gps-time-pi/chrony-clients.txt`: RAM, not the SD card; directory 0750 and file 0640 with group `gps-time`, because the list holds client addresses.
  - On failure it removes the file and logs the error once, not every interval.
- `gps_time_pi/chrony.py` reads the file and ignores one older than 60 s, so a stopped helper reads as UNKNOWN. Without a file it runs `chronyc` directly as before, which works as root (the rollback drop-in). `/api` no longer starts a chronyc process per request for the client list.
- `/api` → `clients` is now up to about 15 s old.
- `install.sh` installs, enables and starts the helper. A helper that fails to start is a warning, not a failed install.
- No change to chrony's configuration or behavior; the helper only reads.
- Tests: `tests/test_chrony_clients.py` (15): the parser, fresh/stale/missing/future-dated file, the script with a fake chronyc (POSIX: exact command, atomic file, failure removes the list), the unit's user, group, modes and sandbox, and that the web service's unit doesn't get `/run/chrony`.
- Docs: ADR-0005 update (decision and rejected alternatives), API reference, deploy guide and both checklists (helper status check; rollback removes the unit).

## 2026-10-04 — main clock in local time (#45)

Display only. The system clock, chrony, logs and every timestamp in the API stay on UTC; nothing reads or sets the Pi's system time zone.

- **Zone** (`gps_time_pi/localtime.py`, `/api` → `timezone`), in this order:
  1. the operator's override (`POST /api/setting {"timezone": ...}`, admin token; Administration → Local time zone);
  2. the zone found **offline** from the station's position, preferring the surveyed site over a single live fix. Labeled `calculated`;
  3. none: the page uses the browser's own zone.
- **Privacy:** a zone narrows the position to a region, so in `hidden` mode it is never derived from the position; the override or the browser's zone is used. `rounded` mode looks up the rounded position only. Same rule as astronomy (`config.privacy_site`).
- **Library:** `tzfpy==2.1.0`, pinned in `requirements.txt`. One 2.9 MB wheel covers Python 3.11 and 3.13 on aarch64, with no dependencies.
  - `timezonefinder` was the suggestion, but its current release has no prebuilt wheel for Python 3.13 on aarch64 (the station must never need a compiler), and the version pip falls back to is 44 MB plus a compiled dependency.
  - tzfpy's zone boundaries are simplified, so a station very close to a zone border may get the neighbouring zone; the override covers that.
  - The import is guarded like astronomy's: without the library there is no zone and the page uses the browser's.
- **Main clock** (`/app/` header, `web/src/lib/localtime.ts`):
  - local time with the zone abbreviation, UTC offset and a DST marker, e.g. `9:15:07 PM EDT UTC−4 · DST`;
  - beneath it, UTC and the Unix epoch;
  - a 12/24-hour toggle, remembered per browser in `localStorage`; until chosen it follows the browser's locale;
  - offsets, abbreviations and DST come from the browser's time-zone database for the chosen zone. Where the browser has only an offset name (`GMT+2`), just the offset is shown.
- **Unchanged:** the clock still ticks from the browser's clock, as before (GPS-004 is open). The sun and moon times still use the browser's zone.
- **Tests:**
  - `tests/test_localtime.py` (18): order of sources; hidden mode makes no lookup; rounded mode looks up the rounded position; override validation; missing library; the setting over HTTP with and without the token; nothing in the code sets a system time zone.
  - `web/src/lib/localtime.test.ts` (16): zone choice, offsets, DST in both hemispheres and at the transition, 12/24-hour formats, UTC and epoch, the stored preference, the demo adapter's privacy rule.
  - CI runs the real lookup through `tzfpy` on both Python versions (USNO → `America/New_York`).
- **Checked in the demo:** the header clock, the toggle surviving a reload, and setting an override from Administration. Not yet seen on a Pi; the next `install.sh` run installs `tzfpy` into the venv.

## 2026-10-05 — roadmap: oscillator profile and smaller items (#46)

- Added `docs/roadmap/ROADMAP-OSCILLATOR-AND-MISC.md` (owner-provided, copied verbatim; SHA-256 `6e4c30cf…`) and indexed it. Status FUTURE; none of it blocks v1.4.0. No rows added to `STATUS.md`.
- Owner-provided documents checked against the owner's copies on 2026-10-05:
  - `ROADMAP-SDR-RF-OBSERVATORY.md` and `ROADMAP-WEB-UPDATES.md`: byte-identical.
  - `ROADMAP-DESKTOP-FIELD-APP.md`: differs by one word, on purpose. #13 changed the accuracy table's label from `estimated` to `inferred`, because `estimated` isn't one of the six provenance labels. The repository copy is kept.
  - The four files from `gps-time-specs.zip`: the archive wasn't available to compare. They have had one commit each since the import (which recorded the archive's SHA-256), so they are unchanged since then.
  - `GPS-Time-Project-Vision-and-Roadmap.md`: not found on the machine, and not in the repository.

## 2026-10-05 — big clock: the station's time in the local zone (#47)

Follow-up to #45, which the owner asked for as "big clock is GPS-derived local time, UTC beneath". #45 put a small clock in the header that ticked from the browser's clock.

- **Big clock on the Overview** (`web/src/components/clock.tsx`), directly under the timing-chain card: local time in large figures; the date, zone, UTC offset and DST marker; UTC beneath; then the Unix epoch. The 12/24-hour choice is shared with the header clock.
- **It shows the station's time, not the browser's.** The browser's clock is corrected by the measured station − browser offset (the four-timestamp exchange with `/api/ping`). The reading is labeled `inferred`, and the card states the offset applied, the best round trip, and that the display can be off by about half the round trip.
- **It says GPS/PPS only on evidence** (`clockDiscipline` in `web/src/lib/banner.ts`): the caption is "GPS/PPS-DISCIPLINED STATION CLOCK" only when the status is GPS/PPS and chrony's selected source is the PPS refclock. Otherwise it names what the banner names: network failover, unsynchronized, inconsistent report, unknown.
- **Before any offset is measured**, or if `/api/ping` fails, the caption reads "THIS BROWSER'S CLOCK · STATION TIME NOT MEASURED YET".
- The header clock uses the same station time. One `/api/ping` loop now serves the whole app (it lives in `StationProvider`); before, each page that used it ran its own.
- GPS-004 is partly addressed: the `/app/` clocks no longer show the browser's clock as if it were the station's. The legacy dashboard's "UTC reference" card is unchanged.
- Tests: `clockDiscipline` (4) and `stationInstant` (2); 78 web tests in all. Checked in the demo with the `pps_selected` and `network_failover` scenarios.

## 2026-10-05 — chrony polling the station itself (#48)

From the owner's list: "Filter the station's own address out of chrony sources picked up from DHCP."

- **What happens.** When the router's DHCP names the station as the LAN's NTP server, the station receives that too, and Debian's chrony adds it as a source (`sourcedir /run/chrony-dhcp`). The station then polls its own address. That source looks like a healthy stratum-1 server, and the software counted it as a network reference: a status could read "NETWORK FAILOVER", synchronized, while chrony was following itself.
- **Fix, in the station software:**
  - `chrony.parse_sources` marks a network source whose address is one of the machine's own (`ip -o addr show`, read-only, cached 60 s; loopback always) with `is_self`.
  - If chrony **selects** it, the status is `HOLDOVER · NO EXTERNAL REFERENCE · CHRONY SELECTED THIS STATION ITSELF`, with the address and what to do.
  - It is never recorded as a fallback source in an outage event, and the Fallback source stage reports it.
  - `/api/timing-chain` → `chrony.selected.is_self` and `chrony.self_sources`; `/api` → `sources[].is_self`. The Network page marks the row THIS STATION.
  - Listed but not selected (PPS selected) doesn't change the status.
- **Not done: changing chrony's configuration.** The software only reads chrony. Stopping chrony from polling itself is a documented operator step: comment out `sourcedir /run/chrony-dhcp` on the station. It's in the fresh-install checklist with a check that finds the problem, and in the deploy guide.
- Tests: `tests/test_self_source.py` (12) with two new source fixtures. Not yet seen on a Pi.

## 2026-10-05 — NMEA refclock offset: a measured recommendation (#49)

From the owner's list: "Calibrate the NMEA refclock offset from measured data." The project's chrony snippet uses a fixed guess, `offset 0.1`.

- **What is measured.** Serial time messages arrive a roughly constant delay after the second they describe, and chrony's `offset` option compensates for it. While PPS disciplines the clock, chrony's own statistics for the NMEA source show what is left over: the `chronyc sourcestats` Offset for NMEA is the residual.
- **`/api/timing-chain` → `chrony.nmea_calibration`** (`timing_chain.nmea_calibration`): the configured offset read from `chrony.conf`, the residual, its standard deviation and sample count (observed), and the suggested offset, configured + residual (calculated).
  - Reported only while PPS is the selected source and chrony has at least 16 NMEA samples; otherwise it says why it isn't measurable.
  - A residual within three standard deviations, or under 5 ms, is reported as "no change is needed".
- **The station never edits `chrony.conf`.** The PPS diagnostics page and the diagnostics snapshot show the recommendation; the operator makes the change. This follows the rule against changing timing behavior.
- **Sign.** In chrony's reports a positive offset means the local clock is ahead of the source, so a positive residual means NMEA is still late and the offset should go up. That is chrony's documented convention, not something confirmed on this hardware yet. So the advice includes a check: after the change the residual should be near zero; if it has doubled, use configured − residual instead.
- `chrony.refclock_config` now reads each refclock's `offset` (0 when absent, unknown when unparseable).
- Tests: `tests/test_nmea_calibration.py` (13), including that nothing in the package opens a chrony file for writing. Demo data: 0.1 s configured, +35 ms residual, 0.135 s suggested.

## 2026-10-05 — satellite C/N₀ bars rendered empty (#50)

Reported from the Pi, with CSP blocking inline styles as the suspected cause.

- **Cause: CSS, not CSP.** The legacy dashboard draws each bar as `<i class="barfill" style="width:72%">`. The rule was `.barfill{height:100%;background:...}` with no `display`, so the `<i>` stayed `display: inline`, and CSS ignores width and height on inline elements. The bars have been empty since the 2026-09-18 baseline, in the demo too; it isn't specific to the Pi.
- **Measured in a browser against the station's real headers:**
  - On the legacy page the inline width **was** applied (`style.width` read `72%`); the element rendered 0 × 0 px because it was inline.
  - After the fix it renders 109 × 5 px in a 175 px track for 62%.
- **Fix:** `.barfill{display:block;...}`. One declaration; no restyle.
- **CSP check of every page, as asked:**
  - All legacy pages (`/`, its four tabs, `/legacy`, `/almanac`, `/history`, `/admin`, `/configure`, `/zones`) are served `style-src 'self' 'unsafe-inline'`, so their style attributes aren't blocked.
  - `/app/` is strict (`style-src 'self'`). All 12 of its pages were opened with a CSP violation observer, including buffered load-time reports: zero violations. React sets styles through the DOM, which CSP doesn't block. Its C/N₀ bars render.
  - The only other inline element given a size in the legacy pages sets `display:inline-block` itself.
- **Tests** (`tests/test_inline_styles.py`, 6):
  - every inline element given a width or height in the legacy pages must have a display that can take one (fails on the old CSS, naming `barfill`);
  - legacy pages that use style attributes are served a CSP that allows them, and scripts never get `'unsafe-inline'`;
  - the strict CSP has no inline exception, and the new UI's source never builds HTML strings or style attributes that it would drop.
- Browsers cache the stylesheet for 5 minutes, so the fix can take that long to show after a deploy.

## 2026-10-05 — legacy Sun widget: "loading" is not "did not answer" (#51)

- Correction to #43. Before the first `/api/almanac` answer arrived, the legacy Sun widget said "the station did not answer /api/almanac". It now says "Astronomy data: loading…" until an attempt has actually failed.
- An almanac request that fails no longer stops the rest of the legacy dashboard from rendering or marks the whole server unavailable; only the Sun widget reports it.
- Tests: 2 more in `web/src/lib/legacy-almanac.test.ts`. No status change.

## 2026-10-05 — installer: chrony takes no NTP servers from DHCP (#52)

Owner decision, 2026-10-04: the installer makes the change that #48 left as an operator step. It is also the first of the smaller items in the owner's timing-metrology spec, which the next PR adds to `docs/specs/`.

- **This changes chrony's configuration**, on the owner's explicit instruction. `install.sh` comments out `sourcedir /run/chrony-dhcp` in `/etc/chrony/chrony.conf`, so chrony no longer adds the NTP servers a DHCP server hands out and can't end up polling the station's own address. The installer restarts chrony afterwards, as it has since v1.3.
- **Scope of the edit** (`scripts/chrony-no-dhcp-sources.sh`):
  - only that one line; refclocks, `pool`/`server` lines and `sourcedir /etc/chrony/sources.d` are untouched;
  - the file as it was before the first change is kept as `chrony.conf.before-gps-time-pi`, and never overwritten;
  - a second run changes nothing;
  - `GTP_KEEP_DHCP_NTP=1` skips it;
  - a failure is a warning, not a failed install.
- **Consequence to know about:** a station whose only network fallback came from DHCP has no network fallback after this, until a `server` or `pool` line is added. Debian's default `pool` line is not affected.
- The running web service still only reads chrony. The #48 detection (`is_self`, THIS STATION, the HOLDOVER status) stays, for a station address named some other way.
- Docs: deploy guide, both checklists (the fresh-install check now confirms the line is commented instead of asking the operator to edit it).
- Tests: `tests/test_installer_dhcp_sources.py` (12; 8 run the script against a fixture `chrony.conf` and are POSIX-only). Not yet run on a Pi.

## 2026-10-05 — v1.4.0-rc.7 (#53)

- Release notes in `docs/releases/v1.4.0-rc.7.md`: everything merged since rc.6 (#42 to #52).
- Both deploy checklists target v1.4.0-rc.7.
- The annotated tag `v1.4.0-rc.7` goes on this PR's merge commit, with a GitHub pre-release using the same notes.
- Not changed, because the facts aren't recorded in the repository: the checklists' statements about how much of the 1.4 line has run on a Pi. Several rc.7 fixes were reported from the first Pi build, so those statements may be out of date; the owner knows what ran.

## 2026-10-05 — spec: timing metrology, time scales and time distribution (#54)

- Added `docs/specs/SPEC-TIMING-METROLOGY.md` (owner-provided, copied verbatim; SHA-256 `dcb3d332…`) and indexed it. Status NEXT.
- `STATUS.md`: new area TM with 29 rows. 28 are `next`; the installer step of §6 is `done` (#52). The next-5 list's free slot (GPS-021, done in #30) now holds timing metrology.
- Owner's instruction, 2026-10-04: build §1, §3, §4 and §6 in that order, one PR each; stop before NTS (§2) and PTP (§5) and report.
- A specification is a requirement, not implemented behavior. No code changed.

## 2026-10-05 — stability analysis: ADEV, MDEV, TDEV (#55)

`specs/SPEC-TIMING-METROLOGY.md` §1. Architecture: `docs/architecture/stability-analysis.md`.

- **New: `gps_time_pi/stability.py`**, pure Python (no NumPy): overlapping Allan deviation, modified Allan deviation, time deviation; power-law noise identification by lag-1 autocorrelation; chi-squared confidence interval for ADEV.
- **Input.** The fractional second of each kernel PPS timestamp: the system clock against the PPS edges as Linux saw them. Labeled `calculated`, with the measurement layer stated in the payload and on the page. This is not the receiver's electrical PPS and not the oscillator alone.
- **Difference from the spec's wording.** The spec says "from chrony PPS offset history". chrony reports a PPS offset once per refclock poll (16 s by default), which can't give a 1 s averaging time. The kernel timestamps are the per-second samples chrony's PPS refclock consumes, so they are used.
- **Storage, RAM only:** 4 h of 1 s samples; 14 d of minute summaries (each minute's last sample for ADEV, its mean for MDEV and TDEV, both exact inputs). Lost on a service restart. Nothing is written to disk.
- **Honesty rules:** a value needs 3 averaging times of history (4 for MDEV, TDEV); a missing second is a gap and nothing is interpolated; no PPS events means `available: false`, never zero; the payload gives the share of samples taken while chrony had PPS selected.
- **Confidence bars for ADEV only.** Where there are too few points to identify the noise type, the type from a shorter averaging time is kept and the point is marked as assumed. No interval is calculated for MDEV or TDEV.
- **`/api/stability`** (recomputed at most once a minute) and **Timing → Stability** in `/app/`: log–log plot with bars, key-point table (1 s, 10 s, 100 s, 1000 s, 1 day; UNKNOWN with the reason where history is too short), and the data behind the values.
- **Poll timing changed.** The timing-chain service now polls on a fixed grid 0.25 s after each whole second. Before, its period was one second plus the tick's own duration, so the read drifted across the pulse and skipped one from time to time. This changes when the station software looks, nothing in chrony, gpsd or PPS.
- **Validated against published values** (NIST SP 1065 §12.4): the 9-point NBS set and the 1000-point suite agree to the seven digits published for ADEV, MDEV and TDEV, and for the degrees of freedom (146.177).
- Tests: `tests/test_stability.py` (33) and `web/src/lib/stability.test.ts` (10). Checked in the demo.
- Not yet run on a Pi. The cost of a full recalculation on a Pi has not been timed.

## 2026-10-05 — time scales panel (#56)

`specs/SPEC-TIMING-METROLOGY.md` §3.

- **New: `gps_time_pi/timescales.py` and `/api/timescales`.** TAI, GPS time with week number and seconds of week, Modified Julian Date and Julian Date, all `calculated` from the station's UTC clock.
- **TAI − UTC is read from a table, not hard-coded.** The spec's "UTC + 37 s at present" is what the table says today. The source is tzdata's `leap-seconds.list` (`external`, IERS data). The payload gives its path, update date and expiry date.
  - A warning starts 60 days before expiry (`GTP_LEAP_EXPIRY_WARN_DAYS`), and an expired table says that TAI and GPS time assume no leap second since.
  - If no file can be read, a built-in list ending 2017-01-01 is used and the expiry is reported as UNKNOWN, with the reason.
  - The next scheduled leap second comes from the table. When there is none, the answer says whether the table is valid enough to rule one out. chrony's own leap status is shown beside it as `observed`.
- **UT1 − UTC** is reported only from a cached IERS `finals2000A` file that the operator places on the station, labeled `external` with the file's date and whether the value is an IERS determination or prediction. The station never fetches it. A file that doesn't cover today isn't used.
- **Timing → Time Scales** in `/app/`: one panel with UTC, local time, TAI, GPS time, GPS week and seconds of week, Unix epoch, MJD, JD and local sidereal time, ticking from the station's clock (the same measured station time as the big clock). The caption says GPS/PPS only when chrony has PPS selected. Without the station's offset, TAI and GPS time read UNKNOWN; the page never assumes 37.
- **Privacy.** Nothing in `/api/timescales` depends on the location. Sidereal time still comes from `/api` and reads "hidden by location privacy" in `hidden` mode.
- **Limits.** MJD and JD are UTC-based and repeat a second during an inserted leap second, as Unix time does. The sidereal time in the panel is the value at the last `/api` update, not a ticking one.
- Nothing here sets the clock or changes chrony.
- Tests: `tests/test_timescales.py` (27; fixture leap-second lists, one with an invented future leap second, and a fixture IERS file) and `web/src/lib/timescales.test.ts` (10). Known epochs checked: GPS start, the 1999 week rollover, J2000.0, MJD 0. Checked in the demo.
- Not yet run on a Pi: that Debian's tzdata there ships `leap-seconds.list` at the expected path is assumed, and the panel says so if it doesn't.

## 2026-10-05 — independent references (#57)

`specs/SPEC-TIMING-METROLOGY.md` §4. Architecture: `docs/architecture/independent-references.md`.

- **New: `gps_time_pi/references.py` and `/api/references`.** The station is compared with NTP servers that chrony measures but isn't using to set the clock. The software reads `chronyc -n sources` (already polled by the timing chain); it contacts no server itself and writes no chrony configuration at run time.
- **Which servers count** is taken from chrony's state, not the configuration: a server chrony has selected or combined is steering the clock and isn't counted; the station's own address is never a reference; everything else is independent. A `noselect` server can never be selected, so it stays independent after a PPS loss too.
- **The comparison:** a usable reference agrees within 50 ms (`GTP_REF_DISAGREE_S`), disagrees beyond it, and is inconclusive when the offset is over the limit but inside chrony's own error bound for that server. The station is flagged when more than half of at least two usable references disagree.
- **A disagreement is not a diagnosis.** The text says the station differs from N of M references and that this doesn't say which clock is wrong or why. No cause is named. The timing-chain status and banner are not changed by it.
- **Offline:** with no server answering the answer is "no external references reachable" (`NONE_REACHABLE`), not an error. An unreachable server shows no offset.
- **Labels:** per-server values are `external`; the outcome is `calculated`.
- **Delay.** `chronyc sources` has no delay column, and `chronyc ntpdata` needs chronyd's Unix socket. The helper service from #44 (user `_chrony`) now publishes `chronyc -n ntpdata` as `/run/gps-time-pi/chrony-ntpdata.txt` beside the client list. It still runs a fixed list of read-only reports and takes no input; a failing report doesn't remove the other file. Without it, delay reads UNKNOWN.
- **History:** RAM only, one point per new measurement, at most one a minute, 1440 points per server, 16 servers.
- **Installer option, off by default** (`scripts/chrony-independent-refs.sh`): `sudo GTP_INDEPENDENT_REFS=1 bash install.sh` adds `time.nist.gov`, `tick.usno.navy.mil` and `tock.usno.navy.mil` as `noselect`, polled every 4 to 17 minutes, in one file under `/etc/chrony/sources.d/`. A custom list or `0` (remove) is accepted; only host names and addresses pass, and every line is written with `noselect`.
  - **Decision to confirm with the owner:** the spec says "continuously compare"; this is off unless asked for, because it changes chrony's configuration and makes chrony contact Internet servers. Making it the default is a one-line change in the script.
- **Timing → References** in `/app/`: the outcome, the server table (offset, bound, delay, comparison), the servers not counted and why, and offset and delay history for one server.
- Tests: `tests/test_references.py` (41; 8 of them run the installer script and are POSIX-only), `tests/test_chrony_clients.py` updated for the second report, `web/src/lib/references.test.ts` (9). Checked in the demo with `?refs=disagree`.
- Not yet run on a Pi. Not confirmed there: the state symbol chrony shows for a `noselect` server (the code doesn't depend on it), and that `ntpdata` is readable by `_chrony` over the socket.

## 2026-10-05 — NTP service counters; NMEA offsets side by side (#58)

`specs/SPEC-TIMING-METROLOGY.md` §6, the two remaining smaller items. The third, the installer's DHCP step, was #52.

- **NTP service view** (`gps_time_pi/ntpservice.py`, `/api/ntp-service`, Network page in `/app/`):
  - chrony's own counters from `chronyc -n serverstats`: NTP packets received and dropped (`observed`), with the share dropped, request rates over the last minute and hour, and a requests-per-minute chart (`calculated`).
  - **"Served" is not a chrony counter.** chrony counts packets received and packets dropped under its rate limit; it does not count replies. The page shows "not dropped (received − dropped)" as the nearest figure and says so.
  - "Dropped" is described only as chrony describes it (its rate limit). No other reason is inferred.
  - History: RAM only, one sample a minute, 24 h. The counters restart at zero with chronyd; the tracker notices, counts the restart and starts the history again.
  - Unreadable counters give UNKNOWN with the reason, never zeros.
  - `serverstats` needs chronyd's Unix socket, so the `_chrony` helper publishes it as a third fixed report (`chrony-serverstats.txt`), like the client list and `ntpdata`. ADR-0005 updated.
  - The Network page's "Request rate" row was a demo-only placeholder; it now shows the measured rate.
- **NMEA refclock offset** on the PPS diagnostics page: the configured value and the suggested value are now shown side by side, with the difference in milliseconds. When the suggestion can't be measured (PPS not selected, too few samples), its side reads UNKNOWN with the reason; the configured side still shows. The calculation from #49 is unchanged, and the station still never edits `chrony.conf`.
- Tests: `tests/test_ntp_service.py` (17), `tests/test_chrony_clients.py` updated for the third report, `web/src/lib/ntpservice.test.ts` (10). Checked in the demo.
- Not yet run on a Pi: that `_chrony` can read `serverstats` over the socket is expected from chrony's design, not confirmed.
- With this, `SPEC-TIMING-METROLOGY.md` §1, §3, §4 and §6 are done. §2 (NTS) and §5 (PTP) are not started, on the owner's instruction to stop and report first.
