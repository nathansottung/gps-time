# SDR node mode: a second Pi carries the SDR load

A second Raspberry Pi runs the dongles, the web SDR and the feeders, so none of that load sits on the timing Pi. The station reads the node's feeds over the LAN. Owner's rc.3 list and design, 2026-11-04 (#163).

## The node (the second Pi)

```sh
sudo GTP_NODE=1 GTP_NODE_STATION=192.0.2.10 GTP_SDR=1 GTP_SDR_1090_SERIAL=00001090 bash install.sh
```

(`192.0.2.10` stands for the station's address; use the real one, an IPv4 or IPv6 literal.)

- **Time from the station over NTP.** The node has no GNSS or PPS. Its chrony gets one source, the station: `server <station> iburst minpoll 4 maxpoll 6 prefer`, in `/etc/chrony/sources.d/gps-time-node.sources`, then `chronyc reload sources`. `chrony.conf` itself isn't changed; Debian's default already reads `sourcedir /etc/chrony/sources.d`, and the installer says so if it doesn't. The node's other configured sources stay as fallbacks.
- **Its timestamps are labelled `ntp`.** `GET /api/time-quality` on the node says `source: ntp` and gives chrony's error bound (`|System time| + Root dispersion + ½ Root delay`, `calculated`). On a LAN that is usually well under a millisecond, but it's only as good as the station. Anything the node timestamps carries that label: clips, observation files.
- **Feeds for the station only:**
  - **rtl_tcp** (with a PPS-role serial) listens on port 1234;
  - **readsb** serves Beast on port 30005, with every other port closed and still no position.
  - Both accept only the node itself and the station's address (`IPAddressAllow=`).
- **The web SDR and the feeders can live here too:** `GTP_WEBSDR=1` and `GTP_FEEDERS=1` work on the node as they do on the station (`websdr.md`, `feeders.md`). The node's own web page manages them.
- **The node's own timing pages** show no GNSS and no PPS. That is the truth for this Pi, so they say UNKNOWN or missing rather than anything else.

## The station (the timing Pi)

```sh
sudo GTP_SDR_NODE=192.0.2.20 bash install.sh
```

(`192.0.2.20` stands for the node's address.)

- **Aircraft:** `gps-time-readsb-node.service`, a network-only readsb, pulls the node's Beast into `/run/readsb/aircraft.json` (RAM), where `reference-adsb` already reads. The station's own readsb is stopped (`Conflicts=`); both write the same file. This reader listens on nothing and can reach the node's address only.
- **Modules:** the SDR modules may reach the node too (a drop-in adds its address to `gps-time-modules.service`). `sdr-pps-marker` can then read the node's rtl_tcp. Its samples are then timed by the node's clock, which is `ntp`.
- **Radio page:** with no web SDR on the station itself, Radio & SDR → Devices → Web SDR links to the node's web SDR and to the node's own Radio page.
- **Nothing else changes on the station:** not its chrony, gpsd or PPS.

## Undo

- On the node: `sudo GTP_NODE=0 bash install.sh`. This removes the chrony source file (and reloads chrony) and the LAN drop-ins.
- On the station: `sudo GTP_SDR_NODE=none bash install.sh`. This removes the reader and the modules drop-in; the station's own readsb can run again.

## Not verified

The script is tested with stub commands under a temporary root, and the time-quality labels with canned `chronyc` output. Not run on two Pis:
- the node's chrony following the station;
- the LAN allow-lists;
- the station's reader against a node's Beast;
- IPv6 addresses in readsb's `--net-connector`. Use IPv4 until that is checked.
