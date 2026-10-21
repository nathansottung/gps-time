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
