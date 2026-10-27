"""reference-broadcast-towers: the cache builder, the checks, geometry, bounds, privacy and the source.

Fixtures are synthetic (fixtures/*-synthetic.csv and the cache built from them), around the US
Naval Observatory example site. No network, no SDR.
"""

import contextlib
import io
import json
import math
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from gps_time_pi.modkit import ModuleContext, Transmitter
from reference_broadcast_towers import build_cache, cache, fetch
from reference_broadcast_towers.geometry import C, slant_range
from reference_broadcast_towers.reference import (REFRACTIVITY, TowerReference, radio_horizon_m, site_frame)
from reference_broadcast_towers.source import EXAMPLE_SITE, FIXTURE_CACHE, TowerSource

FIX = Path(__file__).resolve().parents[1] / "fixtures"
SITE = dict(EXAMPLE_SITE)
CSV_FM = (FIX / "fm-synthetic.csv").read_text(encoding="utf-8")
CSV_TV = (FIX / "tv-synthetic.csv").read_text(encoding="utf-8")
CSV_NOAA = (FIX / "noaa-synthetic.csv").read_text(encoding="utf-8")
NOW_NS = int(1_793_000_000 * 1e9)


def one_tower(**kw):
    t = {"id": "FM:1:90000", "service": "FM", "callsign": "SYNX", "facility_id": "1", "frequency_hz": 90e6,
         "bandwidth_hz": 200e3, "channel": None, "lat": SITE["lat"] + 0.1, "lon": SITE["lon"], "datum": "NAD83",
         "rc_amsl_m": 300.0, "haat_m": 200.0, "erp_kw": 10.0, "status": "LIC", "record_date": "2026-01-01",
         "source": "test"}
    t.update(kw)
    return {"format": cache.FORMAT, "built_utc": "2026-10-01T00:00:00+00:00", "towers": [t]}


def ref_for(doc, **config):
    return TowerReference(config, loader=lambda path: (doc, None))


