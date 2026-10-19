"""The ~3 s browser round trip (owner's list; rc.9).

Measured on the Pi on 2026-10-19: /api/ping alone answered in about 10 ms, but
/api/almanac took about 15.5 s and /api/references returned 1.1 MB, and the
legacy dashboard asks for the almanac on every 5 s refresh. Requests share one
Python process, so pings waited behind the almanac. These tests pin down the
fixes: the almanac's day-level work is computed once and shared, concurrent
identical requests share one computation, the references payload carries one
server's history, and a ping is answered while an almanac is being computed.
"""

import threading
import time
import unittest
from unittest import mock

from tests import _env  # noqa: F401
from tests.test_location_privacy import PrivacyBase
from gps_time_pi import astro, server


class TestMemo(unittest.TestCase):
    def setUp(self):
        server._MEMO.clear()

    def test_built_once_within_the_ttl(self):
        calls = []
        build = lambda: calls.append(1) or len(calls)       # noqa: E731
        self.assertEqual(server.memo("k", 60, build), 1)
        self.assertEqual(server.memo("k", 60, build), 1)
        self.assertEqual(len(calls), 1)

    def test_rebuilt_after_the_ttl(self):
        calls = []
        build = lambda: calls.append(1) or len(calls)       # noqa: E731
        server.memo("k", 0.0, build)
        server.memo("k", 0.0, build)
        self.assertEqual(len(calls), 2)

    def test_concurrent_callers_share_one_build(self):
        calls, results = [], []
        gate = threading.Event()

        def slow():
            calls.append(1)
            gate.wait(2)
            return "value"
        threads = [threading.Thread(target=lambda: results.append(server.memo("same", 60, slow))) for _ in range(5)]
        for t in threads:
            t.start()
        time.sleep(0.2)
        gate.set()
        for t in threads:
            t.join(5)
        self.assertEqual(len(calls), 1, "five identical requests, one computation")
        self.assertEqual(results, ["value"] * 5)

    def test_a_failed_build_is_not_cached_and_does_not_block(self):
        def boom():
            raise RuntimeError("ephemeris")
        with self.assertRaises(RuntimeError):
            server.memo("x", 60, boom)
        self.assertEqual(server.memo("x", 60, lambda: "ok"), "ok")

    def test_size_is_bounded(self):
        for i in range(server.MEMO_MAX + 20):
            server.memo(("k", i), 60, lambda: i)
        self.assertLessEqual(len(server._MEMO), server.MEMO_MAX)


class TestAlmanacCache(PrivacyBase):
    def test_day_level_parts_are_computed_once(self):
        first = self.almanac()
        n = len(self.sites)
        again = self.almanac()
        self.assertEqual(first["sun"], again["sun"])
        self.assertEqual(len(self.sites), n, "a repeated request computes nothing new")

    def test_different_privacy_mode_is_a_different_entry(self):
        self.almanac()
        n = len(self.sites)
        from gps_time_pi import config
        with mock.patch.object(config, "load", lambda: {"location_display": "rounded"}):
            d = self.almanac()
        self.assertEqual(d["location_display"], "rounded")
        self.assertGreater(len(self.sites), n, "the rounded site is computed separately, never served from the exact one")


class TestPingIsNotHeldUp(unittest.TestCase):
    def test_ping_answers_while_an_almanac_is_computed(self):
        """A slow almanac on one request thread must not stop a ping on another.
        Python threads share one interpreter lock, but a computation that waits
        or yields lets the ping through; with the cache the slow part runs once."""
        import json
        import urllib.request
        from http.server import ThreadingHTTPServer
        server._MEMO.clear()
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.shutdown)
        gate = threading.Event()

        def slow_almanac(qs):
            return server.memo("slow-almanac", 60, lambda: gate.wait(3) or {"available": True})

        def get(path):
            req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers={"Host": "localhost"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())

        with mock.patch.object(server, "almanac_api", slow_almanac):
            t = threading.Thread(target=lambda: get("/api/almanac"))
            t.start()
            time.sleep(0.2)
            t0 = time.monotonic()
            get("/api/ping")
            ping_s = time.monotonic() - t0
            gate.set()
            t.join(5)
        self.assertLess(ping_s, 1.0)


class TestReferencesPayload(unittest.TestCase):
    def test_history_only_for_one_server(self):
        from tests.test_references import Rig, rows, src
        rig = Rig(ntp={})
        for _ in range(30):
            rig.feed(rows(src("192.0.2.1", last="5"), src("192.0.2.2", last="5")), advance=120)
        rep = rig.tracker.report()
        with_history = [r["name"] for r in rep["references"] if r["history"]]
        self.assertEqual(with_history, ["192.0.2.1"], "the first independent server by default")
        self.assertEqual([r["history_points"] for r in rep["references"]], [30, 30])
        other = rig.tracker.report(history_for="192.0.2.2")
        self.assertEqual([r["name"] for r in other["references"] if r["history"]], ["192.0.2.2"])
        self.assertEqual(rig.tracker.report(history_for="nope")["references"][0]["history"], [])

    def test_route_passes_the_choice(self):
        from gps_time_pi import timing_chain
        fake = mock.Mock()
        fake.references.report.return_value = {"ok": True}
        with mock.patch.object(server, "DEMO_MODE", False), mock.patch.object(timing_chain, "service", lambda: fake):
            server.references_payload({"history": ["192.0.2.2"]})
        fake.references.report.assert_called_with("192.0.2.2")


if __name__ == "__main__":
    unittest.main()
