# GPS TIME PI — WEB DASHBOARD EXPANSION PLAN

**Date:** September 2, 2026  
**Purpose:** Product/UI specification for expanding the existing GPS-disciplined Stratum-1 Raspberry Pi timing dashboard into a more complete local timing, GNSS, astronomy, and system-health instrument.

---

## 1. Executive summary

The existing GPS Time Pi dashboard already has a strong core identity:

- large human-readable server clock
- GPS reference status
- Stratum 1 status
- current system-clock offset
- root dispersion
- satellite counts
- CPU temperature
- chrony source status
- per-satellite GNSS information
- source statistics
- NTP client information
- plain-text and JSON endpoints

The next stage should **not** turn the dashboard into a generic Raspberry Pi admin panel.

The strongest direction is to make it feel like a **purpose-built time and position instrument**:

> A GPS-disciplined Stratum-1 time server that can answer, at a glance, not only **what time it is**, but **how well it knows the time, where it is, what the sky is doing, and whether the timing solution can be trusted.**

The most useful expansion areas are:

1. human-readable timing quality
2. synchronization state and fault visibility
3. GPS/GNSS position and receiver health
4. holdover behavior
5. astronomical/ephemeris information derived locally from time + position
6. historical stability data
7. NTP-client visibility
8. local-first privacy and offline operation
9. stronger explanation of what each timing number actually means

---

# 2. Current as-built dashboard

The current interface already exposes the following.

## Main dashboard

- current server time
- selected timezone
- GPS reference
- Stratum 1
- current clock offset
- root dispersion
- satellites used / visible
- CPU temperature
- chrony sources
- brief explanation that the server is disciplined by GPS PPS

## GNSS section

Per-satellite data including:

- constellation/system
- satellite ID
- elevation
- azimuth
- signal level

The current page also reports a timing DOP value.

## NTP client section

Currently exposes:

- host
- NTP packets
- dropped packets
- last seen

## Source statistics

Raw chrony-style source statistics expose:

- sample count
- retained runs
- measurement span
- frequency
- frequency skew
- offset
- standard deviation

## Machine-readable access

The page already indicates availability of:

- plain text at `/time`
- JSON at `/api`

This is a very good foundation and should remain.

---

# 3. Design philosophy

The dashboard should answer three questions at three different depths.

## In two seconds

> **Is this clock synchronized?**

A user should be able to determine this without interpreting chrony syntax.

## In ten seconds

> **How good is the current timing solution?**

The page should make timing quality readable without counting decimal places.

## In one minute

> **Why is the clock behaving this way?**

Detailed GNSS, PPS, chrony, oscillator, network, and historical information should be available when needed.

This creates a layered interface:

**Status → Quality → Diagnostics**

---

# 4. Main dashboard redesign

The current dashboard is already visually strong. The goal should be refinement, not redesign.

A proposed hero layout:

```text
10:38:42.785
Wednesday, September 2, 2026 · EDT
UTC 14:38:42.785

● SYNCHRONIZED
STRATUM 1 · GPS/PPS

System clock       157 ns slow
PPS uncertainty    ±203 ns
Root dispersion    13.147 µs
Last PPS            1 s ago
Satellites          8 used / 20 visible
CPU                  56.5 °C
```

Below this, the existing sources table can remain.

---

# 5. Human-readable timing units

This should be one of the first changes.

Do not require users to count zeros.

Instead of:

```text
0.000000157 seconds
```

display:

```text
157 ns
```

and optionally show the raw seconds value underneath or in a tooltip:

```text
0.000000157 s
```

Suggested automatic unit selection:

| Magnitude | Display |
|---|---|
| >= 1 s | seconds |
| >= 1 ms | milliseconds |
| >= 1 µs | microseconds |
| < 1 µs | nanoseconds |

Examples:

```text
8 ns fast
157 ns slow
13.147 µs
3.73 ms
```

Internally, retain full precision.

---

# 6. Synchronization state

The dashboard should expose a clear global timing state.

Recommended states:

- **SYNCHRONIZED**
- **ACQUIRING**
- **HOLDOVER**
- **DEGRADED**
- **UNSYNCHRONIZED**
- **NO GPS FIX**
- **PPS LOST**

Example:

```text
● SYNCHRONIZED
GPS/PPS · Stratum 1
```

If GPS disappears:

```text
● HOLDOVER
GPS PPS lost 04m 18s ago
```

If chrony loses synchronization:

```text
● UNSYNCHRONIZED
Do not use this server as an authoritative time source
```

The page should never require the user to infer the overall health state from `*`, `?`, or `-` source symbols.

---

# 7. Explain chrony source symbols

The raw chrony symbols are useful for technical users but opaque to everyone else.

Provide a legend or human-readable badge.

Examples:

```text
* GPS       SELECTED
+ server    COMBINED
- server    AVAILABLE
? NMEA      NOT SELECTABLE
x source    FALSE TICKER
~ source    TOO VARIABLE
```

If NMEA is deliberately configured only for time-of-day acquisition and not precision timing, label it explicitly:

```text
NMEA
TIME-OF-DAY ONLY
Not used for precision synchronization
```

This avoids a large NMEA offset looking like a malfunction.

---

# 8. Timing quality section

Add a compact timing-quality panel.

Recommended fields:

## System clock offset

Current difference between the system clock and chrony's current reference estimate.

Display:

```text
157 ns slow
```

Do not describe this as guaranteed absolute UTC accuracy.

## Last offset

Most recent measured source offset.

## RMS offset

A long-term measure of synchronization performance.

This may be more informative than a single excellent instantaneous reading.

## Root dispersion

Keep this, but explain it.

Suggested tooltip:

