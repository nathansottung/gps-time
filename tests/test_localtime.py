"""Local-time display zone: override, offline lookup from the position, and the
privacy rule (hidden mode never derives the zone from the position).

The lookup library is replaced by a recorder, so these run without tzfpy.
"""

import os
import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import config, localtime, server
from tests.test_admin_auth import AuthBase

ROOT = Path(__file__).resolve().parents[1]
SITE = {"lat": 38.9217, "lon": -77.0669, "alt_msl": 92.0}          # US Naval Observatory example
KNOWN = {"America/New_York", "Europe/Paris", "UTC", "Etc/GMT+3"}


class ZoneBase(unittest.TestCase):
    def setUp(self):
        self.lookups = []

        def fake_get_tz(lon, lat):
            self.lookups.append((lat, lon))
            return "America/New_York"

        localtime._lookup.cache_clear()
        self.addCleanup(localtime._lookup.cache_clear)
        for p in (mock.patch.object(localtime, "_get_tz", fake_get_tz),
                  mock.patch.dict(localtime.LOOKUP, {"available": True, "reason": None}),
                  mock.patch.object(localtime, "available_timezones", lambda: set(KNOWN))):
            p.start()
            self.addCleanup(p.stop)


class TestDisplayZone(ZoneBase):
    def test_exact_mode_uses_the_position(self):
        z = localtime.display_zone({"location_display": "exact"}, SITE)
        self.assertEqual((z["tz"], z["source"], z["provenance"], z["basis"]),
                         ("America/New_York", "position", "calculated", "exact"))
        self.assertEqual(self.lookups, [(38.922, -77.067)])     # (lat, lon); tzfpy is called (lon, lat)

    def test_rounded_mode_looks_up_only_the_rounded_position(self):
        z = localtime.display_zone({"location_display": "rounded"}, SITE)
        self.assertEqual((z["tz"], z["source"], z["basis"]), ("America/New_York", "position", "rounded"))
        self.assertEqual(self.lookups, [(38.9, -77.1)])

    def test_hidden_mode_never_derives_the_zone_from_the_position(self):
        z = localtime.display_zone({"location_display": "hidden"}, SITE)
        self.assertEqual((z["tz"], z["source"], z["provenance"]), (None, None, None))
        self.assertIn("hidden", z["note"])
        self.assertEqual(self.lookups, [], "no lookup may run in hidden mode")

    def test_override_wins_in_every_mode_without_a_lookup(self):
        for mode in ("exact", "rounded", "hidden"):
            with self.subTest(mode=mode):
                z = localtime.display_zone({"location_display": mode, "timezone": "Europe/Paris"}, SITE)
                self.assertEqual((z["tz"], z["source"], z["provenance"]), ("Europe/Paris", "override", None))
        self.assertEqual(self.lookups, [])

    def test_unknown_override_is_ignored(self):
        z = localtime.display_zone({"location_display": "exact", "timezone": "Mars/Olympus_Mons"}, SITE)
        self.assertEqual((z["tz"], z["source"]), ("America/New_York", "position"))

    def test_no_position_yet(self):
        z = localtime.display_zone({"location_display": "exact"}, None)
        self.assertEqual((z["tz"], z["source"]), (None, None))
        self.assertEqual(z["note"], "no position yet")

    def test_library_missing_means_no_zone_not_an_error(self):
        with mock.patch.dict(localtime.LOOKUP, {"available": False, "reason": "tzfpy not available"}), \
             mock.patch.object(localtime, "_get_tz", None):
            z = localtime.display_zone({"location_display": "exact"}, SITE)
        self.assertEqual((z["tz"], z["source"], z["note"]), (None, None, "tzfpy not available"))

    def test_lookup_error_or_unknown_name_means_no_zone(self):
        def boom(lon, lat):
            raise RuntimeError("corrupt data")
        with mock.patch.object(localtime, "_get_tz", boom):
            self.assertIsNone(localtime.zone_from_position(1.0, 2.0))
        with mock.patch.object(localtime, "_get_tz", lambda lon, lat: "Not/AZone"):
            self.assertIsNone(localtime.zone_from_position(3.0, 4.0))

    def test_lookup_is_cached_for_a_jittering_fix(self):
        for dlat in (0.00001, 0.00002, -0.00003):
            localtime.zone_from_position(SITE["lat"] + dlat, SITE["lon"])
        self.assertEqual(len(self.lookups), 1)


