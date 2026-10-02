# Security policy

GPS Time Pi is intended to be a local-network timing appliance. Timing service availability and integrity take priority over dashboard convenience.

## Supported security model

- NTP serving should be restricted to explicitly allowed networks.
- The normal status interface should be read-only by default.
- Administrative actions must not rely solely on obscurity or LAN placement.
- Extensions and environmental collectors must not receive implicit permission to set system time or rewrite chrony configuration.
- Private location settings must be applied consistently to pages, APIs, exports, and diagnostic bundles.

## Reporting a vulnerability

Please avoid publishing an exploit against an actively deployed timing appliance before the maintainer has had a reasonable opportunity to investigate and fix it. Use a private GitHub security advisory when the repository enables that feature.

## Management interface

- **Admin token:** state-changing requests (admin actions, privacy and survey settings, dashboard layout) are POST-only, JSON-only and same-origin, and need the station admin token. Admin is disabled until a token exists: `sudo python3 -m gps_time_pi.admin_token`.
- **Host allowlist:** every request's `Host` must be allowed, which blocks DNS rebinding.
- **Unprivileged service:** the web service runs as `gps-time`, without root. A polkit rule allows only restarting chrony/gpsd/itself, flushing logs and reboot. `ProtectClock=yes` prevents it from setting the clock.
- **Token handling:** 32-byte random token, compared in constant time. Failed attempts are logged to the journal (never the token) with a per-IP backoff. The installer shows the token on the terminal only.
- **Security headers:** a strict `'self'`-only CSP with `frame-ancestors 'none'`, plus `nosniff`, `no-referrer` and `X-Frame-Options: DENY`, on every response.
- **Rollback:** a documented rollback to the root service exists (`docs/development/raspberry-pi-deploy.md`).
- **No TLS:** the station serves plain HTTP, so the token is not protected in transit. Use a TLS reverse proxy on untrusted networks.

Details: `docs/api/README.md` ("Authentication and request checks") and `docs/decisions/ADR-0005-admin-auth.md`.

## Current development note

The independent review (`docs/review/GPS-Time-Independent-Review-2026-09-27.md`) lists the remaining items; `docs/STATUS.md` tracks them. Do not expose the dashboard outside a trusted LAN until the systemd and polkit setup has been verified on a station and the remaining review items are closed.
