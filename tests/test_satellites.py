"""Satellite ephemeris layer (ADDENDUM-SKY-SOLAR-SATELLITE section 5): cached
orbital elements, positions, passes and shadow crossings.

Fixture: the ISS element set that is the standard published TLE example
(epoch 2008-09-20). No network: the fetcher is tested with an injected
download function. Tests that propagate need the sgp4 package (installed with
Skyfield); the comparison with Skyfield needs Skyfield.
"""

import importlib.util
import inspect
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import labels, satellites as st, shadow as sh, tle_fetch

FIX = Path(__file__).parent / "fixtures" / "tle"
ISS = (FIX / "iss-2008.tle").read_text(encoding="ascii")
USNO = {"lat": 38.9217, "lon": -77.0669, "alt_msl": 92.0, "alt_hae": 59.0}
EPOCH = datetime(2008, 9, 20, 12, 25, 40, tzinfo=timezone.utc)
HAVE_SGP4 = st.SGP4["available"]
HAVE_SKYFIELD = importlib.util.find_spec("skyfield") is not None


def tmpdir(test):
    d = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, d, ignore_errors=True)
    return d


class TestTleParsing(unittest.TestCase):
    def test_three_line_set(self):
        sets, rejected = st.parse_tle_text(ISS)
        self.assertEqual(rejected, 0)
        self.assertEqual(len(sets), 1)
        s = sets[0]
        self.assertEqual((s["norad"], s["name"]), (25544, "ISS (ZARYA)"))
        self.assertAlmostEqual(s["epoch"], EPOCH.timestamp(), delta=1.0)

    def test_two_line_set_and_zero_prefixed_name(self):
        l1, l2 = ISS.splitlines()[1:3]
        sets, _ = st.parse_tle_text(f"{l1}\n{l2}\n")
        self.assertEqual(sets[0]["name"], "NORAD 25544")
        sets, _ = st.parse_tle_text(f"0 ISS (ZARYA)\n{l1}\n{l2}\n")
        self.assertEqual(sets[0]["name"], "ISS (ZARYA)")

    def test_checksum(self):
        l1, l2 = ISS.splitlines()[1:3]
        self.assertEqual((st.tle_checksum(l1), st.tle_checksum(l2)), (7, 7))

    def test_damaged_sets_are_rejected_not_used(self):
        l0, l1, l2 = ISS.splitlines()[:3]
        for bad1, bad2 in ((l1.replace("51782528", "51782529"), l2),      # checksum no longer matches
                           (l1, l2.replace("2 25544", "2 25545")),        # different catalogue numbers
                           (l1[:60], l2)):                                # truncated
            sets, rejected = st.parse_tle_text(f"{l0}\n{bad1}\n{bad2}\n")
            self.assertEqual((sets, rejected), ([], 1))

    def test_an_error_page_has_no_sets(self):
        self.assertEqual(st.parse_tle_text("<html><body>Invalid query</body></html>\n"), ([], 0))
        self.assertEqual(st.parse_tle_text(""), ([], 0))

    def test_epoch_century(self):
        self.assertEqual(st._iso(st.tle_epoch("1 00005U 58002B   58001.00000000")), "1958-01-01T00:00:00+00:00")
        self.assertEqual(datetime.fromtimestamp(st.tle_epoch("1 99999U 26001A   26278.50000000"), timezone.utc),
                         datetime(2026, 10, 5, 12, tzinfo=timezone.utc))


