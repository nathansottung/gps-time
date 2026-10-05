"""Earth-shadow model (ADDENDUM-SKY-SOLAR-SATELLITE sections 1-4): umbra,
penumbra and sunlight for a point in the station's sky. Pure geometry: no
ephemeris, no NumPy, no network, no live GNSS.
"""

import inspect
import json
import math
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import labels, shadow as sh

USNO = {"lat": 38.9217, "lon": -77.0669, "alt_msl": 92.0, "alt_hae": 59.0}
SUN = (1.0, 0.0, 0.0)          # Sun along +x, for hand-checked geometry
D = sh.AU_KM


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


class TestSun(unittest.TestCase):
    def test_meeus_example_25a(self):
        # Meeus, Astronomical Algorithms, example 25.a: 1992 October 13.0 TD
        ra, dec, r = sh.sun_equatorial(2448908.5)
        self.assertAlmostEqual(ra, 198.38083, places=4)
        self.assertAlmostEqual(dec, -7.78507, places=4)
        self.assertAlmostEqual(r, 0.99766, places=5)

    def test_sidereal_time_meeus_example_12b(self):
        # Meeus example 12.b: 1987 April 10, 19h21m00s UT -> mean sidereal time 128.7378734 degrees
        self.assertAlmostEqual(sh.gmst_deg(2446896.30625), 128.7378734, places=5)

    def test_julian_date(self):
        self.assertEqual(sh.julian_date(utc(2000, 1, 1, 12)), 2451545.0)

    def test_subsolar_point_at_an_equinox_noon(self):
        # 2026-03-20 14:46 UTC is the equinox: the Sun is over the equator.
        unit, dist = sh.sun_ecef(utc(2026, 3, 20, 14, 46))
        self.assertAlmostEqual(math.degrees(math.asin(unit[2])), 0.0, delta=0.02)
        self.assertAlmostEqual(dist / sh.AU_KM, 0.996, delta=0.002)

    def test_sun_is_due_south_and_high_at_local_noon(self):
        obs = sh.Observer.from_site(USNO)
        unit, _ = sh.sun_ecef(utc(2026, 6, 21, 17, 10))      # solar noon at 77 W on the solstice
        az, alt = obs.altaz(unit)
        self.assertAlmostEqual(az, 180.0, delta=1.5)
        self.assertAlmostEqual(alt, 90 - 38.9217 + 23.44, delta=0.1)


class TestCones(unittest.TestCase):
    def test_not_a_cylinder(self):
        a_u, a_p = sh.cone_angles(D)
        self.assertAlmostEqual(math.degrees(a_u), 0.264, delta=0.002)
        self.assertAlmostEqual(math.degrees(a_p), 0.269, delta=0.002)
        self.assertGreater(a_p, a_u)

    def test_known_shadow_sizes(self):
        a_u, a_p = sh.cone_angles(D)
        # the umbra ends about 1.38 million km behind the Earth
        self.assertAlmostEqual(sh.R_EARTH_KM / math.sin(a_u), 1.383e6, delta=5e3)
        # at the Moon's distance the umbra is about 4600 km in radius and the penumbra about 8200 km
        on_axis = lambda rho: sh.shadow_state((-384400.0, rho, 0.0), SUN, D)[0]   # noqa: E731
        self.assertEqual(on_axis(4550.0), sh.UMBRA)
        self.assertEqual(on_axis(4650.0), sh.PENUMBRA)
        self.assertEqual(on_axis(8150.0), sh.PENUMBRA)
        self.assertEqual(on_axis(8200.0), sh.SUNLIT)

    def test_umbra_ends(self):
        self.assertEqual(sh.shadow_state((-1.30e6, 0.0, 0.0), SUN, D)[0], sh.UMBRA)
        self.assertEqual(sh.shadow_state((-1.45e6, 0.0, 0.0), SUN, D)[0], sh.PENUMBRA)

    def test_sunward_side_is_sunlit(self):
        for p in ((7000.0, 0.0, 0.0), (100.0, 6500.0, 0.0), (0.0, 0.0, 7000.0)):
            self.assertEqual(sh.shadow_state(p, SUN, D), (sh.SUNLIT, 1.0))

    def test_low_orbit_behind_the_earth(self):
        r = sh.R_EARTH_KM + 550
        self.assertEqual(sh.shadow_state((-r, 0.0, 0.0), SUN, D), (sh.UMBRA, 0.0))
        # the same height, off to the side of the shadow
        self.assertEqual(sh.shadow_state((-1000.0, r, 0.0), SUN, D)[0], sh.SUNLIT)

    def test_penumbra_fraction_runs_from_zero_to_one(self):
        x = 2000.0
        a_u, a_p = sh.cone_angles(D)
        r_u = sh.R_EARTH_KM / math.cos(a_u) - x * math.tan(a_u)
        r_p = sh.R_EARTH_KM / math.cos(a_p) + x * math.tan(a_p)
        fracs = [sh.shadow_state((-x, r_u + k * (r_p - r_u), 0.0), SUN, D) for k in (0.1, 0.5, 0.9)]
        self.assertEqual([s for s, _ in fracs], [sh.PENUMBRA] * 3)
        self.assertEqual([round(f, 2) for _, f in fracs], [0.1, 0.5, 0.9])

    def test_ground_at_sunset_is_penumbra_not_umbra(self):
        # Sun's centre 0.1 degree below the horizon: its upper limb is still up.
        r = sh.R_EARTH_KM
        d = math.radians(0.1)
        state, frac = sh.shadow_state((-r * math.sin(d), r * math.cos(d), 0.0), SUN, D)
        self.assertEqual(state, sh.PENUMBRA)
        self.assertTrue(0.0 < frac < 1.0)
        # one degree below: all of the disc is hidden
        d = math.radians(1.0)
        self.assertEqual(sh.shadow_state((-r * math.sin(d), r * math.cos(d), 0.0), SUN, D)[0], sh.UMBRA)


