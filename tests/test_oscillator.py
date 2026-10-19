"""Temperature logged alongside chrony's frequency (input for the oscillator
profile, roadmap/ROADMAP-OSCILLATOR-AND-MISC.md §1). Fixtures and a manual
clock; no chrony, no hardware.
"""

import inspect
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import labels, oscillator as osc

T0 = 1_790_000_400.0           # on a 10-minute boundary
ID = {"serial_sha256": "a1b2c3d4e5f60718", "model": "Raspberry Pi 4 Model B Rev 1.2"}


def trk(ppm=10.345, fast=True, skew="0.008 ppm", resid="-0.000 ppm"):
    return {"Frequency": f"{ppm:.3f} ppm {'fast' if fast else 'slow'}", "Skew": skew, "Residual freq": resid}


class Rig:
    def __init__(self, test, identity=ID, max_bytes=None, path=None):
        self.dir = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.path = path or os.path.join(self.dir, "oscillator-log.csv")
        self.t = [T0]
        self.temp = [50.0]
        self.log = osc.Log(path=self.path, clock=lambda: self.t[0], temp_reader=lambda: self.temp[0],
                           identity=identity, max_bytes=max_bytes)

    def run(self, minutes, ppm=10.345, pps=True, temp=None, step=60.0):
        for _ in range(minutes):
            if temp is not None:
                self.temp[0] = temp(self.t[0])
            self.log.add(trk(ppm), pps)
            self.t[0] += step


