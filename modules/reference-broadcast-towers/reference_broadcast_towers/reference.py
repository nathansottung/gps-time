"""Broadcast transmitters from the offline cache (Reference interface).

`list(site)`: transmitters in the cache within max_range_km of the site, licensed, in the
services switched on. Rejections are counted by reason (not_licensed, service_off, out_of_range).
`predict(site, tx, t)`: the delay from the antenna to the site, with an approximate 95 % bound.

The delay: the straight-line (ECEF) range at c, times (1 + 300 × 10⁻⁶) for the air near the
ground (radio refractivity, typically 250-350 N-units at the surface). The bound is the
root-sum-square of:
  - the transmitter's position: 30 m for NAD83/WGS84 records given to 1 arc-second; 100 m when
    the datum is NAD27 or not stated (the NAD27 shift isn't applied here);
  - its height: 5 m with the radiation centre above sea level (rc_amsl) and the site's height
    above sea level known; 60 m when only the site's ellipsoidal height is known (geoid not
    known here); 300 m without rc_amsl;
  - refractivity: ±60 × 10⁻⁶ of the range;
  - the site's rounding, in rounded privacy mode.
Not modelled, and said in the note: multipath, the path bending over the horizon, and the
transmitter's own timing (a broadcast's emission time isn't known from its licence record;
an analysis compares arrival-time differences, or calibrates it out).

Whether the path is line of sight is `inferred`: the radio horizon for a 4/3 Earth, from the
tower's HAAT and an assumed 10 m receiving antenna. Beyond it the signal arrives by diffraction
or scatter and the straight-line delay is a lower bound.

The site is the privacy-filtered one from ctx.site(): hidden means nothing is predicted.
Positions are `external` (licence records); ranges and delays are `calculated`.
"""

import math
import os
from datetime import datetime, timezone

from gps_time_pi.modkit import Reference, Transmitter

from . import cache
from .geometry import C, elevation_deg, ground_distance, slant_range

REFRACTIVITY = 300e-6
REFRACTIVITY_BOUND = 60e-6
POS_M = {"NAD83": 30.0, "WGS84": 30.0}
POS_UNKNOWN_DATUM_M = 100.0
H_MSL_M, H_HAE_ONLY_M, H_UNKNOWN_M = 5.0, 60.0, 300.0
RX_ANTENNA_M = 10.0
K_EARTH = 4 / 3
R_EARTH = 6_371_008.8
LICENSED = ("LIC", "LICENSED", "NORMAL")      # NORMAL: a NOAA transmitter in service
REASONS = ("not_licensed", "service_off", "out_of_range")
DEFAULTS = {"cache_path": "/var/lib/gps-time/towers-cache.json", "services": "FM,ATSC,NOAA",
            "max_range_km": 150.0, "max_cache_age_days": 365.0}


def site_frame(site):
    """(lat, lon, h, frame, N) from a privacy-filtered site; None if hidden.
    frame is "msl" when the height above sea level is known (towers' rc_amsl is in the same
    frame), else "hae"; N is the geoid separation (hae − msl) when both are known."""
    if not site or site.get("lat") is None or site.get("lon") is None:
        return None
    msl, hae = site.get("alt_msl"), site.get("alt_hae")
    if msl is not None:
        return site["lat"], site["lon"], float(msl), "msl", (float(hae) - float(msl)) if hae is not None else None
    if hae is not None:
        return site["lat"], site["lon"], float(hae), "hae", None
    return site["lat"], site["lon"], 0.0, "none", None


def site_bound_m(site):
    """Horizontal uncertainty of the site itself: the rounding of a rounded site (~0.05° each way)."""
    if site and site.get("privacy") == "rounded":
        lat = math.radians(site["lat"])
        return math.hypot(0.05 * 111_320.0, 0.05 * 111_320.0 * math.cos(lat))
    return 0.0


def radio_horizon_m(h_tx, h_rx):
    """Distance to the radio horizon for two antenna heights above ground, 4/3 Earth."""
    return math.sqrt(2 * K_EARTH * R_EARTH * h_tx) + math.sqrt(2 * K_EARTH * R_EARTH * h_rx)


