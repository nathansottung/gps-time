"""Frequency-stability statistics of the system clock against kernel PPS.

Overlapping Allan deviation (ADEV), modified Allan deviation (MDEV) and time
deviation (TDEV), per NIST SP 1065 (Riley, Handbook of Frequency Stability
Analysis). Pure Python: the station must not need a compiler or NumPy here.

What is measured. The input is a phase (time-error) series x(t): the
fractional second of each kernel PPS timestamp, i.e. where the Linux system
clock, as chrony disciplines it, read when the PPS interrupt was stamped. These
are the samples chrony's PPS refclock consumes. The statistics therefore
describe the system clock against the PPS edges as Linux saw them, including
interrupt latency and chrony's own loop. They do not describe the receiver's
electrical PPS or the oscillator alone.

Storage is RAM only (project rule: nothing is written at 1 Hz):
  - a ring of the last RING_S seconds, one phase sample per second;
  - one summary per minute for long spans: the minute's last sample (exact
    input for ADEV at tau >= 60 s) and its mean phase (exact input for
    MDEV/TDEV at tau >= 60 s, as they average phase over the tau window).
Both are lost on a service restart.
"""

import math
import threading
import time
from collections import deque
from datetime import datetime, timezone
from statistics import NormalDist

from .pps import phase_ns, require_ns

RING_S = 14400            # 4 h of 1 s samples
RING_MINUTES = 20160      # 14 d of minute summaries
MINUTE_MIN_SAMPLES = 54   # a minute's mean needs 90 % of its seconds
TAUS_SECONDS = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000)
TAUS_MINUTES = (60, 120, 300, 600, 1440, 2880)   # averaging factors of the 60 s series
KEY_TAUS_S = (1, 10, 100, 1000, 86400)
NOISE_ID_MIN_POINTS = 30
CONFIDENCE = 0.683
CACHE_S = 60.0

LAYER_NOTE = ("System clock against kernel PPS timestamps: the Linux/chrony view of PPS, "
              "including interrupt latency and chrony's loop. Not the receiver's electrical PPS "
              "and not the oscillator alone.")
NOISE_NAMES = {2: "white PM", 1: "flicker PM", 0: "white FM", -1: "flicker FM", -2: "random-walk FM"}


# ── estimators (pure; a sample may be None = not observed) ──────────────────

def phase_from_frequency(y, tau0=1.0):
    """Fractional-frequency data -> phase data (one more point than y)."""
    x, acc = [0.0], 0.0
    for v in y:
        acc += v * tau0
        x.append(acc)
    return x


def oadev(x, m, tau0=1.0):
    """Overlapping Allan deviation at tau = m*tau0 from phase data.
    Returns (deviation, terms); (None, 0) without a complete term. A term that
    touches a missing sample is skipped."""
    n, s = 0, 0.0
    for i in range(len(x) - 2 * m):
        a, b, c = x[i], x[i + m], x[i + 2 * m]
        if a is None or b is None or c is None:
            continue
        d = c - 2.0 * b + a
        s += d * d
        n += 1
    if not n:
        return None, 0
    tau = m * tau0
    return math.sqrt(s / (2.0 * n * tau * tau)), n


def window_means(x, m):
    """Mean of each m-sample window of x (None where the window has a gap)."""
    out = []
    total, missing = 0.0, 0
    for i, v in enumerate(x):
        if v is None:
            missing += 1
        else:
            total += v
        if i >= m:
            old = x[i - m]
            if old is None:
                missing -= 1
            else:
                total -= old
        if i >= m - 1:
            out.append(None if missing else total / m)
    return out


def mdev_from_means(means, lag, tau):
    """Modified Allan deviation from window-mean phases: second differences of
    means `lag` entries apart, where each mean covers one tau. `means` may be
    overlapping (stride 1 sample) or one per window (stride tau)."""
    n, s = 0, 0.0
    for i in range(len(means) - 2 * lag):
        a, b, c = means[i], means[i + lag], means[i + 2 * lag]
        if a is None or b is None or c is None:
            continue
        d = c - 2.0 * b + a
        s += d * d
        n += 1
    if not n:
        return None, 0
    return math.sqrt(s / (2.0 * n * tau * tau)), n


def mdev(x, m, tau0=1.0):
    """Modified Allan deviation at tau = m*tau0 from phase data: (deviation, terms)."""
    return mdev_from_means(window_means(x, m), m, m * tau0)


def tdev_from_mdev(mdev_value, tau):
    """Time deviation, seconds: tau * MDEV / sqrt(3)."""
    return None if mdev_value is None else tau * mdev_value / math.sqrt(3.0)


# ── power-law noise identification and confidence intervals ─────────────────

def _longest_run(x):
    best, cur = [], []
    for v in x:
        if v is None:
            if len(cur) > len(best):
                best = cur
            cur = []
        else:
            cur.append(v)
    return cur if len(cur) > len(best) else best


