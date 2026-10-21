"""Sample-to-UTC time model from PPS markers.

Given marker positions (from detector.detect) and a coarse time for sample 0
(the host clock is good enough: it only picks which UTC second each marker is,
so it must be right to better than half a second):

- Seconds: each interval between markers spans round(count / rate) seconds,
  so a marker too weak to see leaves a 2 s interval, not an error.
- Interval check: an interval whose rate is further from nominal than
  ppm_limit is flagged outright (a falling edge taken for a marker, a large
  drop). Every other interval's sample count is compared with the local
  sample rate (median of the neighbouring intervals). A count that is short
  means samples were dropped; long means samples were added. Either way the
  interval is flagged and its samples get no time. Spurious markers (less than
  half a second after the previous one) are discarded.
- Time of a sample: straight-line interpolation between the two markers around
  it. Samples before the first marker, after the last, or in a flagged interval
  have no time (None): the model never guesses across a gap.
- Uncertainty, conservative on short runs:
  1. Scatter: a quadratic (rate and drift) is fitted to each block of up to
     BLOCK good consecutive markers; the residuals give the marker position
     scatter with a known number of degrees of freedom (markers - 3 per block).
  2. Bound: the stated scatter is the 95 % upper confidence bound on it
     (chi-square), so a run with few markers states a larger uncertainty
     rather than a falsely small one.
  3. Floor: FLOOR_SAMPLES is added in quadrature for the interpolation's own
     bias, which the scatter can't see.
  The stated uncertainty is 1 sigma; 1.96 times it is the 95 % interval, which
  the tests check covers the true error in at least 95 % of seeded runs. No
  sample gets a time until there are MIN_DOF degrees of freedom. It covers the
  marker fit only: PPS accuracy, the injection path, the SDR's internal delay
  and antenna/cable delay are calibrated on the bench (research steps 2-4) and
  are not in this number.
- Clock: the measured sample rate, its error against nominal in ppm, and its
  drift, from a straight-line fit of the per-second counts.

Absolute times are an integer UTC second plus a fraction: a float can't hold
nanoseconds at 1.8e9 s.
"""

import math
from dataclasses import dataclass

# Provenance labels come from the station's own definitions (the repository root
# must be importable, as it is for the test runner and the station).
from gps_time_pi.labels import q

TIME_SOURCE = "pps_marker"
# Degrees of freedom of the scatter estimate needed before any sample gets a time.
MIN_DOF = 3
# Markers per block for the quadratic fit: short enough that a crystal's drift
# over the block is close to quadratic.
BLOCK = 30
# Interpolation bias bound, in samples (from the noise-free detector test).
FLOOR_SAMPLES = 0.02
# Lower 5 % quantiles of chi-square for 1..10 degrees of freedom; Wilson-Hilferty above.
_CHI2_05 = (0.003932, 0.1026, 0.3518, 0.7107, 1.1455, 1.6354, 2.1673, 2.7326, 3.3251, 3.9403)


def chi2_lower_05(dof):
    """Lower 5 % quantile of chi-square with dof degrees of freedom."""
    if dof <= len(_CHI2_05):
        return _CHI2_05[dof - 1]
    z = -1.6448536
    return dof * (1 - 2 / (9 * dof) + z * math.sqrt(2 / (9 * dof))) ** 3


def _quad_rss(xs, ys):
    """Residual sum of squares of a least-squares quadratic y = a + b x + c x^2."""
    n = len(xs)
    mx = sum(xs) / n
    u = [x - mx for x in xs]
    s = [sum(v ** k for v in u) for k in range(5)]
    t = [sum(y * v ** k for y, v in zip(ys, u)) for k in range(3)]
    m = [[s[0], s[1], s[2], t[0]], [s[1], s[2], s[3], t[1]], [s[2], s[3], s[4], t[2]]]
    for i in range(3):
        piv = max(range(i, 3), key=lambda r: abs(m[r][i]))
        m[i], m[piv] = m[piv], m[i]
        for r in range(3):
            if r != i:
                f = m[r][i] / m[i][i]
                m[r] = [a - f * b for a, b in zip(m[r], m[i])]
    a, b, c = (m[i][3] / m[i][i] for i in range(3))
    return sum((y - (a + b * v + c * v * v)) ** 2 for y, v in zip(ys, u))
