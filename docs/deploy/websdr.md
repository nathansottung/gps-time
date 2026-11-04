# The optional web SDR (`GTP_WEBSDR=1`)

A browser radio on the station: [OpenWebRX+](https://luarvique.github.io/ppa/) behind a password gate, on the LAN only, linked from Radio & SDR → Devices. Owner request, 2026-11-04. Decision: `../decisions/ADR-0009-web-sdr-on-station.md`.

| Part | Unit | Listens on | Reaches |
|---|---|---|---|
| OpenWebRX+ (Debian package `openwebrx` from the OpenWebRX+ repository) | `gps-time-websdr.service`, user `openwebrx` | 127.0.0.1:8074 (`/etc/openwebrx/openwebrx.conf.d/gps-time.conf`) | the loopback only (`IPAddressAllow=localhost`, `IPAddressDeny=any`) |
| The password gate (`gps_time_pi/websdr_gate.py`) | `gps-time-websdr-gate.service`, a dynamic user | `GTP_WEBSDR_PORT` (8073), all addresses | private ranges only: 10/8, 172.16/12, 192.168/16, 169.254/16, fc00::/7, fe80::/10 and the loopback |

Script: `scripts/websdr.sh`. Units and files: `system/gps-time-websdr.service`, `system/gps-time-websdr-gate.service`, `system/websdr-handoff`, `system/openwebrx-gps-time.conf`. Tests: `tests/test_websdr.py`, `web/src/lib/websdr.test.ts`.

## One dongle, one owner

The web SDR uses one RTL-SDR, picked by serial. By default that is the 1090 MHz dongle (`GTP_SDR_1090_SERIAL` from the SDR stack, `sdr-stack.md`), so:

- **Starting the web SDR stops readsb** (`Conflicts=gps-time-readsb.service readsb.service`, and `After=` waits for it to let go of the dongle). The ADS-B references in `reference-adsb` pause; its readiness shows the 1090 MHz feed as stale.
- **Stopping it starts readsb again** (`ExecStopPost=` runs `websdr-handoff`, which starts readsb if it is enabled; not during a shutdown).
- **Never the PPS or the 978 MHz dongle:** the installer refuses those serials.
- **A session ends by itself** after `GTP_WEBSDR_MAX_HOURS` (default 4; `RuntimeMaxSec=`), so a forgotten web SDR doesn't keep readsb off. The unit then shows as failed (result `timeout`), and readsb comes back. There is no automatic restart.
- **Not enabled at boot.** Start and stop it from the Radio page (admin token) or with `sudo systemctl start|stop gps-time-websdr`. Use start and stop, not restart: a restart briefly starts readsb between the two halves.

## Install

```sh
sudo GTP_WEBSDR=1 bash install.sh
```

With the SDR stack installed and a 1090 MHz serial set, that's all. Otherwise give the serial: `sudo GTP_WEBSDR=1 GTP_WEBSDR_SERIAL=00001090 bash install.sh`. Optional: `GTP_WEBSDR_PORT` (1024–65535, not 8074; default 8073) and `GTP_WEBSDR_MAX_HOURS` (1–24). Settings are kept in `/etc/default/gps-time-websdr`, so a later `sudo bash install.sh` keeps the web SDR as it is.

Then set the password (asks twice; at least 10 characters; the user name is `radio` unless `--user` is given):

```sh
sudo /opt/gps-time-pi/venv/bin/python -m gps_time_pi.websdr_gate passwd
```

Until a password is set, the gate answers 503 to everything. A new password applies from the next start of the web SDR.

For OpenWebRX+'s own settings page, add its admin user too: `sudo openwebrx admin adduser <name>`. That login protects only its settings; the gate protects everything.

**What it changes on the station:**
- **APT:** `/usr/share/keyrings/gps-time-openwebrx-plus.gpg` and `/etc/apt/sources.list.d/gps-time-openwebrx-plus.list` for bookworm or trixie. The signing key is downloaded and kept only if its fingerprint is `82B2 AC14 962B 3C75 FAC9 7206 B64E ADD5 CB69 C981` (Marat Fayzullin, the OpenWebRX+ maintainer; checked 2026-11-04). If the package can't be installed, the repository entry is taken out again.
- **Packages:** `openwebrx` and its dependencies (csdr, the connectors, codecs). The package's own `openwebrx.service` is masked before the install: it would start on port 8073 with the first dongle it finds. If `openwebrx` was already installed and enabled by the owner, the script changes nothing.
- **OpenWebRX+ settings:** `/var/lib/openwebrx/settings.json`. A new file gets one RTL-SDR device with five VHF/UHF profiles (2 m, 70 cm, FM broadcast, airband, NOAA weather). An existing file is kept, with a copy beside it (`settings.json.gps-time-prev`); only its RTL-SDR devices' serial is set.
- **The DVB-T driver** is unloaded if it is loaded.
- **No position:** the installer gives OpenWebRX+ no receiver location. Its default location (Budapest, from the package) stays unless the owner changes it. Don't enter the station's position there: OpenWebRX+ doesn't know the station's privacy mode, and it shows its location to every listener.

**Never touched:** gpsd, chrony, the PPS line and its overlay, and `/boot`.

**Limits of each unit:**
- OpenWebRX+: 200 % CPU (two cores), 512 MiB, `Nice=10`; writes only to `/var/lib/openwebrx` (settings, when changed).
- The gate: 30 % CPU, 64 MiB, no devices, no capabilities.

## Use

Radio & SDR → Devices → Web SDR: state, serial, port, session limit, **Start** (asks first), **Stop**, and **Open the web SDR ↗** while it runs. The link is `http://<the station's address>:8073/`. The browser asks for the web SDR's login.

The listening page is plain HTTP and Basic credentials are only base64 on the wire, so use it on the LAN only. The gate drops anything from outside the private ranges, whatever a router forwards. OpenWebRX+ itself can reach no host but the station: map tiles, PSK Reporter, APRS-IS, receiver lists and update checks don't work, and nothing is reported anywhere. Its map page may still ask the browser to load map tiles from the Internet.

## The usage log

The owner asked for CPU, temperature and PPS jitter while it is in use. The web service (`gps_time_pi/websdr.py`) keeps:

- **Every 10 s:** the whole system's CPU (`/proc/stat`), the web SDR and gate units' CPU (their cgroups), the SoC temperature.
- **Every kernel PPS event**, from the timing chain's poller: its phase, where the system clock read at the edge (the `/api/stability` layer, interrupt latency and chrony's loop included).
- **One bin a minute** in RAM: CPU mean and largest sample, temperature mean and highest, PPS jitter (the standard deviation of the minute's phases), the largest |phase|, and the pulses seen.
- **The last 10 minutes are always kept,** so each session has a before to compare with.
- **While the web SDR runs,** its minutes are kept (RAM, at most 12 h).
- **When it stops,** one summary line is written to `websdr-sessions.jsonl` beside `config.json`: start, end, duration, and the before and during figures. That's one write per session. The file keeps the last 100 sessions.

The Radio page shows this session's (or the last one's) before and during side by side, and earlier sessions' PPS jitter. `/api/websdr` serves all of it (`../api/endpoints.md`).

