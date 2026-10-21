# GPS Time Pi — Almanac expansion: scope and design for review

**Date:** September 2, 2026
**Status:** Design draft, pre-implementation. Seeking feedback on scope, UX decisions, and technical approach.

---

## 1. Context: what exists today

A working GPS-disciplined stratum-1 NTP server on a Raspberry Pi 4:

- Uputronics GPS/RTC HAT (u-blox MAX-M8Q), active antenna, PPS on GPIO 18
- chrony disciplined by PPS (`refclock PPS lock NMEA prefer`), internet pool
  servers as automatic fallback, `noselect` NIST/Cloudflare as benchmarks
- Measured performance: PPS refclock mean offset −1 ns, std dev ~365 ns;
  system clock typically within ±1 µs of UTC
- A self-hosted status page (single Python file, stdlib only, systemd service,
  port 80): live ticking clock with per-device timezone selector, sync status,
  chrony figures, sources table, live satellite table (constellation, el/az,
  SNR, used-in-fix), NTP client list, `/time` (plain text), `/api` (JSON),
  `/zones` (all IANA timezones with current offsets)

Design identity: sparse, instrument-like, local-first. No cloud services; the
appliance derives everything from its own authoritative time + GPS position.

## 2. What's being added

A new **Almanac** page plus supporting sections, turning the device into a
"GPS-disciplined time and position observatory": location-aware sun/moon
almanac, deep-sky object lookup, simplified sky chart, and a three-theme
display system. Astronomy computed locally from UTC + the GPS fix.

## 3. Page design (top to bottom)

### 3.1 Header
- Title, theme toggle (Light / Dark / Night), date navigation:
  arrows + date input, defaulting to today. Any date past or future via
  `/almanac?date=YYYY-MM-DD`. All times render in the page's selected
  timezone (existing per-device dropdown).

### 3.2 Sun section
- Sunrise, solar noon, sunset, daylight duration.
- Daylight deltas in both directions, to the second:
  "−2 m 18 s vs yesterday · −2 m 20 s to tomorrow" (the asymmetry is real
  and makes the seasonal acceleration visible).
- **Daylight bar directly beneath**: 24-hour strip (midnight to midnight),
  sun only — night / astronomical / nautical / civil twilight / day —
  with a "now" tick when viewing today. Labels: astro dawn, sunrise,
  sunset, astro dusk.

### 3.3 Moon section
- Phase name, illumination %, lunar age (days), moonrise, meridian transit,
  moonset, moon-above-horizon duration with delta vs yesterday.
- **Night bar directly beneath**: spans sunset → following sunrise (the
  "tonight" a human thinks in, not a calendar day), so the night gets full
  width. Twilight shading at each end, moon-above-horizon shaded, and the
  unshaded remainder is **true darkness** — astronomical night with the
  moon below the horizon — called out with total and interval:
  "True darkness tonight: 39 min (9:03–9:42 PM)".
- Because the bar crosses a date boundary: **midnight gets a full-height
  tick labeled with the date change** ("midnight → Sep 3"), and any
  rise/set label on the far side carries its date.

### 3.4 Find an object
Search box accepting three input classes, auto-detected:
1. Catalog names/IDs: `M31`, `Andromeda galaxy`, `Jupiter`, `Vega`
2. RA/Dec, J2000 (stated next to the box): `00h42m44s +41d16m09s`,
   `00:42:44 +41:16:09`, or decimal `10.684 +41.269`
3. Anything else → plain "couldn't parse" message with format examples

