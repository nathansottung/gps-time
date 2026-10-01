"""Human-readable formatting of small time quantities.

The rule from the design doc: never make a person count zeros, and never
show an offset without its uncertainty when both are known. Full precision
is preserved internally; only display is rounded.
"""


def fmt_seconds(sec, signed=False):
    """0.000000157 -> '157 ns'; 0.0037 -> '3.70 ms'; 2.5 -> '2.5 s'."""
    if sec is None:
        return "–"
    sign = "-" if sec < 0 else ("+" if signed and sec > 0 else "")
    a = abs(sec)
    if a >= 1:
        return f"{sign}{a:.3f} s"
    if a >= 1e-3:
        return f"{sign}{a * 1e3:.2f} ms"
    if a >= 1e-6:
        return f"{sign}{a * 1e6:.2f} µs"
    return f"{sign}{a * 1e9:.0f} ns"


def fmt_offset(sec):
    """Signed offset in chrony's slow/fast phrasing: '157 ns slow'."""
    if sec is None:
        return "–"
    if sec == 0:
        return "0 ns"
    word = "fast" if sec > 0 else "slow"
    return f"{fmt_seconds(abs(sec))} {word}"


def fmt_pair(offset_sec, err_sec):
    """'157 ns slow ± 203 ns' — offset and uncertainty always together."""
    if offset_sec is None:
        return "–"
    if err_sec is None:
        return fmt_offset(offset_sec)
    return f"{fmt_offset(offset_sec)} ± {fmt_seconds(abs(err_sec))}"


def fmt_duration(sec):
    """86500 -> '24 h 1 m 40 s'; 754 -> '12 m 34 s'."""
    if sec is None:
        return "–"
    sec = int(round(sec))
    sign = "-" if sec < 0 else ""
    sec = abs(sec)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{sign}{h} h {m} m {s} s"
    if m:
        return f"{sign}{m} m {s} s"
    return f"{sign}{s} s"


def fmt_delta(sec):
    """Signed duration for daylight deltas: '-2 m 18 s'."""
    if sec is None:
        return "–"
    sign = "+" if sec >= 0 else "\u2212"
    return f"{sign}{fmt_duration(abs(sec))}"
