"""A marker-timed capture: samples, the UTC time of each, its tuning, and the marker windows to blank.

Reads an observation file through gps_time_pi.obsformat. Only gpstime:time_source "pps_marker"
is accepted: the point of the check is the marker timing. Times come from the file's captures
(core:datetime + (index − core:sample_start) / gpstime:sample_rate); samples in a capture with
"gpstime:time_valid": false have none. Annotations labelled "pps_marker" are set to zero before
correlating, as the marker writer asks. cu8 files (the RTL-SDR's own samples, as sdr-pps-marker's
live capture writes them) are centred with gpstime:calibration's sample_offset and sample_scale.

Tuning: core:frequency of the timed capture is the nominal centre. An RTL-SDR's tuner and its
ADC run from one crystal, so the tuner is off by the same fraction as the sample clock, which
the markers measure (gpstime:sample_rate against core:sample_rate). `tune_hz` applies that
(lo_follows_clock, the default; turn it off for an SDR with a separate tuner reference).
"""

import numpy as np

from gps_time_pi import obsformat


class Capture:
    def __init__(self, meta, data, lo_follows_clock=True):
        g = meta["global"]
        if g.get("gpstime:time_source") != "pps_marker":
            raise ValueError(f"not a marker-timed capture (gpstime:time_source is {g.get('gpstime:time_source')!r})")
        self.meta = meta
        self.samples = np.asarray(obsformat.decode(data, g["core:datatype"]), dtype=complex)
        if g["core:datatype"] == "cu8":
            # the RTL-SDR's raw counts: stored value = offset + scale × sample (gpstime:calibration)
            cal = g.get("gpstime:calibration") or {}
            off, scale = float(cal.get("sample_offset", 127.5)), float(cal.get("sample_scale", 127.5))
            self.samples = (self.samples - complex(off, off)) / scale
        self.n = len(self.samples)
        self.sample_uncertainty_s = g.get("gpstime:sample_time_uncertainty_s")
        self.offset_bound_s = g.get("gpstime:time_offset_bound_s")
        self.rate_nominal = float(g["core:sample_rate"])
        self.blanked = 0
        for a in meta.get("annotations", []):
            if a.get("core:label") == "pps_marker":
                s = max(0, a["core:sample_start"])
                e = min(self.n, a["core:sample_start"] + a.get("core:sample_count", 0))
                if e > s:
                    self.samples[s:e] = 0
                    self.blanked += e - s
        timed = list(self._valid_caps())
        if not timed:
            raise ValueError("the capture has no timed part")
        self.timed_start, self.timed_end, _t0, self.rate = timed[0]
        self.center_hz = next((c.get("core:frequency") for c in meta["captures"] if "core:datetime" in c
                               and c.get("gpstime:time_valid") is not False), None)
        if self.center_hz is None:
            raise ValueError("the capture doesn't say its centre frequency (core:frequency)")
        self.clock_ppm = (self.rate / self.rate_nominal - 1) * 1e6
        self.tune_hz = self.center_hz * (1 + self.clock_ppm * 1e-6) if lo_follows_clock else self.center_hz

    @classmethod
    def read(cls, base, **kw):
        return cls(*obsformat.read(base), **kw)

    def covers(self, freq_hz, half_bw_hz):
        """Hz of the signal's band [f − bw, f + bw] inside this capture's flat passband."""
        lo, hi = self.tune_hz - 0.4 * self.rate, self.tune_hz + 0.4 * self.rate
        return max(0.0, min(hi, freq_hz + half_bw_hz) - max(lo, freq_hz - half_bw_hz))

    def _valid_caps(self):
        caps = self.meta["captures"]
        rate0 = self.meta["global"]["core:sample_rate"]
        for i, c in enumerate(caps):
            if c.get("gpstime:time_valid") is False or "core:datetime" not in c:
                continue
            end = caps[i + 1]["core:sample_start"] if i + 1 < len(caps) else self.n
            yield c["core:sample_start"], end, obsformat.parse_ns(c["core:datetime"]), float(c.get("gpstime:sample_rate", rate0))

    # UTC instants are integer nanoseconds: a float near 1.8e18 ns resolves only 256 ns.

    def time_ns(self, index):
        """UTC (integer ns) of a fractional sample index, or None where the file gives no time."""
        for start, end, t0, rate in self._valid_caps():
            if start <= index < end:
                return t0 + round((index - start) / rate * 1e9)
        return None

    def index_of(self, t_ns):
        """(fractional sample index, sample rate) for a UTC time (integer ns), or None if no timed sample is there."""
        for start, end, t0, rate in self._valid_caps():
            idx = start + (int(t_ns) - t0) / 1e9 * rate
            if start <= idx < end:
                return idx, rate
        return None
