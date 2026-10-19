"""chrony tracking.log parsed by named columns (review GPS-003) and chrony's conditional
error bound (review GPS-007). Fixture lines use the chrony 4.x layout from chrony.conf(5)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import chrony

FIX = Path(__file__).parent / "fixtures" / "chrony"
HDR = ("   Date (UTC) Time     IP Address   St   Freq ppm   Skew ppm     Offset L Co  Offset sd "
       "Rem. corr. Root delay Root disp. Max. error\n")
BAR = "=" * 117 + "\n"
# Row A: positive remaining correction. Row B: negative remaining correction (the review's probe P1).
ROW_A = "2026-10-19 12:00:00 PPS              1     10.295      0.009  1.741e-07 N  1  1.789e-07  2.500e-07  1.000e-09  7.005e-06  2.612e-05\n"
ROW_B = "2026-10-19 12:00:16 PPS              1     10.296      0.009 -3.100e-07 N  1  4.000e-06 -1.200e-07  1.000e-09  7.105e-06  2.701e-05\n"


class HistoryTest(unittest.TestCase):
    def history(self, text):
        d = tempfile.mkdtemp(prefix="gps-time-trk-")
        path = os.path.join(d, "tracking.log")
        Path(path).write_text(text, encoding="ascii")
        with mock.patch.object(chrony, "TRACKING_LOG", path), mock.patch.dict(os.environ, {"GTP_TRACKING_LOG": path}):
            return chrony.history()

    def test_every_column_by_name(self):
        p = self.history(HDR + BAR + ROW_A)["points"][0]
        self.assertEqual(p["offset_s"], 1.741e-07)
        self.assertEqual(p["offset_sd_s"], 1.789e-07)
        self.assertEqual(p["remaining_correction_s"], 2.5e-07)
        self.assertEqual(p["root_delay_s"], 1e-09)
        self.assertEqual(p["root_dispersion_s"], 7.005e-06)
        self.assertEqual(p["max_error_s"], 2.612e-05)
        self.assertEqual((p["freq_ppm"], p["skew_ppm"]), (10.295, 0.009))
        self.assertEqual((p["leap"], p["n_combined"], p["stratum"], p["source"]), ("N", 1, 1, "PPS"))

    def test_a_negative_remaining_correction_changes_nothing_else(self):
        p = self.history(HDR + ROW_B)["points"][0]
        self.assertEqual(p["remaining_correction_s"], -1.2e-07)
        self.assertEqual(p["offset_sd_s"], 4e-06)         # the offset SD stays the offset SD
        self.assertEqual(p["n_combined"], 1)              # and Co stays a count

    def test_no_combined_uncertainty_field(self):
        p = self.history(HDR + ROW_A)["points"][0]
        self.assertNotIn("err_s", p)

    def test_banners_repeat_and_are_skipped(self):
        h = self.history(HDR + BAR + ROW_A + HDR + BAR + ROW_B)
        self.assertEqual(len(h["points"]), 2)
        self.assertEqual(h["skipped_lines"], 0)
        self.assertIsNone(h["note"])

    def test_short_or_odd_lines_are_skipped_and_counted(self):
        short = "2026-10-19 12:00:32 PPS 1 10.2 0.009 1.0e-07 N 1 1.0e-07 1.0e-08 1.0e-09 7.0e-06\n"  # 13 fields
        odd = ROW_A.replace(" N  1 ", " X  1 ")                                                  # unknown leap code
        h = self.history(HDR + short + odd + ROW_B)
        self.assertEqual(len(h["points"]), 1)
        self.assertEqual(h["skipped_lines"], 2)
        self.assertIn("skipped", h["note"])

    def test_a_foreign_layout_is_not_guessed_at(self):
        other = "   Date (UTC) Time     IP Address   St   Freq ppm   Skew ppm     Offset L Co  Offset sd Rem. corr.\n"
        h = self.history(other + ROW_A + HDR + ROW_B)
        self.assertEqual([p["offset_s"] for p in h["points"]], [-3.1e-07])
        self.assertIn("other columns", h["note"])

    def test_missing_log(self):
        with mock.patch.object(chrony, "tracking_log_path", lambda: "/nonexistent/tracking.log"), \
                mock.patch.object(chrony, "_tracking_files", lambda p: [p]):
            h = chrony.history()
        self.assertFalse(h["available"])


class ErrorBoundTest(unittest.TestCase):
    def test_bound_is_offset_plus_dispersion_plus_half_delay(self):
        self.assertAlmostEqual(chrony.max_error_bound(-2e-7, 5e-6, 2e-3), 2e-7 + 5e-6 + 1e-3)

    def test_unknown_parts_give_no_bound(self):
        self.assertIsNone(chrony.max_error_bound(None, 5e-6, 2e-3))
        self.assertIsNone(chrony.max_error_bound(1e-7, None, 2e-3))
        self.assertIsNone(chrony.max_error_bound(1e-7, 5e-6, None))

    def test_quality_reports_it_from_chronyc_tracking(self):
        q = chrony.quality(chrony.parse_tracking((FIX / "tracking_network.txt").read_text()))
        expect = abs(q["system_time_s"]) + q["root_dispersion_s"] + q["root_delay_s"] / 2
        self.assertAlmostEqual(q["max_error_bound_s"], expect)
        self.assertGreater(q["max_error_bound_s"], q["root_dispersion_s"])   # root dispersion alone understated it


if __name__ == "__main__":
    unittest.main()
