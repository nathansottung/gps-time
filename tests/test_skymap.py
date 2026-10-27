"""The learned sky-obstruction map (skymap.py), its losses (§11), the capability
record (capability.py) and the routes. No gpsd: satellites are synthetic."""

import base64
import hashlib
import json
import os
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import capability, config, demo, gps, server, skymap


class Clock:
    def __init__(self):
        self.t = 1_790_000_000.0       # wall time (UTC seconds)
        self.m = 1000.0                # monotonic

    def step(self, s):
        self.t += s
        self.m += s


def sat(i, az, el, snr, gnss="GPS", used=True):
    return {"id": i, "gnss": gnss, "az": az, "el": el, "snr": snr, "used": used}


def west_blocked_sky(minute):
    """One report: satellites on a lattice of directions; the west below 30° is 12 dB weaker and
    often untracked."""
    out, i = [], 0
    for az in range(5, 360, 10):
        for el in (7, 12, 17, 22, 27, 42, 57):
            i += 1
            cn0 = 30 + 0.3 * el
            if 240 <= az <= 310 and el < 30:
                cn0 -= 12
                if (minute + i) % 3 == 0:
                    cn0 = 0
            out.append(sat(i, az, el, cn0))
    return out


class MapBase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gtp-sky-")
        self.path = os.path.join(self.dir, skymap.FILE_NAME)
        self.clock = Clock()
        self.mode = "exact"
        self.map = self.new()

    def new(self):
        return skymap.SkyMap(path=self.path, clock=lambda: self.clock.t, monotonic=lambda: self.clock.m,
                             mode=lambda: self.mode)

    def learn(self, minutes=60, days=2):
        for d in range(days):
            for k in range(minutes):
                self.map.observe(west_blocked_sky(k))
                self.clock.step(60)
            self.clock.step(86400 - minutes * 60)


class TestCells(MapBase):
    def test_cell_edges(self):
        self.assertEqual(skymap.cell_of(0, 0), (0, 0))
        self.assertEqual(skymap.cell_of(359.9, 89.9), (35, 17))
        self.assertEqual(skymap.cell_of(360, 90), (0, 17))
        for az, el in ((None, 10), (10, None), (10, -1), (10, 91), (float("nan"), 10)):
            self.assertIsNone(skymap.cell_of(az, el))

    def test_one_sample_a_minute_from_fresh_reports(self):
        sky = [sat(1, 100, 40, 40)]
        for _ in range(12):                     # the collector's 5 s reports
            self.map.observe(sky)
            self.clock.step(5)
        self.assertEqual(self.map.samples, 1)
        self.assertEqual(self.map.cells[(10, 8)][:3], [1, 1, 1])
        self.map.observe(sky)
        self.assertEqual(self.map.samples, 2)

    def test_untracked_listed_satellites_count_but_carry_no_cn0(self):
        self.map.observe([sat(1, 100, 40, 0, used=False), sat(2, 100, 40, 0, used=False)])
        self.assertEqual(self.map.cells[(10, 8)], [2, 0, 0, 0, 0])
        self.assertTrue(self.map.untracked_seen)

    def test_hidden_mode_collects_nothing(self):
        self.mode = "hidden"
        self.map.observe([sat(1, 100, 40, 40)])
        self.assertEqual(self.map.cells, {})
        self.assertEqual(skymap.payload(self.map, "hidden"),
                         {"available": False, "reason": skymap.HIDDEN_REASON, "location_display": "hidden"})