> Accumulated estimated uncertainty between this system and its synchronization root. This is not the same thing as a direct ±UTC accuracy guarantee.

## Root delay

Expose alongside root dispersion.

## Update interval

How frequently chrony is currently updating the system clock estimate.

## Leap status

Possible states:

- Normal
- Insert second
- Delete second
- Unsynchronized

## Reference ID

Example:

```text
Reference ID: GPS
```

or the current PPS source identifier.

---

# 9. Oscillator and clock-discipline information

This would make the appliance much more interesting technically.

Expose:

- current frequency correction
- residual frequency
- skew / uncertainty
- estimated drift rate
- clock update interval
- current slew rate, if useful
- kernel PPS status
- hardware timestamping status, if present

Example:

```text
OSCILLATOR

Frequency correction     -2.318 ppm
Residual frequency       +0.004 ppm
Estimated skew           0.009 ppm
Clock update interval    16 s
```

A small explanation can say:

> Frequency correction is chrony's estimate of how fast or slow the local oscillator would run without discipline.

---

# 10. PPS status

PPS deserves its own explicit health state because it is the core precision reference.

Recommended fields:

```text
PPS LOCKED
Last pulse             0.4 s ago
Current offset         -221 ns
Estimated uncertainty  ±203 ns
PPS samples            377 reach
```

Possible PPS states:

- LOCKED
- ACQUIRING
- LOST
- UNSTABLE
- REJECTED

If the kernel or hardware reports edge timestamp information, expose it under an advanced section.

---

# 11. Holdover mode

Holdover could become one of the most distinctive features of the system.

When PPS disappears, the server should clearly transition into a holdover state.

Example:

```text
HOLDOVER

GPS PPS lost          07m 42s ago
Last valid fix        10:31:09 EDT
Clock maintained by   learned oscillator correction

Estimated drift       0.009 ppm
Predicted uncertainty ±4.2 µs
```

When GPS returns:

```text
GPS/PPS REACQUIRED

Holdover duration       07m 42s
Clock error at recovery +3.7 µs
Maximum predicted error ±4.2 µs
```

Possible historical metrics:

- longest holdover
- average drift during holdover
- largest reacquisition correction
- number of PPS interruptions
- total GPS uptime

This would allow a user to deliberately disconnect the antenna and test oscillator behavior.

---

# 12. GPS/GNSS location

If the receiver provides a valid position fix, expose:

- latitude
- longitude
- altitude/elevation
- fix type
- position age
- estimated horizontal accuracy
- estimated vertical accuracy
- speed
- course, if meaningful
- constellation mix

Suggested display:

```text
LOCATION

Latitude         38.921700° N
Longitude        77.066900° W
Elevation        92 m MSL
GNSS height      59 m WGS84
Fix              3D
Position age     2 s
```

Exact numbers above are examples only.

---

# 13. Elevation reference must be explicit

Do not display a generic:

```text
Elevation: 59 m
```

unless the reference datum is known.

GNSS altitude may refer to ellipsoid height while users expect elevation above mean sea level.

If available, show both:

```text
Elevation above MSL       92 m
WGS84 ellipsoid height    59 m
Geoid undulation N       −33 m
```

If only one is available, label it correctly.

---

# 14. Location privacy controls

Location is useful but can become sensitive if the dashboard is exposed outside the LAN or included in screenshots.

Provide:

```text
LOCATION DISPLAY

[ Exact ]
[ Rounded ]
[ Hidden ]
```

Suggested behavior:

### Exact

Full receiver coordinates.

### Rounded

Example:

```text
38.92° N, 77.07° W
```

Accurate enough for astronomical calculations while reducing precision in the UI.

### Hidden

No coordinates displayed to browser users, but local astronomical calculations may continue using the internal exact position.

Consider separate control:

```text
Expose exact coordinates through /api
[ On / Off ]
```

---

# 15. GNSS receiver status

Add a compact receiver-health panel.

Potential fields:

```text
GNSS

Fix                 3D
PPS                 Locked
Satellites          8 used / 20 visible
TDOP                1.83
HDOP                0.92
VDOP                1.47
Receiver mode       GPS + GLONASS
Antenna             OK
Position age        1 s
```

Only show values actually supported by the receiver/gpsd.

---

# 16. Satellite visualization

The existing satellite table should remain.

A future enhancement could add a **sky plot** based on existing azimuth/elevation data.

Suggested visualization:

- circular horizon plot
- center = zenith
- edge = horizon
- north at top
- satellite IDs at their azimuth/elevation
- constellation indicated by shape or label
- signal strength optionally represented by point size
- used satellites visually distinguished from visible-but-unused satellites

This should remain diagnostic rather than decorative.

---

# 17. Signal quality

Potential GNSS signal statistics:

- strongest satellite
- weakest used satellite
- average C/N0 or reported signal level
- satellites above threshold
- satellites excluded
- constellation counts

Example:

```text
SIGNAL

Used satellites          8
Visible satellites      20
Average used signal     27 dB
Strongest               GPS 15 · 36 dB
Weakest used            GPS 23 · 19 dB
```

---

# 18. Astronomy / ephemeris page

This is a natural extension of the system because it has both:

- precise time
- geographic position

The astronomical calculations should preferably happen **locally**, without relying on a cloud API.

Recommended page title:

# Ephemeris

Possible subtitle:

> Sun, Moon, twilight, and local astronomical time calculated from the server's GPS position and disciplined clock.

---

# 19. Sun information

Recommended values:

## Daily events

- sunrise
- solar noon
- sunset
- day length

## Twilight

- civil dawn
- sunrise
- solar noon
- sunset
- civil dusk
- nautical dusk
- astronomical dusk
- astronomical dawn
- nautical dawn

## Current position

- solar altitude
- solar azimuth

Example:

