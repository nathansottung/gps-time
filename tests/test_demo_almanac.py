"""The desktop demo's synthetic almanac has the shapes astro.py returns, so the /app/
day and night bars and date navigation can be checked without an ephemeris."""
import unittest

from tests import _env  # noqa: F401
from gps_time_pi import demo


class DemoAlmanacTest(unittest.TestCase):
    def test_honors_the_requested_date(self):
        self.assertEqual(demo.almanac_api({"date": ["2026-11-01"]})["sun"]["date"], "2026-11-01")

    def test_bad_or_missing_date_falls_back_to_today(self):
        today = demo.almanac_api(None)["sun"]["date"]
        self.assertEqual(demo.almanac_api({"date": ["not-a-date"]})["sun"]["date"], today)

    def test_day_bar_covers_the_day(self):
        bar = demo.almanac_api({"date": ["2026-10-19"]})["sun"]["bar"]
        self.assertAlmostEqual(sum(s["frac"] for s in bar), 1.0, places=6)
        self.assertEqual({s["state"] for s in bar}, {0, 1, 2, 3, 4})

    def test_night_bar_shape(self):
        n = demo.almanac_api({"date": ["2026-10-19"]})["night"]
        self.assertTrue(n["defined"])
        for key in ("sunset", "sunrise", "span_s", "sun_segments", "moon_up", "dark", "dark_total_s", "midnight", "astro_note"):
            self.assertIn(key, n)
        for seg in n["sun_segments"] + n["moon_up"] + n["dark"]:
            self.assertLessEqual(0.0, seg["f0"])
            self.assertLessEqual(seg["f0"], seg["f1"])
            self.assertLessEqual(seg["f1"], 1.0)

    def test_marked_as_demo(self):
        self.assertTrue(demo.almanac_api(None)["demo"])

    def test_sky_marks_only_the_named_target(self):
        with_t = demo.almanac_api({"date": ["2026-10-19"], "at": ["22:00"], "target": ["M31"]})["sky"]
        without = demo.almanac_api({"date": ["2026-10-19"], "at": ["22:00"]})["sky"]
        self.assertIsNotNone(with_t["target"])
        self.assertIsNone(without["target"])
        self.assertTrue(with_t["stars"] and with_t["lines"])

    def test_object_transit_altitude_is_at_most_90(self):
        from datetime import date, datetime
        from gps_time_pi import catalog
        for q in ("M31", "Vega", "Polaris", "Jupiter"):
            r = demo.object_api(catalog.lookup(q), date(2026, 10, 19), datetime.now().astimezone())
            if r["transit_alt"] is not None:
                self.assertLessEqual(r["transit_alt"], 90.0, q)


if __name__ == "__main__":
    unittest.main()