class TestInference(MapBase):
    def test_sectors_from_a_learned_map(self):
        self.learn()
        r = skymap.payload(self.map, "exact")
        self.assertEqual(r["summary"]["state"], "learned")
        self.assertEqual(r["summary"]["days"], 2)
        sectors = {s["sector"]: s for s in r["sectors"]}
        self.assertEqual(sectors["W"]["state"], "obstructed")
        self.assertEqual(sectors["W"]["text"], "Expected obstruction below ~30°")
        self.assertEqual(sectors["E"]["state"], "clear")
        self.assertEqual(sectors["E"]["text"], "Mostly clear")
        west = next(c for c in r["cells"] if c["az0"] == 270 and c["el0"] == 20)
        self.assertEqual(west["class"], "blocked")
        self.assertLess(west["delta_db"], -8)
        self.assertTrue(all(s["provenance"] == "inferred" for s in r["sectors"]))
        self.assertNotIn("jam", json.dumps(r).lower())
        self.assertNotIn("spoof", json.dumps(r).lower())

    def test_not_enough_data_is_unknown_never_a_guess(self):
        self.map.observe(west_blocked_sky(0))
        r = self.map.report()
        self.assertEqual(r["summary"]["state"], "learning")
        self.assertTrue(all(c["class"] == "unknown" for c in r["cells"]))
        self.assertTrue(all(s["state"] == "unknown" and s["text"] == "Not enough data" for s in r["sectors"]))
        self.assertIsNone(r["summary"]["clear_pct"])

    def test_a_uniformly_weak_sky_is_not_called_blocked(self):
        for k in range(30):
            self.map.observe([sat(i, az, 20, 22) for i, az in enumerate(range(5, 360, 10))])
            self.clock.step(60)
        self.assertTrue(all(c["class"] == "clear" for c in self.map.report()["cells"]))

    def test_cell_cap_halves_the_counters(self):
        self.map.cells[(10, 8)] = [skymap.CELL_CAP - 1.0, 10.0, 10.0, 400.0, 16000.0]
        self.map.observe([sat(1, 100, 40, 40)])
        self.assertEqual(self.map.cells[(10, 8)], [skymap.CELL_CAP / 2, 5.5, 5.5, 220.0, 8800.0])


class TestLosses(MapBase):
    def lose(self, keep, lost):
        self.map.observe(keep + lost)
        self.clock.step(5)
        self.map.observe(keep)
        return self.map.report()["losses"]

    def test_loss_in_a_blocked_sector_is_expected(self):
        self.learn()
        out = self.lose([], [sat(900, 275, 22, 20)])
        self.assertEqual(out["recent"][0]["class"], "EXPECTED")
        self.assertIn("expected environmental loss", out["recent"][0]["note"])
        self.assertEqual(out["counts"]["EXPECTED"], 1)

    def test_loss_in_a_clear_sector_is_not_explained_low_is_set_unmapped_unknown(self):
        self.learn()
        self.lose([], [sat(901, 95, 42, 44)])
        self.lose([], [sat(902, 95, 3, 30)])
        self.lose([], [sat(903, 95, 87, 44)])          # no data at the zenith
        kinds = [x["class"] for x in self.map.report()["losses"]["recent"]]
        self.assertEqual(kinds, ["UNKNOWN", "SET", "NOT EXPLAINED"])

    def test_untracked_now_counts_as_lost_and_a_gap_compares_nothing(self):
        self.learn()
        self.map.observe([sat(904, 275, 22, 20)])
        self.clock.step(5)
        self.map.observe([sat(904, 275, 22, 0)])
        self.assertEqual(self.map.loss_counts["EXPECTED"], 1)
        self.map.observe([sat(905, 275, 22, 20)])
        self.clock.step(skymap.LOSS_GAP_S + 1)
        self.map.observe([])
        self.assertEqual(self.map.loss_counts["EXPECTED"], 1)

    def test_sky_wide_drop_is_flagged_without_a_cause(self):
        high = [sat(10 + i, az, 50, 45) for i, az in enumerate((10, 100, 190, 280))]
        self.map.observe(high)
        self.clock.step(5)
        self.map.observe([{**s, "snr": 30} for s in high])
        sw = self.map.report()["sky_wide"]
        self.assertEqual(sw["count"], 1)
        self.assertEqual(sw["recent"][0]["quadrants"], 4)
        self.assertIn("does not establish a cause", sw["recent"][0]["note"])
        # one direction only: not sky-wide (after a gap, so the first set isn't compared)
        self.clock.step(skymap.LOSS_GAP_S + 1)
        same = [sat(20 + i, 100 + i, 50, 45) for i in range(4)]
        self.map.observe(same)
        self.clock.step(5)
        self.map.observe([])
        self.assertEqual(self.map.report()["sky_wide"]["count"], 1)