class TestParsing(unittest.TestCase):
    def test_ppm(self):
        self.assertEqual(osc.parse_ppm("10.345 ppm fast"), 10.345)
        self.assertEqual(osc.parse_ppm("2.100 ppm slow"), -2.1)
        self.assertEqual(osc.parse_ppm("-0.000 ppm"), -0.0)
        self.assertEqual(osc.parse_ppm("0.008 ppm"), 0.008)
        self.assertIsNone(osc.parse_ppm(None))
        self.assertIsNone(osc.parse_ppm("n/a"))

    def test_temperature_sysfs(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        p = os.path.join(d, "temp")
        Path(p).write_text("53562\n", encoding="ascii")
        self.assertEqual(osc.read_temp_c(p), 53.56)
        self.assertIsNone(osc.read_temp_c(os.path.join(d, "missing")))

    def test_board_identity_is_hashed_never_raw(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        Path(d, "serial").write_bytes(b"100000001234abcd\0")
        Path(d, "model").write_bytes(b"Raspberry Pi 4 Model B Rev 1.2\0")
        i = osc.board_identity(os.path.join(d, "serial"), os.path.join(d, "model"))
        self.assertEqual(len(i["serial_sha256"]), 16)
        self.assertNotIn("1234abcd", json.dumps(i))
        self.assertEqual(i["model"], "Raspberry Pi 4 Model B Rev 1.2")
        self.assertIsNone(osc.board_identity(os.path.join(d, "x"), os.path.join(d, "y"))["serial_sha256"])


class TestBins(unittest.TestCase):
    def test_one_sample_a_minute_into_ten_minute_bins(self):
        r = Rig(self)
        for _ in range(25 * 60):                       # every second for 25 minutes
            r.log.add(trk(), True)
            r.t[0] += 1
        rep = r.log.report()
        self.assertEqual(len(rep["bins"]), 2, "two finished bins; the third is still open")
        self.assertEqual([b["samples"] for b in rep["bins"]], [10, 10])
        self.assertEqual(rep["bins"][0]["t"], "2026-09-21T14:20:00+00:00")
        self.assertAlmostEqual(rep["bins"][0]["freq_mean_ppm"], 10.345)
        self.assertAlmostEqual(rep["bins"][0]["temp_mean_c"], 50.0)

    def test_pps_selection_is_counted_per_bin(self):
        r = Rig(self)
        r.run(5, pps=True)
        r.run(5, pps=False)
        r.run(1)
        b = r.log.report()["bins"][0]
        self.assertEqual((b["samples"], b["pps_samples"]), (10, 5))

    def test_slow_frequency_is_negative(self):
        r = Rig(self)
        for _ in range(11):
            r.log.add(trk(2.5, fast=False), True)
            r.t[0] += 60
        self.assertAlmostEqual(r.log.report()["bins"][0]["freq_mean_ppm"], -2.5)

    def test_no_chrony_means_no_sample(self):
        r = Rig(self)
        for _ in range(30):
            r.log.add({}, False)
            r.t[0] += 60
        rep = r.log.report()
        self.assertFalse(rep["available"])
        self.assertIn("No 10-minute bin", rep["reason"])

    def test_missing_temperature_is_null_not_zero(self):
        r = Rig(self)
        r.temp[0] = None
        r.run(11)
        b = r.log.report()["bins"][0]
        self.assertIsNone(b["temp_mean_c"])
        self.assertAlmostEqual(b["freq_mean_ppm"], 10.345)


class TestStorage(unittest.TestCase):
    def test_nothing_written_until_the_hourly_flush(self):
        r = Rig(self)
        r.run(59)
        self.assertFalse(os.path.exists(r.path), "no write in the first hour")
        r.run(2)
        lines = Path(r.path).read_text(encoding="ascii").splitlines()
        self.assertTrue(lines[0].startswith("# gps-time oscillator log v1; board_sha256=a1b2c3d4e5f60718"))
        self.assertEqual(lines[1], ",".join(osc.COLUMNS))
        self.assertEqual(len(lines) - 2, 6)

    def test_writes_per_day(self):
        r = Rig(self)
        with mock.patch.object(osc.Log, "flush", wraps=r.log.flush) as f:
            r.run(24 * 60)
        self.assertLessEqual(f.call_count, 25, "about one write an hour, never per sample")

    def test_explicit_flush_on_stop_and_reload(self):
        r = Rig(self)
        r.run(35)
        self.assertEqual(r.log.flush(), 3)
        again = osc.Log(path=r.path, clock=lambda: r.t[0], temp_reader=lambda: 50.0, identity=ID)
        self.assertEqual(len(again.report()["bins"]), 3)
        self.assertEqual(again.report()["bins"][0]["samples"], 10)

    def test_size_cap_drops_the_oldest_quarter(self):
        r = Rig(self, max_bytes=3000)
        r.run(6 * 60)
        r.log.flush()
        size = os.path.getsize(r.path)
        self.assertLessEqual(size, 3000 + 600)
        lines = Path(r.path).read_text(encoding="ascii").splitlines()
        self.assertTrue(lines[0].startswith("# gps-time oscillator log v1"))
        self.assertEqual(lines[1], ",".join(osc.COLUMNS))
        newest = lines[-1].split(",")[0]
        self.assertEqual(newest, "2026-09-21T20:00:00+00:00")      # the 20:10 bin is still open
        self.assertFalse(os.path.exists(r.path + ".tmp"))

    def test_a_log_from_another_board_is_set_aside(self):
        r = Rig(self)
        r.run(61)
        other = osc.Log(path=r.path, clock=lambda: T0 + 9999, temp_reader=lambda: 50.0,
                        identity={"serial_sha256": "ffffffffffffffff", "model": "x"})
        self.assertEqual(other.report()["bins"], [])
        self.assertIsNotNone(other.set_aside)
        self.assertTrue(os.path.exists(other.set_aside))
        self.assertFalse(os.path.exists(r.path))
        self.assertIn("another board", other.report()["problems"][0])

    def test_unknown_serial_does_not_discard(self):
        r = Rig(self, identity={"serial_sha256": None, "model": None})
        r.run(61)
        again = osc.Log(path=r.path, clock=lambda: r.t[0], temp_reader=lambda: 50.0, identity=ID)
        self.assertEqual(len(again.report()["bins"]), 6)

    def test_a_failed_write_keeps_the_bins(self):
        r = Rig(self)
        os.makedirs(r.path)                     # the log path is a directory: every write fails
        r.log = osc.Log(path=r.path, clock=lambda: r.t[0], temp_reader=lambda: 50.0, identity=ID)
        r.run(61)
        rep = r.log.report()
        self.assertGreater(rep["storage"]["pending_bins"], 0)
        self.assertTrue(any("write failed" in p for p in rep["problems"]))


class TestFit(unittest.TestCase):
    def test_slope_from_pps_bins(self):
        r = Rig(self)
        warm = lambda t: 45.0 + ((t - T0) / 3600.0) % 10.0      # noqa: E731  45 to 55 °C, repeating
        for _ in range(12 * 60):
            r.temp[0] = warm(r.t[0])
            r.log.add(trk(abs(10.0 - 0.25 * (r.temp[0] - 50.0))), True)
            r.t[0] += 60
        fit = r.log.report()["fit"]
        self.assertEqual(fit["provenance"], "calculated")
        self.assertAlmostEqual(fit["slope_ppm_per_c"], -0.25, places=2)
        self.assertAlmostEqual(fit["r"], -1.0, places=2)
        self.assertGreaterEqual(fit["bins_used"], osc.FIT_MIN_BINS)

    def test_needs_enough_bins(self):
        r = Rig(self)
        r.run(60)
        fit = r.log.report()["fit"]
        self.assertIsNone(fit["slope_ppm_per_c"])
        self.assertIn("needs 36 bins", fit["reason"])

    def test_needs_a_temperature_span(self):
        r = Rig(self)
        r.run(7 * 60)
        fit = r.log.report()["fit"]
        self.assertIsNone(fit["slope_ppm_per_c"])
        self.assertIn("varied by only 0.0", fit["reason"])

    def test_bins_without_pps_throughout_are_not_used(self):
        r = Rig(self)
        r.run(7 * 60, pps=False, temp=lambda t: 45.0 + ((t - T0) / 3600.0) % 10.0)
        self.assertEqual(r.log.report()["fit"]["bins_used"], 0)


class TestReportAndRoute(unittest.TestCase):
    def test_labels_and_wording(self):
        r = Rig(self)
        r.run(11)
        rep = r.log.report()
        self.assertEqual(rep["provenance"], "observed")
        self.assertIn(rep["latest"]["temp_c"]["provenance"], labels.PROVENANCE)
        self.assertIn("not the crystal", rep["sensor"])
        self.assertIn("not the oscillator profile and not a holdover prediction", rep["fit_note"])
        self.assertEqual(rep["board"]["serial_sha256"], ID["serial_sha256"])
        json.dumps(rep)

    def test_chain_feeds_the_log_only_when_running(self):
        from tests.test_timing_chain import Rig as ChainRig
        rig = ChainRig()
        self.addCleanup(rig.cleanup)
        rig.pulses(3)
        self.assertIsNone(rig.svc._oscillator, "tests and standalone ticks create no log file")
        log = Rig(self).log
        rig.svc._oscillator = log
        rig.svc.tick(refresh_chrony=True)
        self.assertEqual(log._acc["n"], 1)
        self.assertEqual(log._acc["pps"], 1)

    def test_demo_route(self):
        from gps_time_pi import server
        with mock.patch.object(server, "DEMO_MODE", True):
            rep = server.oscillator_payload()
        self.assertTrue(rep["available"])
        self.assertAlmostEqual(rep["fit"]["slope_ppm_per_c"], -0.3, places=2)
        self.assertEqual(rep["problems"], ["sample data"])

    def test_module_never_touches_chrony(self):
        src = inspect.getsource(osc)
        for word in ("subprocess", "chronyc", "socket", "urllib"):
            self.assertFalse(word in src, word)


if __name__ == "__main__":
    unittest.main()
