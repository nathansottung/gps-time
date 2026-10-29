# Build and deploy to Raspberry Pi

Step-by-step checklists: [`../deploy/fresh-pi-install.md`](../deploy/fresh-pi-install.md) for a newly flashed Pi, [`../deploy/first-pi-deploy.md`](../deploy/first-pi-deploy.md) for upgrading a v1.3 station, and [`../deploy/upgrade-1.4-station.md`](../deploy/upgrade-1.4-station.md) for a station that already runs 1.4.

`install.sh` starts with a preflight: it stops, before changing anything, if it isn't run as root, chrony isn't installed, or the `_chrony` or `video` group is missing. It warns if gpsd or polkit is missing. It doesn't install chrony, gpsd or PPS, and it doesn't configure them beyond three `chrony.conf` edits: `log tracking`, `logdir /run/chrony-log`, and disabling DHCP-provided NTP servers (below). Only when asked, it also adds a file of `noselect` servers ("Independent references", below).

## Deployment record

| Date | Version | Result |
|---|---|---|
| 2026-10-04 | v1.4.0-rc.6 | First deploy of the 1.4 line to the Pi. chrony selected the PPS refclock; stratum 1; system clock offset about 300 ns (owner's report). |
| 2026-10-04 to 2026-10-19 | v1.4.0-rc.8 | Soak run, 14 days 20 h without a restart. Real PPS/GNSS outages on 2026-10-17 (below), so **v1.4.0 was not tagged**. Otherwise GPS was chrony's reference throughout. |
| 2026-10-19 | v1.4.0-rc.10 | Deployed (service start 18:10 UTC). Read-only check after 2 h 17 min (below): four outage events, three of them real loss of PPS with weak GNSS signal. Replaced by rc.11 for the soak, which carries the chrony-history fix (#93). |
| 2026-10-19 to 2026-10-26 | v1.4.0-rc.11 | Soak run: service start 21:20:16 UTC, read-only check after 6 days 17 h (below). **CLEAN**: no outages except the installer's at the start, 2 missed pulses. **v1.4.0 tagged** on the same commit (`cbd891c`). |
| 2026-10-26 to 2026-10-29 | v1.5.0-rc.1 | Soak run: service start 18:16:55 UTC, read-only check after 3.01 days (below). **NOT CLEAN**: four PPS outages (8,596 s in all) and 8,906 missed pulses. **v1.5.0 not tagged**; v1.6.0-rc.1 not released. The owner decides. |

Found on that build and fixed since:

- "Astronomy data unavailable." with no reason: the API, the legacy widget and the installer's self-check now state it (#43, #51). The Pi's own reason is still to be read from `/api/almanac`.
- "Client list unavailable": the unprivileged service can't use chronyd's socket; a helper running as `_chrony` publishes the list (#44).
- Empty satellite C/N₀ bars in the legacy dashboard: a CSS `display` rule (#50).

Followed from the owner's list after it: chrony polling the station's own address is detected (#48) and prevented by the installer (#52); a measured NMEA offset recommendation (#49).

### Soak run of v1.4.0-rc.8 (read-only check, 2026-10-19)

State at the check: GPS selected, stratum 1, system time +65 ns, RMS offset 244 ns, root dispersion 13.4 µs, frequency 10.345 ppm fast, skew 0.008 ppm; CPU 53.5 °C, never throttled; 10 of 10 independent references agree within 50 ms; leap-second table valid until 2027-06-28. Stability (history since 2026-10-05 03:38 UTC): ADEV 1.70 × 10⁻⁶ at 1 s, 2.15 × 10⁻⁸ at 100 s, 2.46 × 10⁻¹¹ at 1 day (the 1-day value includes the outages, and its interval rests on an assumed noise type).

**Outages on 2026-10-17, 19:04 to 20:35 UTC.** The owner confirms they were real. The station recorded ten events in that window, about 71 minutes in all: five PPS PATH ANOMALY, four PPS AND GNSS TELEMETRY UNAVAILABLE, and one GNSS RECEPTION ANOMALY lasting 3365 s (19:39:29 to 20:35:34). The classifications are inferred and name a boundary in the signal path, not a cause. Nothing in the system journal for that window (kernel, gpsd, chrony) mentions them.

**Holdover result: 56 minutes, about 1.7 µs.** chrony's tracking log (copied off the station; real station data, kept outside the repository) shows how the clock behaved:

| Gap in chrony updates (UTC) | Length | chrony's first offset afterwards |
|---|---|---|
| 19:03:35 to 19:07:03 | 208 s | +0.07 µs |
| 19:15:20 to 19:18:16 | 176 s | +0.08 µs |
| 19:29:28 to 19:35:05 | 337 s | −0.42 µs |
| 19:39:37 to 20:35:40 | 3363 s (56 min) | **+1.68 µs** |

- chrony did not fail over to a network source. It wrote no tracking entries while it had no usable PPS samples, coasting on its last GPS-disciplined frequency, and GPS was the reference again at the first entry after each gap.
- After the 56-minute gap the first measured offset was +1.68 µs, and −0.16 µs one update (16 s) later. So the free-running clock drifted by roughly 1.7 µs in 56 minutes: about 5 × 10⁻¹⁰ average fractional frequency error. That is one event on one board at room temperature (`observed` from chrony's log; the rate is `calculated`), not a holdover specification.
- Because chrony was coasting rather than following another source, the banner's NETWORK FAILOVER states didn't apply; the station's events are the record of the outage.

Also seen and not yet explained: the PPS monitor counted 112,588 missed pulses over the run (about 9 % of all seconds), and the stability history had 1,875 minutes without their usual sample, which is the same amount of time. The Oct 17 events account for about 4,300 s of it. This may be an artifact of how the station polls, separate from the real outages; rc.9 separates pulses the kernel never counted from pulses the station merely didn't read individually (STATUS "rc.9").

**Log flushing on rc.8 works** (hourly timer, every run successful; the SD copy was 15 minutes old at the check), but it copies the whole RAM log to the SD card every hour (10 MB at the check, about 240 MB a day and growing), and Debian's weekly logrotate keeps rotated full copies. Fixed in rc.9 (#72): append-only, with caps ("chrony's tracking log" below).

Not recorded: which checklist was followed, and the result of each individual check (polkit, admin token, vcgencmd values). Nothing merged after rc.6 has run on a Pi yet; v1.4.0-rc.8 is the next deploy.

### The current station (owner, 2026-10-19)

- **It is a development unit,** not a reference installation: a Raspberry Pi 4 with the Uputronics MAX-M8Q board (`uputronics` profile) and its current antenna, where it is now.
- **Its weak C/N₀ (best about 25 dB-Hz) is an antenna and site limit.** That is the owner's assessment of this installation. The station itself only observes the signal levels and the outages; it does not name their cause, and its event classifications stay `inferred` boundaries. A well-sited active antenna with a clear sky usually reports best C/N₀ in the 40s to about 50 dB-Hz.
- What this means for the soak runs: PPS outages on this unit can come from the antenna and site, so an outage alone doesn't show a software fault. The v1.4.0 criteria (#95) still count every outage except the installer's; a run that fails only on outages is reported to the owner rather than tagged. Outage detection is not weakened (owner, 2026-10-19).
- The next hardware tier, a dual-band u-blox receiver, is scoped in `../hardware/zed-f9-dual-band.md`.

### First hours of v1.4.0-rc.10 (read-only check, 2026-10-19 20:27 UTC)

Read over HTTP and SSH, nothing changed. The service started at 18:10:03 UTC (no restarts); the Pi has been up since 2026-10-04. At the check: GPS/PPS selected, stratum 1, the PPS interval over the last 600 pulses 1.000 000 s ± 1.3 µs (kernel timestamps).

- **Four outage events in 2 h 17 min.** The first, 18:10:07 for 32 s, PPS NOT USED BY CHRONY: the installer restarts chrony and PPS selection takes a moment to return; pulses were healthy throughout. Expected on every upgrade. The other three were real loss of kernel PPS: 19:35:51 (41 s, GNSS RECEPTION ANOMALY), 19:37:35 (231 s, PPS PATH ANOMALY), 19:53:11 (493 s, PPS AND GNSS TELEMETRY UNAVAILABLE). At their start the receiver used 0 satellites with the best C/N₀ 20–28 dB-Hz. The classifications are the station's (`inferred`) and name a boundary in the signal path, not a cause.
- **Weak GNSS signal at the check:** 8 of 23 satellites used, best C/N₀ 25 dB-Hz, median of those used 15 dB-Hz (`observed`). The 2026-10-17 events on rc.8 also started with 0 used and C/N₀ about 22–23 dB-Hz. **Owner, 2026-10-19:** the weak signal is a limit of this antenna and site, not of the software (see "The current station" below).
- **Missed pulses are real absences, not a polling artifact:** 812 missed (9.9 % of 8199 reads), 0 unread, 0 late reads, longest gap between reads 1.049 s. The station read every second and the kernel's own sequence number skipped those pulses. The three real outages cover 765 s of the 812. This answers the question rc.9's poller was built for (the rc.8 run's 9 %), for this window; whether rc.8's 14-day count had the same make-up is not known.
- **Browser round trip is fixed:** `/api/ping` median 16 ms (max 32 ms) from the LAN, 24 ms (max 60 ms) while `/api/almanac` was requested continuously. On rc.8 it was seconds.
- **Stability over this short window is dominated by the outages:** ADEV 2.1 × 10⁻⁵ at 1 s, 1.1 × 10⁻⁵ at 10 s, 1.4 × 10⁻⁶ at 100 s, 1.7 × 10⁻⁷ at 1000 s, with 812 gaps in 7387 samples (PPS selected 99.6 %). rc.8's 1 s value over two weeks was 1.7 × 10⁻⁶. Why the short window is this much higher is not established.
- No warnings from the service in the journal. Network sources sit 4–8 ms from the station's clock, as on rc.8.

### Soak run of v1.4.0-rc.11 (read-only check, 2026-10-26 14:28 UTC)

Read over HTTP (`python tools/soak_check.py http://<station> --expect 1.4.0-rc.11`, GETs only) and read-only SSH; nothing on the station changed. Preconditions: version file 1.4.0-rc.11; `gps-time-pi` active since 2026-10-19 21:20:16 UTC with `NRestarts=0`; the Pi up since 2026-10-04 (no reboot). The criteria were fixed before the run (change log, #95). Result: **CLEAN** (exit 0), so v1.4.0 was tagged on the rc.11 commit `cbd891c`.

| Criterion | The tool's line |
|---|---|
| version | 1.4.0-rc.11 (expected 1.4.0-rc.11) |
| runtime | 580062 PPS reads = 6.71 days since the service started (need 3) |
| timing | status GPS_PPS; stratum 1; reference 47505300 (GPS) |
| outages | open: False; since the service started: 0 (+1 installer restart); evidence files: 5 |
| pulses | missed 2, unread 0 (3.45e-06 of reads); late reads 0; longest gap 1.07 s |
| rtt | idle median 19.4 ms, max 40.0 ms; under /api/almanac load median 30.8 ms, max 58.9 ms |
| stability | ADEV 1 s 1.53e-06, 10 s 1.80e-07, 100 s 2.03e-08, 1000 s 2.12e-09, 1 day 2.08e-11; seconds series 14398 samples, 2 gaps, PPS selected 1.0 |

- **The one event:** 2026-10-19 21:20:18 to 21:20:50 UTC, 32 s, PPS NOT USED BY CHRONY (`inferred`, boundary: chrony source selection), pulses healthy throughout, GNSS healthy, a network source selected meanwhile; chrony's largest remaining correction 38 ns. This is the installer's chrony restart, as on rc.10. Of the five evidence files, one is this event's; the other four are rc.10's four events on 2026-10-19 (18:10 to 20:01 UTC), before this service start.
- **PPS at the check** (`/api/timing-chain`): state SELECTED, pulse health HEALTHY, 580,079 polls with 0 late (largest gap 1.07 s), 0 sequence resets, 3,356 consecutive pulses. Interval over the last 600 pulses 1.000 000 s ± 1.3 µs (kernel timestamps, CLOCK_REALTIME).
- **GNSS at the check:** 3D fix, 9 of 23 satellites used, best C/N₀ 25 dB-Hz, median of those used 18 dB-Hz, TDOP 2.82 (`observed`). The signal is as weak as at the rc.10 check; this time it held for the whole run.
- **chrony** (`chronyc -n tracking`): reference GPS, stratum 1, system time 262 ns slow of NTP time, last offset −198 ns, RMS offset 202 ns, frequency 10.509 ppm fast, residual 0.000 ppm, skew 0.009 ppm, root dispersion 9.5 µs, update interval 16 s, leap status normal.
- **Stability** (`/api/stability`, history since the service start, no resets): ADEV 1.53 × 10⁻⁶ at 1 s (68 % interval 1.52–1.54 × 10⁻⁶, flicker PM), 1.80 × 10⁻⁷ at 10 s, 2.03 × 10⁻⁸ at 100 s, 2.12 × 10⁻⁹ at 1000 s, 2.08 × 10⁻¹¹ at 1 day. The 1000 s and 1-day intervals rest on an assumed noise type. Minute series: 9,667 samples over 6.7 days, 0 gaps, PPS selected 99.99 % (the start-up event). Close to rc.8's two-week values (1.70 × 10⁻⁶ at 1 s, 2.46 × 10⁻¹¹ at 1 day), which included outages.
- **Also:** independent references AGREE, 10 of 10 within 50 ms (`calculated`); no warnings from `gps-time-pi` or `gps-time-pi-chrony-clients` in the journal since the service start; `vcgencmd get_throttled` 0x0.
- What this shows: on this unit, with this antenna and site, rc.11 ran a week without losing PPS. It doesn't show that the outages seen on rc.8 and rc.10 won't come back; the station keeps counting them.

### Soak run of v1.5.0-rc.1 (read-only check, 2026-10-29 18:30 UTC)

Read over HTTP (`python tools/soak_check.py http://<station> --expect 1.5.0-rc.1`, GETs only, run once) and read-only SSH; nothing on the station changed. Preconditions: version file 1.5.0-rc.1; `gps-time-pi` active since 2026-10-26 18:16:55 UTC with `NRestarts=0`; the Pi up since 2026-10-04 (no reboot). The criteria are the ones fixed before the v1.4.0 soak (change log, #95), unchanged. Result: **NOT CLEAN** (exit 1) on two criteria, outages and pulses. **v1.5.0 was not tagged**, and v1.6.0-rc.1 was not released (it waits on v1.5.0). The owner decides what comes next.

| Criterion | | The tool's line |
|---|---|---|
| version | OK | 1.5.0-rc.1 (expected 1.5.0-rc.1) |
| runtime | OK | 260028 PPS reads = 3.01 days since the service started (need 3) |
| timing | OK | status GPS_PPS; stratum 1; reference 47505300 (GPS) |
| outages | **NO** | open: False; since the service started: 4 (+0 installer restart); evidence files: 9 |
| pulses | **NO** | missed 8906, unread 0 (3.43e-02 of reads); late reads 0; longest gap 1.237 s |
| rtt | OK | idle median 16.1 ms, max 31.7 ms; under /api/almanac load median 23.9 ms, max 83.3 ms |
| stability | OK | ADEV 1 s 1.53e-06, 10 s 1.71e-07, 100 s 1.85e-08, 1000 s 1.96e-09, 1 day 7.00e-10; seconds series 14400 samples, 0 gaps, PPS selected 1.0 |

The record lines the tool prints after the result (not criteria; no effect on it):

```
[REC] sdr: UNKNOWN: no SDR status from this station (/api/sdr: before v1.6.0, or systemctl unreadable)
[REC] cpu: load averages 0.45 / 0.28 / 0.21 (1, 5, 15 min)
[REC] usb: RTL-SDRs UNKNOWN; throttled flags 0x0 (none now or since boot)
[REC] temperature: SoC 55.5 °C now
[REC] pps jitter: chrony PPS std dev 370 ns; RMS offset 246 ns; ADEV(1 s) 1.53e-06; TDEV(1 s) 881 ns
```

The SDR line is UNKNOWN as expected: v1.5.0-rc.1 has no `/api/sdr`.

**The four outage events** (`/api/timing-chain`; all PPS_OUTAGE, all closed). The classifications are the station's, `inferred`, and name a boundary in the signal path, not a cause:

| Start (UTC) | Duration | Classification (initial) | Confidence | At the start | During |
|---|---|---|---|---|---|
| 2026-10-26 19:07:14 | 651 s | PPS PATH ANOMALY (initially GNSS RECEPTION ANOMALY) | moderate | GNSS unhealthy, 0 satellites used, best C/N₀ 21 dB-Hz | 0–4 used; chrony's largest remaining correction 17 ns |
| 2026-10-26 23:41:52 | 46 s | PPS PATH ANOMALY (initially PPS AND GNSS TELEMETRY UNAVAILABLE) | moderate | GNSS health unknown, 3 used, best 31 dB-Hz | 3–4 used; 0 ns |
| 2026-10-27 19:04:38 | 6,814 s (1 h 54 min) | GNSS RECEPTION ANOMALY | low | GNSS unhealthy, 0 used, best 28 dB-Hz | 0–4 used; 71 ns |
| 2026-10-28 20:01:48 | 1,085 s | PPS PATH ANOMALY | moderate | GNSS healthy, 6 used, best 30 dB-Hz | 4–6 used, GNSS healthy throughout; 43 ns |

- No fallback source was used in any of them: chrony kept GPS as its reference and coasted, and accepted and selected PPS again as soon as pulses returned (0 s). The largest remaining correction chrony reported during any of them was 71 ns (chrony's estimate, not an independent error measurement).
- The first event started 50 minutes after the service start and is not the installer's: the tool counts no installer restart this time. The 9 evidence files are these four events' and the five from rc.10 and rc.11.
- The four events last 8,596 s in all; the station counts 8,906 missed pulses (pulses the kernel never counted), with 0 unread and 0 late reads. How the other 310 are spread over the run isn't in the record.
- Three of the four started between 19:04 and 20:02 UTC, as did the rc.8 events on 2026-10-17 (19:04–20:35) and rc.10's on 2026-10-19 (19:35–19:53). That is an observation from five dates; the evidence doesn't establish why.

**At the check:**
- **PPS:** state SELECTED, pulse health HEALTHY, 260,046 polls with 0 late (largest gap 1.237 s), 0 sequence resets, 55,655 consecutive pulses; interval over the last 600 pulses 1.000 000 s ± 1.3 µs (kernel timestamps, CLOCK_REALTIME).
- **GNSS:** 3D fix, 10 of 21 satellites used, best C/N₀ 34 dB-Hz, median of those used 21 dB-Hz, TDOP 1.32 (`observed`).
- **chrony** (`chronyc -n tracking`): reference GPS, stratum 1, system time 77 ns fast of NTP time, last offset +90 ns, RMS offset 235 ns, frequency 10.111 ppm fast, residual 0.000 ppm, skew 0.004 ppm, root dispersion 20.2 µs, update interval 16 s, leap status normal.
- **Stability** (`/api/stability`, since the service start, no resets): ADEV 1.53 × 10⁻⁶ at 1 s (68 % interval 1.51–1.54 × 10⁻⁶, white PM), 1.71 × 10⁻⁷ at 10 s, 1.85 × 10⁻⁸ at 100 s, 1.96 × 10⁻⁹ at 1000 s (noise type assumed), 7.00 × 10⁻¹⁰ at 1 day (no interval). The seconds series (last 4 h) has no gaps; the minute series has 150 gaps in 4,184 samples, PPS selected 99.95 %. The 1-day value includes the outages and is far above rc.11's 2.08 × 10⁻¹¹.
- **Also:** independent references AGREE, 10 of 10 within 50 ms (`calculated`); `vcgencmd get_throttled` 0x0.
- What this shows: the timing core recovered from each loss of PPS without leaving GPS, and everything apart from the outages met the criteria. Under the owner's rule outages fail the run; they are reported, not explained away, and detection is not weakened.

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

## chrony's tracking log: RAM, the SD copy, and the caps (rc.9)

chrony writes its tracking log to RAM (`/run/chrony-log/tracking.log`). `scripts/logsync.sh`, run as root by `gps-time-pi-logflush.timer` every hour and at shutdown:

- **appends only the lines written since the last flush** to `/var/log/chrony/station-tracking.txt` (a few tens of kB an hour). Before rc.9 it copied the whole RAM log every hour: about 240 MB a day at 10 MB.
- **RAM cap 8 MiB:** past it the log becomes `tracking.log.1` (replacing the previous one) and chrony reopens a new one (`chronyc cyclelogs`). RAM use stays under 16 MiB. The History page reads both.
- **SD cap 16 MiB:** past it the SD copy becomes `station-tracking.txt.prev`. SD use stays under 32 MiB.
- The SD copy is not named `*.log`, so Debian's chrony logrotate rule doesn't rotate it and keeps no rotated full copies.
- **At boot** the newest part of the SD copy (4 MiB) goes back into RAM, so the History page has data again; those lines are not appended a second time.
- The pre-rc.9 full copy `/var/log/chrony/tracking.log` and its rotated versions are no longer written. They are left in place and age out under logrotate within about five weeks; the first boot after the upgrade restores from them if there is no new copy yet.
- To keep evidence before a restart, copy `/run/chrony-log/tracking.log` (and `.1`) off the station; they are readable without sudo.

## Outage evidence (rc.9)

For every PPS outage the station keeps one file in `/opt/gps-time-pi/evidence/` (the event, a 10 s timeline and chrony's tracking lines from 5 minutes before to 5 minutes after), capped at 20 MiB in all. It survives a reboot, unlike the RAM log. Copy the directory off the station to keep it; Timing → PPS Events lists the files.

## Oscillator log

The station logs the SoC temperature with chrony's frequency, in 10-minute bins appended to `/opt/gps-time-pi/oscillator-log.csv` once an hour (about six short lines an hour; capped at 4 MB). It is the data for the trained oscillator profile and needs nothing from you. The file is bound to the board by a hash of its serial number: if the SD card moves to another Pi, the old file is set aside rather than mixed in. Copy it off the station like the chrony log if you want to keep it.

## Satellite orbital elements (optional)

Sun & Astronomy → Earth Shadow needs nothing. Sun & Astronomy → Satellites needs orbital elements (TLEs), which come from the Internet and go out of date in days. The web service never fetches them; run this on the station when you want them refreshed:

```sh
cd /opt/gps-time-pi
sudo -u gps-time venv/bin/python -m gps_time_pi.tle_fetch --group stations
sudo -u gps-time venv/bin/python -m gps_time_pi.tle_fetch --list
```

- `stations` is a small group that holds the ISS. Other CelesTrak groups work the same way (`visual`, `starlink`, …); a large group is a large file.
- Without Internet on the station, copy a TLE file over and import it: `... -m gps_time_pi.tle_fetch --file my.tle --name mine`.
- The cache is `/opt/gps-time-pi/tle/`. It is written only when you run the command. The page shows how old the elements are, and marks a satellite unreliable beyond 14 days.
- No timer is installed. If you add one, the fetcher refuses to download the same group twice within two hours.
- Details: `../architecture/earth-shadow-and-satellites.md`.

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
- The NTP client list comes from `gps-time-pi-chrony-clients.service`, which runs as `_chrony` and publishes `chronyc -n clients` to `/run/gps-time-pi/` every 15 s. The same helper publishes `ntpdata` (per-server delay for Timing → References) and `serverstats` (the NTP service card on the Network page). The web service itself can't use chronyd's control socket. If the list reads UNKNOWN: `systemctl status gps-time-pi-chrony-clients`.
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
