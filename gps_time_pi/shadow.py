"""Earth's shadow as seen from the station: where in the sky a satellite at a
given height is in sunlight, penumbra or umbra.

Model. The Sun is a disc of finite size and the Earth a sphere, so the shadow
is two cones, not a cylinder: the umbra (no part of the Sun visible) narrows
behind the Earth, and the penumbra (part of the Sun visible) widens. A point is
tested against both cones. The Sun's position comes from a compact analytic
series (Meeus, Astronomical Algorithms, ch. 25; about 0.01 degree), so this
needs no ephemeris file, no NumPy and no network.

What it is and isn't:
  - `modeled`: geometry for the present moment from a physical model.
  - Geometric only. The Earth is taken as an airless sphere of mean radius;
    the real shadow edge is blurred and shifted by the atmosphere by some tens
    of kilometres of height. Angles are not corrected for refraction.
  - It says whether a satellite at that height would be lit. It does not say
    that a satellite is there, or that a lit one is bright enough to see.

Pure functions; nothing here reads the clock, the position or a file.
"""

import math
from datetime import datetime, timezone

R_EARTH_KM = 6371.0            # mean radius: the sphere that casts the shadow
R_SUN_KM = 695700.0
AU_KM = 149597870.7
WGS84_A_KM = 6378.137
WGS84_F = 1.0 / 298.257223563
SHELLS_KM = (200, 350, 400, 550, 1000, 1200, 2000)
SHELL_MIN_KM, SHELL_MAX_KM = 100.0, 50000.0
SEARCH_LIMIT_KM = 50000.0      # zenith boundary heights are searched up to here
MAP_ALT_STEP, MAP_AZ_STEP = 2, 5
STATS_ALT_STEP, STATS_AZ_STEP = 5, 10
STATS_MIN_ALT = 10
SECTORS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

SUNLIT, PENUMBRA, UMBRA = "SUNLIT", "PENUMBRA", "UMBRA"
_CODE = {SUNLIT: "S", PENUMBRA: "P", UMBRA: "U"}

MODEL_NOTE = ("Conical umbra and penumbra of a spherical, airless Earth with the Sun as a disc of finite size. "
              "Geometric: the atmosphere blurs and shifts the real shadow edge by some tens of km of height, "
              "and angles are not corrected for refraction.")
MEANING_NOTE = ("Says whether a satellite at that height would be in sunlight. It does not say that a satellite "
                "is there, or that a sunlit one is bright enough to see.")


# ── time and the Sun ────────────────────────────────────────────────────────

def julian_date(when):
    """Julian Date (UTC) of a timezone-aware datetime."""
    return when.astimezone(timezone.utc).timestamp() / 86400.0 + 2440587.5


def gmst_deg(jd):
    """Greenwich mean sidereal time in degrees (Meeus 12.4; UT1 taken as UTC)."""
    t = (jd - 2451545.0) / 36525.0
    return (280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * t * t - t ** 3 / 38710000.0) % 360.0


def sun_equatorial(jd):
    """Apparent right ascension and declination of the Sun in degrees, and its
    distance in au (Meeus ch. 25, low-accuracy series)."""
    t = (jd - 2451545.0) / 36525.0
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    m = math.radians(357.52911 + 35999.05029 * t - 0.0001537 * t * t)
    e = 0.016708634 - 0.000042037 * t - 0.0000001267 * t * t
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(m)
         + (0.019993 - 0.000101 * t) * math.sin(2 * m) + 0.000289 * math.sin(3 * m))
    true_long = l0 + c
    nu = m + math.radians(c)
    dist = 1.000001018 * (1 - e * e) / (1 + e * math.cos(nu))
    omega = math.radians(125.04 - 1934.136 * t)
    lam = math.radians(true_long - 0.00569 - 0.00478 * math.sin(omega))
    eps = math.radians(23.0 + (26.0 + (21.448 - 46.8150 * t - 0.00059 * t * t + 0.001813 * t ** 3) / 60.0) / 60.0
                       + 0.00256 * math.cos(omega))
    ra = math.degrees(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))) % 360.0
    dec = math.degrees(math.asin(math.sin(eps) * math.sin(lam)))
    return ra, dec, dist


def sun_ecef(when):
    """(unit vector to the Sun in the Earth-fixed frame, distance in km)."""
    jd = julian_date(when)
    ra, dec, dist_au = sun_equatorial(jd)
    lon = math.radians(ra - gmst_deg(jd))        # longitude of the subsolar point
    d = math.radians(dec)
    return (math.cos(d) * math.cos(lon), math.cos(d) * math.sin(lon), math.sin(d)), dist_au * AU_KM


# ── vectors and the observer ────────────────────────────────────────────────

