# ADDENDUM — Timing, Sky, Solar, Satellite, and Environmental Intelligence

## Scope

GPS Time Pi should evolve beyond a simple Stratum-1 NTP appliance into a local timing, GNSS, sky, solar, satellite, RF, and environmental observatory.

The Raspberry Pi station tier must remain lightweight and useful offline. Computationally expensive historical analysis, distributed correlation, large datasets, and ML workloads should remain optional coordinator-tier features.

All calculations must clearly distinguish:

- directly measured values
- values calculated from measured inputs
- astronomical predictions
- estimates
- externally sourced data

---

# 1. Earth Shadow / Satellite Illumination

Add a real-time Earth-shadow model primarily intended to help astronomy and astrophotography users understand satellite contamination.

Do NOT model Earth's shadow solely as an infinite cylinder.

Implement a physically appropriate Sun-Earth shadow model supporting: umbra, penumbra, sunlight.

The model should account for the finite angular size of the Sun.

## Current Shadow Geometry

Calculate for the station's current position and time:

- anti-solar point
- Sun altitude
- Sun azimuth
- solar depression below horizon
- Earth-shadow axis
- umbral boundary
- penumbral boundary

Calculate shadow intersection with representative orbital shells such as: 200 km, 350 km, 400 km, 550 km, 1,000 km, 1,200 km, 2,000 km.

Permit configurable orbital altitude.

The dashboard should be able to answer:

"At this azimuth and altitude in my sky, would a satellite at 550 km currently be illuminated?"

---

# 2. Zenith Satellite-Shadow Metric

Provide an immediately understandable astronomy metric such as:

```
SATELLITE SHADOW AT ZENITH
550 km shell: SUNLIT / PENUMBRA / UMBRA
```

and/or:

```
EARTH SHADOW HEIGHT AT ZENITH
<calculated altitude>
```

This represents the approximate orbital altitude at which the zenith line-of-sight crosses the relevant Earth-shadow boundary.

If appropriate, expose separate full-shadow/umbra boundary and penumbra boundary.

Do not imply that one zenith number describes the entire sky.

---

# 3. Satellite Illumination Sky Map

Provide an optional sky visualization showing the approximate Earth-shadow boundary across the observer's sky.

The actual implementation should use appropriate altitude/azimuth geometry.

Allow orbital-shell selection: 350 km, 550 km, 1,200 km, custom.

The map should visually distinguish full sunlight, penumbra, and umbra.

This should work without requiring Starlink orbital data.

---

# 4. Starlink / Satellite Photography Indicator

Add an astronomy-oriented summary:

```
SATELLITE CONTAMINATION

Sun altitude:             -18.7°
550 km zenith:            SHADOWED
550 km western horizon:   PARTLY SUNLIT
1200 km shell:            SUNLIT IN NW
Astronomical darkness:    YES
```

Example derived messages:

- "Most ~550 km LEO satellites should currently be in Earth's shadow above 45° altitude."
- "Sunlit LEO satellites remain possible in the western sky."

These must be geometric predictions, not guarantees of visible Starlink satellites.

Actual individual satellite predictions should be a separate optional feature requiring orbital-element data.

---

# 5. Optional Satellite Ephemeris Layer

Future/optional support may ingest orbital elements for Starlink, ISS, other LEO constellations, and user-selected satellites.

For an individual satellite calculate: rise, culmination, set, azimuth, altitude, range, angular velocity, illuminated state, umbra entry, penumbra entry, shadow exit, predicted visible interval.

Do not require Internet connectivity for calculations after orbital elements have been obtained.

Display age/epoch of orbital data prominently.

---

# 6. Astrophotography Darkness Status

Create a dedicated observing-status card.

Expose Sun altitude, Sun azimuth, and twilight state: DAY, CIVIL TWILIGHT, NAUTICAL TWILIGHT, ASTRONOMICAL TWILIGHT, ASTRONOMICAL NIGHT.

Show sunset, civil twilight end, nautical twilight end, astronomical twilight end, and corresponding morning events.

