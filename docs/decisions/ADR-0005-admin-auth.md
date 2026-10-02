# ADR-0005: Admin token, POST-only state changes, Host/Origin checks, unprivileged service

**Status:** Accepted (feat/admin-auth, 2026-10-02). Closes review findings GPS-014, GPS-017 and GPS-019. Shipping `web/dist` to the Pi waits on this (owner decision, `STATUS.md`).

## Context

The station served state changes over unauthenticated GET routes: `/api/admin?action=reboot`, `/api/setting?reset_site=1`, and privacy changes. It ran as root, with no Host or Origin checks. Any page viewed by anyone on the LAN could reboot the station, restart chrony, erase the survey, or set privacy to `exact` (CSRF). DNS rebinding could read `/api`. In demo mode, `/api/admin` still ran `systemctl` on the developer's machine. The review's fix order was: POST + Origin/Host → admin off by default → unprivileged user + narrow polkit rule → authentication.

## Decision

1. **Host allowlist on every request** (DNS rebinding). Accepted:
   - IP literals;
   - `localhost` and `*.localhost`;
   - this machine's hostname and `<hostname>.local`;
   - names in `GTP_ALLOWED_HOSTS`.

   Everything else gets 403. Users who reach the station by another DNS name add it to `GTP_ALLOWED_HOSTS`.
2. **State changes are POST-only, JSON-only, same-origin.**
   - GET on a mutation route gets 405.
   - A non-JSON body gets 415. This rules out the "simple request" content types an HTML form can send.
   - A present `Origin` must match `Host` or be listed in `GTP_ALLOWED_ORIGINS` (for a reverse proxy), else 403.
   - A missing `Origin` is allowed for non-browser clients, which still need the token.
3. **Admin token.**
   - **Header:** state changes need `Authorization: Bearer <token>`.
   - **Generation and storage:** the token is 192 random bits (`python3 -m gps_time_pi.admin_token`). Only its SHA-256 is stored, 0640, readable by the service group. It is compared in constant time.
   - **Off by default:** no hash file means admin is disabled (403).
   - **Why a token, not passwords or sessions:** one secret per station is enough for a single-operator appliance, needs no login state on the server, and is easy to rotate.
   - **Not done:** rate limiting. 192 bits makes guessing infeasible.
4. **Demo isolation.** Demo mode needs no token (its writes go to `.dev/`), but `/api/admin` is simulated and never runs anything. Legacy pages show a SAMPLE DATA banner.
5. **Unprivileged service.** `gps-time-pi.service` runs as `gps-time`:
   - **Groups:** `_chrony` for the chronyc socket, `video` for vcgencmd.
   - **Capability:** only `CAP_NET_BIND_SERVICE`, for port 80.
   - **Hardening:** `NoNewPrivileges`, `ProtectSystem=strict` with `ReadWritePaths=/opt/gps-time-pi`, and **`ProtectClock=yes`**, so the web service can never set the system clock.
   - **Admin actions:** fixed `systemctl` argv lists with no shell. A polkit rule (`system/50-gps-time-pi.rules`) allows exactly: restart chrony/gpsd/gps-time-pi, start the log-flush unit, reboot.
   - **Code vs state:** the code directories stay root-owned. `/opt/gps-time-pi` is `root:gps-time 1775`, so the service can write its state files but cannot rename or replace the code.

## Consequences

- **Removed:** `GTP_ALLOW_CONFIG_WRITE` and the loopback exception. Behind a reverse proxy every client looked like loopback, so the token is the only gate.
- **Clients:** the legacy `/admin` and `/configure` pages prompt for the token. The new UI has an Admin access card. The token is kept in `sessionStorage` only.
- **No TLS:** the token crosses the LAN in clear text. On an untrusted LAN, use a TLS reverse proxy and set `GTP_ALLOWED_HOSTS`/`GTP_ALLOWED_ORIGINS`.
- **`chronyc clients`** needs chrony's local socket. If the `_chrony` group does not grant it, `/api` reports `clients: null` (UNKNOWN), not an empty list.
- **Not verified on a Pi** (no hardware in the development environment):
  - the systemd hardening;
  - the polkit rule on Raspberry Pi OS (polkit ≥ 121 JavaScript rules);
  - `_chrony` socket access;
  - vcgencmd under `video`.

  The installer and unit are checked statically by `tests/test_admin_auth.py`. Verify these on a station before release.