class TestValidZone(unittest.TestCase):
    def test_names(self):
        with mock.patch.object(localtime, "available_timezones", lambda: set(KNOWN)):
            self.assertTrue(localtime.valid_zone("America/New_York"))
            self.assertTrue(localtime.valid_zone("Etc/GMT+3"))
            for bad in ("", None, 5, "Mars/Olympus_Mons", "../etc/passwd", "America/New York", "a" * 200,
                        "America/New_York\n"):
                self.assertFalse(localtime.valid_zone(bad), repr(bad))

    def test_without_a_zone_database_only_syntax_is_checked(self):
        with mock.patch.object(localtime, "available_timezones", lambda: set()):
            self.assertTrue(localtime.valid_zone("America/New_York"))
            self.assertFalse(localtime.valid_zone("../etc/passwd"))


class TestApi(ZoneBase, AuthBase):
    demo = True      # /api in demo mode needs no GNSS or chrony; the zone logic is the same

    def setUp(self):
        ZoneBase.setUp(self)
        AuthBase.setUp(self)

    def tz(self):
        status, _, body = self.req("GET", "/api")
        self.assertEqual(status, 200)
        return body["timezone"]

    def test_api_reports_the_zone_from_the_position(self):
        self.assertEqual((self.tz()["tz"], self.tz()["source"]), ("America/New_York", "position"))

    def test_hidden_mode_api_has_no_position_derived_zone(self):
        cfg = config.load()
        cfg["location_display"] = "hidden"
        config.save(cfg)
        z = self.tz()
        self.assertEqual((z["tz"], z["source"]), (None, None))
        self.assertEqual(self.lookups, [])

    def test_set_and_clear_the_override(self):
        status, _, body = self.post("/api/setting", {"timezone": "Europe/Paris"})
        self.assertEqual((status, body), (200, {"ok": True, "timezone": "Europe/Paris"}))
        self.assertEqual(config.load()["timezone"], "Europe/Paris")
        self.assertEqual((self.tz()["tz"], self.tz()["source"]), ("Europe/Paris", "override"))
        for clear in (None, ""):
            status, _, body = self.post("/api/setting", {"timezone": clear})
            self.assertEqual((status, body), (200, {"ok": True, "timezone": None}))
        self.assertEqual(self.tz()["source"], "position")

    def test_unknown_zone_is_refused_and_nothing_changes(self):
        status, _, body = self.post("/api/setting", {"timezone": "Mars/Olympus_Mons"})
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])
        self.assertIsNone(config.load().get("timezone"))


class TestOverrideNeedsTheToken(AuthBase):
    def test_no_token_no_change(self):
        status, _, _ = self.post("/api/setting", {"timezone": "Europe/Paris"}, token=None)
        self.assertEqual(status, 401)
        self.assertIsNone(config.load().get("timezone"))


class TestDisplayOnly(unittest.TestCase):
    def test_nothing_sets_the_system_time_zone(self):
        for path in list((ROOT / "gps_time_pi").glob("*.py")) + [ROOT / "install.sh"] + list((ROOT / "scripts").glob("*")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for forbidden in ("timedatectl", "/etc/localtime", "/etc/timezone", "tzset", 'environ["TZ"]', "TZ="):
                self.assertNotIn(forbidden, text, f"{path.name}: {forbidden}")

    def test_lookup_library_is_pinned(self):
        req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertRegex(req, r"(?m)^tzfpy==\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