class TowerReference(Reference):
    def __init__(self, config=None, loader=cache.load, clock=None):
        self.config = {**DEFAULTS, **(config or {})}
        self.loader = loader
        self.clock = clock
        self.doc, self.problem = None, None
        self._mtime = None
        self._by_id = {}
        self.rejected = {r: 0 for r in REASONS}

    def _services(self):
        s = self.config.get("services")
        items = s.split(",") if isinstance(s, str) else (s or [])
        return {x.strip().upper() for x in items if x.strip()}

    def refresh(self):
        """Read the cache (again, if the file changed). Returns the problem, or None."""
        path = self.config["cache_path"]
        try:
            mtime = os.path.getmtime(path) if self.loader is cache.load else None
        except OSError:
            mtime = None
        if self.doc is None or mtime != self._mtime:
            self.doc, self.problem = self.loader(path)
            self._mtime = mtime
        return self.problem

    def cache_age_days(self, now_s):
        built = (self.doc or {}).get("built_utc")
        try:
            t = datetime.fromisoformat(built).timestamp()
        except (TypeError, ValueError):
            return None
        return max(0.0, (now_s - t) / 86400)

    def list(self, site):
        self.rejected = {r: 0 for r in REASONS}
        self.refresh()
        if not self.doc:
            return []
        on = self._services()
        st = site_frame(site)
        out = []
        for r in self.doc["towers"]:
            if r.get("service") not in on:
                self.rejected["service_off"] += 1
                continue
            if r.get("status") and r["status"] not in LICENSED:
                self.rejected["not_licensed"] += 1
                continue
            if st is not None and ground_distance(st[0], st[1], r["lat"], r["lon"]) > self.config["max_range_km"] * 1000:
                self.rejected["out_of_range"] += 1
                continue
            self._by_id[r["id"]] = r
            out.append(Transmitter(
                id=r["id"], frequency_hz=r["frequency_hz"], bandwidth_hz=r["bandwidth_hz"],
                position={"lat": r["lat"], "lon": r["lon"], "alt_m": r.get("rc_amsl_m"),
                          "alt_kind": "radiation centre above mean sea level" if r.get("rc_amsl_m") is not None else None},
                position_source=(f"{r['service']} licence record {r['callsign']}"
                                 f"{' (facility ' + r['facility_id'] + ')' if r.get('facility_id') else ''}: "
                                 f"{r.get('source') or 'source not stated'}; record dated {r.get('record_date') or 'undated'}; "
                                 f"datum {r.get('datum') or 'not stated'}")))
        return out

    def predict(self, site, tx, t_ns):
        """{"delay_s", "uncertainty_s", "range_m", "elevation_deg", "line_of_sight"} as labeled values."""
        st = site_frame(site)
        r = self._by_id.get(tx.id)
        if st is None or r is None:
            why = "the location is hidden by the privacy setting" if st is None else "unknown transmitter"
            unk = {"value": None, "unit": "s", "provenance": "calculated", "note": f"not predicted: {why}"}
            return {"delay_s": unk, "uncertainty_s": dict(unk), "range_m": {**unk, "unit": "m"},
                    "elevation_deg": {**unk, "unit": "deg"},
                    "line_of_sight": {"value": None, "unit": None, "provenance": "inferred", "note": f"not assessed: {why}"}}
        rc = r.get("rc_amsl_m")
        if rc is not None and st[3] == "msl":
            h_tx, h_bound = rc, H_MSL_M
        elif rc is not None:
            h_tx, h_bound = rc, H_HAE_ONLY_M
        else:
            h_tx, h_bound = st[2] + 100.0, H_UNKNOWN_M
        a, b = st[:3], (r["lat"], r["lon"], h_tx)
        rng = slant_range(a, b)
        parts = {
            "transmitter position": POS_M.get(r.get("datum") or "", POS_UNKNOWN_DATUM_M),
            "transmitter height": h_bound,
            "refractivity": REFRACTIVITY_BOUND * rng,
            "site rounding": site_bound_m(site),
        }
        bound = math.sqrt(sum(v * v for v in parts.values()))
        delay = rng * (1 + REFRACTIVITY) / C
        ground = ground_distance(st[0], st[1], r["lat"], r["lon"])
        haat = r.get("haat_m")
        if haat is None or haat <= 0:
            los, los_note = None, "unknown: the record has no HAAT"
        else:
            horizon = radio_horizon_m(haat, RX_ANTENNA_M)
            los = ground <= horizon
            los_note = (f"{'within' if los else 'beyond'} the radio horizon ({horizon / 1000:.0f} km for HAAT "
                        f"{haat:.0f} m and a {RX_ANTENNA_M:.0f} m receiving antenna, 4/3 Earth)"
                        + ("" if los else "; the straight-line delay is then a lower bound"))
        note = ("95 % bound (approximate), root-sum-square of: "
                + ", ".join(f"{k} {v:.0f} m" for k, v in parts.items() if v)
                + ". Straight-line path; multipath, over-the-horizon paths and the transmitter's own emission "
                  "timing are not modelled.")
        return {
            "delay_s": {"value": delay, "unit": "s", "provenance": "calculated",
                        "note": f"straight-line range at c × (1 + {REFRACTIVITY * 1e6:.0f} × 10⁻⁶) for the air"},
            "uncertainty_s": {"value": bound / C, "unit": "s", "provenance": "calculated", "note": note},
            "range_m": {"value": round(rng, 1), "unit": "m", "provenance": "calculated"},
            "elevation_deg": {"value": round(elevation_deg(a, b), 3), "unit": "deg", "provenance": "calculated",
                              "note": "geometric, from the site's horizon"},
            "line_of_sight": {"value": los, "unit": None, "provenance": "inferred", "note": los_note},
        }