class TestFile(MapBase):
    def test_hourly_flush_reload_and_nothing_when_unchanged(self):
        self.learn(minutes=30, days=1)
        self.assertFalse(os.path.exists(self.path))          # the first hour is in RAM only
        self.map._last_flush -= skymap.FLUSH_INTERVAL_S
        self.clock.step(60)
        self.map.observe(west_blocked_sky(0))
        self.assertTrue(os.path.exists(self.path))
        self.assertFalse(self.map.flush())                    # unchanged: no write
        again = self.new()
        self.assertEqual(again.cells, {k: [round(x, 1) for x in v] for k, v in self.map.cells.items()})
        self.assertEqual(again.days, self.map.days)

    def test_the_file_is_small_and_holds_no_position_or_time_of_day(self):
        self.learn(minutes=20, days=3)
        self.map.flush()
        text = Path(self.path).read_text(encoding="utf-8")
        self.assertLess(len(text), 64 * 1024)
        doc = json.loads(text)
        self.assertEqual(set(doc), {"format", "az_step", "el_step", "note", "written_utc", "samples",
                                    "untracked_seen", "days", "cells"})
        self.assertNotIn("lat", text.replace("format", ""))
        self.assertLessEqual(len(doc["cells"]), skymap.N_AZ * skymap.N_EL)

    def test_an_unreadable_file_is_set_aside(self):
        for bad in ("not json", json.dumps({"format": "other"}), " " * (skymap.MAX_FILE_BYTES + 1),
                    json.dumps({"format": skymap.FORMAT, "az_step": 10, "el_step": 5, "cells": {"99,0": [1, 1, 1, 1, 1]}})):
            with self.subTest(bad=bad[:20]):
                Path(self.path).write_text(bad, encoding="utf-8")
                m = self.new()
                self.assertEqual(m.cells, {})
                self.assertFalse(os.path.exists(self.path))
                self.assertIn("set aside", m.problems[0])


class TestCapability(MapBase):
    SITE = {"lat": 38.9217, "lon": -77.0669}

    def rec(self, cfg, key_path=None):
        return capability.record(cfg, version="1.6.0", status={"code": "GPS_PPS", "source": "PPS"},
                                 receiver={"driver": "u-blox", "firmware": "x"}, site=self.SITE, sky=self.map,
                                 sdr={"installed": True, "dongles": [{"role": "1090 MHz", "serial": "00001090"}]},
                                 key_path=key_path or os.path.join(self.dir, "none.pub"))

    def test_no_exact_position_ever(self):
        exact = self.rec({"location_display": "exact"})
        self.assertEqual((exact["location"]["lat"], exact["location"]["lon"]), (None, None))
        self.assertNotIn("38.92", json.dumps(exact))
        rounded = self.rec({"location_display": "rounded"})
        self.assertEqual((rounded["location"]["lat"], rounded["location"]["lon"]), (38.9, -77.1))
        hidden = self.rec({"location_display": "hidden"})
        self.assertIsNone(hidden["location"]["lat"])
        self.assertNotIn("00001090", json.dumps(exact))          # roles only, never a serial

    def test_sky_quality_is_opt_in_and_never_in_hidden_mode(self):
        self.learn()
        self.assertIsNone(self.rec({"location_display": "exact"})["sky_quality"])
        on = self.rec({"location_display": "exact", "sky_quality_share": True})["sky_quality"]
        self.assertEqual(on["state"], "learned")
        self.assertEqual({s["sector"]: s["state"] for s in on["sectors"]}["W"], "obstructed")
        self.assertNotIn("cells", on)
        hidden = self.rec({"location_display": "hidden", "sky_quality_share": True})
        self.assertIsNone(hidden["sky_quality"])
        self.assertIn("hidden", hidden["sky_quality_note"])

    def test_station_id_from_the_public_key(self):
        raw = bytes(range(32))
        pub = os.path.join(self.dir, "station-key.pub")
        Path(pub).write_text(base64.b64encode(raw).decode() + "\n", encoding="ascii")
        self.assertEqual(self.rec({}, key_path=pub)["station_id"], "ed25519:" + hashlib.sha256(raw).hexdigest())
        self.assertIsNone(self.rec({})["station_id"])

    def test_diagnostic_lines(self):
        self.learn()
        self.assertEqual(skymap.diagnostic_lines(self.map, {}), [
            "sky quality: not included (off (opt-in: POST /api/setting {\"sky_quality_share\": true}))"])
        lines = skymap.diagnostic_lines(self.map, {"sky_quality_share": True})
        self.assertTrue(lines[0].startswith("sky quality (inferred): learned, 2 days"))
        self.assertIn("  W  obstructed below ~30°", lines)


