# The optional SDR stack (`GTP_SDR=1`)

The receivers that the SDR modules read, installed by `install.sh` only when asked for:

| Role | What runs | Unit | Network | Output |
|---|---|---|---|---|
| PPS markers (`sdr-pps-marker`) | `rtl_tcp` (Debian `rtl-sdr`) | `gps-time-rtl-tcp.service` | listens on 127.0.0.1:1234 | samples to the module |
| 1090 MHz ADS-B (`reference-adsb`) | `readsb` (Debian `readsb`) | `gps-time-readsb.service` | none: no `--net`, `IPAddressDeny=any` | `/run/readsb/aircraft.json` (RAM) |
| 978 MHz UAT (`reference-adsb`) | `dump978-fa` and `skyaware978`, built from FlightAware's source at v11.1 (commit `f40aa9a`) | `gps-time-dump978.service`, `gps-time-skyaware978.service` | 127.0.0.1:30978 (raw) and :30979 (JSON) | `/run/skyaware978/aircraft.json` (RAM) |

A drop-in for `gps-time-modules.service` lets the modules reach 127.0.0.1 (for `rtl_tcp`) and nothing else. The module supervisor itself is enabled too: it runs no module while the experimental switch is off. Every unit keeps `IPAddressDeny=any`; where it has `IPAddressAllow=`, it is `localhost`.

Script: `scripts/sdr-stack.sh`. Units: `system/gps-time-*.service`, `system/gps-time-modules-sdr.conf`. Tests: `tests/test_sdr_stack.py`.

## Install

Each role needs its own RTL-SDR, picked by its USB serial. Give each dongle a distinct serial first, with one plugged in at a time: `rtl_eeprom -s 00001090`, then replug it. (`rtl_eeprom` comes with `rtl-sdr`.) Then:

```sh
sudo GTP_SDR=1 GTP_SDR_PPS_SERIAL=00000pps GTP_SDR_1090_SERIAL=00001090 GTP_SDR_978_SERIAL=00000978 bash install.sh
```

- **A role with no serial** is installed but not enabled. One dongle for 1090 MHz alone is fine.
- **Serials are kept** in `/etc/default/gps-time-sdr`, so a later `sudo bash install.sh` keeps the stack as it is. `GTP_SDR=1` with no serials keeps the saved ones. `GTP_SDR_978_SERIAL=none` clears one.
- **Refused, with nothing changed:** a serial that isn't letters, digits, `-` and `_`, or the same serial for two roles.
- **A failure never stops the install.** If dump978 can't be fetched, verified or built, 978 MHz stays off and the rest is installed.

**What it changes on the station:**
- **Packages:** `rtl-sdr`, `readsb` and `soapysdr-module-rtlsdr`. For the dump978 build: `git`, `build-essential` and the Boost and SoapySDR development packages.
- **readsb's own `readsb.service` is masked** before the package is installed, so it can't take the first dongle it finds, which could be the PPS one. Exception: if `readsb` was already installed and enabled, it's left alone, `gps-time-readsb` stays off, and the module reads that instance's `/run/readsb`.
- **The DVB-T driver** (`dvb_usb_rtl28xxu`) is unloaded if it is loaded. `rtl-sdr`'s blacklist keeps it out after a reboot.
- **dump978 is built as `nobody`** from a shallow clone of tag v11.1. The build stops unless the clone is commit `f40aa9a0d2d0a0067c0c628b44ba316f7049b8ce`. Only the two binaries are installed, in `/usr/local/lib/gps-time-sdr/`. `-Werror` is dropped, so a newer compiler's new warnings don't stop the build.

**Never touched:** gpsd, chrony, the PPS line and its overlay, and `/boot`. No decoder is given the station's position: there's no `--lat`/`--lon`, and readsb runs with `--json-location-accuracy 0`.

**Each unit:**
- runs as a dynamic user, with USB devices only (`plugdev`) or no devices;
- has systemd hardening like the web service's;
- has `Nice=5` for the decoders;
- has caps: rtl_tcp 40 % CPU / 128 MiB; readsb and dump978 80 % / 192 MiB each; skyaware978 20 % / 64 MiB.

## Remove

```sh
sudo GTP_SDR=0 bash install.sh
```

This stops and removes the four units and the drop-in. It keeps the packages, `/etc/default/gps-time-sdr`, the dump978 build and the mask on `readsb.service` (`sudo systemctl unmask readsb` lifts it).

## Then: turn the modules on in Administration

With the admin token, on Administration:

1. **SDR receivers** (read only) shows:
   - each unit's state, CPU and memory;
   - the dongles found on USB, with the role of each serial; a dongle held by the DVB-T driver or on a slow port is flagged;
   - each decoder's `aircraft.json` age and aircraft count.
2. **Experimental modules:** turn the switch on, then each module by itself. Each SDR module lists what it needs and whether the station sees it:
   - **`reference-adsb`:** at least one fresh feed. The defaults (`/run/readsb`, `/run/skyaware978`) fit the stack, so it needs no settings.
   - **`sdr-pps-marker`:** rtl_tcp running, and `fs_nominal` with an `rtl_tcp` plan in its **Settings** (the README has an example). The PPS injected at its dongle's input can't be observed from the web service, so it shows UNKNOWN. The module's marker count shows it once it runs.
3. **Settings:**
   - **What can be set:** only the keys the module's manifest declares, with their types.
   - **Never accepted:** positions. A module gets the station's site, privacy-filtered, from the station.
   - **Effect:** a change restarts the module set within about 10 s. Settings never turn a module on.
- **Watch the timing chain:** the decoders add USB and CPU load. Their effect on PPS timing is what the soak record measures; it hasn't been measured yet.

## Not verified

The script is tested with stub commands only: `apt-get`, `systemctl`, `git` and `make` are stubbed, and everything is written under a temporary root. None of this has run on a Pi yet:
- the package installs on Debian 13;
- the dump978 build with trixie's GCC and Boost;
- the units under systemd;
- three dongles on one USB bus.
