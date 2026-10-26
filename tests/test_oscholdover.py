"""Oscillator profile: holdover projections (GPS-008), export/import and board binding.

Synthetic bins and a manual clock; no chrony, no hardware, no network.
"""

import json
import os
import shutil
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

from tests import _env  # noqa: F401
from tests.test_admin_auth import AuthBase
from tests.test_oscprofile import daily, series
from gps_time_pi import oscillator as osc
from gps_time_pi import oscprofile as op
from gps_time_pi import server

MINE = {"serial_sha256": "a1b2c3d4e5f60718", "model": "Raspberry Pi 4 Model B Rev 1.2"}
OTHER = {"serial_sha256": "0f0e0d0c0b0a0908", "model": "Raspberry Pi 4 Model B Rev 1.4"}
LINEAR = {"status": "fitted", "terms": [{"name": "a", "value": 10.0}, {"name": "b", "value": -0.3}],
          "temp_ref_c": 50.0, "residual_rms_ppm": 0.002,
          "covers": {"temp_min_c": 40.0, "temp_max_c": 60.0}}


def by_name(h, name):
    return next(p for p in h["projections"] if p["name"] == name)


class TestHoldover(unittest.TestCase):
    def test_simple_projections_at_the_thresholds(self):
        h = op.holdover(None, -2.14, 0.018, None)
        self.assertEqual(h["provenance"], "modeled")
        self.assertEqual(h["thresholds_s"], [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1.0])
        free, trained = by_name(h, "free_running"), by_name(h, "trained_skew")
        # The review's numbers (GPS-008): raw 2.14 ppm reaches 1 s in 5.4 days, 1 µs in 0.47 s.
        self.assertAlmostEqual(free["times_s"][-1] / 86400, 5.41, places=2)
        self.assertAlmostEqual(free["times_s"][0], 0.467, places=3)
        # Trained (skew 0.018 ppm): 1 µs in about 56 s, 1 ms in about 15 h.
        self.assertAlmostEqual(trained["times_s"][0], 55.6, places=1)
        self.assertAlmostEqual(trained["times_s"][3] / 3600, 15.4, places=1)
        self.assertTrue(all(p["provenance"] == "modeled" for p in h["projections"]))
        self.assertIn("not guarantees", h["note"])

    def test_profile_needs_a_fit(self):
        h = op.holdover({"status": "insufficient", "reason": "needs 72 bins"}, 10.0, 0.01, 50.0)
        p = by_name(h, "profile")
        self.assertFalse(p["available"])
        self.assertIn("needs 72 bins", p["reason"])
        self.assertEqual(p["times_s"], [None] * 7)
        self.assertFalse(by_name(op.holdover(None, None, None, None), "free_running")["available"])

    def test_profile_adds_temperature_and_wander(self):
        h = op.holdover(LINEAR, 10.0, 0.008, 50.0, (44.0, 56.0))
        p = by_name(h, "profile")
        self.assertAlmostEqual(p["components_ppm"]["temperature"], 0.3 * 6, places=6)
        self.assertAlmostEqual(p["rate_ppm"], 0.008 + 0.002 + 1.8)
        self.assertAlmostEqual(p["times_s"][0], 1e-6 / (p["rate_ppm"] * 1e-6))
        self.assertFalse(p["extrapolated"])
        self.assertEqual(p["temp_source"], "the last 24 h's temperature range")
        # Without a 24 h range: ±5 °C from now, said so.
        q = by_name(op.holdover(LINEAR, 10.0, 0.008, 50.0), "profile")
        self.assertAlmostEqual(q["components_ppm"]["temperature"], 1.5)
        self.assertIn("assumed ±5 °C", q["temp_source"])

    def test_extrapolation_is_flagged(self):
        p = by_name(op.holdover(LINEAR, 10.0, 0.008, 58.0, (50.0, 64.0)), "profile")
        self.assertTrue(p["extrapolated"])
        self.assertIn("extrapolated", p["caveat"])

    def test_quadratic_vertex_and_aging(self):
        prof = {"status": "fitted", "temp_ref_c": 50.0, "residual_rms_ppm": 0.0,
                "covers": {"temp_min_c": 30.0, "temp_max_c": 70.0},
                "terms": [{"name": "a", "value": 0.0}, {"name": "b", "value": 0.0},
                          {"name": "c", "value": -0.01}, {"name": "d", "value": 0.05}]}
        # f(T) = −0.01 (T − 50)²: from 45 °C the largest change within 45..55 is at the vertex (50 °C)
        p = by_name(op.holdover(prof, 1.0, 0.0, 45.0, (45.0, 55.0)), "profile")
        self.assertAlmostEqual(p["components_ppm"]["temperature"], 0.25)
        self.assertEqual(p["aging_ppm_per_day"], 0.05)
        # With aging the error grows faster than the constant rate alone
        rate_only = 1.0 / (0.25e-6)
        self.assertLess(p["times_s"][-1], rate_only)
        r, a, t = 0.25e-6, 0.05e-6 / 86400, p["times_s"][-1]
        self.assertAlmostEqual(r * t + a * t * t / 2, 1.0, places=9)

    def test_zero_rate_never_reaches(self):
        self.assertEqual(by_name(op.holdover(None, 0.0, 0.0, None), "trained_skew")["times_s"], [None] * 7)


