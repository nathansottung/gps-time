# Hardware profile scope: dual-band u-blox ZED-F9T / ZED-F9P

## Status

PLAN, **next** (owner, 2026-10-19). Nothing is built. This page says what a dual-band receiver profile needs, what it would and would not improve, and the work in order. Datasheet figures marked *(to confirm)* must be checked against u-blox's current data sheet and interface description for the exact module variant before anything is ordered or wired.

## Why

The current station is a development unit: a Pi 4 with the Uputronics MAX-M8Q board. That is a single-band (L1) receiver, on an antenna and site that the owner rates as weak (best C/N₀ about 25 dB-Hz; `../development/raspberry-pi-deploy.md` → "The current station"). Its PPS outages start with the receiver losing its solution.

A dual-band receiver tracks two bands per satellite (L1 with L2 or L5) and more satellites. That helps it keep a solution, and so a PPS, in poor conditions. It is also the hardware Tier 2 of `../roadmap/ROADMAP-GEOPHYSICS-DISTRIBUTED-SCIENCE.md` depends on: carrier-phase raw data for PPP, ionosphere TEC and Earth tides.

## ZED-F9T or ZED-F9P

| | ZED-F9T (timing) | ZED-F9P (positioning) |
|---|---|---|
| Built for | time and frequency: PPS accuracy, timing modes | centimetre positioning: RTK, moving or fixed base |
| PPS | two time pulses; about 5 ns accuracy (owner's figure; *to confirm* for the variant) | one time pulse; tens of ns *(to confirm)* |
| Fixed-position timing mode | yes: survey-in, then a fixed position, so time comes from every satellite | base-station mode exists, but it isn't a timing mode |
| Raw observations (RXM-RAWX, RXM-SFRBX) for PPP | *to confirm for the variant* | yes |
| Bands | L1/L2 or L1/L5, depending on variant *(to confirm)* | L1/L2 |
| Fits this project | the timing-first station | Tier 2 positioning science, RTK |

**Recommendation:** the **ZED-F9T**, if the chosen variant outputs RXM-RAWX. It matches a timing-first station and still feeds Tier 2 through raw data processed elsewhere. Choose the F9P if centimetre positioning on the station itself (RTK, fast convergence) matters more than timing modes. The rest of this page applies to both unless it says otherwise.

### What the PPS improvement will and won't show on a Pi

The station timestamps PPS through a GPIO interrupt (`pps-gpio`). On this Pi the PPS interval's spread was **1.3 µs** at the rc.10 check (kernel timestamps; `observed`). That spread is interrupt latency, not the receiver. An F9T's nanosecond-level pulse goes through the same path, so the station's PPS statistics, ADEV at short τ, and the time it serves will **not** improve by orders of magnitude. What does improve:

- fewer outages and faster recovery, which is today's real problem;
- more satellites, better DOP, and a better fixed position for the timing mode;
- dual-band ionosphere correction inside the receiver, so less error in the PPS itself.

Nanosecond-level timestamps need a hardware timestamping path: a PPS input on a PTP-capable Ethernet PHY or NIC, for example the Compute Module 4's PHY *(to confirm)*. That belongs with `../specs/SPEC-TIMING-METROLOGY.md` §5 (PTP) and is out of scope here.

## Hardware and wiring

- **Board:** a ZED-F9T or ZED-F9P breakout or HAT with 3.3 V UART and the time pulse brought out. Several vendors make them; record the exact board and revision in the profile, as `../HARDWARE-PROFILES.md` → "Adding profiles" asks.
- **Antenna:** an active dual-band antenna matching the module's bands (L1/L2 or L1/L5), with a ground plane where the antenna needs one. Clear sky view, and mounted with the project's survey and installation guidance (`../GNSS-SURVEY-AND-INSTALLATION.md`). Check the bias voltage the board supplies against what the antenna needs. Fit a lightning arrestor on an outdoor run.
- **Cable delay:** measure or look up the antenna cable's delay. The receiver can compensate it in its time-pulse configuration *(to confirm the key)*, and the profile records the value.

| Module pin | Raspberry Pi | Notes |
|---|---|---|
| UART TX | GPIO 15 (RXD), pin 10 | 3.3 V logic; no level shifter if the board is 3.3 V |
| UART RX | GPIO 14 (TXD), pin 8 | |
| TIMEPULSE (TP1) | GPIO 18, pin 12 (any free GPIO; set in `pps-gpio`) | the same pin as the current profile, so `chrony.conf` and the installer don't change |
| GND | GND, e.g. pin 6 | common ground with the time pulse |
| Power | 5 V or 3.3 V, as the board specifies | dual-band modules draw more than the MAX-M8Q *(to confirm)* |

- **USB instead of the UART** gives NMEA/UBX, but no kernel PPS. That makes it NMEA-only (the `usb-gps` class) unless TP1 is also wired to a GPIO.
- `config.txt`: as now: `enable_uart=1`, `dtoverlay=disable-bt`, `dtoverlay=pps-gpio,gpiopin=18`. The `uputronics` RTC overlay doesn't apply unless the board has an RTC.

## Receiver configuration (once, by the operator)

The station never changes the receiver's configuration (project rule: no changes to timing behavior). The operator configures the module once, saves it to the module's flash, and records it in the profile. Tools: u-center 2 on Windows, or `ubxtool` from gpsd on the Pi (configuration keys through CFG-VALSET).

- **UART speed 115200 baud or higher.** Raw observations at 1 Hz don't fit the default speed *(default to confirm; 38400 on F9 modules)*.
- **Messages:**
  - for gpsd: NMEA (or UBX NAV-PVT / NAV-SAT / NAV-TIMEUTC);
  - for timing research: UBX TIM-TP (next pulse's quantization error);
  - for PPP: UBX RXM-RAWX and RXM-SFRBX.
- **Time pulse:** 1 Hz, rising edge, aligned to GPS or UTC (record which), with the cable delay. Pulse only when locked, so no free-running pulses are presented as GPS time.
- **F9T timing mode:** survey-in to a set accuracy, then fixed position. For the station this replaces the receiver solving its position every epoch. The station's own survey still averages fixes, but it's no longer what the timing depends on.
- **Dynamic model:** stationary.

## gpsd and chrony

- **gpsd:** `DEVICES="/dev/ttyAMA0"`, `GPSD_OPTIONS="-n -s 115200"` (the speed set above). Debian 12 ships gpsd 3.22 and Debian 13 3.25; check each one's u-blox 9 support and `ubxtool` key support on the hardware before the profile claims a release.
- **chrony:** unchanged in shape. `refclock SHM 0 refid NMEA ... noselect` plus `refclock PPS /dev/pps0 lock NMEA refid GPS prefer`. Measure the NMEA offset with the station's existing recommendation (PPS page, #49). Refclocks stay identified from `chrony.conf`, never by name.
- **`tools/generate_config.py`:** new profiles `zed-f9t` and `zed-f9p`. Same `config.txt` and `chrony.conf` as `uputronics` without the RTC, plus the gpsd speed. Their notes name the module and the bands.

## Raw data for PPP

- **What:** RXM-RAWX (pseudorange, carrier phase, Doppler and C/N₀ per signal) and RXM-SFRBX (navigation messages), converted to RINEX 3 (for example with RTKLIB's `convbin`).
- **How much:** roughly 2 KB per epoch with 50–60 signals *(estimate)*. That is about 170 MB a day at 1 Hz, and about 6 MB a day at 30 s (the usual rate for static PPP).
- **Path off the receiver:** gpsd keeps the serial port. Raw UBX is read through gpsd's raw stream (`gpspipe -R`-style) by an optional collector, so the timing path and gpsd are not disturbed.
- **Storage (project rule: nothing to the SD card at 1 Hz):**
  - The collector keeps a RAM ring.
  - It writes hourly compressed chunks at 30 s, either to a non-SD disk (USB SSD) or as an opt-in push to the coordinator tier.
  - It is off by default, with bounded RAM, disk and CPU.
- **Processing: on the coordinator tier, not the Pi.** RTKLIB PPP or PRIDE PPP-AR with IGS products (downloaded there; `external`). Results are `modeled`, with their uncertainty, method and products stated (geophysics roadmap → Tier 2).
- **Privacy:** raw observations give the station's position to centimetres. They are treated like exact coordinates: never published or exported by default, blocked in `hidden` mode, and sent to an online PPP service only on the operator's explicit choice.

## Changes needed in the project

In order, one PR each (after the hardware is chosen and on the bench):

1. **Profiles and docs:** `zed-f9t` and `zed-f9p` in `tools/generate_config.py` (gpsd speed option), `../HARDWARE-PROFILES.md` with the wiring above, and this page updated with what was confirmed.
2. **Per-signal satellites** (`gps_time_pi/gps.py`): gpsd reports a dual-band receiver's satellites once per signal (`gnssid`, `svid`, `sigid`). Today they would count twice in "used / visible" and in the C/N₀ statistics. Group by satellite, keep the signals (band, C/N₀) under it, and count satellites. Fixture: an F9 SKY report.
3. **Satellite views in `/app/`:** a band column and best C/N₀ per band; satellite counts unchanged in meaning.
4. **Receiver identity:** module, firmware and protocol from gpsd's DEVICE report, shown in Administration → Software; the profile in use recorded.
5. **Timing metrology:** the error budget gains the receiver's PPS accuracy beside the Pi's measured timestamp spread, so the page shows which dominates. TIM-TP quantization error is logged as `observed` research data only; it isn't applied to chrony.
6. **F9T timing mode, read-only:** show the receiver's survey-in or fixed-mode state, if gpsd exposes it; otherwise state that it's not observable.
7. **Raw-data collector** (optional module): bounded, off by default, privacy as above, tests with recorded UBX fixtures.
8. **Coordinator-tier PPP:** a separate track with the geophysics roadmap.
9. **Hardware validation** (a deploy-log entry): `ppstest`, `gpsmon`, `chronyc sources -v`, C/N₀ and outage rate beside the MAX-M8Q's, ADEV, and a soak run with `tools/soak_check.py`.

Steps 1–4 and 9 make it a supported profile; 5–8 are what dual-band adds beyond that.

## Decisions for the owner

- F9T or F9P, and which band variant.
- The board, the antenna and the site: the antenna and site matter as much as the receiver for the current outage problem.
- Where raw data goes (USB SSD on the station, or the coordinator), and whether raw collection is wanted at all at first.
- Whether to pursue hardware PPS timestamping (with SPEC-TIMING-METROLOGY §5) to make the F9T's PPS accuracy visible.
