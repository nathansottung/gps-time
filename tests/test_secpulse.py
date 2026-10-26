"""Second pulse (gps_time_pi/secpulse.py) and the comparison tool (tools/pps_compare.py).

No GPIO, root or Pi: the pulse loop runs on a manual clock with a fake line; the
uAPI structures are checked against linux/gpio.h sizes and ioctl numbers; the
tool runs on synthetic fixtures in tests/fixtures/validation/ (not measurements).
"""

import contextlib
import ctypes
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import secpulse

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "validation"
sys.path.insert(0, str(ROOT / "tools"))
import pps_compare  # noqa: E402

S = 1_000_000_000


class ManualClock:
    """Each read advances by `step` ns; sleep_until jumps to the target plus `wake_late`."""

    def __init__(self, t, step=200, wake_late=50_000):
        self.t, self.step, self.wake_late = t, step, wake_late

    def __call__(self):
        self.t += self.step
        return self.t

    def sleep_until(self, target):
        if target > self.t:
            self.t = target + self.wake_late


class FakeLine:
    def __init__(self, clock):
        self.clock, self.sets = clock, []

    def set(self, v):
        self.clock.t += 1500           # the write takes 1.5 us
        self.sets.append((self.clock.t, v))


class TestUapi(unittest.TestCase):
    def test_struct_sizes_and_ioctl_numbers_match_linux_gpio_h(self):
        self.assertEqual(ctypes.sizeof(secpulse._LineRequest), 592)
        self.assertEqual(ctypes.sizeof(secpulse._LineValues), 16)
        self.assertEqual(ctypes.sizeof(secpulse._LineConfig), 272)
        self.assertEqual(secpulse.GPIO_V2_GET_LINE_IOCTL, 0xC250B407)
        self.assertEqual(secpulse.GPIO_V2_LINE_SET_VALUES_IOCTL, 0xC010B40F)
        self.assertEqual(secpulse._LineRequest.fd.offset, 588)


class TestPulser(unittest.TestCase):
    def make(self, t0=1_793_030_400 * S + 300_000_000, **kw):
        clock = ManualClock(t0, **kw)
        line = FakeLine(clock)
        return secpulse.Pulser(line, width_ms=100, lead_us=500, clock=clock, sleep_until=clock.sleep_until), line, clock

    def test_rising_edge_written_just_after_each_second(self):
        p, line, _ = self.make()
        recs = [p.one() for _ in range(5)]
        self.assertEqual([r[0] for r in recs], list(range(1_793_030_401, 1_793_030_406)))
        for (sec, before, after) in recs:
            self.assertGreaterEqual(before, 0)                  # never before the boundary
            self.assertLess(before, 1_000)                      # spun up to it, not woken late
            self.assertGreater(after, before)
        rises = [t for t, v in line.sets if v == 1]
        falls = [t for t, v in line.sets if v == 0]
        for r, f in zip(rises, falls):
            self.assertAlmostEqual((f - r) / 1e6, 100, delta=0.2)   # 100 ms wide
            self.assertLess(r % S, 5_000)                       # edge within 5 us of the second

    def test_a_late_wake_up_skips_that_second(self):
        p, line, clock = self.make(wake_late=int(0.6 * S))
        self.assertIsNone(p.one())
        self.assertEqual((p.skipped, line.sets), (1, []))

    def test_summary(self):
        p, _, _ = self.make()
        for _ in range(10):
            p.one()
        s = p.summary()
        self.assertEqual((s["pulses"], s["skipped"]), (10, 0))
        self.assertGreater(s["write_done_after_ns"]["max"], 0)
        self.assertEqual(secpulse.Pulser(FakeLine(ManualClock(0)), clock=ManualClock(0),
                                         sleep_until=lambda t: None).summary(), {"pulses": 0, "skipped": 0})

    def test_log_lines(self):
        out = io.StringIO()
        p, _, _ = self.make()
        p.out = out
        p.one()
        sec, before, after = out.getvalue().strip().split(",")
        self.assertEqual(sec, "1793030401")
        self.assertLess(int(before), int(after))

    def test_width_bounds(self):
        with self.assertRaises(ValueError):
            secpulse.Pulser(None, width_ms=950, sleep_until=lambda t: None)


class TestPpsLineGuard(unittest.TestCase):
    def test_refuses_the_pps_input(self):
        boot = {"gpio": 18, "assert_edge": "rising", "source": "/boot/firmware/config.txt"}
        self.assertIn("PPS input", secpulse.refuse_pps_line(18, boot))
        self.assertIsNone(secpulse.refuse_pps_line(23, boot))
        self.assertIsNone(secpulse.refuse_pps_line(18, {"gpio": None, "source": "x"}))

    def test_main_refuses_before_touching_gpio(self):
        with mock.patch.object(secpulse.pps, "boot_pps_config", return_value={"gpio": 18, "source": "c"}), \
             mock.patch.object(secpulse, "GpioLine") as gl, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(secpulse.main(["--line", "18"]), 2)
        gl.assert_not_called()

    def test_never_touches_timing_config(self):
        src = (ROOT / "gps_time_pi" / "secpulse.py").read_text(encoding="utf-8")
        for word in ("chrony.conf", "gpsd", "/dev/pps", "systemctl", "config.save"):
            self.assertNotIn(word, src.split('"""', 2)[2], word)