SCOPE_NOTE = ("marker fit only; PPS accuracy, injection path, SDR internal delay and "
              "antenna/cable delay are not included (bench calibration, research steps 2-4)")


@dataclass(frozen=True)
class UtcTime:
    second: int                 # UTC second (Unix time)
    fraction: float             # seconds after it, 0 <= fraction < 1
    uncertainty_s: float        # 1-sigma, marker fit only

    @property
    def ns(self):
        """UTC as integer nanoseconds."""
        return self.second * 1_000_000_000 + int(round(self.fraction * 1e9))


@dataclass(frozen=True)
class Interval:
    first: int        # index into markers
    seconds: int      # whole seconds it spans
    count: float      # samples between the markers
    expected: float   # samples expected at the local rate
    flagged: bool


def _median(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


class TimeModel:
    def __init__(self, markers, fs_nominal, coarse_start_utc, *, marker_delay_s=0.0,
                 tolerance_samples=None, neighbours=5, ppm_limit=200.0):
        """markers: detector Markers (or plain sample positions).
        coarse_start_utc: UTC of sample 0 to better than 0.5 s (host clock).
        marker_delay_s: fixed delay from the PPS edge to the marker in the
        samples (buffer, cable, attenuators, SDR filters), from calibration.
        """
        self.fs_nominal = float(fs_nominal)
        self.marker_delay_s = float(marker_delay_s)
        pos = sorted(getattr(m, "sample", m) for m in markers)
        kept = []
        for p in pos:
            if kept and p - kept[-1] < 0.5 * self.fs_nominal:
                continue    # spurious: less than half a second after the previous marker
            kept.append(p)
        self.markers = kept
        self.discarded = len(pos) - len(kept)

        secs = [max(1, round((b - a) / self.fs_nominal)) for a, b in zip(kept, kept[1:])]
        per_sec = [(b - a) / n for a, b, n in zip(kept, kept[1:], secs)]
        plausible = [abs(r / self.fs_nominal - 1) * 1e6 <= ppm_limit for r in per_sec]
        self.intervals = []
        resid = []
        for k, n in enumerate(secs):
            near = [r for i, r in enumerate(per_sec) if plausible[i] and i != k and abs(i - k) <= neighbours]
            local = _median(near) if near else self.fs_nominal
            count = kept[k + 1] - kept[k]
            resid.append(count - n * local)
            self.intervals.append([k, n, count, n * local])
        ok_resid = [abs(r) for r, p in zip(resid, plausible) if p]
        spread = 1.4826 * _median(ok_resid) if ok_resid else 0.0
        tol = tolerance_samples if tolerance_samples is not None else max(0.5, 8 * spread)
        self.tolerance_samples = tol
        self.intervals = [Interval(k, n, c, e, (not plausible[k]) or abs(c - e) > tol)
                          for k, n, c, e in self.intervals]

        self.seconds = []
        if kept:
            s0 = round(coarse_start_utc + kept[0] / self.fs_nominal - self.marker_delay_s)
            self.seconds = [s0]
            for iv in self.intervals:
                self.seconds.append(self.seconds[-1] + iv.seconds)

        # Runs of markers joined by good intervals, cut into blocks; a quadratic in
        # UTC seconds fitted to each block gives the scatter with markers - 3 dof.
        runs, run = [], [0] if kept else []
        for iv in self.intervals:
            if iv.flagged:
                runs.append(run)
                run = [iv.first + 1]
            else:
                run.append(iv.first + 1)
        if run:
            runs.append(run)
        rss = 0.0
        dof = 0
        for run in runs:
            for b in range(0, len(run), BLOCK):
                block = run[b:b + BLOCK]
                if len(block) >= 4:
                    rss += _quad_rss([self.seconds[i] - self.seconds[block[0]] for i in block],
                                     [kept[i] for i in block])
                    dof += len(block) - 3
        self.dof = dof
        self.position_sd = self.position_bound = None
        if dof >= MIN_DOF:
            self.position_sd = math.sqrt(rss / dof)
            upper = self.position_sd * math.sqrt(dof / chi2_lower_05(dof))
            self.position_bound = math.sqrt(upper ** 2 + FLOOR_SAMPLES ** 2)

        good = [(self.seconds[iv.first] + iv.seconds / 2, iv.count / iv.seconds)
                for iv in self.intervals if not iv.flagged]
        self.rate_hz = self.rate_slope = None
        if len(good) >= 1:
            mt = sum(t for t, _ in good) / len(good)
            mr = sum(r for _, r in good) / len(good)
            stt = sum((t - mt) ** 2 for t, _ in good)
            self.rate_hz = mr
            self.rate_slope = (sum((t - mt) * (r - mr) for t, r in good) / stt) if stt > 0 else None

    def events(self):
        """Flagged intervals: samples missing (dropped) or extra."""
        out = []
        for iv in self.intervals:
            if iv.flagged:
                diff = iv.count - iv.expected
                out.append({"type": "samples_missing" if diff < 0 else "samples_extra",
                            "samples": round(abs(diff)),
                            "after_second": self.seconds[iv.first],
                            "from_sample": self.markers[iv.first],
                            "to_sample": self.markers[iv.first + 1]})
        return out

    def utc(self, sample):
        """UtcTime of a sample index, or None where the model has no time for it."""
        m = self.markers
        if len(m) < 2 or sample < m[0] or sample > m[-1]:
            return None
        lo, hi = 0, len(m) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if m[mid] <= sample:
                lo = mid
            else:
                hi = mid
        iv = self.intervals[lo]
        if iv.flagged or self.position_bound is None:
            return None
        f = (sample - m[lo]) / (m[lo + 1] - m[lo])
        t = f * iv.seconds + self.marker_delay_s
        whole = math.floor(t)
        rate = iv.count / iv.seconds
        unc = self.position_bound / rate * math.sqrt((1 - f) ** 2 + f ** 2)
        return UtcTime(self.seconds[lo] + whole, t - whole, unc)

    def summary(self):
        """Health values for a dashboard, each with a provenance label."""
        n = len(self.markers)
        span = self.seconds[-1] - self.seconds[0] if n >= 2 else 0   # UTC seconds covered
        ppm = drift = None
        if self.rate_hz is not None:
            ppm = (self.rate_hz / self.fs_nominal - 1) * 1e6
        if self.rate_slope is not None:
            drift = self.rate_slope / self.fs_nominal * 1e6 * 3600
        unc = self.position_bound / self.rate_hz if (self.position_bound is not None and self.rate_hz) else None
        return {
            "state": "OK" if n >= 2 and unc is not None else "UNKNOWN",
            "time_source": TIME_SOURCE,
            "markers": q(n, None, "observed"),
            "markers_per_minute": q(60 * (n - 1) / span if span else None, "1/min", "calculated"),
            "sample_rate_hz": q(self.rate_hz, "Hz", "calculated"),
            "clock_error_ppm": q(ppm, "ppm", "calculated"),
            "drift_ppm_per_hour": q(drift, "ppm/h", "calculated"),
            "marker_position_sd_samples": q(self.position_sd, "samples", "calculated",
                                            note=f"estimate from {self.dof} degrees of freedom"),
            "marker_position_bound_samples": q(self.position_bound, "samples", "calculated",
                                               note="95 % upper bound on the scatter, plus the interpolation floor; used for uncertainty"),
            "sample_time_uncertainty_s": q(unc, "s", "calculated", note=SCOPE_NOTE),
            "dropped_sample_events": q(len(self.events()), None, "calculated"),
            "discarded_markers": q(self.discarded, None, "observed"),
        }
