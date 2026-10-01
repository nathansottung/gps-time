# GPS TIME PI — ALMANAC EXPANSION REVIEW

**Date:** September 2, 2026  
**Status:** Design review / pre-implementation recommendations

---

## Executive assessment

The proposed Almanac expansion is a strong v1 scope.

The overall direction is coherent with the existing appliance and does **not** yet cross into feature creep. The device already knows two things unusually well:

- authoritative time
- geographic position

Deriving local solar, lunar, sidereal, and object-position information from those two inputs is a natural extension of the product.

The strongest product framing is:

> **GPS Time Pi is a GPS-disciplined time and position instrument that can also describe the local sky from its own authoritative time and location.**

The design should remain sparse, local-first, and instrument-like rather than evolving into a general-purpose planetarium.

Several details should be revised before implementation, particularly around:

- "true darkness" terminology
- date/time semantics on the object and sky views
- Moon handling in best-viewing calculations
- data licensing language
- GPS-location persistence and caching
- supported date range
- catalog scope versus sky-rendering scope
- isolation of the astronomy dependency from the timing core

---

# 1. Night bar design

## Recommendation

**Keep the sunset → following sunrise night bar.**

This is more intuitive than a midnight-to-midnight representation because it matches how a person thinks about "tonight."

A user wants to understand:

> What happens between this evening and tomorrow morning?

not:

> What fraction of two different calendar days contains darkness?

The proposed full-height midnight marker is the correct solution to the date-boundary issue.

Example:

```text
Sunset                                      Sunrise
  |                                            |
  ├────────────── night interval ─────────────┤
                    |
                midnight
                → Sep 3
```

Rise/set labels that occur after midnight should carry their date when necessary.

Example:

```text
Moonrise
1:18 AM · Sep 3
```

## Important edge cases

The implementation should account for:

- daylight-saving transitions
- dates with no sunset
- dates with no sunrise
- continuous daylight
- continuous darkness
- missing astronomical twilight at high latitudes

The horizontal scale should be calculated in **actual elapsed UTC time** and then labeled in local civil time.

This avoids errors on 23-hour and 25-hour DST days.

The application should display explicit states such as:

```text
Sun does not set on this date.
```

```text
Sun does not rise on this date.
```

```text
Astronomical darkness does not occur tonight.
```

rather than attempting to force nonexistent events into the visualization.

---

# 2. Rename "True darkness"

## Recommendation

Replace:

> **True darkness**

with:

> **Moonless astronomical darkness**

The proposed calculation is:

- Sun below −18°
- Moon below the horizon

That is an excellent and useful metric, but "true darkness" implies the absence of all significant illumination.

Even with the Sun and Moon excluded, the sky can still contain:

- airglow
- zodiacal light
- Milky Way brightness
- aurora
- artificial light pollution
- scattered atmospheric light

The more precise label is therefore:

```text
Moonless astronomical darkness tonight
39 min · 9:03 PM–9:42 PM
```

This is rigorous, descriptive, and still immediately understandable.

---

# 3. Moon handling in "best viewing"

## Current proposal

Best viewing window:

- object altitude > ~25°
- Sun below −18°
- Moon below horizon

## Problem

A hard Moon-down requirement is too strict to represent a universal "best viewing window."

The Moon affects different targets very differently.

Examples:

- Jupiter remains easy to observe with the Moon up.
- Vega is largely unaffected.
- M101 or another low-surface-brightness galaxy can be seriously degraded by moonlight.
- A thin crescent 120° away from a bright target may be irrelevant.

A single Moon-up/Moon-down rule therefore mixes object geometry with object-specific observing sensitivity.

## Recommendation

Do not introduce a black-box observing score in v1.

Instead expose two deterministic windows.

### Dark viewing window

```text
Object altitude > 25°
AND
Sun altitude < −18°
```

### Moonless viewing window

```text
Object altitude > 25°
AND
Sun altitude < −18°
AND
Moon below horizon
```

Example result:

```text
Dark viewing window
8:41 PM–4:58 AM

Moonless viewing window
1:37 AM–4:58 AM
```

