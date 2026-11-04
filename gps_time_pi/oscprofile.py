"""Oscillator profile fit: this board's frequency against temperature, plus slow aging
(roadmap/ROADMAP-OSCILLATOR-AND-MISC.md §1, "fit"). Pure; no NumPy.

Input: the oscillator log's 10-minute bins (oscillator.py) in which chrony had the PPS
refclock selected throughout: (time, mean SoC temperature, mean chrony frequency in ppm).

Model, in ppm (+ = the uncorrected clock runs fast):

    f(T, t) = a + b·(T − T0) [+ c·(T − T0)²] [+ d·(t − t0) in days]

T0 is the mean temperature of the bins used, t0 the time of the first one. The quadratic
term is a candidate only with at least QUAD_MIN_SPAN_C of temperature range, the aging term
only with at least AGING_MIN_SPAN_D days of data; among the candidates the model with the
lowest BIC is kept (so a term must earn its place). One pass of outlier removal: bins more
than OUTLIER_K robust standard deviations (1.4826 × MAD) from the first fit are left out and
counted, never silently.

What it is: a statistical model of how chrony's frequency estimate moved with the SoC
sensor's temperature (and with time) while GPS kept the clock right. Labelled `modeled`.
What it isn't: a measurement of the crystal (the sensor is the processor's), a guarantee of
holdover, or valid outside the temperature range and time span it covers (`covers`).
"""

import math

MIN_BINS = 72                 # 12 hours of PPS-selected bins
MIN_TEMP_SPAN_C = 3.0         # a temperature term needs the temperature to have moved
QUAD_MIN_SPAN_C = 8.0
AGING_MIN_SPAN_D = 3.0
OUTLIER_K = 5.0
MAX_BINS = 90 * 144           # 90 days of 10-minute bins

TERMS = {"linear": ("a", "b"), "quadratic": ("a", "b", "c"),
         "linear+aging": ("a", "b", "d"), "quadratic+aging": ("a", "b", "c", "d")}
UNITS = {"a": "ppm", "b": "ppm/°C", "c": "ppm/°C²", "d": "ppm/day"}


