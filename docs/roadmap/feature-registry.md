# Feature registry

This is the canonical place for ideas raised during project scoping. A feature appearing here is **not** a claim that it is implemented.

## A. Timing core and metrology

| Feature | Status | Compute tier |
|---|---|---|
| GNSS/PPS-disciplined chrony NTP | Historical / harden | Station |
| Internet NTP fallback with honest stratum/source state | Historical / harden | Station |
| NTP client IP activity | Historical / improve | Station |
| Browser RTT + browser clock estimate | Experimental scaffold | Station |
| RAM-first bounded telemetry + periodic durable checkpoints | Planned | Station |
| Source-loss / fallback / reacquisition timeline | Backend implemented (feat/pps-chain): timing-chain stages, PPS state machine, PPS_OUTAGE events with recovery timing; UI and history views planned | Station |
| Oscillator fractional-frequency history | Planned | Station |
| Time-to-1ms/10ms/100ms/1s holdover estimates | Planned | Station |
| Allan deviation / MDEV / TDEV / TIE / MTIE | Experimental roadmap | Station/Analysis |
| Timing error budget + light-distance equivalent | Planned | Station |
| Antenna/coax/user-delay calibration | Planned | Station |
| PTP / Linux PHC / NIC hardware timestamps | Research | Station |
| Common-view GNSS inter-station clock comparison | Research | Station/Analysis |
| White Rabbit support | Research / later | Specialized |
| Physical 1 PPS / future 10 MHz / IRIG-style outputs | Research | Specialized |

## B. GNSS, site and geodesy

| Feature | Status |
|---|---|
| Fresh-only independent GNSS collector | Partially addressed (CHG-001): fresh-epoch gating + background collector thread in the web process; separate collector service planned |
| Survey sessions with rejected/accepted observations | Planned |
| Time-block averaging and covariance/error ellipse | Planned |
| Accepted/locked station coordinate | Planned |
| Live vs candidate vs accepted position | Planned |
| Learned sky-obstruction / RF horizon map from az/el/C/N₀ | Planned |
| Satellite constellation/health/orbit metadata when receiver exposes it | Planned |
| Antenna status/open/short diagnostics when supported | Planned |
| Ellipsoidal height h / orthometric height H / geoid undulation N | Planned |
| EGM geoid offline data pack | Planned |
| Regional terrain / topographic horizon packs | Planned optional data pack |
| USB GNSS on Linux | Planned |
| Serial NMEA/UBX abstraction for Linux/Windows | Planned |
| Receiver capability tiers (NMEA-only, PPS, precision timing) | Planned |
| ZED-F9T precision-timing tier | Future hardware |
| ZED-F9P/RTK precision-position tier | Future hardware |

## C. Offline derived information

- sunrise, solar noon, sunset and yesterday/today/tomorrow deltas
- daylight duration and daily/seasonal rate of change
- civil/nautical/astronomical twilight and moonless darkness
- Sun azimuth/elevation, apparent solar time, mean solar time, equation of time
- **Solar Phase / solar-equivalent-time calculator** between arbitrary dates/times
- shadow direction/length
- solar irradiance and daily irradiation / clear-sky solar-energy model
- tilted-surface/PV potential as modeled output
- Moon phase/rise/transit/set and planetary/star visibility
- sidereal time and meridian transit utilities
- equinoxes/solstices and seasonal events
- Maidenhead, geodesic bearing/distance, long/short path geometry, antipode/midpoint
- greyline/day-night geometry for amateur radio
- WMM magnetic declination/inclination/field model
- timezone/leap-second/time-scale toolbox with data-age disclosure
- optional local gravity/relativity educational calculations
- weather-derived dew point, air density, density altitude, pressure altitude and related quantities when sensors exist

## D. Dashboard and usability

- configurable pages and widget visibility/size (scaffold implemented)
- later drag/reorder/resizing and saved presets
- presets: Timing, Astronomy, Ham Radio, RF Observatory, Weather, Everything, Blank
- Expert + Learn/ELI5 presentation for every major quantity
- tags: observed / calculated / modeled / inferred
- explicit freshness, calibration and uncertainty on measurements
- portable dashboard/station configuration export/import
- redacted diagnostic export
- theme support including night vision
- solar-transit safety acknowledgement before solar-transit predictions/alerts are enabled

## E. SDR / RF observatory

- multiple SDR inventory by serial and assignment
- spectrum/waterfall and RFI history
- noise-floor and signal-occupancy observations
- WWV/CHU frequency/Doppler monitoring
- WSPR/FST4W reception and propagation observations
- ADS-B/Mode-S 1090 MHz adapter
- UAT 978 MHz adapter
- radiosonde reception
- meteor-scatter observations
- satellite RF reception and Doppler-aware tuning
- SDR sample-clock frequency characterization
- SDR sample-epoch characterization
- GPS-L1 software-receiver calibration experiment
- per-frequency/configuration RF group-delay calibration profiles
- PPS/sample-marker and native timing-aware SDR research
- timing tiers: receive-only → calibrated rate → epoch-aligned → PPS/reference-clock → hardware timestamped
- opt-in authorized amateur/test-beacon TOA/TDoA/fox-hunt research

See `../sdr/overview.md` and `../sdr/timing-model.md`.

## F. Aviation, balloons and moving-object tracking

- local readsb/dump1090-compatible 1090 MHz aircraft receiver
- local 978 MHz UAT receiver
- optional ADS-B Exchange or other external feed adapters; never required for local operation
- MLAT station metadata/peer status and optional analysis-node solver integration
- radiosonde live tracking and trajectory adapters
- generalized topocentric alignment engine
- satellite (OMM + SGP4), aircraft and radiosonde Sun/Moon transit predictions
- aircraft predictions treated as short-term/live trajectory estimates, not long-range deterministic promises
- satellite contamination predictions for camera fields of view

## G. Distributed observation network

- decentralized opt-in observation request / accept / reject flow
- exact station location can be shared with solver without being public
- local-first raw data; derived observations uploaded by default where appropriate
- station/instrument/calibration metadata with each observation
- raw capture hashes/signatures for provenance
- optional coordinator; direct/self-hosted operation remains possible
- distributed GNSS anomaly monitoring
- multi-station WWV/WSPR/ionosphere studies
- meteor/acoustic/seismic/magnetic coincidence experiments
- station clock-consistency/closure checks
- networked lightning TOA as separate VLF acquisition path

Supported distributed localization work should target public broadcasts, natural phenomena, amateur-radio fox hunts/test beacons, and explicitly authorized experimental transmitters.

## H. Environmental and other sensors

- external temperature/humidity/pressure
- pyranometer/solar-radiation sensing
- wind/rain/sky-brightness extensions
- magnetometer / geomagnetic observations
- microphone/acoustic thunder timing
- geophone/seismometry
- all-sky/optical event cameras
- power-grid frequency/phase measurement only through proper isolated instrumentation
- future radiation/muon/coincidence experiments

## I. Open lightning research

- ordinary RTL-SDR is not the primary VLF front end
- VLF/audio-codec acquisition path
- PPS/sample timing calibration
- single-station event detection
- crossed-loop bearing optional
- multi-station TOA solver
- open protocol, open project-authored hardware/software/solver and export formats

## J. Data packs

Core pack remains small enough for field distribution, but size is not a hard ceiling. Optional packs can include enhanced geoid, terrain, deeper astronomy, clear-sky climatology, maps and specialized radio/science data. Every pack needs source, license, checksum, version, age/validity and offline installation support.