def _detrend_quadratic(x):
    """Residuals of a least-squares quadratic fit (removes phase offset,
    frequency offset and linear drift)."""
    n = len(x)
    t = [2.0 * i / (n - 1) - 1.0 for i in range(n)]     # scaled to [-1, 1] for conditioning
    s = [sum(v ** k for v in t) for k in range(5)]
    b = [sum(xv * tv ** k for xv, tv in zip(x, t)) for k in range(3)]
    a = [[s[0], s[1], s[2], b[0]], [s[1], s[2], s[3], b[1]], [s[2], s[3], s[4], b[2]]]
    for col in range(3):                                 # Gauss-Jordan, 3x3
        piv = max(range(col, 3), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-300:
            return list(x)
        a[col], a[piv] = a[piv], a[col]
        for r in range(3):
            if r != col:
                f = a[r][col] / a[col][col]
                a[r] = [rv - f * cv for rv, cv in zip(a[r], a[col])]
    c = [a[k][3] / a[k][k] for k in range(3)]
    return [xv - (c[0] + c[1] * tv + c[2] * tv * tv) for xv, tv in zip(x, t)]


def _lag1(x):
    mean = sum(x) / len(x)
    den = sum((v - mean) ** 2 for v in x)
    if den <= 0.0:
        return None
    return sum((x[i] - mean) * (x[i + 1] - mean) for i in range(len(x) - 1)) / den


def noise_alpha(x, m):
    """Power-law noise exponent alpha (2 white PM ... -2 random-walk FM) at
    averaging factor m, by the lag-1 autocorrelation method (Riley & Greenhall;
    SP 1065 section 5.5.6). Uses the longest gap-free run of the decimated
    phase data; None when it has fewer than NOISE_ID_MIN_POINTS points."""
    z = _longest_run(x[::m])
    if len(z) < NOISE_ID_MIN_POINTS:
        return None
    z = _detrend_quadratic(z)
    d = 0
    while True:
        r1 = _lag1(z)
        if r1 is None or r1 <= -1.0:
            return None
        rho = r1 / (1.0 + r1)
        if rho < 0.25 or d >= 2:
            alpha = int(round(-2.0 * (rho + d))) + 2
            return max(-2, min(2, alpha))
        z = [z[i + 1] - z[i] for i in range(len(z) - 1)]
        d += 1


def oadev_edf(alpha, n_points, m):
    """Equivalent degrees of freedom of the overlapping Allan variance for
    n_points phase samples at averaging factor m (SP 1065 section 5.4.1)."""
    n = float(n_points)
    if n <= 3 or n <= 2 * m:
        return None
    if alpha == 2:
        edf = (n + 1) * (n - 2 * m) / (2 * (n - m))
    elif alpha == 1:
        a, b = (n - 1) / (2 * m), (2 * m + 1) * (n - 1) / 4
        if a <= 1 or b <= 1:
            return None
        edf = math.exp(math.sqrt(math.log(a) * math.log(b)))
    elif alpha == 0:
        edf = (3 * (n - 1) / (2 * m) - 2 * (n - 2) / n) * (4 * m * m) / (4 * m * m + 5)
    elif alpha == -1:
        edf = 2 * (n - 2) / (2.3 * n - 4.9) if m == 1 else 5 * n * n / (4 * m * (n + 3 * m))
    elif alpha == -2:
        edf = (n - 2) / (m * (n - 3) ** 2) * ((n - 1) ** 2 - 3 * m * (n - 1) + 4 * m * m)
    else:
        return None
    return edf if edf > 0 else None


def _gamma_p(a, x):
    """Regularized lower incomplete gamma function P(a, x)."""
    if x <= 0:
        return 0.0
    lead = math.exp(-x + a * math.log(x) - math.lgamma(a))
    if x < a + 1:                      # series
        term = total = 1.0 / a
        k = a
        for _ in range(100000):
            k += 1
            term *= x / k
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return total * lead
    tiny = 1e-300                      # continued fraction (modified Lentz) for Q(a, x)
    b = x + 1 - a
    c, d = 1 / tiny, 1 / b
    h = d
    for i in range(1, 100000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return 1.0 - lead * h


def chi2_ppf(p, k):
    """Chi-squared quantile: x with P(X <= x) = p for k degrees of freedom."""
    z = NormalDist().inv_cdf(p)
    guess = k * max(1e-12, 1 - 2 / (9 * k) + z * math.sqrt(2 / (9 * k))) ** 3    # Wilson-Hilferty
    if k > 200:
        return guess      # within 0.01 % here, and the exact search gets slow for large k
    lo, hi = 0.0, max(2 * guess, k + 10 * math.sqrt(2 * k) + 10)
    while _gamma_p(k / 2, hi / 2) < p:
        hi *= 2
    for _ in range(200):
        mid = (lo + hi) / 2
        if _gamma_p(k / 2, mid / 2) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-12 * max(1.0, hi):
            break
    return (lo + hi) / 2


def confidence_interval(dev, edf, confidence=CONFIDENCE):
    """Two-sided interval for a deviation whose variance estimate has `edf`
    chi-squared degrees of freedom: (low, high)."""
    tail = (1 - confidence) / 2
    return (dev * math.sqrt(edf / chi2_ppf(1 - tail, edf)),
            dev * math.sqrt(edf / chi2_ppf(tail, edf)))


def analyze(phase, taus_m, tau0, mean_phase=None, series="seconds"):
    """One row per averaging factor that the data supports.

    phase: phase samples tau0 apart (None = missing), used for ADEV.
    mean_phase: when given, tau0-window mean phases (one per sample of
    `phase`), used for MDEV/TDEV instead of averaging `phase` itself.
    Rules: ADEV needs 3*m samples, MDEV 4*m, so no value rests on one term."""
    rows, last_alpha = [], None
    n_total = len(phase)
    for m in taus_m:
        if n_total < 3 * m:
            continue
        tau = m * tau0
        adev, terms = oadev(phase, m, tau0)
        if adev is None:
            continue
        row = {"tau_s": tau, "series": series, "adev": adev, "adev_terms": terms,
               "adev_low": None, "adev_high": None, "edf": None,
               "noise": None, "noise_assumed": False,
               "mdev": None, "mdev_terms": 0, "tdev_s": None}
        alpha = noise_alpha(phase, m)
        if alpha is None and last_alpha is not None:
            alpha, row["noise_assumed"] = last_alpha, True     # too few points at this tau: keep the last identified type
        if alpha is not None:
            last_alpha = alpha
            row["noise"] = NOISE_NAMES[alpha]
            edf = oadev_edf(alpha, terms + 2 * m, m)
            if edf:
                row["edf"] = edf
                row["adev_low"], row["adev_high"] = confidence_interval(adev, edf)
        if n_total >= 4 * m:
            if mean_phase is None:
                md, mterms = mdev(phase, m, tau0)
            else:
                md, mterms = mdev_from_means(window_means(mean_phase, m), m, tau)
            if md is not None:
                row.update(mdev=md, mdev_terms=mterms, tdev_s=tdev_from_mdev(md, tau))
        rows.append(row)
    return rows


# ── recorder ────────────────────────────────────────────────────────────────

class Recorder:
    """RAM-only phase history fed with kernel PPS timestamps (one per second)."""

    def __init__(self, ring_s=RING_S, ring_minutes=RING_MINUTES, clock=time.time):
        self.clock = clock
        self._lock = threading.Lock()
        self._sec = deque(maxlen=ring_s)          # phase (s) or None, one per second
        self._sec_sel = deque(maxlen=ring_s)      # True/False (PPS selected by chrony) or None
        self._min_last = deque(maxlen=ring_minutes)
        self._min_mean = deque(maxlen=ring_minutes)
        self._min_sel = deque(maxlen=ring_minutes)
        self._last_s = None
        self._first_s = None
        self._minute = None
        self._acc = None
        self.resets = 0
        self._cache = (None, None)

    def _reset(self):
        for d in (self._sec, self._sec_sel, self._min_last, self._min_mean, self._min_sel):
            d.clear()
        self._last_s = self._first_s = self._minute = self._acc = None

    def _flush_minute(self):
        acc = self._acc
        if acc is None:
            return
        self._min_last.append(acc["last"])
        self._min_mean.append(acc["sum"] / acc["n"] if acc["n"] >= MINUTE_MIN_SAMPLES else None)
        self._min_sel.append(acc["sel"] == acc["n"])
        self._acc = None

    def add(self, ts_ns, pps_selected=None):
        """Record one kernel PPS timestamp (CLOCK_REALTIME, integer nanoseconds).
        The phase is its distance from the nearest whole second, found in exact
        integer arithmetic and only then turned into seconds (a float of the
        whole timestamp would resolve just ~0.24 us). A timestamp that does not
        move forward (clock stepped back) restarts the history."""
        second, ph_ns = phase_ns(require_ns(ts_ns))
        phase = ph_ns / 1e9
        with self._lock:
            if self._last_s is not None:
                if second == self._last_s:
                    return
                if second < self._last_s:
                    self._reset()
                    self.resets += 1
            if self._last_s is None:
                self._first_s = second
            else:
                gap = second - self._last_s - 1
                if gap >= self._sec.maxlen:
                    self._sec.clear()
                    self._sec_sel.clear()
                else:
                    self._sec.extend([None] * gap)
                    self._sec_sel.extend([None] * gap)
            self._sec.append(phase)
            self._sec_sel.append(None if pps_selected is None else bool(pps_selected))
            self._last_s = second

            minute = second // 60
            if self._minute is not None and minute != self._minute:
                self._flush_minute()
                skipped = minute - self._minute - 1
                if skipped >= self._min_last.maxlen:
                    for d in (self._min_last, self._min_mean, self._min_sel):
                        d.clear()
                else:
                    for d in (self._min_last, self._min_mean, self._min_sel):
                        d.extend([None] * skipped)
            self._minute = minute
            if self._acc is None:
                self._acc = {"sum": 0.0, "n": 0, "sel": 0, "last": None}
            self._acc["sum"] += phase
            self._acc["n"] += 1
            self._acc["sel"] += 1 if pps_selected else 0
            if second % 60 == 59:
                self._acc["last"] = phase

    @staticmethod
    def _series_info(values, flags, tau0, capacity):
        valid = sum(1 for v in values if v is not None)
        known = [f for f in flags if f is not None]
        return {"tau0_s": tau0, "samples": valid, "gaps": len(values) - valid,
                "span_s": len(values) * tau0, "capacity_s": capacity * tau0,
                "pps_selected_fraction": (sum(1 for f in known if f) / len(known)) if known else None}

    def report(self):
        """The /api/stability payload. Recomputed at most every CACHE_S seconds."""
        now = self.clock()
        cached_at, cached = self._cache
        if cached is not None and 0 <= now - cached_at < CACHE_S:
            return cached
        with self._lock:
            sec, sec_sel = list(self._sec), list(self._sec_sel)
            m_last, m_mean, m_sel = list(self._min_last), list(self._min_mean), list(self._min_sel)
            first_s, resets = self._first_s, self.resets
        points = analyze(sec, TAUS_SECONDS, 1.0, series="seconds")
        points += analyze(m_last, TAUS_MINUTES, 60.0, mean_phase=m_mean, series="minutes")
        out = build_report(points, {
            "seconds": self._series_info(sec, sec_sel, 1.0, self._sec.maxlen),
            "minutes": self._series_info(m_last, m_sel, 60.0, self._min_last.maxlen),
        }, first_s, resets)
        self._cache = (now, out)
        return out


def _tau_label(tau):
    return "1 day" if tau == 86400 else f"{tau:g} s"


def build_report(points, series, first_s, resets=0):
    by_tau = {p["tau_s"]: p for p in points}
    key = []
    for tau in KEY_TAUS_S:
        p = by_tau.get(float(tau))
        need = 3 * tau
        key.append({"tau_s": float(tau), "label": _tau_label(tau), "point": p,
                    "reason": None if p else
                    f"needs about {_span(need)} of PPS history since the service started "
                    f"(three times the averaging time)"})
    sel = series["seconds"]["pps_selected_fraction"]
    notes = []
    if sel is not None and sel < 1.0:
        notes.append(f"chrony had the PPS refclock selected for {sel * 100:.0f}% of the 1 s series; "
                     f"the rest describes the clock under another source, measured against PPS.")
    if series["seconds"]["gaps"]:
        notes.append(f"{series['seconds']['gaps']} of the last {int(series['seconds']['span_s'])} seconds "
                     f"have no PPS sample; terms touching them are left out.")
    return {
        "available": bool(points),
        "reason": None if points else
                  ("No kernel PPS events have been observed since the service started."
                   if not series["seconds"]["samples"] else
                   "Not enough PPS history yet: the shortest averaging time needs 3 samples."),
        "provenance": "calculated",
        "measurement_layer": LAYER_NOTE,
        "method": ("Overlapping Allan deviation, modified Allan deviation and time deviation "
                   "(NIST SP 1065). Input: the fractional second of each kernel PPS timestamp. "
                   "Up to 2000 s from 1 s samples; from 1 h from minute summaries "
                   "(last sample of each minute for ADEV, minute mean for MDEV and TDEV)."),
        "confidence": {
            "level": CONFIDENCE,
            "applies_to": "adev",
            "method": ("Chi-squared interval; degrees of freedom from the power-law noise type "
                       "identified by lag-1 autocorrelation (SP 1065 sections 5.4.1 and 5.5.6). "
                       "No interval is calculated for MDEV or TDEV."),
            "noise_provenance": "inferred",
        },
        "storage": "RAM only; lost when the service restarts",
        "since_utc": (datetime.fromtimestamp(first_s, timezone.utc).isoformat(timespec="seconds")
                      if first_s is not None else None),
        "history_resets": resets,
        "series": series,
        "points": points,
        "key_points": key,
        "notes": notes,
    }


def _span(seconds):
    if seconds >= 86400:
        return f"{seconds / 86400:g} days"
    if seconds >= 3600:
        return f"{seconds / 3600:g} h"
    if seconds >= 60:
        return f"{seconds / 60:g} min"
    return f"{seconds:g} s"
