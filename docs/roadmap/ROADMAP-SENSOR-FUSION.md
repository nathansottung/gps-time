# ROADMAP — Sensors for a Network of Precisely Timed Stations

## Status

FUTURE. Extends ROADMAP-GEOPHYSICS-DISTRIBUTED-SCIENCE.md. Each sensor is an optional module on a node.

## Why timing matters

A network of clocks lets separate stations agree on *when* something happened. Arrival-time differences then give *where*. The timing a sensor needs depends on how fast its signal travels:

| Signal | Speed | 1 ms timing error ≈ |
|---|---|---|
| Sound / infrasound | ~0.34 km/s | 0.34 m |
| Seismic P-wave | ~6 km/s | 6 m |
| Radio / light | 300,000 km/s | 300 km (so radio needs µs–ns) |

So slow signals need only NTP-level time, while radio and particle showers need the station's best PPS time.

## Sensor menu, ranked by science value per cost

### 1. Seismometer (Raspberry Shake)

- Local quakes, quarry blasts, traffic, storms (microseism).
- Network locates events by P/S arrival times.
- Contribute to the existing Raspberry Shake network rather than duplicate it.
- Timing need: ms. Easy.

### 2. Infrasound (Raspberry Boom)

- MEMS differential pressure sensor, about 1–44 Hz.
- Meteors (bolides), thunder, severe storms, explosions, rocket launches.
- Network locates sources by arrival time and gives direction.
- Timing need: ms. Easy.

### 3. VLF lightning receiver

- Loop or whip antenna and a sound-card-class receiver for sferics (3–30 kHz).
- Network locates lightning strikes by time of arrival, as public lightning networks do.
- Timing need: µs (300 m per µs). **Uses the station's PPS time well.**
- Pairs with infrasound: radio flash first, thunder later.

### 4. Cosmic-ray muon detector

- Small scintillator and SiPM (e.g. CosmicWatch-style open designs).
- Single station: muon rate vs pressure, temperature, and solar activity (Forbush decreases).
- Several stations within a few km: coincidences reveal extensive air showers from very high-energy cosmic rays.
- Timing need: ~100 ns or better. **The clearest case for a network of very precise clocks.** Needs the best PPS timing and, ideally, hardware timestamping.

### 5. All-sky camera

- Meteors, fireballs, aurora, satellites, cloud cover.
- Two or more stations triangulate meteor trajectories and estimate orbits; meteorite fall zones for bright fireballs.
- Timing need: ms per frame. Join or follow the methods of existing meteor networks.
- Combines with infrasound and radio meteor scatter for the same event.

### 6. Dual-band GNSS (ZED-F9P / F9T)

- Already in the hardware plan.
- Ionosphere (TEC) maps, scintillation, Earth tides, crustal motion, water vapor.
- Disturbances from storms, quakes, and launches travel through the ionosphere and show up across stations in sequence.

### 7. Magnetometer

- Fluxgate or high-resolution MEMS (e.g. RM3100-class).
- Geomagnetic storms and substorms; links aurora and GNSS disturbances.
- Timing need: about 1 s, but a network gives spatial maps.
- Needs a magnetically quiet site.

### 8. VLF sudden-ionospheric-disturbance monitor

- Receiver tuned to VLF navy transmitters.
- Solar flares change the signal within seconds; a network maps the effect across the sky.

### 9. Radio meteor scatter

- Already in the SDR roadmap; pairs with cameras and infrasound.

### 10. Weather and sky sensors

- Pressure, temperature, humidity, wind, rain, sky quality meter, cloud sensor.
- Mostly context for the other sensors (e.g. pressure corrects muon rates; temperature feeds the oscillator model).

## Cross-sensor events (the network's real strength)

- **Lightning:** VLF sferic (µs) + thunder on infrasound (seconds later) + flash on camera.
- **Bolide/meteor:** camera track + radio echo + infrasound boom + possible seismic signal.
- **Earthquake:** seismometer + GNSS displacement (cm stations) + ionosphere disturbance minutes later.
- **Solar storm:** magnetometer + GNSS scintillation + muon rate drop + aurora on camera.
- **Rocket launch:** infrasound + ionosphere hole on GNSS + camera.

The coordinator correlates events across sensors and stations. It reports coincidences and measured values; it never states a cause the evidence can't support.

## Not feasible (state plainly)

- Gravity field or Earth's mass from clock comparisons (needs optical clocks).
- Gravitational waves.
- Neutrino detection with hobby hardware.

## Order

1. Seismometer and infrasound (cheap, ready-made, ms timing).
2. VLF lightning (shows off µs timing).
3. All-sky camera.
4. Dual-band GNSS.
5. Muon detectors (needs best timing; flagship science).
6. Magnetometer and SID monitor.