def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _add(a, b, k=1.0):
    return (a[0] + k * b[0], a[1] + k * b[1], a[2] + k * b[2])


def _norm(a):
    return math.sqrt(_dot(a, a))


class Observer:
    """A place on the WGS 84 ellipsoid: Earth-fixed position (km) and local east/north/up axes."""

    def __init__(self, lat_deg, lon_deg, height_m=0.0):
        lat, lon = math.radians(lat_deg), math.radians(lon_deg)
        e2 = WGS84_F * (2 - WGS84_F)
        n = WGS84_A_KM / math.sqrt(1 - e2 * math.sin(lat) ** 2)
        h = (height_m or 0.0) / 1000.0
        self.pos = ((n + h) * math.cos(lat) * math.cos(lon), (n + h) * math.cos(lat) * math.sin(lon),
                    (n * (1 - e2) + h) * math.sin(lat))
        self.east = (-math.sin(lon), math.cos(lon), 0.0)
        self.north = (-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat))
        self.up = (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))
        self.radius = _norm(self.pos)

    @classmethod
    def from_site(cls, site):
        height = site.get("alt_hae")
        if height is None:
            height = site.get("alt_msl")
        return cls(site["lat"], site["lon"], height or 0.0)

    def direction(self, az_deg, alt_deg):
        """Unit vector toward an azimuth (from north, through east) and altitude."""
        az, alt = math.radians(az_deg), math.radians(alt_deg)
        ce, cn, cu = math.cos(alt) * math.sin(az), math.cos(alt) * math.cos(az), math.sin(alt)
        return tuple(ce * self.east[i] + cn * self.north[i] + cu * self.up[i] for i in range(3))

    def altaz(self, vec):
        """(azimuth, altitude) in degrees of a direction vector (any length)."""
        n = _norm(vec)
        alt = math.degrees(math.asin(max(-1.0, min(1.0, _dot(vec, self.up) / n))))
        az = math.degrees(math.atan2(_dot(vec, self.east), _dot(vec, self.north))) % 360.0
        return az, alt


# ── the shadow ──────────────────────────────────────────────────────────────

def cone_angles(sun_dist_km):
    """Half-angles (radians) of the umbra and penumbra cones."""
    return (math.asin((R_SUN_KM - R_EARTH_KM) / sun_dist_km),
            math.asin((R_SUN_KM + R_EARTH_KM) / sun_dist_km))


def shadow_state(point_km, sun_unit, sun_dist_km):
    """(state, sunlit fraction) of a point given in Earth-centred km.

    The fraction is 1 in sunlight, 0 in the umbra, and in the penumbra a linear
    estimate across its width: an approximation, not the exact area of the
    Sun's disc that is visible."""
    s = _dot(point_km, sun_unit)
    x = -s                                                   # distance behind the Earth's centre
    a_u, a_p = cone_angles(sun_dist_km)
    # Each cone touches the Earth along a circle: the penumbra's slightly on the
    # sunward side of the centre, the umbra's slightly behind it. Sunward of the
    # first there is no shadow; the umbra exists only behind the second.
    x_pen_start = -R_EARTH_KM * math.sin(a_p)
    x_umbra_start = R_EARTH_KM * math.sin(a_u)
    if x <= x_pen_start:
        return SUNLIT, 1.0
    rho = _norm(_add(point_km, sun_unit, -s))
    r_umbra = R_EARTH_KM / math.cos(a_u) - x * math.tan(a_u)
    r_penumbra = R_EARTH_KM / math.cos(a_p) + x * math.tan(a_p)
    if rho >= r_penumbra:
        return SUNLIT, 1.0
    if x < x_umbra_start:
        # between the two circles, close to the ground: the Sun is partly below the horizon
        return PENUMBRA, max(0.0, min(1.0, (x_umbra_start - x) / (x_umbra_start - x_pen_start)))
    if r_umbra > 0.0 and rho <= r_umbra:
        return UMBRA, 0.0
    lo = max(r_umbra, 0.0)
    return PENUMBRA, max(0.0, min(1.0, (rho - lo) / (r_penumbra - lo)))


def shell_point(obs, az_deg, alt_deg, shell_km):
    """Where the line of sight meets the shell `shell_km` above the observer's
    ground level: (Earth-centred point in km, range in km)."""
    u = obs.direction(az_deg, alt_deg)
    radius = obs.radius + shell_km
    b = _dot(obs.pos, u)
    disc = b * b - (obs.radius ** 2 - radius ** 2)
    rng = -b + math.sqrt(disc)
    return _add(obs.pos, u, rng), rng


def state_at(obs, az_deg, alt_deg, shell_km, sun_unit, sun_dist_km):
    point, rng = shell_point(obs, az_deg, alt_deg, shell_km)
    state, fraction = shadow_state(point, sun_unit, sun_dist_km)
    return state, fraction, rng