```text
SUN

Sunrise                 06:38:12
Solar noon              13:07:51
Sunset                  19:37:28
Daylight                12h 59m 16s

Civil twilight ends     20:04
Nautical twilight ends  20:37
Astronomical dusk       21:11

Current altitude        +34.2°
Current azimuth         224.1°
```

---

# 20. Daylight and darkness durations

Derived values:

- total daylight
- total civil twilight
- total nautical twilight
- total astronomical twilight
- astronomical darkness duration
- time until sunrise
- time until sunset
- time until astronomical darkness

Example:

```text
DAYLIGHT

Daylight                 12h 59m
Astronomical darkness     8h 14m
Sunset in                 8h 42m
Dark sky begins in        10h 16m
```

---

# 21. Golden hour and blue hour

These are useful for photography and visually fit the purpose of a location-aware timing instrument.

Possible values:

- morning blue hour
- morning golden hour
- evening golden hour
- evening blue hour

Avoid pretending there is a single universal definition.

The settings page could expose which solar altitude thresholds are being used.

Example:

```text
PHOTOGRAPHIC LIGHT

Morning blue hour      05:55–06:22
Morning golden hour    06:22–07:17
Evening golden hour    18:58–19:52
Evening blue hour      19:52–20:19
```

---

# 22. Moon information

Recommended values:

- moonrise
- lunar transit / culmination
- moonset
- current lunar altitude
- current lunar azimuth
- phase name
- illumination percentage
- moon age
- angular separation from Sun
- waxing / waning
- distance, optionally
- apparent angular diameter, optionally

Example:

```text
MOON

Phase                   Waning Gibbous
Illumination            73.2%
Age                      19.4 days

Moonrise                 21:42
Transit                  04:21
Moonset                  11:03

Current altitude        -17.4°
Current azimuth          71.0°
```

---

# 23. Next lunar events

Potential additions:

```text
NEXT LUNAR EVENTS

Last Quarter      Sep 4 · 14:51 UTC
New Moon          Sep 11 · 03:27 UTC
First Quarter     Sep 18 · 19:44 UTC
Full Moon         Sep 26 · 08:12 UTC
```

These should be calculated from a trustworthy astronomical library rather than hardcoded approximation formulas if high accuracy is desired.

---

# 24. Local sidereal time

This is particularly appropriate for a GPS timing instrument.

Expose:

- Greenwich Mean Sidereal Time
- Local Mean Sidereal Time
- optionally apparent sidereal time

Example:

```text
SIDEREAL TIME

GMST        09:42:18
LMST        04:31:07
```

A tooltip can explain:

> Local sidereal time represents the right ascension currently crossing the local meridian and is useful for astronomy.

---

# 25. Solar time

Potential values:

- apparent solar time
- mean solar time
- equation of time
- solar noon offset from civil noon

Example:

```text
SOLAR TIME

Local mean solar time      10:23:41
Apparent solar time        10:19:13
Equation of time           -4m 28s
```

This is another elegant connection between precise time and longitude.

---

# 26. Seasonal astronomical information

Potential annual information:

- next equinox
- next solstice
- current season
- solar declination
- day-length trend
- earliest sunset
- latest sunset
- earliest sunrise
- latest sunrise

Example:

```text
SEASON

Autumn equinox          in 20d 09h
Daylight change         -2m 31s/day
```

---

# 27. Solar and lunar event countdowns

Useful live countdowns could include:

```text
NEXT EVENTS

Sunset                  08h 42m
Civil dusk              09h 09m
Astronomical darkness   10h 16m
Moonrise                11h 47m
```

This creates a highly usable field reference.

---

# 28. Optional planetary information

This should be secondary, not part of the main dashboard.

A future astronomy page could show for major planets:

- rise
- transit
- set
- altitude
- azimuth
- constellation
- magnitude
- angular separation from Sun

Objects:

- Mercury
- Venus
- Mars
- Jupiter
- Saturn

This starts to approach planetarium territory, so it should remain optional.

---

# 29. Polaris / celestial pole information

For astronomy-oriented use:

- altitude of north celestial pole
- azimuth of true north
- Polaris altitude/azimuth
- local magnetic declination only if sourced from a local model with known date validity

This could be useful for tripod/mount setup but should not distract from the timing role.

---

# 30. Timezone handling

The device should distinguish:

1. UTC
2. server system timezone
3. location-derived timezone
4. browser-selected display timezone

Recommended UI:

```text
DISPLAY TIMEZONE
America/New_York

GPS-derived timezone
America/New_York

UTC
14:38:42.785
```

Automatic timezone detection from latitude/longitude may require a local timezone boundary database.

Avoid sending GPS coordinates to an external timezone API if local operation is a design goal.

---

# 31. UTC should always be visible

Even if the large clock is user-selectable, keep UTC permanently visible somewhere.

Example:

```text
10:38:42.785 EDT
UTC 14:38:42.785
```

A Stratum-1 timing appliance should never hide UTC behind a menu.

---

# 32. Browser clock disclaimer

Keep the existing distinction between:

- actual server timing state
- browser-rendered human clock

Suggested text:

> **About the clock display:** The clock above is estimated in the browser for human viewing. Browser scheduling and network latency limit the visible clock to approximately millisecond-level accuracy. Nanosecond and microsecond timing figures below are reported directly by the server timing subsystem.

This is important because the visible web clock cannot prove the nanosecond-scale timing performance reported by chrony/PPS.

---

# 33. Historical timing graphs

One of the strongest future improvements would be short rolling history.

Recommended charts:

## System clock offset

Time ranges:

- 5 minutes
- 1 hour
- 24 hours
- 7 days
- 30 days

## PPS offset

Plot measured PPS offset over time.

## Frequency correction

