# The optional SDR stack (`GTP_SDR=1`)

The receivers that the SDR modules read, installed by `install.sh` only when asked for:

| Role | What runs | Unit | Network | Output |
|---|---|---|---|---|
| PPS markers (`sdr-pps-marker`) | `rtl_tcp` (Debian `rtl-sdr`) | `gps-time-rtl-tcp.service` | listens on 127.0.0.1:1234 | samples to the module |
| 1090 MHz ADS-B (`reference-adsb`) | `readsb`, built from wiedehopf's source at v3.16.21 (commit `3219318`) with RTL-SDR support, as `/usr/local/bin/readsb` | `gps-time-readsb.service` | none: no `--net`, `IPAddressDeny=any` | `/run/readsb/aircraft.json` (RAM) |
| 978 MHz UAT (`reference-adsb`) | `dump978-fa` and `skyaware978`, built from FlightAware's source at v11.1 (commit `f40aa9a`) | `gps-time-dump978.service`, `gps-time-skyaware978.service` | 127.0.0.1:30978 (raw) and :30979 (JSON) | `/run/skyaware978/aircraft.json` (RAM) |
| Maps | tar1090 (1090 MHz) and skyaware978's page (978 MHz) | none: static pages | served by the web service at `/tar1090/` and `/skyaware978/` | read from `/run/readsb` and `/run/skyaware978` |

A drop-in for `gps-time-modules.service` lets the modules reach 127.0.0.1 (for `rtl_tcp`) and nothing else. The module supervisor itself is enabled too: it runs no module while the experimental switch is off. Every unit keeps `IPAddressDeny=any`; where it has `IPAddressAllow=`, it is `localhost`.

Script: `scripts/sdr-stack.sh`. Units: `system/gps-time-*.service`, `system/gps-time-modules-sdr.conf`. Tests: `tests/test_sdr_stack.py`.

## Install

Each role needs its own RTL-SDR, picked by its USB serial (see "Two dongles" below to give each one its own). With one dongle:

```sh
sudo GTP_SDR=1 GTP_SDR_1090_SERIAL=00001090 bash install.sh
```

With a 1090 MHz and a 978 MHz dongle, after giving them the serials 00001090 and 00000978 (the owner's):

```sh
sudo GTP_SDR=1 GTP_SDR_1090_SERIAL=00001090 GTP_SDR_978_SERIAL=00000978 bash install.sh
```

Or from your PC, in the same deploy (the deploy scripts pass `install.sh`'s `GTP_*` flags from the environment; `../development/raspberry-pi-deploy.md` → "Install flags from the deploy scripts"):

```powershell
$env:GTP_SDR = '1'; $env:GTP_SDR_1090_SERIAL = '00001090'
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-to-pi.ps1 -PiHost $PiHost -PiUser $PiUser
```

- **The 1090 MHz serial is required** with `GTP_SDR=1` (rc.8). With an empty one, readsb was started with `--device` and nothing after it, exited 1 and restarted every few seconds, and the aircraft map wasn't installed (inferred cause of rc.7 on the owner's Pi). `install.sh` now checks this in its preflight and stops before changing anything; the message lists the RTL-SDR serials on USB. `GTP_SDR_1090_SERIAL=none` says there is no 1090 MHz role on purpose, and is kept as `none`.
- **With one dongle,** it is the 1090 MHz one, and 978 MHz stays off (no `GTP_SDR_978_SERIAL`). The PPS and 978 MHz roles are installed but not enabled without a serial.
- **Serials are kept** in `/etc/default/gps-time-sdr`, the file the units read (`EnvironmentFile=`), so a later `sudo bash install.sh` keeps the stack as it is. `GTP_SDR=1` with no serials keeps the saved ones. `GTP_SDR_978_SERIAL=none` clears one.
- **Refused, with nothing changed:** a serial that isn't letters, digits, `-` and `_`, or the same serial for two roles.
- **Warnings, not refusals:** a serial no plugged-in dongle has (it may be unplugged while installing), two dongles with one serial, and a serial like `00000001` that rtl-sdr's device search can read as a device index once two dongles are plugged in.
- **The units refuse an empty serial too:** each has an `ExecCondition=` that skips the start ("condition failed", no restart loop) when its serial is empty or `none`. readsb and dump978 stop restarting after 5 tries in 5 minutes (`StartLimitBurst=5`).
- **A failure never stops the install.** If dump978 can't be fetched, verified or built, 978 MHz stays off and the rest is installed. The same goes for readsb and 1090 MHz, but that one is a `CHECK FAILED` (below).

### readsb with RTL-SDR support (rc.9)

Debian 13's `readsb` package is built without RTL-SDR support: its device types are only `ifile` and `none`. `gps-time-readsb` then failed with `ERROR: Unknown device type:rtlsdr` and restarted for ever, so tar1090 had no data (observed on the owner's Pi on rc.8). The stack now builds readsb itself:

