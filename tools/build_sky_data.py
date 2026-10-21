#!/usr/bin/env python3
"""Rebuild the bundled sky data from its sources, or check the bundled files against them.

    python tools/build_sky_data.py --openngc <dir> --d3 <dir> [--check]

<dir> for OpenNGC holds `database_files/NGC.csv` and `addendum.csv` (or the two files
directly); for d3-celestial it holds `data/stars.6.json`, `starnames.json` and
`constellations.lines.json` (or the files directly). Both are plain downloads from
https://github.com/mattiaverga/OpenNGC and https://github.com/ofrohn/d3-celestial; this
script never fetches anything.

Messier magnitudes are OpenNGC's V magnitude, else its B magnitude, else none (UNKNOWN).

Outputs (gps_time_pi/data/), each under its source's license (THIRD_PARTY_NOTICES.md):

  messier.json         the 110 Messier objects from OpenNGC              CC BY-SA 4.0
  catalog.json         named bright stars from d3-celestial, planets    BSD 3-Clause (stars)
  stars.json           d3-celestial stars to magnitude 4.5 (sky map)    BSD 3-Clause
  constellations.json  d3-celestial constellation lines (sky map)       BSD 3-Clause

--check compares the bundled files with what the sources would give and exits 1 on any
difference, so a hand edit can't slip in unnoticed.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "gps_time_pi" / "data"

STAR_MAG_LIMIT = 4.5         # sky-map stars
NAMED_STAR_MAG_LIMIT = 2.6   # catalog lookup: every d3-celestial star with a proper name this bright
PLANETS = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Moon", "Sun"]

# OpenNGC object types (its README) -> the wording the station shows.
OPENNGC_TYPES = {
    "*": "star", "**": "double star", "*Ass": "stellar association", "OCl": "open cluster",
    "GCl": "globular cluster", "Cl+N": "cluster with nebulosity", "G": "galaxy", "GPair": "galaxy pair",
    "GTrpl": "galaxy triplet", "GGroup": "group of galaxies", "PN": "planetary nebula",
    "HII": "H II region nebula", "DrkN": "dark nebula", "EmN": "emission nebula", "Neb": "nebula",
    "RfN": "reflection nebula", "SNR": "supernova remnant", "Nova": "nova star", "NonEx": "nonexistent object",
    "Other": "Other",
}

# OpenNGC lists some Messier numbers as duplicates ("Dup") of another object: M102 is a duplicate
# of M101 there. A duplicate takes its data from the object at the same position, with a note,
# because the name alone would otherwise point at nothing.
DUP_NOTES = {102: "listed by OpenNGC as a duplicate of M101; often identified instead with NGC 5866 (Spindle Galaxy)"}


def _find(base: Path, *names: str) -> Path:
    for n in names:
        for cand in (base / n, base / Path(n).name):
            if cand.is_file():
                return cand
    raise SystemExit(f"{Path(names[0]).name} not found under {base}")


def _hms(s: str) -> float:
    h, m, x = s.split(":")
    return (int(h) + int(m) / 60 + float(x) / 3600) * 15


def _dms(s: str) -> float:
    sign = -1 if s.startswith("-") else 1
    d, m, x = s.lstrip("+-").split(":")
    return sign * (int(d) + int(m) / 60 + float(x) / 3600)


def messier(openngc: Path, numbers=range(1, 111)) -> list[dict]:
    rows = []
    for fn in ("database_files/NGC.csv", "database_files/addendum.csv"):
        with open(_find(openngc, fn), encoding="utf-8", newline="") as f:
            rows += list(csv.DictReader(f, delimiter=";"))
    real = [r for r in rows if r["RA"] and r["Type"] != "Dup"]
    by_m = {int(r["M"]): r for r in real if r.get("M")}
    # A duplicate row is named after its own Messier number ("M102"); its M column names the
    # object it duplicates (101), so it is keyed by name.
    dups = {int(r["Name"][1:]): r for r in rows
            if r["Type"] == "Dup" and r["RA"] and r["Name"][:1] == "M" and r["Name"][1:].isdigit()}

    def obj(n: int, r: dict, names: list[str], note: str | None = None) -> dict:
        mag = r["V-Mag"] or r["B-Mag"]
        o = {"id": f"M{n}", "ra": round(_hms(r["RA"]), 4), "dec": round(_dms(r["Dec"]), 4),
             "type": OPENNGC_TYPES.get(r["Type"], r["Type"]), "mag": float(mag) if mag else None,
             "names": names, "con": r["Const"]}
        if note:
            o["note"] = note        # shown with the object; not a searchable name
        return o

    out = []
    for n in numbers:
        if n in by_m:
            r = by_m[n]
            out.append(obj(n, r, [x.strip() for x in r["Common names"].split(",") if x.strip()]))
        elif n in dups:
            d = dups[n]
            same = next((r for r in real if r["RA"] == d["RA"] and r["Dec"] == d["Dec"]), None)
            if same is None:
                raise SystemExit(f"OpenNGC M{n} is a duplicate of nothing at its position")
            out.append(obj(n, same, [], DUP_NOTES.get(n, "listed by OpenNGC as a duplicate of " + same["Name"])))
        else:
            raise SystemExit(f"OpenNGC has no M{n}")
    return out


def _d3(d3: Path, name: str):
    with open(_find(d3, f"data/{name}"), encoding="utf-8") as f:
        return json.load(f)


def _ra(lon: float) -> float:
    """d3-celestial stores RA as longitude in [-180, 180]; the station uses [0, 360)."""
    return lon % 360


def stars(d3: Path) -> list[list[float]]:
    return [[round(_ra(f["geometry"]["coordinates"][0]), 3), round(f["geometry"]["coordinates"][1], 3), f["properties"]["mag"]]
            for f in _d3(d3, "stars.6.json")["features"] if f["properties"]["mag"] <= STAR_MAG_LIMIT]


def named_stars(d3: Path) -> list[dict]:
    feats = {str(f["id"]): f for f in _d3(d3, "stars.6.json")["features"]}
    names = _d3(d3, "starnames.json")
    sel = [(feats[k], v) for k, v in names.items() if v.get("name") and k in feats
           and feats[k]["properties"]["mag"] <= NAMED_STAR_MAG_LIMIT]
    sel.sort(key=lambda fv: fv[0]["properties"]["mag"])          # stable: d3-celestial's order on ties
    return [{"id": v["name"], "ra": round(_ra(f["geometry"]["coordinates"][0]), 4),
             "dec": round(f["geometry"]["coordinates"][1], 4), "type": "star",
             "mag": f["properties"]["mag"], "names": [], "con": v.get("c", "")} for f, v in sel]


def constellations(d3: Path) -> list[dict]:
    return [{"id": f["id"], "lines": [[[round(_ra(x), 2), round(y, 2)] for x, y in line]
                                      for line in f["geometry"]["coordinates"]]}
            for f in _d3(d3, "constellations.lines.json")["features"]]


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def build(openngc: Path, d3: Path) -> dict[str, str]:
    return {
        "messier.json": _dump({"messier": messier(openngc)}),
        "catalog.json": _dump({"stars": named_stars(d3), "planets": PLANETS}),
        "stars.json": _dump(stars(d3)),
        "constellations.json": _dump(constellations(d3)),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--openngc", type=Path, required=True)
    ap.add_argument("--d3", type=Path, required=True)
    ap.add_argument("--check", action="store_true", help="compare with the bundled files; write nothing")
    a = ap.parse_args(argv)
    out = build(a.openngc, a.d3)
    bad = 0
    for name, text in out.items():
        path = DATA / name
        if a.check:
            same = path.is_file() and path.read_text(encoding="utf-8").rstrip("\n") == text
            print(f"{'same     ' if same else 'DIFFERENT'} {name}")
            bad += not same
        else:
            path.write_text(text + "\n", encoding="utf-8", newline="\n")
            print(f"wrote {path.relative_to(ROOT)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