Shows oscillator drift and discipline behavior.

## Root dispersion

Tracks changes in uncertainty.

## Satellite count

Used and visible satellites over time.

## CPU temperature

Useful for determining oscillator sensitivity to temperature.

Important correlation:

> Temperature vs oscillator correction

This could reveal whether the Pi's local oscillator frequency changes measurably as temperature changes.

---

# 34. Temperature / oscillator correlation

A particularly interesting diagnostics page could correlate:

- CPU temperature
- board temperature, if available
- oscillator frequency correction
- PPS offset
- ambient temperature, if future hardware supports it

Potential output:

```text
OSCILLATOR THERMAL BEHAVIOR

Current temperature        56.5 °C
Current correction         -2.318 ppm
24h correction range       0.041 ppm
Temp/frequency correlation 0.82
```

This could help characterize holdover performance.

---

# 35. Long-term stability statistics

Potential derived metrics:

- mean PPS offset
- median PPS offset
- RMS offset
- standard deviation
- 95th percentile
- 99th percentile
- maximum observed offset
- minimum observed offset
- mean absolute error
- uptime in synchronization
- PPS availability percentage

For more serious timekeeping analysis, consider optional:

- Allan deviation
- modified Allan deviation
- time deviation (TDEV)
- maximum time interval error (MTIE)

These are more specialized and belong under an advanced "Clock Stability" page.

---

# 36. Timing performance summary

A compact daily summary could be useful:

```text
LAST 24 HOURS

Synchronized uptime       99.998%
Mean PPS offset             14 ns
RMS PPS offset             221 ns
95th percentile            402 ns
Maximum offset             1.7 µs
PPS interruptions            0
```

This is more meaningful than one excellent instantaneous number.

---

# 37. NTP client visibility

The existing client section is a good start.

Enhance it with:

- hostname
- IP address
- first seen
- last seen
- packet count
- dropped packets
- request rate
- IPv4 / IPv6
- authenticated / unauthenticated, if applicable
- last request offset information if available

Example:

```text
NTP CLIENTS

nas.example
192.0.2.20
Packets: 84,201
Last seen: 3 s ago

workstation.example
192.0.2.30
Packets: 13,292
Last seen: 12 s ago
```

---

# 38. NTP service statistics

Potential service-level information:

- total requests served
- requests per minute
- unique clients
- malformed packets
- denied packets
- rate-limited packets
- IPv4 requests
- IPv6 requests
- NTS requests, if future support is added

---

# 39. NTS support

If the server eventually supports Network Time Security, expose:

```text
NTS
Enabled

Certificates valid until:
2027-08-14
```

This is optional and should not complicate an otherwise simple LAN appliance.

---

# 40. Network status

A compact diagnostics section could show:

- hostname
- LAN IP
- IPv6 address
- interface
- link speed
- packet errors
- default route
- DNS state
- NTP port listening
- uptime

Do not let this turn into a generic router dashboard.

Only expose values relevant to reliable time service.

---

# 41. System health

Recommended:

```text
SYSTEM

Hostname          ntp1
Uptime            43d 18h 21m
CPU temperature   56.5 °C
CPU load          4%
Memory            31%
Storage           22%
chronyd           Running
gpsd              Running
PPS device        Present
```

Add warnings only when thresholds matter.

---

# 42. Power and reboot history

If available:

- last boot
- unexpected shutdown detected
- undervoltage events
- thermal throttling
- filesystem state

Raspberry Pi-specific status could include:

- under-voltage flags
- frequency-capping flags
- throttling flags

These can matter because unstable power could undermine appliance reliability.

---

# 43. GPS outage history

Keep an event log:

```text
2026-09-02 08:14:22  PPS lost
2026-09-02 08:14:22  Entered holdover
2026-09-02 08:19:41  PPS reacquired
2026-09-02 08:19:42  Synchronized
```

Store:

- outage start
- outage end
- duration
- clock correction at recovery
- satellite count at failure/recovery

---

# 44. Event log

Other useful events:

- boot
- chrony start
- gpsd start
- GNSS fix acquired/lost
- PPS acquired/lost
- synchronization acquired/lost
- leap-second state change
- network interface down/up
- high temperature
- under-voltage
- time step performed
- configuration changed

---

# 45. Warnings and alerting

The webpage should surface warnings before external notification systems are added.

Examples:

```text
WARNING
GPS fix available but PPS has not been received for 12 seconds.
```

```text
WARNING
System is in holdover.
Estimated timing uncertainty is increasing.
```

```text
CRITICAL
chronyd is not synchronized.
```

Possible later notifications:

- email
- webhook
- MQTT
- Home Assistant
- syslog
- SNMP

These should be optional.

---

# 46. Local-first architecture

A strong design principle:

> The appliance should remain fully useful without Internet access.

Core functions should work locally:

- GPS synchronization
- PPS discipline
- NTP serving
- location
- timezone resolution, if database installed locally
- sunrise/sunset
- twilight
- Moon calculations
- sidereal time
- ephemeris calculations
- historical graphs
- local API

Internet NTP sources can remain sanity checks or fallback references without becoming required for normal operation.

---

# 47. No-cloud astronomy

Avoid passing exact GPS coordinates to third-party APIs merely to obtain astronomy information.

Prefer local calculation of:

- sunrise
- sunset
- twilight
- solar position
- lunar position
- lunar phase
- moonrise/moonset
- sidereal time

Advantages:

- privacy
- no dependency on API availability
- works offline
- faster
- reproducible
- consistent with the appliance's purpose

---

# 48. API expansion

The existing `/api` endpoint could evolve into versioned sub-endpoints.

Possible structure:

```text
/api/v1/time
/api/v1/status
/api/v1/chrony
/api/v1/pps
/api/v1/gnss
/api/v1/location
/api/v1/satellites
/api/v1/astronomy
/api/v1/clients
/api/v1/system
/api/v1/history
/api/v1/events
```

---

# 49. Example API payload

Example only:

```json
{
  "time": {
    "utc": "2026-09-02T14:38:42.785123456Z",
    "unix": 1788369522.785123456,
    "timezone": "America/New_York"
  },
  "sync": {
    "state": "synchronized",
    "stratum": 1,
    "reference": "GPS/PPS",
    "system_offset_ns": -157,
    "root_dispersion_ns": 13147,
    "pps_age_ms": 420
  },
  "gnss": {
    "fix": "3d",
    "satellites_used": 8,
    "satellites_visible": 20,
    "tdop": 1.83
  }
}
```

Do not force nanosecond precision into JSON if the underlying source does not genuinely supply it.

---

# 50. Machine-readable `/time`

Keep `/time`.

Possible enhancement:

```text
2026-09-02T14:38:42.785123456Z
```

Optional query parameters:

```text
/time?format=iso
/time?format=unix
/time?format=rfc3339
/time?zone=America/New_York
```

For automation, the endpoint should remain simple and stable.

---

# 51. Prometheus metrics

Optional advanced feature:

```text
/metrics
```

Potential metrics:

```text
gps_time_sync_state
gps_time_system_offset_seconds
gps_time_root_dispersion_seconds
gps_time_pps_offset_seconds
gps_time_satellites_used
gps_time_satellites_visible
gps_time_cpu_temperature_celsius
gps_time_holdover_seconds
gps_time_ntp_requests_total
```

This would make Grafana integration straightforward.

---

# 52. Home Assistant / MQTT

Optional future integration:

MQTT topics could expose:

```text
gpsclock/status
gpsclock/time
gpsclock/offset
gpsclock/pps
gpsclock/satellites
gpsclock/sunrise
gpsclock/sunset
gpsclock/moonrise
gpsclock/moonset
```

This should remain entirely optional and disabled by default.

---

# 53. CLI status

A local CLI companion could provide:

```bash
gps-time status
gps-time gnss
gps-time sources
gps-time astronomy
gps-time clients
gps-time holdover
```

Example:

```text
SYNCED · STRATUM 1 · GPS/PPS
Offset: 157 ns slow
PPS: locked
Satellites: 8/20
Root dispersion: 13.147 µs
```

This is not required for the webpage, but it would make the appliance pleasant to administer over SSH.

---

# 54. Display modes

Potential UI modes:

## Simple

Only:

- time
- UTC
- synchronization state
- offset
- GPS state

## Standard

Default dashboard.

## Advanced

Adds:

- chrony internals
- oscillator data
- source statistics
- PPS diagnostics
- network diagnostics

This avoids making casual users stare at timing-engineering terminology.

---

# 55. Tooltips / inline education

Small explanations would dramatically improve usability.

Examples:

### Stratum

> Stratum 1 means this server synchronizes directly to a reference clock rather than another NTP server.

### PPS

> GPS pulse-per-second provides the precision timing edge used to discipline the system clock.

### Clock offset

> Chrony's current estimate of the difference between the system clock and its reference time.

### Root dispersion

> Estimated accumulated timing uncertainty to the synchronization root.

### TDOP

> A measure of satellite geometry as it affects the timing solution. Lower values generally indicate better geometry.

---

# 56. Avoid claiming absolute nanosecond UTC accuracy

This is important.

The interface may legitimately report values such as:

```text
8 ns fast
157 ns slow
```

But those numbers should be described as measured or estimated offsets within the timing system.

Avoid language like:

```text
UTC accuracy: ±8 ns
```

unless the full system has actually been characterized against an independent, traceable reference.

The dashboard should distinguish:

- current correction
- source offset
- statistical variation
- estimated uncertainty
- guaranteed absolute accuracy

Those are not interchangeable.

---

# 57. Data provenance

For every advanced number, consider exposing where it came from.

Example:

```text
System offset
Source: chronyc tracking

PPS offset
Source: chronyc sources

Position
Source: gpsd

Satellite data
Source: gpsd SKY

CPU temperature
Source: Linux thermal subsystem
```

This makes the appliance feel trustworthy and debuggable.

---

# 58. Raw-data access

Keep raw views for technical users.

Potential buttons:

```text
View chronyc tracking
View chronyc sources
View chronyc sourcestats
View gpsd TPV
View gpsd SKY
```

Raw data can be shown in monospace without forcing it onto the main dashboard.

---

# 59. Data freshness

Every major panel should know how old its data is.

Examples:

```text
Updated 0.4 s ago
Last PPS 0.8 s ago
Position 2 s old
Satellite data 1 s old
```

If a value is stale, visually mark it.

Never continue displaying old timing data as though it is live.

---

# 60. Quality-state thresholds

Instead of arbitrary green/yellow/red rules, define thresholds deliberately.

Possible categories:

```text
Excellent
Good
Degraded
Unreliable
Unavailable
```

But the timing thresholds should be configurable or derived from actual application requirements.

Avoid implying that, for example, "500 ns = bad" unless there is a meaningful reason.

---

# 61. Dark mode

A timing instrument would work extremely well in dark mode.

Potential use cases:

- observatory
- telescope setup
- nighttime field use
- server room

Consider:

- automatic system theme
- manually selectable dark mode
- optional extra-low-light "observatory" mode

An observatory mode could reduce brightness and avoid large bright white areas.

---

# 62. Night-vision mode

Optional future feature:

```text
DISPLAY MODE
Standard
Dark
Observatory
```

Observatory mode could:

- minimize emitted brightness
- simplify animation
- reduce visual clutter
- optionally use a red-biased palette

