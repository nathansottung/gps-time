# Legacy dashboard: removal plan

**Status: PLAN. Nothing has been removed.** Written 2026-10-05 from the repository as it stands. Nothing is to be deleted until the owner has read this and said which steps to take.

**Basis.** The owner asked for "the legacy-removal plan from my earlier prompt". That prompt could not be found: it is not in the repository, in the session's memory, or in the other session transcripts that could be searched. So this plan is built from what the repository already commits to: ADR-0004 ("the legacy pages are retired only when the parity list is empty or each item is explicitly dropped") and `web-ui-parity.md`. **If the earlier prompt said something different, it wins; please restate it.**

## 1. What "legacy" is

### Served pages

| Route | Template | Purpose |
|---|---|---|
| `/` | `templates/dashboard.html` | configurable dashboard (layout from `/api/dashboard`) |
| `/configure` | `templates/configure.html` | layout editor that saves to the station |
| `/legacy` | `templates/legacy.html` | instrument view |
| `/almanac` | `templates/almanac.html` | sun, moon, night, sky map, object lookup |
| `/history` | `templates/history.html` | offset chart, survey convergence |
| `/admin` | `templates/admin.html` | diagnostics, admin actions, survey reset, privacy mode |
| `/zones` | built in `server.zones_page()` | time-zone table |

### Files

| File | Lines | Used by |
|---|---|---|
| `gps_time_pi/templates/dashboard.html` | 29 | `/` |
| `gps_time_pi/templates/configure.html` | 6 | `/configure` |
| `gps_time_pi/templates/legacy.html` | 188 | `/legacy` |
| `gps_time_pi/templates/almanac.html` | 284 | `/almanac` |
| `gps_time_pi/templates/history.html` | 196 | `/history` |
| `gps_time_pi/templates/admin.html` | 107 | `/admin` |
| `gps_time_pi/templates/index.html` | 183 | **nothing**: the server doesn't load it (a near copy of `legacy.html`) |
| `gps_time_pi/static/app.js`, `style.css` | 81, 62 | legacy, almanac, history, admin, zones |
| `gps_time_pi/static/dashboard.js`, `dashboard.css` | 43, 4 | `/`, `/configure` |
| `gps_time_pi/static/configure.js` | 19 | `/configure` |
| `gps_time_pi/static/admin-auth.js` | 43 | `/admin`, `/configure` |

The line counts are small because several of these files are minified onto long lines.

### Code that exists only for the legacy pages

- `server.py`: the template loader and per-page CSP table, the six page routes, `zones_page()`, `/static/*` and `/static/custom.css`.
- `security.csp_for_html()`: the CSP exception that lets legacy pages use `style=""` attributes (`style-src 'unsafe-inline'`). Its own comment says it ends when the legacy pages are retired.
- `/api` → `state` and `fmt`: pre-formatted strings for the legacy pages (`units.fmt_pair`, `units.fmt_seconds`). The new UI formats values itself.
- `/api/dashboard` (GET and POST), `/api/dashboard/reset`, `gps_time_pi/dashboard.py`, `data/dashboard.default.json`, `tools/promote_dashboard.py`, and the deploy scripts' `-UseDemoLayout`: the saved-layout model. The new UI's client has the calls but no page uses them.
- `/api/object`'s server-global "last target", which `/api/almanac` reads back.

### Tests and docs that would change

- `tests/test_inline_styles.py` (6), `tests/test_web_ui.py` (13, partly), parts of `test_admin_auth.py`, `test_gnss_freshness.py`, `test_location_privacy.py`, `test_timing_chain.py`.
- `web/src/lib/legacy-almanac.test.ts`, `legacy-dashboard.test.ts` (they test the legacy JavaScript from the web test runner).
- Docs: `api/endpoints.md` ("Legacy pages"), `api/README.md`, ADR-0004, ADR-0005, `web-ui-parity.md`, both deploy checklists, the deploy guide, `install.sh`'s "legacy pages at / still work" message, `CLAUDE.md` ("the old dashboard is not restyled").

### Not legacy, stays whatever happens

`/time`, every `/api/*` route the new UI uses, `/app/`.

## 2. Why it can't simply be deleted today

The legacy pages are still the only place for several things an operator needs. Parity today, checked against the code (the list in `web-ui-parity.md` is dated 2026-10-01):