class LogRig:
    def __init__(self, test, identity=MINE, d=None):
        self.dir = d or tempfile.mkdtemp(prefix="gtp-hold-")
        test.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.log = osc.Log(path=os.path.join(self.dir, "oscillator-log.csv"), clock=lambda: 1_794_000_000.0,
                           temp_reader=lambda: 46.0, identity=identity)


def seed(log, days=4):
    rows = series(days, daily(40, 52), lambda T, d: 10 + 0.07 * (T - 46))
    log._merge_fit(rows)
    return rows


class TestExportImport(unittest.TestCase):
    def test_export_has_metadata_and_no_position_or_raw_serial(self):
        r = LogRig(self)
        rows = seed(r.log)
        doc = r.log.export(receiver={"driver": "u-blox", "firmware": "x"}, software_version="1.5.0-test")
        self.assertEqual(doc["format"], osc.EXPORT_FORMAT)
        self.assertEqual(doc["board"], MINE)
        self.assertEqual(doc["software_version"], "1.5.0-test")
        self.assertEqual(doc["receiver"]["driver"], "u-blox")
        self.assertEqual(len(doc["fit_bins"]["rows"]), len(rows))
        self.assertEqual(doc["profile"]["status"], "fitted")
        text = json.dumps(doc)
        for word in ("lat", "lon", "alt_m", "serial_number"):
            self.assertNotIn(f'"{word}"', text)

    def test_same_board_round_trip_survives_a_reflash(self):
        src = LogRig(self)
        seed(src.log)
        doc = json.loads(json.dumps(src.log.export()))
        fresh = LogRig(self)                                   # a reflashed card: empty log, same board
        self.assertEqual(fresh.log.profile()["status"], "insufficient")
        res = fresh.log.import_profile(doc)
        self.assertEqual((res["ok"], res["binding"], res["used"]), (True, "match", True))
        self.assertEqual(fresh.log.profile()["status"], "fitted")
        self.assertEqual(fresh.log.report()["profile_files"]["imported"]["binding"], "match")
        # kept next to the log: still in use after a restart
        again = LogRig(self, d=fresh.dir)
        self.assertEqual(again.log.profile()["status"], "fitted")
        self.assertEqual(again.log.imported["bins"], len(doc["fit_bins"]["rows"]))
        self.assertIsNone(again.log.reference)

    def test_another_board_is_reference_only(self):
        src = LogRig(self, identity=OTHER)
        seed(src.log)
        doc = src.log.export()
        mine = LogRig(self)
        res = mine.log.import_profile(doc)
        self.assertEqual((res["ok"], res["binding"], res["used"]), (True, "mismatch", False))
        self.assertEqual(mine.log.profile()["status"], "insufficient")         # nothing merged
        self.assertEqual(op.holdover(mine.log.profile(), 1, 0.01, 46)["projections"][2]["available"], False)
        ref = mine.log.report()["profile_files"]["reference"]
        self.assertIn("different board", ref["warning"])
        self.assertEqual(ref["profile"]["status"], "fitted")                   # shown, for reference
        self.assertEqual(ref["board"]["serial_sha256"], OTHER["serial_sha256"])
        again = LogRig(self, d=mine.dir)
        self.assertEqual(again.log.profile()["status"], "insufficient")
        self.assertEqual(again.log.reference["binding"], "mismatch")

    def test_unverifiable_board_is_reference_only(self):
        src = LogRig(self)
        seed(src.log)
        doc = src.log.export()
        unknown = LogRig(self, identity={"serial_sha256": None, "model": None})
        res = unknown.log.import_profile(doc)
        self.assertEqual((res["binding"], res["used"]), ("unverifiable", False))
        doc2 = {**doc, "board": {"serial_sha256": None}}
        self.assertEqual(LogRig(self).log.import_profile(doc2)["binding"], "unverifiable")

    def test_an_imported_file_moved_to_another_board_is_not_used(self):
        src = LogRig(self)
        seed(src.log)
        mine = LogRig(self)
        mine.log.import_profile(src.log.export())
        moved = LogRig(self, identity=OTHER, d=mine.dir)                       # the SD card in another Pi
        self.assertIsNone(moved.log.imported)
        self.assertEqual(moved.log.reference["binding"], "mismatch")
        self.assertEqual(moved.log.profile()["status"], "insufficient")

    def test_bad_files_are_refused(self):
        log = LogRig(self).log
        good = {"format": osc.EXPORT_FORMAT, "board": MINE, "fit_bins": {"rows": [[1_793_000_000, 45.0, 10.0]]}}
        self.assertTrue(log.import_profile(good, dry_run=True)["ok"])
        for bad in ({}, {**good, "format": "other"}, {**good, "fit_bins": {"rows": "x"}},
                    {**good, "fit_bins": {"rows": [[1, 2]]}}, {**good, "fit_bins": {"rows": [[1_793_000_000, 45.0, True]]}},
                    {**good, "fit_bins": {"rows": [[1_793_000_000, 400.0, 10.0]]}},
                    {**good, "fit_bins": {"rows": [[4_000_000_000, 45.0, 10.0]]}}):
            res = log.import_profile(bad)
            self.assertFalse(res["ok"], bad)
            self.assertIn("error", res)
        self.assertFalse(os.path.exists(os.path.join(log._dir(), osc.IMPORTED_NAME)))

    def test_dry_run_saves_nothing(self):
        src = LogRig(self)
        seed(src.log)
        mine = LogRig(self)
        res = mine.log.import_profile(src.log.export(), dry_run=True)
        self.assertTrue(res["simulated"])
        self.assertEqual(mine.log.profile()["status"], "insufficient")
        self.assertEqual(os.listdir(mine.dir), [])

    def test_report_has_holdover_from_the_last_sample(self):
        r = LogRig(self)
        seed(r.log)
        r.log.add({"Frequency": "10.100 ppm fast", "Skew": "0.012 ppm", "Residual freq": "0.000 ppm"}, True)
        h = r.log.report()["holdover"]
        self.assertEqual(by_name(h, "free_running")["rate_ppm"], 10.1)
        self.assertEqual(by_name(h, "trained_skew")["rate_ppm"], 0.012)
        self.assertTrue(by_name(h, "profile")["available"])
        self.assertIsNotNone(h["sample_utc"])