For deep-sky Messier targets, the moonless interval may be emphasized.

For planets and named bright stars, the dark interval may be the primary result.

For coordinate-only inputs, show both because the server does not know what kind of object the user entered.

This is preferable to an opaque score such as:

```text
Viewing quality: 87/100
```

which would imply a degree of astrophysical judgment the system does not actually possess.

---

# 4. Object altitude threshold

## Recommendation

**25° is a defensible inclusive threshold.**

It should not be described as "optimal altitude."

At 25° an object is usable, but atmospheric extinction, seeing, and refraction are more significant than at higher elevations.

Suggested language:

```text
Usable viewing window
Object above 25°
```

If a stricter threshold is later desired, 30° would be reasonable.

Implementation recommendation:

```python
MIN_OBJECT_ALTITUDE_DEG = 25.0
```

Keep the threshold centralized and configurable rather than scattering it through the code.

---

# 5. Seconds in daylight deltas

## Recommendation

**Keep the seconds.**

Example:

```text
−2 m 18 s vs yesterday
−2 m 20 s to tomorrow
```

The seconds are useful because the purpose of the feature is to expose the seasonal acceleration/deceleration of daylight change.

Rounding to whole minutes would destroy much of the interesting information.

The distinction that needs to be clear is:

> computational precision is not identical to observational certainty.

Sunrise and sunset calculations use a conventional apparent-horizon/refraction model. Real observed times vary because of:

- pressure
- temperature
- atmospheric refraction
- local terrain
- buildings
- observer horizon geometry

Therefore retain second-level calculations while adding a short explanatory note.

Suggested tooltip:

> Calculated using standard horizon and atmospheric-refraction assumptions. Actual observed rise/set times can vary with atmospheric conditions and the local horizon.

This preserves the precision of the model without pretending it is a guarantee of physical observation to the second.

---

# 6. Skyfield + NumPy versus stdlib-only astronomy

## Recommendation

**Use Skyfield + NumPy.**

Do not preserve the current "stdlib only" implementation identity at the expense of the astronomy subsystem.

The better architecture is:

> **Timing core: minimal and dependency-light.  
> Astronomy layer: isolated Skyfield/NumPy dependency.**

The precision NTP appliance and the Almanac have different technical requirements.

The timing core should continue operating even if the astronomy subsystem fails.

## Required failure isolation

These functions should continue working independently of Skyfield:

- chrony monitoring
- GPS/PPS synchronization
- NTP serving
- main status page
- `/time`
- core `/api`
- source tables
- NTP clients
- GNSS diagnostics

If any of the following occurs:

- NumPy import failure
- Skyfield import failure
- missing BSP ephemeris
- corrupt ephemeris file
- astronomy runtime exception

the appliance should still start normally.

The Almanac should instead show:

```text
Astronomy unavailable
Planetary ephemeris could not be loaded.
```

## Ephemeris provisioning

Do **not** allow Skyfield to silently download an ephemeris at runtime.

Preferred behavior:

1. provision the ephemeris during installation
2. store it locally
3. verify its checksum
4. load only that known file
5. never require Internet access for normal operation

This is consistent with the appliance's local-first design.

---

# 7. Theme behavior

## Recommendation

Keep the normal theme preference **per-device using localStorage**.

Do not make Night mode a global server setting by default.

A server-side theme would create undesirable behavior:

- wall display switches to Night mode
- laptop browser also unexpectedly switches
- phone inherits a display choice intended for another device

## Better approach

Use:

```text
localStorage
```

for persistent client preference.

Add an optional URL override:

```text
?theme=night
```

Potential wall-display mode:

```text
/almanac?theme=night&fullscreen=1
```

This allows a dedicated display to be configured without changing other browsers.

## Important implementation detail

Apply theme selection before the first paint.

If the browser initially renders a white page and then switches to Night mode, the user can get a bright flash at the telescope.

The selected theme should therefore be read and applied in the `<head>` before the normal page renders.

---

# 8. Night-mode wording

