# Building on the Time Pi — pairings and extension architecture

The thesis: GPS Time Pi is not an NTP server with accessories. It is a
**precision timestamp platform** — a disciplined clock, a surveyed position,
and a dashboard — and any sensor that produces timestamped events becomes
more valuable attached to it. This doc catalogs worthwhile pairings and
sketches the plugin architecture that will make them easy to add.

## Pairings worth building

**VLF lightning receiver** — the flagship; see
[open-lightning-network.md](open-lightning-network.md). Audio-codec ADC with
PPS injected in-band; the µs clock is the enabling ingredient.

**RTL-SDR (~$35, TCXO version)** — *not* for lightning (sferics are at
~10 kHz, below its range; the audio-codec approach wins there), but ideal
for:
- **ADS-B aircraft tracking** (1090 MHz): the classic Pi+SDR build; feeder
  networks locate non-transponder-position aircraft by multilateration —
  the same time-of-arrival math as lightning location
- **NOAA / Meteor weather satellite imagery**: pass predictions computed
  on-device from the almanac's own machinery (Skyfield does satellites)
- **Radiosonde tracking**: decode weather-balloon telemetry
- **WSPR propagation monitoring**: report HF band openings. PPS disciplines
  the Pi's system clock, not the SDR's oscillator: frequency and drift
  measurements improve only if the SDR is itself locked or calibrated
  (see `sdr/timing-model.md`)
- **Meteor scatter counting**: echoes off ionized trails, timestamped

**Magnetometer (RM3100 / HMC5883L, ~$15, I²C)** — geomagnetic storm
detection and an aurora-alert widget that pairs naturally with the
almanac's darkness windows. Slow data, high payoff, trivial wiring.

**Environmental HAT (BME280 class, ~$10, I²C)** — temperature, pressure,
humidity. Feeds the oscillator characterization story (crystal frequency
vs temperature) and general weather logging.

**AS3935 lightning sensor (~$25, I²C)** — storm proximity widget; stage 1
of the lightning roadmap.

**Geophone / seismometer** — Raspberry Shake territory: timestamped ground
motion; networked stations locate quakes by (again) time of arrival.

**Acoustic channel (microphone)** — thunder arrival vs RF detection of the
same stroke gives single-station lightning range (instrumented
flash-to-bang); doubles as an infrasound experiment.

**Muon detector (CosmicWatch-style)** — cosmic-ray coincidence between
separated stations is only meaningful with µs absolute timestamps. The
platform's disciplined clock enables that, subject to characterization: the
host clock is not the detector's timestamp path, so the detector-to-host
latency and its jitter have to be measured (see `sdr/timing-model.md`).

A recurring theme: ADS-B MLAT, lightning TOA, seismic location, and muon
coincidence are conceptually the *same measurement*: timestamped arrivals
at distributed stations. The timestamp paths differ, though (MLAT networks
typically use SDR sample counters synchronized through the aircraft
signals themselves, not host GPS time), so each needs its own
characterization (`sdr/timing-model.md`).

## Extension architecture (v2 direction)

To make iteration easy, the dashboard should become an arranger of
**widgets** fed by **plugins**:

- A plugin is any process that exposes, per a small spec:
  1. `GET /plugin/<name>/data` — current JSON (or pushes events to a local
     bus / socket with `{t_utc_ns, type, payload}`)
  2. A widget descriptor: name, refresh interval, render template or a
     small JS module
- The core server discovers plugins from a `plugins/` directory and
  proxies their data; the web UI renders enabled widgets (since v1.4 the
  web UI's Configure page shows or hides pages and cards per browser;
  this plugin model is not built)
- Core widgets (clock, sync state, quality, satellites, survey, almanac
  summary, history sparkline) are refactored onto the same interface, so
  "full customization" — show/hide/reorder everything — falls out of the
  design rather than being bolted on
- Contract with the timing core unchanged: no plugin can degrade
  timekeeping; a crashed plugin renders as an honest "unavailable" widget

Until v2 lands, extensions can simply add routes + a section to the page —
the codebase is small enough to read in a sitting, which is itself a
feature worth preserving.
