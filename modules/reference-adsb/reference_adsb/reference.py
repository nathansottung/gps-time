"""ADS-B aircraft as self-reported references (Reference interface).

`list(site)`: aircraft whose own transmitted position passes the checks below, as Transmitters.
`predict(site, tx, t)`: the free-space delay from the aircraft to the site, with a bound.

Checks, in order (each rejection is counted by reason, never silent):
  no_position        no latitude/longitude
  not_self_reported  MLAT, TIS-B, ADS-R or Mode S: the signal isn't from where the position says
  stale              position older than max_age_s
  accuracy_unknown   no NACp
  low_accuracy       NACp below min_nac_p
  no_altitude        neither geometric nor barometric altitude
  out_of_range       slant range beyond max_range_km, or below the horizon (elevation < -1°)
  implausible_jump   moved faster than max_speed_mps since its previous accepted position

The site is the privacy-filtered one from ctx.site(): None (hidden) means nothing can be
predicted, and the rounding of a rounded site is added to the uncertainty. Positions are
`external` (self-reported); ranges and delays are `calculated` from them. The delay is
geometric (straight line at c): the troposphere's few metres and the decoder's own latency
aren't modelled, and say so.
"""

import math

from gps_time_pi.modkit import Reference, Transmitter

from .feeds import BANDS, read_file, self_reported
from .geometry import C, elevation_deg, ground_distance, slant_range

# 95 % horizontal position bound (EPU) by NACp, metres (RTCA DO-260B).
EPU_M = {11: 3.0, 10: 10.0, 9: 30.0, 8: 92.6, 7: 185.2, 6: 555.6, 5: 926.0, 4: 1852.0, 3: 3704.0, 2: 7408.0, 1: 18520.0}
# 95 % vertical bound for geometric altitude by GVA (0: unknown or > 150 m).
GVA_M = {2: 45.0, 1: 150.0, 0: 300.0}
BARO_M = 300.0                    # pressure altitude against geometric height: a conservative bound
MSL_SITE_M = 100.0                # site height given above sea level only: the geoid isn't known here
REASONS = ("no_position", "not_self_reported", "stale", "accuracy_unknown", "low_accuracy",
           "no_altitude", "out_of_range", "implausible_jump")
DEFAULTS = {"aircraft_json_1090": "/run/readsb/aircraft.json", "aircraft_json_978": "/run/skyaware978/aircraft.json",
            "max_age_s": 5.0, "min_nac_p": 8, "max_range_km": 450.0, "max_speed_mps": 700.0}


def site_tuple(site):
    """(lat, lon, h above ellipsoid, height bound m) from a privacy-filtered site; None if hidden."""
    if not site or site.get("lat") is None or site.get("lon") is None:
        return None
    if site.get("alt_hae") is not None:
        return site["lat"], site["lon"], float(site["alt_hae"]), 0.0
    if site.get("alt_msl") is not None:
        return site["lat"], site["lon"], float(site["alt_msl"]), MSL_SITE_M
    return site["lat"], site["lon"], 0.0, 500.0


def site_bound_m(site):
    """Horizontal uncertainty of the site itself: the rounding of a rounded site (~0.05° each way)."""
    if site and site.get("privacy") == "rounded":
        lat = math.radians(site["lat"])
        return math.hypot(0.05 * 111_320.0, 0.05 * 111_320.0 * math.cos(lat))
    return 0.0


