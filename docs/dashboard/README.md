# Dashboard architecture

The dashboard is configuration-driven. The same renderer is used in Windows demo mode and on the Pi.

## Configuration

Default: `config/dashboard.default.json` (also packaged under `gps_time_pi/data/`).

Runtime override: set `GTP_DASHBOARD_CONFIG` or allow the server to use `dashboard.json` next to `GTP_CONFIG`.

Pages contain widget records:

```json
{"id":"timing_quality","visible":true,"size":"normal"}
```

The development configuration editor is at `/configure`.

### Write safety

Dashboard configuration writes (`POST /api/dashboard`, `/api/dashboard/reset`) need the station admin token, except in demo mode, where writes go to `.dev/`. The `/configure` page prompts for the token. `GTP_ALLOW_CONFIG_WRITE` and the loopback exception were removed (ADR-0005).

## Planned editor improvements

- create/rename/delete pages from UI
- drag/reorder widgets
- widget-specific settings
- import/export layouts
- presets
- authentication/authorization for remote administration