def zenith_boundaries(obs, sun_unit, sun_dist_km, limit_km=SEARCH_LIMIT_KM):
    """Heights above the observer where the zenith line of sight leaves the
    umbra and where it reaches full sunlight.

    Returns {'umbra_top_km', 'penumbra_top_km', 'ground_state', 'beyond_limit'}.
    A height is None when that boundary isn't crossed: in daylight (no shadow
    overhead), or when the line of sight is still in shadow at `limit_km`."""
    def state(h):
        return shadow_state(_add(obs.pos, obs.up, h), sun_unit, sun_dist_km)[0]

    def top(inside):
        """Greatest height h with inside(state(h)), assuming it holds from the ground up."""
        if not inside(state(0.0)):
            return None
        if inside(state(limit_km)):
            return float("inf")
        lo, hi = 0.0, limit_km
        for _ in range(60):
            mid = (lo + hi) / 2
            if inside(state(mid)):
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    ground = state(0.0)
    umbra = top(lambda s: s == UMBRA)
    penumbra = top(lambda s: s != SUNLIT)
    beyond = umbra == float("inf") or penumbra == float("inf")
    fix = lambda v: None if v is None or v == float("inf") else round(v, 1)   # noqa: E731
    return {"umbra_top_km": fix(umbra), "penumbra_top_km": fix(penumbra),
            "ground_state": ground, "beyond_limit": beyond}


def sky_grid(obs, shell_km, sun_unit, sun_dist_km, alt_step=MAP_ALT_STEP, az_step=MAP_AZ_STEP, min_alt=0):
    """State of the shell over the sky: one string per altitude ring (from
    `min_alt` up to 90), one character per azimuth step: S, P or U."""
    alts = list(range(min_alt, 91, alt_step))
    azs = list(range(0, 360, az_step))
    rows = []
    for alt in alts:
        rows.append("".join(_CODE[state_at(obs, az, alt, shell_km, sun_unit, sun_dist_km)[0]] for az in azs))
    return {"shell_km": shell_km, "alt_step_deg": alt_step, "az_step_deg": az_step,
            "alts_deg": alts, "azs_deg": azs, "rows": rows}


