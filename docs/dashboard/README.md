# Dashboard architecture

The station UI is the React web UI in `web/`, served at `/app/` (ADR-0004). `/` and the retired legacy page paths redirect there. The same UI runs in Windows demo mode and on the Pi.

## Configuration

Layout choices are per browser, not stored on the station. The Configure page shows or hides pages and Overview cards (`gtp-modules` in the browser's local storage; Overview, Configure and Administration can't be hidden) and switches the red night theme (`gtp-theme`, or `?theme=night|dark`). Code: `web/src/lib/prefs.ts`.

The saved-layout model of the legacy dashboard was removed after v1.4.0: `/configure`, `/api/dashboard` (GET/POST), `/api/dashboard/reset`, `gps_time_pi/dashboard.py`, `gps_time_pi/data/dashboard.default.json`, `dashboard.json`, `GTP_DASHBOARD_CONFIG` and `tools/promote_dashboard.py` no longer exist. A `dashboard.json` left on an upgraded station is not read. Removal plan: `legacy-removal-plan.md`.

### Write safety

The settings and actions the UI can change on the station (Administration) need the station admin token, except in demo mode (ADR-0005).

## Planned editor improvements

- drag/reorder widgets
- widget-specific settings
- presets
