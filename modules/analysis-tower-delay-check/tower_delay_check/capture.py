"""A marker-timed capture: samples, the UTC time of each, and the marker windows to blank.

Reads an observation file through gps_time_pi.obsformat. Only gpstime:time_source "pps_marker"
is accepted: the point of the check is the marker timing. Times come from the file's captures
(core:datetime + (index − core:sample_start) / gpstime:sample_rate); samples in a capture with
"gpstime:time_valid": false have none. Annotations labelled "pps_marker" are set to zero before
correlating, as the marker writer asks.
"""

from gps_time_pi import obsformat


class Capture:
    def __init__(self, meta, data):
        g = meta["global"]
        if g.get("gpstime:time_source") != "pps_marker":
            raise ValueError(f"not a marker-timed capture (gpstime:time_source is {g.get('gpstime:time_source')!r})")
        self.meta = meta
        self.samples = obsformat.decode(data, g["core:datatype"])
        self.n = len(self.samples)
        self.sample_uncertainty_s = g.get("gpstime:sample_time_uncertainty_s")
        self.offset_bound_s = g.get("gpstime:time_offset_bound_s")
        self.blanked = 0
        for a in meta.get("annotations", []):
            if a.get("core:label") == "pps_marker":
                s = a["core:sample_start"]
                for i in range(max(0, s), min(self.n, s + a.get("core:sample_count", 0))):
                    self.samples[i] = 0j
                    self.blanked += 1

    @classmethod
    def read(cls, base):
        return cls(*obsformat.read(base))

    def _valid_caps(self):
        caps = self.meta["captures"]
        rate0 = self.meta["global"]["core:sample_rate"]
        for i, c in enumerate(caps):
            if c.get("gpstime:time_valid") is False or "core:datetime" not in c:
                continue
            end = caps[i + 1]["core:sample_start"] if i + 1 < len(caps) else self.n
            yield c["core:sample_start"], end, obsformat.parse_ns(c["core:datetime"]), c.get("gpstime:sample_rate", rate0)

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
