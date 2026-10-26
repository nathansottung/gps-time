# A second station

**Status:** guide, 2026-10-26 (#127). Not yet done on hardware. Install steps are those of [`fresh-pi-install.md`](fresh-pi-install.md); this page covers what's different and what a second station is for.

One station can only compare itself with its own receiver. A second station gives the first an outside view: two clocks, two receivers, and, if you want, two antennas. They can be compared at three levels, coarse to fine:
- over NTP;
- through each other's second pulses on a counter;
- later, through the coordinator.

## Choose the setup

What you compare depends on what the two stations share. Pick one deliberately and write it down. Both are valid; they answer different questions.

| Setup | Shared | Differences between the stations show… | Can't show |
|---|---|---|---|
| **A. One antenna, splitter** | antenna, cable, sky, site | the receivers, PPS paths, Pis and chrony | anything the antenna or site does: both see the same thing |
| **B. Two antennas, same site** | sky, site | A, plus each antenna and cable | site-wide effects |
| **C. Different receiver** (e.g. ZED-F9T, `../hardware/zed-f9-dual-band.md`) | as A or B | as A or B, plus the receiver type | as A or B |

For A, use a GNSS splitter that passes antenna power from one port only and loads the other with a DC block. Two receivers both powering the antenna can damage one of them (`../validation/bench-kit.md`).

None of these compares either station with UTC. Both still depend on GNSS. For UTC, see `../validation/second-pulse.md` → "What it can't show".

## Build it

Follow [`fresh-pi-install.md`](fresh-pi-install.md) top to bottom, with these differences:

- **Hostname:** give it its own name in Raspberry Pi Imager, e.g. `gpstime2`, and set `$PiHost = 'gpstime2.local'`. Use names that say the role, never the place.
- **Release:** check out `v1.4.0` (the stable tag) where the checklist says `v1.4.0-rc.11`. `git describe` must print exactly `v1.4.0`.
- **Hardware profile:** pick the second board's profile in step 2 (`docs/HARDWARE-PROFILES.md`). With setup C the device names may differ.
- **Its own identity:** don't copy anything from the first station. The installer makes:
  - a new admin token, shown once; save it separately;
  - a new station key, so a new station ID (`python -m gps_time_pi.station_key show`).

  Never copy `config.json`: it holds the first station's surveyed position and settings. The second station surveys its own position.
- **Privacy mode:** set it on each station (Administration → Location privacy). The rule applies to diagnostics and screenshots from both.

Then run the station alone for three days, with the same read-only check as the first:

```bash
python tools/soak_check.py http://gpstime2.local --expect 1.4.0
```

## Compare them

### 1. Over NTP (coarse: tens of µs at best on a LAN)

Let each station measure the other without using it. The independent references step adds `noselect` servers, which chrony measures and never steers by (`../architecture/independent-references.md`). On each station, naming the other one:

```sh
cd /opt/gps-time-pi
sudo GTP_INDEPENDENT_REFS="gpstime.local" bash scripts/chrony-independent-refs.sh
sudo systemctl restart chrony
```

This changes chrony's configuration, so it's the owner's step. The script writes only its own file, `sources.d/gps-time-independent.sources`, and `GTP_INDEPENDENT_REFS=0` removes it. The References tab then shows the other station's offset as `external`. It shows agreement or disagreement, never a cause.

### 2. Second pulses on a counter (fine: ns to µs)

Run the second pulse on both stations (`../validation/second-pulse.md`). Put station 1's pulse on counter channel A (start) and station 2's on channel B (stop). Then:

```bash
python tools/pps_compare.py two-stations.csv --delay-gpio-ns <B cable> --delay-pps-ns <A cable>
```

The tool's names still say "PPS" and "pulse". Here x = t(station 2's edge) − t(station 1's edge) = (L₂ − L₁) − (e₂ − e₁): the difference of the two system clocks, plus the difference of their write latencies. With both pulse logs, subtract each station's mean write-window midpoint by hand. The tool takes one log.

To separate the two stations' receivers from their Pis, also record each receiver's PPS against the other's (setup B or C). Same counter, PPS on both channels.

### 3. Through the coordinator (later)

Once stations send events (`../../coordinator/README.md`, ADR-0008), the coordinator can line up both stations' outage events in time. A shared event under setup A points at the antenna side; an event on one station only points at that station's own path. Even so, both are classifications for the evidence, not causes.

## Keep the record

- Add the second station to the deployment record in `../development/raspberry-pi-deploy.md` by role (e.g. "station 2, setup A, ZED-F9T"). Never its address, coordinates or serial numbers.
- Real comparison data (counter files, tracking logs) stays outside the repository, as the first station's does.