class TestObserver(unittest.TestCase):
    def test_directions(self):
        obs = sh.Observer(0.0, 0.0)
        self.assertAlmostEqual(obs.radius, sh.WGS84_A_KM, places=6)
        for az, alt in ((0, 0), (90, 0), (123.4, 56.7), (300, 89)):
            got = obs.altaz(obs.direction(az, alt))
            self.assertAlmostEqual(got[0], az % 360, places=6)
            self.assertAlmostEqual(got[1], alt, places=6)
        self.assertAlmostEqual(sh.Observer(90.0, 0.0).radius, sh.WGS84_A_KM * (1 - sh.WGS84_F), places=6)

    def test_shell_range(self):
        obs = sh.Observer.from_site(USNO)
        _, overhead = sh.shell_point(obs, 0, 90, 550)
        self.assertAlmostEqual(overhead, 550.0, delta=0.01)    # geodetic "up" is not exactly radial
        point, horizon = sh.shell_point(obs, 270, 0, 550)
        self.assertAlmostEqual(horizon, math.sqrt((obs.radius + 550) ** 2 - obs.radius ** 2), places=6)
        self.assertAlmostEqual(math.sqrt(sum(c * c for c in point)), obs.radius + 550, places=6)

    def test_height_falls_back_to_msl_then_zero(self):
        a = sh.Observer.from_site({"lat": 10, "lon": 20, "alt_msl": 500.0})
        b = sh.Observer.from_site({"lat": 10, "lon": 20})
        self.assertAlmostEqual(a.radius - b.radius, 0.5, places=3)


