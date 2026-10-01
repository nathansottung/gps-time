# Ideas ledger — everything discussed, hashed out, or floated

The complete idea inventory from this build's design conversations, in four
buckets. Use the "wanted" sections as the GitHub issues list.

## Implemented (shipped in v1.0–v1.3)

- Stratum-1 GPS/PPS NTP server (chrony + gpsd, NMEA-labels-PPS design,
  internet holdover fallback) — `examples/`, runbook §0
- Status page → full instrument: live clock + UTC line, per-device timezone
  defaulting to the browser's own zone, explicit six-state sync model
- Human-readable units with paired uncertainty ("157 ns slow ± 203 ns");
  born from the `0.000000000` display moment — `units.py`
- Oscillator panel; NMEA-offset FAQ note on the page
- Satellites table with SNR bars; NTP clients table; sourcestats
- Firmware & software visibility panel (receiver driver/firmware via gpsd,
  gpsd/chronyd/app/Python versions) — `system.py`, index template
- Almanac: sun (rise/noon/set, twilight bar, daylight deltas to the second),
  moon (phase/rise/transit+altitude/set), night bar with DST-safe midnight
  tick and moonless astronomical darkness, object search (110 Messier /
  planets / 99 named stars / raw J2000 in three formats), dark vs moonless
  viewing windows with per-class emphasis, SVG sky chart, dates 1850–2149,
  observation time always explicit and auto-populated — `astro.py`,
  `catalog.py`, almanac template
- Three themes incl. red-on-black night mode, pre-paint application
- History page: clock offset + uncertainty band on symlog axis ("error bars
  walking into true time" — your framing that named the whole feature)
- Trusted site position surviving fix loss (antenna-failure lesson)
- Position self-survey: Welford mean/variance, SE shrinking 1/√N, honest
  per-fix scatter + systematic-floor caveat; survey reset endpoint
- Position tracker visualization: narrowing SE curve (persisted) + session
  bullseye scatter — History page, `/api/survey`
- Location privacy modes (exact / rounded / hidden)
- RAM-buffered logging (chrony log in tmpfs, boot restore, hourly +
  shutdown flush) + batched config writes — SD-card longevity
- /admin: Pi diagnostics without SSH (model, uptime, load, mem, SD, CPU
  clock, core voltage, under-voltage/throttle flags live + latched, RAM-log
  status) and management actions (service restarts, flush, survey reset,
  privacy, reboot); honest "Pi 4 can't measure its own watts" note with
  Pi 5 PMIC support ready
- custom.css override hook surviving upgrades; templates-as-plain-HTML;
  API-first design for custom frontends
- Hardware config generator with profiles (uputronics, adafruit-ultimate,
  waveshare-l76x, usb-gps with no-PPS honesty warning) — `tools/`
- Install: one command, ephemeris SHA-256 record/verify, no silent
  runtime downloads; systemd services incl. logsync units
- Per-dataset license audit; GPL data sources deliberately avoided
- Full documentation set: project history/decision log, original spec +
  external review preserved, deployment runbook, this ledger

## Wanted — concrete next steps (issue-ready)

- **Remote log shipping**: RAM buffer done; add periodic dump to an
  external endpoint/server (HTTP push or rsync target, configurable)
- **Customizable dashboard (v2 architecture)**: every data source a widget;
  show/hide/arrange; user-managed layout; plugin interface where core
  widgets and third-party sensors are the same kind of thing; crashed
  plugin = honest "unavailable" widget, timing core untouchable —
  sketched in docs/platform-extensions.md
- **Temperature ↔ frequency correlation chart**: the classic oscillator
  characterization; both data streams already logged
- **Satellite sky plot**: polar az/el of the constellation colored by SNR;
  would have shown the antenna failure at a glance; reuses sky-chart SVG
- **Holdover characterization**: deliberately mask GPS, measure real drift,
  publish "±X ms after N hours" as a stated spec on the status page
- **Prometheus /metrics** + state-change notifications (webhook/ntfy when
  leaving SYNCHRONIZED)
- **NMEA offset tune** (~0.035) so its displayed offset reads near zero —
  cosmetic; it's noselect
- **Verify DHCP option 42 propagation** fills the clients table; optional
  UDP-123 NAT redirect on the home router to catch hardcoded IoT clients (deferred
  as fragile-over-SSH)
- **Antenna upgrade**: roof/eave timing antenna
  (Trimble Bullet / Tallysman class, TNC→SMA, confirm 3.3 V bias) — also
  improves absolute position accuracy more than any amount of averaging
- **README screenshot** (docs/almanac.png) before/at GitHub publish

## Wanted — bigger arcs

- **Open lightning network** (the flagship): AS3935 widget → single-station
  VLF sferic receiver (audio-codec ADC with PPS injected in-band — the
  timestamp trick) → crossed loops for bearing → open TOA protocol, solver,
  and data; explicitly open where Blitzortung is gated — full spec in
  docs/open-lightning-network.md
- **Timestamp-platform pairings**: RTL-SDR (ADS-B with MLAT, NOAA/Meteor
  satellites, radiosondes, WSPR, meteor scatter), magnetometer for
  geomagnetic storms + aurora alerts tied to almanac darkness windows,
  environmental HAT feeding the oscillator story, geophone/seismometry,
  acoustic thunder ranging, muon coincidence — docs/platform-extensions.md
- **Precision-position fork**: ZED-F9P + Virginia CORS corrections for
  RTK (~1–2 cm), or F9T for post-processed timing; at that level the
  instrument resolves solid-earth tides
- **NGC/IC catalog** beyond Messier (explicitly deferred at almanac scoping)

## Corrected / consciously rejected along the way

- RTL-SDR for lightning — wrong tool; sferics at ~10 kHz are below its
  range; audio-codec ADC wins at VLF
- Naive exponential position blend — replaced by true Welford survey so
  precision converges instead of merely tracking
- Claiming sub-meter absolute accuracy from averaging alone — correlated
  errors (sidereal-repeating multipath, atmosphere) and the indoor window
  antenna's half-sky bias set a 1–3 m absolute floor; display designed to stay honest
  about it (altitude worst: GPS vertical is 1.5–2× horizontal by geometry)
- "True darkness" naming — shipped as "moonless astronomical darkness"
- Stellarium data — GPL; chose d3-celestial (BSD-3) + OpenNGC (CC-BY-SA)
- Runtime ephemeris downloads — install-time with recorded checksum only
- Replicating Blitzortung's model — verified not open (member-gated
  firmware/kits/data); the open network is the differentiator, with eyes
  open about why they chose gating (volunteer-project sustainability)
