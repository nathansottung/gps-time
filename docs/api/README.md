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
| GET | `/api/stability` | ADEV, MDEV, TDEV of the system clock against kernel PPS | none | [→](endpoints.md#get-apistability) |
| GET | `/api/timescales` | TAI, GPS time and week, MJD/JD, leap-second table, UT1 − UTC from a cached file | none | [→](endpoints.md#get-apitimescales) |
| GET | `/api/survey` | position-survey convergence + persistence status | none | [→](endpoints.md#get-apisurvey) |
| GET | `/api/system` | host diagnostics (Pi model, load, power, RAM log) | none | [→](endpoints.md#get-apisystem) |
| GET | `/api/almanac` | sun, moon, night, sky for a date | none (reads the sky-map target last set by `/api/object`) | [→](endpoints.md#get-apialmanac) |
| GET | `/api/object` | rise/transit/set and viewing windows for one object | **sets a server-global "last target"** | [→](endpoints.md#get-apiobject) |
| GET | `/api/ping` | server receive/send timestamps | none | [→](endpoints.md#get-apiping) |
| GET | `/api/auth` | whether admin is enabled and the sent token is valid | none | [→](endpoints.md#get-apiauth) |
| GET | `/api/dashboard` | legacy dashboard layout + write permission | none | [→](endpoints.md#get-apidashboard) |
| POST | `/api/dashboard` | save legacy dashboard layout | **writes `dashboard.json`**; admin token | [→](endpoints.md#post-apidashboard) |
| POST | `/api/dashboard/reset` | restore default layout | **writes `dashboard.json`**; admin token | [→](endpoints.md#post-apidashboardreset) |
| POST | `/api/setting` | change location privacy mode, or reset the survey | **writes `config.json`**; admin token | [→](endpoints.md#post-apisetting) |
| POST | `/api/admin` | flush logs, restart gpsd/chrony/web, reboot | **runs system commands**; admin token | [→](endpoints.md#post-apiadmin) |
| GET | `/app/…` | the built web UI (`web/dist`) | none | [→](endpoints.md#get-app) |
| GET | `/`, `/configure`, `/legacy`, `/almanac`, `/history`, `/admin`, `/zones` | legacy HTML pages | none | [→](endpoints.md#legacy-pages) |
| GET | `/time` | plain-text UTC timestamp | none | [→](endpoints.md#get-time) |
| GET | `/static/*`, `/static/custom.css` | legacy CSS/JS, site CSS override | none | [→](endpoints.md#get-static) |

## Conventions

**Transport.** HTTP/1.1, no TLS. The server binds `0.0.0.0:80` on the Pi and `127.0.0.1:8080` in demo mode (`GTP_BIND`, `GTP_PORT`). Without TLS the admin token crosses the LAN in clear text; put the station behind a TLS reverse proxy if the LAN is not trusted (see `GTP_ALLOWED_ORIGINS` below).

## Authentication and request checks

These close review findings GPS-014, GPS-017 and GPS-019. Implementation: `gps_time_pi/security.py` and `server.Handler.do_POST`. Decision: `docs/decisions/ADR-0005-admin-auth.md`.

**Host allowlist (every request).** The `Host` header must be one of:
- an IP literal;
- `localhost` or `*.localhost`;
- this machine's hostname, or `<hostname>.local`;
- a name listed in `GTP_ALLOWED_HOSTS` (comma-separated).

Anything else gets **403** with a plain-text explanation. This defeats DNS rebinding: a page on an attacker's domain that resolves to the station sends the attacker's name as `Host`.

**State changes are POST-only.** That covers `/api/admin`, `/api/setting`, `/api/dashboard` and `/api/dashboard/reset`.
- `GET /api/admin` and `GET /api/setting` return **405** with `Allow: POST`.
- A POST must be `Content-Type: application/json` (else **415**) with a JSON object body of 1 B–256 kB (else **400**).
- If `Origin` is present, it must be same-origin with `Host` or listed in `GTP_ALLOWED_ORIGINS` (else **403**). Browsers always send `Origin` on POST, so cross-site forms and fetches are refused.

**Admin token (outside demo mode).** Every POST needs `Authorization: Bearer <token>`.
- **No token configured:** if the station has no token hash file, admin is **disabled** and POSTs get **403**.
- **Missing or wrong token:** **401** with `WWW-Authenticate: Bearer`.
- **Comparison:** `hmac.compare_digest` on the SHA-256, so the check takes the same time whether or not the token matches.
- **Generation:** the token is 32 random bytes from `secrets` (URL-safe base64, 43 characters).
- **Failed attempts:**
  - Each is logged to the journal: `WARNING gps_time_pi.security: admin token rejected: ip=… route=… reason=missing|malformed|invalid failures=n backoff_s=…`. The token and the header are never logged.
  - After 3 failures from one IP, further attempts get **429** with `Retry-After` for 2, 4, 8 … s (at most 300 s), even with the right token. A success resets the count.
  - `GET /api/auth` with a token counts too.
  - The counters are in memory. Behind a reverse proxy all clients share one IP, so a guesser can delay everyone for up to 5 minutes.
- **Storage:** only a SHA-256 of the token is stored. The file is `admin-token.sha256` next to `config.json`, or `GTP_ADMIN_TOKEN_FILE`, mode 0640 readable by the service group.
- **Create or rotate** with `sudo python3 -m gps_time_pi.admin_token --tty-only --path /opt/gps-time-pi/admin-token.sha256 --group gps-time`.
  - `--tty-only` writes the token to the terminal (`/dev/tty`) only, never to stdout, so it can't end up in a log or a pipe.
  - Without a terminal, nothing is created.
  - `install.sh` does the same on first install. The deploy scripts open a remote terminal only when they run interactively.
  - Delete the file to disable admin.
- **In the web UI** the token is entered on the Administration page (new UI) or prompted by `/admin` and `/configure` (legacy). It is kept in `sessionStorage` for that tab only and never put in a URL.

**Demo mode** (`GTP_DEMO=1`) needs no token, because writes go to `.dev/` only. `POST /api/admin` is **simulated** (`"simulated": true`) and never touches the host. Method, Origin, Content-Type and Host checks still apply.

**Security headers (every response).**
- `Content-Security-Policy`:
  - `default-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; script-src 'self'; style-src 'self'`.
  - Legacy HTML pages differ in two ways. `script-src` adds the SHA-256 hashes of that page's own static inline scripts (never `'unsafe-inline'` for scripts). `style-src` adds `'unsafe-inline'`, because the legacy pages build `style=""` attributes at runtime. That exception ends with the legacy pages.
  - The built UI inlines no assets (`build.assetsInlineLimit: 0`). Web CI fails on `data:` fonts or images in the bundle.
- `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`.

**Privileges.** The service runs as the unprivileged user `gps-time` (`gps-time-pi.service`). Admin actions are fixed `systemctl` commands, and a polkit rule (`system/50-gps-time-pi.rules`) allows exactly those: restart chrony/gpsd/itself, start the log flush, reboot. `ProtectClock=yes` means the web service can never set the system clock.

**Content types and caching.** JSON responses are `application/json; charset=utf-8` with `Cache-Control: no-store`. HTML is `no-store`. `/static/*` is `max-age=300`. `/app/` has its own rules ([details](endpoints.md#get-app)).

**Errors.**
- An unknown path returns HTTP 404.
- An exception inside a GET handler returns **HTTP 200** with `{"error": "<message>"}`. Clients must check for an object whose only key is `error`. `httpApi()` turns that into an `ApiError`.
- Request-check failures use real status codes with `{"ok": false, "error": "..."}` (Host refusal is plain text):
  - 400 bad body
  - 401 token
  - 429 too many failed token attempts (`Retry-After`)
  - 403 Host / Origin / admin disabled
  - 405 method
  - 415 content type
- A POST that passes the checks but fails validation returns HTTP 200 with `{"ok": false, "error": "..."}`.

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
api.token.set('<admin token>');                // per tab (sessionStorage)
await api.setLocationDisplay('hidden');        // POST + JSON + Bearer
```

The app picks its data source once at startup (`web/src/api/station.tsx`):

1. `?source=demo` or `?source=live` in the page URL;
2. otherwise the build-time `VITE_GTP_SOURCE`;
3. otherwise `live`.

`demo` uses `web/src/api/demo.ts`, a client-side adapter with the same interface and synthetic payloads. It makes no network requests, which is useful for UI work without Python. A failed live request is shown as an error or UNKNOWN; the app never falls back to demo data.

During `pnpm run dev`, Vite proxies `/api` to `GTP_API_TARGET` (default `http://127.0.0.1:8080`, the desktop demo).