class TestCollectorHook(unittest.TestCase):
    def test_fresh_sky_reports_reach_listeners_and_a_failing_one_is_ignored(self):
        got = []

        def bad(sats):
            raise RuntimeError("x")
        with mock.patch.object(gps, "_SKY_LISTENERS", []):
            gps.add_sky_listener(bad)
            gps.add_sky_listener(got.append)
            gps.add_sky_listener(got.append)
            gps._notify_sky({"satellites": [{"PRN": 5, "gnssid": 0, "az": 10, "el": 20, "ss": 33, "used": True}]})
            gps._notify_sky({})
        self.assertEqual(got, [[{"id": 5, "gnss": "GPS", "el": 20, "az": 10, "snr": 33, "used": True}]])


class TestHttp(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp(prefix="gtp-sky-http-")
        self.cfg = os.path.join(tmp, "config.json")
        Path(self.cfg).write_text(json.dumps({"location_display": "exact"}))
        for p in (mock.patch.object(config, "_PATH", self.cfg), mock.patch.object(config, "_CACHE", None),
                  mock.patch.object(server, "DEMO_MODE", True)):
            p.start()
            self.addCleanup(p.stop)
        demo._DEMO_SKY.clear()
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        self.base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as r:
            return r.read().decode()

    def post(self, body):
        req = urllib.request.Request(self.base + "/api/setting", data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_routes_follow_the_privacy_mode_and_the_opt_in(self):
        d = json.loads(self.get("/api/sky-obstruction"))
        self.assertTrue(d["available"])
        self.assertEqual({s["sector"]: s["state"] for s in d["sectors"]}["W"], "obstructed")
        cap = json.loads(self.get("/api/capability"))
        self.assertEqual(cap["format"], capability.FORMAT)
        self.assertIsNone(cap["sky_quality"])
        self.assertIn("not included", self.get("/api/diagnostics"))

        self.assertEqual(self.post({"sky_quality_share": "yes"})[0], 400)
        self.assertEqual(self.post({"sky_quality_share": True}), (200, {"ok": True, "sky_quality_share": True}))
        self.assertEqual(json.loads(self.get("/api/capability"))["sky_quality"]["state"], "learned")
        self.assertIn("sky quality (inferred): learned", self.get("/api/diagnostics"))

        self.post({"location_display": "hidden"})
        body = self.get("/api/sky-obstruction")
        self.assertFalse(json.loads(body)["available"])
        self.assertNotIn("az0", body)
        self.assertIsNone(json.loads(self.get("/api/capability"))["sky_quality"])
        self.assertIn("location privacy is hidden", self.get("/api/diagnostics"))


if __name__ == "__main__":
    unittest.main()