The proposed physiology claim should be softened.

Instead of focusing heavily on:

```text
~630 nm minimally bleaches rod photoreceptors
```

use language closer to:

> **Night mode uses a dim deep-red display intended to reduce disruption of dark adaptation. Screen brightness should still be reduced as far as practical.**

The important variable is not merely wavelength.

Brightness matters enormously.

A bright red screen can still damage adaptation.

The feature should be represented as:

> reduces disruption

not:

> preserves night vision

---

# 9. Selected date versus "current" object position

This is one of the most important specification issues.

The Almanac supports arbitrary date navigation:

```text
/almanac?date=YYYY-MM-DD
```

but the object card currently proposes:

```text
Current altitude + azimuth
```

and the chart is:

```text
Sky now
```

Those concepts become contradictory when the selected date is not today.

Example:

The user navigates to:

```text
October 14, 2032
```

What does:

```text
Current altitude
```

mean?

Current in 2026?

Current on October 14, 2032?

At midnight?

At transit?

## Recommendation

Introduce one small **observation-time control** for the object/sky section.

Example:

```text
Observation time

[ 10:00 PM ] [ Now ]
```

### Today

Default:

```text
Now
```

### Other dates

Default to an explicit local time, for example:

```text
10:00 PM
```

The important point is not the particular default.

The important point is that the time be visible and explicit.

The result then becomes:

```text
Altitude at 10:00 PM
47.2°

Azimuth
132.8°
```

and:

```text
Sky at 10:00 PM
October 14, 2032
```

Daily Sun/Moon event sections do not need this control because they are date-level calculations.

---

# 10. Supported date range

The specification currently says:

> Any date past or future

That is too broad.

The selected JPL ephemeris has a finite validity range.

The product should define a supported date interval explicitly.

Possible policies:

```text
Supported Almanac dates:
1850–2149
```

or, for a cleaner user contract:

```text
Supported Almanac dates:
1900–2100
```

The second option may be preferable because it avoids edge-case complexity around historical timezone rules and ephemeris boundaries while still offering an extremely broad useful range.

Unsupported dates should result in a clear message:

```text
Date outside supported Almanac range.
Supported dates: 1900–2100.
```

not an internal astronomy exception.

---

# 11. Astronomy data versioning

GPS can continue supplying UTC indefinitely, but astronomy calculations depend on more than UTC and a BSP file.

The appliance should have an astronomy-data/version policy.

Diagnostics should expose something like:

```text
ASTRONOMY

Skyfield version       1.xx
Planetary ephemeris    DE440s
Ephemeris range        1849–2150
Earth-orientation data updated through ...
Catalog version        ...
```

Updates can remain deliberate maintenance operations.

The appliance should not require background cloud access.

---

# 12. Catalog scope versus render scope

The proposed search catalog and the sky-chart star set are actually two different datasets.

## Search catalog

Designed for user lookup.

Suggested contents:

- 110 Messier objects
- observable planets
- ~25 named bright stars
- aliases

Example aliases:

```text
Andromeda
Andromeda Galaxy
M31
NGC 224
```

could all resolve to the same search object if desired, even if NGC itself is not otherwise indexed.

## Render catalog

Designed for the sky SVG.

If the chart shows stars down to approximately magnitude 4.5, it will need substantially more than ~25 stars.

The render dataset can still remain very small.

Suggested contents:

- stars to ~mag 4.5
- coordinates
- magnitude
- optional Bayer/Flamsteed identifier
- constellation-line endpoints

These two datasets should be treated separately in the code and documentation.

---

# 13. Planet count correction

For an Earth-based observing appliance, there are **seven other planets** visible as sky targets:

- Mercury
- Venus
- Mars
- Jupiter
- Saturn
- Uranus
- Neptune

Earth itself is not an observable sky target from Earth.

If the intended eighth object is Pluto, label it:

```text
Pluto — dwarf planet
```

rather than describing the catalog as eight planets.

---

# 14. Catalog aliases

Aliases should be a first-class part of the object catalog.

Example structure:

```json
{
  "id": "M31",
  "name": "Andromeda Galaxy",
  "aliases": [
    "Andromeda",
    "M31",
    "Messier 31"
  ],
  "type": "galaxy"
}
```

Normalization should support:

- case-insensitive matching
- optional spaces
- common punctuation differences

Examples:

```text
M31
m 31
Messier 31
Andromeda
Andromeda Galaxy
```

should all resolve cleanly.

---

# 15. Coordinate-input semantics

The UI should precisely state what raw RA/Dec means.

Recommended text next to the search field:

> **RA/Dec input interpreted as fixed J2000/ICRS coordinates.**

Coordinate-only targets generally do not provide:

- object type
- magnitude
- proper motion

Therefore result cards should avoid pretending those fields are known.

Example:

```text
Custom coordinate
RA 00h 42m 44s
Dec +41° 16′ 09″
J2000 / ICRS
```

Named stars can carry proper-motion information separately if desired.

---

# 16. Licensing language

The licensing section should be revised before being used as repository documentation.

The software repository can remain MIT while also containing data under other licenses, but those assets must retain their own licensing conditions.

## Skyfield

```text
Skyfield
MIT
```

Straightforward.

## OpenNGC-derived Messier data

If derived from OpenNGC:

```text
CC-BY-SA 4.0
```

That means the derived data asset is not simply MIT because it lives inside an MIT repository.

The repository should distinguish:

```text
Source code: MIT
Astronomical datasets: licenses listed per dataset
```

and include the required attribution/share-alike notices for the derived dataset.

## d3-celestial-derived data

The code license and the licensing/provenance of individual bundled datasets should not automatically be treated as identical.

Audit the exact constellation data file intended for redistribution.

Do not assume every astronomical dataset in a BSD-licensed code repository necessarily inherits the software license.

## Bright-star data

Do not label a dataset "public domain" without a specific, documented basis for that assertion.

If the intended source has unclear redistribution terms, either:

- find a clearly licensed replacement
- derive the small named-star set from a clearly redistributable source
- document the actual license precisely

---

# 17. Stellarium wording

Avoid:

> Stellarium data would virally relicense the MIT repository.

That is too broad.

A better statement is:

> Stellarium-related datasets were not selected because their provenance and licensing can vary by asset and would complicate redistribution of a cleanly licensed bundled dataset.

This is more accurate and avoids implying that one data file automatically relicenses unrelated source code.

---

# 18. Patent wording

Avoid the categorical statement:

```text
No patent exposure.
```

Use something more defensible:

> **No obvious patent concern has been identified for the ordinary astronomical calculations proposed here. No formal freedom-to-operate legal opinion has been performed.**

The relevant astronomy consists primarily of long-published mathematical methods and ephemeris data, so patent risk does not appear to be a practical design concern.

But product documentation should not make an absolute legal conclusion unless counsel has actually provided one.

---

# 19. GPS position failure policy

The proposed rule:

> No valid GPS fix → astronomy unavailable

is honest but probably too strict for a stationary appliance.

A GPS receiver losing its live position fix does not mean the physical server has suddenly moved.

## Better model

Distinguish:

### Live receiver position

Diagnostic GNSS output.

```text
LIVE GPS POSITION
Fix age 1 s
```

### Almanac site position

Stable position used for astronomical calculations.

```text
ALMANAC SITE
GPS-derived site position
```

If live GPS disappears:

```text
LIVE GPS POSITION
Unavailable

ALMANAC SITE
Last trusted GPS site position
Position age: 2h 14m
```

Then show a clear warning:

```text
Live GPS position unavailable.
Astronomy is using the stored trusted site position.
```

Only make astronomy completely unavailable if the appliance has never established or been given a trusted site location.

---

# 20. Site-position lock

A stationary time appliance benefits from a stable astronomical site coordinate.

Potential implementation:

1. wait for good 3D GNSS fix
2. collect position samples over a defined interval
3. reject obvious outliers
4. average or median the position
5. save as trusted Almanac site
6. continue showing live GNSS position independently

