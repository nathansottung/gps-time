# Build and deploy to Raspberry Pi

Step-by-step checklists: [`../deploy/fresh-pi-install.md`](../deploy/fresh-pi-install.md) for a newly flashed Pi, and [`../deploy/first-pi-deploy.md`](../deploy/first-pi-deploy.md) for upgrading a v1.3 station.

`install.sh` starts with a preflight: it stops, before changing anything, if it isn't run as root, chrony isn't installed, or the `_chrony` or `video` group is missing. It warns if gpsd or polkit is missing. It doesn't install chrony, gpsd or PPS, and it doesn't configure them beyond three `chrony.conf` edits: `log tracking`, `logdir /run/chrony-log`, and disabling DHCP-provided NTP servers (below). Only when asked, it also adds a file of `noselect` servers ("Independent references", below).

## Build archives

From Windows/VS Code:

```powershell
cd web; corepack pnpm install --frozen-lockfile; corepack pnpm run build; cd ..
python tools\build_bundles.py
```

The Pi archive ships the built web UI (`web/dist`), so `/app/` works on a station without Node. `build_bundles.py` stops if the UI isn't built, or if it was built from another version than the checkout (`web/dist/version.txt`). `--without-web` builds a bundle with no UI; `/app/` then returns 503 on the station.

Outputs:

- `dist/gps-time-development.zip` — full development/repo archive
- `dist/gps-time-pi-deploy.tar.gz` — deployment-oriented archive
- `dist/SHA256SUMS.txt`

Both archives contain `gps_time_pi/VERSION`, the `git describe` of the checkout you built from (for example `1.4.0-rc.1`, or `1.4.0-rc.1-3-gabc1234-dirty`). The station has no `.git`, so `/api` and the UI footer read their version from this file. To deploy a release, check out its tag first (`git checkout v1.4.0-rc.1`). Without a reachable `v*` tag, the file is left out and the station reports `unknown`.

## One-command-ish deployment

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-to-pi.ps1 -PiHost 192.168.1.50 -PiUser pi
```

The script:

1. builds the web UI, then the bundle, after deleting any old one, so a failed build can't upload a stale archive;
2. uploads it with `scp` into a fresh `~/gps-time-deploy` on the Pi;
3. checks its SHA-256 there;
4. extracts it and runs `sudo bash install.sh`, which also installs the UI to `/opt/gps-time-pi/web/dist`, replacing the previous copy.

It stops at the first failed step, so `install.sh` never runs on an archive that doesn't match. Run it from an interactive terminal: `ssh -t` then lets sudo prompt and shows the admin token. Without a terminal, sudo on the Pi must not need a password.

Bash equivalent:

```bash
./scripts/deploy-to-pi.sh 192.168.1.50 pi
```

## Python dependencies (venv)

The system Python on Debian 12 (Bookworm, 3.11) and Debian 13 (Trixie, 3.13) is externally managed (PEP 668), so `install.sh` doesn't use system pip. It creates `/opt/gps-time-pi/venv` with `python3 -m venv` (installing `python3-venv` if needed), installs the pinned `requirements.txt` into it, and the service runs `/opt/gps-time-pi/venv/bin/python`. If the OS Python is upgraded and the venv's interpreter stops working, re-running `install.sh` recreates it. Installing dependencies needs the Internet (PyPI/piwheels); the service itself doesn't.

Older installs put skyfield into the system Python with `--break-system-packages`. That copy is no longer used. Removing it is optional (`sudo pip3 uninstall --break-system-packages skyfield`), and a full rollback to v1.4.0-rc.1 or earlier still uses it.

## chrony polling the station itself

If the router's DHCP names the station as the LAN's NTP server (option 42), the station receives that too, and Debian's chrony adds it as a source through `sourcedir /run/chrony-dhcp`. The station then polls its own address. That "server" looks like a perfect stratum-1 source, and after a PPS loss chrony can select it and follow itself.

- The station software detects it: `/api` marks the source `is_self`, the Network page shows THIS STATION, it is never counted as a fallback, and if chrony selects it the status is `HOLDOVER · NO EXTERNAL REFERENCE · CHRONY SELECTED THIS STATION ITSELF`.
- `install.sh` stops it: it comments out `sourcedir /run/chrony-dhcp` in `/etc/chrony/chrony.conf` (`scripts/chrony-no-dhcp-sources.sh`), then restarts chrony as it always has.
  - Only that line changes. Refclocks, `pool`/`server` lines and `/etc/chrony/sources.d` are untouched, so a station whose only network fallback came from DHCP needs a `server` or `pool` line of its own.
  - The file as it was before the first change is kept as `/etc/chrony/chrony.conf.before-gps-time-pi`. Running the installer again changes nothing more.
  - To keep DHCP-provided servers: `sudo GTP_KEEP_DHCP_NTP=1 bash install.sh`. To undo later: remove the leading `# ` from that line and `sudo systemctl restart chrony`.
- The running web service still never writes chrony's configuration; only the installer does.

## Local time display

The main clock shows local time; the station itself stays on UTC. Don't change the Pi's system time zone for this (`timedatectl` is not used anywhere). The zone is found offline from the station's position with `tzfpy` (in the venv), or set in Administration → Local time zone. With the location hidden, the zone is not derived from the position.

## Independent references (optional)

Timing → References compares the station with NTP servers that chrony measures but doesn't use to set the clock. It works with whatever such servers chrony already has. To add dedicated ones that can never be selected (`noselect`):

```sh
sudo GTP_INDEPENDENT_REFS=1 bash install.sh
```