- **From wiedehopf's source, pinned:** a shallow clone of tag v3.16.21, which must be commit `321931802d89f1695a38f6dfb0a64ba5c1211be4`, built as `nobody` with `make RTLSDR=yes readsb` (packages: `git`, `build-essential`, `pkg-config`, `libncurses-dev`, `zlib1g-dev`, `libzstd-dev`, `librtlsdr-dev`, `libusb-1.0-0-dev`). Only the binary is installed, as `/usr/local/bin/readsb`; the commit goes to `/usr/local/lib/gps-time-sdr/readsb.commit`. A later run with the same commit and a passing check doesn't rebuild.
- **Every readsb unit uses it:** `gps-time-readsb`, the feeders' drop-in and `gps-time-feed@`, and node mode's drop-in and `gps-time-readsb-node`. It is built whenever `GTP_SDR=1`, with or without a 1090 MHz serial, since the feeders and node mode run it too.
- **Debian's package isn't installed any more.** One already there (rc.8 and earlier) is left alone, `/usr/bin/readsb` included, and its `readsb.service` stays masked. `sudo apt-get remove readsb` removes it if you like; nothing of ours uses it.
- **Checked before it's installed or enabled:** the check runs `readsb --device-type rtlsdr --gtp-check-only`. The made-up option makes readsb stop at its argument parser either way, so the check never opens a dongle (`readsb --device-type rtlsdr --help` would: readsb only stops for `--help` as the first argument). A build without RTL-SDR support says `Unknown device type` first. Then readsb isn't installed, `gps-time-readsb` isn't enabled, and the installer prints `CHECK FAILED: no readsb with RTL-SDR support` and exits 3, which `install.sh` repeats at the end. Code: `scripts/sdr-decoders.sh`.
- **dump978-fa the same way:** it opens its dongle through SoapySDR (`--sdr driver=rtlsdr,serial=…`), which needs SoapySDR's RTL-SDR driver, `librtlsdrSupport.so` from `soapysdr-module-rtlsdr`. Without it, with a 978 MHz serial set, dump978-fa isn't enabled and the installer prints `CHECK FAILED: SoapySDR's RTL-SDR driver …`. It's a file check: `SoapySDRUtil --probe` would open the dongle.
- **In the preflight** (`sdr-stack.sh check`), these are reported, not refused: on a first install neither is there yet, and the install adds both.
- **Why readsb and not dump1090-fa:** tar1090 is written for readsb's output (history files, `receiver.json`), and the units, the feeders' Beast output and node mode already use readsb's options. dump1090-fa would also be a source build (it's not in Debian), and it would change every one of those. Building readsb changes only the binary's path.

### Check it

The installer waits 10 s after starting the decoders. Then, for each one with a dongle, it reports whether its units are active and its `aircraft.json` exists:

```
SDR stack: check: gps-time-readsb.service is active (dongle 00001090).
SDR stack: check: /run/readsb/aircraft.json exists.
```

A decoder that isn't running prints `CHECK FAILED` with its last journal lines, and `install.sh` says it again at the end ("the station is installed, but an aircraft decoder isn't running"). A decoder paused because the web SDR has its dongle is reported as paused. By hand, on the Pi:

```sh
systemctl status gps-time-readsb gps-time-dump978 gps-time-skyaware978 --no-pager
cat /etc/default/gps-time-sdr
ls -l /run/readsb/aircraft.json /run/skyaware978/aircraft.json
rtl_test -t        # each dongle's serial (stop the decoders first: it opens them)
```

Radio & SDR → **Aircraft decoders** shows the same: each decoder's units, the serial it uses, messages per second and aircraft.

### Two dongles

Both of the owner's dongles are NESDR SMArt v5. Their order on USB (the device index) is not stable, so every decoder opens its dongle by serial. A factory serial like `00000001` is fine with one dongle. With two, give each its own. The owner's: **`00001090`** for 1090 MHz and **`00000978`** for 978 MHz.

1. Stop everything that uses a dongle: `sudo systemctl stop gps-time-readsb gps-time-dump978 gps-time-websdr`.
2. Plug in **one** dongle only, the one for 1090 MHz.
3. `rtl_eeprom -s 00001090`. It shows the current EEPROM and asks to confirm; answer `y`. Unplug and replug it.
4. Plug in the other one alone: `rtl_eeprom -s 00000978`, then replug.
5. With both plugged in, `rtl_test -t` lists `SN: 00001090` and `SN: 00000978`.
6. Deploy with `GTP_SDR_1090_SERIAL=00001090 GTP_SDR_978_SERIAL=00000978`. If the web SDR was pinned to the old serial, set `GTP_WEBSDR_SERIAL` too (its default is the 1090 MHz dongle).