| # | Legacy feature | In `/app/` now | Suggested |
|---|---|---|---|
| 6 | Admin actions: flush logs, restart gpsd/chrony/web, reboot | **yes** (#81: Administration → Station actions, confirmation for all but the flush) | done |
| 7 | Survey reset | **no** | **port: blocker** (with a confirmation step) |
| 8 | Almanac date navigation | no | port |
| 9 | Twilight bar and night bar | no (data already in `/api/almanac`) | port |
| 10 | Moon details (time up, transit altitude) | no (data already there) | port |
| 11 | Sky map (stars, constellations, planets) | no (data already there) | port |
| 12 | Object lookup | no | port, and fix the server-global target while doing it |
| 14 | Survey convergence charts | no | port |
| 15 | Survey ingest counters | no | port |
| 13 | Offset chart uncertainty band, symlog axis | no | port **after** GPS-003/GPS-007 (the band's meaning is wrong today) |
| 1 | Themes: light, dark, night (red) | dark only | owner decides: night mode matters for observing |
| 4, 5 | Saved layout editor and layout-driven pages | no; `/app/` has fixed pages and a non-saving preview | owner decides: port, or drop the saved-layout model |
| 18 | `custom.css` site override | no | owner decides |
| 19 | `/zones` time-zone table | no link | owner decides: keep the route, link it, or drop |
| 21 | Throttle flags individually | partly (active flags, now and since boot) | probably enough; owner confirms |
| 16 | chrony detail (residual frequency, update interval, raw sourcestats) | mostly (PPS Diagnostics) | small port |
| 2 | Per-browser time-zone picker | partly: a station-wide override in Administration (#45) | probably enough; owner confirms |
| 20 | "Projected 1 s holdover" = 1/\\|ppm\\| | deliberately not ported | **drop** (needs the owner's explicit yes, per ADR-0004) |
| 3 | Station-corrected clock | **yes** (#47) | done |
| 17 | Satellite table TDOP | **yes** (GNSS page) | done |

Three of 21 are done (item 6 in #81), about four are partly covered, and the rest are open. **Item 7 is the remaining hard blocker:** without it, removing `/admin` leaves no way to reset the survey from a browser.

## 3. Proposed order

Each step is its own PR. Steps 1 to 3 delete nothing.

1. **Owner decisions** on the rows marked "owner decides" and on dropping item 20. Record them in `web-ui-parity.md`.
2. **Port the blockers**, in this order:
   1. Admin actions and survey reset in `/app/` Administration (items 6, 7).
   2. Almanac: date navigation, twilight and night bars, moon details (8, 9, 10).
   3. Sky map and object lookup (11, 12), with the object target made per-request.
   4. Survey convergence and ingest counters (14, 15); remaining chrony detail (16).
   5. Whatever the owner keeps from 1, 4/5, 18, 19.
   6. Item 13 after the chrony-history fix (next-5 item 1).
3. **Switch the front door, keep the old pages.** `/` redirects to `/app/`; the legacy dashboard moves to `/legacy/…` paths and gains a notice that it is going away. Ship that in a release and run it on the Pi. This is the point at which a missed feature shows up while the old page is still one click away.
4. **Remove**, after at least one release with step 3 in use and the owner's go-ahead:
   - the seven templates, including the unused `index.html`;
   - the six static files;
   - the page routes, the template loader, `zones_page()` (unless kept), `/static/*`;
   - `security.csp_for_html()` and the `'unsafe-inline'` style exception: every page then gets the strict CSP;
   - `/api` → `state` and `fmt`, and `units.py` if nothing else uses it then;
   - the saved-layout model (`/api/dashboard*`, `dashboard.py`, `dashboard.default.json`, `tools/promote_dashboard.py`, `-UseDemoLayout`), **only if** the owner dropped items 4 and 5;
   - the legacy tests listed above, replaced by tests of the ported features.
5. **Close what the removal settles:** review findings GPS-016 (unescaped `innerHTML` in the legacy view), GPS-027 (unit labels in `dashboard.js`), GPS-029 (dashboard config hardening, if the layout model goes), and the legacy halves of GPS-004 and GPS-009. Update ADR-0004 with the outcome, and the API docs, checklists and `CLAUDE.md`.

## 4. Timing

- **Not before v1.4.0.** The Pi runs the legacy pages today, rc.8 is about to start its soak run, and the fixes found on the first Pi build were found *through* the legacy pages. Removing them now would change what is being soaked.
- Steps 1 and 2 can proceed at any time: they only add to `/app/`.
- Step 3 fits the first release after v1.4.0; step 4 the one after that.

## 5. One thing that could be done now

`gps_time_pi/templates/index.html` is not loaded by the server, so no route serves it. (`tests/test_inline_styles.py` reads every template, this one included; no test depends on it.) Deleting it changes no behavior. It is still a deletion, so it waits for the owner's word like everything else here.

## 6. Rollback

Until step 4, nothing is lost: every legacy page is still served. After step 4, the previous release tag has them; the bundle for that tag can be redeployed (`docs/development/raspberry-pi-deploy.md` → "Rollback").
