# Open Lightning Network — design spec (future build)

**Goal:** a fully open lightning time-of-arrival (TOA) location network —
open hardware, open firmware, open ingestion protocol, open solver, open
data. Functionally what Blitzortung does; structurally what it isn't:
anyone can build a station from the published design, feed the network,
and use the data.

**Why this platform:** TOA location needs stations that timestamp a radio
waveform to ~1 µs absolute accuracy (1 µs of timing is 300 m of light
travel). GPS Time disciplines the Pi's clock to GPS/PPS; whether a captured
waveform's timestamp reaches that level depends on the capture path, and has
to be characterized (`sdr/timing-model.md`). The rest is ordinary
electronics and software.

## Physics in one paragraph

A lightning stroke drives a multi-kiloampere current pulse that radiates a
broadband VLF "sferic" peaking near 10 kHz, receivable at 1000+ km via
ground wave and ionospheric hops. Stations record the arrival time of the
sferic's leading edge. Each pair of stations constrains the source to a
hyperbola (constant time-difference); three-plus pairs intersect at the
stroke. Four or more stations with µs timestamps yield single-kilometer
location accuracy at hundreds of km baselines.

## Stage 1 — Storm sensing widget (weekend build)

AS3935 "Franklin" I²C lightning sensor (~$25 breakout) on the Pi's existing
I²C bus. Detects strokes to ~40 km with a coarse energy/distance estimate.
No timestamps, no waveforms — not TOA-capable — but it delivers a live
storm widget for the dashboard, validates local activity against later
stages, and exercises an interrupt-driven sensor pipeline.

- Wiring: 3V3, GND, SDA/SCL (shared with RTC), IRQ to a free GPIO
- Software: kernel-timestamped IRQ, event log, dashboard widget with
  stroke count / estimated distance / storm state
- Caveat: indoor RF noise (SMPS, LED drivers) causes false triggers;
  the calibration dance is part of the learning

## Stage 2 — The sferic receiver (the real instrument)

A single station that captures VLF waveforms with absolute µs timestamps.

**Antenna.** Two orthogonal magnetic loops (crossed loops give arrival
bearing from the H-field ratio — a single-station capability worth having).
Either ~30 cm air-core loops of ~20 turns, or ferrite rods. Indoor works
poorly; an attic or eave mount away from mains wiring matters more than
antenna refinement.

**Analog front end.** Per channel: low-noise op-amp (e.g. OPA2277/NE5532
class) transimpedance or voltage amp, gain ~40 dB, band-pass ~3–30 kHz
(high-pass kills hum and its low harmonics; low-pass is the anti-alias
filter). A dozen passive components and two op-amps per channel;
publishable as a one-evening solderable board.

**Digitizer + the timestamp trick.** A 192 kHz stereo USB audio codec is
the poor-man's precision ADC (~5.2 µs/sample). USB audio has unknowable
buffering latency — fatal for absolute time — so we don't timestamp in the
computer. Instead: inject the Pi's **PPS pulse into one audio channel**
(resistor divider from the GPIO). Every captured block then contains the
time reference *in-band*, sampled by the same converter clock as the
signal. Arrival times are computed as sample offsets from the PPS edge;
USB latency cancels exactly. This is the classic amateur precision-timing
trick. It establishes which sample is at the PPS edge; absolute accuracy
still depends on the input network, AC-coupling distortion of the PPS edge,
channel skew and anti-alias group delay, which have to be measured (see
below and `sdr/timing-model.md`). With crossed
loops: sferics on L, PPS on R, or a 4-channel codec for both loops + PPS.

**Software (Python, on the Pi).**
1. Continuous capture (ALSA), ring buffer
2. PPS edge detection in-band → absolute time of sample 0 of each second
3. Trigger: amplitude/derivative threshold with adaptive noise floor
4. For each event: leading-edge time (interpolated below sample period),
   bearing from L/R ratio and sign, waveform snippet (few ms), local RMS
   noise context
5. Dashboard widget: strokes/min, bearing rose, waveform gallery
6. Data format (the future network packet), JSONL:
   `{t_utc_ns, station_id, lat, lon, bearing_deg, snr_db, waveform_b64,
   fw_version}`

**Single-station science:** detection + bearing + rough range from
waveform dispersion (ionospheric hop delay grows with distance). Pairs
with the AS3935 for cross-validation and with a microphone channel for
acoustic thunder ranging on nearby strokes.

**BOM sketch:** codec ~$15–25, op-amps/passives ~$10, loop wire/forms
~$15, enclosure/cable ~$20. Under $75 on top of an existing Time Pi.

## Stage 3 — The network (the moonshot)

**Minimum viable network:** 4 stations, 50–500 km baselines. Below 4, no
locations; geometry (spread, not a line) matters as much as count. This is
a "recruit three collaborators" problem before it is a software problem —
the repo, docs, and kit-ability of Stage 2 are the recruiting tools.

**Ingestion protocol (open, versioned):** stations push trigger packets
(above) over UDP or MQTT to any server implementing the spec; servers are
self-hostable. No firmware lock, no blessed hardware — conformance is
"produces valid packets with honest timestamps."

**Solver:** time-difference-of-arrival multilateration. Coarse grid search
seeded by bearings, refined by nonlinear least squares on hyperbolic
residuals; reject outliers (ionospheric-hop misidentification is the
classic error — matching ground wave at one station to sky wave at
another). Waveform cross-correlation between stations upgrades leading-edge
picks. All standard, well-published math; Python + NumPy is adequate at
hobby event rates.

**Validation:** compare located strokes against public maps
(Blitzortung's viewer, national network summaries, GOES GLM satellite
data). Publish accuracy honestly, per the project's house style.

**Licensing:** hardware CERN-OHL-S, code MIT (matching gps-time-pi),
data ODbL. The explicit non-goal: recreating Blitzortung's closed
kit/firmware/data model.

## Risks, honestly

- **RF noise is the real enemy.** Modern homes are VLF-hostile; expect the
  antenna to end up outdoors and the first month to be a noise hunt.
- **Recruitment.** Stage 3 is social. Four stations is the minimum bar for
  a single demo map.
- **Timestamp integrity across codecs.** Different USB codecs have
  different filter group delays; the PPS-in-band trick calibrates each
  station's own chain, but the station spec must require reporting the
  codec model and measured PPS edge shape.
- **Solver subtleties** (sky-wave contamination, propagation speed over
  ground vs ionosphere) are where location error will actually come from.
  Ship coarse first; refine with data.

## Sequencing

1. AS3935 widget → dashboard (fits the customizable-dashboard v2 work)
2. Single-loop receiver, PPS-in-band capture, waveform gallery
3. Crossed loops + bearing; publish Stage 2 as a buildable kit doc
4. Protocol spec + reference server; recruit; first 4-station fix