This is only worthwhile if the dashboard will actually be used around telescopes or dark-adapted users.

---

# 63. Full-screen instrument mode

Provide a full-screen clock view.

Example:

```text
14:38:42.785
UTC

GPS/PPS LOCKED
STRATUM 1

+157 ns
```

Useful for:

- lab bench
- wall display
- observatory
- network operations screen

---

# 64. Mobile layout

On phones, prioritize:

1. time
2. sync state
3. current offset
4. GPS/PPS state
5. astronomy "today"
6. diagnostics below

Do not shrink desktop tables until they become unreadable.

Convert source and satellite rows to responsive cards where necessary.

---

# 65. Accessibility

Important basics:

- never encode timing health using color alone
- preserve sufficient contrast
- use labels in addition to icons
- keyboard navigation
- readable numerical fonts
- tabular numerals for clocks and measurements
- screen-reader labels for live status
- avoid excessively rapid live-region updates

---

# 66. Precision formatting

Use tabular digits where possible.

Keep decimal precision meaningful.

Examples:

```text
157 ns
13.147 µs
0.009 ppm
56.5 °C
1.83 TDOP
```

Do not show ten decimal places merely because the backend can.

---

# 67. Clock rendering behavior

Potential best practice:

- server sends a timestamp
- browser estimates current server time between updates
- periodic resynchronization prevents browser drift
- visible precision limited appropriately
- page explicitly labels browser estimate

Do not update via a network request every millisecond.

---

# 68. Status page health hierarchy

Suggested warning order:

## Critical

- chrony unsynchronized
- PPS unavailable beyond threshold
- no valid time reference
- time step required
- clock error exceeds configured limit

## Warning

- holdover
- low satellite count
- degraded geometry
- GPS fix intermittent
- excessive temperature
- under-voltage

## Informational

- fallback NTP source selected
- antenna reacquired
- network source unavailable
- location changed

---

# 69. Location-change detection

For a normally stationary appliance, a large GPS location change could indicate:

- the device was physically moved
- a stale/invalid GNSS solution
- antenna/receiver problems
- spoofing or severe multipath

Potential message:

```text
LOCATION CHANGED

Previous position:
38.9217, -77.0669

Current position:
38.8895, -77.0353

Distance:
6.9 km
```

This should be informational unless there is a specific threat model.

---

# 70. GNSS anomaly indicators

Optional advanced diagnostics:

- sudden position jump
- impossible velocity for a stationary installation
- abrupt satellite constellation change
- large PPS phase jump
- disagreement between GNSS and Internet NTP
- receiver reports invalid time
- leap information disagreement

These should be framed as diagnostics, not definitive spoofing detection.

---

# 71. Reference cross-checking

Internet NTP servers can act as rough sanity checks even when GPS/PPS remains authoritative.

Example:

```text
REFERENCE CROSS-CHECK

GPS/PPS            selected
NIST               +3.7 ms
Cloudflare         +3.5 ms
Other peers        within expected WAN uncertainty
```

The UI should make it clear that Internet peers have much larger network uncertainty and are not expected to match PPS at nanosecond scale.

---

# 72. Geographic astronomy page layout

Potential layout:

```text
EPHEMERIS

Location
38.9217° N · 77.0669° W
92 m MSL

TODAY
Sunrise          06:38
Solar noon       13:08
Sunset           19:37
Astronomical dark 21:11

MOON
Waning Gibbous
73.2% illuminated
Moonrise         21:42
Moonset          11:03

NOW
Sun              +34.2° · 224.1°
Moon             -17.4° · 71.0°

TIME
UTC              14:38:42
LMST             04:31:07
```

This keeps it instrument-like rather than turning it into a weather app.

---

# 73. Calendar / table view

Optional ephemeris table:

| Date | Sunrise | Sunset | Daylight | Astro Dark | Moonrise | Moonset | Illumination |
|---|---:|---:|---:|---:|---:|---:|---:|
| Sep 2 | 06:38 | 19:37 | 12h59m | 8h14m | 21:42 | 11:03 | 73% |
| Sep 3 | ... | ... | ... | ... | ... | ... | ... |

Useful ranges:

- 7 days
- 30 days

No need to provide a year-long almanac by default.

---

# 74. Exportable astronomy data

Potential endpoints:

```text
/api/v1/astronomy/today
/api/v1/astronomy/now
/api/v1/astronomy/2026-09-02
```

Optional calendar export:

```text
/ephemeris.ics
```

Could include:

- sunrise
- sunset
- astronomical dusk
- moonrise
- moonset

This is optional but potentially useful.

---

# 75. GPS-derived location versus manual location

Provide a setting:

```text
LOCATION SOURCE

● GNSS receiver
○ Manual coordinates
```

Why manual mode may be useful:

- GPS antenna is remote from the user
- server is indoors
- astronomy is desired for a different observing site
- GPS receiver does not produce position
- user intentionally hides exact appliance position

Astronomy calculations should clearly state which location source they are using.

---

# 76. Location lock

For a stationary time server, consider:

```text
Lock astronomical location to current GPS position
```

This stores a known-good location and prevents temporary GNSS errors from moving the astronomy calculations around.

The live GPS position can still be shown separately.

---

# 77. Configuration page

Suggested settings:

## Time

- default display timezone
- 12/24-hour clock
- fractional-second display
- UTC always visible

## Location

- GPS / manual
- exact / rounded / hidden
- latitude format
- altitude units

## Astronomy

- show/hide photography light
- local/UTC event display
- astronomical library/model information

## Dashboard

- Simple / Standard / Advanced
- update rate
- dark mode

## API

- enabled
- exact location exposure
- API token, if ever needed

---

# 78. Units settings

Allow:

```text
Distance / elevation
Metric / Imperial

Coordinates
Decimal degrees / DMS

Temperature
°C / °F
```

Timing units should remain SI automatically:

- s
- ms
- µs
- ns

---

# 79. Device identity

A small About page could show:

```text
GPS TIME PI

Hostname          ntp1
Software version  1.0.0
OS                ...
chrony            ...
gpsd              ...
Receiver          ...
PPS device        ...
Boot time         ...
```

Also include links or text identifying:

- open-source licenses
- project repository, if public
- build/version identifier
- configuration export

---

# 80. Self-test page

A one-click diagnostics page could report:

```text
TIME SERVER SELF TEST

[PASS] chronyd running
[PASS] gpsd running
[PASS] PPS device available
[PASS] GNSS 3D fix
[PASS] PPS selected
[PASS] Stratum 1
[PASS] System synchronized
[PASS] NTP port listening
[PASS] Network reachable
[PASS] CPU temperature normal
```

This could make troubleshooting much easier.

---

# 81. Startup/acquisition timeline

After reboot, showing the acquisition sequence would be useful:

```text
10:00:03  gpsd started
10:00:05  GNSS receiver detected
10:00:21  2D fix acquired
10:00:25  3D fix acquired
10:00:26  PPS detected
10:00:29  chrony synchronized
```

This helps identify slow antenna lock or PPS problems.

---

# 82. Time-to-fix metrics

Optional:

- cold-start time to first fix
- time to 3D fix
- time to PPS lock
- time to chrony synchronization

Could be especially useful after reboot testing or antenna changes.

---

# 83. Antenna diagnostics

If supported by receiver hardware:

- antenna present
- antenna open circuit
- antenna short
- active antenna power state

If unsupported, do not infer it from signal levels.

---

# 84. Geographic map

A map is not necessary for the local dashboard.

Coordinates are more useful and more privacy-preserving.

If a map is added later, it should be:

- optional
- local or privacy-preserving
- disabled by default if it requires third-party tiles

Avoid leaking coordinates to a map provider merely by loading the page.

---

# 85. Weather should probably remain separate

The server knows time and position, but it does **not** inherently know weather.

Avoid automatically turning this into a weather dashboard unless local sensor hardware is added.

If future sensors exist, local environmental data could be useful:

- ambient temperature
- pressure
- humidity
- barometric trend

These could affect oscillator characterization and astronomy planning, but they are outside the core time-server mission.

---

# 86. Atmospheric astronomy, optional

If local pressure and temperature sensors are later added, astronomical calculations could optionally compensate for:

- atmospheric refraction
- apparent horizon effects

This should be advanced and clearly labeled.

---

# 87. Camera / photography-oriented data

Because sunrise/sunset data naturally supports photographers, optional fields could include:

- golden hour
- blue hour
- Sun azimuth at sunrise
- Sun azimuth at sunset
- Moon azimuth at moonrise/moonset
- Moon illumination
- Moon-Sun angular separation

A very useful line:

```text
Sunset
19:37 · Azimuth 277.4°
```

Likewise:

```text
Moonrise
21:42 · Azimuth 74.1°
```

---

# 88. Shadow information

Optional:

- current Sun altitude
- theoretical shadow-length ratio

Example:

```text
Sun altitude      34.2°
Shadow ratio      1.47× object height
```

Useful but not essential.

---

# 89. Astronomical precision disclosure

Like the timing data, astronomy should indicate calculation provenance.

Example:

```text
Solar/lunar positions calculated locally using [library/model].
Times include standard atmospheric-refraction assumptions.
Location: GPS-derived.
```

This keeps the system transparent.

---

# 90. Leap seconds

A dedicated time appliance should expose leap-second awareness.

Potential panel:

```text
LEAP STATUS
Normal
```

If a leap second is pending:

```text
LEAP SECOND PENDING

UTC leap second insertion scheduled:
202X-XX-XX 23:59:60 UTC
```

Only display when supported by the timing source/software.

---

# 91. GPS week / GNSS time

Advanced page could expose:

- GPS week
- time-of-week
- GPS time
- UTC offset from GPS time

This is useful for technical diagnostics but should stay out of the normal dashboard.

---

# 92. TAI

For serious timing enthusiasts, optionally expose:

- UTC
- TAI
- GPS time

Example:

```text
TIME SCALES

UTC       14:38:42
TAI       ...
GPS       ...
```

This should be clearly explained and kept under advanced settings.

---

# 93. Julian date

Astronomy page could expose:

- Julian Date
- Modified Julian Date

Example:

```text
JD   246...
MJD  6....
```

Useful for astronomy and scientific workflows.

---

# 94. Unix and other machine time formats

Optional technical page:

```text
Unix time
1788369522.785

RFC 3339
2026-09-02T14:38:42.785Z

NTP era/seconds
...
```

This is especially useful for software developers testing time-sensitive applications.

---

# 95. Precision clock comparison mode

Future advanced feature:

Allow the user to compare:

- system clock
- GPS/PPS reference
- Internet NTP peers

Display offsets on a common scale.

This could make the dashboard educational without conflating the accuracy of each source.

---

# 96. Source history

For each NTP source:

- uptime
- reach history
- average offset
- min/max offset
- standard deviation
- last successful reply
- current state

Clicking a source could open a detail panel.

---

# 97. Network-path awareness

For Internet NTP peers, expose round-trip delay.

This helps users understand why:

```text
GPS PPS   ±200 ns
NIST      ±30 ms
```

are not contradictory.

The WAN source has a much larger uncertainty due to network transit.

---

# 98. Data retention

Suggested defaults:

## High-rate data

PPS/offset samples:

- retain raw for 24–72 hours

## Downsampled data