class TestZenith(unittest.TestCase):
    def at(self, when):
        return sh.report(USNO, when)

    def test_daylight_has_no_shadow_overhead(self):
        r = self.at(utc(2026, 10, 5, 17, 0))
        self.assertGreater(r["sun"]["altitude_deg"], 30)
        self.assertEqual(r["zenith"]["umbra_top_km"], None)
        self.assertEqual(r["zenith"]["penumbra_top_km"], None)
        self.assertEqual(r["zenith"]["ground_state"], sh.SUNLIT)
        self.assertIn("no Earth shadow overhead", r["zenith"]["note"])
        self.assertEqual(r["darkness"], {"stage": "day", "astronomical_darkness": False})

    def test_heights_bracket_the_cylinder_formula(self):
        # A cylindrical shadow would put the edge at R (1/cos(depression) - 1). The
        # umbra ends a little below that and full sunlight starts a little above.
        for when in (utc(2026, 10, 5, 23, 30), utc(2026, 10, 6, 0, 30), utc(2026, 10, 6, 2, 0)):
            r = self.at(when)
            dep = math.radians(r["sun"]["depression_deg"])
            cylinder = sh.R_EARTH_KM * (1 / math.cos(dep) - 1)
            z = r["zenith"]
            with self.subTest(when=when):
                self.assertLess(z["umbra_top_km"], cylinder)
                self.assertGreater(z["penumbra_top_km"], cylinder)
                self.assertLess(z["penumbra_top_km"] - z["umbra_top_km"], 0.06 * cylinder + 5)
                self.assertFalse(z["beyond_limit"])

    def test_shadow_height_rises_through_the_evening(self):
        tops = [self.at(utc(2026, 10, 5, 23, 0) + timedelta(minutes=30 * k))["zenith"]["umbra_top_km"] for k in range(6)]
        self.assertEqual(tops, sorted(tops))

    def test_zenith_note_says_it_is_not_the_whole_sky(self):
        self.assertIn("zenith only", self.at(utc(2026, 10, 6, 1, 0))["zenith"]["note"])

    def test_shell_state_matches_the_boundary_heights(self):
        r = self.at(utc(2026, 10, 6, 1, 0))          # umbra top ~760 km
        z = r["zenith"]
        by = {s["altitude_km"]: s["zenith"] for s in r["shells"]}
        for km, state in by.items():
            if km < z["umbra_top_km"] - 5:
                self.assertEqual(state, sh.UMBRA, km)
            if km > z["penumbra_top_km"] + 5:
                self.assertEqual(state, sh.SUNLIT, km)


class TestSkyMapAndShells(unittest.TestCase):
    def setUp(self):
        self.r = sh.report(USNO, utc(2026, 10, 6, 1, 0), 550.0, query=(300.0, 20.0))

    def test_default_shells_plus_the_chosen_one(self):
        self.assertEqual([s["altitude_km"] for s in self.r["shells"]], [200, 350, 400, 550, 1000, 1200, 2000])
        custom = sh.report(USNO, utc(2026, 10, 6, 1, 0), 780.0)
        self.assertIn(780.0, [s["altitude_km"] for s in custom["shells"]])
        self.assertEqual(custom["map"]["shell_km"], 780.0)

    def test_grid_shape(self):
        m = self.r["map"]
        self.assertEqual((m["alt_step_deg"], m["az_step_deg"]), (2, 5))
        self.assertEqual(len(m["rows"]), 46)
        self.assertTrue(all(len(row) == 72 and set(row) <= set("SPU") for row in m["rows"]))
        self.assertEqual(m["alts_deg"][0], 0)
        self.assertEqual(m["alts_deg"][-1], 90)

    def test_the_sunlit_part_of_the_sky_is_toward_the_sun(self):
        m, sun_az = self.r["map"], self.r["sun"]["azimuth_deg"]
        horizon = m["rows"][0]
        toward = horizon[int(round(sun_az / 5)) % 72]
        away = horizon[int(round(((sun_az + 180) % 360) / 5)) % 72]
        self.assertEqual((toward, away), ("S", "U"))
        self.assertEqual(set(m["rows"][-1]), {"U"})            # 550 km overhead is in shadow at this hour

    def test_higher_shells_are_lit_over_more_of_the_sky(self):
        fractions = [s["sunlit_sky_fraction"] for s in self.r["shells"]]
        self.assertEqual(fractions, sorted(fractions))
        self.assertLess(fractions[0], fractions[-1])

    def test_point_question(self):
        q = self.r["query"]
        self.assertEqual((q["azimuth_deg"], q["altitude_deg"], q["shell_km"]), (300.0, 20.0, 550.0))
        self.assertIn(q["state"], (sh.SUNLIT, sh.PENUMBRA, sh.UMBRA))
        self.assertGreater(q["range_km"], 550)
        self.assertIsNone(sh.report(USNO, utc(2026, 10, 6, 1, 0))["query"])

    def test_summary_names_where_sunlit_satellites_remain(self):
        s = [x for x in self.r["shells"] if x["altitude_km"] == 550][0]
        self.assertEqual(s["zenith"], sh.UMBRA)
        self.assertTrue(set(s["sunlit_sectors"]) & {"W", "NW"})
        self.assertIn("In Earth's shadow above", s["summary"])

    def test_labels_and_wording(self):
        self.assertEqual(self.r["provenance"], "modeled")
        self.assertIn(self.r["provenance"], labels.PROVENANCE)
        self.assertIn("airless", self.r["model"])
        self.assertIn("does not say that a satellite", self.r["meaning"])
        text = " ".join(self.r["messages"])
        self.assertIn("geometric predictions", text)
        self.assertIn("not sightings", text)
        for word in ("guarantee", "will be visible", "Starlink"):
            self.assertNotIn(word, text)
        json.dumps(self.r)

    def test_messages_by_time_of_day(self):
        day = sh.report(USNO, utc(2026, 10, 5, 17, 0))["messages"]
        self.assertEqual(len(day), 1)
        self.assertIn("The Sun is up", day[0])
        deep = " ".join(sh.report(USNO, utc(2026, 10, 6, 4, 0))["messages"])
        self.assertIn("~550 km LEO should be in Earth's shadow over the whole sky", deep)

    def test_twilight_stages(self):
        self.assertEqual([sh.twilight(a) for a in (10, -0.5, -3, -9, -15, -18.5)],
                         ["day", "day", "civil twilight", "nautical twilight", "astronomical twilight", "night"])

    def test_shell_input_is_validated(self):
        self.assertEqual([sh.valid_shell(v) for v in ("550", "1200.5", "99", "60000", "abc", "nan", None, "inf")],
                         [550.0, 1200.5, None, None, None, None, None, None])

    def test_module_is_pure(self):
        src = inspect.getsource(sh)
        for word in ("open(", "urllib", "socket", "subprocess", "import numpy", "skyfield"):
            self.assertFalse(word in src, f"shadow.py must not use {word}")