def _sector(az):
    return SECTORS[int(((az + 22.5) % 360) // 45)]


def shell_summary(obs, shell_km, sun_unit, sun_dist_km):
    """One shell over the sky above STATS_MIN_ALT degrees."""
    grid = sky_grid(obs, shell_km, sun_unit, sun_dist_km, STATS_ALT_STEP, STATS_AZ_STEP, STATS_MIN_ALT)
    weight_all = weight_lit = 0.0
    lit_sectors, max_lit_alt, min_dark_alt = [], None, None
    for alt, row in zip(grid["alts_deg"], grid["rows"]):
        w = math.cos(math.radians(alt)) or 1e-9          # solid angle of a ring cell
        for az, code in zip(grid["azs_deg"], row):
            weight_all += w
            if code != "U":
                weight_lit += w if code == "S" else 0.5 * w
                if _sector(az) not in lit_sectors:
                    lit_sectors.append(_sector(az))
                max_lit_alt = alt if max_lit_alt is None else max(max_lit_alt, alt)
            else:
                min_dark_alt = alt if min_dark_alt is None else min(min_dark_alt, alt)
    zenith = state_at(obs, 0.0, 90.0, shell_km, sun_unit, sun_dist_km)[0]
    fraction = weight_lit / weight_all
    lit_sectors.sort(key=SECTORS.index)
    if max_lit_alt is None:
        text = f"In Earth's shadow everywhere above {STATS_MIN_ALT}°."
    elif min_dark_alt is None:
        text = f"Sunlit everywhere above {STATS_MIN_ALT}°."
    elif max_lit_alt >= 90:
        text = f"Sunlit over part of the sky, including overhead ({', '.join(lit_sectors)})."
    else:
        text = (f"In Earth's shadow above {max_lit_alt}° altitude; sunlit positions remain possible lower in the "
                f"{', '.join(lit_sectors)}.")
    return {"altitude_km": shell_km, "zenith": zenith,
            "sunlit_sky_fraction": round(fraction, 3),
            "sunlit_max_altitude_deg": max_lit_alt,
            "sunlit_sectors": lit_sectors,
            "summary": text}


def twilight(sun_alt_deg):
    """Name of the present twilight stage from the Sun's geometric altitude."""
    if sun_alt_deg > -0.833:
        return "day"
    if sun_alt_deg > -6:
        return "civil twilight"
    if sun_alt_deg > -12:
        return "nautical twilight"
    if sun_alt_deg > -18:
        return "astronomical twilight"
    return "night"


def valid_shell(value):
    """A shell height in km from user input, or None if it isn't usable."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and SHELL_MIN_KM <= v <= SHELL_MAX_KM else None


def report(site, when, map_shell_km=550.0, query=None, shells=SHELLS_KM):
    """The /api/shadow payload for a site ({'lat', 'lon', ...}) and a UTC time.

    query: optional (azimuth, altitude) in degrees: is a satellite at
    `map_shell_km` in that direction sunlit?"""
    obs = Observer.from_site(site)
    sun_unit, sun_dist = sun_ecef(when)
    sun_az, sun_alt = obs.altaz(sun_unit)
    a_u, a_p = cone_angles(sun_dist)
    zen = zenith_boundaries(obs, sun_unit, sun_dist)
    all_shells = sorted(set(float(s) for s in shells) | {float(map_shell_km)})
    summaries = [shell_summary(obs, s, sun_unit, sun_dist) for s in all_shells]
    stage = twilight(sun_alt)

    if zen["ground_state"] == SUNLIT:
        zen_note = "The Sun is up: there is no Earth shadow overhead."
    elif zen["beyond_limit"]:
        zen_note = f"The zenith line of sight is still in shadow at {SEARCH_LIMIT_KM:g} km."
    else:
        zen_note = ("Height at which the line straight up leaves the shadow. One number for the zenith only: "
                    "the boundary is lower toward the Sun and higher away from it.")

    out = {
        "available": True, "reason": None,
        "provenance": "modeled",
        "model": MODEL_NOTE, "meaning": MEANING_NOTE,
        "as_of_utc": when.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "sun": {"altitude_deg": round(sun_alt, 2), "azimuth_deg": round(sun_az, 2),
                "depression_deg": round(-sun_alt, 2) if sun_alt < 0 else 0.0,
                "distance_au": round(sun_dist / AU_KM, 6),
                "antisolar": {"azimuth_deg": round((sun_az + 180.0) % 360.0, 2), "altitude_deg": round(-sun_alt, 2)},
                "note": "geometric altitude, no refraction; analytic solar position, about 0.01°"},
        "darkness": {"stage": stage, "astronomical_darkness": sun_alt <= -18.0},
        "cone": {"umbra_half_angle_deg": round(math.degrees(a_u), 4),
                 "penumbra_half_angle_deg": round(math.degrees(a_p), 4),
                 "umbra_length_km": round(R_EARTH_KM / math.sin(a_u)),
                 "axis": "from the Earth's centre toward the anti-solar point"},
        "zenith": {**zen, "search_limit_km": SEARCH_LIMIT_KM, "note": zen_note},
        "shells": summaries,
        "map": sky_grid(obs, float(map_shell_km), sun_unit, sun_dist),
        "query": None,
    }
    if query is not None:
        az, alt = query
        state, fraction, rng = state_at(obs, az, alt, float(map_shell_km), sun_unit, sun_dist)
        out["query"] = {"azimuth_deg": az, "altitude_deg": alt, "shell_km": float(map_shell_km),
                        "state": state, "sunlit_fraction": round(fraction, 3), "range_km": round(rng, 1),
                        "note": "sunlit fraction inside the penumbra is a linear estimate"}
    out["messages"] = contamination_messages(out)
    return out


def contamination_messages(rep):
    """Plain-language lines for the contamination card. Geometric statements only."""
    msgs = []
    by = {s["altitude_km"]: s for s in rep["shells"]}
    stage = rep["darkness"]["stage"]
    if stage == "day":
        return ["The Sun is up: satellites are sunlit, and the sky is too bright for this to matter."]
    for km, name in ((550.0, "~550 km LEO"), (1200.0, "~1200 km")):
        s = by.get(km)
        if not s:
            continue
        if s["sunlit_max_altitude_deg"] is None:
            msgs.append(f"Satellites at {name} should be in Earth's shadow over the whole sky above {STATS_MIN_ALT}°.")
        elif s["sunlit_sky_fraction"] >= 0.999:
            msgs.append(f"Satellites at {name} are sunlit over the whole sky.")
        elif s["sunlit_max_altitude_deg"] >= 90:
            msgs.append(f"Satellites at {name} are still sunlit over part of the sky, including overhead "
                        f"({', '.join(s['sunlit_sectors'])}).")
        else:
            msgs.append(f"Most satellites at {name} should be in Earth's shadow above "
                        f"{s['sunlit_max_altitude_deg']}° altitude; sunlit ones remain possible in the "
                        f"{', '.join(s['sunlit_sectors'])}.")
    msgs.append("These are geometric predictions from the shadow model, not sightings: they don't say that a "
                "satellite is there or that it is bright enough to record.")
    return msgs


def now_utc():
    return datetime.now(timezone.utc)