class AdsbReference(Reference):
    def __init__(self, config=None, reader=read_file, clock=None):
        self.config = {**DEFAULTS, **(config or {})}
        self.reader = reader
        self.clock = clock
        self.rejected = {r: 0 for r in REASONS}
        self.seen = {1090: 0, 978: 0}
        self._last = {}               # tx id -> (t_pos, lat, lon) of its previous accepted position
        self._meta = {}               # tx id -> what predict() needs besides the position

    def _feeds(self):
        out = []
        for band in (1090, 978):
            path = self.config.get(f"aircraft_json_{band}")
            if path:
                aircraft, now = self.reader(path, band)
                out.append((band, aircraft, now))
        return out

    def list(self, site):
        """Transmitters near the site; counts what was seen and rejected (self.seen, self.rejected)."""
        self.rejected = {r: 0 for r in REASONS}
        self.seen = {1090: 0, 978: 0}
        st = site_tuple(site)
        out = []
        for band, aircraft, _ in self._feeds():
            self.seen[band] += len(aircraft)
            for ac in aircraft:
                reason = self._check(ac, st)
                if reason:
                    self.rejected[reason] += 1
                    continue
                tx_id = f"{band}:{ac.icao}"
                self._last[tx_id] = (ac.t_pos, ac.lat, ac.lon)
                self._meta[tx_id] = ac
                b = BANDS[band]
                out.append(Transmitter(
                    id=tx_id, frequency_hz=b["frequency_hz"], bandwidth_hz=b["bandwidth_hz"],
                    position={"lat": ac.lat, "lon": ac.lon, "alt_m": round(ac.alt_m, 1), "alt_kind": ac.alt_kind},
                    position_source=f"self-reported ({b['link']}, NACp {ac.nac_p})"))
        return out

    def _check(self, ac, st):
        c = self.config
        if ac.lat is None or ac.lon is None:
            return "no_position"
        if not self_reported(ac):
            return "not_self_reported"
        if ac.seen_pos_s is None or ac.seen_pos_s > c["max_age_s"]:
            return "stale"
        if ac.nac_p is None:
            return "accuracy_unknown"
        if ac.nac_p < c["min_nac_p"]:
            return "low_accuracy"
        if ac.alt_m is None:
            return "no_altitude"
        if st is not None:
            rng = slant_range(st[:3], (ac.lat, ac.lon, ac.alt_m))
            if rng > c["max_range_km"] * 1000 or elevation_deg(st[:3], (ac.lat, ac.lon, ac.alt_m)) < -1.0:
                return "out_of_range"
        prev = self._last.get(f"{ac.band}:{ac.icao}")
        if prev and ac.t_pos is not None and prev[0] is not None and ac.t_pos > prev[0]:
            v = ground_distance(prev[1], prev[2], ac.lat, ac.lon) / (ac.t_pos - prev[0])
            if v > c["max_speed_mps"]:
                return "implausible_jump"
        return None

    def predict(self, site, tx, t_ns):
        """{"delay_s", "uncertainty_s", "range_m"} as labeled values; None values (UNKNOWN) without a site."""
        st = site_tuple(site)
        ac = self._meta.get(tx.id)
        if st is None or ac is None:
            why = "the location is hidden by the privacy setting" if st is None else "unknown transmitter"
            unk = {"value": None, "unit": "s", "provenance": "calculated", "note": f"not predicted: {why}"}
            return {"delay_s": unk, "uncertainty_s": dict(unk), "range_m": {**unk, "unit": "m"}}
        p = tx.position
        rng = slant_range(st[:3], (p["lat"], p["lon"], p["alt_m"]))
        age = 0.0 if ac.t_pos is None else max(0.0, t_ns / 1e9 - ac.t_pos)
        parts = {
            "position (NACp)": EPU_M.get(ac.nac_p, 18520.0),
            "altitude": GVA_M.get(ac.gva if ac.gva is not None else 0, 300.0) if ac.alt_kind == "geometric" else BARO_M,
            "movement since the fix": (ac.gs_mps or 0.0) * age,
            "site height": st[3],
            "site rounding": site_bound_m(site),
        }
        bound = math.sqrt(sum(v * v for v in parts.values()))
        note = ("95 % bound (approximate), root-sum-square of: "
                + ", ".join(f"{k} {v:.0f} m" for k, v in parts.items() if v)
                + ". Straight-line path at c; troposphere and decoder latency not modelled.")
        return {"delay_s": {"value": rng / C, "unit": "s", "provenance": "calculated",
                            "note": "free-space delay from the self-reported position to the site"},
                "uncertainty_s": {"value": bound / C, "unit": "s", "provenance": "calculated", "note": note},
                "range_m": {"value": round(rng, 1), "unit": "m", "provenance": "calculated"}}