Result card fields:
- Name, type, magnitude (catalog hits; coordinate hits skip these)
- Current altitude + azimuth
- Rise time
- **Meridian transit: time and the altitude reached** (transit is the
  object's best moment; the altitude says whether "best" is any good)
- Set time
- **Best viewing window**: intersection of (object above ~25° altitude) ∧
  (sun below −18°) ∧ (moon below horizon), for the selected date
- Edge cases stated plainly: "circumpolar — always up; highest at transit
  HH:MM" or "never rises from this latitude" instead of blank fields

### 3.5 Sky now
Simplified static chart, regenerated per page load (SVG): dome projection,
cardinal points, constellation stick figures, stars to ~mag 4.5, planets,
the moon, and the searched object marked. Explicitly NOT an interactive
pan/zoom planetarium.

### 3.6 Location section (main page, already designed)
- Lat/lon from GPS; elevation shown as both MSL and ellipsoid HAE (gpsd
  provides `altMSL` and `altHAE` separately — no geoid guessing)
- Fix type, satellites used, local sidereal time
- Privacy setting, server-side, applies to all viewers:
  **Exact / Rounded (~0.1°) / Hidden**; exact coordinates always used
  internally for computation

## 4. Catalog scope (deliberately small)

- 110 Messier objects
- 8 planets
- ~25 named bright stars (Vega, Polaris, Sirius, Arcturus, ...)
- One bundled `catalog.json`, a few hundred KB
- **NGC/IC catalogs explicitly deferred** — the RA/Dec input covers
  anything not in the catalog; NGC becomes a future decision, not a v1
  burden

## 5. Themes

- **Light** and **Dark**: standard.
- **Night**: deep red (~#E03A2F) on black, overall contrast reduced —
  ~630 nm light minimally bleaches rod photoreceptors, so moonrise can be
  checked at the telescope without destroying dark adaptation. Honest
  limitation: at normal screen brightness it reduces rather than fully
  preserves adaptation.
- Choice saved per-device (localStorage), applies to all pages.

## 6. Technical approach

- **Engine: Skyfield** (Python, MIT license) + **JPL DE440s ephemeris**
  (public domain, ~32 MB one-time download, then fully offline).
  Rise/set to the second, positions to sub-arcsecond — almanac-grade.
  Rejected alternative: hand-rolled Meeus/NOAA formulas (zero deps but
  ~1 min / ~1 arcmin accuracy; conflicts with the "hyper accurate" goal).
- Skyfield pulls numpy; acceptable on a Pi 4 (even underclocked to
  600 MHz). Per-date almanac computed once and cached; "now" quantities
  (altitudes, sidereal time) computed per request — cheap.
- Repo restructure from single file to package:
  `server.py` (HTTP/routing), `chrony.py` (parsers), `gps.py` (gpsd
  client), `astro.py` (Skyfield computations), `catalog.json`,
  `templates/`. Same zero-config systemd deploy.
- Failure honesty: if no valid GPS fix, the almanac says "Astronomy
  unavailable — no valid location" rather than reusing a stale fix
  silently. Stale data is labeled with its age.

## 7. Licensing / IP review

No patent exposure: astronomical computation is published mathematics.
Copyright/licenses of code and data, all permissive, repo stays MIT:

| Component | Source | License |
|---|---|---|
| Astronomy engine | Skyfield | MIT |
| Ephemeris | JPL DE440s | Public domain (US gov) |
| Messier data | OpenNGC-derived subset | CC-BY-SA 4.0 (attributed) |
| Bright stars | Yale Bright Star Catalog | Public domain |
| Constellation lines | d3-celestial datasets | BSD-3 |

**Verified 2026-10-21 (#101):** the bundled stars came from d3-celestial (its Hipparcos-based
`stars.6.json`), not the Yale Bright Star Catalogue as the table says. The Messier data is
OpenNGC (CC BY-SA 4.0) and now lives in its own file, `messier.json`. Sources, versions and
licenses per file: `gps_time_pi/data/README.md`.

Deliberately avoided: Stellarium data files (GPL — would virally
relicense the MIT repo if bundled).

## 8. Out of scope (v1)

NGC/IC catalogs, satellite passes, interactive planetarium, weather,
generic system administration, cloud anything.

## 9. Open questions for the reviewer

1. Night bar spanning sunset→sunrise with a labeled midnight tick — clear
   enough, or is midnight-to-midnight with the night split at the edges
   less confusing for a first-time viewer?
2. Best-viewing thresholds (object >25°, sun <−18°, moon below horizon):
   should moonlight be a soft penalty (e.g. allow moon up if <20%
   illuminated and >90° away) rather than a hard exclusion?
3. Is per-device theme (localStorage) right, or should Night mode be a
   server-side setting so a wall-mounted display can be switched remotely?
4. The daylight deltas show seconds ("−2 m 18 s") — meaningful precision
   or false precision, given atmospheric refraction alone shifts rise/set
   by ~±30 s day to day with pressure/temperature?
5. Skyfield+numpy vs pure-stdlib Meeus: is almanac-grade accuracy worth
   the dependency on a project whose identity so far is "stdlib only"?
6. Anything in section 3 that breaks the "sparse instrument, not a
   planetarium app" identity?
