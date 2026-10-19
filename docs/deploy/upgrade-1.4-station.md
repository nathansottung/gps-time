# Upgrading a station that already runs 1.4: checklist

For a station on a v1.4.0 release candidate, going to **v1.4.0-rc.11**. The Pi runs **v1.4.0-rc.10** (since 2026-10-19 18:10 UTC). The steps are the same from rc.8, rc.9 or rc.10. For a newly flashed Pi use [`fresh-pi-install.md`](fresh-pi-install.md); for a v1.3 station use [`first-pi-deploy.md`](first-pi-deploy.md).

PowerShell blocks run on Windows, `sh` blocks on the Pi. Set these once per PowerShell window, with your own values. Don't commit them.

```powershell
$PiHost = '<pi address or hostname>'
$PiUser = '<pi user>'
$Pi = "$PiUser@$PiHost"
```

## What the upgrade changes on the station

**New in rc.11** (code only: no change to the installer, the services, chrony's configuration or the files the station writes):

- `/api/history` reads chrony's tracking log by named column (review GPS-003); `/api` adds chrony's error bound `max_error_bound_s` (GPS-007). Both UIs label chrony's System time as the remaining correction and show the bound instead of "± root dispersion". The legacy history chart's band is now chrony's offset SD.
- `/app/`: station actions and survey reset (Administration), decoded throttle flags with an under-voltage warning, almanac date navigation with day and night bars, the sky map and object lookup (the sky target is per request now), survey convergence and ingest counters, chrony tracking detail, the offset history with band and symmetric-log axis, the red night theme and show/hide modules (Configure).
- The legacy almanac sky map's E and W labels are on the correct sides.

**New in rc.10:**

- The legacy dashboard's Sun & daylight widget shows sunset as large as sunrise.
- `/app/` has a screenshot mode: a header toggle (Alt+Shift+S) that hides coordinates, heights, NTP client addresses and the hostname on screen. Display only; remembered in each browser.

**From rc.8, also everything rc.9 brought:**

- `install.sh` **restarts chrony**, as on every run. PPS selection takes a few minutes to come back.
- `chrony.conf` is not changed further (the DHCP line was commented out by rc.7 or rc.8; the installer says "nothing changed").
- The web service is restarted. Its RAM histories (stability, references, NTP service, PPS counters) start empty.
- **New files written by the station** in `/opt/gps-time-pi/`:
  - `oscillator-log.csv`: the SoC temperature with chrony's frequency, 10-minute bins appended once an hour (capped at 4 MB).
  - `evidence/`: one file per PPS outage (event, 10 s timeline, chrony lines ±5 min), only when an outage happens (capped at 20 MiB).
- **Log flush:** the hourly flush appends only new lines to `/var/log/chrony/station-tracking.txt` and caps the RAM log (8 MiB) and the SD copy (16 MiB). The old full copy `/var/log/chrony/tracking.log` is no longer written; it and its rotated copies age out under logrotate.
- **PPS reads** run on their own thread; the PPS page shows missed and unread pulses and the station's poll statistics.
- The almanac is cached (the browser's round trip should no longer climb to seconds while the legacy dashboard is open).
- The admin token, `config.json`, the survey and the event history are kept.
- Not changed: gpsd, the PPS setup, the refclock lines, and everything else in `chrony.conf`. Independent `noselect` servers are **not** added unless you ask (step 4).

## 1. Before

- [ ] Keep a copy of chrony's configuration and of the RAM log: the restart is fine for both, but the RAM log is your only copy of the last weeks' tracking data until the new flush has written its own.

  ```powershell
  ssh -t $Pi "chronyc -n sources; chronyc tracking | head -4; sudo cp -a /etc/chrony/chrony.conf ~/chrony.conf.before-rc11"
  scp "${Pi}:/run/chrony-log/tracking.log" "$HOME\gps-time-logs\tracking-before-rc11.log"
  ```

## 2. Upgrade

- [ ] In a normal, interactive PowerShell window (not a VS Code task), from the repository folder, with a clean working tree. `git describe` must print exactly `v1.4.0-rc.11`.

  ```powershell
  git fetch --tags
  git checkout v1.4.0-rc.11
  git status --short
  git describe --tags --dirty
  ```

- [ ] Run the deploy. It builds the web UI and the bundle, uploads it, verifies its SHA-256 on the Pi and runs `sudo bash install.sh`.

  ```powershell
  powershell -ExecutionPolicy Bypass -File .\scripts\deploy-to-pi.ps1 -PiHost $PiHost -PiUser $PiUser
  ```

  Expect, among the installer's sections: "chrony is not using NTP servers from DHCP ... nothing changed", `Independent references: none added` (or "kept as it is"), `Installed web UI 1.4.0-rc.11`, `Existing admin token kept`, and a last line `Astronomy: available` or `Astronomy: UNAVAILABLE - <reason>`.

- [ ] If the script stops with `... failed (exit N); deploy stopped.`, nothing after that step ran. Fix what it names and run it again.

- [ ] Go back to the main branch: `git checkout main`.

## 3. Checks

```powershell
ssh $Pi
```

- [ ] The version is `1.4.0-rc.11` and the services are active.

  ```sh
  systemctl is-active gps-time-pi gps-time-pi-chrony-clients
  curl -s localhost/api | python3 -c "import sys,json; print(json.load(sys.stdin)['versions']['app'])"
  ```

- [ ] chrony has selected PPS again (give it a few minutes): a `#*` line for the PPS refclock and `Stratum : 1`.

  ```sh
  chronyc -n sources
  chronyc tracking | head -4
  ```

- [ ] The PPS reader and its counters. Run it twice a minute apart: polls rise by about 60, late polls stay at or near 0.

  ```sh
  curl -s localhost/api/timing-chain | python3 -c "import sys,json; p=json.load(sys.stdin)['pps']; v=lambda x: x and x.get('value'); print('missed', v(p.get('missed_pulses')), '| unread', v(p.get('unread_pulses')), '| poller', p.get('poller'))"
  ```

- [ ] The log flush. After the first hourly run (or start it now with `sudo systemctl start gps-time-pi-logflush.service`), the station reports the new SD copy:

  ```sh
  curl -s localhost/api/system | python3 -c "import sys,json; print(json.load(sys.stdin)['ramlog'])"
  ```

  Expect `sd_copy` ending in `station-tracking.txt` and a small `flushed_age_s`. Before the first flush it may still name the old `tracking.log`.

- [ ] The new endpoints answer.

  ```sh
  curl -s localhost/api/oscillator | python3 -c "import sys,json; d=json.load(sys.stdin); print('oscillator:', d['available'], d['reason'] or len(d['bins']), d['storage']['bytes'], d['problems'])"
  curl -s localhost/api/evidence   | python3 -c "import sys,json; d=json.load(sys.stdin); print('evidence files:', len(d['files']), d['total_bytes'], d['problems'])"
  curl -s -o /dev/null -w "ping %{time_total}s\n" "localhost/api/ping?n=1"
  ```

  - Oscillator: `False` with "No 10-minute bin..." for the first ten minutes, then `True`. No problems listed.
  - Evidence: `0` files until an outage happens.
  - Ping: a few milliseconds.

- [ ] In a browser, `http://<station>/app/`: the footer shows `1.4.0-rc.11`; Timing → Oscillator loads; Network & Devices → Browser Connection Test shows a round trip of milliseconds, not seconds, also with the legacy dashboard open in another tab.

- [ ] An outage event at the service start, "PPS NOT USED BY CHRONY" with healthy pulses, is expected: the installer restarts chrony and PPS selection takes a moment to return (seen on rc.10). Any other event is real.

- [ ] rc.11: `/app/` Overview shows "Remaining correction (chrony)" with "bound ≤ …" beneath; Timing → Overview shows the offset history with its band; Administration shows the throttle table and Station actions (don't press them for the check).

- [ ] The two UI changes (rc.10):
  - Legacy dashboard (`http://<station>/`), Sun & daylight: each day shows a sunrise and a sunset figure of the same size.
  - `/app/`: press Alt+Shift+S (or click **Screenshot off · display only** in the header). The hostname, the coordinates and heights (GNSS & Site → Position and Geodesy) and the client addresses (Network & Devices) turn into blurred masks. Reload: it stays on. Press it again to turn it off.

## 4. Optional: independent `noselect` references

Only if you want chrony to poll NIST and USNO for comparison (it changes chrony's configuration and contacts those servers). The deploy script can't pass this option, so run the installer by hand in the folder the deploy left on the Pi:

```sh
cd ~/gps-time-deploy/gps-time && sudo GTP_INDEPENDENT_REFS=1 bash install.sh
```

Remove them again with `GTP_INDEPENDENT_REFS=0`. Details: `../architecture/independent-references.md`.

## 5. The soak run before v1.4.0

- At the end, run the read-only check from Windows (HTTP GETs only; it changes nothing): `python tools/soak_check.py http://<station> --expect 1.4.0-rc.11`. It prints each criterion and `CLEAN` or `NOT CLEAN` (exit 0 / 1; 2 if the station can't be read). The criteria are in its docstring and in the change log entry for #95.
- The stability history is kept in RAM and starts again whenever the web service restarts. For the longest averaging times, don't restart `gps-time-pi` or reboot during the run.
- What appears when, counted from the service start:

  | After | On Timing → Stability |
  |---|---|
  | a few seconds | 1 s |
  | 50 minutes | up to 1000 s |
  | 3 hours | the first minute-based point (1 h) |
  | 3 days | ADEV at 1 day |
  | 4 days | MDEV and TDEV at 1 day |

  So a 3-day run ends just as the 1-day ADEV point appears, and without its MDEV or TDEV.
- Worth recording at the end, for the v1.4.0 notes: the key-point table, missed and unread pulses with the poll statistics (this settles whether the rc.8 run's 9 % was real), any PPS outage events and their evidence files, the references outcome, the oscillator slope if there is one, and `journalctl -u gps-time-pi -u gps-time-pi-chrony-clients --since "3 days ago" -p warning --no-pager`.

## What the first soak run found (2026-10-04 to 2026-10-19)

Fourteen days on rc.8 without a restart, with real PPS/GNSS outages on 2026-10-17 and a 56-minute holdover that ended about 1.7 µs off. Details and numbers: `../development/raspberry-pi-deploy.md` → "Soak run of v1.4.0-rc.8". From rc.9 the station keeps each outage's evidence on the SD card itself.

## Rollback

- Previous release: check out `v1.4.0-rc.10` and run the same deploy command (rc.11 changed no installer or service). Earlier: `v1.4.0-rc.9` the same way. To go back to `v1.4.0-rc.8`: same command; rc.8's flush copies the whole RAM log again, and the files rc.9 added (`oscillator-log.csv`, `evidence/`, `/var/log/chrony/station-tracking.txt`) stay and are ignored.
- chrony configuration: `sudo cp -a ~/chrony.conf.before-rc11 /etc/chrony/chrony.conf && sudo systemctl restart chrony` (or restore `/etc/chrony/chrony.conf.before-gps-time-pi`).
- Root-service rollback and other levels: `../development/raspberry-pi-deploy.md` → "Rollback".