- 1-minute aggregates for 30 days
- hourly aggregates for 1 year

This keeps storage modest.

---

# 99. Database choice

If history is implemented, a small local database is sufficient.

Potential approaches:

- SQLite
- round-robin database
- lightweight time-series store

Avoid introducing a heavy external database dependency unless needed.

---

# 100. Failure behavior

The page should degrade honestly.

Examples:

## GPS unavailable

```text
GPS DATA UNAVAILABLE
Last valid data 22 seconds ago
```

## chrony unavailable

```text
TIMING ENGINE UNAVAILABLE
chronyd is not responding
```

## astronomy unavailable

```text
ASTRONOMY UNAVAILABLE
No valid location is available
```

Never silently reuse stale values without labeling them.

---

# 101. Recommended navigation

Possible top navigation:

```text
Time
GNSS
Ephemeris
Clients
History
Diagnostics
Settings
```

Or a simpler layout:

```text
Overview
Sky
History
Advanced
```

The current minimalist visual identity should remain.

---

# 102. Proposed page structure

## Overview

- clock
- UTC
- sync state
- Stratum
- offset
- PPS status
- root dispersion
- GPS summary
- CPU temperature
- source summary

## GNSS

- fix
- location
- DOP
- satellite count
- satellite table
- sky plot

## Ephemeris

- Sun
- twilight
- Moon
- local sidereal time
- next events

## Clients

- NTP clients
- request counts
- service statistics

## History

- clock offset
- PPS offset
- frequency correction
- root dispersion
- temperature
- satellite count

## Diagnostics

- raw chrony
- raw gpsd
- network state
- system health
- event log
- self-test

## Settings

- timezone
- units
- location privacy
- display modes
- API settings

---

# 103. Suggested implementation priorities

## Phase 1 — Improve interpretation

Low effort, high value:

- display offsets in ns/µs/ms automatically
- explicit synchronized state
- UTC permanently visible
- chrony source legend
- root delay
- RMS offset
- leap status
- PPS age
- explain key metrics with tooltips

## Phase 2 — GNSS position

- latitude
- longitude
- correctly labeled altitude
- fix type
- position age
- DOP values
- location privacy controls

## Phase 3 — Astronomy

- sunrise/sunset
- solar noon
- civil/nautical/astronomical twilight
- daylight duration
- solar altitude/azimuth
- moonrise/moonset
- Moon phase/illumination
- lunar altitude/azimuth
- local sidereal time

## Phase 4 — Holdover

- holdover detection
- holdover timer
- oscillator frequency/skew
- predicted uncertainty
- reacquisition statistics
- holdover event history

## Phase 5 — History

- offset graphs
- PPS graphs
- oscillator correction
- root dispersion
- temperature
- satellite count
- daily statistics

## Phase 6 — Advanced integration

- Prometheus
- MQTT
- Home Assistant
- webhook alerts
- self-test
- event log
- NTS
- advanced stability metrics

---

# 104. Features that should remain out of scope initially

Avoid diluting the product.

Do not prioritize:

- general weather forecasts
- news
- generic system administration
- package manager UI
- file browser
- router functionality
- generic GPS navigation
- full planetarium software
- cloud account system

The appliance should remain about:

**time + timing quality + position + sky geometry + service health**

---

# 105. Product identity

The dashboard has the opportunity to become more than a web wrapper around chrony.

A useful internal product statement:

> **GPS Time Pi is a local-first precision time and position appliance. It disciplines its system clock from GNSS PPS, serves Stratum-1 NTP to the local network, exposes the quality and health of that timing solution, and derives useful astronomical information directly from its authoritative time and geographic position.**

A shorter UI description:

> **GPS-disciplined Stratum-1 time, position, and ephemeris.**

---

# 106. Core trust principle

The interface should be rigorous about the difference between:

- what the server measures
- what chrony estimates
- what GNSS reports
- what the browser displays
- what the system can actually guarantee

This means:

- report `157 ns slow` when chrony says so
- do not call that `±157 ns UTC accuracy`
- show PPS statistical uncertainty separately
- show root dispersion separately
- label browser time as a millisecond-class visual estimate
- show stale-data age
- expose source provenance
- never hide degraded timing state

This will make the dashboard feel like a real instrument rather than a decorative clock.

---

# 107. Success criteria

The finished interface should allow someone unfamiliar with chrony to answer:

1. Is the server synchronized?
2. Is GPS available?
3. Is PPS working?
4. Is the system Stratum 1?
5. How far is the system clock currently offset?
6. How stable has it been over time?
7. What timing source is selected?
8. Are backup NTP sources available?
9. Where does the GNSS receiver think it is?
10. How many satellites are being used?
11. When is sunrise/sunset at this location?
12. When does astronomical darkness begin?
13. What is the Moon doing?
14. Is the server currently in holdover?
15. Are LAN clients actually using it?
16. Is the hardware healthy?
17. Is the information live or stale?
18. Where did each number come from?

If the dashboard can answer all of these while retaining its current sparse visual design, it will be a very complete and unusually polished GPS time appliance.

---

# 108. Recommended next build

If development continues immediately, the strongest next increment would be:

1. **Human-readable ns/µs/ms formatting**
2. **SYNCHRONIZED / HOLDOVER / UNSYNCHRONIZED status**
3. **UTC line**
4. **PPS status + age**
5. **RMS offset + root delay + leap status**
6. **GNSS latitude/longitude/altitude**
7. **Exact / rounded / hidden location setting**
8. **Local sunrise/sunset + twilight**
9. **Moonrise/moonset + phase**
10. **Local sidereal time**

That single increment would move the project from a very good chrony status page to a distinctive **precision time + GNSS + ephemeris instrument** without requiring a fundamental redesign.
