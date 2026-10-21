# ROADMAP — GPS Time Desktop (Field / Ham Radio Edition)

## Status

FUTURE. Not scheduled. Do not start until the Raspberry Pi station work in docs/specs/ is complete.

## Goal

A cross-platform desktop app (Windows, macOS, Linux) that turns a laptop plus a GNSS receiver into an off-grid time source and GNSS dashboard. It is a tray app that runs the station's own Python backend, packaged per OS (for example with PyInstaller), and opens the UI in the default browser. No Electron (owner decision, 2026-10-21; ADR-0006). Main use: keeping a laptop clock accurate enough for ham digital modes (JS8Call, FT8, FT4, WSPR) with no Internet.

It reuses the `web/` React dashboard and the design system in `web/guidelines/Guidelines.md`.

## Accuracy targets and honesty

The app must state the accuracy it can actually achieve and never imply Pi-class precision.

| Receiver path | Typical accuracy | Label |
|---|---|---|
| USB GNSS, NMEA only | ~10–100 ms; ~10–20 ms after offset calibration | inferred |
| USB GNSS with PPS on DCD (Linux) | ~10 µs – 1 ms | observed (USB-limited) |
| LAN NTP from a GPS Time Pi | ~0.1–1 ms | external |

Ham digital modes need about ±1 s; best decode under ~0.2 s. Every supported path clears that bar. Show a clear "Ready for FT8/JS8" indicator based on measured offset, not on receiver presence.

## Core features

1. **Receiver input.** Read NMEA from a serial/USB port (in the Python backend, e.g. `pyserial`). Auto-detect common u-blox, SiRF, and MediaTek dongles. Show baud, sentence types, and sentence timing.
2. **GNSS dashboard.** Satellites, C/N0, sky plot, fix, DOP, position, all using existing `web/` components.
3. **Time offset.** Measure system clock vs GNSS time. Show offset, jitter, and trend. Support a per-receiver NMEA delay calibration, stored per device.
4. **Set system time.** Optional, off by default. Step the clock once when the offset is large, then hold it with periodic small corrections. Log every change.
5. **Ham helpers.** Maidenhead grid square from position (4 and 6 character), with a privacy toggle that hides it from screenshots and exports. UTC clock large enough to read from the radio.
6. **Offline.** No network calls at runtime. Fonts and assets bundled.

## Setting the clock safely

Changing system time needs elevated rights on every OS. Neither the tray app nor the browser UI ever runs elevated.

- **Windows:** a small signed helper service holding the right to set time, called by the UI over a local named pipe. Option to defer to an installed tool (Meinberg NTP, BktTimeSync) instead.
- **macOS:** a privileged helper installed through the system's helper-tool mechanism, called over XPC.
- **Linux:** prefer configuring gpsd + chrony (same stack as the Pi). Fallback: a polkit-authorized helper.
- The helper accepts only "set time to X" or "slew by Y" requests, with bounds checks. No general command execution.
- Refuse to set the clock when the fix is invalid, satellites are too few, or the time is implausible.

## Linux PPS path

On Linux, a receiver that drives PPS on the serial DCD line can appear as `/dev/pps0` via `ldattach`. Reuse the Pi's timing-chain model and PPS state machine unchanged.

## Desktop host

Owner's notes, 2026-10-21.

- Same backend and `web/` UI as the Pi, served on localhost from a tray app (Windows, macOS).
- The receiver inspector becomes the Receivers page: identity, lock times, C/N0, sky, timing.
- Each time source gets a tier and an honest ± bound: PPS, USB native, USB bridge.
- Trust receiver time only after leap-second data has arrived. Observed: a u-blox 7 ran 2 s off for 12 minutes before it had the GPS–UTC offset.
- The Pi stays the reference; desktops learn their offsets from it.

## Shared code

- The UI is the `web/` app, served on localhost by the same backend and API as the Pi.
- Timing-chain, PPS, and event logic stay in one place: the desktop app bundles the Python backend; nothing is ported to TypeScript (decided 2026-10-21).

## Out of scope

- Microsecond timing on Windows or macOS.
- Acting as an NTP server for other machines (possible later on Linux).
- Rig control or decoding; leave that to JS8Call, WSJT-X, and similar.

## Open questions

- Packaging per OS: PyInstaller or another bundler, and installer format.
- Tray library per OS, and how the tray app starts, stops and finds a free localhost port.
- Code-signing and notarization costs per platform.
- Which dongles to officially support and test.
