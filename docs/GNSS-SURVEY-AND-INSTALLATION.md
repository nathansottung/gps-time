# Fixed-site GNSS survey and installation quality

## Why this matters

GPS Time Pi has two different precision problems:

1. **Timing:** determine UTC and discipline the host clock from GNSS/PPS.
2. **Position:** determine a defensible fixed antenna/site coordinate.

They are related, but they are not the same measurement. A receiver can provide an excellent PPS while its navigation solution has meter-scale or geometry-dependent position error.

## Repeatability is not absolute accuracy

For a stationary receiver, random position scatter can be reduced by combining many independent observations. In the idealized independent-noise case, uncertainty of the mean falls approximately as 1/sqrt(N). Real GNSS errors are not independent at one-second intervals. Multipath, satellite geometry, atmospheric errors, receiver filtering and a persistent obstruction can remain correlated for minutes or hours.

Therefore GPS Time Pi must not report a tiny standard error from thousands of one-second fixes as if it were absolute position accuracy.

The software should expose at least three quantities separately:

- **Fix scatter:** how much individual navigation solutions wander.
- **Survey repeatability / statistical precision:** how stable independent time blocks are around the candidate position.
- **Absolute accuracy:** unknown unless supported by an external survey/correction/reference; do not infer it from averaging alone.

## Obstructed installations

A receiver beside a window may see only a portion of the sky. This creates two problems:

- reduced satellite geometry, often visible in DOP and the sky plot;
- persistent multipath and directional bias from the building/window environment.

A long survey can therefore converge tightly around the wrong point. The UI must warn when sky coverage is asymmetric or insufficient.

### Proposed installation-quality model

Track the visible/used satellites by azimuth and elevation over time and build a learned sky-visibility mask. Divide azimuth into sectors (for example 12 x 30-degree sectors) and track:

- observations per sector;
- time-visible per sector;
- elevation distribution;
- signal-quality distribution where available;
- satellites used vs merely visible;
- DOP / receiver error estimates;
- rejected stale or duplicate fixes.

Classify the installation using descriptive states rather than pretending to calculate a universal accuracy:

- **OPEN SKY** — broad multi-direction sky coverage over a full-day observation window.
- **PARTIALLY OBSTRUCTED** — meaningful missing sectors or consistently poor low-elevation visibility.
- **STRONGLY DIRECTIONAL** — fixes depend on a narrow azimuth range, such as a single window view.
- **INSUFFICIENT DATA** — not enough time/geometry has been observed to classify the site.

The classification thresholds should be documented and configurable before they are treated as a specification.

### User-entered installation context

During setup optionally ask:

- Antenna placement: outdoors / attic / window / indoors / other.
- Approximate clear-sky direction(s), if known.
- External antenna in use: yes/no.
- Antenna moved since last accepted survey: yes/no.

This is metadata, not a substitute for measured sky visibility. The software should eventually infer the sky mask from actual satellite history.

## Better survey estimator

Do not count every 1 Hz fix as an independent sample.

Proposed pipeline:

1. Accept only fresh, uniquely identified fixes.
2. Record quality metadata with every accepted fix.
3. Reject fixes outside configurable health/quality gates.
4. Compute short block means (initial proposal: 5-15 minute blocks).
5. Estimate repeatability from the distribution of block means, not raw 1 Hz fixes.
6. Preserve horizontal covariance and show a confidence ellipse rather than only one scalar radius.
7. Compare results across different hours and, for long surveys, different days/satellite geometries.
8. Surface directional sky-coverage warnings alongside the numerical convergence result.
9. Require explicit user acceptance before a candidate survey becomes the station's fixed site.

The exact block duration and statistical estimator should be validated with recorded datasets before being frozen.

## East-window example

For a receiver that primarily sees due east through a window, GPS Time Pi should eventually report something conceptually like:

```
Survey candidate       39.xxxxxx, -78.xxxxxx
Independent blocks     86
Raw fix scatter        ...
Block repeatability    ...
Sky coverage           STRONGLY DIRECTIONAL
Dominant visibility    E / NE / SE
Western sky            little or none observed
Absolute accuracy      NOT ESTABLISHED
Recommendation         External antenna / broader sky view for a reference-quality site
```

The candidate coordinate can still be useful for local astronomy/weather metadata. It should simply carry the installation-quality warning with it.

## Timing consequences of poor sky view

PPS timing and navigation position are different outputs. A receiver with a stable fix can still provide excellent PPS timing even when position accuracy is limited. However, poor sky view that causes fix loss, weak signals or unstable receiver operation can degrade availability and timing quality. GPS Time Pi should therefore keep separate indicators for:

- receiver connected;
- UTC/time solution valid;
- navigation fix valid;
- PPS present;
- PPS selected by chrony;
- satellite/antenna quality;
- position-survey quality.

## Precision upgrades

If a user actually needs a defensible sub-meter, decimeter or centimeter position, the project should direct them to hardware/correction approaches designed for it (multi-band GNSS, RTK/PPP, surveyed coordinates, or timing receivers with fixed-position modes). Averaging a basic single-band navigation receiver should not be marketed as a replacement for those methods.
