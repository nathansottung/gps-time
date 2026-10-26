"""Positions never reach storage in the skeleton.

SPEC-COORDINATOR: exact positions are used only with the owner's consent, and
members see approximate positions. The skeleton has no consent handling yet,
so it removes anything that looks like a position from every event, at any
depth, and counts what it removed.
"""

POSITION_KEYS = frozenset({
    "lat", "lon", "lng", "latitude", "longitude", "alt", "alt_msl", "alt_hae", "altitude", "height",
    "position", "site", "location", "ecef", "x_ecef", "y_ecef", "z_ecef",
})


def strip_positions(obj):
    """(copy without position keys, number of keys removed)."""
    if isinstance(obj, dict):
        out, n = {}, 0
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in POSITION_KEYS:
                n += 1
                continue
            out[k], m = strip_positions(v)
            n += m
        return out, n
    if isinstance(obj, list):
        out, n = [], 0
        for v in obj:
            c, m = strip_positions(v)
            out.append(c)
            n += m
        return out, n
    return obj, 0
