# Upgrading a station that already runs 1.4: checklist

For a station on a v1.4.0 release candidate (the Pi has run **v1.4.0-rc.6** since 2026-10-04), going to **v1.4.0-rc.8**. For a newly flashed Pi use [`fresh-pi-install.md`](fresh-pi-install.md); for a v1.3 station use [`first-pi-deploy.md`](first-pi-deploy.md).

PowerShell blocks run on Windows, `sh` blocks on the Pi. Set these once per PowerShell window, with your own values. Don't commit them.

```powershell
$PiHost = '<pi address or hostname>'
$PiUser = '<pi user>'
$Pi = "$PiUser@$PiHost"
```

## What the upgrade changes on the station

- `install.sh` **restarts chrony**, as on every run. PPS selection takes a few minutes to come back.
- **One line of `chrony.conf` changes** (new since rc.6): `sourcedir /run/chrony-dhcp` is commented out, so chrony stops taking NTP servers from DHCP and can't poll the station itself. The file as it was is kept as `/etc/chrony/chrony.conf.before-gps-time-pi`. If DHCP was the station's only network fallback, add a `server` or `pool` line afterwards.
- The chrony helper service (`gps-time-pi-chrony-clients`) is restarted and now publishes three reports: `clients`, `ntpdata`, `serverstats`.
- The web service is restarted. Its RAM histories (stability, references, NTP service) start empty.
- New pages: Timing → Stability, Time Scales, References; an NTP service card on Network & Devices; the NMEA offsets side by side on PPS Diagnostics.
- The admin token, `config.json`, the survey and the event history are kept.
- Not changed: gpsd, the PPS setup, the refclock lines, and everything else in `chrony.conf`. Independent `noselect` servers are **not** added unless you ask (step 4).

## 1. Before

- [ ] Note what chrony has selected now, and keep a copy of its configuration.

  ```powershell
  ssh $Pi "chronyc -n sources; chronyc tracking | head -4; sudo cp -a /etc/chrony/chrony.conf ~/chrony.conf.before-rc8"
  ```

## 2. Upgrade

- [ ] In a normal, interactive PowerShell window (not a VS Code task), from the repository folder, with a clean working tree. `git describe` must print exactly `v1.4.0-rc.8`.

  ```powershell
  git fetch --tags
  git checkout v1.4.0-rc.8
  git status --short
  git describe --tags --dirty
  ```

- [ ] Run the deploy. It builds the web UI and the bundle, uploads it, verifies its SHA-256 on the Pi and runs `sudo bash install.sh`.

  ```powershell
  powershell -ExecutionPolicy Bypass -File .\scripts\deploy-to-pi.ps1 -PiHost $PiHost -PiUser $PiUser
  ```

  Expect, among the installer's sections: `Disabled 'sourcedir /run/chrony-dhcp'` (or "nothing changed" if the line wasn't there), `Independent references: none added`, `Installed web UI 1.4.0-rc.8`, `Existing admin token kept`, and a last line `Astronomy: available` or `Astronomy: UNAVAILABLE - <reason>` (note the reason; it doesn't affect timing).

- [ ] If the script stops with `... failed (exit N); deploy stopped.`, nothing after that step ran. Fix what it names and run it again.

- [ ] Go back to the main branch: `git checkout main`.

## 3. Checks

```powershell
ssh $Pi
```

- [ ] The version is `1.4.0-rc.8` and the service is active.

  ```sh
  systemctl is-active gps-time-pi gps-time-pi-chrony-clients
  curl -s localhost/api | python3 -c "import sys,json; print(json.load(sys.stdin)['versions']['app'])"
  ```

- [ ] chrony has selected PPS again (give it a few minutes): a `#*` line for the PPS refclock and `Stratum : 1`.

  ```sh
  chronyc -n sources
  chronyc tracking | head -4
  ```

- [ ] The DHCP line is commented out, and chrony isn't polling the station. The second command prints nothing when all is well.

  ```sh
  grep -n "chrony-dhcp" /etc/chrony/chrony.conf
  for a in $(hostname -I); do chronyc -n sources | grep -F " $a "; done
  ```

- [ ] The helper publishes all three reports.

  ```sh
  sudo ls -l /run/gps-time-pi/
  journalctl -u gps-time-pi-chrony-clients -n 10 --no-pager
  ```

  Expect `chrony-clients.txt`, `chrony-ntpdata.txt` and `chrony-serverstats.txt`, and no "failed" lines. This is the first time `ntpdata` and `serverstats` are read as `_chrony` on a Pi; if one is missing, the journal line says what chronyd answered, and the page that needs it reads UNKNOWN. Timing isn't affected.

- [ ] The new endpoints answer.

  ```sh
  curl -s localhost/api/stability   | python3 -c "import sys,json; d=json.load(sys.stdin); print('stability:', d['available'], d['series']['seconds']['samples'], 'samples,', d['series']['seconds']['gaps'], 'gaps')"
  curl -s localhost/api/timescales  | python3 -c "import sys,json; d=json.load(sys.stdin); l=d['leap_seconds']; print('TAI-UTC:', d['tai_utc_s']['value'], '| leap table:', l['source'], l['status'], l['expires_utc'])"
  curl -s localhost/api/references  | python3 -c "import sys,json; d=json.load(sys.stdin); print('references:', d['verdict']['code'], '| delay available:', d['delay_available'])"
  curl -s localhost/api/ntp-service | python3 -c "import sys,json; d=json.load(sys.stdin); print('ntp service:', d['state'], d['ntp'] and d['ntp']['received']['value'])"
  ```

  - Stability: `True` after a few seconds, with the sample count rising by about one a second and few or no gaps.
  - Time scales: `37`, source `file`, status `OK` with an expiry date. Source `builtin` means tzdata's `leap-seconds.list` isn't where the code looks; note it.
  - References: `AGREE`, `ONE_REFERENCE`, `NONE_CONFIGURED` or `NONE_REACHABLE` are all valid answers; which one depends on the servers chrony polls.
  - NTP service: a state other than `UNKNOWN` and a packet count.

- [ ] In a browser, `http://<station>/app/`: the footer shows `1.4.0-rc.8`, and Timing → Stability, Time Scales and References load.

## 4. Optional: independent `noselect` references

Only if you want chrony to poll NIST and USNO for comparison (it changes chrony's configuration and contacts those servers). The deploy script can't pass this option, so run the installer by hand in the folder the deploy left on the Pi:

```sh
cd ~/gps-time-deploy/gps-time && sudo GTP_INDEPENDENT_REFS=1 bash install.sh
```

Remove them again with `GTP_INDEPENDENT_REFS=0`. Details: `../architecture/independent-references.md`.

## 5. The soak run before v1.4.0

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
- Worth recording at the end, for the v1.4.0 notes: the key-point table, "Seconds without a sample", the share of time PPS was selected, any PPS outage events, the references outcome, and `journalctl -u gps-time-pi -u gps-time-pi-chrony-clients --since "3 days ago" -p warning --no-pager`.

## Rollback

- Previous release: check out `v1.4.0-rc.6` and run the same deploy command. The rc.6 installer doesn't touch the DHCP line, so it stays commented out. The helper service stays installed, which rc.6 ignores.
- chrony configuration: `sudo cp -a ~/chrony.conf.before-rc8 /etc/chrony/chrony.conf && sudo systemctl restart chrony` (or restore `/etc/chrony/chrony.conf.before-gps-time-pi`).
- Root-service rollback and other levels: `../development/raspberry-pi-deploy.md` → "Rollback".