def _solve(xtx, xty):
    """Gauss-Jordan with partial pivoting; returns (beta, inverse of xtx) or None if singular."""
    n = len(xtx)
    m = [list(row) + [xty[i]] + [1.0 if j == i else 0.0 for j in range(n)] for i, row in enumerate(xtx)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-15:
            return None
        m[c], m[p] = m[p], m[c]
        piv = m[c][c]
        m[c] = [v / piv for v in m[c]]
        for r in range(n):
            if r != c and m[r][c] != 0.0:
                f = m[r][c]
                m[r] = [vr - f * vc for vr, vc in zip(m[r], m[c])]
    return [m[i][n] for i in range(n)], [m[i][n + 1:] for i in range(n)]


def _design(row, terms):
    dT, dd = row
    return [{"a": 1.0, "b": dT, "c": dT * dT, "d": dd}[k] for k in terms]


def _ols(rows, ys, terms):
    """Least squares; returns coefficients, standard errors, residuals, RSS, or None."""
    p = len(terms)
    if len(rows) <= p:
        return None
    X = [_design(r, terms) for r in rows]
    xtx = [[sum(x[i] * x[j] for x in X) for j in range(p)] for i in range(p)]
    xty = [sum(x[i] * y for x, y in zip(X, ys)) for i in range(p)]
    sol = _solve(xtx, xty)
    if sol is None:
        return None
    beta, inv = sol
    res = [y - sum(b * v for b, v in zip(beta, x)) for x, y in zip(X, ys)]
    rss = sum(r * r for r in res)
    s2 = rss / (len(rows) - p)
    se = [math.sqrt(max(0.0, inv[i][i] * s2)) for i in range(p)]
    return {"beta": beta, "se": se, "res": res, "rss": rss}


def _bic(n, rss, p):
    return n * math.log(max(rss, 1e-300) / n) + p * math.log(n)


def fit(bins):
    """bins: iterable of (t_epoch_s, temp_c, freq_ppm), PPS selected throughout. Returns the profile dict."""
    pts = [(t, T, f) for t, T, f in bins
           if t is not None and T is not None and f is not None and math.isfinite(T) and math.isfinite(f)]
    pts.sort()
    pts = pts[-MAX_BINS:]
    out = {"status": "insufficient", "reason": None, "provenance": "modeled", "model": None, "terms": [],
           "bins_used": len(pts), "outliers": 0, "residual_rms_ppm": None, "r2": None,
           "t0_utc_epoch": None, "temp_ref_c": None, "covers": None, "candidates": []}
    if len(pts) < MIN_BINS:
        out["reason"] = f"needs {MIN_BINS} bins (12 h) with PPS selected throughout; {len(pts)} so far"
        return out
    temps = [p[1] for p in pts]
    span_c = max(temps) - min(temps)
    t0 = pts[0][0]
    span_d = (pts[-1][0] - t0) / 86400.0
    out["covers"] = {"temp_min_c": round(min(temps), 2), "temp_max_c": round(max(temps), 2),
                     "first_utc_epoch": pts[0][0], "last_utc_epoch": pts[-1][0], "days": round(span_d, 3)}
    if span_c < MIN_TEMP_SPAN_C:
        out["reason"] = (f"the temperature has varied by only {span_c:.1f} °C; the fit needs at least "
                         f"{MIN_TEMP_SPAN_C:g} °C")
        return out

    def run(points):
        T0 = sum(p[1] for p in points) / len(points)
        rows = [(p[1] - T0, (p[0] - t0) / 86400.0) for p in points]
        ys = [p[2] for p in points]
        names = ["linear"]
        if span_c >= QUAD_MIN_SPAN_C:
            names.append("quadratic")
        if span_d >= AGING_MIN_SPAN_D:
            names.append("linear+aging")
            if span_c >= QUAD_MIN_SPAN_C:
                names.append("quadratic+aging")
        results = []
        for name in names:
            r = _ols(rows, ys, TERMS[name])
            if r:
                results.append((name, r, _bic(len(points), r["rss"], len(TERMS[name]))))
        return T0, ys, results

    T0, ys, results = run(pts)
    if not results:
        out["reason"] = "the fit could not be solved (the data don't separate the terms)"
        return out
    name, best, _ = min(results, key=lambda x: x[2])
    # One pass of outlier removal against the chosen model, then refit.
    res = best["res"]
    med = sorted(res)[len(res) // 2]
    mad = sorted(abs(r - med) for r in res)[len(res) // 2] * 1.4826
    keep = [p for p, r in zip(pts, res) if mad == 0 or abs(r - med) <= OUTLIER_K * mad]
    outliers = len(pts) - len(keep)
    if outliers and len(keep) >= MIN_BINS:
        T0, ys, results = run(keep)
        name, best, _ = min(results, key=lambda x: x[2])
        pts = keep
    else:
        outliers = 0
    n = len(pts)
    mean_y = sum(ys) / n
    tss = sum((y - mean_y) ** 2 for y in ys)
    terms = TERMS[name]
    out.update(
        status="fitted", reason=None, model=name, bins_used=n, outliers=outliers,
        residual_rms_ppm=round(math.sqrt(best["rss"] / n), 5),
        r2=round(1 - best["rss"] / tss, 4) if tss > 0 else None,
        t0_utc_epoch=t0, temp_ref_c=round(T0, 3),
        terms=[{"name": k, "value": best["beta"][i], "se": best["se"][i], "unit": UNITS[k]} for i, k in enumerate(terms)],
        candidates=[{"model": nm, "bic": round(b, 2)} for nm, _, b in results],
    )
    return out


def predict(profile, temp_c, t_epoch):
    """Modeled frequency (ppm) at a temperature and time, and whether it is inside what the fit covers.
    (None, reason) without a fitted profile."""
    if not profile or profile.get("status") != "fitted":
        return None, "no fitted profile"
    c = {t["name"]: t["value"] for t in profile["terms"]}
    dT = temp_c - profile["temp_ref_c"]
    dd = (t_epoch - profile["t0_utc_epoch"]) / 86400.0
    f = c.get("a", 0.0) + c.get("b", 0.0) * dT + c.get("c", 0.0) * dT * dT + c.get("d", 0.0) * dd
    cov = profile["covers"]
    inside = cov["temp_min_c"] <= temp_c <= cov["temp_max_c"] and t_epoch <= cov["last_utc_epoch"] + 86400
    return f, None if inside else "outside the temperature range or time span the fit covers (extrapolated)"


# -- holdover projection (GPS-008) ----------------------------------------------------------

THRESHOLDS_S = (1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1.0)
DEFAULT_EXCURSION_C = 5.0      # temperature change assumed when the last day's swing isn't known

HOLDOVER_NOTE = ("Projections of how long the clock would take to drift past each error if GPS and PPS went "
                 "away now and chrony kept running on its last frequency estimate. All three are models, not "
                 "measurements and not guarantees: none has been checked against a real outage yet (that "
                 "needs the offset measured when PPS comes back).")


def _time_to(err_s, rate, accel):
    """Time (s) for |x| = rate·τ + accel·τ²/2 to reach err_s; rate and accel as fractions (s/s, 1/s)."""
    if accel > 0:
        return (-rate + math.sqrt(rate * rate + 2 * accel * err_s)) / accel
    return err_s / rate if rate > 0 else None


def _freq_change(profile, temp_c, lo, hi):
    """Largest |f(T) − f(temp_c)| in ppm for T in [lo, hi], from the profile's temperature terms."""
    c = {t["name"]: t["value"] for t in profile["terms"]}
    b, cc, T0 = c.get("b", 0.0), c.get("c", 0.0), profile["temp_ref_c"]

    def f(T):
        dT = T - T0
        return b * dT + cc * dT * dT
    pts = [lo, hi]
    if cc:
        v = T0 - b / (2 * cc)                         # the parabola's vertex
        if lo < v < hi:
            pts.append(v)
    return max(abs(f(T) - f(temp_c)) for T in pts)


def holdover(profile, freq_ppm, skew_ppm, temp_c, temp_range=None, scorecard=None):
    """The projections below, and with a scorecard (holdover_check.Scorecard.summary()) how each
    model did against real outages; from SCORE_MIN eligible outages on, a `scored` projection too."""
    return apply_scorecard(_holdover(profile, freq_ppm, skew_ppm, temp_c, temp_range), scorecard)


def apply_scorecard(out, scorecard):
    """Feed the measured outages into the projections: each model's record, and a `scored`
    projection whose rate is the profile's (else the trained) rate times the worst measured/predicted
    ratio seen, never less than the model itself. Still `modeled`: a model scaled by measurements."""
    if not scorecard:
        return out
    out["scorecard"] = scorecard
    rec = {m["name"]: m for m in scorecard.get("models", [])}
    for p in out["projections"]:
        p["validated"] = rec.get(p["name"])
    n = scorecard.get("eligible", 0)
    if n:
        out["note"] = (f"Projections of how long the clock would take to drift past each error if GPS and PPS went "
                       f"away now and chrony kept running on its last frequency estimate. Models, not guarantees; "
                       f"checked so far against {n} outage{'s' if n != 1 else ''} measured at the first good PPS "
                       f"pulse after recovery (the scorecard below).")
    base = next((p for p in out["projections"] if p["name"] == "profile" and p.get("available")), None) or         next((p for p in out["projections"] if p["name"] == "trained_skew" and p.get("available")), None)
    from .holdover_check import SCORE_MIN
    if n < SCORE_MIN:
        out["projections"].append({"name": "scored", "provenance": "modeled", "available": False,
                                   "rate_ppm": None, "aging_ppm_per_day": 0.0, "times_s": [None] * len(THRESHOLDS_S),
                                   "reason": f"needs {SCORE_MIN} scored outages, has {n}"})
        return out
    worst = (rec.get(base["name"]) or {}).get("worst_ratio") if base else None
    if base is None or worst is None:
        out["projections"].append({"name": "scored", "provenance": "modeled", "available": False,
                                   "rate_ppm": None, "aging_ppm_per_day": 0.0, "times_s": [None] * len(THRESHOLDS_S),
                                   "reason": "no profile or trained projection now, or no record for it"})
        return out
    k = max(1.0, worst)
    rate, aging = base["rate_ppm"] * k, (base.get("aging_ppm_per_day") or 0.0) * k
    r, a = abs(rate) * 1e-6, abs(aging) * 1e-6 / 86400.0
    out["projections"].append({
        "name": "scored", "provenance": "modeled", "available": True, "rate_ppm": rate,
        "aging_ppm_per_day": aging, "times_s": [_time_to(e, r, a) for e in THRESHOLDS_S],
        "factor": round(k, 4), "from": base["name"], "outages": n,
        "basis": (f"the {base['name'].replace('_', ' ')} rate times {k:.3g}, the worst measured/predicted ratio "
                  f"over {n} scored outages" + (" (it never did worse than predicted, so unscaled)" if worst <= 1 else ""))})
    return out


def _holdover(profile, freq_ppm, skew_ppm, temp_c, temp_range=None):
    """Time to each error threshold in holdover, three ways, all `modeled`:

    - free_running: the clock without chrony's correction (|Frequency|): an untrained crystal;
    - trained_skew: chrony keeps its learned correction; the error grows at Skew, chrony's own
      bound on its frequency estimate. No temperature, no aging;
    - profile: as trained_skew, plus the profile's residual RMS (wander the fit doesn't explain),
      the largest frequency change the profile gives for a temperature anywhere in temp_range
      (the last 24 h's observed (min, max); else ±DEFAULT_EXCURSION_C from now), and the aging
      term as a frequency ramp. Needs a fitted profile.

    Rates are magnitudes added together (a pessimistic sum, not an RSS), as if the worst
    temperature were reached at once. Times in seconds; None where the rate is zero."""
    out = {"provenance": "modeled", "thresholds_s": list(THRESHOLDS_S), "note": HOLDOVER_NOTE,
           "projections": []}

    def proj(name, rate_ppm, aging_ppm_day=0.0, **extra):
        times = [None] * len(THRESHOLDS_S)
        if rate_ppm is not None:
            rate, accel = abs(rate_ppm) * 1e-6, abs(aging_ppm_day) * 1e-6 / 86400.0
            times = [_time_to(e, rate, accel) for e in THRESHOLDS_S]
        out["projections"].append({"name": name, "provenance": "modeled", "rate_ppm": rate_ppm,
                                   "aging_ppm_per_day": aging_ppm_day, "times_s": times, **extra})

    if freq_ppm is None:
        proj("free_running", None, available=False, reason="chrony's frequency is not known")
    else:
        proj("free_running", abs(freq_ppm), available=True,
             basis="|chrony Frequency|: how fast the clock would run with no correction at all")
    if skew_ppm is None:
        proj("trained_skew", None, available=False, reason="chrony's skew is not known")
    else:
        proj("trained_skew", abs(skew_ppm), available=True,
             basis="chrony Skew: its own bound on the error of the frequency it would keep applying; "
                   "no temperature, no aging")

    if not profile or profile.get("status") != "fitted":
        why = profile.get("reason") if profile else None
        proj("profile", None, available=False, reason="no fitted oscillator profile" + (f": {why}" if why else ""))
        return out
    if skew_ppm is None or temp_c is None:
        proj("profile", None, available=False, reason="chrony's skew or the SoC temperature is not known now")
        return out
    if temp_range and None not in temp_range:
        lo, hi = min(temp_range[0], temp_c), max(temp_range[1], temp_c)
        source = "the last 24 h's temperature range"
    else:
        lo, hi = temp_c - DEFAULT_EXCURSION_C, temp_c + DEFAULT_EXCURSION_C
        source = f"assumed ±{DEFAULT_EXCURSION_C:g} °C from now (no 24 h range yet)"
    dtemp = _freq_change(profile, temp_c, lo, hi)
    resid = profile.get("residual_rms_ppm") or 0.0
    aging = next((t["value"] for t in profile["terms"] if t["name"] == "d"), 0.0)
    cov = profile["covers"]
    inside = cov["temp_min_c"] <= lo and hi <= cov["temp_max_c"]
    proj("profile", abs(skew_ppm) + resid + dtemp, aging, available=True,
         components_ppm={"skew": abs(skew_ppm), "residual_rms": resid, "temperature": round(dtemp, 6)},
         temp_now_c=round(temp_c, 2), temp_assumed_c=[round(lo, 2), round(hi, 2)], temp_source=source,
         extrapolated=not inside,
         basis=(f"Skew + the profile's residual RMS + its largest frequency change for {lo:.1f}–{hi:.1f} °C"
                + (" + aging as a ramp" if aging else "")),
         caveat=None if inside else ("the temperatures assumed go beyond what the profile has seen "
                                     f"({cov['temp_min_c']:.1f}–{cov['temp_max_c']:.1f} °C); extrapolated"))
    return out