class TestCache(unittest.TestCase):
    def test_missing_directory_is_empty_not_an_error(self):
        c = st.load_cache(os.path.join(_env.TMP, "no-tle-dir"))
        self.assertEqual((c["sats"], c["groups"], c["problems"]), ({}, [], []))

    def test_groups_and_manifest(self):
        d = tmpdir(self)
        tle_fetch.store(d, "stations", ISS, "https://example.invalid/stations", EPOCH + timedelta(hours=5))
        c = st.load_cache(d)
        self.assertEqual(list(c["sats"]), [25544])
        self.assertEqual(c["sats"][25544]["group"], "stations")
        g = c["groups"][0]
        self.assertEqual((g["group"], g["count"], g["rejected"]), ("stations", 1, 0))
        self.assertEqual(g["source"], "https://example.invalid/stations")
        self.assertEqual(g["fetched_utc"], "2008-09-20T17:25:40+00:00")
        self.assertEqual(g["newest_epoch_utc"], "2008-09-20T12:25:40+00:00")

    def test_changed_file_is_reread(self):
        d = tmpdir(self)
        tle_fetch.store(d, "a", ISS, "x")
        self.assertEqual(len(st.load_cache(d)["sats"]), 1)
        os.remove(os.path.join(d, "a.tle"))
        self.assertEqual(len(st.load_cache(d)["sats"]), 0)

    def test_rejected_sets_are_reported(self):
        d = tmpdir(self)
        l0, l1, l2 = ISS.splitlines()[:3]
        Path(d, "mixed.tle").write_text(ISS + f"BROKEN\n{l1[:-1]}0\n{l2}\n", encoding="ascii")
        c = st.load_cache(d)
        self.assertEqual(len(c["sats"]), 1)
        self.assertTrue(any("rejected" in p for p in c["problems"]))

    def test_summary_shows_the_age_of_the_elements(self):
        d = tmpdir(self)
        tle_fetch.store(d, "stations", ISS, "x")
        s = st.summary(st.load_cache(d), EPOCH + timedelta(days=3))
        self.assertEqual(s["satellites"], 1)
        self.assertEqual(s["newest_age_days"], 3.0)
        self.assertEqual(s["provenance"], "external")

    def test_search(self):
        d = tmpdir(self)
        tle_fetch.store(d, "stations", ISS, "x")
        c = st.load_cache(d)
        self.assertEqual([m["norad"] for m in st.search(c, "zarya", EPOCH)], [25544])
        self.assertEqual([m["norad"] for m in st.search(c, "25544", EPOCH)], [25544])
        self.assertEqual(st.search(c, "hubble", EPOCH), [])
        self.assertEqual(st.search(c, "", EPOCH), [])


