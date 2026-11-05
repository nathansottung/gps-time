"""The live aircraft map (tar1090 on readsb): the page, readsb's data, the station marker by the
privacy mode, the map's own CSP, and the Aviation status. No readsb, network or root needed: the
page and readsb's files are written to temp directories, and the real server serves them.
"""
import base64
import hashlib
import http.client
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401  (sets GTP_* paths before gps_time_pi is imported)
from gps_time_pi import config, security, server, tar1090

USNO = {"lat": 38.92170123, "lon": -77.06690456, "alt_msl": 92.0}
INLINE = b'let databaseFolder = "db-2ab834a";'
INDEX = b"<!DOCTYPE html><html><head><script>" + INLINE + b"</script><script src=\"script.js\"></script></head></html>"


class MapBase(unittest.TestCase):
    mode = "exact"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gps-time-tar1090-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.html = self.tmp / "html"
        self.data = self.tmp / "readsb"
        self.html.mkdir()
        self.data.mkdir()
        self.sky_html = self.tmp / "sky-html"
        self.sky_data = self.tmp / "skyaware978"
        self.sky_html.mkdir()
        self.sky_data.mkdir()
        (self.sky_html / "index.html").write_bytes(b"<!DOCTYPE html><html><script>var a = 1;</script></html>")
        (self.sky_data / "aircraft.json").write_text(json.dumps({"now": 1, "aircraft": [{"hex": "~a00001"}]}))
        (self.sky_data / "receiver.json").write_text(json.dumps({"version": "skyaware978", "lat": 5.0, "lon": 6.0}))
        (self.html / "index.html").write_bytes(INDEX)
        (self.html / "script.js").write_text("console.log(1)")
        (self.tmp / "secret.txt").write_text("outside")
        (self.data / "aircraft.json").write_text(json.dumps({"now": 1, "aircraft": [{"hex": "a1b2c3"}, {"hex": "abc123"}]}))
        (self.data / "history_0.json").write_text("{}")
        (self.data / "receiver.json").write_text(json.dumps({"version": "readsb", "refresh": 1000, "history": 1,
                                                              "lat": 1.0, "lon": 2.0}))
        cfg_path = self.tmp / "config.json"
        cfg_path.write_text(json.dumps({"location_display": self.mode, "site": USNO}))
        for p in (mock.patch.object(tar1090, "HTML_DIR", str(self.html)),
                  mock.patch.object(tar1090, "DATA_DIR", str(self.data)),
                  mock.patch.object(tar1090, "SKY_HTML_DIR", str(self.sky_html)),
                  mock.patch.object(tar1090, "SKY_DATA_DIR", str(self.sky_data)),
                  mock.patch.object(server, "DEMO_MODE", False),
                  mock.patch.object(config, "_PATH", str(cfg_path)),
                  mock.patch.object(config, "_CACHE", None),
                  mock.patch.dict(os.environ, {"GTP_ALLOWED_HOSTS": "gpstime.example.lan"})):
            p.start()
            self.addCleanup(p.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=10)
        self.addCleanup(self.conn.close)

    def get(self, path, host=None, method="GET"):
        self.conn.request(method, path, headers={"Host": host or f"127.0.0.1:{self.httpd.server_address[1]}"})
        r = self.conn.getresponse()            # one kept-alive connection for every request
        return r.status, dict(r.getheaders()), r.read()


class TestSkyaware978(MapBase):
    def test_the_978_page_and_its_data(self):
        status, h, body = self.get("/skyaware978/")
        self.assertEqual(status, 200)
        self.assertIn(b"var a = 1;", body)
        self.assertIn("script-src 'self' 'sha256-", h["Content-Security-Policy"])
        status, _, body = self.get("/skyaware978/data/aircraft.json")
        self.assertEqual((status, json.loads(body)["aircraft"][0]["hex"]), (200, "~a00001"))
        self.assertEqual(self.get("/skyaware978")[0], 301)
        self.assertEqual(self.get("/skyaware978/../readsb/aircraft.json")[0], 404)
        self.assertEqual(self.get("/skyaware978/", host="evil.example")[0], 403)

    def test_its_receiver_json_follows_the_privacy_mode(self):
        r = json.loads(self.get("/skyaware978/data/receiver.json")[2])
        self.assertEqual((r["lat"], r["lon"]), (USNO["lat"], USNO["lon"]))        # not skyaware978's own
        config.save({**config.load(), "location_display": "hidden"})
        r = json.loads(self.get("/skyaware978/data/receiver.json")[2])
        self.assertNotIn("lat", r)

    def test_not_installed_says_how(self):
        (self.sky_html / "index.html").unlink()
        status, _, body = self.get("/skyaware978/")
        self.assertEqual(status, 503)
        self.assertIn(b"GTP_SDR_978_SERIAL", body)

    def test_the_app_keeps_the_strict_csp(self):
        self.get("/skyaware978/")
        _, h, _ = self.get("/api/aircraft-map")
        self.assertEqual(h["Content-Security-Policy"], security.CSP_STRICT)


