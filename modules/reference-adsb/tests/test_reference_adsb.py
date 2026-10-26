"""reference-adsb: parsing, the self-reported rule, checks, geometry, bounds, privacy and the source.

Fixtures are synthetic (fixtures/aircraft-1090.json, aircraft-978.json), around the US Naval
Observatory example site. No network, no decoder, no SDR.
"""

import json
import math
import unittest
from pathlib import Path

from gps_time_pi.modkit import ModuleContext, Transmitter
from reference_adsb import feeds
from reference_adsb.geometry import C, FT, slant_range
from reference_adsb.reference import EPU_M, AdsbReference, site_tuple
from reference_adsb.source import EXAMPLE_SITE, AdsbSource, _fixture_reader

FIX = Path(__file__).resolve().parents[1] / "fixtures"
SITE = dict(EXAMPLE_SITE)
NOW = json.loads((FIX / "aircraft-1090.json").read_text(encoding="utf-8"))["now"]


def doc(*aircraft, now=NOW):
    return {"now": now, "aircraft": list(aircraft)}


def reader_for(d1090, d978=None):
    def r(path, band):
        d = d1090 if band == 1090 else d978
        return feeds.parse(d, band) if d else ([], None)
    return r


def overhead(**kw):
    a = {"hex": "abc123", "type": "adsb_icao", "lat": SITE["lat"], "lon": SITE["lon"], "alt_geom": 10000 / FT,
         "gs": 0, "nac_p": 9, "gva": 2, "seen_pos": 0.0}
    a.update(kw)
    return a


class TestFeeds(unittest.TestCase):
    def test_parse(self):
        ac, now = feeds.parse(doc(overhead(alt_geom=None, alt_baro=12000, flight="TST1  ", gs=400)), 1090)
        self.assertEqual(now, NOW)
        a = ac[0]
        self.assertEqual((a.icao, a.flight, a.alt_kind), ("abc123", "TST1", "barometric"))
        self.assertAlmostEqual(a.alt_m, 12000 * FT)
        self.assertAlmostEqual(a.gs_mps, 400 * 1852 / 3600)
        self.assertEqual(a.t_pos, NOW)
        g = feeds.parse(doc({"hex": "x", "alt_baro": "ground", "lat": 1, "lon": 2}), 1090)[0][0]
        self.assertIsNone(g.alt_m)

    def test_self_reported_rule(self):
        for kw, ok in (({}, True), ({"type": "mlat"}, False), ({"type": "tisb_icao"}, False), ({"type": "adsr_icao"}, False),
                       ({"type": "mode_s"}, False), ({"mlat": ["lat", "lon"]}, False), ({"tisb": ["lat"]}, False),
                       ({"mlat": ["gs"]}, True), ({"type": None}, True)):
            a = feeds.parse(doc(overhead(**kw)), 1090)[0][0]
            self.assertEqual(feeds.self_reported(a), ok, kw)

    def test_missing_file_is_empty(self):
        self.assertEqual(feeds.read_file(str(FIX / "nope.json"), 1090), ([], None))