- This adds `time.nist.gov`, `tick.usno.navy.mil` and `tock.usno.navy.mil` in `/etc/chrony/sources.d/gps-time-independent.sources`, polled every 4 to 17 minutes. Give your own list instead with `GTP_INDEPENDENT_REFS="host1 host2"`. Remove them with `GTP_INDEPENDENT_REFS=0`.
- It is off unless you ask: it changes chrony's configuration and makes chrony contact those servers over the Internet. Without the variable, the installer leaves an existing file alone.
- Without Internet the page reads "no external references reachable". Nothing else is affected.
- The per-server network delay comes from the same helper service as the NTP client list (`systemctl status gps-time-pi-chrony-clients`). If it isn't running, delay reads UNKNOWN.
- Details: `../architecture/independent-references.md`.

## Leap seconds and UT1 (time scales panel)

- TAI and GPS time on Timing → Time Scales use the leap-second table from Debian's `tzdata` package (`/usr/share/zoneinfo/leap-seconds.list`). The panel warns 60 days before the table expires. To renew it: `sudo apt-get update && sudo apt-get install --only-upgrade tzdata`. This doesn't touch chrony.
- UT1 − UTC is shown only if you place an IERS `finals2000A.daily` file at `/opt/gps-time-pi/iers/finals2000A.daily` (readable by `gps-time`). The station never downloads it. Fetch it on another machine from the IERS data centre, copy it over, and replace it every few weeks; the panel shows the file's date and whether the value is an IERS determination or prediction.

## Admin token and service user

`install.sh` creates the unprivileged service user `gps-time` and installs the polkit rule `/etc/polkit-1/rules.d/50-gps-time-pi.rules`. On a first install it also creates an admin token and **shows it once, on the terminal only**; keep it. Settings changes and service actions in the web UI need it. Without a terminal (non-interactive ssh, a CI log), no token is created and admin stays disabled until you run the command below on the station.

- Create or rotate: `sudo python3 -m gps_time_pi.admin_token --tty-only --path /opt/gps-time-pi/admin-token.sha256 --group gps-time` (run in `/opt/gps-time-pi`).
- Failed token attempts are in the journal: `journalctl -u gps-time-pi | grep "admin token"`.
- Disable admin: delete `/opt/gps-time-pi/admin-token.sha256`.
- The NTP client list comes from `gps-time-pi-chrony-clients.service`, which runs as `_chrony` and publishes `chronyc -n clients` to `/run/gps-time-pi/` every 15 s. The web service itself can't use chronyd's control socket. If the list reads UNKNOWN: `systemctl status gps-time-pi-chrony-clients`.
- If you reach the station by a DNS name other than its hostname, add it to `GTP_ALLOWED_HOSTS` in the service (`sudo systemctl edit gps-time-pi`). Otherwise requests get 403.

After upgrading an existing station, check `systemctl status gps-time-pi`, `/api/system` (vcgencmd values) and the NTP client list. ADR-0005 lists what has not yet been verified on a Pi.

## Rollback

If the station misbehaves after an upgrade to the unprivileged service, use one of the two levels below. Before either, capture `journalctl -u gps-time-pi -n 200` and `systemctl status gps-time-pi`.

**Symptoms:** the web UI is unreachable, `systemctl status gps-time-pi` shows a failure, or values are missing that worked before (system diagnostics, NTP clients, PPS).

**Level 1: root service, new code.** This restores the pre-upgrade privileges and keeps the new code, including the admin token checks.

```sh
sudo install -D -m 0644 /opt/gps-time-pi/rollback/gps-time-pi-root-rollback.conf \
     /etc/systemd/system/gps-time-pi.service.d/zz-root-rollback.conf
sudo systemctl daemon-reload && sudo systemctl restart gps-time-pi
systemctl show gps-time-pi -p User        # User= (empty) means root
```

To undo, once the cause is fixed:

```sh
sudo rm /etc/systemd/system/gps-time-pi.service.d/zz-root-rollback.conf
sudo systemctl daemon-reload && sudo systemctl restart gps-time-pi
```

**Level 2: previous release.** Redeploy the previous `gps-time-pi-deploy.tar.gz`. Keep the last good one from `dist/` before upgrading, or rebuild it from the tag: `git checkout v1.4.0-rc.1 && python tools/build_bundles.py`. Then remove the parts the old version doesn't use:

```sh
sudo systemctl disable --now gps-time-pi-chrony-clients.service
sudo rm -f /etc/systemd/system/gps-time-pi-chrony-clients.service
sudo rm -f /etc/polkit-1/rules.d/50-gps-time-pi.rules /etc/systemd/system/gps-time-pi.service.d/zz-root-rollback.conf
sudo systemctl daemon-reload && sudo systemctl restart gps-time-pi
```

The old version ignores `admin-token.sha256` and the `gps-time` user, which can stay. chrony, gpsd and PPS configuration are not touched by either level.

## Important

The current installer is still based on the historical v1.3 deployment model and may use Internet access at install time for Python dependencies/JPL ephemeris. Runtime offline operation is a design goal; a future offline dependency/data bundle remains planned.

The hardware/gpsd/chrony configuration remains installation-specific. Generate and review it with `tools/generate_config.py` before applying it.

To deploy the current `.dev/dashboard.json` intentionally:

```powershell
.\scripts\deploy-to-pi.ps1 -PiHost 192.168.1.50 -PiUser pi -UseDemoLayout
```

Without `-UseDemoLayout`, local demo experiments are not promoted into the deployment archive.
