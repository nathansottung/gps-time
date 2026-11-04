"""Holdover validation: predicted against measured error at each PPS outage (holdover_check).

Runs on the timing-chain rig (temp sysfs tree, chronyc fixtures, manual clock) and synthetic
entries. No live GNSS, chrony, network or root.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import _env  # noqa: F401
from tests.test_timing_chain import Rig, gnss_no_signal, gnss_ok
from gps_time_pi import holdover_check as hc
from gps_time_pi import oscprofile as op


class FakeOsc:
    """Stands in for oscillator.Log: fixed projections (ppm)."""

    def __init__(self, trained=0.01, free=2.0):
        self.scorecard = None
        self.trained, self.free = trained, free

    def holdover(self):
        return {"sample_utc": "2026-09-21T12:00:00Z", "projections": [
            {"name": "free_running", "available": True, "rate_ppm": self.free, "aging_ppm_per_day": 0.0},
            {"name": "trained_skew", "available": True, "rate_ppm": self.trained, "aging_ppm_per_day": 0.0},
            {"name": "profile", "available": False, "rate_ppm": None, "aging_ppm_per_day": 0.0}]}

    def add(self, *a):
        pass


class ScoreRig(Rig):
    def __init__(self, osc=None, **kw):
        super().__init__(**kw)
        self.svc._oscillator = osc if osc is not None else FakeOsc()

    def stamp(self, err_ns):
        """One pulse: the kernel timestamp err_ns from the whole second (integer ns, as the kernel writes)."""
        self.t[0] += 1.0
        self.seq += 1
        sec = int(self.t[0]) - 1
        ns = err_ns
        if ns < 0:
            sec, ns = sec - 1, 1_000_000_000 + ns
        Path(self.sysfs, "assert").write_text(f"{sec}.{ns:09d}#{self.seq}\n")
        return self.tick()

    def stamps(self, n, err_ns=0):
        c = None
        for _ in range(n):
            c = self.stamp(err_ns)
        return c


def outage(r, during="sources_holdover", tracking="tracking_holdover_last_gps", silent=120, err_ns=2_000):
    """PPS selected, then pulses and GNSS lost for `silent` s, then back with err_ns, then re-selected."""
    r.stamps(5)
    r.sources, r.tracking, r.gnss = during, tracking, gnss_no_signal
    r.silence(silent)
    r.gnss = gnss_ok
    r.stamps(3, err_ns)                                    # pulses back; chrony hasn't selected PPS yet
    r.sources, r.tracking = "sources_pps_selected", "tracking_pps"
    return r.stamps(2, err_ns)


class TestErrorAt(unittest.TestCase):
    def test_rate_and_aging(self):
        self.assertAlmostEqual(hc.error_at(0.01, 0.0, 100.0), 1e-6)
        self.assertAlmostEqual(hc.error_at(-0.01, 0.0, 100.0), 1e-6)
        self.assertAlmostEqual(hc.error_at(0.0, 0.864, 1000.0), 0.5 * 1e-11 * 1e6)
        self.assertIsNone(hc.error_at(None, 0.0, 10.0))

    def test_basis_skips_unavailable_and_scored(self):
        b = hc.basis_from(FakeOsc().holdover())
        self.assertEqual([m["name"] for m in b["models"]], ["free_running", "trained_skew"])
        self.assertIsNone(hc.basis_from({"projections": [{"name": "scored", "available": True, "rate_ppm": 1.0}]}))


class TestScorecardOnTheRig(unittest.TestCase):
    def rig(self, **kw):
        tmp = tempfile.mkdtemp(prefix="gtp-hc-")
        self.addCleanup(shutil.rmtree, tmp, True)
        r = ScoreRig(events_path=os.path.join(tmp, "timing-events.json"), **kw)
        self.addCleanup(r.cleanup)
        return r, tmp

    def test_holdover_outage_is_scored(self):
        r, tmp = self.rig()
        c = outage(r, err_ns=2_000)
        self.assertIsNone(c["events"]["open"])
        sc = r.svc.scorecard
        self.assertEqual(len(sc.entries), 1)
        e = sc.entries[0]
        self.assertEqual(e["measured_at"], "recovery")
        self.assertEqual(e["measured_error_s"], {"value": 2e-6, "unit": "s", "provenance": "observed",
                                                 "note": e["measured_error_s"]["note"]})
        self.assertTrue(e["eligible"])
        self.assertFalse(e["network_ntp"])
        self.assertIsNone(e["not_scored_because"])
        tau = e["time_since_start_s"]["value"]
        self.assertGreater(tau, 100)
        trained = next(p for p in e["predictions"] if p["name"] == "trained_skew")
        self.assertEqual(trained["predicted_error_s"]["provenance"], "modeled")
        self.assertAlmostEqual(trained["predicted_error_s"]["value"], 0.01e-6 * tau, places=12)
        self.assertEqual(trained["ratio"]["provenance"], "calculated")
        self.assertEqual(trained["held"], 2e-6 <= 0.01e-6 * tau)
        free = next(p for p in e["predictions"] if p["name"] == "free_running")
        self.assertTrue(free["held"])                     # 2 ppm over ~2 min is far past 2 µs
        # The event carries the result, and the scorecard is on disk (written once, at close).
        ev = c["events"]["recent"][0]
        self.assertTrue(ev["recovery"]["holdover_check"]["eligible"])
        self.assertEqual(ev["recovery"]["network_ntp"]["value"], False)
        doc = json.loads(Path(tmp, "holdover-scorecard.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["schema"], hc.SCHEMA)
        self.assertEqual(len(doc["entries"]), 1)
        self.assertNotIn("38.92", json.dumps(doc))         # no position

    def test_network_ntp_is_flagged_not_scored(self):
        r, _ = self.rig()
        outage(r, during="sources_failover", tracking="tracking_network")
        e = r.svc.scorecard.entries[0]
        self.assertTrue(e["network_ntp"])
        self.assertEqual(e["network_ntp_sources"], ["192.0.2.10"])
        self.assertIn("network_ntp", e["flags"])
        self.assertFalse(e["eligible"])
        self.assertIn("network NTP", " ".join(e["not_scored_because"]))
        rec = r.svc.latest()["events"]["recent"][0]["recovery"]
        self.assertEqual(rec["network_ntp"]["value"], True)
        self.assertEqual(rec["network_ntp"]["provenance"], "observed")
        self.assertEqual(rec["network_ntp_sources"], ["192.0.2.10"])
        s = r.svc.scorecard.summary()
        self.assertEqual((s["entries"], s["eligible"], s["network_ntp"]), (1, 0, 1))
        self.assertEqual(s["models"], [])

    def test_chrony_only_outage_is_measured_after_reselection(self):
        r, _ = self.rig()
        r.stamps(5)
        r.sources, r.tracking = "sources_pps_rejected", "tracking_holdover_last_gps"
        r.stamps(60, 1_000)                                # pulses and GNSS fine throughout
        r.sources, r.tracking = "sources_pps_selected", "tracking_pps"
        r.stamps(2, 1_000)
        e = r.svc.scorecard.entries[0]
        self.assertEqual(e["measured_at"], "reselected")
        self.assertIn("after_reselection", e["flags"])
        self.assertFalse(e["eligible"])

    def test_boot_outage_has_no_prediction(self):
        tmp = tempfile.mkdtemp(prefix="gtp-hc-")
        self.addCleanup(shutil.rmtree, tmp, True)
        from tests.test_timing_chain import T0
        r = ScoreRig(events_path=os.path.join(tmp, "ev.json"), boot=(T0 - 10, "boot-x"),
                     sources="sources_holdover", tracking="tracking_unsync", gnss=gnss_no_signal)
        self.addCleanup(r.cleanup)
        r.silence(1800, step=30.0)                         # past the 30 min acquire window: outage from boot
        r.gnss = gnss_ok
        r.stamps(2, 5_000)
        r.sources, r.tracking = "sources_pps_selected", "tracking_pps"
        r.stamps(2, 5_000)
        e = r.svc.scorecard.entries[0]
        self.assertIn("no_prediction", e["flags"])
        self.assertIn("boot", " ".join(e["not_scored_because"]))
        self.assertEqual(e["predictions"], [])

    def test_half_second_errors_are_ambiguous(self):
        r, _ = self.rig()
        outage(r, err_ns=-450_000_000)
        e = r.svc.scorecard.entries[0]
        self.assertIn("ambiguous_second", e["flags"])
        self.assertFalse(e["eligible"])
        self.assertAlmostEqual(e["measured_error_s"]["value"], -0.45)

    def test_prediction_is_kept_in_the_checkpointed_event(self):
        r, tmp = self.rig()
        r.stamps(5)
        r.sources, r.tracking, r.gnss = "sources_holdover", "tracking_holdover_last_gps", gnss_no_signal
        r.silence(60)
        doc = json.loads(Path(tmp, "timing-events.json").read_text(encoding="utf-8"))
        basis = doc["open"]["holdover_check"]["basis"]
        self.assertEqual([m["name"] for m in basis["models"]], ["free_running", "trained_skew"])

    def test_reload_and_corrupt_file(self):
        tmp = tempfile.mkdtemp(prefix="gtp-hc-")
        self.addCleanup(shutil.rmtree, tmp, True)
        p = os.path.join(tmp, "holdover-scorecard.json")
        Path(p).write_text(json.dumps({"schema": hc.SCHEMA, "entries": [{"eligible": False}] * 3}), encoding="utf-8")
        self.assertEqual(len(hc.Scorecard(p, max_entries=2).entries), 2)
        Path(p).write_text("{not json", encoding="utf-8")
        sc = hc.Scorecard(p, clock=lambda: 1234.0)
        self.assertEqual(sc.entries, [])
        self.assertTrue(os.path.exists(p + ".corrupt-1234"))
        self.assertTrue(sc.problems)


def entry(name_ratios, eligible=True):
    return {"eligible": eligible, "network_ntp": not eligible, "predictions": [
        {"name": n, "held": r <= 1, "ratio": {"value": r}} for n, r in name_ratios.items()]}


class TestFedIntoTheProjections(unittest.TestCase):
    def card(self, ratios_list):
        sc = hc.Scorecard(None)
        sc.entries = [entry(r) for r in ratios_list]
        return sc.summary()

    def test_summary_per_model(self):
        s = self.card([{"trained_skew": 0.5}, {"trained_skew": 2.0}, {"trained_skew": 0.8}])
        m = s["models"][0]
        self.assertEqual((m["name"], m["n"], m["held"], m["worst_ratio"], m["median_ratio"]),
                         ("trained_skew", 3, 2, 2.0, 0.8))
        self.assertEqual(m["provenance"], "calculated")

    def test_scored_projection_needs_enough_outages(self):
        h = op.holdover(None, 2.0, 0.01, None, scorecard=self.card([{"trained_skew": 2.0}]))
        sc = next(p for p in h["projections"] if p["name"] == "scored")
        self.assertFalse(sc["available"])
        self.assertIn("needs 3", sc["reason"])
        self.assertIn("1 outage measured", h["note"])
        trained = next(p for p in h["projections"] if p["name"] == "trained_skew")
        self.assertEqual(trained["validated"]["n"], 1)

    def test_scored_projection_scales_by_the_worst_ratio(self):
        h = op.holdover(None, 2.0, 0.01, None, scorecard=self.card([{"trained_skew": r} for r in (0.5, 2.5, 1.0)]))
        sc = next(p for p in h["projections"] if p["name"] == "scored")
        self.assertTrue(sc["available"])
        self.assertEqual(sc["provenance"], "modeled")
        self.assertEqual((sc["from"], sc["factor"], sc["outages"]), ("trained_skew", 2.5, 3))
        self.assertAlmostEqual(sc["rate_ppm"], 0.025)
        self.assertAlmostEqual(sc["times_s"][0], 1e-6 / 0.025e-6)

    def test_never_better_than_the_model(self):
        h = op.holdover(None, 2.0, 0.01, None, scorecard=self.card([{"trained_skew": r} for r in (0.1, 0.2, 0.3)]))
        sc = next(p for p in h["projections"] if p["name"] == "scored")
        self.assertEqual(sc["factor"], 1.0)
        self.assertIn("unscaled", sc["basis"])

    def test_without_a_scorecard_nothing_changes(self):
        h = op.holdover(None, 2.0, 0.01, None)
        self.assertNotIn("scorecard", h)
        self.assertEqual([p["name"] for p in h["projections"]], ["free_running", "trained_skew", "profile"])
        self.assertIn("none has been checked", h["note"])


if __name__ == "__main__":
    unittest.main()
