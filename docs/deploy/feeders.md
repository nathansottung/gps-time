# Opt-in ADS-B feeders (`GTP_FEEDERS=1`)

Send the aircraft the station receives to services you choose: aggregators that take Beast data, and FlightAware's PiAware. Owner's rc.3 list and design, 2026-11-04 (#161).

**Nothing is sent until you turn a feeder on.** That happens in Administration → Feeders, one feeder at a time, with the admin token and the service's name typed out. Turning it off needs no confirmation.

## What each one shares

| Feeder | Sends | The station's location |
|---|---|---|
| adsb.fi, airplanes.live, ADSBExchange, a custom aggregator | the aircraft messages readsb decodes (Beast, reduced), with a random feeder UUID | **not sent**: no feeder is given the position, and MLAT isn't offered for these. From the aircraft it hears, a service can tell roughly where the station is. |
| FlightAware (PiAware) | the same | **not sent** while MLAT is off. PiAware is set never to read gpsd, which would otherwise give it the exact position. |
| FlightAware MLAT | timing for multilateration | **exact location**: MLAT needs it. A separate opt-in (type `share my exact location`), refused in hidden privacy mode. |

Each card on Administration says this in plain words. When MLAT is on, the card reads **"Shares your exact location with FlightAware."** With MLAT off, the PiAware card still carries the warning, in amber: **"Shares your location with FlightAware: the aircraft it receives show roughly where the station is. Your exact location only with MLAT, which is off."**

**Location sharing**, a card below the feeders, lists everything that shares or could share the station's location, in one place:
- each feeder and FlightAware MLAT;
- the capability record (rounded location in rounded mode; not sent anywhere yet);
- the sky-quality summary (sectors only, opt-in).

When the exact location is being shared, it says so first.

**Hidden privacy mode:** MLAT can't be turned on. Switching to hidden turns it off and restarts PiAware without it. PiAware's start-up helper also refuses MLAT whenever `config.json` says hidden.

## Install

Needs the SDR stack's readsb (`GTP_SDR=1` with a 1090 MHz serial, `sdr-stack.md`).

```sh
sudo GTP_FEEDERS=1 bash install.sh                                   # the Beast aggregators
sudo GTP_FEEDERS=1 GTP_FEEDERS_PIAWARE=1 bash install.sh             # and PiAware
sudo GTP_FEEDERS=1 GTP_FEEDERS_CUSTOM=feed.example.org:30004 bash install.sh   # and one of your own
```

From your PC, the deploy scripts pass these flags too (`../development/raspberry-pi-deploy.md` → "Install flags from the deploy scripts").

**What it changes on the station:**
- **readsb** (`gps-time-readsb.service`) gets a drop-in. It decodes exactly as before, and adds one output: Beast on `127.0.0.1:30005`. Every other port stays closed, and readsb still reaches no host but this one. It's still never given `--lat`/`--lon`.
- **One unit per aggregator,** `gps-time-feed@<name>.service`:
  - a second readsb in `--net-only` mode, reading `127.0.0.1:30005` and sending to the host in `/etc/gps-time-feeders/<name>.conf`;
  - its random UUID is in `<name>.uuid`;
  - it runs as a dynamic user, with no devices, no listeners, 15 % CPU and 64 MiB.
  - Enabled so your choice survives a reboot, but `ConditionPathExists=/opt/gps-time-pi/feeders/<name>.on` keeps it from running until you turn it on.
- **PiAware** (`GTP_FEEDERS_PIAWARE=1`), from FlightAware's own repository (`apt.svc.flightaware.com`, bookworm or trixie):
  - **The repository's key:** taken from FlightAware's `flightaware-apt-repository` package (its SHA-256 checked against the repository's index), and kept only if it holds `56B6 684E 1389 29F4 E7CF 014B C3B2 A470 AAD5 A173`, the key that signs the trixie release (checked 2026-11-04).
  - **Masked while installing:** `piaware.service` and `dump1090-fa.service` are masked before the install, because PiAware's defaults would read gpsd and send the position. It's installed with `--no-install-recommends`, so dump1090-fa (a decoder of its own) isn't.
  - **Settings, applied before every start** by a drop-in and `/usr/local/lib/gps-time-sdr/piaware-settings`: `receiver-type other` on `127.0.0.1:30005`, `use-gpsd no`, no automatic or manual updates, and `allow-mlat` only with your MLAT opt-in.
  - **Waits for you:** it runs only once you've turned it on (`ConditionPathExists=…/piaware.on`).
- **The polkit rule** lets the web service start, stop and try-restart `gps-time-feed@<name>.service` and `piaware.service`, and nothing else new.

**Never touched:** gpsd, chrony, the PPS line.

## PiAware's feeder ID

FlightAware links a feeder to an account by its feeder ID, which PiAware gets at its first connection. To claim the station on FlightAware's site, or to move an existing feeder ID onto it, follow FlightAware's instructions (`piaware-config feeder-id <id>`, then restart from Administration).

## Remove

```sh
sudo GTP_FEEDERS=0 bash install.sh
```

This stops and disables the feeder units and PiAware, and removes the units, the drop-ins and your on-switches. readsb goes back to no network at all. The packages, `/etc/gps-time-feeders` (the UUIDs, so a later install keeps the same feeder identity) and the FlightAware repository are kept.

## Not verified

The installer is tested with stub commands, and the module and routes on temp folders. None of it has run on a Pi:
- Debian readsb's `--net-connector … beast_reduce_plus_out` and `--uuid-file` with each aggregator;
- the PiAware install on trixie arm64 with its unit masked;
- `piaware-config` under the drop-in;
- the feeds being accepted on the services' side.