class TestCacheBuild(unittest.TestCase):
    def build(self):
        return cache.build([("FM", "fm.csv", CSV_FM), ("ATSC", "tv.csv", CSV_TV), ("NOAA", "nwr.csv", CSV_NOAA)],
                           (SITE["lat"], SITE["lon"]), 150, "2026-10-26", "2026-10-26T12:00:00+00:00")

    def test_counts_and_rejections(self):
        doc = self.build()
        kept = {s: sum(1 for t in doc["towers"] if t["service"] == s) for s in cache.SERVICES}
        self.assertEqual(kept, {"FM": 5, "ATSC": 4, "NOAA": 2})
        self.assertEqual(doc["rejected"], {"no_callsign": 1, "no_position": 1, "bad_position": 0,
                                           "bad_frequency": 3, "service_not_used": 0, "duplicate": 1,
                                           "out_of_area": 1})
        self.assertEqual([s["rows_kept"] for s in doc["sources"]], [5, 4, 2])
        self.assertTrue(all(len(s["sha256"]) == 64 for s in doc["sources"]))

    def test_every_position_has_a_source_and_date(self):
        for t in self.build()["towers"]:
            self.assertIn("retrieved 2026-10-26", t["source"])
            self.assertTrue(t["record_date"])

    def test_the_site_is_never_stored(self):
        doc = self.build()
        self.assertEqual((doc["area"]["center_lat"], doc["area"]["center_lon"]), (38.9, -77.1))
        text = json.dumps(doc)
        self.assertNotIn("38.9217", text)
        self.assertNotIn("77.0669", text)

    def test_dms_headers_and_channels(self):
        tv = {t["callsign"]: t for t in self.build()["towers"] if t["service"] == "ATSC"}
        self.assertAlmostEqual(tv["SYN10TV"]["lat"], 38 + 57 / 60, places=6)
        self.assertAlmostEqual(tv["SYN10TV"]["lon"], -(77 + 4 / 60 + 48 / 3600), places=6)
        self.assertEqual(tv["SYN10TV"]["frequency_hz"], 593e6)          # RF 34: 590-596 MHz
        self.assertEqual(tv["SYN12TV"]["frequency_hz"], 189e6)          # RF 9: 186-192 MHz
        self.assertIsNone(tv["SYN13TV"]["datum"])
        self.assertIsNone(tv["SYN13TV"]["rc_amsl_m"])
        for ch, mhz in ((2, 57), (4, 69), (5, 79), (6, 85), (7, 177), (13, 213), (14, 473), (36, 605)):
            self.assertEqual(cache.atsc_center_hz(ch), mhz * 1e6, ch)
        for ch in (1, 37, 51):
            self.assertIsNone(cache.atsc_center_hz(ch))

    def test_the_fixture_cache_rebuilds_identically(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        out = os.path.join(d, "c.json")
        fixture = json.loads(FIXTURE_CACHE.read_text(encoding="utf-8"))
        with contextlib.redirect_stdout(io.StringIO()):
            build_cache.main(["--fm", str(FIX / "fm-synthetic.csv"), "--tv", str(FIX / "tv-synthetic.csv"),
                              "--noaa", str(FIX / "noaa-synthetic.csv"), "--near", "38.9217,-77.0669",
                              "--radius-km", "150", "--retrieved", "2026-10-26", "--built-utc", fixture["built_utc"],
                              "--comment", fixture["comment"], "--out", out])
        self.assertEqual(json.loads(Path(out).read_text(encoding="utf-8")), fixture)
        self.assertIn("SYNTHETIC", fixture["comment"])

    def test_load_problems(self):
        self.assertIn("no tower cache", cache.load(str(FIX / "missing.json"))[1])
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        bad = Path(d, "bad.json")
        bad.write_text('{"format": "other"}', encoding="utf-8")
        self.assertIn("not a tower cache", cache.load(str(bad))[1])
        bad.write_text("{", encoding="utf-8")
        self.assertIn("could not be read", cache.load(str(bad))[1])


class TestReference(unittest.TestCase):
    def test_fixture_listing(self):
        ref = TowerReference({"cache_path": str(FIXTURE_CACHE)})
        txs = ref.list(SITE)
        self.assertEqual(len(txs), 10)
        self.assertEqual(ref.rejected, {"not_licensed": 1, "service_off": 0, "out_of_range": 0})
        self.assertTrue(all("record dated" in t.position_source for t in txs))
        ref.config["services"] = "ATSC"
        self.assertEqual(len(ref.list(SITE)), 4)
        self.assertEqual(ref.rejected["service_off"], 7)
        ref.config.update(services="FM,ATSC,NOAA", max_range_km=10)
        near = ref.list(SITE)
        self.assertEqual(ref.rejected["out_of_range"], 6)
        self.assertEqual(len(near), 4)

    def test_delay_and_bound(self):
        ref = ref_for(one_tower())
        tx = ref.list(SITE)[0]
        pr = ref.predict(SITE, tx, NOW_NS)
        rng = slant_range((SITE["lat"], SITE["lon"], SITE["alt_msl"]), (SITE["lat"] + 0.1, SITE["lon"], 300.0))
        self.assertAlmostEqual(pr["range_m"]["value"], rng, delta=0.1)
        self.assertAlmostEqual(pr["delay_s"]["value"], rng * (1 + REFRACTIVITY) / C, delta=1e-12)
        self.assertAlmostEqual(pr["uncertainty_s"]["value"] * C, math.sqrt(30 ** 2 + 5 ** 2 + (60e-6 * rng) ** 2), places=3)
        self.assertEqual(pr["delay_s"]["provenance"], "calculated")
        self.assertIn("emission timing", pr["uncertainty_s"]["note"])
        self.assertIs(pr["line_of_sight"]["value"], True)
        self.assertEqual(pr["line_of_sight"]["provenance"], "inferred")

    def test_bound_grows_with_missing_datum_height_and_rounding(self):
        exact = ref_for(one_tower())
        b0 = exact.predict(SITE, exact.list(SITE)[0], NOW_NS)["uncertainty_s"]["value"] * C
        loose = ref_for(one_tower(datum=None, rc_amsl_m=None, haat_m=None))
        pr = loose.predict(SITE, loose.list(SITE)[0], NOW_NS)
        self.assertGreater(pr["uncertainty_s"]["value"] * C, math.hypot(100, 300) - 1)
        self.assertGreater(pr["uncertainty_s"]["value"] * C, b0)
        self.assertIsNone(pr["line_of_sight"]["value"])
        hae_only = {"lat": SITE["lat"], "lon": SITE["lon"], "alt_hae": 59.0, "privacy": "exact"}
        self.assertEqual(site_frame(hae_only)[3], "hae")
        b_hae = exact.predict(hae_only, exact.list(hae_only)[0], NOW_NS)["uncertainty_s"]["value"] * C
        self.assertGreater(b_hae, 60)
        rounded = {"lat": 38.9, "lon": -77.1, "alt_msl": 90.0, "privacy": "rounded"}
        r = exact.predict(rounded, exact.list(rounded)[0], NOW_NS)
        self.assertGreater(r["uncertainty_s"]["value"] * C, 5000)
        self.assertIn("site rounding", r["uncertainty_s"]["note"])

    def test_beyond_the_radio_horizon_is_a_lower_bound(self):
        far = ref_for(one_tower(lat=SITE["lat"] + 1.2, haat_m=50.0), max_range_km=300)
        pr = far.predict(SITE, far.list(SITE)[0], NOW_NS)
        self.assertIs(pr["line_of_sight"]["value"], False)
        self.assertIn("lower bound", pr["line_of_sight"]["note"])
        self.assertAlmostEqual(radio_horizon_m(100, 10) / 1000, 54.3, delta=0.2)

    def test_hidden_site_predicts_nothing(self):
        ref = ref_for(one_tower())
        tx = ref.list(None)[0]
        pr = ref.predict(None, tx, NOW_NS)
        self.assertIsNone(pr["delay_s"]["value"])
        self.assertIn("hidden", pr["delay_s"]["note"])
        unknown = Transmitter("FM:zz:1", 1e8, 2e5, {"lat": 0, "lon": 0, "alt_m": 0}, "x")
        self.assertIsNone(ref.predict(SITE, unknown, NOW_NS)["delay_s"]["value"])

    def test_cache_reread_only_when_changed(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        path = os.path.join(d, "c.json")
        Path(path).write_text(json.dumps(one_tower()), encoding="utf-8")
        ref = TowerReference({"cache_path": path})
        self.assertEqual(len(ref.list(SITE)), 1)
        first = ref.doc
        ref.list(SITE)
        self.assertIs(ref.doc, first)
        doc = one_tower()
        doc["towers"].append({**doc["towers"][0], "id": "FM:2:91000", "frequency_hz": 91e6})
        Path(path).write_text(json.dumps(doc), encoding="utf-8")
        os.utime(path, (os.path.getmtime(path) + 5, os.path.getmtime(path) + 5))
        self.assertEqual(len(ref.list(SITE)), 2)


class TestSource(unittest.TestCase):
    def ctx(self, site, **config):
        out = []
        return ModuleContext("reference-broadcast-towers", config=config, emit=out.append, site=lambda: site,
                             clock_ns=lambda: NOW_NS), out

    def test_cycle_with_a_site(self):
        c, _ = self.ctx(SITE, max_per_service=2)
        obs = TowerSource().cycle(c, TowerReference({"cache_path": str(FIXTURE_CACHE)}), SITE, NOW_NS)
        self.assertEqual(len(obs), 1 + 2 + 2 + 2)
        s = obs[0].values
        self.assertEqual(s["references_accepted"]["value"], 10)
        self.assertEqual((s["in_cache_fm"]["value"], s["accepted_fm"]["value"]), (5, 4))
        self.assertIs(s["cache_available"]["value"], True)
        self.assertIs(s["cache_stale"]["value"], False)
        per = obs[1].values
        self.assertEqual(per["lat"]["provenance"], "external")
        self.assertEqual(per["delay_s"]["provenance"], "calculated")
        fm = [o.values["uncertainty_s"]["value"] for o in obs[1:] if o.values["transmitter"]["value"].startswith("FM")]
        self.assertEqual(fm, sorted(fm))

    def test_stale_cache_is_flagged(self):
        c, _ = self.ctx(SITE)
        obs = TowerSource().cycle(c, TowerReference({"cache_path": str(FIXTURE_CACHE)}), SITE,
                                  NOW_NS + int(400 * 86400 * 1e9))
        self.assertIs(obs[0].values["cache_stale"]["value"], True)

    def test_hidden_site_emits_counts_only(self):
        c, _ = self.ctx(None)
        obs = TowerSource().cycle(c, TowerReference({"cache_path": str(FIXTURE_CACHE)}), None, NOW_NS)
        self.assertEqual(len(obs), 1)
        self.assertIs(obs[0].values["site_available"]["value"], False)

    def test_without_a_cache_nothing_is_invented(self):
        c, _ = self.ctx(SITE)
        obs = TowerSource().cycle(c, TowerReference({"cache_path": str(FIX / "none.json")}), SITE, NOW_NS)
        self.assertEqual(len(obs), 1)
        self.assertIs(obs[0].values["cache_available"]["value"], False)
        self.assertIn("no tower cache", obs[0].values["cache_available"]["note"])
        self.assertEqual(obs[0].values["references_accepted"]["value"], 0)

    def test_demo_runs_once_from_the_example_site(self):
        c, out = self.ctx(None, demo=True)
        TowerSource().start(c)
        self.assertEqual(len(out), 1 + 10)
        for o in out:
            d = o.to_dict()
            self.assertEqual(d["schema"], "observation/1")
            for v in d["values"].values():
                self.assertIn(v["provenance"], ("observed", "calculated", "modeled", "predicted", "inferred", "external"))

    def test_fixtures_are_synthetic(self):
        for f in ("fm-synthetic.csv", "tv-synthetic.csv", "noaa-synthetic.csv"):
            calls = [ln.split(",")[0] for ln in (FIX / f).read_text(encoding="utf-8").splitlines()[1:]]
            self.assertTrue(all(c == "" or c.startswith("SYN") for c in calls), f)
        for f in ("fm-fcc-synthetic.txt", "tv-fcc-synthetic.txt"):
            for ln in (FIX / f).read_text(encoding="utf-8").splitlines():
                self.assertTrue(ln.split("|")[1].startswith("SYN"), ln[:20])
                self.assertIn("SYNTHETIC LICENSEE", ln)
        rows = json.loads(NWR_JS[NWR_JS.index("["):].rstrip().rstrip(";"))
        self.assertTrue(all(r["callsign"].startswith("SYN") for r in rows))


FCC_FM_TXT = (FIX / "fm-fcc-synthetic.txt").read_text(encoding="utf-8")
FCC_TV_TXT = (FIX / "tv-fcc-synthetic.txt").read_text(encoding="utf-8")
NWR_JS = (FIX / "nwr-synthetic.js").read_text(encoding="utf-8")


class TestRealFormats(unittest.TestCase):
    """The FCC text output and NOAA's ccl-data.js, in their real layouts (synthetic rows)."""

    def test_detect(self):
        self.assertEqual(cache.detect(FCC_FM_TXT), "fcc")
        self.assertEqual(cache.detect(NWR_JS), "nwr")
        self.assertEqual(cache.detect(CSV_FM), "csv")
        self.assertEqual(cache.detect("\ufeff" + FCC_TV_TXT), "fcc")

    def test_positions_follow_the_fcc_key(self):
        # The FCC key's order: 38 FM fields, 39 TV fields; positions come from the key's names.
        self.assertEqual((len(cache.FCC_FM_KEY), len(cache.FCC_TV_KEY)), (38, 39))
        self.assertEqual(cache.FCC_FM_KEY[cache.FCC_FM["rc_amsl_m"] - 1], "RCAMSL horizontal (meters)")
        self.assertEqual(cache.FCC_TV_KEY[cache.FCC_TV["virtual_channel"] - 1], "DTV Virtual Channel")
        self.assertEqual((cache.FCC_FM["facility_id"], cache.FCC_FM["lat_deg"], cache.FCC_FM["lon_sec"]), (18, 20, 26))
        self.assertEqual((cache.FCC_TV["channel"], cache.FCC_TV["atsc3"], cache.FCC_TV["rc_amsl_m"]), (4, 6, 31))
        # Real lines carry one undocumented trailing identifier: 39 (FM) and 40 (TV) items plus the two ends.
        self.assertEqual({len(ln.split("|")) for ln in FCC_FM_TXT.splitlines()}, {41})
        self.assertEqual({len(ln.split("|")) for ln in FCC_TV_TXT.splitlines()}, {42})

    def test_fm_text(self):
        recs, rej = cache.parse_rows(FCC_FM_TXT, "FM")
        self.assertEqual(rej["service_not_used"], 1)                    # the FX translator
        r = recs[0]
        self.assertEqual((r["callsign"], r["frequency_hz"], r["facility_id"], r["datum"]),
                         ("SYN1FM", 88.5e6, "900001", "NAD83"))
        self.assertEqual((r["erp_kw"], r["haat_m"], r["rc_amsl_m"], r["status"]), (50.0, 180.0, 250.0, "LIC"))
        self.assertAlmostEqual(r["lat"], 38.95, places=4)
        self.assertAlmostEqual(r["lon"], -77.08, places=4)

    def test_tv_text(self):
        recs, rej = cache.parse_rows(FCC_TV_TXT, "ATSC")
        self.assertEqual((rej["service_not_used"], rej["bad_frequency"]), (2, 1))   # DTS, analog LPT; RF 50
        tv = {r["callsign"]: r for r in recs}
        self.assertEqual(sorted(tv), ["SYN20TV", "SYN21TV", "SYN22LD"])
        self.assertEqual((tv["SYN20TV"]["channel"], tv["SYN20TV"]["frequency_hz"], tv["SYN20TV"]["virtual_channel"]),
                         (34, 593e6, "20"))
        self.assertFalse(tv["SYN20TV"]["atsc3"])
        self.assertTrue(tv["SYN21TV"]["atsc3"])
        self.assertIsNone(tv["SYN22LD"]["virtual_channel"])
        self.assertEqual(tv["SYN22LD"]["haat_m"], 0.0)

    def test_nwr_js(self):
        recs, rej = cache.parse_rows(NWR_JS, "NOAA")
        self.assertEqual(rej["bad_frequency"], 1)                        # 162.600 is not an NWR channel
        self.assertEqual([(r["callsign"], r["status"], r["datum"], r["rc_amsl_m"]) for r in recs],
                         [("SYNWX1", "NORMAL", None, None), ("SYNWX2", "OUT OF SERVICE", None, None)])

    def build(self):
        return cache.build([("FM", "fm.txt", FCC_FM_TXT), ("ATSC", "tv.txt", FCC_TV_TXT), ("NOAA", "nwr.js", NWR_JS)],
                           (SITE["lat"], SITE["lon"]), 150, "2026-10-27", "2026-10-27T00:00:00+00:00")

    def test_the_licence_wins_a_duplicate(self):
        doc = self.build()
        fm = [t for t in doc["towers"] if t["callsign"] == "SYN2FM"]
        self.assertEqual([t["status"] for t in fm], ["LIC"])           # the permit came first
        self.assertEqual(doc["rejected"]["duplicate"], 1)
        self.assertEqual(doc["rejected"]["out_of_area"], 1)
        self.assertEqual([s["rows_kept"] for s in doc["sources"]], [3, 3, 2])
        self.assertEqual([s["format"] for s in doc["sources"]], ["fcc", "fcc", "nwr"])

    def test_reference_uses_licensed_and_in_service_only(self):
        ref = ref_for(self.build())
        txs = ref.list(SITE)
        ids = {t.id for t in txs}
        self.assertIn("NOAA:SYNWX1:162550", ids)
        self.assertNotIn("NOAA:SYNWX2:162475", ids)                     # out of service
        self.assertEqual(ref.rejected["not_licensed"], 1)
        tx = next(t for t in txs if t.id.startswith("ATSC:900022"))
        self.assertIsNone(ref.predict(SITE, tx, NOW_NS)["line_of_sight"]["value"])   # HAAT 0: unknown


class FakeFetch:
    def __init__(self, bodies):
        self.bodies, self.urls = bodies, []

    def __call__(self, url):
        self.urls.append(url)
        body = self.bodies[url]
        if isinstance(body, Exception):
            raise body
        return body


def national(key):
    """A download big enough to pass the size check: the fixture rows repeated."""
    if key == "noaa":
        return NWR_JS.encode() + b"/*" + b'"callsign"' * 200 + b"*/"
    return ((FCC_FM_TXT if key == "fm" else FCC_TV_TXT) * 300).encode()


class TestFetch(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.now = datetime(2026, 10, 27, 1, 0, tzinfo=timezone.utc)
        self.urls = {k: url for k, (_s, _n, url) in fetch.SOURCES.items()}

    def fetch_all(self):
        return fetch.fetch(self.d, fetcher=FakeFetch({u: national(k) for k, u in self.urls.items()}), now=self.now)

    def test_no_location_in_any_request(self):
        for url in self.urls.values():
            q = parse_qs(urlparse(url).query, keep_blank_values=True)
            self.assertFalse({"dlat2", "dlon2", "mlat2", "slat2", "dist", "lat", "lon"} & set(q), url)
            self.assertEqual(urlparse(url).scheme, "https")

    def test_downloads_and_manifest_then_build(self):
        manifest, problems = self.fetch_all()
        self.assertEqual(problems, [])
        self.assertEqual(sorted(manifest["files"]), ["fm", "noaa", "tv"])
        m = manifest["files"]["fm"]
        self.assertEqual((m["records"], m["retrieved_utc"]), (6 * 300, "2026-10-27T01:00:00+00:00"))
        out = os.path.join(self.d, "towers-cache.json")
        with contextlib.redirect_stdout(io.StringIO()):
            build_cache.main(["--downloads", self.d, "--near", "38.9217,-77.0669", "--out", out])
        doc = json.loads(Path(out).read_text(encoding="utf-8"))
        self.assertEqual({s["retrieved"] for s in doc["sources"]}, {"2026-10-27"})
        self.assertEqual([s["sha256"] for s in doc["sources"]],
                         [manifest["files"][k]["sha256"] for k in ("fm", "noaa", "tv")])
        self.assertNotIn("38.9217", json.dumps(doc))

    def test_a_failed_or_short_download_keeps_the_previous_file(self):
        self.fetch_all()
        before = Path(self.d, "fm.txt").read_bytes()
        bodies = {self.urls["fm"]: b"<html>Access Denied</html>", self.urls["tv"]: OSError("timed out"),
                  self.urls["noaa"]: national("noaa")}
        manifest, problems = fetch.fetch(self.d, fetcher=FakeFetch(bodies), now=self.now)
        self.assertEqual(len(problems), 2)
        self.assertEqual(Path(self.d, "fm.txt").read_bytes(), before)
        self.assertEqual(manifest["files"]["fm"]["records"], 6 * 300)

    def test_a_changed_download_is_refused(self):
        self.fetch_all()
        Path(self.d, "tv.txt").write_text("|edited", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            build_cache.main(["--downloads", self.d, "--near", "38.9,-77.1", "--out", os.path.join(self.d, "c.json")])


if __name__ == "__main__":
    unittest.main()
