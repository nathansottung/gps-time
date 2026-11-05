# The optional web SDR (`GTP_WEBSDR=1`)

A browser radio on the station: [OpenWebRX+](https://luarvique.github.io/ppa/) behind a LAN gate, open to anyone on the LAN (an optional login), never beyond it, linked from Radio & SDR → Devices. It comes with decoders (SSTV, FT8, FT4, WSPR, APRS, packet, CW, RTTY, fax) and band bookmarks. Owner requests, 2026-11-04. Decision: `../decisions/ADR-0009-web-sdr-on-station.md`.

| Part | Unit | Listens on | Reaches |
|---|---|---|---|
| OpenWebRX+ (Debian package `openwebrx` from the OpenWebRX+ repository) | `gps-time-websdr.service`, user `openwebrx` | 127.0.0.1:8074 (`/etc/openwebrx/openwebrx.conf.d/gps-time.conf`) | the loopback only (`IPAddressAllow=localhost`, `IPAddressDeny=any`) |
| The LAN gate (`gps_time_pi/websdr_gate.py`; a login if `GTP_WEBSDR_AUTH=1`) | `gps-time-websdr-gate.service`, a dynamic user | `GTP_WEBSDR_PORT` (8073), all addresses | private ranges only: 10/8, 172.16/12, 192.168/16, 169.254/16, fc00::/7, fe80::/10 and the loopback |

Script: `scripts/websdr.sh`. Units and files: `system/61-gps-time-rtl-sdr.rules`, `system/gps-time-websdr.service`, `system/gps-time-websdr-gate.service`, `system/gps-time-websdr-signout.service`, `system/websdr-handoff`, `system/openwebrx-gps-time.conf`, `system/openwebrx-gps-time-profiles.json`, `system/openwebrx-gps-time-decoders.json`. Tests: `tests/test_websdr.py`, `web/src/lib/websdr.test.ts`.

## One dongle, one owner

The web SDR uses one RTL-SDR, picked by serial (`GTP_WEBSDR_SERIAL`). By default that is the 1090 MHz dongle (`GTP_SDR_1090_SERIAL` from the SDR stack, `sdr-stack.md`). It takes whichever dongle it's pinned to, and **only the service on that dongle pauses** (rc.8):

| Pinned to | Stops while it runs | Keeps running |
|---|---|---|
| the 1090 MHz dongle (the default) | readsb (`gps-time-readsb`, or the package's `readsb.service`) | dump978-fa, skyaware978 |
| the 978 MHz dongle | dump978-fa and skyaware978 | readsb |
| a dongle with no other role | nothing | everything |

- **How:** the installer writes `gps-time-websdr.service.d/gps-time-dongle.conf` with `Conflicts=` and `After=` for that dongle's units (none for a free dongle), and `GTP_WEBSDR_SHARES` in `/etc/default/gps-time-websdr`. The base unit has no `Conflicts=` of its own since rc.8.
- **Stopping it starts the same units again** (`ExecStopPost=` runs `websdr-handoff`, which resets a failed start limit and starts each one that is enabled; never another unit, and not during a shutdown).
- **The pause shows** on Radio & SDR → Aircraft decoders and on the maps as PAUSED; the Start confirmation names the service that will stop. The references in `reference-adsb` from that band pause too.
- **Never the PPS dongle:** it carries the injected PPS. The installer refuses its serial.
- **The roles are read at install time:** after changing the SDR stack's serials, deploy with `GTP_WEBSDR=1` too, so the drop-in follows them.
- **On a Pi 4, a dongle of its own counts toward the limit of 3** (`sdr-stack.md` → "Roles and the limit"). Sharing the 1090 MHz or 978 MHz dongle doesn't.
- **A session ends by itself** after `GTP_WEBSDR_MAX_HOURS` (default 4; `RuntimeMaxSec=`), so a forgotten web SDR doesn't keep a decoder off. The unit then shows as failed (result `timeout`), and the decoder comes back. There is no automatic restart.
- **Not enabled at boot.** Start and stop it from the Radio page or with `sudo systemctl start|stop gps-time-websdr`. On the Radio page anyone on the LAN can start and stop it, with no admin token (owner, 2026-11-04, rc.6). Use start and stop, not restart: a restart briefly starts the paused decoder between the two halves.

## Install

```sh
sudo GTP_WEBSDR=1 bash install.sh
```

Or in the deploy from your PC: `$env:GTP_WEBSDR = '1'` before `scripts\deploy-to-pi.ps1` (or `GTP_WEBSDR=1 bash scripts/deploy-to-pi.sh ...`). The password is still set on the Pi.

With the SDR stack installed and a 1090 MHz serial set, that's all. Otherwise give the serial: `sudo GTP_WEBSDR=1 GTP_WEBSDR_SERIAL=00001090 bash install.sh`. Optional:
- `GTP_WEBSDR_PORT`: 1024–65535, not 8074; default 8073.
- `GTP_WEBSDR_MAX_HOURS`: 1–24; default 4.
- `GTP_WEBSDR_AUTH`: `1` turns the login on; `0`, the default, leaves it off ("Login" below).
- `GTP_WEBSDR_REMEMBER_DAYS`: how long "Remember this browser" lasts, 1–365; default 30.
- `GTP_WEBSDR_HF`: `off` (default), `direct` or `native` ("HF" below).

Settings are kept in `/etc/default/gps-time-websdr`, so a later `sudo bash install.sh` keeps the web SDR as it is. A changed setting applies from the next start of the web SDR.

## Login (optional)

The owner's decisions (2026-11-04): **the web SDR is open to anyone on the LAN.** The login is off by default, and since rc.6 **Start and Stop need no admin token**. The gate still drops anything from outside the private ranges, and the web service still refuses a Start or Stop from another site (Origin and Host checks, JSON only), so a web page can't start it behind your back. Sign out all browsers still needs the token. An install from before rc.5 has no `GTP_WEBSDR_AUTH` line, so its login is off after the upgrade; the password file is kept for when it's turned on.

To turn it on:

```sh
sudo GTP_WEBSDR=1 GTP_WEBSDR_AUTH=1 bash install.sh
sudo /opt/gps-time-pi/venv/bin/python -m gps_time_pi.websdr_gate passwd
```

`passwd` asks twice (at least 10 characters; the user name is `radio` unless `--user` is given). With the login on and no password set, the gate answers 503 to everything.

**With the login on:**
- **The sign-in page:** a browser opening the web SDR gets the gate's sign-in page (`/gps-time-login`), with a **Remember this browser** box.
- **Ticked:** a signed cookie for `GTP_WEBSDR_REMEMBER_DAYS` (30 days by default). It is `HttpOnly` (page scripts can't read it) and `SameSite=Strict` (other sites can't send it). It is not `Secure`, because the page is plain HTTP.
- **Not ticked:** the cookie lasts until the browser closes, at most 12 hours.
- **How it's signed:** HMAC-SHA256 with a key derived from `/etc/gps-time-websdr/cookie-key` (random, made by the installer, 0600) and the stored password hash. The cookie holds an expiry and a random nonce, nothing else. The gate strips it before the request reaches OpenWebRX+, and passes OpenWebRX+'s own cookies through.
- **Basic credentials still work** (`websdr_gate check`, scripts). A WebSocket request without a login gets a plain 401, never the page.
- **Wrong passwords** back off per address (5 in 5 minutes, then a minute's wait), on the page and with Basic alike. The address is logged, never the password. A sign-in posted from another site (its `Origin`) is refused.
- **`/gps-time-logout`** clears this browser's cookie.

**Signing browsers out:**
- **A new password** (`passwd`) signs every browser out. The key depends on the password's salted hash, so even the same password set again does it.
- **Sign out all browsers** keeps the password and makes a new cookie key. It's on Radio & SDR → Devices → Web SDR when the login is on (admin token, asks first), or on the station: `sudo /opt/gps-time-pi/venv/bin/python -m gps_time_pi.websdr_gate signout-all`. The button starts `gps-time-websdr-signout.service`, a root one-shot unit that can write only `/etc/gps-time-websdr` and runs no Python (nothing from `/opt/gps-time-pi`, which the web service's user can write); polkit lets the web service start it and nothing else.
- **Both apply at once:** they restart a running gate (`systemctl try-restart gps-time-websdr-gate.service`), because it reads its files at start. That also disconnects anyone listening.
- **Migration** (`migrate.md`) carries the password, not the cookie key. A new card makes a new key, so remembered browsers sign in again there.

For OpenWebRX+'s own settings page, add its admin user too: `sudo openwebrx admin adduser <name>`. That login protects only its settings; the gate protects everything.

**What it changes on the station:**
- **APT:** `/usr/share/keyrings/gps-time-openwebrx-plus.gpg` and `/etc/apt/sources.list.d/gps-time-openwebrx-plus.list` for bookworm or trixie. The signing key is downloaded and kept only if its fingerprint is `82B2 AC14 962B 3C75 FAC9 7206 B64E ADD5 CB69 C981` (Marat Fayzullin, the OpenWebRX+ maintainer; checked 2026-11-04). If the package can't be installed, the repository entry is taken out again.
- **Packages:** `openwebrx` and its dependencies (csdr, the connectors, codecs). The package's own `openwebrx.service` is masked before the install: it would start on port 8073 with the first dongle it finds. If `openwebrx` was already installed and enabled by the owner, the script changes nothing.
- **OpenWebRX+ settings:** `/var/lib/openwebrx/settings.json`. A new file gets one RTL-SDR device with five VHF/UHF profiles (2 m, 70 cm, FM broadcast, airband, NOAA weather). An existing file is kept, with a copy beside it (`settings.json.gps-time-prev`); only its RTL-SDR devices' serial is set.
- **The DVB-T driver** (`dvb_usb_rtl28xxu`, with `rtl2832` and `rtl2832_sdr`) would claim the dongle as it's plugged in. `scripts/rtl-dvb-blacklist.sh` writes `/etc/modprobe.d/gps-time-rtl-sdr.conf` (those three and `rtl2830`), so it stays off from the next boot, and unloads it now if it's loaded. If a dongle is busy and it can't be unloaded, the script says to reboot. It never names a shared module (`dvb_core`, `videodev`, `regmap_i2c`), and changes nothing in `/boot` or the initramfs (#157). The `openwebrx` package may not bring `rtl-sdr`'s own blacklist, so this one matters here.
- **No position:** the installer gives OpenWebRX+ no receiver location. Its default location (Budapest, from the package) stays unless the owner changes it. Don't enter the station's position there: OpenWebRX+ doesn't know the station's privacy mode, and it shows its location to every listener.

- **Decoders' helpers:** `direwolf` (APRS, packet), `wsjtx` (FT8, FT4, WSPR: its `jt9` and `wsprd`), `aprs-symbols` and `csdr-skimmer` (CW and RTTY skimmers). They are installed by name, so they are there even where APT skips the package's Recommends. A failure here is reported and leaves the rest of the web SDR in place.
- **Band profiles and bookmarks:** see "Decoders and band bookmarks".

**Never touched:** gpsd, chrony, the PPS line and its overlay, and `/boot`.

**Limits of each unit:**
- OpenWebRX+: 200 % CPU (two cores), 512 MiB, `Nice=10`; writes only to `/var/lib/openwebrx` (settings, when changed).
- The gate: 30 % CPU, 64 MiB, no devices, no capabilities.

## Use

Radio & SDR → Devices → Web SDR: state, serial, port, session limit, login, HF profiles, **Start** (asks first) and **Stop** (anyone on the LAN, no token), **Sign out all browsers** (login on only; admin token; asks first), and **Open the web SDR ↗** while it runs. The link is `http://<the station's address>:8073/`. With the login on, the sign-in page comes first.

The listening page is plain HTTP, and with the login on the password crosses the LAN in clear, so use it on the LAN only. The gate drops anything from outside the private ranges, whatever a router forwards. OpenWebRX+ itself can reach no host but the station: map tiles, PSK Reporter, APRS-IS, receiver lists and update checks don't work, and nothing is reported anywhere. Its map page may still ask the browser to load map tiles from the Internet.

### Check it from your PC

Once it runs and has a password, from any machine on the LAN with this repository:

```sh
python -m gps_time_pi.websdr_gate check http://<station>:8073/
```

With the login on it asks for the password. Then it checks three things: the gate refuses a request with no credentials; with them, the WebSocket at `/ws/` upgrades through the gate; and OpenWebRX+ answers its handshake (`CLIENT DE SERVER server=openwebrx …`). Then it closes cleanly. It changes nothing, though OpenWebRX+ may open the dongle for a moment. Exit status 0 when all three pass. The same client runs in CI against a fake OpenWebRX+ behind the real gate (`tests/test_websdr_websocket.py`), and checks the upgrade, a 76,800-byte server frame, a masked client frame split across writes, and the close.
With the login off, the first check reports "login off: no credentials needed" instead of a refusal, and no password is asked.

## Decoders and band bookmarks

OpenWebRX+ decodes from the mode list once a signal is tuned; nothing runs in the background. Its background decoding stays off: it would load the CPU while nobody listens. What each decoder needs, from OpenWebRX+'s own sources (`owrx/feature.py`, `owrx/modes.py`, checked 2026-11-04):

| Decoder | OpenWebRX+ mode | Needs |
|---|---|---|
| FT8, FT4, WSPR | `ft8`, `ft4`, `wspr` (USB) | `wsjtx` (`jt9`, `wsprd`) |
| APRS, packet | `packet` (FM) | `direwolf`, `aprs-symbols` |
| SSTV | `sstv` (USB, LSB or FM) | built in |
| Fax | `fax` (USB) | built in |
| CW | `cwdecoder` (USB or LSB); CW Skimmer | built in; the skimmer needs `csdr-skimmer` |
| RTTY | `rtty170`, `rtty450`, `rtty85`; RTTY Skimmer | built in; the skimmer needs `csdr-skimmer` |

Decoded spots stay on the page. Reporting them (PSK Reporter, WSPRnet, APRS-IS) can't work, because OpenWebRX+ reaches no outside host. Expect the decoders to raise the CPU figures in the usage log, FT8 above all (a decode every 15 s).

**Band profiles** (`system/openwebrx-gps-time-profiles.json`, keys `gtp-*`) are set on every RTL-SDR in `settings.json` at each install. The owner's own profiles are kept.
- **Always:** 10 m (28.4 MHz ± 1.2), 6 m (50.3 MHz ± 1.2) and 2 m digital (145.0 MHz ± 1.0: APRS on 144.390, FT8, WSPR, the ISS on 145.800 and 145.825).
- **With `GTP_WEBSDR_HF=direct` or `native`:** 160 m, 80 m, 60/40 m, 30 m, 20 m, 17 m, 15 m and 12 m (see HF). `off` removes them again.
- **A new `settings.json`** also gets the base set as before (2 m, 70 cm, FM broadcast, airband, NOAA weather).

**Bookmarks** (`/etc/openwebrx/bookmarks.d/gps-time-decoders.json`, 68 of them):
- the FT8, FT4 and WSPR dial frequencies from 160 m to 2 m;
- APRS on 144.390 MHz, and the ISS packet and SSTV channels;
- SSTV calling frequencies;
- W1AW's CW and RTTY bulletin frequencies;
- the US Coast Guard HF weather-fax frequencies (Boston, Point Reyes, New Orleans; dial 1.9 kHz below the assigned frequency).

Each bookmark selects its decoder. They are fixed, published frequencies for North America and say nothing about where the station is. They are not verified on air; schedules change, so check the W1AW and fax schedules before relying on one. A test checks that every bookmark falls inside a station profile.

## HF (below 24 MHz)

An RTL-SDR's R820T2 tuner covers about 24 MHz to 1.7 GHz. Without HF profiles (`GTP_WEBSDR_HF=off`, the default), the web SDR reaches 10 m, 6 m and above. The HF bookmarks are there, but no profile covers them.

**The Nooelec NESDR SMArt v5 can receive HF by direct sampling.** Its product page gives 100 kHz to 1.75 GHz, says "HF reception below 25MHz is accomplished with direct sampling and requires a suitable antenna", and still recommends an upconverter (Ham It Up) for HF ([nooelec.com](https://www.nooelec.com/store/sdr/nesdr-smart-sdr.html), checked 2026-11-04). Nooelec support names the Q branch (`direct_samp=Q` in a device string). In OpenWebRX+ that is `direct_sampling: 2`, which `GTP_WEBSDR_HF=direct` sets on each HF profile.

| `GTP_WEBSDR_HF` | For | HF profiles get |
|---|---|---|
| `off` (default) | any RTL-SDR | none; 24 MHz and up |
| `direct` | NESDR SMArt v5, RTL-SDR Blog V3 (Q-branch direct sampling) | `direct_sampling: 2` |
| `native` | a dongle with its own HF path, e.g. RTL-SDR Blog V4 (built-in upconverter) | `direct_sampling: 0` |

**HF limits with direct sampling:**
- **No tuner, no LNA, no filter.** The antenna goes straight to the RTL2832U's ADC. Sensitivity is poor next to a real HF receiver or an upconverter. Below about 500 kHz it is poor.
- **Aliases.** The ADC samples at 28.8 MHz, so 0–14.4 MHz and 14.4–28.8 MHz fold onto each other. Without a low-pass filter, strong signals in one half show as images in the other: on 17 m, 15 m and 12 m, expect images of 40–20 m stations and AM broadcast. Strong FM broadcast breaks through as well. A 30 MHz low-pass filter, or a band-pass filter per band, helps.
- **An HF antenna.** The 1090 MHz antenna the web SDR shares with readsb hears almost nothing on HF. HF needs a long wire or an HF antenna. Moving the shared dongle between ADS-B and HF means moving antennas, or a separate dongle with its own antenna (counted toward the limit of 3).
- **Lightning and static.** A long wire collects static, and the dongle's input has little protection. Use a static bleed and a lightning arrestor, and disconnect it in storms (`validation/bench-kit.md` → surge protection).
- **One band at a time.** A profile spans 2.4 MHz. Changing profile retunes the dongle for every listener.
- **Not verified:** no HF profile has run on a station. Two things are expected but not checked: that this OpenWebRX+ version applies `direct_sampling` per profile, and that a V4 works with OpenWebRX+'s rtl connector and Debian's librtlsdr.

**With an upconverter** (Ham It Up and similar), keep `GTP_WEBSDR_HF=off` and add profiles with the converter's offset on OpenWebRX+'s own settings page. The station doesn't manage those.

## Airband bookmarks

Radio & SDR → Devices → **Airband bookmarks** lists the web SDR's airband channels (AM), and OpenWebRX+ shows them as bookmarks (#162).

- **Built in, always:** 121.500 MHz guard, 122.750 air-to-air, 123.025 helicopter air-to-air, 122.900 MULTICOM. These are the same everywhere, need no download and say nothing about the station's location.
- **From the FAA:**
  - **Source:** the 28-day NASR frequency file (`FRQ`) of the current cycle, from `https://nfdc.faa.gov/webContent/28DaySub/extra/<DD>_<Mon>_<YYYY>_FRQ_CSV.zip`.
  - **Filter:** VHF airband (118.000–136.975 MHz) within 80 km of the station's site, at the precision its privacy mode allows: exact, or rounded to 0.1°.
  - **Labels:** each bookmark shows the NASR cycle it came from. The card shows the cycle date and flags the set once it's more than 28 days old. Cycles start every 28 days from 2026-10-29.
- **Refresh now** (admin token) fetches the current cycle. It is the only time anything is downloaded.
  - **How:** the admin action `refresh_airband` starts `gps-time-airband-fetch.service`, a one-shot unit running as the web service's user. The web service itself never fetches.
  - **Writes:** one small file beside `config.json` (`airband-bookmarks.json`), and OpenWebRX+'s bookmarks (`airband-openwebrx.json`, linked from `/etc/openwebrx/bookmarks.d/`).
  - **The station's own position is never written** into either file.
  - **If it fails** (no network, a changed file layout), the card says why, and the previous bookmarks stay.
- **Hidden privacy mode:** no refresh, because a list of nearby airports would show where the station is. The built-ins still work.
- **A stricter mode withdraws what a refresh learned** (security review 2026-11-04, H2). Switching to hidden deletes the NASR set, and OpenWebRX+ keeps the built-ins only. Switching from exact to rounded drops the distances, which were computed from the exact site. Switching back needs a new refresh.
- **Not verified:** the FAA's file server answered this development machine's checks with 503, so the FRQ file's column names (`FREQ`, `FREQ_USE`, `LAT_DECIMAL`, `LONG_DECIMAL`, `SERVICED_FACILITY`) are the expected ones, not yet confirmed. The refresh reads columns by header and refuses a file without them, so a different layout shows as a failed refresh, never as wrong bookmarks.

## The usage log

The owner asked for CPU, temperature and PPS jitter while it is in use. The web service (`gps_time_pi/websdr.py`) keeps:

- **Every 10 s:** the whole system's CPU (`/proc/stat`), the web SDR and gate units' CPU (their cgroups), the SoC temperature.
- **Every kernel PPS event**, from the timing chain's poller: its phase, where the system clock read at the edge (the `/api/stability` layer, interrupt latency and chrony's loop included).
- **One bin a minute** in RAM: CPU mean and largest sample, temperature mean and highest, PPS jitter (the standard deviation of the minute's phases), the largest |phase|, and the pulses seen.
- **The last 10 minutes are always kept,** so each session has a before to compare with.
- **While the web SDR runs,** its minutes are kept (RAM, at most 12 h).
- **When it stops,** one summary line is written to `websdr-sessions.jsonl` beside `config.json`: start, end, duration, and the before and during figures. That's one write per session. The file keeps the last 100 sessions.

The Radio page shows this session's (or the last one's) before and during side by side, and earlier sessions' PPS jitter. `/api/websdr` serves all of it (`../api/endpoints.md`).

What it can and can't say:
- It shows what changed while the web SDR ran, not why. A higher jitter during a session is a correlation; the station names no cause.
- The PPS timestamps are integer nanoseconds from the kernel's text on (since #153), so the jitter figures resolve to 1 ns. Before that they were floats, which near today's epoch resolve only about 0.24 µs.
- A session that was already running when the web service started is marked partial: its first part wasn't recorded.
- The soak record (`tools/soak_check.py`) doesn't include the web SDR's units; a soak run should be done with the web SDR stopped.

## The dongle: serial and USB access

The owner's first start on the Pi (rc.6, 2026-11-04) failed. OpenWebRX+ logged `usb_open error -3`, and the installer had printed `0 RTL-SDR device(s) in OpenWebRX+ set to serial 00000001`. Since rc.7 the installer does four things about it:

- **The serial is pinned as `serial=<serial>`.** OpenWebRX+'s `rtl_connector` then matches it exactly. A bare `00000001` (a common factory serial) is first tried as a serial, and is then read as a device index when the serials can't be read. That opens some other dongle, or none.
- **A device is added when `settings.json` has none.** An existing file without an RTL-SDR device (no `sdrs` key, or only other kinds of radio) left OpenWebRX+ on its built-in device, which names no serial. That was the "0 devices". Now the installer adds `rtlsdr` with the base profiles, keeps the owner's other devices and settings, and says so.
- **The dongles go to the `plugdev` group.** `-3` is libusb's access error: the dongle's node under `/dev/bus/usb` wasn't open to the `openwebrx` user. The unit runs with `SupplementaryGroups=plugdev`, like readsb. Debian's rule (`60-librtlsdr0.rules`) gives RTL2832U dongles to `plugdev`, but udev applies it only when a dongle is plugged in. A dongle that was plugged in before the package arrived can keep root-only access until it's replugged. The installer adds `/etc/udev/rules.d/61-gps-time-rtl-sdr.rules` (0bda:2832 and 0bda:2838, `0660`, `plugdev`) and applies it to the plugged-in dongles at once (`udevadm trigger`, access only, no driver change). It's kept when the web SDR is removed, because readsb uses it too. Since rc.8 the SDR stack installs the same rule (`scripts/rtl-access.sh`).
- **It reports each dongle**: its USB port, serial, group and mode. It also warns when no dongle has the web SDR's serial, or when two have the same one. Two dongles reporting `00000001` can't be told apart. Give each its own serial with `rtl_eeprom -d <index> -s <serial>`, with nothing using the dongles, then replug. The installer never writes a dongle's EEPROM.

Check it on the Pi after the deploy:

```sh
sudo bash -c 'for d in /sys/bus/usb/devices/*; do [ "$(cat $d/idVendor 2>/dev/null)" = 0bda ] && ls -l /dev/bus/usb/$(printf %03d $(cat $d/busnum))/$(printf %03d $(cat $d/devnum)) && cat $d/serial; done'
sudo systemctl start gps-time-websdr && journalctl -u gps-time-websdr -n 40 --no-pager | grep -i "device\|usb"
```

Each node should show `crw-rw---- root plugdev`, and the log should say `Using device <n>` for the right serial.

## Online receiver lists off

OpenWebRX+ has no setting for its online lists. It scrapes other receivers from receiverbook.de, kiwisdr.com and websdr.org. It also downloads repeaters from RepeaterBook, sending the receiver's position, and the EIBI broadcast schedule. Each is fetched when its cache file in `/var/lib/openwebrx` is empty or older than a day (a week for repeaters). The installer writes `receivers.json`, `repeaters.json` and `eibi.json` as empty lists dated 2037-12-31, so they're never stale and never fetched. This was checked against OpenWebRX+ 1.2.128 (`owrx/web/__init__.py`, `WebAgent.refresh`). The map shows no other receivers, repeaters or EIBI transmitters. `IPAddressDeny=any` in the unit blocks any of them that a later version fetches some other way.

## Remove

```sh
sudo GTP_WEBSDR=0 bash install.sh
```

This stops and removes the three units, the session-limit drop-in, `websdr-handoff`, the OpenWebRX+ port setting and the decoders' bookmarks. It keeps the packages and the repository, the mask on `openwebrx.service`, the DVB-T blacklist, the RTL-SDR udev rule, `/etc/default/gps-time-websdr`, the password and cookie key, and `/var/lib/openwebrx` (with the station's profiles in it). To remove the rest: `sudo apt-get purge openwebrx`, `sudo rm /etc/apt/sources.list.d/gps-time-openwebrx-plus.list /usr/share/keyrings/gps-time-openwebrx-plus.gpg`, `sudo systemctl unmask openwebrx`.

## Not verified

The script is tested with stub commands only (`apt-get`, `systemctl`, `curl`, `gpg` and `dpkg` are stubbed; every path is under a temporary root). The gate is tested end to end on the loopback, and the usage log with a manual clock. None of this has run on a Pi yet:
- the `openwebrx` package install on trixie arm64, and its postinst with the unit masked;
- OpenWebRX+ under this unit's hardening (it may need a path or address family the unit doesn't allow);
- the serial pin in `settings.json` (`device: serial=…`), the udev rule and its trigger, and the dongle report, on the Pi (rc.7; the tests use a temporary sysfs tree);
- the online lists staying off with a later OpenWebRX+ version;
- the handoff under systemd (readsb, or dump978-fa and skyaware978 with the 978 MHz dongle), and `RuntimeMaxSec=` ending a session;
- OpenWebRX+'s CPU on the station, and its effect on PPS timing, which is what the usage log is for;
- the sign-in page and its cookie in a real browser against the real OpenWebRX+ (the tests use a stand-in upstream);
- the decoders' packages on trixie arm64, the decoders on air, and the HF profiles (see HF).
