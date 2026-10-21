# Project history and decision log

The narrative behind the code — what was built, what broke, what was
decided and why. Written so a future contributor (or future you) can
reconstruct the reasoning, not just the result.

## The build

**Hardware.** Raspberry Pi 4, Uputronics GPS/RTC Expansion Board (u-blox
MAX-M8Q, PPS on GPIO 18, RV-3028-C7 RTC), active GPS patch antenna (SMA)
as an indoor window antenna on a steel-sheet ground plane. Network: home
router distributing the Pi's address via DHCP option 42.

**System layer.** Raspberry Pi OS Lite 64-bit. Boot config: UART enabled,
Bluetooth disabled (frees the good UART), pps-gpio on 18, i2c-rtc rv3028
with backup switchover, and the CPU clock locked at 600 MHz — a fixed
clock trades speed for lower PPS interrupt jitter and less thermal swing.
gpsd on /dev/ttyAMA0 with `-n`; chrony with two refclocks:

- **NMEA (SHM), `noselect`** — time-of-day only. It exists to label which
  second each PPS pulse belongs to and is never used for precision. A
  large NMEA offset (tens of ms) is *expected*, not a malfunction — this
  is the most repeated FAQ of the build.
- **PPS, `lock NMEA`, `prefer`** — the actual precision source.

Internet servers (NIST, Cloudflare) ride along as `noselect` sanity
references; a `pool` group stays selectable as holdover fallback — a
decision that paid off within hours (below).

**Result:** stratum 1, GPS selected, sourcestats std-dev ~365 ns, system
clock typically within a few microseconds of UTC. Wired LAN clients sync
within tens–hundreds of µs; WiFi 0.5–5 ms. Internet servers *appear*
3–5 ms off from here — asymmetric residential routing, not clock error.

## The antenna failure (and what it taught the design)

About an hour into first light, GPS died. Diagnosis chain, preserved
because it's the useful part:

1. `ppstest` → `time_pps_fetch() error -1 timed out` — no pulses.
2. `gpspipe` GSV sentences → every satellite at 0 dB except one at
   ~27 dB. That pattern is the signature of an **unpowered antenna LNA**:
   the bare receiver can barely hear one strong bird without its amp.
3. `ubxtool` MON-HW → jamming indicator low (not interference); antenna
   supervisor unwired on this board (no help there).
4. Multimeter: HAT SMA center-to-shell = **3.3 V present** (board bias
   fine). Antenna plug center-to-shell = **open circuit** — the DC feed
   to the LNA is broken inside the antenna/cable.

Verdict: antenna/cable DC-feed fault. The fault later proved
**intermittent** (GPS returned on its own; likely a hairline break moving
with temperature) — visible in a later satellite screenshot showing 8
birds at 20–36 dB in solution: working, but peak SNR notably low for an
active antenna, consistent with a marginal connection.

During the outage, chrony rode through on the pool sources at raised
stratum, exactly as configured. Three features exist because of this
event: the explicit **HOLDOVER** state, the **trusted site position**
(the almanac shouldn't forget where it is because a cable broke), and the
History chart (where such an event appears as the uncertainty band
ballooning, then snapping shut on reacquisition).

## From status page to instrument

v1 was a single-file status page (clock, chrony figures, satellites,
clients). The expansion into the current app was driven by two documents
preserved in this folder — `dashboard-expansion-plan.md` (product spec:
human-readable units, explicit sync states, layered
Status→Quality→Diagnostics) and `almanac-expansion-review.md` (external
review of the almanac design) — reconciled into `almanac-design-scope.md`.
Decisions that survived review:

- **Human units with paired uncertainty**, always: `157 ns slow ± 203 ns`.
  Never make a person count zeros; never show an offset without its error.
  (Prompted by a real moment: the display once read `0.000000000` — the
  estimate crossing zero — which is precisely when you need the ± term.)
- **Observation time is always explicit and labeled** ("Now" live for
  today; 22:00 default elsewhere) — an almanac that silently assumes a
  time is lying a little.
- **Two viewing windows** (dark: object >25°, sun < −18°; moonless: +moon
  down), emphasized per object class — deep-sky wants moonless, planets
  only need dark, raw coordinates get both.
- **Night bar** measured sunset→next-sunrise in elapsed UTC (DST-safe),
  midnight tick labeled with the date it becomes.
- **1850–2149** hard range from the DE440s ephemeris; out-of-range says
  so rather than extrapolating.
- **Skyfield + JPL DE440s on-device**; ephemeris provisioned by install
  with recorded SHA-256, never downloaded silently at runtime.
- **Isolation contract:** the astronomy layer may never break
  timekeeping; guarded imports, honest "Astronomy unavailable — reason."
- Licensing audited per-dataset (see README table); Stellarium data
  avoided (GPL) in favor of d3-celestial (BSD-3) + OpenNGC (CC-BY-SA).

## Testing notes

Astronomy validated in development against a real JPL ephemeris:
sunrise/sunset/noon, daylight deltas (~−2 m 19 s/day, early Sept, mid-Atlantic latitude),
moon events, night segments, M31 transit altitude matching the
declination hand-calculation (90° − |lat − dec| for the mid-Atlantic
development site, dec +41.27),
circumpolar (Polaris) and never-rises (dec −80°) edge states, LST, sky
snapshot counts. Server routes exercised including every degradation
path: no chrony, no gpsd, no ephemeris, garbage object input,
out-of-range dates.

**Field bug worth remembering:** DE440s (the excerpt) carries *only the
barycenter* for Mars — no separate planet-center target like DE421 has.
First deploy crashed the almanac until `mars` → `mars barycenter`.
Mercury/Venus have their planet centers and no meaningful moons; Mars
barycenter is within meters of the planet (Phobos and Deimos are gravel).

## v1.1 additions

- **Site survey:** Welford running mean/variance over accepted 3D fixes;
  standard error shrinks as 1/√N (the location analogue of the clock
  walking into true time), displayed beside the honest per-fix scatter
  (~2–4 m, which does *not* shrink). Stated floor: systematic GPS errors
  (~1–2 m) don't average away. `reset_site` endpoint for antenna moves.
- **Browser-default timezone** (Intl API) — nobody should have to tell a
  clock where they are.
- **Observation time auto-populated**, live while "Now" is active.
- **Firmware & software panel:** receiver driver + firmware strings from
  gpsd, device path, gpsd/chronyd/app/Python versions.
- **custom.css hook** and the hardware **config generator**
  (`tools/generate_config.py`) — see customization-and-hardware.md.
  (The custom.css hook was removed with the legacy pages after v1.4.0.)

## Open items

- NMEA refclock offset could be tuned (~0.035 s) so its reported offset
  reads near zero — cosmetic only; it's `noselect`.
- Verify LAN clients appear in the clients table once DHCP option 42
  propagates leases.
- Consider a roof/eave timing antenna
  (Trimble Bullet / Tallysman class, TNC→SMA, verify 3.3 V bias) — which
  would also serve the VLF ambitions in open-lightning-network.md.

## Where this is going

See `platform-extensions.md` (the platform thesis: timestamped-event
sensors + a widget/plugin dashboard) and `open-lightning-network.md`
(the flagship future build). The README's roadmap is the condensed form.
