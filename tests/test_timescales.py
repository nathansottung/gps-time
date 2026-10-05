"""Time scales panel (SPEC-TIMING-METROLOGY section 3): TAI, GPS time, MJD/JD,
the leap-second table and UT1-UTC from a cached file. Fixtures only: no
Internet, no chrony, no system tzdata.
"""

import calendar
import inspect
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import labels, timescales as ts

FIX = Path(__file__).parent / "fixtures" / "timescales"
LEAP = str(FIX / "leap-seconds.list")              # updated 2026-06-21, expires 2026-12-28
LEAP_FUTURE = str(FIX / "leap-seconds-future.list")  # plus an invented leap second on 2027-01-01
IERS = str(FIX / "finals2000A.sample")             # MJD 61316..61320


def utc(*ymdhms):
    return float(calendar.timegm(ymdhms))


NOW = utc(2026, 10, 5, 2, 23, 20)                  # MJD 61318.0995...


class TestScales(unittest.TestCase):
    def setUp(self):
        self.table = ts.load_leap_table([LEAP])

    def test_offsets_today(self):
        s = ts.scales(self.table, NOW)
        self.assertEqual(s["tai_utc_s"]["value"], 37)
        self.assertEqual(s["gps_utc_s"]["value"], 18)
        self.assertEqual(s["tai"]["value"], "2026-10-05 02:23:57")
        self.assertEqual(s["gps"]["time"]["value"], "2026-10-05 02:23:38")
        self.assertEqual(s["utc"], "2026-10-05T02:23:20+00:00")
        self.assertEqual(s["unix_s"], 1791167000)

    def test_gps_week_and_seconds_of_week(self):
        # GPS weeks start on Sunday; 2026-10-05 is a Monday.
        s = ts.scales(self.table, NOW)
        self.assertEqual(s["gps"]["week"]["value"], 2439)
        self.assertEqual(s["gps"]["week_mod_1024"]["value"], 2439 % 1024)
        self.assertEqual(s["gps"]["seconds_of_week"]["value"], 86400 + 2 * 3600 + 23 * 60 + 38)

    def test_known_gps_epochs(self):
        # The first week rollover: GPS week 1024 began 1999-08-22 00:00:00 GPS, 13 s ahead of UTC.
        s = ts.scales(self.table, utc(1999, 8, 21, 23, 59, 47))
        self.assertEqual(s["gps_utc_s"]["value"], 13)
        self.assertEqual((s["gps"]["week"]["value"], s["gps"]["seconds_of_week"]["value"]), (1024, 0))
        self.assertEqual(s["gps"]["week_mod_1024"]["value"], 0)
        # GPS time started equal to UTC.
        s0 = ts.scales(self.table, utc(1980, 1, 6, 0, 0, 0))
        self.assertEqual(s0["gps_utc_s"]["value"], 0)
        self.assertEqual((s0["gps"]["week"]["value"], s0["gps"]["seconds_of_week"]["value"]), (0, 0))

    def test_julian_dates(self):
        # J2000.0 is JD 2451545.0 = MJD 51544.5 (2000-01-01 12:00).
        s = ts.scales(self.table, utc(2000, 1, 1, 12, 0, 0))
        self.assertEqual(s["mjd"]["value"], 51544.5)
        self.assertEqual(s["jd"]["value"], 2451545.0)
        self.assertEqual(ts.scales(self.table, utc(1858, 11, 17, 0, 0, 0))["mjd"]["value"], 0.0)
        self.assertAlmostEqual(ts.scales(self.table, NOW)["mjd"]["value"], 61318.099537, places=6)

    def test_offset_steps_at_a_leap_second(self):
        self.assertEqual(ts.tai_minus_utc(self.table, utc(2016, 12, 31, 23, 59, 59)), 36)
        self.assertEqual(ts.tai_minus_utc(self.table, utc(2017, 1, 1, 0, 0, 0)), 37)
        self.assertIsNone(ts.tai_minus_utc(self.table, utc(1971, 1, 1, 0, 0, 0)))

    def test_before_the_table_is_unknown_not_zero(self):
        s = ts.scales(self.table, utc(1970, 6, 1, 0, 0, 0))
        self.assertIsNone(s["tai_utc_s"]["value"])
        self.assertIsNone(s["tai"])
        self.assertIsNone(s["gps"])

    def test_every_value_is_labeled_calculated(self):
        s = ts.scales(self.table, NOW)
        for v in (s["tai_utc_s"], s["gps_utc_s"], s["tai"], s["mjd"], s["jd"], *s["gps"].values()):
            self.assertEqual(v["provenance"], "calculated")
            self.assertIn(v["provenance"], labels.PROVENANCE)