Also show TIME UNTIL ASTRONOMICAL DARKNESS or TIME REMAINING BEFORE ASTRONOMICAL TWILIGHT.

---

# 7. Solar Time

Implement the previously discussed solar-time functionality.

Expose:

- civil/local clock time
- UTC
- apparent solar time
- mean solar time where useful
- solar noon
- difference between clock noon and solar noon
- equation-of-time contribution where appropriate

Example:

```
CLOCK TIME            21:14:32 EDT
APPARENT SOLAR TIME   20:57:18
SOLAR OFFSET          -17m 14s
```

This is an astronomical/environmental metric and must remain distinct from the precision UTC timing system.

---

# 8. Solar Geometry

Calculate locally: solar altitude, solar azimuth, solar declination, hour angle, sunrise, sunset, solar noon, civil/nautical/astronomical twilight, daylight duration, change in daylight from previous day, change in sunrise from previous day, change in sunset from previous day.

Where useful include tomorrow's daylight change. Solstice/equinox context may be included.

---

# 9. Solar-Energy Estimate

Retain the previously proposed solar-energy feature.

Estimate theoretical clear-sky solar exposure, daylight duration, Sun elevation profile, and potential solar-energy window.

If weather/cloud data becomes available, optionally distinguish THEORETICAL SOLAR POTENTIAL from WEATHER-ADJUSTED ESTIMATE.

Never present this as calibrated photovoltaic production unless actual panel and irradiance measurements exist.

---

# 10. Learned Sky-Obstruction Map

Implement the previously proposed learned GNSS sky-obstruction model.

Over time record satellite azimuth, elevation, C/N0, constellation, used/not-used state, acquisition/loss, and time.

Build a statistical sky map representing the station's normal RF visibility.

Example:

```
EAST   Expected obstruction below ~28°
SOUTH  Mostly clear
WEST   Intermittent attenuation 10–20°
```

This is particularly useful for this station because the antenna is indoors near a window.

The system should learn the normal environment rather than treating every satellite disappearance as anomalous.

---

# 11. GNSS Integrity + Obstruction Correlation

Use the learned obstruction map as context for GNSS integrity monitoring.

- Loss of low-elevation satellites in a historically obstructed eastern sector → EXPECTED ENVIRONMENTAL LOSS
- Simultaneous C/N0 collapse among high-elevation satellites across multiple azimuths → GNSS INTEGRITY ANOMALY

This should materially reduce false jamming alerts.

---

# 12. Sky Quality / Observing Conditions

Create an optional observing dashboard integrating locally available measurements.

Potential measurements: temperature, humidity, dew point, pressure, wind, cloud estimate, precipitation, sky temperature, SQM/sky brightness, all-sky camera condition, Moon altitude/phase/illumination, Sun altitude, astronomical darkness, satellite illumination risk.

Derived astrophotography metrics may include DEW RISK (LOW / MODERATE / HIGH), ASTRONOMICAL DARKNESS (YES / NO), and SATELLITE CONTAMINATION RISK (derived from illumination geometry).

Do not fabricate weather data when sensors are unavailable.

---

# 13. Weather-Station Integration

Retain the previously scoped weather-station path.

Design an extensible sensor interface for temperature, humidity, pressure, wind speed, wind direction, rainfall, and optional solar irradiance.

Environmental observations should be timestamped against the station's precision clock.

---

# 14. All-Sky Camera

Retain all-sky-camera support in the roadmap.

Possible uses: cloud detection, sky-condition history, meteor detection, satellite trail detection, aircraft detection, aurora detection where applicable, twilight monitoring, validation of predicted satellite illumination, validation of learned sky obstruction.

Images should not be required for normal NTP operation.

Heavy computer-vision processing belongs on optional analysis infrastructure where appropriate.

---

# 15. SDR / Radio-Time Layer

Retain SDR as a formal roadmap component.

Potential observations include WWV/WWVH, other appropriate time broadcasts, ADS-B, weather satellites, radiosondes, lightning networks/signals where practical, and experimental RF monitoring.

