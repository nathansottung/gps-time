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

Dashboard configuration writes are allowed in demo mode, from loopback by default, or when `GTP_ALLOW_CONFIG_WRITE=1` is explicitly set for a trusted environment. This is **not** the final authentication model for a stable appliance.

## Planned editor improvements

- create/rename/delete pages from UI
- drag/reorder widgets
- widget-specific settings
- import/export layouts
- presets
- authentication/authorization for remote administration
