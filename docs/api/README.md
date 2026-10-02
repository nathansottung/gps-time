# Station HTTP API

The station's web server (`gps_time_pi/server.py`, Python standard library) serves the API, the legacy pages and the new web UI. This directory documents every route the server answers. The reference is [`endpoints.md`](endpoints.md); this page covers the conventions that apply to all of them.

The TypeScript types in `web/src/api/types.ts` mirror these responses, and `web/src/api/client.ts` is the typed client. When a response changes, update the server, `endpoints.md` and `types.ts` in the same branch.

## Index

| Method | Path | Returns | Side effects | Doc |
|---|---|---|---|---|
| GET | `/api` | core status (chrony, GNSS, location, survey, versions) | none | [→](endpoints.md#get-api) |
| GET | `/api/timing-chain` | GNSS → PPS → chrony stages, PPS state, events | none | [→](endpoints.md#get-apitiming-chain) |
| GET | `/api/diagnostics` | plain-text diagnostic snapshot | none | [→](endpoints.md#get-apidiagnostics) |
| GET | `/api/history` | chrony tracking-log offset series | none | [→](endpoints.md#get-apihistory) |
| GET | `/api/survey` | position-survey convergence + persistence status | none | [→](endpoints.md#get-apisurvey) |
| GET | `/api/system` | host diagnostics (Pi model, load, power, RAM log) | none | [→](endpoints.md#get-apisystem) |
| GET | `/api/almanac` | sun, moon, night, sky for a date | none (reads the sky-map target last set by `/api/object`) | [→](endpoints.md#get-apialmanac) |
| GET | `/api/object` | rise/transit/set and viewing windows for one object | **sets a server-global "last target"** | [→](endpoints.md#get-apiobject) |
| GET | `/api/ping` | server receive/send timestamps | none | [→](endpoints.md#get-apiping) |
| GET | `/api/dashboard` | legacy dashboard layout + write permission | none | [→](endpoints.md#get-apidashboard) |
| POST | `/api/dashboard` | save legacy dashboard layout | **writes `dashboard.json`** | [→](endpoints.md#post-apidashboard) |
| POST | `/api/dashboard/reset` | restore default layout | **writes `dashboard.json`** | [→](endpoints.md#post-apidashboardreset) |
| GET | `/api/setting` | change location privacy mode, or reset the survey | **writes `config.json`** | [→](endpoints.md#get-apisetting) |
| GET | `/api/admin` | flush logs, restart gpsd/chrony/web, reboot | **runs system commands** | [→](endpoints.md#get-apiadmin) |
| GET | `/app/…` | the built web UI (`web/dist`) | none | [→](endpoints.md#get-app) |
| GET | `/`, `/configure`, `/legacy`, `/almanac`, `/history`, `/admin`, `/zones` | legacy HTML pages | none | [→](endpoints.md#legacy-pages) |
| GET | `/time` | plain-text UTC timestamp | none | [→](endpoints.md#get-time) |
| GET | `/static/*`, `/static/custom.css` | legacy CSS/JS, site CSS override | none | [→](endpoints.md#get-static) |

## Conventions

**Transport.** HTTP/1.1, no TLS. The server binds `0.0.0.0:80` on the Pi and `127.0.0.1:8080` in demo mode (`GTP_BIND`, `GTP_PORT`). There is no authentication: every route, including the ones that write or run commands, trusts the LAN. Dashboard writes are the only route with a gate (see [`POST /api/dashboard`](endpoints.md#post-apidashboard)). This is a known open item (`docs/review/GPS-Time-Independent-Review-2026-09-27.md`).

**Content types and caching.** JSON responses are `application/json; charset=utf-8` with `Cache-Control: no-store`. HTML is `no-store`. `/static/*` is `max-age=300`. `/app/` has its own rules ([details](endpoints.md#get-app)).

**Errors.**
- An unknown path returns HTTP 404.
- An exception inside a GET handler returns **HTTP 200** with `{"error": "<message>"}`. Clients must check for an object whose only key is `error`. `httpApi()` turns that into an `ApiError`.
- POST failures return HTTP 200 with `{"ok": false, "error": "..."}`.

**Units and labels.**
- Machine values are SI with the unit in the key name (`_s`, `_m`, `_ppm`, `_c`, `epoch_ms`).
- `/api/timing-chain` wraps measurements as `{"value", "unit", "provenance", "note"?}`. `provenance` is one of the six labels (observed, calculated, modeled, predicted, inferred, external); the code is in `gps_time_pi/labels.py`.
- `null` means the station could not establish the value. Clients show UNKNOWN; they never substitute a default.

**Location privacy.** `config.json` → `location_display` is `exact`, `rounded` or `hidden`. It is applied by the server in `/api` (`location`), `/api/diagnostics`, and the legacy pages. `/api/survey` → `fixes` are offsets in metres around the mean, never absolute positions. Known gaps are listed under [Privacy notes](endpoints.md#privacy-notes).

**Demo mode.** With `GTP_DEMO=1` the server swaps chrony/gpsd/sysfs readers for sample data. Shapes are unchanged, but some payloads carry a marker:
- `/api` → `"demo": true`
- `/api/timing-chain` → `"demo": {...}`
- `/api/almanac` → `"demo": true`
- `/api/dashboard` → `_meta.demo`

The web UI shows the demo banner whenever any of these is present.

## Using the API from the web UI

```ts
import { httpApi } from './api/client';        // same-origin station
const api = httpApi('');
const core = await api.core();                 // typed CoreStatus
```

The app picks its data source once at startup (`web/src/api/station.tsx`):

1. `?source=demo` or `?source=live` in the page URL;
2. otherwise the build-time `VITE_GTP_SOURCE`;
3. otherwise `live`.

`demo` uses `web/src/api/demo.ts`, a client-side adapter with the same interface and synthetic payloads. It makes no network requests, which is useful for UI work without Python. A failed live request is shown as an error or UNKNOWN; the app never falls back to demo data.

During `pnpm run dev`, Vite proxies `/api` to `GTP_API_TARGET` (default `http://127.0.0.1:8080`, the desktop demo).
