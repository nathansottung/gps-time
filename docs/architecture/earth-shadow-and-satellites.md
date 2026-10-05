# Earth shadow and satellites

Status: implemented (`gps_time_pi/shadow.py`, `gps_time_pi/satellites.py`, `gps_time_pi/tle_fetch.py`; `/api/shadow`, `/api/satellites`; Sun & Astronomy → Earth Shadow and → Satellites in `/app/`). Requirement: `specs/ADDENDUM-SKY-SOLAR-SATELLITE.md` §1–§5. Not yet run on a Pi.

The purpose is practical: an astrophotographer wants to know whether satellites overhead are still catching the Sun.

## The shadow model (§1)

- The Sun is a disc of finite size and the Earth a sphere, so the shadow is **two cones, not a cylinder**: the umbra (none of the Sun visible) narrows behind the Earth, and the penumbra (part of the Sun visible) widens. A point is tested against both.
- The Sun's position comes from a compact analytic series (Meeus, *Astronomical Algorithms*, ch. 25; about 0.01°). So the shadow needs **no ephemeris file, no NumPy, no network**, and works when the almanac doesn't.
- Label: `modeled` (a physical model for the present moment).

What the model leaves out, stated in every payload:

- It is geometric. The Earth is an airless sphere of mean radius. The real shadow edge is blurred and shifted by the atmosphere by some tens of kilometres of height.
- Angles are not corrected for refraction.
- The sunlit fraction inside the penumbra is a linear estimate across its width, not the exact visible area of the Sun's disc.
- It says whether a satellite at that height **would be** in sunlight. It does not say that a satellite is there, or that a sunlit one is bright enough to see.

Shells: 200, 350, 400, 550, 1000, 1200 and 2000 km, plus any height from 100 to 50 000 km. A shell is that height above the station's ground level.

## Zenith metric (§2)

- "550 km shell, straight up": SUNLIT, PENUMBRA or UMBRA.
- "Earth shadow height at zenith": the height at which the line straight up leaves the umbra, and the height above which it is in full sunlight.
- The page says this is one number for the zenith only. The boundary is lower toward the Sun and higher away from it.
- In daylight there is no shadow overhead, and the page says so instead of showing a height.

## Sky map (§3)

- The chosen shell over the whole sky on a 2° × 5° grid, drawn as a polar plot (zenith at the centre, north up). Sunlight, penumbra and umbra are three colours; the penumbra is a thin band.
- Presets 350, 550 and 1200 km, and a custom height.
- Clicking the map asks the station about that direction: "at this azimuth and altitude, would a satellite at this height be sunlit?", with the distance to that point.
- No orbital data is needed.

## Contamination summary (§4)

Sun altitude; the 550 km shell at the zenith; for 550 km and 1200 km the share of the sky above 10° where the shell is sunlit and the compass sectors where that is; whether it is astronomical darkness; and one or two sentences such as "Most satellites at ~550 km LEO should be in Earth's shadow above 45° altitude; sunlit ones remain possible in the W, NW."

Every set of sentences ends by saying these are geometric predictions from the shadow model, not sightings.

## Individual satellites (§5)

Orbital elements (TLEs) are `external` data with a short useful life. They are kept in a cache directory on the station (`GTP_TLE_DIR`, default `tle/` next to `config.json`).

- **The web service never uses the network for this.** Getting elements is a separate, explicit step:

  ```sh
  cd /opt/gps-time-pi
  sudo -u gps-time venv/bin/python -m gps_time_pi.tle_fetch --group stations     # download one CelesTrak group
  sudo -u gps-time venv/bin/python -m gps_time_pi.tle_fetch --file my.tle --name mine   # or import a file, no network
  sudo -u gps-time venv/bin/python -m gps_time_pi.tle_fetch --list
  ```

  The text is validated (line length, line numbers, checksums, matching catalogue numbers) before it replaces anything, and written beside the old file and renamed. An error page or a failed download leaves the cache as it was. A group isn't downloaded again within two hours unless `--force` is given. No timer is installed; schedule it yourself if you want it.
- Once elements are in the cache, every calculation is offline.
- **The age of the elements is shown prominently**: on the cache card, on each satellite, and on the pass table. Beyond 14 days a satellite is marked unreliable.

For one satellite:

| Now (`modeled`) | Each pass in the next 24 h (`predicted`) |
|---|---|
| azimuth, altitude, range, height | rise, culmination, set: time, azimuth, altitude, range |
| angular speed across the sky | penumbra entry, umbra entry, shadow exit during the pass |
| sunlit / penumbra / umbra | the interval in which it could be seen |

"Could be seen" is geometry only: above 10°, not in the umbra, and the Sun at least 6° below the station's horizon. It says nothing about brightness, cloud or obstructions.

Propagation is SGP4 (the `sgp4` package, which Skyfield already installs). The frame rotation, the direction from the station and the shadow test are this project's own code, so passes need neither the JPL ephemeris nor NumPy. If `sgp4` can't be imported, `/api/satellites` says so.

The ISS (25544) and the Chinese station (48274) are shown first when they are in the cache. Any cached satellite can be found by name or catalogue number.

## Privacy

Shadow geometry and passes are functions of the station's position.

- `hidden`: neither is computed; the answer is `available: false` with the reason.
- `rounded`: both are computed from the rounded site (about 11 km). Pass times can be off by several seconds.
- Same rule as the almanac (`config.privacy_site`).

## Validation

- Solar position and sidereal time: Meeus's worked examples (25.a, 12.b), to the digits printed.
- Shadow cones: the known sizes of the Earth's shadow (umbra length about 1.38 million km; radius at the Moon's distance about 4600 km, penumbra about 8200 km), and hand-checked points.
- Zenith heights bracket the cylinder formula R(1/cos d − 1), with the umbra edge below it and full sunlight above.
- Satellites: direction and range against Skyfield for the same element set (within 0.05° and 1 km over 400 instants), and rise and set times that match Skyfield's `find_events` to the second. CI runs these in the station's virtual environment, with the real `sgp4`.

## Cost

`/api/shadow` evaluates about 8000 sky points per request and `/api/satellites` propagates one satellite for a day; each takes a few tenths of a second on a desktop. Answers are kept for 20 s. Neither has been timed on a Pi.