Time observations from independent systems can eventually provide useful cross-checks against GNSS.

---

# 16. Independent Time References

Where supported, compare GNSS/PPS, Internet NTP, radio time, RTC, and system oscillator.

Do not treat all sources as having equivalent accuracy.

The UI should show both CURRENTLY SELECTED SOURCE and INDEPENDENT REFERENCES.

This can eventually provide another useful input to GNSS-integrity analysis.

---

# 17. ADS-B / Aircraft

Retain optional ADS-B support: nearby aircraft, aircraft tracks, altitude, range, timestamped observations, aircraft contamination of all-sky/astro images.

Advanced distributed stations may eventually explore multilateration. MLAT belongs primarily in the coordinator/distributed infrastructure tier.

---

# 18. Distributed Precision Observations

Preserve the long-term distributed-node architecture.

Multiple GPS Time Pi stations could correlate GNSS anomalies, PPS disturbances, ADS-B observations, RF events, meteor observations, satellite observations, lightning, radio signals, and other precisely timestamped transient events.

Station nodes should collect lightweight timestamped evidence. Heavy correlation belongs on optional coordinator infrastructure.

---

# 19. Dashboard "Now" Page

Create a unified NOW page. It should answer at a glance:

- TIME — UTC / local / solar
- TIMING — GPS/PPS / fallback / holdover
- GNSS — satellites / integrity
- SUN — altitude / azimuth / twilight
- DARKNESS — time until/from astronomical darkness
- EARTH SHADOW — 550 km LEO illumination state
- SATELLITES — current illumination risk
- MOON — phase / altitude / illumination
- WEATHER — temperature / humidity / dew point
- SKY — clear/cloudy if measurement exists

The user should be able to customize which modules appear.

---

# 20. Scientific Data Provenance

Every derived value should expose its provenance where appropriate.

Examples:

- Earth shadow: CALCULATED LOCALLY (station coordinates + UTC + solar ephemeris)
- Sun altitude: CALCULATED LOCALLY
- GNSS satellites: MEASURED — GPS RECEIVER
- Temperature: MEASURED — LOCAL SENSOR
- Cloud forecast: EXTERNAL DATA

This distinction is important to the scientific character of the project.

---

# 21. Offline Requirement

Core calculations should operate without Internet connectivity wherever reasonable.

Local/offline calculations should include Sun position, twilight, solar time, Earth-shadow geometry, satellite illumination geometry when orbital data is already available, GNSS state, PPS state, oscillator/holdover state, and local environmental sensors.

External services should enhance the station rather than be prerequisites.

---

# 22. Resource Tiers

**STATION / PI TIER:** PPS monitoring, GNSS monitoring, solar geometry, twilight, Earth-shadow geometry, basic satellite illumination, weather sensors, lightweight obstruction model, local dashboard, event recording.

**OPTIONAL ANALYSIS / COORDINATOR:** large historical datasets, multiple-station correlation, MLAT, advanced RF analysis, computer vision, long-term all-sky analysis, sophisticated anomaly detection, fleet-wide GNSS-integrity analysis.

This separation is mandatory so GPS Time Pi remains useful on Raspberry Pi-class hardware.

---

# Acceptance Goal

The finished station should be capable of answering questions such as:

- "What is disciplining my clock right now?"
- "Is PPS actually reaching Linux?"
- "How long have I been on failover?"
- "Is GNSS behaving normally?"
- "Is the Sun below astronomical twilight?"
- "At what orbital altitude does Earth's shadow cross my zenith?"
- "Are ~550 km LEO satellites likely to be sunlit in the part of the sky I'm photographing?"
- "When will the 550 km shell become shadowed across most of my usable sky?"
- "How much daylight did I gain or lose today?"
- "What is apparent solar time?"
- "Which portions of my GNSS sky are normally obstructed?"
- "Is today's satellite loss normal for this antenna location?"
- "How long would my clock take to drift by one second without PPS?"

The project should combine precision timekeeping with useful scientific context derived from having a precisely timed, geographically fixed observing station.
