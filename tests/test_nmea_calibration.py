"""NMEA refclock offset: a measured recommendation, never an automatic change."""

import tempfile
import unittest
from pathlib import Path

from tests import _env  # noqa: F401
from gps_time_pi import chrony, labels, timing_chain as tc

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures" / "chrony"
NMEA_CFG = {"driver": "SHM", "param": "0", "refid": "NMEA", "offset_s": 0.1}
STATS = {"samples": 32, "runs": 17, "span_s": 480, "offset_s": 0.035, "std_dev_s": 0.001271}


def val(x):
    return x["value"]


class TestRecommendation(unittest.TestCase):
    def test_suggests_configured_plus_residual_while_pps_is_selected(self):
        c = tc.nmea_calibration(NMEA_CFG, STATS, pps_selected=True)
        self.assertTrue(c["available"])
        self.assertEqual(val(c["configured_offset_s"]), 0.1)
        self.assertEqual(val(c["residual_s"]), 0.035)
        self.assertEqual(val(c["suggested_offset_s"]), 0.135)
        self.assertTrue(c["change_worthwhile"])
        self.assertIn("`offset 0.1` to `offset 0.135`", c["advice"])
        self.assertIn("use `offset 0.065`", c["advice"], "the advice says how to recover if the sign is reversed")

    def test_negative_residual_lowers_the_offset(self):
        c = tc.nmea_calibration(NMEA_CFG, {**STATS, "offset_s": -0.042}, pps_selected=True)
        self.assertEqual(val(c["suggested_offset_s"]), 0.058)

    def test_absent_offset_option_counts_as_zero(self):
        c = tc.nmea_calibration({**NMEA_CFG, "offset_s": 0.0}, STATS, pps_selected=True)
        self.assertEqual(val(c["suggested_offset_s"]), 0.035)

    def test_small_or_noisy_residual_needs_no_change(self):
        for stats in ({**STATS, "offset_s": 0.002}, {**STATS, "offset_s": 0.02, "std_dev_s": 0.01}):
            c = tc.nmea_calibration(NMEA_CFG, stats, pps_selected=True)
            self.assertTrue(c["available"])
            self.assertFalse(c["change_worthwhile"])
            self.assertIn("no change is needed", c["advice"])

    def test_labels(self):
        c = tc.nmea_calibration(NMEA_CFG, STATS, pps_selected=True)
        self.assertEqual(c["residual_s"]["provenance"], "observed")
        self.assertEqual(c["suggested_offset_s"]["provenance"], "calculated")
        for k in ("configured_offset_s", "residual_s", "std_dev_s", "samples", "span_s", "suggested_offset_s"):
            self.assertIn(c[k]["provenance"], labels.PROVENANCE)


class TestNotMeasurable(unittest.TestCase):
    def test_needs_pps_selected(self):
        c = tc.nmea_calibration(NMEA_CFG, STATS, pps_selected=False)
        self.assertFalse(c["available"])
        self.assertIn("PPS must be the selected source", c["reason"])
        self.assertNotIn("suggested_offset_s", c)

    def test_needs_enough_samples(self):
        c = tc.nmea_calibration(NMEA_CFG, {**STATS, "samples": 5}, pps_selected=True)
        self.assertFalse(c["available"])
        self.assertIn("too few", c["reason"])

    def test_needs_statistics_and_a_configured_refclock(self):
        self.assertIn("no statistics", tc.nmea_calibration(NMEA_CFG, None, True)["reason"])
        self.assertIn("no NMEA/serial refclock", tc.nmea_calibration(None, STATS, True)["reason"])
        self.assertIn("could not be read", tc.nmea_calibration({**NMEA_CFG, "offset_s": None}, STATS, True)["reason"])


class TestConfigAndChain(unittest.TestCase):
    def conf(self, text):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        p = Path(d.name) / "chrony.conf"
        p.write_text(text, encoding="utf-8")
        return chrony.refclock_config(str(p))

    def test_offset_is_read_from_chrony_conf(self):
        cfg = self.conf("refclock SHM 0 refid NMEA offset 0.1 delay 0.2 noselect\n"
                        "refclock PPS /dev/pps0 lock NMEA refid GPS prefer\n")
        self.assertEqual(cfg["nmea"]["offset_s"], 0.1)
        self.assertEqual(cfg["pps"]["offset_s"], 0.0)

    def test_project_example_snippet(self):
        cfg = chrony.refclock_config(str(ROOT / "examples" / "chrony.conf.snippet"))
        self.assertEqual(cfg["nmea"]["offset_s"], 0.1)

    def test_garbled_offset_is_unknown_not_zero(self):
        self.assertIsNone(self.conf("refclock SHM 0 refid NMEA offset banana noselect\n")["nmea"]["offset_s"])

    def test_chrony_view_carries_it_only_when_pps_is_selected(self):
        refcfg = {"pps": {"driver": "PPS", "param": "/dev/pps0", "refid": "GPS", "lock": "NMEA", "offset_s": 0.0},
                  "nmea": NMEA_CFG, "source": "chrony.conf"}

        def view(sources):
            return tc.chrony_view({"sources_ok": True, "sources_text": (FIX / f"{sources}.txt").read_text(),
                                   "tracking_ok": True, "tracking_text": (FIX / "tracking_pps.txt").read_text(),
                                   "sourcestats_ok": True, "sourcestats_text": (FIX / "sourcestats.txt").read_text()},
                                  refcfg)["nmea_calibration"]

        ok = view("sources_pps_selected")
        self.assertTrue(ok["available"])
        self.assertEqual(val(ok["suggested_offset_s"]), 0.135)
        self.assertFalse(view("sources_failover")["available"])


class TestReadOnly(unittest.TestCase):
    def test_nothing_writes_chrony_conf(self):
        for path in (ROOT / "gps_time_pi").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"open\([^)]*chrony[^)]*['\"][wa]", path.name)


if __name__ == "__main__":
    unittest.main()