class TestHead(MapBase):
    def test_head_answers_like_get_without_a_body(self):
        for path in ("/tar1090/", "/tar1090/script.js", "/skyaware978/", "/api/aircraft-map", "/nope"):
            with self.subTest(path):
                gs, gh, gbody = self.get(path)
                hs, hh, hbody = self.get(path, method="HEAD")
                self.assertEqual(hs, gs)
                self.assertEqual(hbody, b"")
                self.assertNotEqual(hs, 501)
                if gs == 200 and "Content-Length" in gh and "json" not in gh.get("Content-Type", ""):
                    self.assertEqual(hh["Content-Length"], gh["Content-Length"])
                self.assertIn("Content-Security-Policy", hh)
        # The connection still works after a HEAD (no body was left on it).
        self.assertEqual(self.get("/tar1090/script.js")[2], b"console.log(1)")


class TestPausedOnlyForItsDongle(MapBase):
    def test_the_web_sdr_on_the_978_dongle_pauses_the_978_map_only(self):
        from gps_time_pi import sdr, websdr
        with mock.patch.object(websdr, "unit_active", return_value=True), mock.patch.object(sdr, "websdr_band", return_value="978"):
            st = json.loads(self.get("/api/aircraft-map")[2])
        self.assertNotEqual(st["state"], "paused")
        self.assertEqual(st["uat"]["state"], "paused")
        with mock.patch.object(websdr, "unit_active", return_value=True), mock.patch.object(sdr, "websdr_band", return_value="1090"):
            st = json.loads(self.get("/api/aircraft-map")[2])
        self.assertEqual(st["state"], "paused")
        self.assertNotEqual(st["uat"]["state"], "paused")
        with mock.patch.object(websdr, "unit_active", return_value=True), mock.patch.object(sdr, "websdr_band", return_value=None):
            st = json.loads(self.get("/api/aircraft-map")[2])
        self.assertNotIn("paused", (st["state"], st["uat"]["state"]))