class TestReference(unittest.TestCase):
    def test_fixtures(self):
        ref = AdsbReference(reader=_fixture_reader)
        txs = ref.list(SITE)
        self.assertEqual(ref.seen, {1090: 15, 978: 4})
        self.assertEqual(len(txs), 8)
        self.assertEqual(ref.rejected, {"no_position": 1, "not_self_reported": 4, "stale": 2, "accuracy_unknown": 1,
                                        "low_accuracy": 1, "no_altitude": 1, "out_of_range": 1, "implausible_jump": 0})
        self.assertTrue(all(t.position_source.startswith("self-reported") for t in txs))
        self.assertEqual({t.frequency_hz for t in txs}, {1090e6, 978e6})

    def test_delay_of_an_aircraft_overhead(self):
        ref = AdsbReference(reader=reader_for(doc(overhead())))
        tx = ref.list(SITE)[0]
        pr = ref.predict(SITE, tx, int(NOW * 1e9))
        self.assertAlmostEqual(pr["range_m"]["value"], 10000 - SITE["alt_hae"], delta=0.5)
        self.assertAlmostEqual(pr["delay_s"]["value"], (10000 - SITE["alt_hae"]) / C, delta=2e-9)
        # NACp 9 (30 m) and GVA 2 (45 m), not moving, exact site: sqrt(30² + 45²)
        self.assertAlmostEqual(pr["uncertainty_s"]["value"] * C, math.hypot(EPU_M[9], 45.0), delta=0.01)
        self.assertEqual(pr["delay_s"]["provenance"], "calculated")
        self.assertIn("troposphere", pr["uncertainty_s"]["note"])

    def test_bound_grows_with_age_baro_and_rounding(self):
        moving = overhead(gs=500, seen_pos=1.0, alt_geom=None, alt_baro=30000)
        ref = AdsbReference(reader=reader_for(doc(moving)))
        tx = ref.list(SITE)[0]
        exact = ref.predict(SITE, tx, int(NOW * 1e9))["uncertainty_s"]["value"] * C
        later = ref.predict(SITE, tx, int((NOW + 2) * 1e9))["uncertainty_s"]["value"] * C
        self.assertGreater(later, exact)                           # older fix: wider bound
        self.assertGreater(exact, 300)                             # barometric altitude ±300 m
        rounded = {"lat": 38.9, "lon": -77.1, "alt_msl": 90.0, "privacy": "rounded"}
        r = ref.predict(rounded, tx, int(NOW * 1e9))
        self.assertGreater(r["uncertainty_s"]["value"] * C, 5000)  # the site's rounding dominates
        self.assertIn("site rounding", r["uncertainty_s"]["note"])
        self.assertEqual(site_tuple(rounded)[3], 100.0)            # height above MSL only: ±100 m

    def test_hidden_site_predicts_nothing(self):
        ref = AdsbReference(reader=reader_for(doc(overhead())))
        tx = ref.list(None)[0]                                     # listing works; no range check without a site
        pr = ref.predict(None, tx, int(NOW * 1e9))
        self.assertIsNone(pr["delay_s"]["value"])
        self.assertIn("hidden", pr["delay_s"]["note"])
        unknown = Transmitter("1090:zzz", 1090e6, 2.6e6, {"lat": 0, "lon": 0, "alt_m": 0}, "x")
        self.assertIsNone(ref.predict(SITE, unknown, 0)["delay_s"]["value"])

    def test_below_the_horizon_and_too_far(self):
        far = overhead(lat=SITE["lat"] + 4.5)                      # ~500 km north at 10 km: beyond 450 km
        low = overhead(lat=SITE["lat"] + 3.0, alt_geom=100 / FT)   # ~330 km at 100 m: below the horizon
        ref = AdsbReference(reader=reader_for(doc(far, {**low, "hex": "def456"})))
        self.assertEqual(ref.list(SITE), [])
        self.assertEqual(ref.rejected["out_of_range"], 2)

    def test_implausible_jump(self):
        a = overhead(seen_pos=0.0)
        ref = AdsbReference(reader=reader_for(doc(a)))
        self.assertEqual(len(ref.list(SITE)), 1)
        b = overhead(seen_pos=0.0, lat=SITE["lat"] + 1.0)          # 111 km in 10 s
        ref.reader = reader_for(doc(b, now=NOW + 10))
        self.assertEqual(ref.list(SITE), [])
        self.assertEqual(ref.rejected["implausible_jump"], 1)
        c = overhead(seen_pos=0.0, lat=SITE["lat"] + 0.01)         # 1.1 km in 10 s: fine
        ref.reader = reader_for(doc(c, now=NOW + 10))
        self.assertEqual(len(ref.list(SITE)), 1)

    def test_geometry_symmetry(self):
        a, b = (38.9, -77.0, 50.0), (39.5, -76.0, 9000.0)
        self.assertAlmostEqual(slant_range(a, b), slant_range(b, a), places=6)


class TestSource(unittest.TestCase):
    def ctx(self, site, **config):
        out = []
        c = ModuleContext("reference-adsb", config=config, emit=out.append, site=lambda: site,
                          clock_ns=lambda: int(NOW * 1e9))
        return c, out

    def test_cycle_with_a_site(self):
        c, _ = self.ctx(SITE, max_per_band=2)
        obs = AdsbSource().cycle(c, AdsbReference(reader=_fixture_reader), SITE, int(NOW * 1e9))
        self.assertEqual(len(obs), 1 + 2 + 2)                      # summary + 2 per band
        s = obs[0].values
        self.assertEqual(s["references_accepted"]["value"], 8)
        self.assertIs(s["site_available"]["value"], True)
        per = obs[1].values
        self.assertEqual(per["lat"]["provenance"], "external")
        self.assertEqual(per["delay_s"]["provenance"], "calculated")
        bounds = [o.values["uncertainty_s"]["value"] for o in obs[1:] if o.values["transmitter"]["value"].startswith("1090")]
        self.assertEqual(bounds, sorted(bounds))                    # best-bounded first

    def test_hidden_site_emits_counts_only(self):
        c, _ = self.ctx(None)
        obs = AdsbSource().cycle(c, AdsbReference(reader=_fixture_reader), None, int(NOW * 1e9))
        self.assertEqual(len(obs), 1)
        self.assertIs(obs[0].values["site_available"]["value"], False)

    def test_demo_runs_once_from_the_example_site(self):
        c, out = self.ctx(None, demo=True)
        AdsbSource().start(c)
        self.assertEqual(len(out), 1 + 8)
        for o in out:
            d = o.to_dict()
            self.assertEqual(d["schema"], "observation/1")
            for v in d["values"].values():
                self.assertIn(v["provenance"], ("observed", "calculated", "modeled", "predicted", "inferred", "external"))

    def test_without_decoder_files_nothing_is_invented(self):
        c, _ = self.ctx(SITE)
        obs = AdsbSource().cycle(c, AdsbReference({"aircraft_json_1090": str(FIX / "none-1090.json"),
                                                   "aircraft_json_978": ""}), SITE, int(NOW * 1e9))
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0].values["references_accepted"]["value"], 0)

    def test_fixtures_are_marked_synthetic(self):
        for f in ("aircraft-1090.json", "aircraft-978.json"):
            self.assertIn("SYNTHETIC", json.loads((FIX / f).read_text(encoding="utf-8"))["comment"])


if __name__ == "__main__":
    unittest.main()