class TestCompare(unittest.TestCase):
    def run_tool(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = pps_compare.main([str(a) for a in args])
        return code, out.getvalue()

    def test_counter_export(self):
        raw, meta = pps_compare.read_intervals((FIX / "counter_ti.csv").read_text(encoding="utf-8"))
        self.assertEqual(meta["column"], "Time Interval 1 to 2")
        self.assertEqual(meta["rows"], 180)
        r = pps_compare.analyze(raw)
        self.assertEqual((r["samples"]["pairing_errors"], r["samples"]["outliers"]), (2, 1))
        self.assertAlmostEqual(r["x"]["mean"]["value"], 2.0e-6, delta=20e-9)
        self.assertAlmostEqual(r["x"]["sd"]["value"], 50e-9, delta=10e-9)
        self.assertEqual(r["x"]["mean"]["provenance"], "calculated")
        self.assertEqual(r["clock"]["bound"]["provenance"], "calculated")
        self.assertIsNone(r["clock"]["offset"])               # no pulse log: no point estimate

    def test_scope_export_units_and_sign(self):
        raw, meta = pps_compare.read_intervals((FIX / "scope_delay.csv").read_text(encoding="utf-8"))
        self.assertEqual(meta["column"], "Delay(C1-C2) (us)")
        self.assertIn("header", meta["unit"])
        r = pps_compare.analyze(raw, sign=-1.0)
        self.assertAlmostEqual(r["x"]["mean"]["value"], 2.0e-6, delta=20e-9)

    def test_several_numeric_columns_need_a_choice_unless_one_is_named(self):
        text = "a,b\n1,2\n3,4\n"
        with self.assertRaises(ValueError):
            pps_compare.read_intervals(text)
        self.assertEqual(pps_compare.read_intervals(text, column="b")[0], [2.0, 4.0])
        self.assertEqual(pps_compare.read_intervals(text, column="1")[0], [1.0, 3.0])

    def test_unit_suffixes(self):
        vals, meta = pps_compare.read_intervals("850ns\n1.2us\n0.0000011 s\n")
        self.assertEqual([round(v * 1e9, 3) for v in vals], [850.0, 1200.0, 1100.0])
        self.assertIn("suffix", meta["unit"])

    def test_delays(self):
        r = pps_compare.analyze([1e-6] * 10, delay_gpio_s=30e-9, delay_pps_s=10e-9)
        self.assertAlmostEqual(r["x"]["mean"]["value"], 0.98e-6, places=15)
        self.assertIsNone(r["corrections"]["note"])

    def test_pulse_log_gives_a_modeled_offset(self):
        raw, _ = pps_compare.read_intervals((FIX / "counter_ti.csv").read_text(encoding="utf-8"))
        log = pps_compare.read_pulse_log((FIX / "secpulse_log.csv").read_text(encoding="utf-8"))
        r = pps_compare.analyze(raw, pulse_log=log)
        off = r["clock"]["offset"]
        self.assertEqual(off["provenance"], "modeled")
        # write window midpoint ~2 us after the boundary, x ~2 us: the clock is within ~0.1 us of PPS
        self.assertLess(abs(off["value"]), 100e-9)

    def test_white_noise_adev_falls_as_one_over_tau(self):
        r = pps_compare.analyze(pps_compare.read_intervals((FIX / "counter_ti.csv").read_text(encoding="utf-8"))[0])
        a = {d["tau_s"]: d["adev"] for d in r["stability"]}
        self.assertAlmostEqual(a[1] / a[10], 10, delta=3)

    def test_nothing_usable(self):
        with self.assertRaises(ValueError):
            pps_compare.analyze([None, 1.0, -0.9])

    def test_cli_text_and_json(self):
        code, out = self.run_tool(FIX / "counter_ti.csv")
        self.assertEqual(code, 0)
        self.assertIn("not behind PPS by more than", out)
        self.assertIn("says nothing about PPS against UTC", out)
        code, out = self.run_tool(FIX / "counter_ti.csv", "--json", "--pulse-log", FIX / "secpulse_log.csv")
        doc = json.loads(out)
        self.assertEqual(doc["clock"]["offset"]["provenance"], "modeled")
        code, _ = self.run_tool(FIX / "missing.csv")
        self.assertEqual(code, 2)

    def test_fixtures_are_marked_synthetic(self):
        self.assertIn("Synthetic", (FIX / "counter_ti.csv").read_text(encoding="utf-8").splitlines()[0])


if __name__ == "__main__":
    unittest.main()