Potential UI:

```text
ALMANAC LOCATION

Source
GPS-derived locked site

Latitude
38.921700° N

Longitude
77.066900° W

Locked
Sep 2, 2026 · 10:14 AM

[ Refresh site from GPS ]
```

This also improves caching.

---

# 21. Astronomy cache keys

Do not key cached Almanac calculations to raw live GNSS coordinates.

GNSS position jitter could otherwise cause tiny coordinate changes to invalidate the cache continuously.

Use a stable site identifier or stored site coordinates.

Example cache key:

```text
date
timezone
site_version
ephemeris_version
```

Potentially:

```python
(date, site_id, timezone_name, astro_data_version)
```

This produces predictable cache behavior.

---

# 22. Elevation handling

Using both:

```text
altMSL
altHAE
```

from gpsd is the correct approach.

Display them explicitly.

Example:

```text
Elevation above MSL
92 m

WGS84 ellipsoid height
59 m
```

Do not calculate an assumed geoid separation if gpsd already supplies both values.

## Important caveat

Observer elevation does not automatically reveal the actual visible horizon.

A site at 92 m elevation may have:

- mountains
- trees
- buildings
- a nearby ridge
- an ocean horizon
- a valley wall

Therefore avoid silently modifying sunrise/set times as though "92 m MSL" means the observer has an unobstructed geometric horizon.

Any future terrain-horizon correction should be a separate feature.

---

# 23. Moon-above-horizon delta

The proposed field:

```text
Moon-above-horizon duration
delta vs yesterday
```

is less useful than the equivalent daylight delta.

The daylight delta tells an intuitive seasonal story.

Lunar rise/set behavior shifts according to the lunar day and changing lunar declination, so the day-to-day duration delta is less immediately meaningful.

## Recommendation

Keep:

```text
Moon above horizon
7h 42m
```

but drop:

```text
+17m 22s vs yesterday
```

Use that visual space for:

```text
Moonless astronomical darkness
39 min
```

which is directly actionable.

---

# 24. Static sky chart and product identity

The proposed SVG sky view still fits the product.

Recommended scope:

- static
- regenerated for selected observation time
- cardinal directions
- horizon dome
- constellation stick figures
- naked-eye stars
- Moon
- planets
- searched target
- no pan
- no zoom
- no catalog exploration

This remains an **instrument display**.

The boundary should be explicit.

Do not add in v1:

- interactive panning
- zoom
- telescope control
- eyepiece simulation
- camera field-of-view overlays
- thousands of object labels
- observing lists
- object recommendations
- constellation artwork
- sky photography layers

A useful guiding rule:

> **Show the sky state; do not become a sky browser.**

---

# 25. Why deferring NGC/IC is correct

Deferring NGC/IC is a strong product decision.

The RA/Dec input already provides the escape hatch for advanced users.

Someone looking for an obscure target can paste:

```text
RA
Dec
```

without requiring the appliance to ship tens of thousands of catalog records.

The v1 search catalog can remain:

- recognizable
- fast
- easy to license
- easy to audit
- easy to maintain

Future NGC/IC support can be evaluated independently.

---

# 26. Suggested section naming

A coherent page hierarchy could be:

```text
Almanac
├── Sun
├── Moon
├── Object
├── Sky
└── Location
```

Avoid names implying a full planetarium.

For example:

```text
Sky
```

is better than:

```text
Planetarium
```

and:

```text
Find an object
```

is better than:

```text
Object browser
```

---

# 27. Proposed object-result structure

Example:

```text
ANDROMEDA GALAXY
M31 · Galaxy · Mag 3.4

At 10:00 PM
Altitude       54.2°
Azimuth        71.8°

Rise           2:13 PM
Transit        11:47 PM · 83.1°
Set            9:24 AM · Sep 3

Dark viewing
8:41 PM–5:02 AM

Moonless viewing
1:37 AM–5:02 AM
```

For a circumpolar object:

```text
POLARIS

Circumpolar
Always above the horizon

Highest
12:11 AM · 39.4°
```

