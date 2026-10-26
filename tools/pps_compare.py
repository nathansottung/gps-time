"""Compare the station's second pulse with the receiver's PPS, from a scope or counter CSV.

    python tools/pps_compare.py measurements.csv [--column NAME|N] [--unit s|ms|us|ns]
                                [--sign gpio-minus-pps|pps-minus-gpio]
                                [--delay-gpio-ns D] [--delay-pps-ns D]
                                [--pulse-log secpulse.csv] [--json]

Input: one time interval per second between the receiver's PPS and the
station's second pulse (gps_time_pi/secpulse.py), as a time-interval counter
or a scope's delay measurement exports them. Delimiter, header lines, unit
suffixes ("1.2E-06 s", "850ns") and units in the header ("Delay (us)") are
recognised; --column and --unit override.

What it reports (labels as in web/guidelines/Guidelines.md):
- x = t(second pulse edge) - t(PPS edge), after the cable/probe delays given
  (observed by the instrument; corrected values calculated).
- Statistics of x: mean, SD, median, percentiles, range, drift, and ADEV/TDEV
  of x as a phase series at 1 s spacing (calculated).
- What x says about the system clock. With e = system clock minus PPS time
  and L >= 0 the latency from the second boundary to the edge, x = L - e.
  Without the pulse log, L is unknown, so only a bound follows: the system
  clock is not behind PPS by more than x (calculated). With --pulse-log,
  the edge is taken at the middle of the logged write window, which is a
  model, so e is labelled modeled, with half the window as its uncertainty.

What it can't say: anything about PPS against UTC (the receiver's PPS error,
antenna cable delay), or a cause for any outlier. Values more than 0.5 s from
zero are pairing errors (a missed or extra edge) and are dropped and counted;
values far from the median are flagged as outliers and left out of the
statistics unless --keep-outliers.
"""

import argparse
import csv
import io
import json
import math
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gps_time_pi import stability  # noqa: E402

UNITS = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "µs": 1e-6, "μs": 1e-6, "ns": 1e-9, "ps": 1e-12}
NUM = re.compile(r"^\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*([a-zA-Zµμ]*)\s*$")
HEADER_UNIT = re.compile(r"[\(\[]\s*(s|ms|us|µs|μs|ns|ps)\s*[\)\]]")
PREFERRED = re.compile(r"interval|delay|\bti\b|offset|value|meas|delta|skew", re.I)
PAIRING_LIMIT_S = 0.5
OUTLIER_MADS = 10.0
OUTLIER_FLOOR_S = 1e-6
TAUS = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)


def parse_number(cell):
    """(value_in_s_or_None_if_no_unit_suffix, unit_scale_or_None) or None if not numeric."""
    m = NUM.match(cell.replace(",", ".") if cell.count(",") == 1 and "." not in cell else cell)
    if not m:
        return None
    unit = m.group(2)
    if unit and unit not in UNITS:
        return None
    return float(m.group(1)), (UNITS[unit] if unit else None)


