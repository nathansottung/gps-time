"""CHG-001: only genuinely fresh GNSS epochs may advance the site survey.

gpsd is replaced by a scripted fake and the monotonic clock by a manual one,
so these tests need no hardware, network or real waiting.
"""

import json
import os
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

from tests import _env
from gps_time_pi import chrony, config, gps, server

SKY = {"class": "SKY", "tdop": 0.9, "hdop": 1.1,
       "satellites": [{"PRN": 5, "gnssid": 0, "el": 40, "az": 120, "ss": 38, "used": True}]}
NOTHING = ({}, {}, {}, {})


def tpv(epoch_s, lat=39.0, lon=-77.0, mode=3, **extra):
    t = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(epoch_s)) + ".000Z"
    d = {"class": "TPV", "mode": mode, "lat": lat, "lon": lon,
         "altMSL": 100.0, "altHAE": 67.0, "time": t}
    d.update(extra)
    return d


class FakeGpsd:
    """Returns scripted poll results in order, then silence forever."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = 0
        self.lock = threading.Lock()

    def __call__(self, timeout=3.0):
        with self.lock:
            self.calls += 1
            return self.results.pop(0) if self.results else NOTHING


class FreshnessBase(unittest.TestCase):
    T0 = 1_790_000_000  # receiver epoch base (UTC seconds)

    def setUp(self):
        gps.stop_collector()
        self.path = os.path.join(_env.TMP, f"config-{self.id()}.json")
        config._PATH = self.path
        config._CACHE = None
        config._LAST_WRITE = 0.0
        gps._cache.update(tpv={}, tpv_rx=None, sky={}, sky_rx=None,
                          version={}, device={}, polls=0)
        gps._ingest.update(last_epoch=None, last_accept_mono=None, accepted=0,
                           last_reason=None,
                           rejected=dict.fromkeys(gps._REJECT_REASONS, 0))
        del gps._FIXES[:]
        self.clock = [1000.0]
        p = mock.patch.object(gps, "_monotonic", lambda: self.clock[0])
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(gps.stop_collector)

    def fake(self, *results):
        f = FakeGpsd(*results)
        p = mock.patch.object(gps, "_poll", f)
        p.start()
        self.addCleanup(p.stop)
        return f

    def n(self):
        return config.site_stats(config.load())["n"]

    def advance(self, s):
        self.clock[0] += s


class TestReviewedFailure(FreshnessBase):
    """The exact scenario reproduced in the 2026-09-27 review (GPS-001)."""

    def test_silent_gpsd_never_recounts_the_last_fix(self):
        self.fake((tpv(self.T0), SKY, {}, {}))
        self.assertEqual(gps.poll_once(), "accepted")
        self.assertEqual(self.n(), 1)
        ages = []
        for _ in range(5):
            self.advance(61)
            gps.poll_once()                  # collector keeps polling a silent gpsd
            for _ in range(3):
                snap = gps.snapshot()        # repeated snapshot/API reads
            ages.append(snap["data_age_s"])
        self.assertEqual(self.n(), 1)
        self.assertEqual(ages, sorted(ages))
        self.assertGreater(ages[0], 0)
        self.assertAlmostEqual(ages[-1], 305.0)
        self.assertTrue(snap["stale"])
        self.assertIsNone(snap["fix"])
        self.assertIsNone(snap["live"])
        self.assertEqual(snap["last_fix"], "3D")    # still displayable, labeled stale
        self.assertEqual(gps.ingest_status()["rejected_this_session"]["no_tpv"], 5)

    def test_two_distinct_epochs_count_two(self):
        self.fake((tpv(self.T0), SKY, {}, {}), (tpv(self.T0 + 61), SKY, {}, {}))
        gps.poll_once()
        self.advance(61)
        self.assertEqual(gps.poll_once(), "accepted")
        self.assertEqual(self.n(), 2)
        stats = config.site_stats(config.load())
        self.assertEqual((stats["n_fresh"], stats["n_legacy"]), (2, 0))


class TestEpochIdentity(FreshnessBase):
    def test_repeated_identical_epoch_is_rejected(self):
        self.fake(*[(tpv(self.T0), SKY, {}, {})] * 4)
        gps.poll_once()
        for _ in range(3):
            self.advance(61)
            self.assertEqual(gps.poll_once(), "repeat_epoch")
        self.assertEqual(self.n(), 1)

    def test_older_epoch_is_rejected(self):
        self.fake((tpv(self.T0), SKY, {}, {}), (tpv(self.T0 - 30), SKY, {}, {}))
        gps.poll_once()
        self.advance(61)
        self.assertEqual(gps.poll_once(), "older_epoch")
        self.assertEqual(self.n(), 1)

    def test_new_epoch_too_soon_is_rate_limited(self):
        self.fake((tpv(self.T0), SKY, {}, {}), (tpv(self.T0 + 5), SKY, {}, {}))
        gps.poll_once()
        self.advance(5)
        self.assertEqual(gps.poll_once(), "rate_limited")
        self.assertEqual(self.n(), 1)

    def test_invalid_or_non_3d_fixes_are_rejected(self):
        bad = [tpv(self.T0, mode=2), tpv(self.T0, lat=float("nan")),
               tpv(self.T0, lat=95.0), tpv(self.T0, lon=-181.0),
               {k: v for k, v in tpv(self.T0).items() if k != "time"},
               tpv(self.T0, time="garbage")]
        self.fake(*[(b, SKY, {}, {}) for b in bad])
        reasons = []
        for _ in bad:
            self.advance(61)
            reasons.append(gps.poll_once())
        self.assertEqual(reasons, ["no_3d_fix"] + ["invalid"] * 5)
        self.assertEqual(self.n(), 0)

    def test_wall_clock_steps_do_not_affect_spacing(self):
        self.fake((tpv(self.T0), SKY, {}, {}), (tpv(self.T0 + 5), SKY, {}, {}))
        gps.poll_once()
        self.advance(5)                      # only 5 s of monotonic time elapse…
        with mock.patch.object(gps.time, "time", lambda: 9e9):   # …while wall clock jumps
            self.assertEqual(gps.poll_once(), "rate_limited")
        self.assertEqual(self.n(), 1)

    def test_snapshot_never_polls_or_ingests(self):
        f = self.fake((tpv(self.T0), SKY, {}, {}))
        for _ in range(50):
            gps.snapshot()
            gps.observing_site()
        self.assertEqual(f.calls, 0)
        self.assertEqual(self.n(), 0)


class TestConcurrency(FreshnessBase):
    def test_concurrent_polls_count_one_epoch_once(self):
        self.fake(*[(tpv(self.T0), SKY, {}, {})] * 8)
        real = config.update_site

        def slow(*a):
            time.sleep(0.1)              # widen the race window deliberately
            return real(*a)

        with mock.patch.object(config, "update_site", slow):
            threads = [threading.Thread(target=gps.poll_once) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(self.n(), 1)
        self.assertEqual(gps.ingest_status()["rejected_this_session"]["repeat_epoch"], 7)

    def test_concurrent_http_api_reads_do_not_ingest(self):
        """Many simultaneous /api requests must neither poll gpsd nor count."""
        f = self.fake((tpv(self.T0), SKY, {}, {}))
        gps.poll_once()                      # the one real observation
        calls_after_collect = f.calls
        stubs = {"tracking": lambda: {}, "sources": lambda: [], "sourcestats": lambda: "",
                 "clients": lambda: [], "version": lambda: None}
        patches = [mock.patch.object(chrony, k, v) for k, v in stubs.items()]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        url = f"http://127.0.0.1:{httpd.server_address[1]}/api"
        results = []

        def hit():
            with urllib.request.urlopen(url, timeout=10) as r:
                results.append(json.loads(r.read()))

        for _ in range(3):
            self.advance(61)
            threads = [threading.Thread(target=hit) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(len(results), 30)
        self.assertEqual(f.calls, calls_after_collect)
        self.assertEqual(self.n(), 1)
        last = results[-1]
        self.assertEqual(last["survey"]["n"], 1)
        self.assertTrue(last["gps"]["stale"])
        self.assertGreaterEqual(last["gps"]["data_age_s"], 183.0)


class TestCollectorIndependence(FreshnessBase):
    def test_collector_samples_without_any_reader(self):
        epochs = [(tpv(self.T0 + 61 * i), SKY, {}, {}) for i in range(4)]
        f = self.fake(*epochs)

        def tick():                          # each poll also advances the fake clock
            self.advance(61)
            return self.clock[0]

        with mock.patch.object(gps, "_monotonic", tick):
            gps.start_collector(interval=0.01)
            deadline = time.time() + 5
            while f.calls < 6 and time.time() < deadline:
                time.sleep(0.01)
            gps.stop_collector()
        self.assertEqual(self.n(), 4)        # 4 distinct epochs, silence afterwards
        self.assertGreaterEqual(f.calls, 6)

    def test_collector_survives_poll_exceptions(self):
        def boom(timeout=3.0):
            raise RuntimeError("gpsd exploded")

        with mock.patch.object(gps, "_poll", boom):
            t = gps.start_collector(interval=0.01)
            time.sleep(0.1)
            self.assertTrue(t.is_alive())


class TestLegacySurveyPreservation(FreshnessBase):
    def test_existing_survey_is_kept_and_marked_legacy(self):
        legacy = {"lat": 39.0, "lon": -77.0, "n_lat": 5, "m2_lat": 1e-9,
                  "n_lon": 5, "m2_lon": 1e-9, "history": [[1, 2, 0.5, 0.9]]}
        with open(self.path, "w") as fh:
            json.dump({"location_display": "exact", "site": legacy}, fh)
        config._CACHE = None
        before = config.site_stats(config.load())
        self.assertEqual((before["n"], before["n_legacy"], before["n_fresh"]), (5, 5, 0))

        self.fake((tpv(self.T0), SKY, {}, {}))
        gps.poll_once()
        site = config.load()["site"]
        self.assertEqual(site["legacy_samples_before_fresh_gating"], 5)
        self.assertEqual(site["ingest_rule"], config.INGEST_RULE)
        self.assertEqual(site["history"][0], [1, 2, 0.5, 0.9])   # history untouched
        stats = config.site_stats(config.load())
        self.assertEqual((stats["n"], stats["n_legacy"], stats["n_fresh"]), (6, 5, 1))

    def test_pre_survey_plain_mean_counts_as_one_legacy_sample(self):
        with open(self.path, "w") as fh:
            json.dump({"site": {"lat": 39.0, "lon": -77.0}}, fh)
        config._CACHE = None
        self.fake((tpv(self.T0), SKY, {}, {}))
        gps.poll_once()
        stats = config.site_stats(config.load())
        self.assertEqual((stats["n"], stats["n_legacy"], stats["n_fresh"]), (2, 1, 1))


class TestEpochParsing(unittest.TestCase):
    def test_parse_epoch(self):
        self.assertEqual(gps.parse_epoch("1970-01-01T00:00:01.500Z"), 1.5)
        self.assertEqual(gps.parse_epoch("2026-09-20T12:00:00Z"), 1789905600.0)
        for bad in (None, "", "2026-09-20 12:00:00", "2026-13-40T99:00:00Z", 12345):
            self.assertIsNone(gps.parse_epoch(bad))


if __name__ == "__main__":
    unittest.main()
