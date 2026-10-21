# Customization and hardware support

## Scope of the current build (v1.1)

**Timing core:** chrony + gpsd status, explicit sync states, quality figures
with paired uncertainties, oscillator panel, sources/satellites/clients,
firmware & software versions panel.
**Position:** live fix + Welford site survey converging as 1/√N, privacy
modes, survey reset endpoint.
**Almanac:** sun/moon/night/objects/sky, 1850–2149, three themes,
browser-default timezone, observation time auto-populated.
**History:** offset + uncertainty convergence chart from chrony's own log.
**Isolation guarantee:** astronomy can never break timekeeping.

## Customizing the pages

Three tiers, least to most invasive:

1. **Configure** — in the web UI (`/app/`), show or hide pages and Overview
   cards and switch the red night theme. Stored per browser; nothing on the
   station changes.
2. **Web UI source** — the UI is the React app in `web/` (follow
   `web/guidelines/Guidelines.md`). Edit it, rebuild (`corepack pnpm run
   build`) and redeploy; the bundle ships `web/dist`.
3. **API-first rebuild** — everything in the UI comes from `/api`,
   `/api/almanac`, `/api/object`, `/api/history` and the other routes in
   `docs/api/`. A fully custom frontend needs nothing from `web/`.

(The legacy pages, `custom.css` and `gps_time_pi/templates/` were removed
after v1.4.0; a `custom.css` left on a station is no longer loaded.)

The planned v2 widget/plugin dashboard (see platform-extensions.md) will
make tier 1-level customization cover show/hide/rearrange of everything.

## Supporting different GPS hardware

Hardware differences reduce to three parameters: the serial device, the
PPS GPIO (if any), and the RTC overlay (if any). The generator turns those
into ready-to-apply system config:

```bash
python3 tools/generate_config.py                     # interactive
python3 tools/generate_config.py --profile uputronics
python3 tools/generate_config.py --uart /dev/ttyAMA0 --pps-gpio 4
```

Built-in profiles: `uputronics` (this build's board), `adafruit-ultimate`
(PPS on GPIO 4), `waveshare-l76x`, `usb-gps` (NMEA-only — the generator
warns that without PPS you get a ~10–100 ms convenience clock, not a
stratum-1 instrument; the honesty is the point).

Adding a profile is a one-line dict entry in `tools/generate_config.py` —
PRs welcome with a link to the board and a photo of it working.

## Firmware visibility

The status page's "Firmware & software" panel reports what gpsd knows:
receiver driver and firmware subtype strings, gpsd release, chronyd
version, and this app's version. For deeper u-blox introspection
(`MON-VER`, per-constellation config), `ubxtool -p MON-VER` with
`UBXOPTS="-P 18"` remains the tool of choice at the shell.