`rtl_eeprom` writes the dongle's EEPROM; the installer never runs it. Why not keep `00000001`: rtl-sdr's device search (rtl_tcp, rtl_test, OpenWebRX+) tries a number as a device index first, so with two dongles `00000001` means index 1, whichever dongle that is. `00001090` and `00000978` are far larger than the number of dongles, so they're always read as serials. The installer still warns about a serial that could be read as an index. (readsb's own search never reads a serial with a leading 0 as an index, and dump978-fa matches `serial=` exactly.)

The 978 MHz role brings skyaware978's map at `/skyaware978/`. PiAware, when installed and turned on (`feeders.md`), feeds the 978 MHz UAT data too.

**What it changes on the station:**
- **Packages:** `rtl-sdr` and `soapysdr-module-rtlsdr` (not Debian's `readsb` since rc.9). For the readsb build: see "readsb with RTL-SDR support" above. For the dump978 build: `git`, `build-essential` and the Boost and SoapySDR development packages. For the aircraft map: `git`.
- **readsb's own `readsb.service` is masked** (from a Debian `readsb` package installed by rc.8 or earlier, or later by hand), so it can't take the first dongle it finds, which could be the PPS one. Exception: if `readsb` was already installed and enabled, it's left alone, `gps-time-readsb` stays off, and the module reads that instance's `/run/readsb`.
- **The DVB-T driver** (`dvb_usb_rtl28xxu`, with `rtl2832` and `rtl2832_sdr`) would claim every RTL-SDR as it's plugged in. `scripts/rtl-dvb-blacklist.sh` writes `/etc/modprobe.d/gps-time-rtl-sdr.conf` (those three and `rtl2830`), so it stays off from the next boot, and unloads it now if it's loaded. If a dongle is busy and it can't be unloaded, the script says to reboot. It never names a shared module (`dvb_core`, `videodev`, `regmap_i2c`), and changes nothing in `/boot` or the initramfs (#157).
- **dump978 is built as `nobody`** from a shallow clone of tag v11.1. The build stops unless the clone is commit `f40aa9a0d2d0a0067c0c628b44ba316f7049b8ce`. The two binaries go to `/usr/local/lib/gps-time-sdr/`, and skyaware978's page (`skyaware/` in the same commit) to `/usr/local/share/gps-time-skyaware978/html`. `-Werror` is dropped, so a newer compiler's new warnings don't stop the build. A station upgraded from rc.7 clones once more to get the page.
- **USB access:** `/etc/udev/rules.d/61-gps-time-rtl-sdr.rules` gives RTL2832U dongles to `plugdev` (mode 0660), and is applied to the dongles plugged in now (`scripts/rtl-access.sh`). Every decoder unit has `SupplementaryGroups=plugdev`. Before rc.8 only the web SDR installed this rule.

**Never touched:** gpsd, chrony, the PPS line and its overlay, and `/boot`. No decoder is given the station's position: there's no `--lat`/`--lon`, and readsb runs with `--json-location-accuracy 0`.

**Each unit:**
- runs as a dynamic user, with USB devices only (`plugdev`) or no devices;
- has systemd hardening like the web service's;
- has `Nice=5` for the decoders;
- has caps: rtl_tcp 40 % CPU / 128 MiB; readsb and dump978 80 % / 192 MiB each; skyaware978 20 % / 64 MiB.

The web SDR (`GTP_WEBSDR=1`, `websdr.md`) takes the dongle it's pinned to. Only the decoder on that dongle stops while it runs (readsb for the 1090 MHz dongle, dump978-fa and skyaware978 for the 978 MHz one), and it starts again afterwards.

## The live aircraft map (tar1090)

On by default with the 1090 MHz role (owner, 2026-11-04, rc.6). [tar1090](https://github.com/wiedehopf/tar1090) is a static web page that draws readsb's aircraft on a map. Aviation → **1090 MHz ADS-B map** links to it (and **978 MHz UAT map** to `/skyaware978/`, since rc.9): `http://<station>/tar1090/`.

- **Fetched by commit:** tar1090 `5d59b1b` (3.14.1825) and its aircraft database `tar1090-db` `2ab834a`. Both are fetched as `nobody` with `git fetch --depth 1 <repo> <commit>`, and each is checked against its pinned commit. Only the page's files are kept, in `/usr/local/share/gps-time-tar1090/html` (the database as `db-2ab834a/`). If either can't be fetched or verified, the map isn't installed and the rest of the stack is.
- **No listener of its own:** the station's web service serves it at `/tar1090/`. It has the same port, the same Host checks and the same LAN as the rest of the station, and no lighttpd or nginx. tar1090's own `tar1090.service` (history chunks) isn't installed. The page falls back to readsb's own history files, so a few minutes of trails show when it opens.
- **Data:** `/tar1090/data/aircraft.json` and `history_<n>.json` are readsb's files from `/run/readsb` (RAM), as they are. Nothing new is written to the SD card.
- **The station marker** comes from the web service, not readsb: `/tar1090/data/receiver.json` is readsb's file with the position set by the privacy mode. Exact mode shows the survey position, rounded mode rounds it to 0.1°, and hidden mode shows no marker and no range rings. readsb is still never given a position.
- **The web SDR pauses tracking** when it runs on the 1090 MHz dongle: starting it stops readsb, and the card shows PAUSED. Stopping it starts readsb again, and the map picks up. The web SDR's own session limit ends a forgotten pause. On another dongle, the map keeps running.
- **HEAD requests** get the same answer as GET without a body, on every route (before rc.8 the server answered 501).
- **Where it is on the Pi:** `/usr/local/share/gps-time-tar1090/html`, not `/usr/share/tar1090` or `/opt/tar1090` as with tar1090's own installer. It is installed whenever the 1090 MHz role has a serial and `GTP_TAR1090=1` (the default). Before rc.8, an empty 1090 MHz serial skipped it, and `/tar1090/` answered 503 "not installed".
- **Map tiles:** the viewer's browser loads them from the chosen map layer's servers (OpenStreetMap by default). The station fetches nothing. The page has its own Content-Security-Policy: scripts from the station only (its two inline ones by hash), images and tile requests from https.
- **What the map says about the station:** the aircraft it shows are the ones the station hears, which says roughly where it is, as for the feeders. On the LAN that is the owner's choice. The marker follows the privacy mode.
- **Off:** `GTP_TAR1090=0` removes the page; `1` puts it back. Kept in `/etc/default/gps-time-sdr`.
- **Not verified on a Pi:** the page against a real readsb (`receiver.json`'s history count, the trails), and the database loader on a phone. On the desktop demo with stand-in data, the pinned page loads under the station's CSP, decodes the gzipped database and draws the aircraft over OpenStreetMap tiles.

## The 978 MHz map (skyaware978)

With the 978 MHz role, skyaware978's own page is served at `http://<station>/skyaware978/` in the same way: static files from `/usr/local/share/gps-time-skyaware978/html`, data from `/run/skyaware978` (RAM), and `receiver.json`'s position set by the privacy mode. The page gets its own CSP; the rest of the app keeps the strict one. It reads files on this machine only, and nothing new listens. Not verified on a Pi: the page against a live skyaware978.

## Roles and the limit

Every dongle is given its role by its USB serial, never by its position on the bus:

| Role | Set by | Kept in |
|---|---|---|
| PPS markers (`rtl_tcp`) | `GTP_SDR_PPS_SERIAL` | `/etc/default/gps-time-sdr` |
| 1090 MHz (readsb) | `GTP_SDR_1090_SERIAL` | `/etc/default/gps-time-sdr` |
| 978 MHz (dump978) | `GTP_SDR_978_SERIAL` | `/etc/default/gps-time-sdr` |
| Web SDR (OpenWebRX+) | `GTP_WEBSDR_SERIAL` (default: the 1090 MHz one; may be the 978 MHz one or a free dongle, never the PPS one) | `/etc/default/gps-time-websdr` |

**The limit (owner, 2026-11-04): at most 3 RTL-SDRs by serial on a Pi 4** (also a Pi 400 or a Compute Module 4).
- **Why:** its four USB ports share one USB 2.0 bus, and the dongles share power and CPU with the timing core.
- **How it's counted:** by distinct serial, across every installed role. The web SDR sharing the 1090 MHz or 978 MHz dongle adds none.
- **Enforced** by both installers (`scripts/dongle-roles.sh`) before anything changes. The model comes from `/proc/device-tree/model`.
- **Other boards:** no limit. If the model can't be read, no limit is applied, and the installer says so.
- **On Administration → SDR receivers:** the roles with a serial, the dongles on USB, and the limit. It's a warning when more are given a role, or plugged in, than the limit allows (`/api/sdr` → `limit`).

## Remove

```sh
sudo GTP_SDR=0 bash install.sh
```

This stops and removes the four units and the drop-in. It keeps the packages, `/etc/default/gps-time-sdr`, the dump978 build, the mask on `readsb.service` (`sudo systemctl unmask readsb` lifts it) and the DVB-T blacklist (`sudo rm /etc/modprobe.d/gps-time-rtl-sdr.conf`, then reboot, lets the TV driver claim dongles again).

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
