"""Object lookup: the small curated catalog plus RA/Dec coordinate parsing.

Input classes, auto-detected:
  1. Catalog: 'M31', 'm 31', 'Andromeda', 'Vega', 'Jupiter'
  2. Coordinates (J2000/ICRS): '00h42m44s +41d16m09s',
     '00:42:44 +41:16:09', '10.684 +41.269'
  3. Anything else -> None (caller shows the format examples)
"""

import json
import os
import re

_HERE = os.path.dirname(__file__)
with open(os.path.join(_HERE, "data", "catalog.json")) as f:
    _CAT = json.load(f)

_BY_KEY = {}
for obj in _CAT["messier"]:
    _BY_KEY[obj["id"].lower()] = obj
    for n in obj["names"]:
        _BY_KEY[n.lower()] = obj
for obj in _CAT["stars"]:
    _BY_KEY[obj["id"].lower()] = obj

PLANETS = {p.lower(): p for p in _CAT["planets"]}

_HMS = re.compile(
    r"^\s*(\d{1,2})[h:\s](\d{1,2})[m:\s](\d{1,2}(?:\.\d+)?)s?\s*[,;/]?\s*"
    r"([+\-])?\s*(\d{1,3})[d°:\s](\d{1,2})[m':\s](\d{1,2}(?:\.\d+)?)[s\"]?\s*$")
_DEC = re.compile(
    r"^\s*(\d{1,3}(?:\.\d+)?)\s*[,;/\s]\s*([+\-]?\d{1,2}(?:\.\d+)?)\s*$")


def parse_radec(text):
    """Return (ra_deg, dec_deg) or None."""
    m = _HMS.match(text)
    if m:
        h, mi, s, sign, d, dm, ds = m.groups()
        ra = (float(h) + float(mi) / 60 + float(s) / 3600) * 15
        dec = float(d) + float(dm) / 60 + float(ds) / 3600
        if sign == "-":
            dec = -dec
        if 0 <= ra < 360 and -90 <= dec <= 90:
            return ra, dec
        return None
    m = _DEC.match(text)
    if m:
        ra, dec = float(m.group(1)), float(m.group(2))
        if 0 <= ra < 360 and -90 <= dec <= 90:
            return ra, dec
    return None


def lookup(query):
    """Resolve a query to a target dict, or None.

    Target kinds:
      {'kind':'planet','name':'Jupiter'}
      {'kind':'fixed','id':'M31','name':..,'ra':..,'dec':..,'type':..,'mag':..,'deepsky':bool}
      {'kind':'coords','ra':..,'dec':..}
    """
    q = query.strip()
    if not q:
        return None
    low = re.sub(r"\s+", " ", q.lower())
    if low in PLANETS:
        return {"kind": "planet", "name": PLANETS[low]}
    key = low.replace("m ", "m") if re.match(r"^m \d+$", low) else low
    hit = _BY_KEY.get(key)
    if hit is None and not key.startswith("m"):
        hit = _BY_KEY.get(next((k for k in _BY_KEY if k.startswith(key) and len(key) >= 4), ""))
    if hit:
        deepsky = hit["type"] not in ("star", "double star")
        name = hit["id"] + (" — " + hit["names"][0] if hit["names"] else "")
        return {"kind": "fixed", "id": hit["id"], "name": name, "ra": hit["ra"],
                "dec": hit["dec"], "type": hit["type"], "mag": hit["mag"],
                "con": hit["con"], "deepsky": deepsky}
    rd = parse_radec(q)
    if rd:
        return {"kind": "coords", "ra": rd[0], "dec": rd[1]}
    return None