class TestPageAndData(MapBase):
    def test_the_page_and_its_files(self):
        status, h, body = self.get("/tar1090/")
        self.assertEqual(status, 200)
        self.assertEqual(body, INDEX)
        self.assertTrue(h["Content-Type"].startswith("text/html"))
        self.assertEqual(self.get("/tar1090/script.js")[0], 200)
        status, h, _ = self.get("/tar1090")
        self.assertEqual((status, h.get("Location")), (301, "/tar1090/"))

    def test_nothing_outside_the_page_or_readsb_files(self):
        for path in ("/tar1090/../secret.txt", "/tar1090/%2e%2e/secret.txt", "/tar1090/data/../../secret.txt",
                     "/tar1090/data/stats.json", "/tar1090/data/receiver.json.bak", "/tar1090/data/history_x.json",
                     "/tar1090/missing.js", "/tar1090/chunks/chunks.json"):
            self.assertEqual(self.get(path)[0], 404, path)

    def test_readsb_data_is_served_as_it_is(self):
        status, h, body = self.get("/tar1090/data/aircraft.json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["aircraft"][0]["hex"], "a1b2c3")
        self.assertEqual(h["Cache-Control"], "no-store")
        self.assertEqual(self.get("/tar1090/data/history_0.json")[0], 200)

    def test_the_map_page_has_its_own_csp_and_nothing_else_does(self):
        _, h, _ = self.get("/tar1090/")
        csp = h["Content-Security-Policy"]
        sha = "'sha256-" + base64.b64encode(hashlib.sha256(INLINE).digest()).decode() + "'"
        script = next(d for d in csp.split("; ") if d.startswith("script-src"))
        self.assertEqual(script, f"script-src 'self' {sha}")             # no 'unsafe-inline' for scripts
        self.assertIn("frame-ancestors 'none'", csp)
        # The same kept-alive connection: the next answers go back to the strict policy.
        for path in ("/tar1090/data/aircraft.json", "/tar1090/script.js", "/api/aircraft-map"):
            _, h, _ = self.get(path)
            self.assertEqual(h["Content-Security-Policy"], security.CSP_STRICT, path)

    def test_the_gzipped_database_goes_out_as_content_encoding_gzip(self):
        import gzip
        db = self.html / "db-2ab834a"
        db.mkdir()
        (db / "A.js").write_bytes(gzip.compress(b'{"a1b2c3":["N1"]}'))
        (db / "plain.js").write_text("x")
        status, h, body = self.get("/tar1090/db-2ab834a/A.js")
        self.assertEqual((status, h.get("Content-Encoding")), (200, "gzip"))
        self.assertEqual(gzip.decompress(body), b'{"a1b2c3":["N1"]}')
        self.assertIsNone(self.get("/tar1090/db-2ab834a/plain.js")[1].get("Content-Encoding"))
        self.assertIsNone(self.get("/tar1090/script.js")[1].get("Content-Encoding"))

    def test_lan_only_like_the_rest(self):
        self.assertEqual(self.get("/tar1090/", host="evil.example")[0], 403)

    def test_not_installed_says_how(self):
        (self.html / "index.html").unlink()
        status, _, body = self.get("/tar1090/")
        self.assertEqual(status, 503)
        self.assertIn(b"GTP_SDR_1090_SERIAL", body)


class TestStationMarker(MapBase):
    def receiver(self):
        status, _, body = self.get("/tar1090/data/receiver.json")
        self.assertEqual(status, 200)
        return json.loads(body)

    def set_mode(self, mode):
        config.save({**config.load(), "location_display": mode})

    def test_exact_mode_shows_the_survey_position_not_readsbs(self):
        r = self.receiver()
        self.assertEqual((r["lat"], r["lon"]), (USNO["lat"], USNO["lon"]))
        self.assertEqual(r["history"], 1)                                   # the rest kept

    def test_rounded_mode_rounds(self):
        self.set_mode("rounded")
        r = self.receiver()
        self.assertEqual((r["lat"], r["lon"]), (38.9, -77.1))

    def test_hidden_mode_has_no_marker_at_all(self):
        self.set_mode("hidden")
        body = self.get("/tar1090/data/receiver.json")[2]
        r = json.loads(body)
        self.assertNotIn("lat", r)
        self.assertNotIn("lon", r)
        self.assertNotIn(b"38.9", body)
        self.assertNotIn(b"77.0", body)
        st = json.loads(self.get("/api/aircraft-map")[2])
        self.assertFalse(st["station_marker"])

    def test_no_receiver_file_still_answers_without_a_position_from_readsb(self):
        (self.data / "receiver.json").unlink()
        self.set_mode("hidden")
        self.assertNotIn("lat", self.receiver())


class TestStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_live_stale_paused_and_no_data(self):
        cfg = {"location_display": "exact", "site": USNO}
        self.assertEqual(tar1090.status(cfg, data_dir=str(self.tmp))["state"], "no_data")
        f = self.tmp / "aircraft.json"
        f.write_text(json.dumps({"aircraft": [{}, {}, {}]}))
        now = time.time()
        st = tar1090.status(cfg, data_dir=str(self.tmp), now=now)
        self.assertEqual((st["state"], st["aircraft"]), ("live", 3))
        self.assertTrue(st["station_marker"])
        self.assertEqual(tar1090.status(cfg, data_dir=str(self.tmp), now=now + 120)["state"], "stale")
        # The web SDR has the dongle: tracking is paused, whatever the file says.
        self.assertEqual(tar1090.status(cfg, websdr_active=True, data_dir=str(self.tmp), now=now)["state"], "paused")
        self.assertFalse(tar1090.status({"location_display": "hidden", "site": USNO}, data_dir=str(self.tmp))["station_marker"])
        self.assertFalse(tar1090.status({"location_display": "exact"}, data_dir=str(self.tmp))["station_marker"])


class TestUnits(unittest.TestCase):
    def test_readsb_gets_no_position_and_the_web_sdr_pauses_it(self):
        root = Path(__file__).resolve().parents[1] / "system"
        readsb = (root / "gps-time-readsb.service").read_text(encoding="utf-8")
        start = next(ln for ln in readsb.splitlines() if ln.startswith("ExecStart="))
        self.assertNotIn("--lat", start)
        self.assertNotIn("--lon", start)
        self.assertIn("--write-json /run/readsb", readsb)
        web = (root / "gps-time-websdr.service").read_text(encoding="utf-8")
        # Which decoder pauses depends on the web SDR's dongle: the drop-in scripts/websdr.sh writes.
        self.assertNotRegex(web, r"(?m)^Conflicts=")
        self.assertIn("websdr-handoff", web)
        self.assertIn("GTP_WEBSDR_SHARES", (root / "websdr-handoff").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
