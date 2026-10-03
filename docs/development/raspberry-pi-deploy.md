# Build and deploy to Raspberry Pi

## Build archives

From Windows/VS Code:

```powershell
python tools\build_bundles.py
```

Outputs:

- `dist/gps-time-development.zip` — full development/repo archive
- `dist/gps-time-pi-deploy.tar.gz` — deployment-oriented archive
- `dist/SHA256SUMS.txt`

Both archives contain `gps_time_pi/VERSION`, the `git describe` of the checkout you built from (for example `1.4.0-rc.1`, or `1.4.0-rc.1-3-gabc1234-dirty`). The station has no `.git`, so `/api` and the UI footer read their version from this file. To deploy a release, check out its tag first (`git checkout v1.4.0-rc.1`). Without a reachable `v*` tag, the file is left out and the station reports `unknown`.

## One-command-ish deployment

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-to-pi.ps1 -PiHost 192.168.1.50 -PiUser pi
```

This builds, uploads with `scp`, extracts over SSH and runs `sudo bash install.sh`.

Bash equivalent:

```bash
./scripts/deploy-to-pi.sh 192.168.1.50 pi
```

## Admin token and service user

`install.sh` creates the unprivileged service user `gps-time` and installs the polkit rule `/etc/polkit-1/rules.d/50-gps-time-pi.rules`. On a first install it also creates an admin token and **shows it once, on the terminal only**; keep it. Settings changes and service actions in the web UI need it. Without a terminal (non-interactive ssh, a CI log), no token is created and admin stays disabled until you run the command below on the station.

- Create or rotate: `sudo python3 -m gps_time_pi.admin_token --tty-only --path /opt/gps-time-pi/admin-token.sha256 --group gps-time` (run in `/opt/gps-time-pi`).
- Failed token attempts are in the journal: `journalctl -u gps-time-pi | grep "admin token"`.
- Disable admin: delete `/opt/gps-time-pi/admin-token.sha256`.
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

**Level 2: previous release.** Redeploy the previous `gps-time-pi-deploy.tar.gz`. Keep the last good one from `dist/` before upgrading. Then remove the parts the old version doesn't use:

```sh
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
