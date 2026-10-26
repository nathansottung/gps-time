"""WGS84 geometry for slant ranges between the station and an aircraft. Pure."""

import math

A = 6378137.0                      # WGS84 semi-major axis, m
F = 1 / 298.257223563
E2 = F * (2 - F)
C = 299_792_458.0                  # speed of light, m/s
FT = 0.3048
KT = 1852 / 3600                   # knot in m/s


def ecef(lat, lon, h):
    """Geodetic (deg, deg, m above the ellipsoid) to ECEF metres."""
    la, lo = math.radians(lat), math.radians(lon)
    n = A / math.sqrt(1 - E2 * math.sin(la) ** 2)
    return ((n + h) * math.cos(la) * math.cos(lo), (n + h) * math.cos(la) * math.sin(lo), (n * (1 - E2) + h) * math.sin(la))


def slant_range(a, b):
    """Straight-line distance (m) between two (lat, lon, h) points."""
    p, q = ecef(*a), ecef(*b)
    return math.dist(p, q)


def elevation_deg(site, target):
    """Elevation of target above the site's local horizon (ellipsoid normal), degrees."""
    p, q = ecef(*site), ecef(*target)
    la, lo = math.radians(site[0]), math.radians(site[1])
    up = (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))
    d = [q[i] - p[i] for i in range(3)]
    r = math.sqrt(sum(x * x for x in d))
    return math.degrees(math.asin(sum(d[i] * up[i] for i in range(3)) / r)) if r else 90.0


def ground_distance(lat1, lon1, lat2, lon2):
    """Great-circle distance on a mean sphere, m (for plausibility checks only)."""
    la1, la2 = math.radians(lat1), math.radians(lat2)
    dla, dlo = la2 - la1, math.radians(lon2 - lon1)
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * 6371008.8 * math.asin(min(1.0, math.sqrt(h)))
