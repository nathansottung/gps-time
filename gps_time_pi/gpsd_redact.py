"""Remove the station's position from gpsd JSON before it goes into an evidence archive.

Used by scripts/capture-pps-evidence.sh. Standard library only, and runnable as a
plain file (``python3 -I gpsd_redact.py``), so it works even when the station's
venv or service is broken.

By default every position field is removed, in every privacy mode: timing
evidence never needs the position. ``--include-position`` keeps what the
station's location privacy mode allows on screen (exact: as received; rounded:
1 decimal of latitude/longitude and MSL altitude to 10 m; hidden: nothing).
In hidden mode satellite azimuth/elevation are also removed, as in
``config.privacy_sats``. Lines that are not JSON objects (NMEA, gpsd errors) are
dropped, because they may carry the position.
"""

import argparse
import json
import sys

MODES = ("exact", "rounded", "hidden")

# Fields that give the position, or narrow it down (geoid separation and magnetic
# variation both depend on where the receiver is). Removed at any depth.
POSITION_KEYS = frozenset({
    "lat", "lon", "alt", "altHAE", "altMSL", "geoidSep", "magvar",
    "ecefx", "ecefy", "ecefz", "ecefvx", "ecefvy", "ecefvz", "ecefpAcc", "ecefvAcc",
    "relN", "relE", "relD", "base",
})
# Kept in rounded mode when --include-position is given, rounded like displayed_location().
# gpsd's deprecated "alt" is HAE or MSL depending on version, so it is never kept rounded.
ROUNDED = {"lat": 1, "lon": 1, "altMSL": -1}


def config_mode(path):
    """The location privacy mode from the station's config.json. Anything
    unreadable or unknown counts as hidden, the safest mode."""
    try:
        with open(path, encoding="utf-8") as f:
            mode = json.load(f).get("location_display", "exact")
    except (OSError, ValueError, AttributeError):
        return "hidden"
    return mode if mode in MODES else "hidden"


def _position_policy(mode, include_position):
    if not include_position or mode == "hidden":
        return "drop"
    return "keep" if mode == "exact" else "round"


def redact(obj, mode, include_position=False):
    """A copy of one gpsd JSON object with the position handled by the mode."""
    policy = _position_policy(mode, include_position)

    def walk(o):
        if isinstance(o, list):
            return [walk(v) for v in o]
        if not isinstance(o, dict):
            return o
        out = {}
        for k, v in o.items():
            if k in POSITION_KEYS and policy != "keep":
                if policy == "round" and k in ROUNDED and isinstance(v, (int, float)):
                    out[k] = round(v, ROUNDED[k])
                continue
            if mode == "hidden" and k in ("az", "el"):
                out[k] = None
                continue
            out[k] = walk(v)
        return out

    return walk(obj)


def redact_lines(lines, mode, include_position=False):
    """Yield redacted JSON lines; return (kept, dropped) counts via StopIteration value."""
    kept = dropped = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            obj = None
        if not isinstance(obj, dict):
            dropped += 1
            continue
        kept += 1
        yield json.dumps(redact(obj, mode, include_position), separators=(",", ":"))
    return kept, dropped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", help="station config.json; prints its privacy mode and exits")
    ap.add_argument("--mode", choices=MODES, default="hidden")
    ap.add_argument("--include-position", action="store_true")
    a = ap.parse_args(argv)
    if a.config:
        print(config_mode(a.config))
        return 0
    gen = redact_lines(sys.stdin, a.mode, a.include_position)
    try:
        while True:
            print(next(gen))
    except StopIteration as stop:
        kept, dropped = stop.value
    print(f"gpsd lines kept: {kept}; dropped (not JSON objects): {dropped}; "
          f"privacy mode: {a.mode}; position: {_position_policy(a.mode, a.include_position)}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