For an object that never rises:

```text
This object never rises from this latitude.
```

For a coordinate-only target:

```text
CUSTOM COORDINATE
J2000 / ICRS

RA   00h 42m 44s
Dec +41° 16′ 09″
```

Do not display blank magnitude/type fields.

---

# 28. Proposed Sun section

Example:

```text
SUN

Sunrise
6:38:12 AM

Solar noon
1:07:51 PM

Sunset
7:37:28 PM

Daylight
12h 59m 16s

−2m 18s vs yesterday
−2m 20s to tomorrow
```

Immediately below:

```text
24-hour daylight bar
```

Segments:

- night
- astronomical twilight
- nautical twilight
- civil twilight
- day

Labels:

- astronomical dawn
- sunrise
- sunset
- astronomical dusk

When viewing today, include:

```text
NOW
```

tick.

---

# 29. Proposed Moon section

Example:

```text
MOON

Waning Gibbous
73.2% illuminated
19.4 days old

Moonrise
9:42 PM

Transit
4:21 AM · Sep 3
Altitude 68.4°

Moonset
11:03 AM · Sep 3

Above horizon
13h 21m

Moonless astronomical darkness
39 min
9:03 PM–9:42 PM
```

Immediately below:

```text
night bar
sunset → following sunrise
```

with:

- evening twilight
- astronomical night
- Moon-above-horizon overlay
- midnight marker
- morning twilight
- true unshaded moonless astronomical interval

---

# 30. Proposed observation-time control

For Object + Sky:

```text
OBSERVATION TIME

[ 10:00 PM ]   [ Now ]
```

Behavior:

### Selected date = today

Default:

```text
Now
```

### Selected date != today

Default:

```text
10:00 PM local
```

The page should always state:

```text
Sky at 10:00 PM
Sep 14, 2026 · America/New_York
```

This eliminates ambiguity.

---

# 31. Location privacy

The current Exact / Rounded / Hidden model is good.

Recommended server-side behavior:

```text
Exact
Full coordinates exposed

Rounded
Coordinates exposed to ~0.1°

Hidden
Coordinates not exposed in page/API
```

Exact coordinates should still be used internally for astronomy in all modes.

Potential API control:

```text
Expose exact location through API
On / Off
```

If hidden:

```text
Location
Hidden by server setting
```

but the Almanac continues to calculate normally.

---

# 32. Local sidereal time

Keep local sidereal time in the Location section.

This feature fits the appliance unusually well because it directly connects:

- authoritative time
- longitude
- astronomy

Example:

```text
Local sidereal time
04:31:07
```

Tooltip:

> Local sidereal time indicates which right ascension is currently crossing the local meridian.

---

# 33. Recommended code structure

The proposed restructuring is sensible.

```text
server.py
chrony.py
gps.py
astro.py
catalog.json
templates/
```

Potential slightly fuller version:

```text
gps_time_pi/
├── server.py
├── chrony.py
├── gps.py
├── astro.py
├── catalog.py
├── models.py
├── templates/
├── static/
│   ├── css/
│   └── js/
└── data/
    ├── catalog.json
    ├── stars.json
    ├── constellations.json
    └── de440s.bsp
```

The exact degree of modularization should stay proportional to project size.

Do not over-engineer it into a framework simply because the single-file phase is ending.

---

# 34. Astronomy module boundary

`astro.py` should expose clean domain functions rather than leaking Skyfield objects throughout the server.

Example conceptual API:

```python
get_daily_solar_events(date, site)
get_daily_lunar_events(date, site)
get_twilight_intervals(date, site)
get_object_events(target, date, site)
get_object_position(target, timestamp, site)
get_sidereal_time(timestamp, site)
get_sky_snapshot(timestamp, site)
```

This keeps the HTTP/UI layer independent from the exact astronomy library.

If Skyfield is ever replaced later, most of the application remains unchanged.

---

# 35. Failure honesty

The existing design principle should remain:

> Never silently display stale or invalid data as current.

But distinguish between:

- stale live GPS data
- trusted stored site location
- unavailable astronomy engine
- unavailable ephemeris
- unsupported date
- invalid coordinate input

Examples:

```text
GPS position unavailable
Last live fix: 14m ago
Almanac using stored site position.
```

```text
Astronomy unavailable
Planetary ephemeris could not be loaded.
```

```text
Unable to parse object input.
Try:
M31
Vega
00:42:44 +41:16:09
10.684 +41.269
```

---

# 36. Recommended v1 scope

## Include

### Header

- date navigation
- explicit supported date range
- timezone selector
- Light / Dark / Night

### Sun

- sunrise
- solar noon
- sunset
- daylight duration
- daylight delta yesterday/tomorrow
- 24-hour twilight/daylight bar

### Moon

- phase
- illumination
- age
- moonrise
- transit + transit altitude
- moonset
- above-horizon duration
- moonless astronomical darkness
- sunset→sunrise night bar

### Object search

- Messier
- planets
- named stars
- J2000/ICRS RA/Dec input
- aliases
- current/selected-time alt/az
- rise
- transit time + altitude
- set
- dark viewing window
- moonless viewing window
- circumpolar / never-rises states

### Sky

- static SVG
- selected observation time
- cardinal points
- constellation sticks
- stars to ~mag 4.5
- Moon
- planets
- target marker

### Location

- lat/lon
- altMSL
- altHAE
- fix state
- satellites
- local sidereal time
- privacy control
- trusted Almanac site

---

# 37. Explicitly defer

Keep these out of v1:

- NGC/IC
- satellite passes
- weather
- interactive planetarium
- telescope control
- FOV simulation
- observing lists
- sky recommendations
- cloud services
- terrain-horizon modeling
- Moonlight scoring model
- automated "quality score"
- photometric sky-brightness model

These can be reconsidered later without compromising the current design.

---

# 38. Mandatory changes before implementation

The following changes should be treated as requirements rather than optional polish.

## 1. Resolve date/time semantics

Selected date cannot coexist ambiguously with "current altitude" and "Sky now."

Introduce an explicit observation time.

## 2. Rename true darkness

Use:

```text
Moonless astronomical darkness
```

## 3. Separate viewing windows

Expose:

```text
Dark viewing
Moonless viewing
```

rather than treating Moon-down as universally required.

## 4. Define supported Almanac date range

Do not promise infinite past/future dates.

## 5. Separate search catalog from sky-render catalog

~25 named stars are insufficient for a mag-4.5 sky chart.

## 6. Isolate Skyfield failure from the timing core

Astronomy must never prevent NTP/status functionality from starting.

## 7. Audit dataset licenses individually

Do not assume the software license automatically applies to bundled data.

## 8. Replace absolute patent language

Use a limited non-legal-review statement.

## 9. Introduce trusted site position

Do not disable astronomy simply because a stationary receiver temporarily loses a live fix.

---

# 39. Product identity test

The proposed design still passes the instrument test.

Each section answers one clear question.

### Time

> What time is it, and can I trust it?

### GNSS

> Where am I, and how good is the positioning/timing fix?

### Almanac

> What are the Sun and Moon doing at this location?

### Object

> When and where can I observe this coordinate?

### Sky

> Where is that object relative to the local horizon?

This is not arbitrary feature accumulation.

It is one continuous chain:

```text
GNSS
  ↓
UTC + position
  ↓
local sky geometry
  ↓
Sun / Moon / object events
```

That is a coherent product.

---

# 40. Final recommendation

Proceed with the Almanac.

The strongest version of the project is not merely:

> a Raspberry Pi NTP server with a web page

but:

> **a local-first GPS-disciplined time and position observatory that exposes its own timing quality and derives the local sky from authoritative time + location.**

The Almanac should remain constrained by three principles:

1. **Instrument, not planetarium**
2. **Derived locally, not cloud-dependent**
3. **State exactly what is known, calculated, stale, or unavailable**

With the changes in this review, the proposed v1 scope is technically coherent, visually consistent with the existing appliance, and narrow enough to remain maintainable.
