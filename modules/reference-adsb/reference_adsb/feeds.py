"""Aircraft from a local ADS-B decoder's aircraft.json (1090 MHz or 978 MHz UAT).

Format: the readsb / dump1090-fa / skyaware978 `aircraft.json`:
    {"now": <epoch s>, "aircraft": [{"hex", "type", "flight", "lat", "lon", "alt_geom", "alt_baro",
                                     "gs", "nac_p", "gva", "seen_pos", "mlat": [...], "tisb": [...]}, ...]}
`alt_geom` is the geometric altitude, feet above the WGS84 ellipsoid; `alt_baro` is pressure
altitude in feet, or "ground". Fields the decoder doesn't know are absent.

Only what the aircraft itself transmitted is a reference here. Positions computed by
multilateration (`type` "mlat", or `lat` listed in the `mlat` array), re-broadcast by a ground
station (TIS-B, ADS-R: `type` starting "tisb" or "adsr", or `lat` in `tisb`) or Mode S without
a position are refused: their radio signal doesn't come from where the position says.
"""

import json
from dataclasses import dataclass, field

from .geometry import FT

BANDS = {1090: {"frequency_hz": 1090e6, "bandwidth_hz": 2.6e6, "link": "ADS-B 1090ES"},
         978: {"frequency_hz": 978e6, "bandwidth_hz": 1.3e6, "link": "UAT 978"}}
NOT_SELF = ("mlat", "tisb", "adsr", "mode_s")


@dataclass
class Aircraft:
    band: int
    icao: str
    flight: str | None
    lat: float | None
    lon: float | None
    alt_m: float | None
    alt_kind: str | None               # "geometric" (HAE) or "barometric"
    nac_p: int | None
    gva: int | None
    gs_mps: float | None
    seen_pos_s: float | None
    t_pos: float | None                # epoch s of the position (decoder clock)
    source_type: str | None
    derived: list = field(default_factory=list)   # fields the decoder marks as MLAT/TIS-B derived


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def parse(doc, band):
    """Aircraft from one aircraft.json document (dict). Unparseable entries are skipped."""
    now = _num(doc.get("now"))
    out = []
    for a in doc.get("aircraft", []) if isinstance(doc, dict) else []:
        if not isinstance(a, dict) or not isinstance(a.get("hex"), str):
            continue
        geom, baro = _num(a.get("alt_geom")), _num(a.get("alt_baro"))
        alt_m, kind = (geom * FT, "geometric") if geom is not None else (baro * FT, "barometric") if baro is not None else (None, None)
        seen = _num(a.get("seen_pos"))
        gs = _num(a.get("gs"))
        out.append(Aircraft(
            band=band, icao=a["hex"].lower().lstrip("~"), flight=(a.get("flight") or "").strip() or None,
            lat=_num(a.get("lat")), lon=_num(a.get("lon")), alt_m=alt_m, alt_kind=kind,
            nac_p=int(a["nac_p"]) if _num(a.get("nac_p")) is not None else None,
            gva=int(a["gva"]) if _num(a.get("gva")) is not None else None,
            gs_mps=None if gs is None else gs * 1852 / 3600, seen_pos_s=seen,
            t_pos=None if (now is None or seen is None) else now - seen,
            source_type=a.get("type") if isinstance(a.get("type"), str) else None,
            derived=[*(a.get("mlat") or []), *(a.get("tisb") or [])]))
    return out, now


def self_reported(ac):
    """True if the position came from the aircraft's own transmission."""
    if ac.source_type and ac.source_type.startswith(NOT_SELF):
        return False
    return not any(f in ("lat", "lon") for f in ac.derived)


def read_file(path, band):
    """([Aircraft], now) from a decoder's aircraft.json; ([], None) if absent or unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            return parse(json.load(f), band)
    except (OSError, ValueError):
        return [], None