class TestDemo(unittest.TestCase):
    def test_demo_payload(self):
        from gps_time_pi import demo
        rep = demo.oscillator()
        p = by_name(rep["holdover"], "profile")
        self.assertTrue(p["available"])
        self.assertIsInstance(p["extrapolated"], bool)    # depends on the time of day the demo runs
        self.assertIsNone(rep["profile_files"]["imported"])


class TestHttp(AuthBase):
    def setUp(self):
        super().setUp()
        src = LogRig(self)
        seed(src.log)
        self.doc = src.log.export()
        self.mine = LogRig(self)
        p = mock.patch.object(server, "oscillator_log", lambda: self.mine.log)
        p.start()
        self.addCleanup(p.stop)

    def test_export_is_a_download_and_needs_no_token(self):
        status, headers, body = self.req("GET", "/api/oscillator/profile")
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(body["format"], osc.EXPORT_FORMAT)

    def test_import_needs_the_token(self):
        self.assertEqual(self.post("/api/oscillator/profile", self.doc, token=None)[0], 401)
        self.assertEqual(self.mine.log.profile()["status"], "insufficient")
        status, _, body = self.post("/api/oscillator/profile", self.doc)
        self.assertEqual(status, 200)
        self.assertEqual(body["binding"], "match")
        self.assertEqual(self.mine.log.profile()["status"], "fitted")

    def test_a_90_day_export_fits_under_the_route_cap(self):
        rows = [[1_786_000_000 + i * 600, 45.12, -12.3456] for i in range(op.MAX_BINS)]
        doc = {**self.doc, "fit_bins": {"rows": rows}}
        size = len(json.dumps(doc, separators=(",", ":")))
        self.assertGreater(size, server.MAX_BODY)
        self.assertLess(size, server.ROUTE_MAX_BODY["/api/oscillator/profile"])
        self.assertEqual(self.post("/api/oscillator/profile", doc)[0], 200)

    def test_bad_file_is_400(self):
        status, _, body = self.post("/api/oscillator/profile", {"format": "nope"})
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])


class TestHttpDemo(TestHttp):
    demo = True

    def test_import_needs_the_token(self):
        status, _, body = self.post("/api/oscillator/profile", self.doc, token=None)
        self.assertEqual(status, 200)
        self.assertTrue(body["simulated"])
        self.assertEqual(self.mine.log.profile()["status"], "insufficient")

    def test_a_90_day_export_fits_under_the_route_cap(self):
        pass


if __name__ == "__main__":
    unittest.main()
