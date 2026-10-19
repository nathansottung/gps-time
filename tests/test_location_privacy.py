"""Location privacy mode applies to position-revealing astronomy.

Sunrise/sunset, solar noon, day length, moon and object rise/set times, the
sky map and local sidereal time are all functions of the station position, so
/api/almanac, /api/object and /api → sidereal must honor location_display:
exact → the site; rounded → only the rounded site (as /api → location shows);
hidden → nothing computed.

The astronomy layer is replaced by recorders (Skyfield is not needed); the
tests check which site each calculation receives.
"""

import json
import os
import tempfile
import threading
import unittest
import urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401  (sets GTP_* paths before gps_time_pi is imported)
from gps_time_pi import astro, catalog, config, gps, server

# The project's example location (US Naval Observatory). h = H + N, N ≈ −33 m.
SITE = {"lat": 38.9217, "lon": -77.0669, "alt_msl": 92.0, "alt_hae": 59.0,
        "updated": "2026-10-01T00:00:00+00:00"}
ROUNDED = {"lat": 38.9, "lon": -77.1, "alt_msl": 90.0}


class PrivacyBase(unittest.TestCase):
    mode = "exact"

    def setUp(self):
        server._MEMO.clear()     # the almanac cache must not carry results from one test into another
        tmp = tempfile.mkdtemp(prefix="gps-time-privacy-")
        cfg_path = os.path.join(tmp, "config.json")
        Path(cfg_path).write_text(json.dumps({"location_display": self.mode}))
        self.sites = []          # every site handed to an astronomy function

        def rec(result):
            def f(*args, **kw):
                self.sites.extend(a for a in args if isinstance(a, dict) and "lat" in a)
                return result
            return f

        sun = {"available": True, "date": "2026-10-01", "tz": "UTC",
               "events": {"sunrise": "2026-10-01T10:47:00+00:00", "sunset": "2026-10-01T22:48:00+00:00"},
               "noon": "2026-10-01T16:48:00+00:00", "daylight_s": 43260.0, "bar": [], "notes": []}
        patches = [
            mock.patch.object(config, "_PATH", cfg_path),
            mock.patch.object(config, "_CACHE", None),
            mock.patch.object(server, "DEMO_MODE", False),
            # Windows has no IANA database without the tzdata package; zones are not under test here.
            mock.patch.object(server, "ZoneInfo", lambda name: timezone.utc),
            mock.patch.object(server, "available_timezones", lambda: {"UTC"}),
            mock.patch.object(gps, "observing_site", lambda: (dict(SITE), "live")),
            mock.patch.dict(astro.STATUS, {"available": True, "reason": None}),
            mock.patch.object(astro, "date_supported", lambda d: True),
            mock.patch.object(astro, "solar_day", rec(sun)),
            mock.patch.object(astro, "daylight_deltas", rec((-131.0, -132.0))),
            mock.patch.object(astro, "lunar_day", rec({"available": True, "phase": "Waxing crescent", "illum": 28.4,
                                                       "rise": None, "set": None})),
            mock.patch.object(astro, "night", rec({"available": True, "defined": False})),
            mock.patch.object(astro, "sky_snapshot", rec({"available": True, "stars": [], "lines": [], "bodies": [], "target": None})),
            mock.patch.object(astro, "object_report", rec({"available": True, "rise": None, "set": None})),
            mock.patch.object(astro, "sidereal", rec("12:34:56")),
            mock.patch.object(catalog, "lookup", lambda q: {"kind": "planet", "name": "Jupiter"} if q else None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def almanac(self):
        return server.almanac_api({"date": ["2026-10-01"], "tz": ["UTC"], "at": ["22:00"]})

    def obj(self):
        return server.object_api({"q": ["jupiter"], "date": ["2026-10-01"], "tz": ["UTC"], "at": ["22:00"]})

    def sidereal(self):
        return server.sidereal_for(config.load(), dict(SITE))


class TestExact(PrivacyBase):
    mode = "exact"

    def test_almanac_uses_exact_site(self):
        d = self.almanac()
        self.assertTrue(d["available"])
        self.assertEqual(d["location_display"], "exact")
        self.assertTrue(self.sites)
        for s in self.sites:
            self.assertEqual((s["lat"], s["lon"]), (SITE["lat"], SITE["lon"]))

    def test_object_and_sidereal_use_exact_site(self):
        self.assertTrue(self.obj()["available"])
        self.assertEqual(self.sidereal(), "12:34:56")
        for s in self.sites:
            self.assertEqual((s["lat"], s["lon"]), (SITE["lat"], SITE["lon"]))

    def test_portable_time_labels(self):
        d = self.almanac()
        self.assertEqual(d["sky_when"], "10:00 PM · Oct 1, 2026 · UTC")
        self.assertEqual(self.obj()["at_label"], "10:00 PM")
        dt = datetime(2026, 10, 1, 0, 5, tzinfo=timezone.utc)
        self.assertEqual(server._clock_label(dt), "12:05 AM")
        self.assertEqual(server._clock_label(dt.replace(hour=12)), "12:05 PM")


class TestRounded(PrivacyBase):
    mode = "rounded"

    def assert_only_rounded(self):
        self.assertTrue(self.sites, "no astronomy call was recorded")
        for s in self.sites:
            self.assertEqual(s["lat"], ROUNDED["lat"])
            self.assertEqual(s["lon"], ROUNDED["lon"])
            self.assertEqual(s.get("alt_msl"), ROUNDED["alt_msl"])
            self.assertIsNone(s.get("alt_hae"), "ellipsoidal height is not exposed in rounded mode")

    def test_almanac_computes_from_rounded_site_only(self):
        d = self.almanac()
        self.assertTrue(d["available"])
        self.assertEqual(d["location_display"], "rounded")
        self.assert_only_rounded()

    def test_object_computes_from_rounded_site_only(self):
        d = self.obj()
        self.assertTrue(d["available"])
        self.assertEqual(d["location_display"], "rounded")
        self.assert_only_rounded()

    def test_sidereal_from_rounded_site_only(self):
        self.assertEqual(self.sidereal(), "12:34:56")
        self.assert_only_rounded()

    def test_demo_mode_reports_rounded(self):
        with mock.patch.object(server, "DEMO_MODE", True):
            self.assertEqual(self.almanac()["location_display"], "rounded")
            self.assertEqual(server.core_api()["location"]["lat"], ROUNDED["lat"])

    def test_rounding_matches_displayed_location(self):
        cfg = config.load()
        site, mode = config.privacy_site(cfg, dict(SITE))
        shown = config.displayed_location(cfg, dict(SITE))
        self.assertEqual(mode, "rounded")
        self.assertEqual((site["lat"], site["lon"], site["alt_msl"]), (shown["lat"], shown["lon"], shown["alt_msl"]))


class TestHidden(PrivacyBase):
    mode = "hidden"

    def test_almanac_refuses_and_computes_nothing(self):
        d = self.almanac()
        self.assertFalse(d["available"])
        self.assertEqual(d["location_display"], "hidden")
        self.assertIn("privacy", d["reason"])
        self.assertEqual(self.sites, [])
        for leak in ("sun", "moon", "night", "sky", "neighbors", "delta_yesterday"):
            self.assertNotIn(leak, d)

    def test_object_refuses_and_computes_nothing(self):
        d = self.obj()
        self.assertFalse(d["available"])
        self.assertEqual(self.sites, [])

    def test_unparsed_object_still_reports_unparsed(self):
        self.assertEqual(server.object_api({"q": [""]}), {"error": "unparsed"})

    def test_sidereal_is_null(self):
        self.assertIsNone(self.sidereal())
        self.assertEqual(self.sites, [])

    def test_demo_mode_also_hides(self):
        with mock.patch.object(server, "DEMO_MODE", True):
            self.assertFalse(self.almanac()["available"])
            core = server.core_api()
            self.assertIsNone(core["sidereal"])
            self.assertEqual(core["location"], {"mode": "hidden", "lat": None, "lon": None})

    def test_http_responses_contain_no_times_or_coordinates(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        for path in ("/api/almanac?date=2026-10-01&tz=UTC", "/api/object?q=jupiter&tz=UTC"):
            with urllib.request.urlopen(base + path, timeout=10) as r:
                body = r.read().decode()
            d = json.loads(body)
            self.assertFalse(d["available"], path)
            for leak in ("T10:47", "T22:48", "38.9", "77.0"):
                self.assertNotIn(leak, body, path)


SATS = [{"id": 3, "gnss": "GPS", "el": 42, "az": 296, "snr": 32, "used": True},
        {"id": 11, "gnss": "Galileo", "el": 18, "az": 101, "snr": 27, "used": False}]


def _snapshot():
    return {"live": dict(SITE), "fix": "3D", "mode": 3, "sats": [dict(s) for s in SATS], "used": 1, "visible": 2,
            "tdop": 0.8, "hdop": 0.9, "last_fix": "3D", "last_fix_time": "2026-10-01T00:00:00Z", "stale": False,
            "data_age_s": 1.0, "sky_stale": False, "sky_age_s": 1.0, "gpsd_version": None, "receiver": None}


class SatAnglesBase(PrivacyBase):
    """Satellite azimuth/elevation: dropped in hidden, kept in exact/rounded."""

    def live_core(self):
        from gps_time_pi import chrony
        stubs = {"tracking": lambda: {}, "sources": lambda: [], "sourcestats": lambda: "",
                 "clients": lambda: [], "version": lambda: None, "refclock_config": lambda: {}}
        with mock.patch.multiple(chrony, **stubs), mock.patch.object(gps, "snapshot", _snapshot):
            return server.core_api()

    def demo_core(self):
        with mock.patch.object(server, "DEMO_MODE", True):
            return server.core_api()


class TestSatAnglesHidden(SatAnglesBase):
    mode = "hidden"

    def test_live_api_drops_az_el_keeps_the_rest(self):
        sats = self.live_core()["gps"]["sats"]
        self.assertEqual(len(sats), len(SATS))
        for got, want in zip(sats, SATS):
            self.assertIsNone(got["az"])
            self.assertIsNone(got["el"])
            self.assertEqual({k: got[k] for k in ("id", "gnss", "snr", "used")},
                             {k: want[k] for k in ("id", "gnss", "snr", "used")})

    def test_demo_api_drops_az_el(self):
        sats = self.demo_core()["gps"]["sats"]
        self.assertTrue(sats)
        self.assertTrue(all(s["az"] is None and s["el"] is None for s in sats))

    def test_helper_does_not_mutate_input(self):
        src = [dict(s) for s in SATS]
        config.privacy_sats({"location_display": "hidden"}, src)
        self.assertEqual(src, SATS)


class TestSatAnglesRounded(SatAnglesBase):
    mode = "rounded"

    def test_live_api_keeps_az_el(self):
        self.assertEqual(self.live_core()["gps"]["sats"], SATS)

    def test_demo_api_keeps_az_el(self):
        self.assertTrue(any(s["az"] is not None for s in self.demo_core()["gps"]["sats"]))


class TestSatAnglesExact(SatAnglesBase):
    mode = "exact"

    def test_live_api_keeps_az_el(self):
        self.assertEqual(self.live_core()["gps"]["sats"], SATS)


if __name__ == "__main__":
    unittest.main()


class TestSkyTargetPerRequest(PrivacyBase):
    """GPS-030: the sky map marks only the target the request names; a lookup by one
    client never changes another client's sky map (there is no server-global target)."""
    mode = "exact"

    def setUp(self):
        super().setUp()
        self.targets = []
        p = mock.patch.object(astro, "sky_snapshot",
                              lambda site, when, target=None: self.targets.append(target) or
                              {"available": True, "stars": [], "lines": [], "bodies": {}, "target": None})
        p.start()
        self.addCleanup(p.stop)

    def almanac_with(self, target):
        qs = {"date": ["2026-10-01"], "tz": ["UTC"], "at": ["22:00"]}
        if target is not None:
            qs["target"] = [target]
        return server.almanac_api(qs)

    def test_named_target_is_marked(self):
        self.assertTrue(self.almanac_with("jupiter")["available"])
        self.assertEqual(self.targets, [{"kind": "planet", "name": "Jupiter"}])

    def test_a_lookup_does_not_mark_anyone_elses_sky(self):
        self.assertTrue(self.obj()["available"])            # another client looks up Jupiter
        server._MEMO.clear()
        self.almanac_with(None)
        server._MEMO.clear()
        self.almanac_with("")
        self.assertEqual(self.targets, [None, None])

    def test_no_global_target_exists(self):
        self.assertFalse(hasattr(server, "_LAST_TARGET"))

