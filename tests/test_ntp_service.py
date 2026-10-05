"""NTP service health from chrony's serverstats (SPEC-TIMING-METROLOGY
section 6). Fixtures only: no chrony, no network.
"""

import inspect
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import chrony, labels, ntpservice

ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / "tests" / "fixtures" / "chrony" / "serverstats.txt").read_text(encoding="utf-8")


class Rig:
    def __init__(self, received=1000, dropped=0):
        self.t = [1_790_000_000.0]
        self.stats = {"ntp_received": received, "ntp_dropped": dropped, "cmd_received": 5, "cmd_dropped": 0}
        self.tracker = ntpservice.Tracker(clock=lambda: self.t[0], reader=lambda: self.stats)

    def step(self, seconds=60, received=0, dropped=0):
        self.t[0] += seconds
        if self.stats is not None:
            self.stats = {**self.stats, "ntp_received": self.stats["ntp_received"] + received,
                          "ntp_dropped": self.stats["ntp_dropped"] + dropped}
        self.tracker.update()
        return self.tracker.report()


class TestParse(unittest.TestCase):
    def test_fixture(self):
        s = chrony.parse_serverstats(TEXT)
        self.assertEqual(s["ntp_received"], 1598)
        self.assertEqual(s["ntp_dropped"], 8)
        self.assertEqual(s["cmd_received"], 19)
        self.assertEqual(s["client_log_dropped"], 0)
        self.assertEqual(s["nts_ke_accepted"], 3)
        self.assertEqual(s["ntp_interleaved"], 43)
        self.assertNotIn("NTP timestamps held", s)

    def test_an_error_message_is_unknown_not_zero(self):
        self.assertIsNone(chrony.parse_serverstats("501 Not authorised\n"))
        self.assertIsNone(chrony.parse_serverstats(""))
        self.assertIsNone(chrony.parse_serverstats("NTP packets dropped : 3\n"))

    def test_published_file_is_used_and_a_stale_one_ignored(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        p = os.path.join(d, "chrony-serverstats.txt")
        Path(p).write_text(TEXT, encoding="utf-8")
        with mock.patch.object(chrony, "SERVERSTATS_FILE", p), \
                mock.patch.object(chrony, "run_chronyc", side_effect=AssertionError("chronyc must not run")):
            self.assertEqual(chrony.serverstats()["ntp_received"], 1598)
        old = os.stat(p).st_mtime - chrony.CLIENTS_MAX_AGE_S - 30
        os.utime(p, (old, old))
        with mock.patch.object(chrony, "SERVERSTATS_FILE", p), mock.patch.object(chrony, "run_chronyc", lambda *a: (False, "")):
            self.assertIsNone(chrony.serverstats())


class TestTracker(unittest.TestCase):
    def test_unreadable_is_unknown(self):
        t = ntpservice.Tracker(clock=lambda: 0.0, reader=lambda: None)
        t.update()
        rep = t.report()
        self.assertFalse(rep["available"])
        self.assertEqual(rep["state"], "UNKNOWN")
        self.assertIsNone(rep["ntp"])
        self.assertIn("helper service", rep["reason"])
        json.dumps(rep)

    def test_before_any_update(self):
        self.assertFalse(ntpservice.Tracker(clock=lambda: 0.0, reader=lambda: None).report()["available"])

    def test_totals_and_labels(self):
        rig = Rig(received=1598, dropped=8)
        rep = rig.step(0)
        self.assertTrue(rep["available"])
        self.assertEqual(rep["ntp"]["received"]["value"], 1598)
        self.assertEqual(rep["ntp"]["received"]["provenance"], "observed")
        self.assertEqual(rep["ntp"]["dropped"]["value"], 8)
        self.assertEqual(rep["ntp"]["not_dropped"]["value"], 1590)
        self.assertEqual(rep["ntp"]["not_dropped"]["provenance"], "calculated")
        self.assertIn("does not count the replies", rep["ntp"]["not_dropped"]["note"])
        self.assertAlmostEqual(rep["ntp"]["drop_fraction"]["value"], 8 / 1598)
        for v in rep["ntp"].values():
            self.assertIn(v["provenance"], labels.PROVENANCE)

    def test_no_rate_until_there_is_a_minute_of_history(self):
        rep = Rig().step(0)
        self.assertIsNone(rep["rates"]["last_minute"]["received_per_s"]["value"])
        self.assertIsNone(rep["rates"]["last_hour"]["received_per_s"]["value"])
        self.assertIn("no rate yet", rep["state_basis"])

    def test_rates_and_history(self):
        rig = Rig()
        rig.step(0)
        for _ in range(5):
            rep = rig.step(60, received=30)
        self.assertAlmostEqual(rep["rates"]["last_minute"]["received_per_s"]["value"], 0.5)
        self.assertIsNone(rep["rates"]["last_hour"]["received_per_s"]["value"], "under an hour of history")
        self.assertEqual(rep["state"], "SERVING")
        self.assertEqual(rep["state_basis"], "over the last minute")
        self.assertEqual([h["received_per_min"] for h in rep["history"]], [30.0] * 5)
        for _ in range(60):
            rep = rig.step(60, received=60)
        self.assertAlmostEqual(rep["rates"]["last_hour"]["received_per_s"]["value"], 1.0)
        self.assertEqual(rep["state_basis"], "over the last hour")

    def test_states(self):
        rig = Rig()
        rig.step(0)
        self.assertEqual(rig.step(60, received=0)["state"], "NO_REQUESTS")
        self.assertEqual(rig.step(60, received=10)["state"], "SERVING")
        rep = rig.step(60, received=10, dropped=2)
        self.assertEqual(rep["state"], "SERVING_WITH_DROPS")
        self.assertEqual(rep["history"][-1]["dropped_per_min"], 2.0)
        self.assertEqual(rep["state_provenance"], "calculated")

    def test_no_cause_beyond_chronys_own_definition(self):
        rig = Rig()
        rig.step(0)
        text = json.dumps(rig.step(60, received=10, dropped=5)).upper()
        for word in ("ATTACK", "FLOOD", "ABUSE", "DOS", "MALICIOUS"):
            self.assertNotIn(word, text)
        self.assertIn("RATE LIMIT", text)

    def test_chronyd_restart_restarts_the_history(self):
        rig = Rig(received=5000)
        rig.step(0)
        rig.step(60, received=100)
        rig.stats = {"ntp_received": 3, "ntp_dropped": 0}
        rep = rig.step(60)
        self.assertEqual(rep["counter_resets"], 1)
        self.assertEqual(rep["history"], [])
        self.assertEqual(rep["ntp"]["received"]["value"], 3)

    def test_history_is_bounded_and_sampled_once_a_minute(self):
        rig = Rig()
        for _ in range(4 * (ntpservice.HISTORY_POINTS + 100)):
            rig.t[0] += 15
            rig.stats = {**rig.stats, "ntp_received": rig.stats["ntp_received"] + 1}
            rig.tracker.update()
        self.assertEqual(len(rig.tracker.report()["history"]), ntpservice.HISTORY_POINTS)

    def test_helper_going_away_becomes_unknown(self):
        rig = Rig()
        rig.step(0)
        rig.stats = None
        rep = rig.step(60)
        self.assertFalse(rep["available"])
        self.assertEqual(rep["state"], "UNKNOWN")

    def test_a_failing_reader_does_not_raise(self):
        def boom():
            raise OSError("gone")
        t = ntpservice.Tracker(clock=lambda: 0.0, reader=boom)
        t.update()
        self.assertFalse(t.report()["available"])

    def test_module_does_not_talk_to_chronyd_or_write_files(self):
        src = inspect.getsource(ntpservice)
        for word in ("open(", "subprocess", "socket", "run_chronyc"):
            self.assertFalse(word in src, f"ntpservice.py must not use {word}")


class TestServiceAndRoute(unittest.TestCase):
    def test_timing_chain_reads_the_counters(self):
        from tests.test_timing_chain import Rig as ChainRig
        rig = ChainRig()
        self.addCleanup(rig.cleanup)
        rig.svc.ntp_service.reader = lambda: {"ntp_received": 42, "ntp_dropped": 1}
        rig.pulses(2)
        self.assertEqual(rig.svc.ntp_service.report()["ntp"]["received"]["value"], 42)

    def test_route_in_demo_mode(self):
        from gps_time_pi import server
        with mock.patch.object(server, "DEMO_MODE", True):
            rep = server.ntp_service_payload()
        self.assertTrue(rep["available"])
        self.assertEqual(len(rep["history"]), 120)
        self.assertIn("Sample data", rep["note"])
        json.dumps(rep)


if __name__ == "__main__":
    unittest.main()