def _rows(text):
    lines = [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    body = "\n".join(lines)
    try:
        dialect = csv.Sniffer().sniff("\n".join(lines[:50]), delimiters=",;\t")
        rows = list(csv.reader(io.StringIO(body), dialect))
    except csv.Error:
        rows = [l.split() for l in lines]     # whitespace-separated, or one value per line
    return [[c.strip() for c in r] for r in rows if any(c.strip() for c in r)]


def read_intervals(text, column=None, unit=None):
    """Interval values in seconds, one per data row, in file order; plus what was assumed."""
    rows = _rows(text)
    header, data = None, []
    for r in rows:
        parsed = [parse_number(c) for c in r]
        if 2 * sum(1 for p in parsed if p is not None) >= len(parsed):   # a data row: at least half numbers
            data.append((r, parsed))
        elif not data:
            header = r                       # the last non-numeric row before the data
    if not data:
        raise ValueError("no numeric rows found")
    width = max(len(p) for _, p in data)
    if width == 1 and header and len(header) > 1:
        header = [" ".join(header)]          # one value per line: the header is one name
    numeric_cols = [i for i in range(width)
                    if sum(1 for _, p in data if i < len(p) and p[i] is not None) >= 0.9 * len(data)]
    if column is not None:
        if str(column).isdigit():
            col = int(column) - 1
        elif header and column in header:
            col = header.index(column)
        else:
            raise ValueError(f"column {column!r} not found (header: {header})")
    elif len(numeric_cols) == 1:
        col = numeric_cols[0]
    else:
        named = [i for i in numeric_cols if header and i < len(header) and PREFERRED.search(header[i])]
        if not named:
            raise ValueError(f"several numeric columns {[i + 1 for i in numeric_cols]}; choose one with --column")
        col = named[0]
    name = header[col] if header and col < len(header) else f"column {col + 1}"
    scale, how = None, None
    if unit:
        scale, how = UNITS[unit], f"--unit {unit}"
    elif header and col < len(header) and HEADER_UNIT.search(header[col]):
        u = HEADER_UNIT.search(header[col]).group(1)
        scale, how = UNITS[u], f"unit {u} from the header"
    values, suffixed = [], 0
    for _, p in data:
        if col >= len(p) or p[col] is None:
            values.append(None)
            continue
        v, suffix_scale = p[col]
        if suffix_scale is not None:
            suffixed += 1
            values.append(v * suffix_scale)
        else:
            values.append(v * (scale if scale is not None else 1.0))
    if scale is None and not suffixed:
        how = "no unit given or found: seconds assumed"
    elif scale is None:
        how = "units from each value's suffix"
    return values, {"column": name, "unit": how, "rows": len(data)}


def read_pulse_log(text):
    """secpulse --log: [(second, before_ns, after_ns)]."""
    out = []
    for r in csv.reader(io.StringIO(text)):
        if len(r) >= 3 and r[0].strip().isdigit():
            out.append((int(r[0]), int(r[1]), int(r[2])))
    return out


def _pct(sorted_v, p):
    if not sorted_v:
        return None
    k = (len(sorted_v) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return sorted_v[lo] + (sorted_v[hi] - sorted_v[lo]) * (k - lo)


def _slope(xs):
    pts = [(i, v) for i, v in enumerate(xs) if v is not None]
    if len(pts) < 3:
        return None
    mi = statistics.fmean(i for i, _ in pts)
    mv = statistics.fmean(v for _, v in pts)
    den = sum((i - mi) ** 2 for i, _ in pts)
    return sum((i - mi) * (v - mv) for i, v in pts) / den if den else None


def q(value, unit, provenance, note=None):
    d = {"value": value, "unit": unit, "provenance": provenance}
    if note:
        d["note"] = note
    return d


def analyze(raw, sign=1.0, delay_gpio_s=0.0, delay_pps_s=0.0, keep_outliers=False, pulse_log=None):
    """The report for interval values in seconds (None = missing). Pure; no I/O."""
    x = [None if v is None else sign * v - delay_gpio_s + delay_pps_s for v in raw]
    pairing = [i for i, v in enumerate(x) if v is not None and abs(v) > PAIRING_LIMIT_S]
    for i in pairing:
        x[i] = None
    present = [v for v in x if v is not None]
    if not present:
        raise ValueError("no usable intervals")
    med = statistics.median(present)
    mad = statistics.median(abs(v - med) for v in present) * 1.4826
    limit = max(OUTLIER_MADS * mad, OUTLIER_FLOOR_S)
    outliers = [i for i, v in enumerate(x) if v is not None and abs(v - med) > limit]
    if not keep_outliers:
        for i in outliers:
            x[i] = None
    kept = sorted(v for v in x if v is not None)
    n = len(kept)
    mean = statistics.fmean(kept)
    sd = statistics.stdev(kept) if n > 1 else None
    slope = _slope(x)
    devs = []
    for m in TAUS:
        if 2 * m >= len(x):
            break
        a, terms = stability.oadev(x, m)
        md, _ = stability.mdev(x, m)
        if a is None:
            continue
        devs.append({"tau_s": m, "adev": a, "tdev_s": stability.tdev_from_mdev(md, m), "terms": terms})
    report = {
        "samples": {"rows": len(raw), "used": n, "missing": sum(1 for v in raw if v is None),
                    "pairing_errors": len(pairing), "outliers": len(outliers),
                    "outliers_kept": bool(keep_outliers), "outlier_limit_s": limit},
        "corrections": {"sign": "gpio-minus-pps" if sign > 0 else "pps-minus-gpio",
                        "delay_gpio_s": delay_gpio_s, "delay_pps_s": delay_pps_s,
                        "note": None if (delay_gpio_s or delay_pps_s) else
                        "no cable or probe delays given: x includes their difference"},
        "x": {
            "definition": "t(second pulse edge) - t(PPS edge)",
            "mean": q(mean, "s", "calculated"),
            "sd": q(sd, "s", "calculated"),
            "median": q(statistics.median(kept), "s", "calculated"),
            "min": q(kept[0], "s", "observed"), "max": q(kept[-1], "s", "observed"),
            "p05": q(_pct(kept, 0.05), "s", "calculated"), "p95": q(_pct(kept, 0.95), "s", "calculated"),
            "p01": q(_pct(kept, 0.01) if n >= 100 else None, "s", "calculated"),
            "p99": q(_pct(kept, 0.99) if n >= 100 else None, "s", "calculated"),
            "drift": q(slope, "s/s", "calculated", "slope of x against row number, assuming one row per second"),
        },
        "stability": devs,
        "clock": {
            "bound": q(mean, "s", "calculated",
                       "the system clock is not behind PPS by more than this, on average "
                       "(x = L - e with the write latency L >= 0 unknown)"),
            "offset": None,
        },
        "limits": ["Compares the system clock with this receiver's PPS only; says nothing about PPS against UTC.",
                   "Outliers and pairing errors are counted, not explained."],
    }
    if pulse_log:
        mids = [(b + a) / 2e9 for _, b, a in pulse_log]
        halves = [(a - b) / 2e9 for _, b, a in pulse_log]
        L = statistics.fmean(mids)
        report["pulse_log"] = {"pulses": len(pulse_log),
                               "write_done_after_median": q(statistics.median(a / 1e9 for _, _, a in pulse_log), "s", "observed"),
                               "write_window_median": q(statistics.median(2 * h for h in halves), "s", "observed")}
        report["clock"]["offset"] = q(L - mean, "s", "modeled",
                                      "system clock minus PPS time, taking each edge at the middle of its logged "
                                      f"write window; uncertainty +/-{statistics.fmean(halves) * 1e9:.0f} ns from the window, "
                                      "plus the SD of the mean of x")
    return report


def text_report(r, meta):
    def ns(d):
        v = d["value"] if isinstance(d, dict) else d
        return "UNKNOWN" if v is None else f"{v * 1e9:,.1f} ns"
    s, x = r["samples"], r["x"]
    d = x["drift"]["value"]
    drift = "UNKNOWN" if d is None else f"{d * 1e9:.3f} ns/s"
    lines = [f"Input: {meta['rows']} rows, {meta['column']}; {meta['unit']}.",
             f"Used {s['used']}; missing {s['missing']}; pairing errors {s['pairing_errors']}; "
             f"outliers {s['outliers']} ({'kept' if s['outliers_kept'] else 'left out'}, beyond +/-{s['outlier_limit_s'] * 1e9:,.0f} ns of the median).",
             f"Sign: {r['corrections']['sign']}; delays gpio {r['corrections']['delay_gpio_s'] * 1e9:g} ns, pps {r['corrections']['delay_pps_s'] * 1e9:g} ns."
             + (f" Note: {r['corrections']['note']}." if r['corrections']['note'] else ""),
             "",
             f"x = {x['definition']}  (calculated from observed intervals)",
             f"  mean {ns(x['mean'])}   SD {ns(x['sd'])}   median {ns(x['median'])}",
             f"  min {ns(x['min'])}   max {ns(x['max'])}   p05 {ns(x['p05'])}   p95 {ns(x['p95'])}"
             + (f"   p01 {ns(x['p01'])}   p99 {ns(x['p99'])}" if x['p01']['value'] is not None else ""),
             f"  drift {drift} (one row per second assumed)"]
    if r["stability"]:
        lines.append("")
        lines.append("  tau (s)   ADEV of x      TDEV")
        for d in r["stability"]:
            tdev = "UNKNOWN" if d["tdev_s"] is None else f"{d['tdev_s'] * 1e9:.2f} ns"
            lines.append(f"  {d['tau_s']:>7}   {d['adev']:.3e}   {tdev}")
    lines += ["", "System clock (e = system clock minus PPS time):",
              f"  bound: not behind PPS by more than {ns(r['clock']['bound'])} on average (calculated; write latency unknown)"]
    if r["clock"]["offset"]:
        lines.append(f"  offset: {ns(r['clock']['offset'])} (modeled: {r['clock']['offset']['note']})")
    lines += [""] + [f"Limit: {t}" for t in r["limits"]]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("csv")
    ap.add_argument("--column")
    ap.add_argument("--unit", choices=sorted(UNITS))
    ap.add_argument("--sign", choices=("gpio-minus-pps", "pps-minus-gpio"), default="gpio-minus-pps",
                    help="what the instrument's value means: counter started by PPS and stopped by the pulse "
                         "gives gpio-minus-pps (default)")
    ap.add_argument("--delay-gpio-ns", type=float, default=0.0, help="cable and probe delay of the pulse channel")
    ap.add_argument("--delay-pps-ns", type=float, default=0.0, help="cable and probe delay of the PPS channel")
    ap.add_argument("--pulse-log", help="the CSV from python -m gps_time_pi.secpulse --log")
    ap.add_argument("--keep-outliers", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        raw, meta = read_intervals(Path(a.csv).read_text(encoding="utf-8-sig", errors="replace"), a.column, a.unit)
        log = read_pulse_log(Path(a.pulse_log).read_text(encoding="ascii")) if a.pulse_log else None
        r = analyze(raw, 1.0 if a.sign == "gpio-minus-pps" else -1.0, a.delay_gpio_ns * 1e-9, a.delay_pps_ns * 1e-9,
                    a.keep_outliers, log)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    r["input"] = meta
    print(json.dumps(r, indent=2) if a.json else text_report(r, meta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
