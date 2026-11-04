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

## 2026-10-05 — deploy record; v1.4.0-rc.8 (#59)

- **Deploy docs now state what happened** (owner's report): v1.4.0-rc.6 was deployed to the Pi on 2026-10-04; chrony selected the PPS refclock, stratum 1, system clock offset about 300 ns. `docs/development/raspberry-pi-deploy.md` has a deployment record with the fixes found on that build (#43, #51, #44, #50) and what followed from the owner's list (#48, #49, #52).
  - The two checklists no longer say that nothing has run on a Pi.
  - Still not recorded, and left that way: which checklist was followed and the result of each individual check. The per-item "not yet verified on a Pi" notes in `STATUS.md` and ADR-0005 stay until someone records the check.
- **New: `docs/deploy/upgrade-1.4-station.md`**, for a station that already runs a 1.4 release candidate: what the upgrade changes (the one `chrony.conf` line, the helper's new reports, RAM histories starting empty), the deploy command, checks for the new endpoints, the optional `noselect` step, and what the stability page can show after a 3-day run.
- Release notes in `docs/releases/v1.4.0-rc.8.md`: everything merged since rc.7 (#54 to #58). Checklists, README and START-HERE target rc.8.
- The annotated tag `v1.4.0-rc.8` goes on this PR's merge commit, with a GitHub pre-release using the same notes.
- `STATUS.md`: "First Pi deploy of the 1.4 line" → done; new rows for the rc.8 tag and the owner's soak run (next-5 item 5).

## 2026-10-05 — spec: RF node, MLAT calibration and distributed TDOA (#60)

- Added `docs/specs/SPEC-RF-NODE-AND-TDOA.md` (owner-provided, copied verbatim; SHA-256 `8444e4d8…`) and indexed it. Status PLANNED: it builds on `roadmap/ROADMAP-SDR-RF-OBSERVATORY.md` and starts after v1.4.0.
- `STATUS.md`: new area RF with 19 rows, all `planned`. Three of them point at the existing Feature E and F rows they overlap (ADS-B 1090, MLAT solver, fox-hunt TDoA); those rows are unchanged. The next-5 list is unchanged.
- A specification is a requirement, not implemented behavior. No code changed, and no `rf-node/` directory exists yet.

## 2026-10-05 — Earth shadow and satellites (#61)

`specs/ADDENDUM-SKY-SOLAR-SATELLITE.md` §1 to §5. Architecture: `docs/architecture/earth-shadow-and-satellites.md`.

- **Shadow model** (`gps_time_pi/shadow.py`, `/api/shadow`): umbra and penumbra as two cones from a Sun of finite size, not a cylinder. The Sun's position is an analytic series (Meeus, about 0.01°), so this needs no ephemeris file, no NumPy and no network, and it works when the almanac doesn't. Labeled `modeled`.
  - Stated limits: geometric only (an airless spherical Earth, no refraction); the atmosphere moves the real edge by some tens of km of height; the sunlit fraction inside the penumbra is a linear estimate.
- **Zenith metric:** the 550 km shell's state straight up, and the heights at which the zenith line leaves the umbra and reaches full sunlight. It says that this is the zenith only. In daylight it says there is no shadow overhead.
- **Sky map:** the chosen shell (350, 550, 1200 km or a custom height) over the whole sky; clicking it asks "would a satellite at this height, in this direction, be sunlit?".
- **Contamination summary:** Sun altitude, the 550 km and 1200 km shells (share of the sky sunlit, and where), astronomical darkness, and sentences that are geometric statements. They never say a satellite is visible, and they end by saying so.
- **Satellites** (`gps_time_pi/satellites.py`, `/api/satellites`): for one satellite, the present azimuth, altitude, range, angular speed and shadow state (`modeled`), and for each pass in the next 24 h the rise, culmination and set, the penumbra and umbra crossings, and the interval in which it could be seen (`predicted`).
  - "Could be seen" is geometry: 10° up, not in the umbra, Sun 6° down. Nothing about brightness or weather.
  - SGP4 comes from the `sgp4` package that Skyfield already installs. The rest is this project's code, so passes need no ephemeris.
  - **Offline cache.** Elements are `external` and live in `tle/` next to `config.json`. The web service never fetches them. `python -m gps_time_pi.tle_fetch`, run by the operator, downloads a CelesTrak group or imports a local file; it validates checksums before replacing anything, writes atomically, and refuses to fetch the same group twice within two hours. No timer is installed.
  - **Element age** is shown on the cache, on each satellite and on the pass table, and a satellite is marked unreliable beyond 14 days.
  - Scope: one satellite at a time. Nothing counts or tracks a whole constellation.
- **Privacy:** both depend on the position. `hidden` computes neither; `rounded` uses the rounded site. Demo mode honors the mode too.
- **Sun & Astronomy** in `/app/` now has three tabs: Sun & Moon (as before), Earth Shadow, Satellites.
- **Validation:** Meeus's worked examples for the Sun and sidereal time; the known size of the Earth's shadow; zenith heights that bracket the cylinder formula; satellite direction and range against Skyfield (0.05°, 1 km) and rise and set times equal to Skyfield's to the second.
- **CI:** the plain test run has no `sgp4`, so the satellite geometry tests would be skipped there. A new step runs them in the station's virtual environment and fails if any are skipped.
- Tests: `tests/test_shadow.py` (37), `tests/test_satellites.py` (37), `web/src/lib/shadow.test.ts` (13). Checked in the demo.
- `STATUS.md`: ADD §1 to §5 and AC6, AC7 → done; AC8 stays planned (the time at which a shell goes into shadow isn't predicted). Also, on the owner's request, the three RF-spec rows that overlapped feature-registry rows are merged into one row each (three fewer rows).
- Not yet run on a Pi; the cost of a request there has not been timed.

## 2026-10-05 — legacy dashboard: removal plan, nothing removed (#62)

- Added `docs/dashboard/legacy-removal-plan.md`. It is a plan only: no file, route or test was deleted or changed.
- **Basis.** The owner asked for "the legacy-removal plan from my earlier prompt". That prompt was not found in the repository, the session memory or the searchable session transcripts. The plan is therefore built from ADR-0004 and `web-ui-parity.md`, and says so at the top. If the earlier prompt differs, it takes precedence.
- **Inventory:** the seven routes, seven templates and six static files; the server code, CSP exception, `/api` fields and saved-layout model that exist only for them; the tests and docs that would change.
- **Parity re-checked against the code:** of the 21 items, 2 are done, 3 are partly covered, the rest are open. Admin actions and survey reset are not in `/app/`, so removing `/admin` today would leave no browser way to restart a service or reset the survey.
- **Proposed order:** owner decisions; port the blockers; make `/app/` the front door while keeping the old pages for a release; then remove; then close the review findings that the removal settles (GPS-016, GPS-027, GPS-029 and the legacy halves of GPS-004, GPS-009).
- **Timing:** not before v1.4.0. The Pi runs the legacy pages and rc.8 is about to start its soak run.
- **Found:** `gps_time_pi/templates/index.html` is not served by any route. It was left in place; deleting it is listed as the one thing that could be done now, for the owner to decide.
- `STATUS.md`: the parity row's note updated; a new planned row "Retire the legacy pages".

## 2026-10-19 — rc.8 soak run: outages, holdover, rc.9 list (#69)

Docs only. Read-only checks of the Pi on 2026-10-19; nothing on the station was changed.

- **v1.4.0 was not tagged.** The rc.8 soak run lasted 14 days 20 h without a restart, but the station recorded real PPS/GNSS outages on 2026-10-17 between 19:04 and 20:35 UTC (ten events, about 71 minutes). The owner confirms they were real and that outage detection is not to be weakened.
- **Holdover recorded** in `development/raspberry-pi-deploy.md`: from chrony's tracking log (copied off the station, kept outside the repository), chrony coasted through four gaps without switching source; after the longest, 56 minutes, its first offset was +1.68 µs. One event on one board, not a specification.
- The system journal has nothing about the outages, so the station's events and the RAM tracking log were the only evidence. That is why rc.9 keeps outage evidence on the SD card.
- **Log flush checked:** it works on rc.8, but copies the whole RAM log to the SD card every hour (about 240 MB a day at the check) and logrotate keeps rotated full copies.
- **`STATUS.md`:** a "v1.4.0-rc.9: to do" list (flush fix with caps; outage evidence on the SD card under a size cap; PPS polling on its own thread with missed and unread pulses counted separately; the queued UI fixes). The rc.8 soak row is done with its result; next-5 item 5 is rc.9; OBS §13 moves to next.
- `deploy/upgrade-1.4-station.md` points to the result and says how to keep the RAM log before a restart.

## 2026-10-19 — PPS reads on their own thread; missed and unread pulses (#70)

rc.9 item 3. The rc.8 soak run counted 112,588 missed pulses (about 9 % of the run), while the real outages on 2026-10-17 account for about 4,300 s. Owner, 2026-10-19: keep counting missed pulses from the kernel's sequence number, move polling off the request thread, and don't weaken outage detection.

- **A dedicated `pps-poller` thread** reads the kernel PPS every second (0.25 s after the second) and records the newest event for the stability history. It does nothing else.
- **The chain evaluation** (chronyc calls, GNSS, outage events, references, NTP counters) runs on its own `timing-chain` thread, 0.45 s after the second. Before, one thread did both, so a slow evaluation postponed the next PPS read.
- **No HTTP request polls or evaluates any more.** `start()` evaluates once before the server takes requests; requests return the latest evaluation. Before, a request that arrived before the first evaluation ran one itself.
- **Missed pulses are still counted from the kernel's sequence number:** the pulses the elapsed kernel time calls for, minus the ones the kernel counted. Unchanged.
- **New: unread pulses** — pulses the kernel counted that the station didn't read one by one (two or more arrived between polls). Not lost; previously not shown at all.
- **New: poll statistics** — polls, late polls (more than 1.5 s apart), longest gap. With the two counters, the next run shows whether a high count is pulses that never reached Linux or the station reading late.
- **Outage detection is unchanged:** it still works from the age of the newest kernel event, every second. A test checks that a loss still opens an outage with the poller doing the reading.
- `/api/timing-chain` → `pps.unread_pulses`, `pps.poller`; the PPS page and the diagnostics snapshot show them.
- Tests: `tests/test_pps_poller.py` (16). Not yet run on a Pi.

## 2026-10-19 — oscillator log: temperature with chrony's frequency (#71)

Owner's request: "temperature logging alongside chrony frequency, to feed the oscillator profile" (`roadmap/ROADMAP-OSCILLATOR-AND-MISC.md` §1). Architecture: `docs/architecture/oscillator-log.md`.

- **Recorded once a minute:** chrony's `Frequency`, `Skew` and `Residual freq` (observed) and the SoC temperature from `/sys/class/thermal` (observed; the processor's sensor, not the crystal's, and the page says so), with whether chrony had PPS selected.
- **Storage:** 10-minute bins in RAM; finished bins appended to `oscillator-log.csv` next to `config.json` once an hour and on a clean stop (fsync). About six short lines an hour; never a write per sample. Capped at 4 MB (`GTP_OSCILLATOR_LOG_MAX_BYTES`); past the cap the oldest quarter goes in one atomic rewrite. The last 7 days are read back into RAM on start.
- **Board-bound:** the file starts with a hash of the board's serial number (never the serial) and the model. A file from another board is set aside, not mixed in.
- **Slope:** a straight line of frequency against temperature over bins with PPS selected throughout, `calculated`, once there are 36 such bins and 2 °C of range. Labeled as not the oscillator profile and not a holdover prediction.
- **Timing → Oscillator** in `/app/`: scatter with the fit, temperature and frequency over time, the log's state.
- Tests and standalone timing-chain evaluations write no log file; only the running service does.
- Not done: the profile itself (fitted model, holdover projection, export/import).
- Tests: `tests/test_oscillator.py` (23), `web/src/lib/oscillator.test.ts` (5). Checked in the demo. Not yet run on a Pi.

## 2026-10-19 — tracking-log flush: append-only, with caps (#72)

rc.9 item 1, with next-5 item 3 (GPS-011, GPS-012). Found on the rc.8 soak run: the hourly flush copied the whole RAM log (10 MB and growing) to the SD card every hour, about 240 MB a day, and Debian's logrotate kept rotated full copies.

- **`scripts/logsync.sh flush`** appends only the bytes written since the last flush to `/var/log/chrony/station-tracking.txt`. It remembers the RAM file's inode and the bytes already on the SD card; a new file (rotation, reboot) or a shorter one starts from zero.
- **RAM cap** 8 MiB: the log becomes `tracking.log.1` (replacing the previous one) and chrony reopens its logs (`chronyc cyclelogs`). Lines written in between are appended from `.1`. RAM use stays under 16 MiB.
- **SD cap** 16 MiB: the SD copy becomes `.prev`. SD use stays under 32 MiB.
- **Out of logrotate's reach:** the SD copy isn't `*.log`, so Debian's rule doesn't rotate it.
- **`restore` at boot** puts the newest 4 MiB back in RAM, from the first whole line, and records them as already flushed. The first boot after the upgrade restores from the old full copy if there is no new one yet.
- **Not deleted:** the old `/var/log/chrony/tracking.log` and its rotated copies (they may hold evidence); they age out under logrotate.
- **GPS-012:** the tracking-log path is resolved on every call, not at import. The History page reads `tracking.log.1` and `tracking.log`, oldest first.
- `/api/system` → `ramlog` gains `sd_copy` and `sd_size_kb`; `size_kb` includes `.1`.
- Units and timer unchanged.
- Tests: `tests/test_logsync.py` (16; 11 run the script and are POSIX-only, also run locally under Git Bash). Not yet run on a Pi.

## 2026-10-19 — outage evidence on the SD card (#73)

rc.9 item 2; OBS §13. On the rc.8 soak run the 2026-10-17 outages left nothing in the system journal; the evidence was the event list and the RAM tracking log, which a reboot would have lost.

- **`gps_time_pi/evidence.py`:** for each outage event, one JSON file in `evidence/` next to `config.json` with the event, a 10 s timeline of the station's view (status, PPS state and counters, chrony's view, selected source, offset, GNSS counts and best C/N₀) from a 2-hour RAM ring, chrony's tracking lines from 5 minutes before to 5 minutes after, and chrony's output when written.
- **When:** 5 minutes after the outage opens, and 5 minutes after it closes (replacing the first). A quiet station writes nothing; nothing at 1 Hz.
- **Cap:** 20 MiB (`GTP_EVIDENCE_MAX_BYTES`) and 200 files, oldest first; one file's tracking lines at most 2 MiB.
- **Privacy:** no position is stored.
- **Not captured:** kernel messages, gpsd output or raw NMEA. These would need privileges or another process; the journal had nothing for Oct 17 anyway.
- `/api/evidence` (index, or one file by `id`); Timing → PPS Events lists the files.
- Outage detection unchanged.
- Tests: `tests/test_evidence.py` (14), using the timing-chain rig to produce real events. Not yet run on a Pi.

## 2026-10-19 — the ~3 s browser round trip (#74)

From the owner's list. Measured read-only on the Pi on 2026-10-19 (rc.8):

| Request | Time | Size |
|---|---|---|
| `/api/ping` alone | about 10 ms (13 ms from the LAN, 3 ms on the Pi) | |
| `/api` | 42 ms | 11 kB |
| `/api/stability` | 1.7 s | 9 kB |
| `/api/almanac` | **15.5 s** | 25 kB |
| `/api/references` | 0.24 s | **1.1 MB** |

So the network and `/api/ping` were fine. All requests share one Python process, and the legacy dashboard at `/` asks for `/api/almanac` on every 5 s refresh: the station was computing almanacs nearly all the time, and the browser's pings (which measure the round trip) waited behind them.

- **Almanac:** the day-level parts depend only on the date, the zone and the privacy-reduced site, so they are computed once and kept for 6 hours; the sky snapshot is kept for a minute. Concurrent identical requests share one computation (`server.memo`). The privacy mode is part of the key, so a rounded or hidden answer is never served from an exact one. A failed computation is not kept.
- **References:** one server's history per response (`?history=<server>`, else the first), with `history_points` for the others. 1.1 MB became a few tens of kB. The References page asks for the server you pick.
- **History:** the tracking log is parsed at most once a minute.
- The legacy dashboard's request pattern is unchanged (it isn't restyled or reworked); the cache makes its requests cheap.
- Not changed: `/api/stability` (1.7 s at most once a minute, only while the page is open).
- Tests: `tests/test_rtt.py` (10), one more web test. Not yet measured on a Pi after the change.

## 2026-10-19 — sunrise and sunset shifts in h/m/s (#75)

From the owner's list. The Overview's day-to-day shifts of sunrise, solar noon and sunset (#31) were signed whole seconds ("−131 s"). They are now hours, minutes and seconds: "+56 s", "−2 m 11 s", "+1 h 00 m 05 s" (a clock change). Same values, same rounding to the second. The daylight-length change keeps its existing "−2m 11.3s" form. Tests: `web/src/lib/sun.test.ts`.

## 2026-10-19 — Dependabot updates (#66, #67, #68)

- Merged after green CI: `actions/setup-node` 7.0.0 → 7.1.0 (#66), `tzfpy` 2.1.0 → 2.1.1 (#67), and the web minor-and-patch group (#68: React and React DOM 19.3, Vite 8.3, Tailwind 4.3, `@vitejs/plugin-react` 6.1, Vitest 5.0.4, `lucide-react` 1.56, `oxfmt` 0.73, matching type packages). Type check, tests and build pass on `main` with them.
- Held for the owner: TypeScript 5.9 → 7.0 (#65) and `@types/node` 22 → 26 (#64); both are major updates.

## 2026-10-19 — v1.4.0-rc.9 (#76)

- Release notes in `docs/releases/v1.4.0-rc.9.md`: the fixes from the rc.8 soak run (#70, #72, #73, #74), the oscillator log (#71), Earth shadow and satellites (#61), the h/m/s shifts (#75), the dependency updates.
- `deploy/upgrade-1.4-station.md` is now the rc.8 → rc.9 checklist, with checks for the PPS counters, the new flush, the oscillator log, the evidence files and the round trip. The other checklists, README and START-HERE target rc.9.
- Not in rc.9: "sunset prominence" and "screenshot mode" (owner's list), which need the owner's description.
- The annotated tag `v1.4.0-rc.9` goes on this PR's merge commit, with a GitHub pre-release using the same notes.

## 2026-10-19 — roadmap page, README vision, public release checklist (#77)

From the owner's list.

- `roadmap/ROADMAP-GEOPHYSICS-DISTRIBUTED-SCIENCE.md` added as the owner wrote it (FUTURE, research). It also lists what no tier of this project can measure (gravity or Earth's mass from clock comparisons).
- `ROADMAP.md`: one page for outside readers. Every spec and roadmap in five phases, each with its status and the done / scheduled / planned counts from `STATUS.md` on 2026-10-19; `STATUS.md` stays authoritative.
- `README.md`: a three-line vision linking `ROADMAP.md`.
- `public-release-checklist.md`: DRAFT. History scan (secrets, coordinates, personal infrastructure, archives), current tree, release blockers, licensing, outside-reader docs, GitHub settings. Only the commit-identity check has been run (all noreply). Going public stays the owner's decision.

## 2026-10-19 — sunset as prominent as sunrise (#78)

From the owner's list ("sunset prominence"). In the legacy dashboard's Sun & daylight widget, each day showed sunrise as the large figure and sunset in the small grey line under it ("Sunrise · 6:24:12 PM sunset"). Each day now has two figures of the same size, sunrise then sunset, each labeled. A content fix in one widget, not a restyle: no CSS changed. The `/app/` Overview already gave both the same size; unchanged. Tests: `web/src/lib/legacy-dashboard.test.ts` (3).

## 2026-10-19 — screenshot mode (#79)

From the owner's list: a way to take screenshots of the station UI without showing where it is or who uses it.

- **What it hides, in `/app/`:** latitude and longitude, heights (h, H and the geoid undulation N = h − H, which is derived from them), NTP client addresses, the hostname (header and the Overview's engineering console), and the station's own address when chrony polls it.
- **How:** each hidden value is replaced by a mask of the same shape (digits → 0, letters → x: `38.9217°` → `00.0000°`), blurred. The real value is not drawn at all, because blurred digits in a known font can be recovered.
- **Display only.** Nothing changes on the station, in the API or in exports, and the station's location privacy mode is unaffected; the toggle says "display only" and its tooltip points to Location privacy. Values it does not hide: sun and moon times, sidereal time and the local zone, which narrow the position only coarsely; for those, use the station's rounded or hidden mode.
- **Toggle:** in the header; Alt+Shift+S (by key position, so it also works on macOS). Remembered per browser in `localStorage` (`gtp-screenshot-mode`); if storage is blocked it lasts for the page.
- The legacy pages are not changed (they are not restyled; noted in `dashboard/web-ui-parity.md`).
- Tests: `web/src/lib/screenshot.test.ts` (6). Checked in the desktop demo: the toggle, the shortcut, the setting surviving a reload, and no client address left in the page text.

## 2026-10-19 — v1.4.0-rc.10 (#80)

- Release notes in `docs/releases/v1.4.0-rc.10.md`: sunset as prominent as sunrise (#78), screenshot mode (#79), the roadmap page, README vision, geophysics roadmap and draft public release checklist (#77). Over rc.9 only the web UI changed (`gps_time_pi/static/dashboard.js` and `web/`).
- `deploy/upgrade-1.4-station.md` now goes to rc.10 from rc.8 or rc.9 (the Pi's last recorded release is rc.8), with a check for each UI change; rollback is rc.9. The other checklists, README, START-HERE and `ROADMAP.md` target rc.10.
- `STATUS.md`: rc.10 replaces rc.9 as the soak-run candidate; all four queued UI fixes are done.
- The annotated tag `v1.4.0-rc.10` goes on this PR's merge commit, with a GitHub pre-release using the same notes.

## 2026-10-19 — station actions in /app/ (#81)

Owner's request: port the legacy-removal blockers into `/app/`, one PR each. This is the first (parity item 6; `dashboard/legacy-removal-plan.md`).

- Administration → **Station actions**: flush logs to SD, restart gpsd, restart chrony, restart the web service, reboot. Same `POST /api/admin` and admin token as the legacy `/admin` page; the station side (fixed commands, polkit) is unchanged.
- Every action except the log flush asks first, inline, saying what it interrupts. The confirmation never claims timing is unaffected.
- Afterwards the page shows the station's own answer. A request with no answer (timeout or network) is reported as "may still have run", not as a failure. Restart and reboot say the station will be unreachable for a while; the page's polling reconnects.
- The legacy `/admin` page keeps its buttons; nothing is removed.
- Tests: `web/src/lib/admin.test.ts` (8). Checked in the desktop demo (simulated: "demo, not executed"). Not run on a Pi.

## 2026-10-19 — survey reset in /app/ (#82)

The second legacy-removal blocker (parity item 7).

- Administration → **Position survey**: the accepted-fix count and horizontal standard error, and "Reset position survey…". Same `POST /api/setting {"reset_site": true}` and admin token as the legacy `/admin` page; the station side is unchanged.
- The reset can't be undone from the UI, so one click isn't enough: the page states what would be discarded, from the station's own counts ("Discards 18,432 accepted fixes, …"; UNKNOWN when the station hasn't reported), and the operator types RESET. Escape or Cancel closes it.
- The outcome is the station's answer; no answer is reported as "may or may not have been reset", with the count to check.
- The legacy `/admin` page keeps its button; nothing is removed.
- Tests: `web/src/lib/survey.test.ts` (7). Checked in the desktop demo. Not run on a Pi.

## 2026-10-19 — TypeScript 7 (#65)

Dependabot's TypeScript 5.9 → 7.0.2, held for the owner on 2026-10-19 and merged after review. Its CI had failed on one error: TS 7 removed `baseUrl` (TS5102). The line is removed from `web/tsconfig.json`; `paths` (`@/*` → `./src/*`) now resolve relative to the file, and the `@/` imports still type-check. With main merged in: type check, 161 web tests and the build pass, and a deliberate type error is still reported. TypeScript is only the type check; Vite builds the bundle without it, so the shipped UI is unchanged.

## 2026-10-19 — Dependabot: @types/node majors ignored; #64 closed (#83)

Owner's decision after review. #64 offered `@types/node` 22 → 26, but the web toolchain runs on Node 22 (`web/.mise.toml`, `.github/workflows/web.yml`). Types for Node 26 would let code use APIs Node 22 doesn't have and still pass the type check; #64's CI was green only because nothing uses them yet. #64 is closed, and `.github/dependabot.yml` now ignores semver-major `@types/node` updates (minor and patch still come). Raise the major by hand when the toolchain's Node changes (next LTS: 24).

## 2026-10-19 — legacy removal queued after v1.4.0 (#84)

Owner's request, after the two blockers landed (#81, #82). `STATUS.md` has a new section, "Legacy removal: queue (after v1.4.0)": nine steps in the plan's order (owner decisions; almanac; sky map and object lookup; survey charts and chrony detail; kept items; the uncertainty band after GPS-003/007; front-door switch; removal; closing the findings), with one planned row each. `dashboard/legacy-removal-plan.md` marks step 2.1 done and its timing note now names the rc.10 soak. No code changed; nothing is deployed while the Pi soaks.

## 2026-10-19 — legacy parity decisions (#86)

Owner's decisions for removal step 1, recorded in `STATUS.md` → Decisions and in `dashboard/web-ui-parity.md`: keep dark and red night themes, drop light (1); replace the saved-layout editor with show/hide modules (4, 5); drop `custom.css` (18), `/zones` (19) and the 1/|ppm| holdover figure (20). Items 2 and 21 were not decided and stay as a planned "owner confirms" row. Step 5 is now the night theme and show/hide modules.

## 2026-10-19 — almanac in /app/: date navigation, day and night bars, moon details (#87)

Legacy removal step 2 (parity 8, 9, 10; `STATUS.md` → "Legacy removal: queue").

- **Date navigation** on Sun & Astronomy → Sun & Moon: ← date → and Today, limited to the station's ephemeris range (1850–2149). Every card on the tab follows the date; the three-day columns read "Day before / <date> / Day after" when it isn't today. The "Sky at" time belongs with the sky map (step 3).
- **Day bar** (midnight to midnight) and **night bar** (sunset to sunrise): night, astronomical, nautical and civil twilight and day; the moon above the horizon as a strip below; moonless astronomical darkness outlined, with its total and windows; the local-midnight tick. Laid out from `sun.bar` and `night` in `/api/almanac`; the page computes no astronomy. Colors are new `--sky-*` tokens.
- **Moon:** transit altitude and time above the horizon. Times that fall on another calendar day carry the date ("01:33 · 20 Oct"). A moonrise or moonset that doesn't happen that day reads "none this day", not UNKNOWN; UNKNOWN stays for values the station didn't send.
- Twilight card adds nautical dawn and dusk.
- `api/types.ts` now types `sun.bar` and `night` (they were `unknown`).
- Both demos (`gps_time_pi/demo.py` and `web/src/api/demo.ts`) return a synthetic day bar, night bar and moon details for the requested date, marked demo.
- Tests: `web/src/lib/almanac.test.ts` (10), `tests/test_demo_almanac.py` (5). Checked in the desktop demo (date navigation sends `?date=`). Not run on a Pi.

## 2026-10-19 — sky map and object lookup in /app/; per-request sky target (#88)

Legacy removal step 3 (parity 11, 12) and the remaining half of review finding GPS-030.

- **Sky & Objects** tab on Sun & Astronomy: the sky map (stars sized by magnitude, constellation lines, Sun, Moon and planets, the target reticle or "target below the horizon") at Now or a chosen time on the selected date, beside **Find an object** (Messier numbers, star names, planets, J2000 RA/Dec): position at that time, rise, transit and altitude, set, circumpolar or never up, dark and moonless viewing windows (the moonless one first for deep-sky objects).
- The map uses the projection of the other `/app/` sky plots: north up, east right. Constellation lines are split where they dip below the horizon rather than drawn across it. (The legacy map plots east-azimuth objects on the left but labels the right edge "E"; it is not changed here.)
- **GPS-030:** `/api/almanac` takes `target=` (the same text `/api/object` reads as `q`) and marks only that on its sky map. `/api/object` no longer writes the server-global `_LAST_TARGET`, which is removed: one browser's lookup can't change another's map. The legacy almanac page now sends its own target. The memo key already included the target.
- `api.object()` in the typed client returns `{error: 'unparsed'}` instead of throwing, so the card can show examples.
- Demo: `gps_time_pi/demo.py` places the bundled chart stars and constellation lines with a plain equatorial-to-horizontal conversion for the example site (no precession or refraction; labeled "demo positions, shapes only") and answers `/api/object` with a synthetic card; the client-side demo has a small fixed sky.
- Tests: `web/src/lib/sky.test.ts` (10), `web/src/api/object.test.ts` (3), `tests/test_location_privacy.py` (3 new: the named target is marked; a lookup doesn't mark another request's sky; no global exists), `tests/test_demo_almanac.py` (2 new). Checked in the desktop demo. Not run on a Pi.

## 2026-10-19 — survey convergence, ingest counters, chrony tracking detail in /app/ (#89)

Legacy removal step 4 (parity 14, 15, 16).

- **GNSS & Site → Survey** (fetches `/api/survey` only while the tab is open):
  - **Survey convergence:** horizontal and vertical standard error of the mean over time, log scale. Zero or missing values are gaps, never drawn as 0. The caption says what the number is: computed as if the fixes were independent; GNSS errors are correlated, so the mean's real uncertainty is larger, and below about 1 m systematic error dominates (review GPS-009's point; the legacy page still says "±").
  - **This session's fixes:** offsets from the mean in metres (no absolute position, so it shows in every privacy mode), north up and east right, rings at 1, 2 and 3 × per-fix scatter, the mean's standard-error ring.
  - **Survey ingest:** collector running, accepted and rejected this session (by reason), last rejection, total accepted.
- **Timing → Overview, chrony tracking:** frequency, residual frequency, skew, update interval, last offset and reference time, as `chronyc -n tracking` reports them. The PPS sample age and raw `sourcestats` were already on PPS Diagnostics; with this, parity item 16 is covered.
- Tests: `web/src/lib/survey.test.ts` (7 new). Checked with the client-side demo (`?source=demo`); the station demo has no survey history until fixes arrive, and says so. Not run on a Pi.

## 2026-10-19 — red night theme and show/hide modules in /app/ (#90)

Legacy removal step 5: what the owner kept from step 1 (#86).

- **Night theme (parity 1):** header "Night", Configure → Theme, or `?theme=night`. It is a red layer over the whole page, multiplied, so no green or blue light leaves the screen whatever color a chart or control uses underneath. Only the red channel is left, so in night mode the dim text and rule tokens are lifted to stay legible. Remembered per browser in `gtp-theme`, the legacy pages' key: a night choice made there carries over, and their dropped "light" reads as dark. Native browser controls (date and time pickers, scrollbars) are outside the page's control; the overlay covers what the page draws.
- **Show/hide modules (parity 4, 5):** Configure is now the modules page. It replaces the non-saving layout preview that was there. **Pages:** hide any of the nine optional pages from the sidebar; their data is still collected; Overview, Configure and Administration always show. **Overview cards:** hide any of the seven optional cards of the default layout (A); the timing chain, the clock and timing quality always show (CHG: timing source and PPS state first). A hidden page you are on falls back to the Overview. Stored per browser (`gtp-modules`), sanitized on load. "Show everything, dark theme" resets.
- Per browser rather than station-wide: one browser's choice doesn't change another's. The legacy saved-layout editor (`/configure`, `/api/dashboard*`) keeps working until the legacy pages are removed (step 8).
- `Toggle` now has `role="switch"`, `aria-checked` and an optional label.
- Tests: `web/src/lib/prefs.test.ts` (7). Checked in the desktop demo: night overlay with multiply blending, the choice surviving a reload, a hidden page leaving the sidebar, a hidden card leaving the Overview. Not run on a Pi.

## 2026-10-19 — throttle flags decoded; parity items 2 and 21 decided; Dependabot (#91, #85)

- Owner's decisions: the per-browser time-zone picker (parity 2) is dropped, since the station-wide override covers it; throttle flags (21) are kept, decoded; module visibility (#90) stays per browser.
- **Administration → Power** now shows every get_throttled condition: under-voltage, frequency capped, throttled, soft temperature limit, each now and since boot, with the raw value. Before, it listed only the active flags in two lines. Under-voltage now (red) or since boot (amber) adds a note: an unsteady supply can disturb the Pi's clock and the GNSS receiver, so check the supply and cable before reading timing results. No vcgencmd: UNKNOWN, not "all clear".
- The station side already decoded the bits; the decoding is now `system.decode_throttled()`, so the desktop demo shows a sample through the real decoder (under-voltage and throttling since boot). The client-side demo has the same sample.
- Tests: `web/src/lib/throttle.test.ts` (3), `tests/test_throttled.py` (5; there was no test for the decoding before). Checked in the desktop demo. Not run on a Pi.
- **Dependabot #85** (React and React DOM 19.3.1, Vitest 5.0.5, lucide-react 1.58, `@types/node` 22.20.5 — still on 22): merged when green, after checking it merged with the current main and passed the type check, tests and build.

## 2026-10-19 — legacy sky map: E/W labels fixed (#92)

Found while porting the sky map (#88), fixed at the owner's request. The legacy almanac page plots azimuth 90° (east) on the left (`x = cx + r·sin(az − 180°)`, the view looking up), but labeled the left edge "W" and the right "E". The two letters are swapped back; the projection is unchanged, so nothing on the map moves. The `/app/` map keeps its map-style projection (north up, east right) and its own correct labels. Test: `web/src/lib/legacy-almanac-sky.test.ts` (3) reads the projection and the labels from the template and checks they agree; it fails on the old labels.

## 2026-10-19 — chrony history semantics: named columns, error bound, labels (#93)

Next-5 item 1, review findings GPS-003 and GPS-007 (both pre-release blockers).

- **GPS-003, `/api/history`:** the tracking log is read by named column from the chrony 4.x layout (`chrony.TRACKING_COLUMNS`). A line is used only if it has exactly that shape (14 fields, a valid leap code, an integer source count) and the last banner, if any, names exactly those columns; anything else is skipped and counted (`skipped_lines`, `note`). Each point now carries `offset_s`, `offset_sd_s`, `remaining_correction_s`, `root_delay_s`, `root_dispersion_s`, `max_error_s`, `freq_ppm`, `skew_ppm`, `leap`, `n_combined`, `stratum`, `source`. The old `err_s` is gone: it took the first non-negative of columns 10, 9, 8, so a negative remaining correction turned it into the offset SD and the next fallback was a source count.
- **Legacy history page:** the band is offset ± chrony's offset SD, drawn only between updates that both report it; ± chrony's max-error bound is a dashed pair of lines. It no longer draws ±|offset| when a value is missing. The text says what each mark is.
- **GPS-007:** `quality.max_error_bound_s` = |System time| + root dispersion + ½ root delay (chronyc's bound; null unless all three are known), labeled as valid only if the reference is right. chronyc's System time is labeled "remaining correction" (still being slewed out, not the error against UTC). The "±" next to it is gone in both UIs: `/app/` shows "bound ≤ …", and the light-distance figures (Overview, Timing → Light Distance) use the bound. `fmt.system_pair` is the remaining correction alone; `fmt.error_bound` is new. The legacy dashboard's timing widget and `/legacy` say the same.
- On NTP fallback the bound includes half the root delay (often milliseconds), which root dispersion alone left out.
- Demos send the new fields; the server demo formats its strings from its numbers.
- Tests: `tests/test_tracking_history.py` (10: every column by name, a negative remaining correction, repeated banners, short and odd lines, a foreign banner, the missing log, the bound, quality from a chronyc fixture), `web/src/lib/chrony-labels.test.ts` (3: the labels in both UIs, no synthesized band). Checked in the desktop demo. Not run on a Pi.

## 2026-10-19 — offset history: offset-SD band, max-error bound, symlog axis (#94)

Legacy removal step 6 (parity 13), on top of the named tracking.log columns from #93.

- Timing → Overview, **Time Offset History** now draws chrony's offset with ± chrony's offset SD as a band, only between updates that both report it (nothing is filled in), and ± chrony's maximum-error bound as dashed lines (a bound on the error around zero, valid only if the reference is right; it can be switched off).
- The axis is symmetric-log, as on the legacy page: linear within ±1 µs, one step per decade beyond, so nanosecond wander and a millisecond excursion fit on one chart. The tooltip gives the three values for each update.
- If the server skipped tracking.log lines, its note is shown under the chart.
- The small one-hour sparkline charts are unchanged.
- Tests: `web/src/lib/offset.test.ts` (7). Checked with the client-side demo (the band is drawn; with demo values of a few ns it is thin at this scale). Not run on a Pi.

## 2026-10-19 — rc.10's first hours; v1.4.0-rc.11 (#95)

- **rc.10 on the Pi:** deployed by the owner, service start 18:10 UTC. A read-only check (HTTP GETs and read-only SSH; nothing changed) after 2 h 17 min found three real PPS outages starting with weak GNSS signal, one expected event at the service start (chrony restarted by the installer), 812 missed pulses (9.9 %) that are real absences rather than a polling artifact, a 16 ms browser round trip, and short-window stability dominated by the outages. Record: `development/raspberry-pi-deploy.md` → "First hours of v1.4.0-rc.10".
- **Release route (owner):** rc.11 from main, then v1.4.0 on the same commit after three clean days. Removal step 7 stays out.
- **What "clean" means for that tag**, fixed before the run: version 1.4.0-rc.11; at least 3 days of PPS reads since the service start; timing status GPS_PPS; no outage events since the service start, except the one at the start itself ("PPS NOT USED BY CHRONY" with healthy pulses, within 5 minutes, caused by the installer's chrony restart); missed plus unread pulses at most 1 in 10,000 reads, no late reads above 1 in 1,000, longest gap between reads under 2.5 s; `/api/ping` from the LAN median under 50 ms and maximum under 250 ms, idle and while `/api/almanac` is requested; ADEV present at 1, 10, 100 and 1000 s, ADEV at 1 s between 1 × 10⁻⁹ and 1 × 10⁻⁵, PPS selected for at least 99 % of samples, gaps at most 0.1 %. Not clean means no tag and a report to the owner.
- Release notes in `docs/releases/v1.4.0-rc.11.md`. `deploy/upgrade-1.4-station.md` goes to rc.11 from rc.8, rc.9 or rc.10, says the start-up event is expected, and has checks for the rc.11 items. The other checklists, README, START-HERE and `ROADMAP.md` target rc.11.
- The annotated tag `v1.4.0-rc.11` goes on this PR's merge commit, with a GitHub pre-release using the same notes.

## 2026-10-19 — tools/soak_check.py (#96)

The read-only check used on rc.10, committed so the rc.11 check is the same code. `python tools/soak_check.py http://<station> --expect <version> [--days 3]`: HTTP GETs of `/api`, `/api/timing-chain`, `/api/stability`, `/api/evidence` and `/api/ping` (with `/api/almanac` as load during the round-trip test); nothing on the station changes. It applies the criteria fixed in #95 and prints each with its numbers, then `CLEAN` or `NOT CLEAN`; exit 0, 1, or 2 when the station can't be read.

The decision logic is a pure function (`evaluate`), tested with fixture answers. Writing the tests found one gap: a station answer without an `events` list passed the outage criterion. Missing data now fails it (UNKNOWN is not clean). Tests: `tests/test_soak_check.py` (11; one runs `main()` against a stub HTTP server on loopback and fails on any POST).

## 2026-10-19 — deploy log: the station is a development unit (#97)

Owner's statement, recorded in `development/raspberry-pi-deploy.md` ("The current station") and `STATUS.md` → Decisions: the Pi is a development unit, and its weak C/N₀ (best about 25 dB-Hz) is an antenna and site limit. It is attributed to the owner; the station's own classifications are unchanged and still name boundaries, not causes. The soak criteria (#95) are unchanged, and a run that fails only on outages is reported rather than tagged.

## 2026-10-19 — dual-band receiver profile scoped; next-5 re-ordered (#98)

Owner's request: scope a hardware profile for a dual-band u-blox receiver, the ZED-F9T (timing) or ZED-F9P (positioning). Plan only, marked next. The plan is `hardware/zed-f9-dual-band.md`:

- the choice between the two (recommendation: F9T, if its variant outputs raw observations);
- what it will and won't improve on a Pi: the GPIO timestamp spread measured on this Pi (1.3 µs) hides nanosecond PPS, so the gain is fewer outages and better tracking;
- wiring and PPS, the one-time receiver configuration (by the operator; the station never changes it), gpsd and chrony, raw data for PPP (volume, storage off the SD card, coordinator-tier processing, privacy as for coordinates);
- the code changes in order. One finding for later: gpsd reports a dual-band receiver's satellites once per signal, which `gps.py` would count twice today.

Figures not yet checked against the u-blox data sheets are marked "to confirm".

`STATUS.md`: the next-5 list drops the two done items and takes in the profile as item 2; ten Hardware rows (six next, four planned); a decision entry. Index, hardware README, HARDWARE-PROFILES.md and ROADMAP.md link the plan.

## 2026-10-21 — legacy pages removed; / redirects to /app/ (#99)

Legacy removal steps 7–9, done together at the owner's request while rc.11 soaks (nothing deployed). v1.4.0, to be tagged on the rc.11 commit, still has the legacy pages; this is on main for the release after it.

- **Front door:** `/` and the old page paths (`/legacy`, `/almanac`, `/history`, `/admin`, `/configure`, `/zones`) answer 302 to `/app/`, with the query string kept, so bookmarks land on the web UI. `/app/` stays the UI's prefix.
- **Removed:**
  - the seven templates and six static files, `/static/*` and `/static/custom.css`, the template loader and page routes, and `zones_page()`;
  - `security.csp_for_html()`: every response now carries the one strict CSP (no `style-src 'unsafe-inline'`, no hashed inline scripts);
  - `/api`'s `state` and `fmt` (strings pre-formatted for the legacy pages) and `gps_time_pi/units.py`;
  - the saved-layout model: `/api/dashboard` (GET, POST), `/api/dashboard/reset`, `dashboard.py`, `data/dashboard.default.json`, `GTP_DASHBOARD_CONFIG`, `tools/promote_dashboard.py`, the deploy scripts' `-UseDemoLayout` / `--use-demo-layout`, and the VS Code task;
  - the web client's layout calls and types, and the sidebar's "Legacy dashboard" link.
- **Upgrades:** `install.sh` deletes the retired `templates/`, `static/`, `dashboard.py` and `dashboard.default.json` from the station (its `cp -r` would have left them), and stops changing ownership of `dashboard.json` and `custom.css`. Those files, if present, stay on the station unused.
- **Review findings closed by the removal:** GPS-016 (unescaped `innerHTML` in the legacy view), GPS-027 (unit labels in `dashboard.js`), GPS-029 (dashboard config hardening), and the legacy halves of GPS-004 (browser clock) and GPS-009 (survey "repeatability").
- **Docs:** ADR-0004 gains its outcome, `web-ui-parity.md` is closed, `legacy-removal-plan.md` records what was done, and `CLAUDE.md`, the API docs, the checklists, the guides and `web/AGENTS.md` are updated.
- **Tests:** `test_inline_styles.py` and the web tests that read the legacy JavaScript are removed. New tests check that `/` and every old path redirect with the query kept; that `/static/*`, `custom.css` and `/api/dashboard` are 404; and that every kind of response carries exactly `CSP_STRICT`. Python 575 tests and web 196 pass (an earlier count of 583 in #99's description included the removed legacy tests).
- **Rollback:** deploy v1.4.0-rc.11 (or v1.4.0) to get the legacy pages back.

## 2026-10-21 — public release preparation (#100)

Owner's request: run the public release checklist, scan all history, confirm the license and third-party notices, write CONTRIBUTING and a public README, and report before the repository is made public. It stays private.

- **History scan (read-only):**
  - Every git object (1,231; all branches, tags and remote refs, including `refs/pull/*`), all messages, and the one committed archive were scanned for secrets, coordinates and personal details. So were the PR bodies and comments and the release notes.
  - Found: no secrets, no real station coordinates, no personal email or usernames, and only noreply commit identities. **No history rewrite is needed.**
  - The demo's NTP client addresses were in the owner's LAN range: moved to RFC 5737 addresses. A personal folder name was trimmed from `development/new-machine.md`.
- **GPS-022 (bundle builder):** `tools/build_bundles.py` archives only files git tracks, so an untracked `.env`, `config.json` or token file in a checkout never ships. Station state and secrets (`config.json*`, `admin-token.sha256`, `timing-events.json`, `.env*`, `*.bsp`, `*.log`, `*.sha256`) are refused even without git. Tests plant untracked files in the checkout and check that neither archive contains them.
- **Licensing:**
  - `LICENSE` is standard MIT.
  - New `THIRD_PARTY_NOTICES.md` lists the bundled datasets, the npm packages shipped in the web UI (MIT, ISC, BSD-3; fonts under OFL-1.1), the Python packages a station installs, and the data it downloads, with the BSD notice.
  - The two OFL texts are in `third_party/licenses/`. The notices and license texts ship in the Pi bundle.
  - The sources of the three sky datasets are as `almanac-design-scope.md` states (OpenNGC, Yale BSC, d3-celestial), marked "to confirm" for the owner (GPS-023 partial).
- **GPS-026:** the five sentences in `platform-extensions.md` and `open-lightning-network.md` that claimed more timing accuracy than the platform establishes are rephrased. They now say "enables, subject to characterization" and point to `sdr/timing-model.md`.
- **GPS-025 (partial):** the runbook's "idempotent", "RAM-backed chrony history", the plugin/localStorage text and the folder name are corrected.
- **For outside readers:**
  - `README.md` rewritten: what it does, what it won't claim, status and known limitations, demo, Pi setup, hardware, docs, contributing, license.
  - `CONTRIBUTING.md` rewritten: design rules, checks, PR rules, hardware profiles, privacy when reporting bugs.
  - The bug template explains how to share diagnostics under privacy mode.
- **`public-release-checklist.md`** records the result of each item, and section 8 lists what is left for the owner: confirm the dataset sources, wait for v1.4.0, the screenshot, the flip, and the settings that only exist once the repository is public.
- Checks: Python 578 tests (575 plus the three new bundle tests) and web 196 pass; the build succeeds.
- **Process slip:** the test-count correction (`9f4acaa`) was committed and pushed directly to `main` by mistake (a stray branch switch), outside a PR. It touched only this change log; its line is moved into this entry here. `main` was not force-pushed.

## 2026-10-21 — sky data provenance verified; Messier data rebuilt from OpenNGC (#101)

Owner's request: compare the bundled Messier, star and constellation files with OpenNGC, the Yale Bright Star Catalogue and d3-celestial; confirm the sources; add the required attribution; keep each file's own license; regenerate whatever can't be confirmed.

- **Compared** (the sources downloaded for the comparison; nothing fetched at runtime):
  - `stars.json`: all 921 stars are d3-celestial's `stars.6.json` to magnitude 4.5, identical to the committed bytes. **Not** the Yale BSC, as `almanac-design-scope.md` said: its magnitudes differ (Sirius −1.44 here and in d3-celestial, −1.46 in the BSC).
  - The 99 named stars in `catalog.json`: exactly every d3-celestial star with a proper name to magnitude 2.6, brightest first.
  - `constellations.json`: all 89 figures (Serpens in two parts) identical to d3-celestial's `constellations.lines.json`.
  - The Messier list: 107 of 110 positions match OpenNGC to 0.5″, magnitudes and constellations match. M40, M45 and M102, two names and seven magnitudes (M22, M35, M62, M69, M70, M71, M107) came from elsewhere and couldn't be confirmed.
- **Licenses confirmed at the source:** OpenNGC: CC BY-SA 4.0 (Mattia Verga). d3-celestial: BSD 3-Clause, © 2015 Olaf Frohn; its star data come from the XHIP compilation of Hipparcos.
- **One license per file:** the Messier list moves from `catalog.json` to its own `messier.json` (CC BY-SA 4.0, an adapted work of OpenNGC). `catalog.json` keeps the named stars (BSD-3) and the planet list. `catalog.py` reads both.
- **Rebuilt from source:**
  - `tools/build_sky_data.py` builds all four files from pinned OpenNGC (`be3cd6c54988`) and d3-celestial (`7e720a3de062`) files. `--check` confirms the committed files match.
  - The Messier list now carries OpenNGC's values for M40 and M45, and no magnitude where OpenNGC has none (the object card leaves it out).
  - M102 follows OpenNGC, which lists it as a duplicate of M101. It takes M101's data with a note naming the NGC 5866 (Spindle Galaxy) identification. The note is shown on the object card (`/api/object` → `meta`) but is not a searchable name, so "Spindle" doesn't resolve to M101's position.
- **Attribution:**
  - `gps_time_pi/data/README.md`: source, version, license and rebuild steps per file.
  - `third_party/licenses/CC-BY-SA-4.0-OpenNGC.txt`: attribution, license and the list of changes.
  - `third_party/licenses/BSD-3-Clause-d3-celestial.txt`: d3-celestial's own LICENSE.
  - `THIRD_PARTY_NOTICES.md` updated, and the correction noted in `almanac-design-scope.md`. All of these ship in the Pi bundle. Review finding GPS-023 is closed.
- **Tests:** `tests/test_sky_data.py` (10). The builder is tested on small synthetic fixtures in the sources' formats (`tests/fixtures/sky/`): the V→B magnitude fallback, no invented magnitude, the duplicate rule, RA wrap, the magnitude limits, both Serpens parts. Also covered: the bundled files' shape, the provenance and license records, and lookups ("Spindle" finds nothing). Python 588 tests pass.

## 2026-10-21 — M102 is NGC 5866 again, marked as departing from OpenNGC (#102)

Owner's decision after #101.

- **The override:** `tools/build_sky_data.py` has one override (`OVERRIDES`). M102 takes OpenNGC's own NGC 5866 row (position, type, magnitude 9.89, Draco) instead of following OpenNGC's listing of M102 as a duplicate of M101. The name "Spindle Galaxy" and a note are the project's additions. The note reads "departs from OpenNGC: OpenNGC lists M102 as a duplicate of M101; mapped here to NGC 5866 (Spindle Galaxy), a common identification" and is shown on the object card.
- **Lookups:** "Spindle" and "Spindle Galaxy" find M102 at NGC 5866's position again. M101 is unchanged.
- **Records:** the departure is recorded with the CC BY-SA attribution (`third_party/licenses/CC-BY-SA-4.0-OpenNGC.txt`, list of changes), in `gps_time_pi/data/README.md` and in `THIRD_PARTY_NOTICES.md`.
- **Unchanged:** `catalog.json`, `stars.json` and `constellations.json` rebuild byte-identical; only `messier.json` changes.
- **Tests:** `tests/test_sky_data.py` (12). The M102 override is tested with the departure note. The generic duplicate rule keeps its own test on a synthetic duplicate row. "Spindle" finds M102 and not M101, and the departure is recorded with the license.

## 2026-10-21 — coordinator and RF tasking specs, sensor roadmap, reference node imported (#103)

Owner's request: add the five spec files from 2026-10-19 and index them in `ROADMAP.md`, if not in yet.

- **Already in:** `roadmap/ROADMAP-GEOPHYSICS-DISTRIBUTED-SCIENCE.md` (#77), identical to the owner's copy.
- **Added, copied verbatim:**
  - `specs/SPEC-COORDINATOR.md` (PLANNED): the optional coordinator tier.
  - `specs/SPEC-RF-TASKING-AND-FM-TDOA-TRIAL.md` (OPTION, planned): RF tasking between nodes and a first FM TDOA trial.
  - `roadmap/ROADMAP-SENSOR-FUSION.md` (FUTURE): optional sensors on timed nodes.
  - `hardware/HARDWARE-REFERENCE-NODE.md` (DRAFT): reference parts list in four tiers.
- **Indexed** in `ROADMAP.md` (Phase 2: the parts list; Phase 4, now "Radio and the coordinator": the coordinator and RF tasking specs; Phase 5: the sensor roadmap), `INDEX.md`, `hardware/README.md` and `STATUS.md`.
- No code changed. No items are scheduled from these documents.

## 2026-10-21 — README screenshot (#104)

Owner's request: take a README screenshot from the demo with screenshot mode on (public release checklist, section 5).

- `docs/screenshots/overview.png`: the Overview page (`/app/`) of the desktop demo, synthetic data, 1440 × 900, dark theme. Screenshot mode on, location privacy set to rounded in a throwaway demo config.
- Captured with headless Edge through the DevTools protocol from a local demo server; the capture script is not part of the repository.
- Checked by eye: the hostname is masked; the page shows no coordinates, heights or client addresses. The demo banner ("All values are synthetic") is left in.
- `README.md` shows it under the opening paragraph. Checklist section 5 item and section 8 step 3 ticked.

## 2026-10-21 — PPS evidence capture script (#105)

Owner's request: build the PPS evidence capture script (`ROADMAP-OSCILLATOR-AND-MISC.md` §4).

- **`scripts/capture-pps-evidence.sh`**: run before rebooting during a timing incident. Saves one archive, `pps-evidence-<UTC time>.tar.gz`, in `/tmp` or `--out DIR`, with: the `/dev/pps*` listing; sysfs PPS state and a few `assert` samples one second apart; a short `ppstest` per device (root only); `chronyc -n` tracking, sources, sourcestats and activity; this boot's kernel messages about PPS, GPIO, serial ports and voltage; the chrony, gpsd, boot and kernel-module lines that set up the chain; service states and restart counts; a few seconds of gpsd output.
- **Read-only:** changes no configuration, service or clock; writes only a temporary directory and the archive (mode 0600 via `umask 077`); never calls `sudo` itself. Nothing is written on a schedule.
- **Privacy:** gpsd output goes through `gps_time_pi/gpsd_redact.py` (standard library only, runs without the venv). It removes the position in every privacy mode (latitude, longitude, heights, geoid separation, magnetic variation, ECEF and relative fields), drops non-JSON lines, and in hidden mode also removes satellite azimuth/elevation. `--include-position` keeps only what the station's mode shows on screen (exact; rounded to 1 decimal and MSL altitude to 10 m; hidden: nothing). An unreadable config counts as hidden. Without `python3` the gpsd output is left out. No hostname, NTP client addresses or chrony `allow` lines are collected.
- **Docs:** `architecture/timing-chain.md` troubleshooting step 5 now names the script. The read-only button on the PPS diagnostics page is still to do (`STATUS.md`, planned).
- **Tests:** `tests/test_pps_evidence_capture.py` (17): the filter in every mode, config mode fallback, the script's text (only read-only `chronyc` reports, only `systemctl show`, no privilege escalation, writes only to its own directory), and on POSIX the whole script against a fake sysfs/dev/etc/boot tree with stub tools: archive contents, no example coordinates in any file in any mode, `--include-position`, missing `gpspipe`, bad options. Not yet run on a Pi.

## 2026-10-21 — desktop host notes in the desktop field app roadmap (#106)

Owner's request: merge the desktop host notes into `roadmap/ROADMAP-DESKTOP-FIELD-APP.md` as a "Desktop host" section; the notes file itself is not added.

- New section "Desktop host", after "Linux PPS path": the same backend and `web/` UI served on localhost from a tray app (Windows, macOS); the receiver inspector as the Receivers page; a tier and ± bound per time source (PPS, USB native, USB bridge); receiver time trusted only after leap-second data has arrived (observed: a u-blox 7 2 s off for 12 minutes); the Pi as the reference desktops learn their offsets from.
- The rest of the roadmap is unchanged. Its Goal still names Electron and its open questions still list "Python bundled vs TypeScript port"; the notes point to the bundled backend in a tray app, which the owner settles when the work is scoped.
- Docs only. The roadmap stays FUTURE, not scheduled.

## 2026-10-21 — desktop app: tray app with the Python backend, not Electron (#107)

Owner's decision: drop Electron. A tray app runs the same Python backend, packaged per OS (e.g. PyInstaller), and opens the UI in the default browser.

- `roadmap/ROADMAP-DESKTOP-FIELD-APP.md`: Goal rewritten; receiver input via the Python backend (e.g. `pyserial`) instead of Node `serialport`; "neither the tray app nor the browser UI runs elevated"; shared code settled (bundled backend, no TypeScript port); open questions now ask about the packager, installer format, tray library and localhost port, instead of bundled-vs-port.
- `decisions/ADR-0006-desktop-tray-app.md` records the decision; indexed in `INDEX.md`.
- `STATUS.md`: decision entry and one done row. Docs only; the roadmap stays FUTURE, not scheduled.

## 2026-10-21 — README reworked for first-time visitors (#108)

Owner's request: README in this order: what it is (two sentences and the screenshot), quick start (demo on a PC, install on a Pi), supported hardware (tested vs expected, with known limits), planned hardware, features now and planned, accuracy (measured figures only), docs/contributing/license. Short, linking out.

- **Supported hardware:** tested is only the Pi 4 + Uputronics MAX-M8Q on Debian 12 (one development unit, weak antenna site). The Adafruit, SparkFun and Waveshare profiles, USB receivers (NMEA only), the Pi 5 and Debian 13 are listed as expected to work, untested on hardware.
- **Accuracy:** only figures measured on that unit, from `development/raspberry-pi-deploy.md`: chrony RMS offset 244 ns (rc.8, 14 days); PPS interval 1.000 000 s ± 1.3 µs (rc.10, 600 pulses); ADEV 1.7 × 10⁻⁶ at 1 s and 2.2 × 10⁻⁸ at 100 s; +1.7 µs after one 56-minute PPS loss; 9.9 % missed pulses in a weak-signal window. The README says these are agreement with the station's own PPS reference and that accuracy against UTC has not been measured.
- **Removed from the README** (still in the linked docs): the Vision section (`ROADMAP.md`), the "won't claim" list (folded into one line under features; `docs/README.md`), and the known-limitations list (linked as open issues in `STATUS.md`). `public-release-checklist.md` updated to match.
- Docs only.

## 2026-10-21 — README: the tested Pi runs Debian 13 (#109)

Owner's correction: the tested Pi runs Debian 13 (Trixie, Python 3.13), not Debian 12.

- `README.md`: the tested row and the Pi install line say Debian 13; Debian 12 (Bookworm, Python 3.11) moves to "expected to work" (its Python runs in CI, untested on hardware).
- `deploy/fresh-pi-install.md` says which release is tested on hardware. `STATUS.md`: the Debian 13 support row (#38) no longer says "not yet run on a Pi". No status changed.
- Docs only.

## 2026-10-21 — module architecture spec; README "Where this is going" (#110)

Owner's request: add `SPEC-EXTENSIBILITY.md` to `docs/specs/`, add the vision text to `README.md` as "Where this is going", and mark the spec next.

- `specs/SPEC-EXTENSIBILITY.md` (NEXT), copied verbatim: module types, layout, manifest, interfaces, data contracts, UI cards, tooling, the first example modules and the order of work. Indexed in `ROADMAP.md` (Phase 3) and `INDEX.md`.
- `README.md`: "Where this is going" added verbatim, after Accuracy and before the docs list.
- `STATUS.md`: next-5 item 5 is the module architecture (the list had four items); new area EXT with one `next` row per step of the spec's order of work; one done row for this import.
- Debian 13: already fixed in #109; nothing else in the repository names Debian 12 as the tested release.
- Docs only.

## 2026-10-21 — observation format and tasking spec; module spec updated (#111)

Owner's request: add both new specs from 2026-10-21 to `docs/specs/`, mark them next in `STATUS.md`, link them from `ROADMAP.md`.

- `specs/SPEC-OBSERVATION-FORMAT-AND-TASKING.md` (new, copied verbatim): SigMF-based observation format with a `gpstime:` extension, converters to domain formats, capture requests across stations (scheduled and look-back), and signal-independent analyses. Its own status: NEXT for the format, PLANNED for tasking.
- `specs/SPEC-EXTENSIBILITY.md` replaced by the owner's updated version (verbatim): adds module safety, API stability, receiver profiles as modules, data licence and governance. Order of work unchanged.
- `STATUS.md`: next-5 item 5 now covers the module architecture and the observation format. New area OBSF: format (order 1) `next`; rolling buffers, capture requests, generic analyses and stages B/C `planned`, following the spec's own status line. Five new EXT rows: module safety and API stability `next` (they go with the loader), receiver modules, data licence and governance `planned`. One done row for the import.
- `ROADMAP.md` (Phase 3) and `INDEX.md` list both.
- Docs only.

## 2026-10-21 — README "Where this is going" updated (#112)

Owner's request: replace the README's "Where this is going" with the updated vision section.

- Replaced with the owner's text, which adds "Aircraft as moving references" and "Build on it".
- One sentence changed: the text linked `docs/modules/README.md` and a "module idea" issue, neither of which exists yet. It now links `specs/SPEC-EXTENSIBILITY.md`, says the guide comes with the first module work, and points to the feature request template. Restore the original wording once the guide and the label exist.
- Docs only.

## 2026-10-21 — full scope review (#113)

Owner's request: add the scope review as `docs/SCOPE-REVIEW.md` and each section 7 gap to `STATUS.md` as planned.

- `SCOPE-REVIEW.md`: the owner's review, copied verbatim. Linked from `INDEX.md` and `ROADMAP.md`.
- `STATUS.md`: nine `planned` rows (area Scope, refs Gap 1–9), one per numbered gap in §7: accuracy validation against UTC, antenna and cable delay calibration, the CPU clock experiment, stability history persistence, kiosk/mobile/PWA, acoustic thunder ranging (extends the existing Feature H row), network partners, docs website and prebuilt image, legal and safety notes. One done row for the import.
- Noted, not changed (the review is kept verbatim): it cites `SPEC-RF-REFERENCE-SIGNALS-AND-TRUST`, which is not in the repository; it lists the README vision as next (merged in #110 and #112) and the oscillator profile fit as next (`STATUS.md` has it as future); and it says the new UI is at `/` (it is served at `/app/`, `/` redirects there).
- Docs only.

## 2026-10-21 — RF reference signals spec; oscillator profile next; scope review corrections (#114)

Owner's request, four parts.

1. `specs/SPEC-RF-REFERENCE-SIGNALS-AND-TRUST.md` (OPTION, planned), copied verbatim: reference signal catalog, calibration checks, trusted node cluster. Indexed in `ROADMAP.md` (Phase 4), `INDEX.md` and the `STATUS.md` future list.
2. Checked: all seven named documents are in the repository (`specs/SPEC-COORDINATOR.md`, `roadmap/ROADMAP-SENSOR-FUSION.md`, `hardware/HARDWARE-REFERENCE-NODE.md`, `specs/SPEC-RF-TASKING-AND-FM-TDOA-TRIAL.md`, `specs/SPEC-EXTENSIBILITY.md`, `specs/SPEC-OBSERVATION-FORMAT-AND-TASKING.md`, `roadmap/ROADMAP-GEOPHYSICS-DISTRIBUTED-SCIENCE.md`). None missing.
3. Oscillator profile (`ROADMAP-OSCILLATOR-AND-MISC.md` §1) moved to next: next-5 item 6 (six items until the soak is done), five OSC rows `next`, GPS-008 `next` (the modeled projection closes it). `ROADMAP.md` row updated.
4. `SCOPE-REVIEW.md`: a dated "Corrections" section for the README vision (done), the UI location (`/app/`), the RF reference spec (now in) and the oscillator profile (now next). The review above it is unchanged.

## 2026-10-21 — SDR PPS marker spec (research); step 1 built as a module (#115)

Owner's request: add `SPEC-SDR-PPS-MARKER.md` as research, link it from `ROADMAP.md` and `SCOPE-REVIEW.md`, add `STATUS.md` rows, and build research step 1 (synthetic detector and time model) as a module.

- **Spec:** `specs/SPEC-SDR-PPS-MARKER.md`, copied verbatim. Linked from `ROADMAP.md` (Phase 4), `INDEX.md`, and a dated "Added since" section in `SCOPE-REVIEW.md`.
- **Module `modules/sdr-pps-marker/`** (the first module; layout from `SPEC-EXTENSIBILITY.md`: `module.toml`, `README.md`, package, `fixtures/`, `tests/`). Standard library only.
  - `synth.py`: synthetic IQ with noise, an optional slow carrier, a spike per PPS edge (rising and falling), clock error and drift, dropped sample blocks, missed markers; deterministic by seed.
  - `detector.py`: high-pass candidate test, threshold for one false alarm per hour, local carrier removal (complex quadratic), matched filter, log-parabolic sub-sample interpolation. Falling edges are dropped, by pairing and, when alone, by their phase against confirmed rising edges.
  - `timemodel.py`: the UTC second of each marker from a coarse host clock; interval checks (samples missing or extra, rate beyond 200 ppm); sample to UTC as an integer second plus a fraction, with a 1-sigma uncertainty that covers the marker fit only; measured sample rate, ppm error and drift; a labeled summary, state UNKNOWN until there are five scatter checks. No time is given before the first marker, after the last, or inside a flagged interval.
  - Synthetic results: marker position error 0.02-0.10 samples RMS across the scenarios (8-43 ns at 2.4 MS/s); drops flagged with the exact count; ppm measured to better than 0.3. Simulated, not measured; the limits are in the module's README.
- **Not run by the station:** no module loader exists yet (EXT order 1), and the Pi bundle doesn't include `modules/`.
- **Tests:** `tests/test_modules.py` loads every module's tests by path (their folder is also called `tests`) and checks the module layout. The module has 20 tests: fixture scenarios, time model, detector, summary labels, manifest, standard-library-only imports. CI and the documented checks now compile `modules/` (and `tests/`, which CI had left out).
- **STATUS.md:** area PPSM. Research step 1 done; research steps 2-5, the MLAT path, outputs and the kit planned (research). One done row for the `modules/` test hook.

## 2026-10-21 — sdr-pps-marker: conservative uncertainty on short runs (#116)

Owner's request: make the stated uncertainty conservative on short runs, and test that it covers the true error in 95 % of seeded runs.

- **Scatter estimate:** a quadratic in UTC seconds (rate and drift) is fitted to each block of up to 30 good consecutive markers; the pooled residuals give the marker position scatter with markers − 3 degrees of freedom per block. It replaces the neighbour-line estimate, whose small samples gave too small an uncertainty (up to about 2× in the short scenarios).
- **Stated uncertainty:** the 95 % upper confidence bound on that scatter (chi-square: exact quantiles to 10 degrees of freedom, Wilson-Hilferty above), plus 0.02 samples in quadrature for the interpolation's bias. No sample gets a time below 3 degrees of freedom. The summary reports both the estimate (`marker_position_sd_samples`, with its degrees of freedom) and the bound used (`marker_position_bound_samples`).
- **Coverage test:** 200 seeded runs of 7–10 s with random noise, clock error (±50 ppm), drift, start phase, carrier (in 30 % of runs) and a dropped block (in 20 %), at 4 kS/s. The 95 % interval (1.96 × stated sigma) must cover the true error in at least 95 % of the runs that give a time. Result: 180 runs gave a time, all 180 covered; the median error was about a third of the stated sigma (conservative, as asked). 20 runs gave no time, mostly because a drop left blocks too short to estimate the scatter.
- Synthetic only; the module's README is updated.

## 2026-10-21 — module loader and scaffolder (#117)

Owner's request: the module loader and scaffolder (SPEC-EXTENSIBILITY order of work steps 1–2), with sdr-pps-marker as the first module it loads.

- **Kit `gps_time_pi/modkit/`** (standard library only):
  - interfaces: Source, Reference, Analysis; Observation, Result, Transmitter. `INTERFACE_VERSION` is 1.0.0 (semver).
  - manifest checks: schema plus name, entry points and a compatible interface version.
  - a small JSON Schema checker.
  - `ctx`: clock in ns, timing quality (UNKNOWN when the host gives none), privacy-filtered site, config, emit, log, size-capped atomic storage.
  - the loader and host: discovery; off by default (`modules_enabled` in the station config); refusals with a reason; one thread per source; a crash is contained to its module; emitted items are checked against the schemas, and invalid ones dropped and counted.
  - CLI: `python -m gps_time_pi.modkit list|check|demo <name>`.
- **Schemas** `schemas/observation.v1.json`, `result.v1.json`, `manifest.v1.json`. The Pi bundle and `install.sh` now include `schemas/`; the bundle still doesn't include `modules/`.
- **Scaffolder** `tools/new_module.py <name> --type source|reference|analysis|ui`: manifest, README, package with a working fake, fixtures, tests that pass as created, and a `web/Card.tsx` stub.
- **First module loaded:** `modules/sdr-pps-marker` gets `interface = "1.0"`, an `[entry]` and `sdr_pps_marker/source.py`. In demo mode it emits one Observation per fixture scenario with the time model's labeled health values. Otherwise it emits nothing, since there is no SDR input until research step 2.
- **No behaviour change:** the web service doesn't import the kit (tested).
- **Not yet** (EXT Safety stays next): modules run in the host's process, so declared permissions are recorded but not enforced, and there are no CPU or memory caps. Own unprivileged process per module next.
- **Docs:** `docs/modules/README.md` (guide), `interfaces.md`, `schemas.md`; ADR-0007. The README's "Build on it" now links the guide.
- **Tests:** `tests/test_modkit.py` (manifests, interface versions, host: off by default, runs, crash containment, refusals, storage; the first module's demo; CLI; no behaviour change) and `tests/test_new_module.py` (every type's generated tests pass; a generated source runs under the loader; bad names refused).
- **STATUS.md:** EXT order 1, order 2 and API stability done; Safety next (partial).
- **Flaky test fixed:** `tests/test_evidence.py` `test_routes` failed once in CI. The demo's sample evidence id came from the current second, so it changed between the index call and the read when a second boundary fell between them. The sample outage now starts on the hour (`gps_time_pi/demo.py`).

## 2026-10-21 — observation files: writer, reader, validator; sdr-pps-marker writes pps_marker (#118)

Owner's request: the observation format's writer, reader and validator, with sdr-pps-marker outputting time_source pps_marker.

- **`gps_time_pi/obsformat.py`** (standard library only):
  - SigMF 1.2.0 with the `gpstime:` extension; datatypes `cf32_le`, `ci16_le`, `cu8`, `rf32_le`, `ri16_le`.
  - `build_meta`, `encode`/`decode`, `write` (data, then metadata with its SHA-256; each atomic), `read`, `validate`, `sample_time`, `filename`, and ISO 8601 times to the nanosecond.
  - CLI: `python -m gps_time_pi.obsformat validate|info <base>`.
- **Schema** `schemas/sigmf-gpstime.v1.json` for the global object. The validator adds:
  - the checksum and data size;
  - captures in order, each with a parseable UTC time unless marked `gpstime:time_valid: false`;
  - consecutive timed captures that agree with their sample rates;
  - `core:frequency` on RF captures;
  - annotations within the data;
  - the privacy rule: hidden carries no position; rounded carries at most 1 decimal and the altitude to 10 m.
  - Warnings: unsigned; unknown uncertainty; unknown station bound.
- **Rule enforced:** the time of every sample that claims one is computable from its capture's datetime, start and rate (`gpstime:sample_rate` on the capture when present).
- **sdr-pps-marker:**
  - `sdr_pps_marker/observation.py` writes a capture with `gpstime:time_source = pps_marker`: one capture per marker interval (UTC time and measured rate), captures without time where the model has none, the model's stated uncertainty, the SDR clock's measured error (`frequency_reference` calibrated, `source: pps_marker`), and the marker windows and dropped-sample intervals as annotations.
  - `ci16_le` output is scaled to full range, with the scale in `gpstime:calibration`.
  - Its demo observations now carry `time_source`.
- **Not yet:** signatures (they wait for station keys; the field is null and the validator warns); converters to miniSEED and WAV (next); rolling buffers and capture requests.
- **Spec note:** the spec's example names `ri16_le` for RF IQ, but in SigMF `r` means real samples; the guide says to use `ci16_le` for IQ.
- **Docs:** `docs/modules/observation-format.md`; `schemas.md`, the module guide, `INDEX.md`, `CLAUDE.md` and the module's README updated.
- **Tests:**
  - `tests/test_obsformat.py`: time strings to the ns, encoding, write/read, sample times with per-capture rates and captures without time, 13 rejection cases, data checks, warnings, CLI.
  - The module: the file is valid with `pps_marker`; file times match the time model to 2 ns and the truth within 1.96 sigma; no time across a drop; `ci16_le` round trip; no file without a time model.
- **STATUS.md:** OBSF order 1 (writer, reader, validator) done, converters as order 1b next; PPSM observation outputs done, dashboard health planned.

## 2026-10-21 — spec example: ci16_le for RF IQ (#119)

Owner's request: fix the spec example. `specs/SPEC-OBSERVATION-FORMAT-AND-TASKING.md` now gives `ci16_le` for RF IQ. In SigMF `r` means real samples, so `ri16_le` was wrong for IQ. The note about the mismatch in `docs/modules/observation-format.md` is replaced by the rule. No status changed.

## 2026-10-21 — module isolation: own process, unprivileged user, caps and permissions enforced (#120)

Owner's request: each module in its own unprivileged process, with permissions and CPU, memory and disk caps enforced; the station doesn't load modules until this lands.

- **Own process:** `gps_time_pi/modkit/runner.py`. The host (`loader.ModuleHost`) never imports module code. It starts `python -m gps_time_pi.modkit.runner` per module and talks to it in JSON lines (spec, stop, context in; ready, emit, exit, error out). The module's own prints go to stderr, kept as a short tail in its status.
- **Unprivileged:** the runner refuses to run a module as root and drops to the module user (no supplementary groups) before anything else.
- **Caps:**
  - in the module's process: address space (`[limits] memory_mib`, default 256 MiB, host maximum 512), file size (its storage cap), 64 open files, no core dumps;
  - watched by the host: CPU share over a 60 s window (`[limits] cpu_percent`, default 25 %, maximum 50 %), resident memory, output lines (1 MiB) and items (50 per second); over a cap, the module is killed with the reason;
  - storage: a size cap, plus a write-rate cap of 4 MiB per hour for `disk:` storage.
- **Permissions:** a Python audit hook (`sandbox.py`), installed before the module is imported, blocks:
  - sockets without network permission;
  - undeclared devices;
  - writes outside the module's storage;
  - new processes;
  - ctypes;
  - signals;
  - paths the host denies (config, admin token, station key).
- **Station:**
  - `system/gps-time-modules.service`: a supervisor (`gps_time_pi/modkit/supervisor.py`) as root with only CAP_SETUID/SETGID/CHOWN/DAC_READ_SEARCH, the web service's hardening plus `PrivateDevices=yes` and `IPAddressDeny=any`, and totals `MemoryMax=768M`, `CPUQuota=60%`, `TasksMax=128`.
  - `install.sh` creates the `gps-time-mod` user and installs the unit but doesn't enable it.
  - Modules get the site through `config.privacy_site`, and timing as UNKNOWN until the web service publishes it. Status and the latest items go to `/run/gps-time-modules/status.json` (RAM).
- **Platforms:** where the sandbox isn't available (Windows), the host refuses modules. `python -m gps_time_pi.modkit demo` runs them unenforced and says so (desktop demo only).
- **Not yet:** one user per module (`EXT Safety+`, planned).
- **Manifest:** optional `[limits]` (`memory_mib`, `cpu_percent`); sdr-pps-marker asks for 50 % CPU (its demo computes in bursts).
- **Tests:** `tests/test_module_isolation.py`.
  - On Linux, against real processes: one process per module; memory cap; CPU share cap; network and devices only with permission; writes only in storage; disk cap; the OS file-size limit; no processes, ctypes, signals or denied reads; output flood; crash isolation; stop; site only from the host; root without a module user refused.
  - Everywhere: the guard's rules, limits capped by the host, refusal without a sandbox, the storage write rate, the unit's hardening, installed but not enabled.
  - `test_modkit.py` and `test_new_module.py` adapted: an entry-point failure now shows when the module starts, in its own process.
- **STATUS.md:** EXT Safety done; one user per module added as planned.

## 2026-10-21 — station key pair; observation files signed and verified (#121)

Owner's request: generate a station key pair at install, sign observation files, verify in the validator.

- **`gps_time_pi/station_key.py`:**
  - Ed25519 through the `cryptography` package (new dependency, pinned 50.0.2; CI checks its aarch64 wheels, as for the others).
  - The private key is `/opt/gps-time-pi/station-key` (PKCS#8 PEM, 0600, owned by gps-time); the public key is `station-key.pub`. The station ID is `ed25519:<SHA-256 of the public key>`. `generate` never overwrites an existing key.
  - CLI: `generate | show | sign <base> | verify <base> [--trust ID]`.
- **Signing:** `obsformat.write(..., signer=station_key.load())` and `to_bytes(..., signer=...)` set `gpstime:station_id`, `gpstime:public_key` and `gpstime:signature`. The signature is over the canonical metadata JSON with the signature cleared; the metadata holds the data's SHA-256, so the samples are covered too.
- **Verification in the validator:**
  - error: any change after signing, a public key that doesn't match the station ID;
  - warning: unsigned files, a valid signature from a station not in the trusted list, or no `cryptography` package to check with. A signature that can't be checked is never reported as valid.
- **Install:** `install.sh` creates the key once, with the venv's Python, owned by gps-time. The module user can't read it, and the module guard denies the path (#120).
- **Schema:** `gpstime:public_key` added; `gpstime:signature` must start with `ed25519:` when present.
- **CI:** the plain test run has no third-party packages, so `tests/test_station_key.py` also runs in the station venv, which fails if any of it is skipped.
- **Notices:** `THIRD_PARTY_NOTICES.md` lists cryptography (Apache 2.0 or BSD 3-Clause; its wheels bundle OpenSSL) and its dependencies cffi and pycparser.
- **Not yet:** who signs on the station. Modules don't get the key; signing their files will go through the supervisor or the web service when module output is wired in. The `sign` CLI covers files by hand.
- **Tests:** `tests/test_station_key.py`: generation (0600, once), signed files verify, tampering with time, uncertainty or annotations is caught, changed samples, a swapped public key, a re-signed file against a trusted list, CLI, sign needs the checksum, no library means "not checked", installer and deny list.

## 2026-10-21 — converters: observation files to WAV and miniSEED (#122)

Owner's request: miniSEED and WAV converters.

- **`gps_time_pi/convert.py`** (standard library only). CLI: `python -m gps_time_pi.convert wav|miniseed`.
- **WAV:**
  - 16-bit PCM: mono for real samples, stereo I/Q for complex. Floats are scaled to full range; cu8 is re-centred; int16 is kept as is.
  - A SigMF sidecar names the WAV in `core:dataset`, with `core:header_bytes` 44. It keeps the original captures, so sample times are exact, and records `gpstime:derived_from` (source checksum, station, signature, method) and the scale.
  - The signature doesn't carry over; `--sign` signs the sidecar with this station's key.
  - `obsformat.read` now follows `core:dataset` (a bare file name next to the metadata) and skips the header.
- **miniSEED 2:**
  - 512-byte big-endian records: INT32 (from `ri16_le`) or FLOAT32 (from `rf32_le`). Complex data and non-integer nominal rates are refused, as are invalid network, station, location and channel codes.
  - Each record's start time comes from the observation's timing for its first sample: BTIME plus blockette 1001, to 1 µs. Blockette 100 has the measured rate. Untimed samples are left out, as a gap.
  - "Clock locked" is set for pps and pps_marker time sources; timing quality is left 0.
  - A `<out>.gpstime.json` note keeps the station ID, source checksum and signature, uncertainties and provenance.
- **Checked against ObsPy 1.5.1** in a scratch environment: codes, start times to the µs, rates, encodings, sample values, the gap as two traces, the clock flag. `tests/test_convert.py` has that check; it runs where ObsPy is installed (not in CI).
- **Schema:** `core:dataset` and `gpstime:derived_from` added.
- **Tests:** `tests/test_convert.py`: BTIME of a known time and the carry into the next second; WAV round trip with exact times, IQ stereo, cu8; refusing an invalid source; miniSEED records, times, samples, gap, blockette 100, the note; INT32; refusals; rate factors; CLI.
- **STATUS.md:** OBSF order 1b (converters) done.

## 2026-10-26 — soak run of v1.4.0-rc.11 clean; v1.4.0 (#124)

Scheduled read-only check, authorized by the owner on 2026-10-19 (tag only if clean).

- **Preconditions** (read-only SSH): version 1.4.0-rc.11; `gps-time-pi` active since 2026-10-19 21:20:16 UTC, `NRestarts=0`; no reboot.
- **`tools/soak_check.py`** (HTTP GETs only), against the criteria fixed in #95, unchanged and run once: **CLEAN** (exit 0). 6.71 days of PPS reads; GPS_PPS, stratum 1; 0 outages since the start besides the installer's chrony restart (32 s, pulses healthy); 2 missed and 0 unread pulses (3.45 × 10⁻⁶ of reads), 0 late reads, longest gap 1.07 s; `/api/ping` median 19.4 ms idle and 30.8 ms under `/api/almanac` load; ADEV 1.53 × 10⁻⁶ at 1 s to 2.08 × 10⁻¹¹ at 1 day, PPS selected for every sample. Also recorded: chrony RMS offset 202 ns, 10 of 10 independent references agree, no service warnings in the journal, never throttled. GNSS signal as weak as before (best C/N₀ 25 dB-Hz). Record: `development/raspberry-pi-deploy.md` → "Soak run of v1.4.0-rc.11".
- **Tag:** annotated `v1.4.0` on `cbd891c`, the rc.11 commit (checked with `git rev-parse v1.4.0-rc.11^{commit}`). The first two pushes of the tag got HTTP 500 from GitHub; the third went through. GitHub release (stable) with `releases/v1.4.0.md`.
- **Docs:** `releases/v1.4.0.md` (what 1.4 contains relative to v1.3.0, the soak result, known open issues, the development unit); the deployment record; `STATUS.md` (next-5 item 1 done, soak row done, a "Tag v1.4.0" row, a decision entry); INDEX, README (status line, rc.11 figures in the accuracy table), START-HERE and `ROADMAP.md`.
- Nothing on the station was changed and nothing was deployed. Work merged after #95 (#96 onwards) is on `main` only, not in v1.4.0.

## 2026-10-26 — experimental modules switch on Administration (#125)

Owner's request: an experimental modules toggle on Administration, needing the admin token, with modules staying off one by one.

- **Two settings, both off by default:** `modules_experimental` (the switch) and `modules_enabled` (each module). `loader.enabled_from_config` returns nothing unless the switch is on. Turning the switch on, or off, clears `modules_enabled`, so no module starts because of the switch.
- **API:** `GET /api/modules` (read only, no token) lists installed modules from their manifests, each one's setting, and the supervisor's state when its status file is under 60 s old (otherwise `null`, shown as UNKNOWN). `POST /api/setting` takes `{"modules_experimental": bool}` and `{"module": name, "enabled": bool}`, with the admin token. Turning a module on needs the switch (409), an installed module (404) and a valid manifest (409); turning one off always works.
- **The web service still never loads modules.** It imports only `modkit/settings.py`, which reads manifests (TOML) and the status file. The guard tests now check exactly that, instead of "no `modkit` in `server.py`".
- **Supervisor:** at each 10 s publish it checks the config file's mtime and, when the module settings changed, stops its modules and starts the new set. Read only (it never sets the file aside). `site()` follows the current privacy mode. `gps-time-modules.service` stays installed and not enabled; enabling it is still the owner's step on the station.
- **UI:** Administration → Experimental modules: the switch (with a confirmation), one row per module (maturity, permissions, status, its own toggle), the supervisor line. `lib/modules.ts` holds the logic; the demo adapter applies the same rules. `Toggle` takes `disabled`, and its thumb is pinned to the track's left edge; it sat off the track's end before.
- **`python -m gps_time_pi.modkit list`** prints the switch.
- **Tests:** `tests/test_modules_toggle.py` (gate, rules, refusals, listing without importing code, supervisor state freshness, HTTP with and without the token, demo mode, supervisor reload helpers); `web/src/lib/modules.test.ts`.
- **STATUS.md:** a done EXT "Admin" row. The totals line is recounted from the table (it was one row behind since #124).

## 2026-10-26 — second pulse and the PPS comparison tool (#126)

Owner's request: validation, with a GPIO pulse at each system-clock second and a tool comparing it with PPS from a scope or counter CSV. The first step of the accuracy validation (SCOPE-REVIEW §7 item 1).

- **`gps_time_pi/secpulse.py`** (`python -m gps_time_pi.secpulse --line N`):
  - drives a rising edge at each whole second of CLOCK_REALTIME, 100 ms wide, through the GPIO character device (uAPI v2, ctypes structures checked against `linux/gpio.h`: request 592 bytes, ioctls `0xC250B407` and `0xC010B40F`);
  - sleeps with `clock_nanosleep(TIMER_ABSTIME)` to 500 µs before the second, then spins on the clock;
  - logs per pulse the clock just before and after the write, relative to the boundary;
  - skips a second whose wake-up came more than 0.2 s late, rather than putting a pulse in the wrong place;
  - refuses the PPS input line named by the `pps-gpio` overlay in `config.txt`;
  - doesn't touch chrony, gpsd or PPS settings, and keeps a RAM ring with a summary line per minute; the per-pulse CSV only with `--log` (the guide puts it on `/dev/shm`);
  - `--rt` for SCHED_FIFO.
- **`tools/pps_compare.py`:**
  - reads counter and scope exports (delimiter, header lines, units in the header or on each value), the sign convention and cable/probe delays;
  - drops pairing errors (|x| > 0.5 s) and counts them; flags outliers (10 MADs, at least 1 µs) and leaves them out unless asked;
  - reports mean, SD, median, percentiles, range, drift, and ADEV/TDEV of x (reusing `stability.py`'s estimators);
  - says what x means for the system clock, using x = L − e: without the pulse log only a bound (calculated); with it an offset taking the edge at the middle of the write window (modeled, with the window as uncertainty);
  - never says anything about PPS against UTC, and never names a cause.
- **Guide:** `docs/validation/second-pulse.md` (what is measured, wiring, run, compare, what it can't show).
- **Not run on hardware yet.** No deploy. The tests use a manual clock, a fake line and synthetic fixtures (`tests/fixtures/validation/`, marked synthetic).
- **Tests:** `tests/test_secpulse.py`.
- **STATUS.md:** a done "Gap 1a" row; Gap 1 stays planned, with a partial note.

## 2026-10-26 — bench kit, second station, coordinator skeleton, Oct 17 write-up (#127)

Owner's request: bench kit list, second-station guide, coordinator skeleton for TrueNAS, and the Oct 17 write-up.

- **Coordinator skeleton** (`coordinator/`; ADR-0008; spec `specs/SPEC-COORDINATOR.md`):
  - `gps_time_coordinator`: signed envelopes (Ed25519 over canonical JSON; `station_id` is the station key's fingerprint, so a station signs with the key it has; `seq` increasing, so no replays);
  - `POST /v1/join`: pending until the owner approves with the CLI; `POST /v1/events`: approved stations only;
  - position fields removed before anything is stored; SQLite with a retention window; `GET /v1/health` with counts only;
  - container for TrueNAS SCALE 24.10+ (`compose.yaml`, Install via YAML): user 568:568, read-only root, no capabilities, config mounted read only;
  - `demo-client` to exercise it with a throwaway key.
  - The station is unchanged: nothing sends to it, the bundle doesn't ship it, and `gps_time_pi` never imports it. Not yet run on TrueNAS. Open: TLS, the persistent transport, the station-side sender (RAM queue, off by default), one-time-code approval, the event schema.
  - CI compiles `coordinator/` and runs `tests/test_coordinator.py` again in the venv with `cryptography`, failing if anything is skipped.
- **`docs/incidents/2026-10-17-pps-gnss-outages.md`:** the rc.8 soak run's outages, from the records made at the time. Ten events, about 71 minutes, the station's inferred classifications and their rules. chrony coasted without failover, and its first offset after the 56-minute gap was +1.68 µs. Also: what isn't known (the cause; the receiver's detail during the gaps; the make-up of rc.8's missed-pulse count) and what changed because of it (#70, #72, #73, the clean rc.11 soak).
- **`docs/deploy/second-station.md`:** shared-antenna, two-antenna and different-receiver setups and what each can and can't show; what differs from the fresh install (own hostname, token and station key; never copy `config.json`); comparing over NTP (`noselect`, the owner's step), with second pulses on a counter, and later through the coordinator.
- **`docs/validation/bench-kit.md`:** counter or scope, probes, tee, line driver for 50 Ω inputs, independent references (second receiver, GPSDO, 10 MHz into the counter), splitter for a shared antenna, what to record. Examples, no prices.
- **STATUS.md:** four done Repo rows; Feature G "Optional coordinator" stays planned, with a partial note.

## 2026-10-26 — v1.5.0-rc.1 (#128)

Owner's request: tag v1.5.0-rc.1 with notes and the deploy command.

- **`docs/releases/v1.5.0-rc.1.md`:**
  - the deploy command (Windows and Linux), and which checklist to follow with which substitution;
  - what the upgrade changes on the station: `/` → `/app/` with the legacy pages removed; the `gps-time-mod` user and `gps-time-modules.service`, installed and not enabled; the station key, made once; `cryptography` in the venv;
  - what's new since v1.4.0 (#96 to #127), what isn't verified on a Pi, the known open issues, and rollback to v1.4.0 (what stays behind and is ignored).
- **Tag:** annotated `v1.5.0-rc.1` on this PR's merge commit, and a GitHub pre-release with the notes. Nothing deployed.
- README, START-HERE, `ROADMAP.md`, INDEX: the pre-release is named next to the stable v1.4.0.
- **STATUS.md:** a done "Tag v1.5.0-rc.1" row and a planned soak-run row. The next-5 list is unchanged.

## 2026-10-26 — responsive audit: every page from 360 to 1920 px (#129)

Owner's request: check every `/app/` page at 360, 768, 1024, 1280 and 1920 px and at half-screen widths, fix overlapping and clipped fields, and add a browser test at those widths.

- **The audit** (`web/e2e/layout-audit.ts`, run by `responsive.spec.ts` in Playwright on the built UI with demo data):
  - every page, and every tab on it, at 360, 640, 683, 768, 960, 1024, 1280 and 1920 px;
  - it flags sideways scroll of the page or `main`, anything past the right edge outside a deliberate scroller, text clipped by its box, and text drawn over other text (clipped to what scrollers leave visible).
  - Before the fixes: 60 of 96 page-and-width tests failed, with about 1,440 findings (most at 360–768 px, where the 188 px sidebar and fixed grids left no room). Also, at every width the Timing outage chart's axis label lay over its tick values, and at 960 px the Timing tab row was wider than the page. After: 96 of 96 pass.
- **Fixes:**
  - **Navigation:** below 1024 px the sidebar is a drawer (☰ in the header; closes on navigation, the backdrop or Escape; hidden from tab order when closed).
  - **Header:** wraps; the stratum, reference and Unix time drop out below 768 px; below 640 px the clock and toggles take their own row.
  - **Grids:** every fixed `grid-cols-N` became container-query columns (`main` and every `Card` are size containers), 53 places.
  - **Wrapping and scrolling:** `MetricRow`, card headers and control rows wrap; tables scroll inside their card (`.table-scroll`), as do tab rows.
  - **Content:** the Overview's main reading stacks above its chart in a narrow card, and the Error Budget rows stack.
  - **Charts:** X axes drop colliding ticks; the outage chart's axis label moved clear of the ticks; fixed-size plots scale down.
  - **Labels at data positions:** sky plots and polar maps place labels where the data falls; they are marked `data-layout-ok="plot"` and checked for overflow, not overlap.
- **Page in the URL hash** (`lib/route.ts`): `#timing`, `#admin`… Reloads, bookmarks and Back keep the page; the tests open pages directly.
- **`Tabs`** have `role="tablist"`/`tab` and `aria-selected`; nav items have `aria-current`.
- **CI:** `web.yml` installs Chromium and runs `pnpm run test:e2e` after the build. New dev dependency `@playwright/test` (browser downloaded at install time only; nothing at runtime).
- **Guidelines:** Layout → "Narrow screens", and the grid patterns now use container queries.
- **Tests:** `e2e/responsive.spec.ts` (96), `e2e/navigation.spec.ts` (4), `src/lib/route.test.ts` (3).

## 2026-10-26 — design pass against Guidelines.md (#130)

Owner's request: a design pass against the guidelines (spacing, type scale, number alignment, contrast, focus states, empty and loading states); list the deviations, then fix them. The list, with counts and fixes: `dashboard/design-review-2026-10-26.md`.

- **Contrast.** The guidelines' own `--t3` and `--t4` were below WCAG AA (2.2–2.5:1 and 1.2–1.4:1), so about 1,840 text runs failed.
  - Tokens raised, keeping hue and order: `--t2` #9fa7ba, `--t3` #8188a3 (4.8:1 worst case over all surfaces); `--muted-text`, `--mod-text` and `--err-text` lifted too.
  - `--t4` is decorative only now; its 132 text uses moved to `--t3`.
  - No text is dimmed with `opacity`.
  - **The UI reads lighter**: labels, units and notes are brighter than before.
- **Tokens, not palette classes:** about 35 Tailwind palette or hex colour classes replaced (GNSS, Radio & SDR, Secondary, Timing); 4px radii → 2px; a table row hover removed.
- **Type:**
  - one page-title size (14px);
  - a display set (16, 20, 36, 44, 72px);
  - the 7px badge → 8px;
  - letter-spacing reduced to four values;
  - the station name in mono.
- **Loading is not UNKNOWN:**
  - `MetricRow` shows `…` while the station's first answers (`useStarting()`) or the card's own request (`<Card pending>`) are pending;
  - `LoadingNote` and `EmptyNote` replace ad-hoc messages;
  - "Not loaded." after a failure now says the station did not answer.
- **Focus:** the ring is documented. Fields show it on any focus, including a date field's calendar button, which showed none before.
- **Guidelines.md:** new sections for the type scale, the contrast rule, focus states, and loading/empty/unknown. Tokens, the Do-not list, and the ELI5, sidebar and sky-plot entries are updated.
- **Tests:** `e2e/design.spec.ts` (26): the design audit on every page and tab, focus on every page, loading versus a failed request.

## 2026-10-26 — linear/log toggle on time-offset and stability charts (#131)

Owner's request: a linear/log toggle on every time-offset and stability chart, remembered per browser, with ns/µs/ms axis labels.

- **Charts with the toggle** (LIN | LOG):
  - Overview Δt over the last hour (all three views share one choice);
  - Timing → time offset history;
  - Timing → holdover error at reacquisition;
  - References → offset and delay of the picked server;
  - Stability → ADEV / MDEV / TDEV.
  - Not on the NTP request-rate chart (a rate, not a time; now `RateChart`) or the oscillator and survey charts.
- **Log on signed offsets** is a symmetric-log axis (linear near zero, a decade per step beyond), so zero and both signs stay visible. The linear zone comes from the data (the decade at or below the 10th percentile of |value|); the offset history keeps its ±1 µs.
- **Log on positive values** (delay, holdover error, ADEV) is a plain log axis.
- **Stability:** τ stays logarithmic; the toggle sets the value axis.
- **Defaults** keep what each chart showed before: offset history and stability start on log, the rest on linear.
- **Axis labels:** time ticks carry their own unit (ns, µs, ms, s; `fmtTime`), so captions like "(ns)" are gone. Series are converted to seconds before drawing. ADEV and MDEV ticks are ×10⁻ⁿ.
- **Remembered** per chart in this browser (`localStorage` `gtp-chart-scales`, guarded; unknown values fall back to the default).
- **Also:**
  - The time-series X axis is a numeric time axis with five evenly spaced ticks; on the reference delay chart the old category axis let labels run together.
  - The Stability card's "Stability data not loaded." is now a loading or failed state (#130's rule).
- **Guidelines:** Charts → "Axis scale".
- **Tests:** `src/lib/timeaxis.test.ts` (9), `src/lib/prefs.test.ts` (+3), `e2e/scale.spec.ts` (7: every toggle, tick labels with units in both modes, remembered across a reload, Overview views share the choice).

## 2026-10-26 — the soak rule in the release docs; v1.5.0-rc.1 soaking (#132)

Owner's request: check the Pi's version (read-only), schedule the soak check if it runs 1.5.0-rc.1, and put the soak rule in the release docs.

- **The Pi** (read-only SSH): 1.5.0-rc.1, deployed by the owner. Service start 2026-10-26 18:16:55 UTC, `NRestarts=0`, no reboot since 2026-10-04.
- **Scheduled check:** a task fires 2026-10-29 14:30 EDT, after the 72 h are up. It checks the preconditions, runs `tools/soak_check.py --expect 1.5.0-rc.1` once, and tags v1.5.0 on `709145f` (the rc.1 commit) only if clean; otherwise it records the run in a docs PR and reports. The UI work merged after rc.1 (#129–#131) isn't in v1.5.0.
- **`docs/releases/README.md`:** the rule in one place, previously spread over #95, #97, #124 and STATUS decisions. It covers:
  - how candidates are tagged;
  - what makes a run valid (version, no restart, no reboot, 72 h from the service start; a restart starts a new run);
  - the check and its criteria table;
  - the decision (CLEAN: stable tag on the same commit; not clean: no tag, a recorded run, the owner decides);
  - what never happens (relaxing or rerunning criteria, weakening outage detection, tagging a run that failed only on outages);
  - who does what;
  - the record of soak runs.
- **Test:** `tests/test_soak_check.py` checks that the rule's criteria table lists exactly the criteria `soak_check.py` checks.
- **Also:** CLAUDE.md points to the rule. STATUS: the v1.5.0-rc.1 soak row is in progress, plus a done row for the rule.

## 2026-10-26 — oscillator profile fit (#133)

Owner's request: the oscillator profile fit (`roadmap/ROADMAP-OSCILLATOR-AND-MISC.md` §1, the "fit" row; next-5 item 6).

- **`gps_time_pi/oscprofile.py`** (pure Python, no NumPy). The model, in ppm: f = a + b·(T − T0) [+ c·(T − T0)²] [+ d·days].
  - The quadratic term is a candidate from 8 °C of range, aging from 3 days of data; the lowest-BIC candidate is kept, and all candidates' BIC are reported.
  - One pass of outlier removal (5 robust SDs), counted.
  - Standard errors for each term, residual RMS, R², bins used, the temperature range and time span covered.
  - `predict()` flags a request outside what the fit covers.
  - It needs 72 PPS bins (12 h) and 3 °C of range; until then `insufficient`, with the reason.
- **Data:** the log keeps every bin with PPS selected throughout from the whole file (up to 90 days; read at start, then each closing bin). The 7-day RAM window still feeds the charts and the straight-line slope. The fit is cached until a bin is added. Nothing new is written to the SD card.
- **`/api/oscillator` → `profile`** (modeled), with times as ISO strings and a note: a model of sensor and crystal together, valid only over the range and span it covers, not a holdover guarantee.
- **UI (Timing → Oscillator):** an "Oscillator Profile (fit)" card shows the model, each term as Δf/f ×10⁻ⁿ ± SE with ppm in brackets, and the fit quality, coverage and BIC comparison. The profile's curve is drawn on the scatter (only over the covered temperatures), and the straight line is now dashed in the `calculated` colour. The demo adapter carries a matching profile.
- **Not in this PR:** the holdover projection (GPS-008), export/import, board binding on import, the file's metadata (STATUS OSC rows, still next).
- **Tests:** `tests/test_oscprofile.py` (10: recovers known coefficients from synthetic seeded series, picks terms only when the data support them, outliers, insufficiency, prediction inside and outside, the log fitting the whole file past the RAM window, the demo payload); `web/src/lib/oscillator.test.ts` (+3).

## 2026-10-26 — reference-adsb module: 1090 and 978 MHz, with fixtures (#134)

Owner's request: the reference-adsb module (1090 and 978) with fixtures. SPEC-EXTENSIBILITY's first example reference module (order of work 4, first half).

- **`modules/reference-adsb/`** (experimental), both `reference` (`AdsbReference.list`, `predict`) and `source` (`AdsbSource`, what the supervisor runs; the host only runs source entries).
- **Input:** the `aircraft.json` that readsb or dump1090-fa (1090 MHz) and skyaware978 (978 MHz) write. Files only: no network permission, no devices.
- **Only self-reported positions:**
  - MLAT positions are refused (computed by a network);
  - so are TIS-B and ADS-R (re-broadcast by a ground station, so the signal isn't from the aircraft) and Mode S without a position.
- **Other checks:** stale (> 5 s), NACp unknown or < 8, no altitude, out of range (> 450 km or below the horizon), implausible jump (> 700 m/s). Every rejection is counted by reason.
- **Predicted delay:** slant range (WGS84 ECEF) to the privacy-filtered site, divided by c, labelled `calculated`; positions are `external`. The bound is an approximate 95 %, root-sum-square of:
  - the NACp position bound;
  - the altitude bound (GVA; ±300 m barometric);
  - movement since the fix;
  - the site's height (±100 m if only MSL is known) and, in rounded mode, its rounding.
  - The troposphere and decoder latency aren't modelled, and the note says so.
- **Privacy:** a hidden site means nothing is predicted (counts only); the module never outputs the site.
- **Emits** every 10 s: a summary (seen per band, accepted, rejected by reason, site available), and up to 10 references per band, best-bounded first. That stays inside the host's output cap.
- **Fixtures:** `fixtures/aircraft-1090.json` (15 aircraft: 6 good, 9 covering every rejection) and `aircraft-978.json` (4). Synthetic, around the US Naval Observatory example site, marked so. The demo emits the summary and 8 references.
- **Not yet:** a run against a live decoder, and measured arrival times (an SDR source and an analysis module, SPEC-RF-NODE-AND-TDOA).
- **Tests:** `modules/reference-adsb/tests/test_reference_adsb.py` (15, run with the station's through `tests/test_modules.py`). They cover parsing, the self-reported rule, the fixture counts, the delay of an aircraft overhead to 0.5 m, how the bound grows with age, barometric altitude and rounding, the hidden site, the horizon and range, jumps, the source cycle and demo, and no invented aircraft without a file.

## 2026-10-26 — Oscillator profile: holdover projection, export/import, board binding (#135)

Owner's request: the modeled holdover projection (closes GPS-008), export/import, and board binding by serial hash. This finishes next-5 item 6 (`ROADMAP-OSCILLATOR-AND-MISC.md` §1), after the fit in #133.

- **Holdover projection** (`oscprofile.holdover`, `/api/oscillator` → `holdover`): the time to ±1 µs … ±1 s if GPS and PPS went away now, three ways, all labelled `modeled`:
  - free-running (|chrony Frequency|);
  - trained, skew only (chrony's Skew), the two the review asked for;
  - the profile's: Skew + residual RMS + the largest frequency change over the last 24 h's temperature range (±5 °C before a day is logged) + aging as a ramp. Pessimistic on purpose: the temperature is assumed to jump to its worst value at once.
  - An assumed range beyond what the profile covers is flagged as extrapolated. None is validated against an outage yet, and the payload says so.
- **UI:** a "Holdover Projection" card on Timing → Overview, replacing the synthetic time-to-error preview, and on Timing → Oscillator. The Holdover Performance scatter stays planned (it needs the offset measured at PPS reacquisition).
- **Export:** `GET /api/oscillator/profile`, one JSON file. It holds the profile, the fit bins (≤ 90 days), the board's serial hash and model, the receiver's driver and firmware, the software version and the export time. No position, no raw serial.
- **Import:** `POST /api/oscillator/profile`, admin token, 2 MB cap on that route only. Shape and range checks on every row.
- **Board binding:**
  - match: the bins join the fit and the file is kept next to the log;
  - mismatch, or a hash that's missing: kept as a reference file, shown with a warning and refitted for display, never used;
  - checked again at every start, so an SD card moved to another Pi doesn't carry its profile over.
  - Written only on import.
- **Demo:** the demo board hash is now a visibly synthetic 16-hex value (`0000000000000000`), so a demo export imports as "same board"; demo imports save nothing.
- **Tests:** `tests/test_oscholdover.py` (23 tests). They cover:
  - the review's numbers at the thresholds and the profile's components, extrapolation, the parabola's vertex and aging;
  - export contents, the same-board round trip across a restart, another board, an unverifiable board, an SD card moved to another Pi, bad files, dry runs;
  - HTTP: export needs no token, import needs it, a 90-day file fits under the route cap, demo mode.
  - `web/src/lib/oscillator.test.ts`: +8.
- **Not yet:** run on a Pi; validation against real outages.

## 2026-10-26 — reference-broadcast-towers module: FM, ATSC and NOAA from an offline cache (#136)

Owner's request: reference-broadcast-towers, with FCC FM/ATSC/NOAA data cached offline, predicted delays from the surveyed site, and fixtures. This is SPEC-EXTENSIBILITY's second example reference module, finishing order of work 4.

- **`modules/reference-broadcast-towers/`** (experimental): both `reference` (`TowerReference.list`, `predict`) and `source` (`TowerSource`). No network permission, no devices.
- **Offline cache** (`gpstime-towers-cache/1`), built by the operator with `python -m reference_broadcast_towers.build_cache` from CSV exports of FCC FM Query, FCC TV Query and the NOAA Weather Radio list:
  - columns are found by header name with common aliases, never by position. The FCC's text layout key couldn't be fetched to check field positions, so no positional parser was written;
  - FM 88.1–107.9 MHz; ATSC by RF channel 2–36 (centre frequency); NOAA on its seven channels;
  - each transmitter keeps its source file, SHA-256, retrieval date and record date (the trust spec's rule);
  - rejected rows are counted by reason;
  - `--near` is rounded to 0.1° and only that point is stored.
- **Selection:** licensed only (a construction permit is left out), by service and within 150 km. Each rejection is counted.
- **Predicted delay** (`calculated`): straight-line range (WGS84 ECEF) at c × (1 + 300 × 10⁻⁶). Heights are compared in one frame (radiation centre above sea level against the site's height above sea level). The approximate 95 % bound is the RSS of:
  - position (30 m NAD83/WGS84; 100 m NAD27 or no datum);
  - height (5, 60 or 300 m);
  - refractivity (±60 × 10⁻⁶ of the range);
  - the site's rounding.
- **Line of sight** (`inferred`): from the 4/3-Earth radio horizon using HAAT. Beyond it, the delay is a lower bound.
- **Not modelled,** and said in every note: multipath, over-the-horizon paths, and the transmitter's own emission timing. A record doesn't give that, so the analysis compares differences between towers.
- **Emits** hourly (the cache is re-read only when it changes):
  - a summary: per-service counts, rejections, the cache's age and staleness (over 365 days), any read problem, and whether a site was available;
  - up to 10 references per service, best-bounded first.
  - A hidden site gives counts only. Without a cache it emits the summary with the problem, and never invents a transmitter.
- **Fixtures:** synthetic CSVs (call signs `SYN…`, invented positions around the US Naval Observatory). The FM file uses decimal columns; the TV file uses FCC-style degrees/minutes/seconds headers. There is one row per rejection reason, plus the cache built from them (marked SYNTHETIC; a test checks that it rebuilds identically). The demo emits the summary and 10 references.
- **Tests:** `modules/reference-broadcast-towers/tests/test_reference_broadcast_towers.py` (18, run through `tests/test_modules.py`). They cover:
  - build counts and rejections, sources and dates, the site never stored, DMS headers and channel frequencies, the rebuild, load problems;
  - selection, the delay and bound, how the bound grows, beyond the horizon, the hidden site, re-reading only on change;
  - the source cycle, the stale flag, hidden counts, no cache, the demo, synthetic fixtures.
- **Not yet:** a cache from real exports, and measured arrival times (`analysis-tower-delay-check` next, then an SDR source).

## 2026-10-26 — analysis-tower-delay-check module, on synthetic data (#137)

Owner's request: analysis-tower-delay-check, comparing a marker-timed capture with the predictions, on synthetic data. This is SPEC-EXTENSIBILITY's order of work 5, and the calibration check of SPEC-RF-REFERENCE-SIGNALS-AND-TRUST §3.

- **`modules/analysis-tower-delay-check/`** (research), the first `analysis` module. Entry `tower_delay_check.check:TowerDelayCheck`; results are `result/1`.
- **Input:** an observation file with `gpstime:time_source` `pps_marker` (what `sdr-pps-marker` writes). UTC per sample comes from its captures, and samples without time are never used. Marker windows are zeroed first. The predictions are `reference-broadcast-towers` observations. Each emission gives a waveform and its nominal emission time.
- **Measurement:**
  - complex cross-correlation with the waveform's template, ±20 µs around the nominal arrival;
  - a parabolic peak;
  - detected only at SNR ≥ 25 against the correlation's median, otherwise `unknown` with nothing claimed;
  - arrival from the marker timing, in integer nanoseconds. A float near 1.8 × 10¹⁸ ns resolves only 256 ns, which the first synthetic run exposed.
  - 1-sigma from the correlator (Cramér-Rao with a 0.02-sample floor), the capture's sample-time uncertainty and the prediction's bound.
- **Modes:**
  - `absolute`: emission times known; the station's clock bound is added.
  - `common_offset` (default): one unknown emission and clock offset is shared by the towers. It is estimated by a weighted median with three or more towers (one bad tower can't drag the rest), or a weighted mean with two. Then z per tower and χ² for the set.
  - Verdicts are `inferred` (agree, disagree, unknown) and never name a cause.
- **Waveform:** only a seeded pseudo-random chip code (`prn`), standing in for a real broadcast's known segment. Real ATSC or FM waveforms aren't implemented.
- **Runs from its CLI** (`python -m tower_delay_check check | synth | demo`): the module host runs only `source` entries.
- **Fix found on the way:** `/api/modules` listed an enabled module as `runs: true` even without a `source` entry, which the host never runs. Now `runs` needs a source entry, and a new `host_runs` field says whether the host runs the module at all. Administration shows "not run by the host (runs from its command line)" for such a module instead of a state. Tests: `tests/test_modules_toggle.py` (+1), `web/src/lib/modules.test.ts` (+1 assertion).
- **Synthetic results** (2.4 MS/s, clock −15 to +15 ppm):
  - every tower agrees when nothing is injected (arrival errors 6–70 ns against a 1-sigma of 89–118 ns);
  - an unknown 2.5 µs common offset is recovered within 60 ns, and the tower made 4 µs late disagrees (z ≈ 35) while the others agree;
  - a buried tower is `unknown`;
  - over 24 seeds, all 72 arrivals fell within 1.96 σ (median 0.39 σ).
- **Tests:** `modules/analysis-tower-delay-check/tests/test_tower_delay_check.py` (15, through `tests/test_modules.py`). They cover:
  - the waveform, the peak, the robust offset, marker-timed captures only, blanking and untimed samples;
  - the three scenarios against the truth, a single tower with an unknown offset, a missing prediction;
  - schema and labels, coverage over 24 seeds;
  - the CLI round trip (synth → `obsformat validate` → check), the demo, synthetic fixtures.
- **Not yet:** a real broadcast waveform, an SDR source writing marker-timed captures, a real capture.

## 2026-10-27 — A real tower cache: FCC and NOAA lists downloaded nationally, read by the FCC's key (#138)

Owner's request: build a real tower cache. Download the FCC FM/TV and NOAA exports for the rounded site, fix the header mapping, and keep the cache out of git.

- **The header mapping was the problem.** The FCC's text output (`list=4`) has no header row: it is pipe-delimited by position. So the header-name parser from #136 couldn't read a real export.
  - The FCC's key ("Text output option for AM, FM, and TV Queries", updated 2024-02-02) was readable in a browser this time. `cache.py` now holds its field names in order: 38 for FM, 39 for TV.
  - The positions we read come from those names. They were checked against real rows: a station's coordinates against its FCC detail page, and RF against virtual channels for known stations.
  - Real lines carry one more trailing identifier than the key lists; it is ignored.
  - Both query result pages state "Coordinates are NAD83".
- **NOAA:** the station listing's data file `ccl-data.js` (`var cclData = [...]`) gives call sign, position, frequency and status for about 1,000 transmitters. It has no height and no datum. `NORMAL` counts as in service.
- **`fetch.py` (new, operator tool)** downloads the three national lists.
  - **No location goes into any request.** The area is chosen offline by `build_cache.py`, from the site rounded to 0.1°.
  - **Manifest:** it writes atomically, with `fetch-manifest.json` (URL, retrieval time, size, SHA-256).
  - **Failures:** a failed or too-short reply keeps the previous file.
  - **The module itself still has no network permission.**
- **`build_cache.py --downloads DIR`** checks each file against the manifest's SHA-256. It takes each retrieval date from the manifest, and carries the SHA-256 into the cache.
- **Records:**
  - **FCC services:** full-power FM only. TV keeps DTV, DCA, LPD and DRT. DTS (synchronized transmitters, no single delay) and analog LPT are left out, as `service_not_used`.
  - **ATSC flags:** ATSC 3.0 stations are flagged `atsc3` (no ATSC 1.0 field sync), and the virtual channel is kept.
  - **Duplicates:** when a facility has a permit or application on the same frequency as its licence, the licensed record wins.
- **A real cache was built** (2026-10-27, 150 km): 334 transmitters (FM 187, ATSC 136, NOAA 11). The module accepts 273 of them as licensed or in service. Neither the area nor the cache is in the repository: `.gitignore` now ignores `towers-cache*.json`, `towers-downloads/` and `fetch-manifest.json`, except the synthetic fixture. Nothing was deployed.
- **Fixtures:** `fm-fcc-synthetic.txt`, `tv-fcc-synthetic.txt` and `nwr-synthetic.js`, synthetic rows in the real layouts.
- **Tests:** 11 new ones (formats, the key positions, services, duplicates, NOAA status, fetch with no location, the manifest, a failed download, a changed file).
- **Module:** version 0.2.0.

## 2026-10-27 — Real waveforms for the tower delay check: ATSC field sync and FM correlation (#139)

Owner's request: real waveforms, ATSC field sync and FM correlation, replacing the stand-in signal.

- **The stand-in pseudo-random code is gone.** There are two kinds now.
- **`atsc_field_sync`** follows ATSC A/53 Part 2:2011 §5.3, read from the standard (atsc.org).
  - **Known symbols:** the segment sync, PN511, the first and third PN63, and the VSB-mode symbols for trellis-coded 8-VSB: 665 symbols, 68 µs.
  - **Left out:** the middle PN63 (inverted on alternate fields), and the reserved and precode symbols.
  - **Sequences:** the code holds the standard's printed PN511 and PN63, and a test regenerates both from their polynomials and preloads.
  - **Signal model:** the 8-VSB model (pilot 1.25, root-raised cosine α = 0.1152, upper sideband) gives the complex baseband a_k·(−j)^k through a low-pass root-raised cosine of Nyquist Sr/4. It is derived from §5.4, and tests check where the pilot lands and that the band stays inside 6 MHz.
- **`fm_reference`** is FM correlation. The template is a 2 ms segment of site a's capture, shifted to 0 Hz and band-limited to ±100 kHz, then found in site b's capture.
- **Templates per capture:** each template is made for the capture's rate and tuning.
  - **Tuning:** the tuner is taken to follow the marker-measured sample clock (one crystal, as on an RTL-SDR; `lo_follows_clock`).
  - **Passband:** the SDR's filter is modelled as flat to 80 % of Nyquist with a raised-cosine edge.
  - **Captures:** one per tuning. A tower is looked for in the capture holding most of its band.
- **Peak refinement:** windowed-sinc interpolation of the complex correlation. The parabola it replaces was biased by up to 50 ns (0.12 sample) at these bandwidths, whatever the SNR. After the change, the mean error is within ±3 ns.
- **FM's correlator SNR** comes from the coherence at the peak, m·ρ²/(1 − ρ²). Program audio correlates with itself away from the peak, which made the stated sigma about 10× too large.
- **New modes:**
  - `tdoa`: two sites; the emission time cancels, the realistic case. Both clocks are trusted to their bounds.
  - `tdoa_common_offset`: site b's clock offset is estimated across the towers (the reference-transmitter method of the FM trial spec).
  - The single-site modes need emission times from elsewhere. ATSC stations aren't required to align their fields to UTC.
- **Synthetic scenarios (5):**
  - ATSC arrival errors −12 to +15 ns against a 25–32 ns sigma.
  - A hidden 2.5 µs common offset recovered within 9 ns, and a tower made 4 µs late flagged at z ≈ 64.
  - A buried tower is `unknown`.
  - FM TDOA errors −17 to +17 ns against 34–70 ns.
  - Site b's hidden 1.7 µs clock offset recovered within 7 ns, and an FM tower made 3 µs late flagged at z ≈ 33.
  - Coverage over 40 seeds: ATSC 100 % within 1.96 σ, FM 95 %.
- **Fixtures:** predictions for site a (US Naval Observatory example) and site b (Washington Monument example), from `reference-broadcast-towers`' synthetic cache. A test recomputes them.
- **numpy** is a station dependency. The tests skip without it, and a new CI step runs them in the station venv and fails if they skip.
- **CLI:** `check --window W.json` (captures per site, predictions per site, emissions, mode); `synth --out DIR`.
- **Not yet:** a real capture. An SDR source writing marker-timed captures is next.

## 2026-10-27 — sdr-pps-marker: live RTL-SDR capture through rtl_tcp, timed windows as observation files (#140)

Owner's request: an SDR source module, rtl-sdr capture with PPS markers, written as observation files, using numpy for speed.

- **Where:** in `sdr-pps-marker` (0.2.0), whose source already held research step 1. Its README said step 2 needed "a faster path, for example numpy". The detector, time model and writer are shared, not copied.
- **Why rtl_tcp:** the sandbox doesn't allow a module to start processes or load native libraries through ctypes, so neither `rtl_sdr` nor pyrtlsdr can be used.
  - **The service:** `rtl_tcp` (osmocom) runs as its own service. `system/gps-time-rtl-tcp.service` is new: 127.0.0.1 only, USB devices only, and not installed or enabled by `install.sh`.
  - **The client:** `rtltcp.py` speaks the protocol from `rtl_tcp.c`: the 12-byte header, 5-byte big-endian commands, cu8 samples.
  - **Permissions:** the manifest now says `network = true`, used for localhost only. A drop-in on `gps-time-modules.service` (`IPAddressAllow=localhost`, documented) keeps the service's `IPAddressDeny=any` for everything else. `devices = []`, because the USB device is rtl_tcp's. `storage = "ram"`.
- **`fast.py`:** a numpy version of the detector's high-pass test, noise level and threshold crossings. It feeds the same grouping, refinement and edge rules (`detector.py` refactored into `spikes_from` and `classify_edges`, unchanged in behaviour).
  - **Equivalence:** on every fixture scenario it returns exactly the reference detector's markers, whole or in blocks.
  - **Speed:** 10 s at 2.4 MS/s takes about 1 s on a desktop (not measured on a Pi).
- **`capture.py` and live mode:** per plan entry, one dwell.
  - **A new connection:** rtl_tcp then starts with an empty buffer. Otherwise samples queued while the previous dwell was processed would carry the wrong host time.
  - **Settle, record:** tune and drop 0.3 s, then 10 s of cu8 in RAM.
  - **Time:** markers, the time model, and a check that the host clock puts the markers within 0.25 s of whole seconds. Otherwise the UTC second is ambiguous and nothing is written.
  - **Windows:** each one becomes an observation file (`window_observation`): cu8 with its offset and scale, `time_source` `pps_marker`, captures and annotations cut to the window, the privacy-filtered position.
  - **Storage:** files go to RAM storage, newest `keep_files` (40) kept, never the SD card.
  - **Health:** one observation per dwell.
  - **Outages:** rtl_tcp down, or a lost connection, is reported as `UNKNOWN` with the reason and retried later.
  - **The default dwell is 10 s:** 6 s with one USB drop left too few markers per run for the scatter estimate, and the model rightly gave no time.
- **`fakesdr.py`:** a synthetic `rtl_tcp` on 127.0.0.1, with PPS edges, clock ppm and drops, used by the tests and runnable on a desktop (`python -m sdr_pps_marker.fakesdr`).
- **Kit:** `CappedStorage.names()` and `delete()`, and `modkit demo` now gives a module that asks for storage a temporary folder.
- **analysis-tower-delay-check:** reads cu8 files (centred with the calibration's offset and scale).
- **Tests:** `modules/sdr-pps-marker/tests/test_live_capture.py` (11).
  - **Covers:** fast against the reference detector, cu8, the rtl_tcp client and a non-rtl_tcp server, dwells against the truth (window times within 4 × the stated uncertainty), a USB drop annotated, no markers means no files, a host clock off by 0.45 s means no files, retention, rtl_tcp down, and the analysis reading a window.
  - **Also:** the kit test for storage names and delete.
  - **CI:** the station-venv step now fails if any module test that needs numpy is skipped.
- **Not done:** no hardware. The PPS injection isn't built, nothing ran against a real RTL-SDR, and nothing was deployed.

## 2026-10-27 — Plan for v1.5.1, the UI release after the v1.5.0 soak (#141)

Owner's request: plan v1.5.1 (UI work) to follow the v1.5.0 soak.

- **`docs/releases/v1.5.1-plan.md`** (new).
- **Why:** the v1.5.0 tag goes on the soaked rc.1 commit (`709145f`), so the UI merged after it (#129 responsive layout, #130 design pass, #131 chart scale toggle, the holdover panel of #135, the modules label of #137) needs its own release.
- **The station's changes since rc.1:** the oscillator fit, holdover and profile export/import, and small module-kit changes. Modules and the rtl_tcp unit stay in the repository, not on the station. The installer, requirements and service are unchanged.
- **Gates:** a clean v1.5.0 check comes first. If it isn't clean, the owner decides, and a new candidate would carry this work.
- **Before rc.1** (proposed, one PR each):
  1. module output in the web UI: the supervisor already publishes the latest items; `/api/modules` and Administration would show them;
  2. the flaky PPS evidence test: timestamps matched the example position's digits;
  3. a desktop UI review.
- **Then:** the notes PR, the tag, the owner's deploy, and a 72 h soak with the #95 criteria.
- **Also in the plan:** the checks on the Pi after the deploy, and the candidates after v1.5.1 (PPS history views, tower check results, NTS/PTP state, the Updates page).
- **STATUS:** a v1.5.1 section and six rows (one done: this plan).
- **Not touched:** the station, the v1.5.0 run and its scheduled check.

## 2026-10-27 — Module output in the web UI (#142)

Owner's request: build the v1.5.1 items now on main (no tag until the v1.5.0 soak passes); item 1, module output in the web UI.

- **`/api/modules` gains `latest` per module:** the newest item the module emitted, from the status file the supervisor already writes in RAM (`/run/gps-time-modules/status.json`). Nothing new runs; the web service still never loads modules.
  - **Fields:** `kind`, `time_ns`, `age_s`, `items_kept`, up to 40 labeled values (notes cut to 300 characters), and `left_out`.
  - **Left out:** a value without one of the six provenance labels (never relabeled), one that isn't a single value, and any position-like value (`lat`, `lon`, `alt_m`, `position` and the like), whatever a module emits.
  - **Freshness:** `null` while the supervisor isn't reporting, as `state` already was.
- **Administration → Experimental modules** shows it under each module as labeled values with their age.
  - **Formatting:** seconds in ns/µs/ms; very small or large numbers as ×10ⁿ; a value the module didn't establish shows UNKNOWN.
- **Demo:** with the module turned on, the demo shows a canned sample of what the module's own synthetic demo emits, and says so ("a canned sample of the module's synthetic demo, not a running supervisor"). The demo's module row now matches its 0.2.0 manifest.
- **STATUS:** the v1.5.0 known issue "module output isn't shown in the web UI yet" is closed, and so is the PPSM "Health" row (on Administration, not the Overview).
- **Tests:**
  - `tests/test_modules_toggle.py` (+3): the newest item with its labels, no position and no unlabeled value, bounds and staleness.
  - `web/src/lib/modules.test.ts` (+2, and the demo test).
  - `web/e2e/modules.spec.ts` (new): the card with output at 360, 768 and 1280 px, layout and design audits, and off again.

## 2026-10-27 — A flaky test: wall-clock times matched as positions (#143)

Owner's request: the v1.5.1 items on main; item 2, the flaky-test fix.

- **The failure:** `tests/test_pps_evidence_capture.py` checks that no output of the evidence script carries the example position's digits (`38.92`, `77.06`, …). The script's output also has wall-clock times, and one CI run of #140 failed on `…02:11:38.925…`.
- **The fix:** times (`2026-10-27T02:11:38.92…Z`, `02:11:38.92…`) are replaced with `<time>` before the check. A position is never written as a time of day, so a real leak still fails.
- **A new test** shows that both hold: a time passes, while a time next to `lat 38.9217` or `-77.0669` still fails.
- **Scope:** tests only. Nothing in the script or the redaction changed.

## 2026-10-27 — Desktop UI review of the v1.5.1 candidate (#144)

Owner's request: the v1.5.1 items on main; item 3, the desktop UI review. Record: `docs/dashboard/ui-review-2026-10-27.md`.

- **How:** the built UI served by the Python demo station, which uses the station's own demo API, not the client-side adapter the browser tests use. The new opt-in check `web/e2e-station/` (`corepack pnpm run test:station`; `GTP_STATION_URL`) covers every page and tab: layout at 360–1920 px, design at 1280 px, no console errors, screenshot mode never showing the demo position, and the night-theme layout. 72/72 pass. Full-height screenshots were then looked at by eye.
- **Fixed:**
  1. **Timing's PPS state bar:** the hour labels were drawn stretched (SVG text in a `preserveAspectRatio="none"` graphic); they are now HTML.
  2. **Holdover performance:** a category x-axis (outages in list order, 2 of 5 points at 360 px) is now a numeric log duration axis, with dot size restored.
  3. **Holdover projection:** values no longer break across lines.
  4. **Oscillator time charts:** date ticks repeated; now one per local midnight (`dayTicks`).
  5. **Administration:** a sentence linking the removed legacy `/admin` page is gone.
  6. **Night tooltip and Configure:** "shared with the legacy pages" removed.
- **Not changed (for the owner):**
  - night-theme legibility of green and cyan values, left alone on purpose by the 2026-10-26 design review;
  - the station server's listen queue of 5: requests were refused with several browsers at once, none with one (GPS-018).
- **Tests:** `dayTicks` and `fmtDurationTick` unit tests; the browser suites pass.

## 2026-10-27 — Optional SDR stack in the installer: `GTP_SDR=1` (#145)

Owner's request (v1.6.0, item 1): an optional installer flag for rtl-sdr, the rtl_tcp unit, readsb (1090 MHz) and dump978 (978 MHz), all localhost only. Guide: `docs/deploy/sdr-stack.md`.

- **What it installs** (`scripts/sdr-stack.sh`, run by `install.sh`; nothing unless `GTP_SDR` is set):
  - `rtl-sdr` with `gps-time-rtl-tcp.service` (127.0.0.1:1234);
  - Debian's `readsb` as `gps-time-readsb.service`, with no network listeners at all and `aircraft.json` in `/run/readsb`;
  - `dump978-fa` and `skyaware978`, built as `nobody` from FlightAware's v11.1 at a checked commit, on 127.0.0.1:30978/30979, with `aircraft.json` in `/run/skyaware978`;
  - a drop-in that lets `gps-time-modules.service` reach 127.0.0.1 only.
- **Dongles by serial:** one RTL-SDR per role, by USB serial (`GTP_SDR_PPS_SERIAL`, `GTP_SDR_1090_SERIAL`, `GTP_SDR_978_SERIAL`, kept in `/etc/default/gps-time-sdr`). A role with no serial is installed, not enabled. Bad or shared serials change nothing.
- **readsb's own unit** is masked before the package is installed, so it can't take the PPS dongle. An instance the owner already runs is left alone.
- **Never touched:** gpsd, chrony, PPS and `/boot`. No decoder is given a position.
- **Failures:** a failure warns and never stops the install. `GTP_SDR=0` removes the units.
- **Tests:** `tests/test_sdr_stack.py`: units fenced to the loopback or no network, listeners on 127.0.0.1, no position, serials, the pinned commit; the script under stub commands (POSIX only).
- **Not verified:** the installs, the build and the units have not run on a Pi.

## 2026-10-27 — The SDR modules from Administration (#146)

Owner's request (v1.6.0, item 2): enable sdr-pps-marker and reference-adsb from Administration.

- **What was missing on a station:**
  - `install.sh` never copied `modules/` to `/opt/gps-time-pi/modules`, so Administration listed none;
  - the supervisor service was never enabled;
  - `sdr-pps-marker` needs settings (`fs_nominal`, an `rtl_tcp` plan) that could only be set by editing `config.json`.
- **Now:**
  - **The modules are installed:** `install.sh` copies the modules (read only, all off).
  - **The supervisor is on with the SDR stack:** `GTP_SDR=1` enables `gps-time-modules.service`, which runs nothing while the switch is off.
  - **Settings from Administration:** each module's settings can be set there (`POST /api/setting {"module", "config"}`). They are checked against the manifest's `[config]` keys and types, at most 8 KiB, with no position-like key at any depth. A change never turns a module on.
- **Readiness on the card:**
  - `sdr-pps-marker`: rtl_tcp running and the live plan set; the injected PPS is UNKNOWN, since it can't be observed from the web service;
  - `reference-adsb`: each feed fresh.
- **New card: SDR receivers.** `/api/sdr` (`gps_time_pi/sdr.py`), read only, shows:
  - unit states, CPU and memory from the cgroups, and restarts;
  - RTL-SDR dongles from sysfs, with serial, role, speed and whether the DVB-T driver holds one;
  - the decoders' `aircraft.json` age and aircraft count, never a position.
- **Tests:**
  - `tests/test_sdr_status.py` (new): temp sysfs and cgroup tree, a fake `systemctl`;
  - `tests/test_modules_toggle.py` (+5): settings rules, listing, HTTP with the token;
  - `web/src/lib/sdr.test.ts` (new) and `modules.test.ts` (+5);
  - `web/e2e/modules.spec.ts` (+2): readiness, settings refused and saved, and the receivers card at 360 and 1280 px, with the layout and design audits.
- **Not verified:** not run on a Pi. The cgroup paths assume cgroup v2 (Debian 12 and 13).

## 2026-10-27 — SDR load in the soak record (#147)

Owner's request (v1.6.0, item 3): add the SDR load to the soak record, with CPU, USB, temperature and PPS jitter.

- **What the tool adds:** `tools/soak_check.py` prints, after the criteria, `[REC]` lines for the record (`docs/releases/README.md`, "The record"):
  - **sdr:** each SDR unit's CPU now, from two `/api/sdr` samples 30 s apart (`--window`), CPU since its start, memory and restarts;
  - **cpu:** the load averages;
  - **usb:** the RTL-SDRs with serial, role and speed, and the throttled flags;
  - **temperature:** the SoC temperature;
  - **pps jitter:** chrony's PPS standard deviation, the RMS offset, and ADEV and TDEV at 1 s.
- **The criteria are unchanged.** The record changes no exit status. Its reads go through their own error handling, so an unreadable `/api/sdr` or `/api/system` is recorded as UNKNOWN and never fails or stops the check.
- **The v1.5.0 check:** v1.5.0-rc.1 has no `/api/sdr`, so its record says UNKNOWN for the SDR line and gives the other figures. Read-only against the station today:

  | Record | Value |
  |---|---|
  | load averages | 0.19 / 0.27 / 0.24 |
  | throttled flags | 0x0 |
  | SoC temperature | 54.0 °C |
  | chrony PPS std dev | 342 ns |
  | RMS offset | 209 ns |
  | ADEV(1 s) | 1.57 × 10⁻⁶ |
  | TDEV(1 s) | 908 ns |
- **Tests:** `tests/test_soak_check.py` (+6):
  - rates from two samples;
  - UNKNOWN without SDR status, never zero;
  - no rate across a restart;
  - the record never changes CLEAN;
  - its reads never fail the check;
  - `main()` against the stub with `/api/sdr`.

## 2026-10-27 — Learned sky-obstruction map and the capability record (#148)

Owner's request: build the learned sky-obstruction map (addendum §10–11): bin C/N₀ by azimuth and elevation over days, save a capped grid to the SD card, show a polar heatmap on GNSS & Site, and mark satellite loss in blocked sectors as expected. Add an opt-in sky-quality summary to the capability record and the export. Off in hidden mode. For v1.6.0-rc.1.

- **Collection** (`gps_time_pi/skymap.py`):
  - the GNSS collector passes each fresh SKY report to the map (`gps.add_sky_listener`); HTTP traffic never feeds it;
  - once a minute each listed satellite is counted in its 10° × 5° cell: listed, tracked, used, and the sum and sum of squares of C/N₀ (observed).
- **Storage:**
  - `sky-obstruction.json` next to `config.json`, written atomically once an hour and on a clean stop, only when changed;
  - a fixed grid of 648 cells; a cell's counters are halved at 20 000 samples, and at most 400 day numbers are kept (about 25 KB when full);
  - no position and no time of day. An unreadable file is set aside.
- **Inference** (`inferred`):
  - each cell against the median of its elevation band (±5°): blocked at 8 dB below or tracked < 50 %, attenuated at 4 dB or < 80 %;
  - the tracked share only when the receiver lists untracked satellites;
  - eight sectors ("Expected obstruction below ~N°", "Intermittent attenuation a–b°", "Mostly clear", "Not enough data"); learned after 2 days.
- **Losses (§11):**
  - each lost satellite is EXPECTED, NOT EXPLAINED, SET or UNKNOWN from its last direction;
  - a sky-wide C/N₀ drop above 30° in three or more quadrants is flagged with "the evidence does not establish a cause";
  - kept in RAM, never a cause.
- **Privacy:** in hidden mode nothing is collected, served or exported; the file on the card is kept.
- **Capability record** (`gps_time_pi/capability.py`, `GET /api/capability`):
  - station ID, version, timing state, receiver and SDR roles;
  - a location only in rounded mode, at 0.1°; none in exact or hidden;
  - the sky-quality summary (sectors only) when `sky_quality_share` is on (`POST /api/setting`, admin token, default off), never in hidden mode. The same summary ends `GET /api/diagnostics`;
  - not sent anywhere yet.
- **UI:**
  - GNSS & Site → Sky Obstruction replaces the preview with the station's map: a polar heatmap shaded by class or by mean C/N₀, the sectors and the satellite-loss table;
  - Administration → Capability record has the opt-in switch.
- **Tests:**
  - `tests/test_skymap.py` (21): cells, the one-a-minute sampling, hidden mode, classes, sectors, a uniformly weak sky, the cell cap, each loss class, the sky-wide drop, the hourly file and its reload, a set-aside file, the capability record's location and opt-in, the routes;
  - `web/src/lib/skymap.test.ts` (5);
  - `web/e2e/skymap.spec.ts` (7).
- **Also fixed:** GNSS & Site → Survey's convergence chart had four full date-time labels, which collided at 360 px depending on the time of day (the layout audit failed on `main` too). It now has three: start, middle and end.
- **Not yet run on a Pi.** The thresholds come from synthetic tests and the demo.

## 2026-10-29 — v1.5.0-rc.1 soak run: not clean, v1.5.0 not tagged (#149)

Docs only. The scheduled read-only check of the Pi on 2026-10-29 at 18:30 UTC, 3.01 days after the rc.1 service start; nothing on the station was changed. Preconditions held (version 1.5.0-rc.1, no service restart, no reboot). `tools/soak_check.py` was run once with the unchanged criteria (#95).

- **NOT CLEAN** (exit 1) on outages (four PPS_OUTAGE events, 46 s to 6,814 s, 8,596 s in all; no installer restart) and pulses (8,906 missed, 3.4 % of reads; 0 unread, 0 late reads). Version, runtime, timing, round trip and stability were OK.
- The station's classifications (`inferred`, boundaries, not causes): three PPS PATH ANOMALY, one GNSS RECEPTION ANOMALY (the longest). chrony kept GPS as its reference through all four, with no fallback source; its largest remaining correction was 71 ns.
- **Not done, by the owner's rule:** no v1.5.0 tag, no release notes for it, no v1.6.0-rc.1 (the branch `docs/release-v1.6.0-rc.1` is left as it is). A run that fails only on outages is reported to the owner, who decides about v1.5.0 and v1.6.0-rc.1. Outage detection is not weakened.
- Recorded in `development/raspberry-pi-deploy.md` → "Soak run of v1.5.0-rc.1" (every criterion, the `[REC]` lines, the events, the state at the check), the Record table in `releases/README.md`, and the soak row in `STATUS.md`.

## 2026-11-04 — Optional web SDR: OpenWebRX+ behind a password gate, with a usage log (#152)

Owner request: an optional `GTP_WEBSDR=1` that installs OpenWebRX+ on the station, LAN-only and password-protected, linked from the Radio page; it gets the dongle to itself with readsb stopped while it runs; CPU, temperature and PPS jitter logged while it's in use. Decision: `decisions/ADR-0009-web-sdr-on-station.md`; guide: `deploy/websdr.md`.

- **Installer** (`scripts/websdr.sh`, run by `install.sh`; unset changes nothing, `0` removes the units):
  - the OpenWebRX+ apt repository for bookworm or trixie, kept only if the signing key's fingerprint is `82B2AC14962B3C75FAC97206B64EADD5CB69C981`; taken out again if the install fails;
  - `openwebrx` with its own unit masked; an owner's enabled `openwebrx.service` is left alone;
  - a `conf.d` file: OpenWebRX+ on 127.0.0.1:8074; its RTL-SDR devices pinned to `GTP_WEBSDR_SERIAL` (default: the 1090 MHz serial). The PPS and 978 MHz serials are refused;
  - settings kept in `/etc/default/gps-time-websdr` (serial, port 8073, session limit 4 h); a password file that keeps the gate closed until the owner sets one.
- **Units:** `gps-time-websdr.service` (loopback only, reaches no outside host, 2 cores and 512 MiB at most, no restart, `Conflicts=` readsb, `ExecStopPost=` `websdr-handoff` starts readsb again, `RuntimeMaxSec=` from a drop-in) and `gps-time-websdr-gate.service` (bound to it; private ranges only; the password as a systemd credential). Neither has an `[Install]` section.
- **Gate** (`gps_time_pi/websdr_gate.py`, stdlib): HTTP Basic on each new connection, PBKDF2-SHA256 hash, 503 with no password, backoff after 5 failures from an address, no password in the log, Authorization stripped before OpenWebRX+, then a byte pipe (WebSockets work). `python -m gps_time_pi.websdr_gate passwd` sets the password.
- **Start and stop:** admin actions `websdr_start` and `websdr_stop` (`system.ACTIONS`); the polkit rule allows `start` and `stop` of `gps-time-websdr.service` and nothing else new.
- **Usage log** (`gps_time_pi/websdr.py`, `GET /api/websdr`): the timing chain's PPS poller hands each new kernel PPS timestamp to it (`pps_listeners`); every 10 s the system CPU, the two units' CPU and the SoC temperature. Minute bins in RAM, the last 10 minutes always kept as the before, a session's minutes while the unit runs (cgroup present), one summary line per session in `websdr-sessions.jsonl` (100 kept). Jitter is `calculated`, |phase| and pulses `observed`. The timestamps' float resolution (about 0.24 µs) is stated; it limits `/api/stability` the same way.
- **UI:** Radio & SDR → Devices → Web SDR: state, serial, port, session limit, Start (asks first), Stop, the link while it runs, and before/during figures for this or the last session (`web/src/components/websdr.tsx`, `web/src/lib/websdr.ts`). The demo adapter and `GTP_DEMO=1` have synthetic answers.
- **Tests:** `tests/test_websdr.py` (gate credentials, backoff, an end-to-end proxy on the loopback; the usage log with a manual clock: before and during, partial sessions, missed pulses, the file cap; units; the script under stub commands: defaults, refusals, an existing OpenWebRX+ settings file, apt failure, an owner's OpenWebRX, removal); `tests/test_admin_auth.py` (the two actions, the polkit rule); `web/src/lib/websdr.test.ts` (5).
- **Not verified:** nothing has run on a Pi: the package on trixie arm64, OpenWebRX+ under this hardening, the serial pin, the readsb handoff, the session limit, the load.

## 2026-11-04 — PPS timestamps in integer nanoseconds; the soak outages against the RTL-SDR's USB connect (#153)

Owner request, after #152: check whether the 2026-10-29 soak outages line up with the RTL-SDR's USB connect time (read-only on the Pi), and fix PPS timestamps to integer nanoseconds end to end.

- **The check** (read-only SSH; `development/raspberry-pi-deploy.md` → "Soak run of v1.5.0-rc.1" → follow-up): the persistent journal covers the whole run. The dongle's only USB connect this boot is 2026-11-04 14:56:05 UTC, six days after the check; there was no USB event during the run. So the outages can't line up with plugging it in. Their cause is still not established. The only kernel lines in the run are Ethernet link flaps on 2026-10-29 around 08:11 UTC, away from every outage.
- **Why the fix:** `pps.read_assert` turned `<sec>.<nsec>` into a float of seconds. Near today's epoch a float steps in about 238 ns, so the phases fed to `/api/stability` and the web SDR usage log were quantized to that. A ±37 ns phase read as 0 (ADEV 0 instead of 1.05 × 10⁻⁷). On this station's real figures (ADEV(1 s) about 1.5 × 10⁻⁶, chrony's PPS std dev about 370 ns) the effect was a small added quantization noise, not a wrong order of magnitude.
- **Now:**
  - `read_assert` returns integer ns: `sec * 10⁹ + nsec`, with a short fraction right-padded;
  - `PPSMonitor` keeps integer-ns timestamps and intervals; missed pulses are counted in integer arithmetic; seconds are made only from differences (interval, rate, phase), plus the display time and the coarse age;
  - `pps.phase_ns` gives the nearest second and the signed phase in ns; `stability.Recorder.add` and `websdr.UsageLog.add_pps` take integer ns and refuse a float (`pps.require_ns`);
  - the demo's PPS reader gives integer ns.
- **No API change:** every payload keeps its shape and units (seconds where it had seconds).
- **Tests:** existing PPS, stability and usage-log tests feed integer ns. New: an exact ±37 ns phase series and its ADEV, `phase_ns` at the rounding edges, a float refused, an interval of 1 s + 30 ns kept exactly, `read_assert` exact. The usage-log jitter test is now exact to 0.2 ns, not 250 ns.

## 2026-11-04 — v1.6.0-rc.1: release notes; v1.5.0 skipped (#154)

Owner, 2026-11-04: "Tag v1.6.0-rc.1 from main with notes recording the soak finding (v1.5.0 skipped, site-limited)". This replaces the rule of 2026-10-27 (tag v1.6.0-rc.1 once v1.5.0 is tagged).

- **`releases/v1.6.0-rc.1.md`:** from the draft on `docs/release-v1.6.0-rc.1` (#148 era), brought up to date.
  - The soak finding: not clean (#149); the owner's decision to skip v1.5.0, with the outages taken as this unit's antenna and site limit (the owner's assessment; the station names no cause); the USB check (#153) and the outage-timing comparison.
  - #149 to #153 added: the web SDR (`GTP_WEBSDR=1`, opt-in, not for the soak run) and integer-ns PPS timestamps.
  - "New since v1.5.0-rc.1"; rollback to v1.5.0-rc.1 or v1.4.0.
- **Soak record** (`development/raspberry-pi-deploy.md` → "Soak run of v1.5.0-rc.1"): the outage-timing follow-up, read-only:
  - 9 real outages on 5 evenings since 2026-10-04;
  - the three measured drops of the receiver's solution to 0 satellites at GMST 21:28–21:29, UTC spread over 31 minutes;
  - time of day nearly as close; SoC temperature a poor fit; C/N₀ by sector not recorded;
  - stated as a lead from three points, with no cause.
- **Version lines:** README, START-HERE, ROADMAP, INDEX; the release record in `releases/README.md`; STATUS rows for the tag and the next soak run. `v1.5.1-plan.md` marked superseded.
- **Owner, 2026-11-04: the formal soak waits for the antenna move.** The first run of rc.1 is for sector data and web SDR testing (`GTP_WEBSDR=1` allowed) and isn't a soak run. STATUS and the notes say so.
- **Unchanged:** the soak criteria and outage detection. v1.6.0 needs a clean 72-hour run of v1.6.0-rc.1, after the antenna move.
- **Tag:** `v1.6.0-rc.1` on this PR's merge commit, with a GitHub pre-release using these notes.

## 2026-11-04 — The Pi bundle ships modules/; an install-from-bundle test; v1.6.0-rc.2 (#155)

The owner's deploy of v1.6.0-rc.1 failed: `install.sh` stopped at `cp -r modules` ("cannot stat"), because the bundle had no `modules/`.

- **Cause:** #146 made `install.sh` install the bundled modules, all off. But `tools/build_bundles.py`'s `PI_TOP` didn't list `modules`, and ADR-0007 still said the bundle ships none. Two tests (`test_modkit`, `test_modules`) asserted that `"modules"` wasn't in `build_bundles.py`, so CI passed.
- **Fix:** `modules` is in `PI_TOP`, the two tests check the opposite, and ADR-0007 is amended.
- **New: `tests/test_bundle_install.py`.**
  - It builds the bundle (`build_pi_tar`, with a stand-in built UI), extracts it, and runs the bundle's own `install.sh` with bash.
  - The script's destinations (`/etc/…`, `/opt/gps-time-pi`) point into a temporary root, and system commands are stubs. The venv's pip is skipped; everything else runs for real.
  - It checks that the install finishes, that every bundled module, the code, UI, rollback file and units are installed, that `chrony.conf` got only the installer's edits, and that the service restart comes after chrony's.
  - Any other absolute path in `install.sh` fails the test until it's listed, so the test never writes outside its root.
  - With `modules` removed from `PI_TOP` it fails with the deploy's own error.
  - It runs on POSIX in CI and skips on Windows. `install.sh` is unchanged.
- **The station after the failed install** (read-only, `development/raspberry-pi-deploy.md`): timing recovered within about a minute of each chrony restart, with no clock step, but up to about 6 ms of drift while on a network source. The web service is still the v1.5.0-rc.1 process, over rc.1's files. The steps after `cp -r modules` didn't run.
- **Release:** `releases/v1.6.0-rc.2.md`. `v1.6.0-rc.1.md` is marked can't-be-installed. Version lines updated. The tag `v1.6.0-rc.2` goes on this PR's merge commit, with a GitHub pre-release.

## 2026-11-04 — The deploy scripts pass install.sh's GTP_* flags (#156)

Owner's rc.3 list, first item. Before, `deploy-to-pi.ps1` (and `.sh`) always ran `sudo bash install.sh`, so `GTP_SDR=1` or `GTP_WEBSDR=1` meant a second run by hand on the Pi.

- **Both scripts** read an allowlist of `install.sh`'s flags from the local environment and run `sudo env <name>='<value>' ... bash install.sh`. With none set, the command is unchanged.
- **The allowlist** is exactly the `GTP_*` names that `install.sh`, `sdr-stack.sh`, `websdr.sh` and the two chrony scripts read, minus test hooks and the client-list helper's own settings. A test fails if either script's list differs.
- **Values are checked** before anything is built or uploaded: letters, digits, space and `. _ : , / -`, at most 200 characters, since they reach a shell on the Pi. A bad value stops the deploy (exit 2 in bash).
- **Other `GTP_*` names** in the environment are listed as not passed; `GTP_DEPLOY_TTY` stays local.
- **Tests** (`tests/test_deploy_scripts.py`): the allowlist against `install.sh`; the check before the build; for each script, flags passed exactly and unknown names listed; a bad value (`;`, `$(...)`, a quote, a newline) stops with nothing built or uploaded. The PowerShell runs pass on Windows; the bash runs are for CI's Linux.
- **Docs:** `development/raspberry-pi-deploy.md` → "Install flags from the deploy scripts"; `deploy/sdr-stack.md` and `deploy/websdr.md` show the PC-side form.

## 2026-11-04 — The station's own DVB-T driver blacklist (#157)

Owner's rc.3 list. On 2026-11-04 the station's newly plugged-in dongle was held by the TV driver (`dvb_usb_rtl28xxu`, `rtl2832`, `rtl2832_sdr` loaded; no blacklist in `/etc/modprobe.d`). `GTP_SDR=1` relied on Debian's `rtl-sdr` blacklist, and `GTP_WEBSDR=1` had none, so with the web SDR alone the driver came back at every boot.

- **`scripts/rtl-dvb-blacklist.sh`**, run by `sdr-stack.sh` and `websdr.sh`:
  - writes `/etc/modprobe.d/gps-time-rtl-sdr.conf` (blacklist `rtl2832_sdr`, `dvb_usb_rtl28xxu`, `rtl2832`, `rtl2830`) atomically, mode 0644;
  - unloads whichever of them is loaded with `modprobe -r`, `rtl2832_sdr` first;
  - if one is busy it says to reboot, and the install goes on.
- **Never named:** shared modules (`dvb_core`, `dvb_usb_v2`, `videodev`, `regmap_i2c`, which the board's RTC driver also uses). Nothing in `/boot` or the initramfs changes.
- **Kept** when either stack is removed (`GTP_SDR=0`, `GTP_WEBSDR=0`); the guides say how to remove it.
- **Replaces** the two partial copies (each unloaded `dvb_usb_rtl28xxu` only).
- **Tests:**
  - `tests/test_dvb_blacklist.py`: the station's own `/proc/modules` as a fixture; the file's contents and mode; the unload order; nothing loaded means no `modprobe`; a busy module; idempotent; no shared module, `/boot` or timing word in the script; both installers call it and never remove it.
  - The SDR-stack and web-SDR script tests check the file is written.

## 2026-11-04 — Dongle roles by serial, at most 3 on a Pi 4 (#159)

Owner's rc.3 list. Roles were already given by serial (PPS, 1090, 978, and the web SDR's), but nothing counted them across the two installers, and Administration didn't show the web SDR's.

- **`scripts/dongle-roles.sh`**, sourced by `sdr-stack.sh` and `websdr.sh` before they change anything:
  - counts distinct serials across every installed role (a role of a stack that isn't installed doesn't count; the web SDR sharing the 1090 MHz dongle adds none);
  - refuses more than 3 on a Raspberry Pi 4, 400 or Compute Module 4 (the owner's limit: one USB 2.0 bus, shared power and CPU), from `/proc/device-tree/model`;
  - other boards have no limit; an unreadable model applies none and says so.
- **`/api/sdr`:** each dongle's role includes the web SDR (`1090 MHz + web SDR` when shared, `web SDR` alone). A new `limit` object gives the model (`observed`), the max, roles assigned (`calculated`), dongles plugged (`observed`), `over`, and the rule.
- **Administration → SDR receivers:** a line with the roles, the dongles on USB, and the limit; a warning when over it.
- **Tests:**
  - `tests/test_dongle_roles.py`: the helper with a temp device tree (3 on a Pi 4 fine, 4 refused, shared counted once, no limit on a Pi 5 or an unknown model); both installers refuse a fourth dongle before any `apt-get` and accept a shared one;
  - `tests/test_sdr_status.py`: roles and the limit;
  - `web/src/lib/sdr.test.ts`: the limit line.
- **Docs:** `deploy/sdr-stack.md` → "Roles and the limit", the web SDR guide, `/api/sdr`.

## 2026-11-04 — Station migration: export and import in one encrypted file (#160)

Owner's rc.3 list: migration export/import (config, keys, survey, oscillator). Needed before the antenna move and for a second Pi.

- **`python -m gps_time_pi.migrate export <file>` / `import <file> [--dry-run]`**, run with sudo in the station venv.
- **Moves:** `config.json` (+ `.prev`), with the site survey, exact position, privacy mode, time zone and module settings; `station-key` and `.pub`; `admin-token.sha256`; the web SDR password hash; `oscillator-log.csv` and the two profile files.
- **Never moves:** the event history and outage evidence (they describe the old install), and the sky-obstruction map (it describes the old antenna site).
- **Oscillator:** the log keeps its board binding. On the same Pi it carries on; on another Pi the station sets it aside at start (`oscillator.py`, unchanged).
- **Encrypted:** AES-256-GCM, with the key from scrypt (n = 2¹⁵, r = 8, p = 1). The header is authenticated as associated data. The passphrase is asked twice (at least 12 characters), never taken from arguments or the environment. The file is 0600 and handed to `SUDO_USER`; nothing is served over HTTP.
- **Import:**
  - refuses while `gps-time-pi` runs;
  - verifies every file's SHA-256 and refuses entries it doesn't know, or with a path in their name;
  - with root, checks the station's accounts exist before writing anything;
  - keeps each replaced file as `<name>.before-migrate-<UTC>`, and writes atomically with `install.sh`'s owner and mode;
  - is idempotent.
- **Tests:** `tests/test_migrate.py` (13): the parts moved and not moved; no plaintext secret, position or file name in the file; a round trip into a new station with backups and modes; idempotent; dry run; a running service; a wrong passphrase, a flipped byte and a changed header refused; an unknown or path-like entry refused; the passphrase never an argument. CI runs them in the station venv and fails if they're skipped.
- **Docs:** `deploy/migrate.md`; INDEX; CLAUDE.md.

## 2026-11-04 — The web SDR's WebSockets through the gate: a test, and `websdr_gate check` (#158)

Owner's rc.3 list: a web SDR WebSocket test. OpenWebRX+ streams audio and the waterfall over a WebSocket (`/ws/`). The gate checks the first request of each connection and then pipes bytes both ways. Until now only a plain HTTP request was tested through it.

- **`gps_time_pi/websdr_gate.py`:** a small stdlib WebSocket client (RFC 6455 handshake and framing). It backs `python -m gps_time_pi.websdr_gate check <url>`, the owner's check from a LAN machine:
  - no credentials are refused;
  - with them, the upgrade passes, with the right `Sec-WebSocket-Accept`;
  - OpenWebRX+ answers `SERVER DE CLIENT` with `CLIENT DE SERVER`;
  - then a clean close (it waits for the server's close frame).
  - The password is asked, never taken from the command line. A gate with no password says so.
- **`tests/test_websdr_websocket.py`:** the real gate in front of a fake OpenWebRX+ on the loopback.
  - Framing at every length size, masked and not; the RFC's own accept-key example.
  - `check` passes, and OpenWebRX+ never sees the `Authorization` header.
  - A wrong password never reaches it.
  - Frames pass both ways unchanged: 76,800 bytes from the server, a client frame split across writes, the close.
  - With no password, `check` says so.
- **Caught on the way:** the first draft named the new client `check`, which replaced the gate's password check of the same name, and every login crashed. The new test failed on it; the client is `check_station`.
- **Docs:** `deploy/websdr.md` → "Check it from your PC".

## 2026-11-04 — FAA airband bookmarks for the web SDR, offline, with the NASR cycle date (#162)

Owner's rc.3 list and design: NASR data; the cycle date shown on the bookmarks, flagged past 28 days; a "refresh now" admin button like the TLE cache.

- **`gps_time_pi/airband.py`:**
  - **Built-ins:** 121.5 guard, 122.75, 123.025, 122.9.
  - **The NASR set,** from the FAA's 28-day FRQ CSV of the current cycle. The cycles come from the anchor 2026-10-29, checked against the FAA's page today. URLs use fixed month names, not the locale's.
  - **Filter:** VHF airband, 118.000–136.975 MHz AM, within 80 km of `config.privacy_site` (exact or rounded); deduplicated.
  - **Columns** are read by header; a missing `FREQ`, `LAT_DECIMAL` or `LONG_DECIMAL` is refused.
  - **Writes:** `airband-bookmarks.json` and OpenWebRX+'s `airband-openwebrx.json`, atomically, once per refresh. The station's position isn't in either.
  - **Hidden mode:** nothing is fetched. A failed refresh keeps the previous bookmarks and is recorded in `airband-refresh.json`.
- **Refresh now:**
  - the admin action `refresh_airband` runs `systemctl start --no-block gps-time-airband-fetch.service`, a one-shot unit as `gps-time` (`ProtectSystem=strict`, writes only `/opt/gps-time-pi`), never enabled or timed;
  - polkit allows starting that unit only;
  - `websdr.sh` installs it, and links `/etc/openwebrx/bookmarks.d/gps-time-airband.json` to the file it writes;
  - the web service never fetches.
- **`GET /api/airband`** and the **Airband bookmarks** card on Radio & SDR → Devices: the cycle line (good, or a warning past 28 days with the current cycle), the last refresh, Refresh now, and the channels with their source.
- **Tests:**
  - `tests/test_airband.py`: the cycles, URLs, parsing (the radius, VHF only, duplicates), an unknown layout, a refresh with an injected download, rounded and hidden modes, bad downloads keeping the old set, staleness, the wiring;
  - the admin and polkit tests;
  - `web/src/lib/airband.test.ts`.
- **Not verified:** the FAA's file server answered this machine with 503, so the FRQ column names are the expected ones, not confirmed; a mismatch shows as a failed refresh. Not run on a Pi.

## 2026-11-04 — SDR node mode: a second Pi for the SDR load, its time from the station (#163)

Owner's rc.3 list and design: an SDR-only node; its chrony a client of the station (no GNSS or PPS), so its timestamps are sub-ms and labelled `ntp`; it may host the web SDR and feeders, so all SDR load can leave the timing Pi; feeds to the station only from its address.

- **`scripts/node.sh`:**
  - **On the node,** `GTP_NODE=1 GTP_NODE_STATION=<addr>`:
    - writes `/etc/chrony/sources.d/gps-time-node.sources` (`server <station> iburst minpoll 4 maxpoll 6 prefer`) and reloads chrony's sources. This is the only chrony change, on the node only, at the owner's request; `chrony.conf` itself is untouched.
    - fills drop-ins that let `rtl_tcp` (0.0.0.0:1234) and readsb's Beast (0.0.0.0:30005) take connections from the node and the station's address only.
  - **On the station,** `GTP_SDR_NODE=<addr>`:
    - fills `gps-time-readsb-node.service`, a network-only readsb that pulls the node's Beast into `/run/readsb/aircraft.json` (it `Conflicts=` the station's own readsb, and may reach the node only);
    - adds the node's address to the modules' drop-in.
  - **Rules:** addresses are IPv4 or IPv6 literals; `GTP_NODE=0` and `GTP_SDR_NODE=none` undo; a node can't also read a node; never the station's chrony, gpsd or PPS.
- **`gps_time_pi/timequality.py`, `GET /api/time-quality`:** role (station or SDR node), source (`refclock`, `ntp`, `unknown`) from `chronyc -n tracking`, and chrony's error bound (`calculated`). The clip recorder (next PR) labels its timestamps with it.
- **Web SDR link:** `/api/websdr` → `node_host`. With no web SDR on the station, the Radio page links to the node's web SDR and Radio page.
- **Deploy scripts** pass `GTP_NODE`, `GTP_NODE_STATION` and `GTP_SDR_NODE`.
- **Tests:** `tests/test_sdr_node.py`:
  - time quality for a station, a node, unknown, and the station knowing its node;
  - the templates (station-only allow-lists, no position, the reader reaching the node only);
  - no station timing in the script;
  - the script under stubs on both Pis: chrony source and drop-ins filled, the station's chrony never touched, refusals, a node can't read a node, undo.
- **Not run on two Pis** (`deploy/sdr-node.md` → "Not verified").

## 2026-11-04 — Capped clip recording: audio and IQ as SigMF with the station's timing (#164)

Owner's rc.3 list and design:
- audio and IQ (SigMF with timing);
- a capped RAM folder by default, oldest dropped;
- optionally a USB drive or NAS mount the owner names, capped, never the SD card;
- listed and downloadable on the Radio page;
- the timestamps carry the station's timing quality.

- **`gps_time_pi/clips.py`:**
  - **Source:** a small rtl_tcp client (the 12-byte header, then the sample-rate, frequency and gain commands).
  - **Kinds:** IQ as `cu8` at 1.024, 2.048 or 2.4 MS/s; AM, NFM and wide FM demodulated with numpy from 240 kS/s to 48 kHz `ri16_le`.
  - **Files:** written with `obsformat` and signed with the station key.
  - **Timing:** `time_source` from `timequality` (`pps` on the station, `ntp` on a node, `free_running`), `time_offset_bound_s` from chrony, and `sample_time_uncertainty_s` from the USB buffer (256 KiB at the byte rate, at least 50 ms; modeled). The position is at the privacy mode.
  - **Storage:** `/run/gps-time-clips` (RAM) or `GTP_CLIPS_DIR`, refused on the root file system's device. The cap drops the oldest clips; a clip too large for the cap is refused before recording.
- **Recording runs in `gps-time-clip.service`:** a one-shot as `gps-time`, localhost only, writing the RAM folder (or the owner's one folder, via a drop-in). The web service only validates and queues; polkit allows starting that unit only.
- **`scripts/clips.sh`** (run by `install.sh`): installs the unit and the tmpfiles entry. `GTP_CLIPS_DIR` (under /mnt, /media or /srv, not on the SD card's device) and `GTP_CLIPS_MAX_MB` are kept in `/etc/default/gps-time-clips`. The deploy scripts pass both.
- **API and UI:**
  - `GET /api/clips`, `GET /api/clips/file` (meta, data, and a WAV built on the fly; anything else is 404), `POST /api/setting {clip}` and `{clip_delete}`;
  - Radio & SDR → Devices → **Clips** (record, list with timing labels, download, delete).
- **Tests:**
  - `tests/test_clips.py`: validation, queueing one at a time, a unit that won't start, never the SD card, the cap, an IQ clip from a fake rtl_tcp that validates as SigMF with the commands sent, a node's clip labelled `ntp` with no position in hidden mode, a busy rtl_tcp, AM audio carrying a 1 kHz tone (numpy; CI runs it in the station venv), the listing, downloads refusing anything but a clip, delete, the unit and script;
  - `web/src/lib/clips.test.ts`;
  - the bundle-install test points `clips.sh` and `node.sh` at its root, and checks the clip unit is installed.
- **Not verified on a Pi** (`deploy/clips.md` → "Not verified").