class TestLeapTable(unittest.TestCase):
    def test_file_is_parsed(self):
        t = ts.load_leap_table([LEAP])
        self.assertEqual(t["source"], "file")
        self.assertEqual(len(t["entries"]), 28)
        self.assertEqual(t["entries"][0], (utc(1972, 1, 1, 0, 0, 0), 10))
        self.assertEqual(t["entries"][-1], (utc(2017, 1, 1, 0, 0, 0), 37))
        self.assertEqual(t["expires"], utc(2026, 12, 28, 0, 0, 0))

    def test_builtin_list_matches_the_file(self):
        self.assertEqual(ts._builtin_entries(), ts.load_leap_table([LEAP])["entries"])

    def test_missing_file_falls_back_and_says_so(self):
        t = ts.load_leap_table([os.path.join(_env.TMP, "nope.list")])
        self.assertEqual(t["source"], "builtin")
        self.assertEqual(len(t["problems"]), 1)
        st = ts.leap_status(t, NOW)
        self.assertEqual(st["status"], "UNKNOWN")
        self.assertIsNone(st["expires_utc"])
        self.assertIn("built-in list", st["warning"])
        self.assertTrue(st["next_note"].startswith("UNKNOWN"))

    def test_unreadable_content_falls_back(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        bad = os.path.join(d, "leap-seconds.list")
        Path(bad).write_text("# nothing here\n", encoding="utf-8")
        self.assertEqual(ts.load_leap_table([bad])["source"], "builtin")

    def test_first_readable_file_wins(self):
        t = ts.load_leap_table([os.path.join(_env.TMP, "nope.list"), LEAP])
        self.assertEqual((t["source"], t["path"]), ("file", LEAP))


class TestLeapStatus(unittest.TestCase):
    def status(self, now, path=LEAP, **kw):
        return ts.leap_status(ts.load_leap_table([path]), now, **kw)

    def test_valid(self):
        st = self.status(NOW)
        self.assertEqual(st["status"], "OK")
        self.assertIsNone(st["warning"])
        self.assertEqual(st["provenance"], "external")
        self.assertEqual(st["expires_utc"], "2026-12-28T00:00:00+00:00")
        self.assertEqual(st["updated_utc"][:10], "2026-06-21")
        self.assertEqual(st["days_to_expiry"], 83.9)
        self.assertEqual(st["last"], {"utc": "2017-01-01T00:00:00+00:00", "tai_utc_s": 37})
        self.assertIsNone(st["next"])
        self.assertIn("None scheduled", st["next_note"])
        self.assertIn("2026-12-28", st["next_note"])

    def test_warns_well_before_expiry(self):
        st = self.status(utc(2026, 11, 15, 0, 0, 0))     # 43 days left, threshold 60
        self.assertEqual(st["status"], "EXPIRES_SOON")
        self.assertIn("expires in 43 days", st["warning"])
        self.assertEqual(self.status(utc(2026, 10, 28, 0, 0, 0))["status"], "OK")   # 61 days left

    def test_threshold_is_configurable(self):
        self.assertEqual(self.status(NOW, warn_days=120)["status"], "EXPIRES_SOON")

    def test_expired(self):
        st = self.status(utc(2027, 2, 1, 0, 0, 0))
        self.assertEqual(st["status"], "EXPIRED")
        self.assertIn("expired on 2026-12-28", st["warning"])
        self.assertTrue(st["next_note"].startswith("UNKNOWN"))

    def test_next_scheduled_leap_second(self):
        st = self.status(NOW, LEAP_FUTURE)
        self.assertEqual(st["next"], {"utc": "2027-01-01T00:00:00+00:00", "tai_utc_s": 38, "kind": "insert",
                                      "last_second_utc": "2026-12-31T23:59:59+00:00"})
        self.assertIsNone(st["next_note"])
        after = self.status(utc(2027, 1, 1, 0, 0, 0), LEAP_FUTURE)
        self.assertIsNone(after["next"])
        self.assertEqual(after["last"]["tai_utc_s"], 38)

    def test_chrony_leap_status_is_reported_as_observed(self):
        st = self.status(NOW, chrony_leap="Insert second")
        self.assertEqual(st["chrony_leap_status"]["value"], "Insert second")
        self.assertEqual(st["chrony_leap_status"]["provenance"], "observed")
        self.assertIsNone(self.status(NOW)["chrony_leap_status"]["value"])


class TestUt1(unittest.TestCase):
    def test_no_file_is_not_shown(self):
        u = ts.ut1(NOW, path=os.path.join(_env.TMP, "no-iers"))
        self.assertFalse(u["available"])
        self.assertIsNone(u["ut1_utc_s"])
        self.assertIn("does not fetch", u["reason"])

    def test_cached_file_is_external_with_its_date(self):
        u = ts.ut1(NOW, path=IERS)
        self.assertTrue(u["available"])
        self.assertEqual(u["provenance"], "external")
        self.assertIsNotNone(u["file_date_utc"])
        # MJD 61318.0995: between 0.0704 (61318) and 0.0700 (61319)
        self.assertAlmostEqual(u["ut1_utc_s"], 0.0704 - 0.0004 * 0.0995370, places=6)
        self.assertEqual(u["kind"], "predicted by IERS")      # the later row is a prediction

    def test_determined_rows_are_labeled_as_such(self):
        self.assertEqual(ts.ut1(utc(2026, 10, 4, 6, 0, 0), path=IERS)["kind"], "IERS determination")

    def test_file_that_does_not_cover_today_is_not_used(self):
        u = ts.ut1(utc(2027, 3, 1, 0, 0, 0), path=IERS)
        self.assertFalse(u["available"])
        self.assertIn("does not cover today", u["reason"])
        self.assertIsNotNone(u["file_date_utc"])

    def test_garbage_file(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        p = os.path.join(d, "finals")
        Path(p).write_text("not an IERS file\n" * 3, encoding="ascii")
        self.assertFalse(ts.ut1(NOW, path=p)["available"])


class TestReportAndRoute(unittest.TestCase):
    def test_report_shape(self):
        r = ts.report(NOW, chrony_leap="Normal", leap_paths=[LEAP], iers_path=IERS)
        self.assertEqual(r["provenance"], "calculated")
        self.assertEqual(r["leap_seconds"]["status"], "OK")
        self.assertTrue(r["ut1"]["available"])
        json.dumps(r)

    def test_route_in_demo_mode(self):
        from gps_time_pi import server
        with mock.patch.object(server, "DEMO_MODE", True):
            r = server.timescales_payload()
        self.assertEqual(r["tai_utc_s"]["value"], 37)
        self.assertEqual(r["leap_seconds"]["status"], "OK")
        self.assertFalse(r["ut1"]["available"])
        json.dumps(r)

    def test_route_reads_chrony_leap_status_from_the_timing_chain(self):
        from gps_time_pi import server, timing_chain
        fake = mock.Mock()
        fake.latest.return_value = {"raw": {"tracking": "Reference ID    : 47505300 (GPS)\nLeap status     : Insert second\n"}}
        with mock.patch.object(server, "DEMO_MODE", False), mock.patch.object(timing_chain, "service", lambda: fake), \
                mock.patch.object(ts, "LEAP_FILES", [LEAP]):
            r = server.timescales_payload()
        self.assertEqual(r["leap_seconds"]["chrony_leap_status"]["value"], "Insert second")
        self.assertEqual(r["leap_seconds"]["source"], "file")

    def test_module_never_uses_the_network_or_sets_the_clock(self):
        src = inspect.getsource(ts)
        for word in ("urllib", "socket", "requests", "subprocess", "settimeofday", "clock_settime", "timedatectl"):
            self.assertNotIn(word, src)
        self.assertFalse(re.search(r"open\([^,)]*,\s*['\"][wax+]", src), "the module must not open a file for writing")


if __name__ == "__main__":
    unittest.main()