class TestRouteAndPrivacy(unittest.TestCase):
    def payload(self, mode, qs=None, site=USNO):
        from gps_time_pi import config, gps, server
        server._SKY_CACHE.clear()
        seen = []
        real = sh.report

        def spy(s, *a, **k):
            seen.append(dict(s))
            return real(s, *a, **k)
        with mock.patch.object(server, "DEMO_MODE", False), \
                mock.patch.object(config, "load", lambda: {"location_display": mode}), \
                mock.patch.object(gps, "observing_site", lambda: (site and dict(site), "live")), \
                mock.patch.object(sh, "report", spy):
            return server.shadow_payload(qs or {}), seen

    def test_exact(self):
        r, seen = self.payload("exact")
        self.assertTrue(r["available"])
        self.assertEqual(r["location_display"], "exact")
        self.assertEqual(seen[0]["lat"], 38.9217)

    def test_rounded_mode_computes_from_the_rounded_site_only(self):
        r, seen = self.payload("rounded")
        self.assertTrue(r["available"])
        self.assertEqual(r["location_display"], "rounded")
        self.assertEqual((seen[0]["lat"], seen[0]["lon"]), (38.9, -77.1))
        self.assertNotIn("alt_hae", seen[0])

    def test_hidden_mode_computes_nothing(self):
        r, seen = self.payload("hidden")
        self.assertFalse(r["available"])
        self.assertEqual(seen, [])
        self.assertIn("privacy", r["reason"])
        self.assertNotIn("map", r)
        self.assertNotIn("sun", r)

    def test_no_position_is_unknown(self):
        r, seen = self.payload("exact", site=None)
        self.assertFalse(r["available"])
        self.assertIn("No valid location", r["reason"])
        self.assertEqual(seen, [])

    def test_query_arguments(self):
        r, _ = self.payload("exact", {"shell": ["1200"], "az": ["300"], "alt": ["20"]})
        self.assertEqual(r["map"]["shell_km"], 1200.0)
        self.assertEqual(r["query"]["shell_km"], 1200.0)
        bad, _ = self.payload("exact", {"shell": ["5"], "az": ["400"], "alt": ["20"]})
        self.assertEqual(bad["map"]["shell_km"], 550.0)
        self.assertIsNone(bad["query"])

    def test_demo_mode_uses_the_demo_site(self):
        from gps_time_pi import config, server
        server._SKY_CACHE.clear()
        with mock.patch.object(server, "DEMO_MODE", True), mock.patch.object(config, "load", lambda: {}):
            r = server.shadow_payload({})
        self.assertTrue(r["available"])


if __name__ == "__main__":
    unittest.main()
