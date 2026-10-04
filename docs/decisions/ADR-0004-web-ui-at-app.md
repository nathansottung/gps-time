# ADR-0004: Serve the React web UI from the station at /app/, beside the legacy pages

**Status:** Accepted (feat/web-dashboard, 2026-10-01)

## Context

The React/Vite UI in `web/` is being ported to become the Pi UI (CLAUDE.md). Until now it was a standalone prototype with hard-coded synthetic data (`web/src/data/demo.ts`), not connected to the station. The legacy dashboard (`gps_time_pi/templates`, `static/`) is still the only complete UI, and must stay until the new one reaches parity.

## Decision

1. **Same server, separate prefix.**
   - `gps_time_pi/server.py` serves the built app (`web/dist`, override with `GTP_WEB_DIST`) under `/app/`.
   - The legacy routes (`/`, `/legacy`, `/almanac`, `/history`, `/admin`, `/configure`, `/zones`) and every `/api` route are unchanged.
   - No new process, port or dependency. The standard-library server reads files per request and never writes.
   - `index.html` is `no-store`; Vite's content-hashed `assets/` are cached immutably.
   - Path traversal is refused.
   - A missing build returns 503 with instructions instead of a broken page.
2. **One typed client, two adapters.**
   - `web/src/api/client.ts` defines `StationApi`, typed against the documented API (`docs/api/`).
   - `httpApi()` talks to the station (same origin).
   - `demoApi()` (`web/src/api/demo.ts`) returns synthetic payloads in the same shapes, for UI work with no station.
   - The source is chosen explicitly (`?source=`, `VITE_GTP_SOURCE`, default live). A failed live request is never replaced with demo data.
3. **Previews only under demo.**
   - Panels for features that have no endpoint yet use `<Planned>`. With demo data they show the preview (from `web/src/api/previews.ts`) under the demo banner. With a live station they show "Not available from this station yet" and what the feature needs.
   - The demo banner appears whenever the client adapter is demo **or** the station reports demo mode (`GTP_DEMO`).

## Consequences

- ADR-0002 still holds. The server's demo mode (`GTP_DEMO=1`) remains the primary demo, and the new UI renders it through the same live client. The client-side adapter is a provider swap for front-end development, not a separate mockup.
- The new UI can be tried on any station at `/app/` without affecting the legacy pages. The parity gap list is `docs/dashboard/web-ui-parity.md`. The legacy pages are retired only when that list is empty or each item is explicitly dropped.
- Update 2026-10-04: the deploy bundle ships `web/dist` and `install.sh` installs it to `/opt/gps-time-pi/web/dist`. The UI is built on the deploying machine; the Pi needs no Node. (Before that, a station returned 503 at `/app/`.)
- The API has no authentication. Exposing more write actions in the new UI (admin actions, survey reset) waits on the administrative-security item in the independent review.