What it can and can't say:
- It shows what changed while the web SDR ran, not why. A higher jitter during a session is a correlation; the station names no cause.
- The PPS timestamps reach Python as floats, which near today's epoch resolve about 0.24 µs. Jitter figures near that are at the resolution limit. The same holds for `/api/stability`.
- A session that was already running when the web service started is marked partial: its first part wasn't recorded.
- The soak record (`tools/soak_check.py`) doesn't include the web SDR's units; a soak run should be done with the web SDR stopped.

## Remove

```sh
sudo GTP_WEBSDR=0 bash install.sh
```

This stops and removes the two units, the session-limit drop-in, `websdr-handoff` and the OpenWebRX+ port setting. It keeps the package and its repository, the mask on `openwebrx.service`, `/etc/default/gps-time-websdr`, the password and `/var/lib/openwebrx`. To remove the rest: `sudo apt-get purge openwebrx`, `sudo rm /etc/apt/sources.list.d/gps-time-openwebrx-plus.list /usr/share/keyrings/gps-time-openwebrx-plus.gpg`, `sudo systemctl unmask openwebrx`.

## Not verified

The script is tested with stub commands only (`apt-get`, `systemctl`, `curl`, `gpg` and `dpkg` are stubbed; every path is under a temporary root). The gate is tested end to end on the loopback, and the usage log with a manual clock. None of this has run on a Pi yet:
- the `openwebrx` package install on trixie arm64, and its postinst with the unit masked;
- OpenWebRX+ under this unit's hardening (it may need a path or address family the unit doesn't allow);
- the serial pin in `settings.json` (key `device`) with this OpenWebRX+ version;
- the readsb handoff under systemd, and `RuntimeMaxSec=` ending a session;
- OpenWebRX+'s CPU on the station, and its effect on PPS timing, which is what the usage log is for.
