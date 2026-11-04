# ADR-0009: A web SDR on the station, behind a LAN gate (login optional since rc.5), sharing the 1090 MHz dongle

**Status:** Accepted (owner request, 2026-11-04: "Web SDR on the station Pi: add an optional GTP_WEBSDR=1 that installs OpenWebRX+, LAN-only and password-protected, linked from the Radio page. It gets the dongle on its own, with readsb stopped while it runs. Log CPU, temperature, and PPS jitter while it's in use."). Guide: `../deploy/websdr.md`.

## Context

The station tier stays lightweight and offline, and its timing core is protected. A web SDR is a heavy, interactive, third-party application: FFTs and demodulators per listener, a web server, WebSockets. The owner wants one on the station anyway, opt-in, with its cost measured.

OpenWebRX+ protects its settings with a login, but not its listening page. It listens on all addresses by default, and its package unit starts on install with the first RTL-SDR it finds.

## Decision

- **Opt-in at install** (`GTP_WEBSDR=1`, `scripts/websdr.sh`), never enabled at boot. Started and stopped on demand: Radio page (admin token; polkit allows `start` and `stop` of `gps-time-websdr.service` only) or `systemctl`. A session limit (`RuntimeMaxSec=`, default 4 h) ends a forgotten session.
- **OpenWebRX+ from its maintainer's apt repository,** the signing key pinned by fingerprint; the package's own unit masked; our unit runs it on 127.0.0.1:8074 and lets it reach the loopback only.
- **A password gate of our own** (`gps_time_pi/websdr_gate.py`, stdlib asyncio): HTTP Basic on each new connection, then a byte-for-byte pipe to OpenWebRX+, so WebSockets work. It fails closed with no password, backs off per address, logs no password, and strips the Authorization header before OpenWebRX+. Its unit accepts private address ranges only. Chosen over nginx because nginx's package would start on port 80, where the station's web service runs, and it is more to configure and keep for one route.
- **One dongle, one owner:** the 1090 MHz dongle by default. `Conflicts=` stops readsb before the web SDR opens it; `ExecStopPost=` starts readsb again. The PPS and 978 MHz dongles are refused.
- **The usage log in the web service,** which already reads every kernel PPS event: minute bins in RAM, a 10-minute baseline kept always, one summary line per session on the SD card. Phase jitter is `calculated` from `observed` timestamps; differences are reported, never a cause.

## Consequences

- The station gains a LAN listener while the web SDR runs. It is password-protected, plain HTTP, and private ranges only.
- ADS-B references pause while the web SDR runs. The usage log shows what the web SDR costs in CPU, temperature and PPS jitter, against the minutes before.
- OpenWebRX+ is AGPL-3.0 and is installed from its own repository, not shipped in the bundle (`THIRD_PARTY_NOTICES.md`).
- Features of OpenWebRX+ that need the Internet (map tiles fetched by the station, reporting, receiver lists) don't work. That is intended.
- Not run on a Pi yet (`../deploy/websdr.md` → "Not verified").

## Amendment, 2026-11-04 (rc.5): the login is optional

Owner: "Web SDR auth is optional: off by default, GTP_WEBSDR_AUTH=1 turns it on. When on, 'Remember this browser' sets a signed HttpOnly SameSite=Strict cookie (30 days, configurable). Changing the password or 'sign out all browsers' revokes it. Start/Stop always need the admin token."

- **The gate stays** in front of OpenWebRX+ either way: it is what keeps the web SDR on the LAN (`IPAddressAllow=` private ranges only) and OpenWebRX+ on the loopback. With the login off it passes every LAN connection through.
- **With the login on,** the gate serves its own sign-in page and still takes Basic credentials. "Remember this browser" is a cookie signed with HMAC-SHA256: the key comes from a random cookie key file and the stored password hash. So a new password revokes every cookie, and a new key (`signout-all`, the admin action `websdr_signout_all` through a root one-shot unit) revokes them without a new password. Both restart a running gate.
- **Start and Stop** stay admin actions (token, polkit), unchanged by the login.
- **Consequence:** with the default, anyone on the LAN can listen while the web SDR runs. An existing install has no `GTP_WEBSDR_AUTH` line, so it upgrades to login off; the installer says so. The cookie can't be `Secure` on plain HTTP.

The same release adds the decoders' helper packages, the station's band profiles and bookmarks, and opt-in HF profiles (`GTP_WEBSDR_HF`). None of that changes this decision's boundaries: OpenWebRX+ still reaches no outside host, and the station never touches gpsd, chrony or the PPS line.