class TestFetcher(unittest.TestCase):
    def test_download_goes_to_the_fixed_source_and_is_stored(self):
        d, urls = tmpdir(self), []

        def fake(url):
            urls.append(url)
            return ISS
        n = tle_fetch.fetch_group(d, "stations", fetch=fake, now=EPOCH)
        self.assertEqual(n, 1)
        self.assertEqual(urls, ["https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle"])
        self.assertEqual(sorted(os.listdir(d)), ["manifest.json", "stations.tle"])
        m = json.loads(Path(d, "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["stations"]["count"], 1)
        self.assertEqual(len(m["stations"]["sha256"]), 64)

    def test_an_error_page_never_replaces_good_elements(self):
        d = tmpdir(self)
        tle_fetch.fetch_group(d, "stations", fetch=lambda url: ISS, now=EPOCH)
        before = Path(d, "stations.tle").read_bytes()
        with self.assertRaises(ValueError):
            tle_fetch.fetch_group(d, "stations", force=True, fetch=lambda url: "<html>error</html>", now=EPOCH)
        self.assertEqual(Path(d, "stations.tle").read_bytes(), before)
        self.assertEqual(sorted(os.listdir(d)), ["manifest.json", "stations.tle"], "no temporary file may be left")

    def test_a_failed_download_changes_nothing(self):
        d = tmpdir(self)

        def boom(url):
            raise OSError("no route to host")
        with self.assertRaises(OSError):
            tle_fetch.fetch_group(d, "stations", fetch=boom, now=EPOCH)
        self.assertFalse(os.path.exists(os.path.join(d, "stations.tle")))

    def test_two_hour_limit(self):
        d, calls = tmpdir(self), []
        fake = lambda url: calls.append(url) or ISS       # noqa: E731
        tle_fetch.fetch_group(d, "stations", fetch=fake, now=EPOCH)
        with self.assertRaises(ValueError) as cm:
            tle_fetch.fetch_group(d, "stations", fetch=fake, now=EPOCH + timedelta(minutes=30))
        self.assertIn("--force", str(cm.exception))
        tle_fetch.fetch_group(d, "stations", fetch=fake, now=EPOCH + timedelta(minutes=30), force=True)
        tle_fetch.fetch_group(d, "stations", fetch=fake, now=EPOCH + timedelta(hours=3))
        self.assertEqual(len(calls), 3)

    def test_group_names_cannot_change_the_url_or_the_path(self):
        d = tmpdir(self)
        for bad in ("../etc", "stations&x=1", "a b", "", "UPPER", "a/b", "x.tle"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                tle_fetch.fetch_group(d, bad, fetch=lambda url: ISS)
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                tle_fetch.store(d, bad, ISS, "x")
        self.assertEqual(os.listdir(d), [])

    def test_import_a_local_file_from_the_command_line(self):
        d = tmpdir(self)
        with mock.patch("builtins.print"):
            status = tle_fetch.main(["--file", str(FIX / "iss-2008.tle"), "--name", "mine", "--dir", d])
        self.assertEqual(status, 0)
        self.assertEqual(list(st.load_cache(d)["sats"]), [25544])
        self.assertEqual(st.load_cache(d)["groups"][0]["source"], "file:iss-2008.tle")

    def test_only_the_fetcher_uses_the_network(self):
        for module in (st, sh):
            src = inspect.getsource(module)
            for word in ("urllib", "socket", "http.client", "requests"):
                self.assertFalse(word in src, f"{module.__name__} must not use {word}")
        self.assertIn("https://celestrak.org/", tle_fetch.URL)
        from gps_time_pi import server
        self.assertNotIn("tle_fetch", inspect.getsource(server), "the web service must never fetch elements")


@unittest.skipUnless(HAVE_SGP4, "sgp4 package needed")
class TestGeometry(unittest.TestCase):
    def setUp(self):
        self.elements = st.parse_tle_text(ISS)[0][0]
        self.sat = st._satrec(self.elements)
        self.obs = sh.Observer.from_site(USNO)

    def test_orbit_is_the_iss(self):
        p = st.look(self.obs, self.sat, EPOCH)
        self.assertAlmostEqual(p["height_km"], 350, delta=25)
        self.assertGreater(p["range_km"], 300)

    @unittest.skipUnless(HAVE_SKYFIELD, "Skyfield needed for the comparison")
    def test_direction_and_range_agree_with_skyfield(self):
        import math
        from skyfield.api import EarthSatellite, load, wgs84
        ts = load.timescale()
        ref = EarthSatellite(self.elements["line1"], self.elements["line2"], "ISS", ts)
        place = wgs84.latlon(USNO["lat"], USNO["lon"], elevation_m=USNO["alt_hae"])
        for k in range(400):
            when = EPOCH + timedelta(seconds=211 * k)
            mine = st.look(self.obs, self.sat, when)
            alt, az, dist = (ref - place).at(ts.from_datetime(when)).altaz()
            daz = abs((mine["az"] - az.degrees + 180) % 360 - 180) * math.cos(math.radians(alt.degrees))
            self.assertLess(daz, 0.05)
            self.assertAlmostEqual(mine["alt"], alt.degrees, delta=0.05)
            self.assertAlmostEqual(mine["range_km"], dist.km, delta=1.0)

    def test_passes_of_the_first_day(self):
        ps = st.passes(self.obs, self.sat, EPOCH, 24)
        self.assertEqual(len(ps), 7)
        first = ps[0]
        # checked against Skyfield's find_events for this element set and site
        self.assertEqual(first["rise"]["utc"], "2008-09-20T22:48:49+00:00")
        self.assertEqual(first["set"]["utc"], "2008-09-20T22:57:16+00:00")
        self.assertAlmostEqual(first["culmination"]["altitude_deg"], 12.9, delta=0.2)
        self.assertEqual(first["rise"]["altitude_deg"], 0.0)
        self.assertEqual(first["provenance"], "predicted")
        for p in ps:
            self.assertLess(p["rise"]["utc"], p["culmination"]["utc"])
            self.assertLess(p["culmination"]["utc"], p["set"]["utc"])
            self.assertFalse(p["in_progress"])

    def test_evening_pass_enters_the_shadow_and_has_a_visible_interval(self):
        p = st.passes(self.obs, self.sat, EPOCH, 24)[1]
        self.assertEqual(p["rise"]["utc"], "2008-09-21T00:23:10+00:00")
        self.assertEqual([c["kind"] for c in p["shadow_changes"]], ["penumbra entry", "umbra entry"])
        pen, umb = (c["utc"] for c in p["shadow_changes"])
        self.assertLess(pen, umb)
        self.assertEqual(p["set"]["state"], sh.UMBRA)
        v = p["visible"]
        self.assertIsNotNone(v)
        self.assertLessEqual(v["end_utc"], umb)
        self.assertGreater(v["start_utc"], p["rise"]["utc"])           # not until it is 10 degrees up
        self.assertAlmostEqual(v["max_altitude_deg"], 48.3, delta=0.3)
        self.assertLess(p["sun_altitude_deg"], -6)

    def test_no_visible_interval_in_daylight_or_in_full_shadow(self):
        ps = st.passes(self.obs, self.sat, EPOCH, 24)
        self.assertIsNone(ps[0]["visible"], "the Sun is up during the first pass")
        self.assertIsNone(ps[5]["visible"], "the middle-of-the-night pass is in the umbra throughout")
        self.assertEqual(ps[5]["culmination"]["state"], sh.UMBRA)

    def test_pass_in_progress_has_no_rise(self):
        ps = st.passes(self.obs, self.sat, datetime(2008, 9, 21, 0, 27, tzinfo=timezone.utc), 1)
        self.assertTrue(ps[0]["in_progress"])
        self.assertIsNone(ps[0]["rise"])
        self.assertEqual(ps[0]["set"]["utc"], "2008-09-21T00:32:59+00:00")

    def test_angular_speed_is_highest_near_culmination(self):
        high = st.angular_speed(self.obs, self.sat, datetime(2008, 9, 21, 0, 28, 4, tzinfo=timezone.utc))
        low = st.angular_speed(self.obs, self.sat, datetime(2008, 9, 21, 0, 23, 30, tzinfo=timezone.utc))
        self.assertGreater(high, 2 * low)
        self.assertAlmostEqual(high, 0.9, delta=0.4)        # degrees per second, ISS at 48 degrees

    def test_now_state(self):
        s = st.now_state(self.obs, self.elements, datetime(2008, 9, 21, 0, 28, 4, tzinfo=timezone.utc))
        self.assertTrue(s["available"])
        self.assertEqual(s["provenance"], "modeled")
        self.assertIn(s["provenance"], labels.PROVENANCE)
        self.assertAlmostEqual(s["altitude_deg"], 48.3, delta=0.3)
        self.assertEqual((s["state"], s["could_be_seen"], s["above_horizon"]), (sh.SUNLIT, True, True))
        self.assertEqual(s["epoch_utc"], "2008-09-20T12:25:40+00:00")
        self.assertEqual(s["age_days"], 0.5)
        self.assertFalse(s["stale"])


@unittest.skipUnless(HAVE_SGP4, "sgp4 package needed")
class TestReport(unittest.TestCase):
    def setUp(self):
        self.dir = tmpdir(self)
        tle_fetch.store(self.dir, "stations", ISS, "x", EPOCH)

    def test_report(self):
        r = st.report(USNO, EPOCH, directory=self.dir)
        self.assertTrue(r["available"])
        self.assertEqual(r["provenance"], "external")
        self.assertEqual([f["norad"] for f in r["featured"]], [25544])
        self.assertEqual(r["satellite"]["norad"], 25544, "the first featured satellite is shown by default")
        self.assertEqual(len(r["passes"]), 7)
        self.assertEqual(r["cache"]["satellites"], 1)
        self.assertIn("says nothing about brightness", r["meaning"])
        json.dumps(r)

    def test_old_elements_are_flagged_prominently(self):
        r = st.report(USNO, EPOCH + timedelta(days=40), directory=self.dir, hours=1)
        s = r["satellite"]
        self.assertTrue(s["stale"])
        self.assertEqual(s["age_days"], 40.0)
        self.assertIn("40 days old", s["age_note"])
        self.assertIn("unreliable", s["age_note"])
        self.assertEqual(r["cache"]["newest_age_days"], 40.0)

    def test_unknown_satellite(self):
        r = st.report(USNO, EPOCH, norad=20580, directory=self.dir)
        self.assertFalse(r["satellite"]["available"])
        self.assertIn("not in the cached elements", r["satellite"]["reason"])
        self.assertEqual(r["passes"], [])

    def test_empty_cache_says_how_to_fill_it(self):
        r = st.report(USNO, EPOCH, directory=tmpdir(self))
        self.assertFalse(r["available"])
        self.assertIn("tle_fetch", r["reason"])
        self.assertIn("offline", r["reason"])
        self.assertEqual(r["cache"]["satellites"], 0)

    def test_works_with_the_network_cut_off(self):
        import socket
        with mock.patch.object(socket, "socket", side_effect=AssertionError("no network allowed")), \
                mock.patch.object(socket, "create_connection", side_effect=AssertionError("no network allowed")):
            r = st.report(USNO, EPOCH, directory=self.dir)
        self.assertEqual(len(r["passes"]), 7)


class TestWithoutSgp4(unittest.TestCase):
    def test_missing_package_is_a_reason_not_a_crash(self):
        with mock.patch.dict(st.SGP4, {"available": False, "reason": "The sgp4 package could not be imported (x)."}):
            r = st.report(USNO, EPOCH, directory=os.path.join(_env.TMP, "none"))
        self.assertFalse(r["available"])
        self.assertIn("sgp4", r["reason"])


class TestRouteAndPrivacy(unittest.TestCase):
    def payload(self, mode, qs=None, demo=False):
        from gps_time_pi import config, gps, server
        server._SKY_CACHE.clear()
        seen = []

        def spy(site, when, norad=None, query=None, **k):
            seen.append((dict(site), norad, query))
            return {"available": True, "reason": None}
        with mock.patch.object(server, "DEMO_MODE", demo), \
                mock.patch.object(config, "load", lambda: {"location_display": mode}), \
                mock.patch.object(gps, "observing_site", lambda: (dict(USNO), "live")), \
                mock.patch.object(st, "report", spy):
            return server.satellites_payload(qs or {}), seen

    def test_hidden_mode_computes_nothing(self):
        r, seen = self.payload("hidden")
        self.assertFalse(r["available"])
        self.assertIn("privacy", r["reason"])
        self.assertEqual(seen, [])
        demo, _ = self.payload("hidden", demo=True)
        self.assertFalse(demo["available"], "demo mode honors the privacy mode too")

    def test_rounded_mode_uses_the_rounded_site(self):
        r, seen = self.payload("rounded")
        self.assertEqual(r["location_display"], "rounded")
        self.assertEqual((seen[0][0]["lat"], seen[0][0]["lon"]), (38.9, -77.1))

    def test_arguments(self):
        _, seen = self.payload("exact", {"sat": ["25544"], "q": ["zarya" + "x" * 100]})
        self.assertEqual(seen[0][1], 25544)
        self.assertEqual(len(seen[0][2]), 40)
        _, seen = self.payload("exact", {"sat": ["abc"]})
        self.assertIsNone(seen[0][1])
        _, seen = self.payload("exact", {"sat": ["-5"]})
        self.assertIsNone(seen[0][1])

    def test_demo_payload_needs_no_elements(self):
        r, seen = self.payload("exact", demo=True)
        self.assertEqual(seen, [])
        self.assertTrue(r["available"])
        self.assertEqual(len(r["passes"]), 2)
        self.assertIn("synthetic", r["demo"]["note"])
        json.dumps(r)


if __name__ == "__main__":
    unittest.main()
