"""Oscillator profile fit (gps_time_pi/oscprofile.py) on synthetic bins with known coefficients.

No station data: every series is generated here, seeded, from a stated model plus noise.
"""

import math
import random
import unittest

from tests import _env  # noqa: F401
from gps_time_pi import oscprofile as op

T_START = 1_793_000_000.0


def series(days, temp_fn, f_fn, noise=0.002, seed=1, step_s=600):
    rnd = random.Random(seed)
    out = []
    n = int(days * 86400 / step_s)
    for i in range(n):
        t = T_START + i * step_s
        T = temp_fn(i * step_s / 86400.0)
        out.append((t, T, f_fn(T, (t - T_START) / 86400.0) + rnd.gauss(0, noise)))
    return out


def daily(lo, hi):
    """A daily temperature cycle between lo and hi °C."""
    return lambda d: lo + (hi - lo) * (0.5 + 0.5 * math.sin(2 * math.pi * d))


def term(p, name):
    return next(t for t in p["terms"] if t["name"] == name)


class TestFit(unittest.TestCase):
    def test_linear_recovered(self):
        p = op.fit(series(2, daily(40, 46), lambda T, d: 10.3 + 0.08 * (T - 43)))
        self.assertEqual((p["status"], p["model"], p["provenance"]), ("fitted", "linear", "modeled"))
        b = term(p, "b")
        self.assertAlmostEqual(b["value"], 0.08, delta=3 * b["se"] + 1e-4)
        self.assertLess(p["residual_rms_ppm"], 0.003)
        self.assertGreater(p["r2"], 0.99)
        self.assertEqual(p["covers"]["days"], round((2 * 144 - 1) * 600 / 86400, 3))

    def test_quadratic_and_aging_when_the_data_support_them(self):
        f = lambda T, d: 10.0 + 0.05 * (T - 45) - 0.004 * (T - 45) ** 2 + 0.01 * d
        p = op.fit(series(6, daily(38, 52), f))
        self.assertEqual(p["model"], "quadratic+aging")
        self.assertAlmostEqual(term(p, "c")["value"], -0.004, delta=5e-4)
        self.assertAlmostEqual(term(p, "d")["value"], 0.01, delta=1e-3)
        self.assertEqual({c["model"] for c in p["candidates"]}, set(op.TERMS))

    def test_no_aging_term_on_a_short_log(self):
        p = op.fit(series(1, daily(40, 50), lambda T, d: 10 + 0.05 * T + 0.05 * d))
        self.assertNotIn("aging", p["model"])
        self.assertNotIn("linear+aging", [c["model"] for c in p["candidates"]])

    def test_bic_keeps_out_a_term_the_data_dont_need(self):
        p = op.fit(series(6, daily(38, 52), lambda T, d: 10 + 0.05 * (T - 45)))
        self.assertEqual(p["model"], "linear")

    def test_outliers_counted_and_left_out(self):
        s = series(2, daily(40, 46), lambda T, d: 10 + 0.08 * (T - 43))
        s[50] = (s[50][0], s[50][1], s[50][2] + 2.0)
        s[120] = (s[120][0], s[120][1], s[120][2] - 3.0)
        p = op.fit(s)
        self.assertEqual(p["outliers"], 2)
        self.assertAlmostEqual(term(p, "b")["value"], 0.08, delta=0.002)

    def test_insufficient(self):
        p = op.fit(series(0.25, daily(40, 46), lambda T, d: 10))
        self.assertEqual(p["status"], "insufficient")
        self.assertIn("needs 72 bins", p["reason"])
        p = op.fit(series(2, lambda d: 45 + 0.5 * math.sin(d), lambda T, d: 10))
        self.assertIn("varied by only", p["reason"])
        self.assertEqual(op.fit([])["bins_used"], 0)

    def test_bad_values_ignored(self):
        s = series(2, daily(40, 46), lambda T, d: 10 + 0.08 * T)
        s += [(T_START, None, 1.0), (T_START, 40.0, float("nan"))]
        self.assertEqual(op.fit(s)["bins_used"], 2 * 144)


class TestPredict(unittest.TestCase):
    def test_inside_and_outside(self):
        p = op.fit(series(2, daily(40, 46), lambda T, d: 10 + 0.08 * (T - 43)))
        f, note = op.predict(p, 43.0, T_START + 86400)
        self.assertAlmostEqual(f, 10.0, delta=0.01)
        self.assertIsNone(note)
        f, note = op.predict(p, 60.0, T_START + 86400)
        self.assertIn("extrapolated", note)
        self.assertEqual(op.predict({"status": "insufficient"}, 40, T_START), (None, "no fitted profile"))


class TestLogIntegration(unittest.TestCase):
    """The log keeps every PPS-throughout bin from the whole file for the fit, beyond the 7-day RAM window."""

    def test_profile_over_the_whole_file(self):
        import os
        import tempfile
        from gps_time_pi import oscillator as osc
        tmp = tempfile.mkdtemp(prefix="gtp-osc-")
        path = os.path.join(tmp, "oscillator-log.csv")
        ident = {"serial_sha256": "abc", "model": "test board"}
        log = osc.Log(path=path, clock=lambda: T_START, temp_reader=lambda: None, identity=ident)
        rows = series(10, daily(40, 52), lambda T, d: 10 + 0.07 * (T - 46))
        with open(path, "w", encoding="ascii") as f:
            f.write(log._header())
            for i, (t, T, fr) in enumerate(rows):
                pps = 10 if i % 50 else 7               # some bins without PPS throughout: never fitted
                b = {"t": t, "samples": 10, "pps_samples": pps, "temp_mean_c": T, "temp_min_c": T, "temp_max_c": T,
                     "freq_mean_ppm": fr, "freq_min_ppm": fr, "freq_max_ppm": fr, "skew_mean_ppm": 0.01, "residual_mean_ppm": 0.0}
                f.write(osc.Log._row(b))
        log = osc.Log(path=path, clock=lambda: T_START + 10 * 86400, temp_reader=lambda: 45.0, identity=ident)
        rep = log.report()
        self.assertEqual(len(rep["bins"]), osc.RAM_BINS)              # RAM: the last 7 days
        p = rep["profile"]
        self.assertEqual(p["status"], "fitted")
        self.assertEqual(p["bins_used"], len(rows) - len(range(0, len(rows), 50)))
        self.assertGreater(p["covers"]["days"], 9.9)                    # the fit: the whole file
        self.assertAlmostEqual(term(p, "b")["value"], 0.07, delta=0.002)
        self.assertIn("not a holdover guarantee", p["note"])
        self.assertTrue(p["covers"]["first_utc"].startswith("2026"))
        # the fit is cached until a bin is added
        self.assertIs(log.profile(), log.profile())

    def test_demo_payload_has_a_profile(self):
        from gps_time_pi import demo
        p = demo.oscillator()["profile"]
        self.assertEqual(p["status"], "fitted")
        self.assertEqual(p["provenance"], "modeled")


if __name__ == "__main__":
    unittest.main()
