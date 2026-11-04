"""Stability analysis (SPEC-TIMING-METROLOGY section 1).

The estimators are checked against the published reference values of NIST
SP 1065 (Riley, Handbook of Frequency Stability Analysis), section 12.4:
the 9-point NBS Monograph 140 data set and the 1000-point test suite. No live
PPS, chrony or Internet needed.
"""

import json
import math
import random
import unittest

from tests import _env  # noqa: F401
from gps_time_pi import stability
from gps_time_pi.labels import PROVENANCE

# NBS Monograph 140, Annex 8.E: nine fractional-frequency values, tau0 = 1.
NBS9 = [892, 809, 823, 798, 671, 644, 883, 903, 677]


def nbs1000():
    """SP 1065 section 12.4: 1000 values from n[i+1] = 16807 n[i] mod (2^31 - 1),
    seed 1234567890, divided by 2^31 - 1."""
    n = [1234567890]
    for _ in range(999):
        n.append(16807 * n[-1] % 2147483647)
    assert n[1:4] == [395529916, 1209410747, 633705974]     # the values printed in SP 1065
    return [v / 2147483647 for v in n]


def white_pm(count, sigma=3e-7, seed=1):
    rng = random.Random(seed)
    return [rng.gauss(0.0, sigma) for _ in range(count)]


class TestPublishedReferenceValues(unittest.TestCase):
    def close(self, got, want):
        self.assertAlmostEqual(got / want, 1.0, places=6, msg=f"{got!r} != published {want!r}")

    def test_nbs9_overlapping_adev(self):
        x = stability.phase_from_frequency(NBS9)
        self.close(stability.oadev(x, 1)[0], 91.22945)
        self.close(stability.oadev(x, 2)[0], 85.95287)

    def test_nbs9_mdev_and_tdev(self):
        x = stability.phase_from_frequency(NBS9)
        self.close(stability.mdev(x, 1)[0], 91.22945)
        self.close(stability.mdev(x, 2)[0], 74.78849)
        self.close(stability.tdev_from_mdev(stability.mdev(x, 1)[0], 1), 52.67135)
        self.close(stability.tdev_from_mdev(stability.mdev(x, 2)[0], 2), 86.35831)

    def test_1000_point_suite(self):
        x = stability.phase_from_frequency(nbs1000())
        published = {    # averaging factor: (overlapping ADEV, MDEV, TDEV)
            1: (2.922319e-01, 2.922319e-01, 1.687202e-01),
            10: (9.159953e-02, 6.172376e-02, 3.563623e-01),
            100: (3.241343e-02, 2.170921e-02, 1.253382e+00),
        }
        for m, (adev, mdev, tdev) in published.items():
            with self.subTest(m=m):
                self.close(stability.oadev(x, m)[0], adev)
                got_mdev = stability.mdev(x, m)[0]
                self.close(got_mdev, mdev)
                self.close(stability.tdev_from_mdev(got_mdev, m), tdev)

    def test_1000_point_suite_is_identified_as_white_fm_with_the_published_edf(self):
        x = stability.phase_from_frequency(nbs1000())
        self.assertEqual(stability.noise_alpha(x, 1), 0)
        self.assertEqual(stability.noise_alpha(x, 10), 0)
        # SP 1065 section 12.4: overlapping ADEV at AF 10, white FM, edf 146.177
        self.assertAlmostEqual(stability.oadev_edf(0, 1001, 10), 146.177, places=3)

    def test_term_counts(self):
        x = stability.phase_from_frequency(nbs1000())     # 1001 phase points
        self.assertEqual(stability.oadev(x, 10)[1], 1001 - 20)
        self.assertEqual(stability.mdev(x, 10)[1], 1001 - 30 + 1)


class TestChiSquared(unittest.TestCase):
    def test_quantiles_match_standard_tables(self):
        for p, k, want in ((0.95, 10, 18.307), (0.05, 10, 3.940), (0.5, 1, 0.4549),
                           (0.975, 100, 129.561), (0.025, 100, 74.222), (0.99, 2, 9.210)):
            with self.subTest(p=p, k=k):
                self.assertAlmostEqual(stability.chi2_ppf(p, k), want, delta=want * 2e-4)

    def test_interval_brackets_the_estimate_and_narrows_with_edf(self):
        lo1, hi1 = stability.confidence_interval(1.0, 5)
        lo2, hi2 = stability.confidence_interval(1.0, 500)
        self.assertLess(lo1, 1.0)
        self.assertGreater(hi1, 1.0)
        self.assertLess(hi2 - lo2, hi1 - lo1)
        self.assertAlmostEqual(lo2, 1.0, delta=0.05)

    def test_edf_is_positive_and_never_exceeds_the_number_of_samples(self):
        for alpha in (2, 1, 0, -1, -2):
            for m in (1, 10, 100):
                edf = stability.oadev_edf(alpha, 1001, m)
                self.assertGreater(edf, 0)
                self.assertLessEqual(edf, 1001)


class TestNoiseIdentification(unittest.TestCase):
    def test_white_pm(self):
        self.assertEqual(stability.noise_alpha(white_pm(2000), 1), 2)

    def test_random_walk_fm(self):
        rng = random.Random(3)
        y, f = [], 0.0
        for _ in range(3000):
            f += rng.gauss(0, 1e-9)
            y.append(f)
        self.assertEqual(stability.noise_alpha(stability.phase_from_frequency(y), 1), -2)

    def test_too_few_points_is_not_identified(self):
        self.assertIsNone(stability.noise_alpha(white_pm(2000), 100))     # 20 decimated points

    def test_white_pm_adev_follows_the_known_law(self):
        # For white PM of standard deviation s, ADEV(tau) = sqrt(3) s / tau.
        x = white_pm(20000, sigma=1e-6, seed=7)
        for m in (1, 10, 100):
            self.assertAlmostEqual(stability.oadev(x, m)[0] / (math.sqrt(3) * 1e-6 / m), 1.0, delta=0.05)


class TestGaps(unittest.TestCase):
    def test_terms_touching_a_gap_are_skipped_not_guessed(self):
        x = white_pm(500)
        full, n_full = stability.oadev(x, 5)
        x[250] = None
        gapped, n_gapped = stability.oadev(x, 5)
        self.assertEqual(n_full - n_gapped, 3)
        self.assertAlmostEqual(gapped / full, 1.0, delta=0.05)

    def test_window_means(self):
        self.assertEqual(stability.window_means([1.0, 2.0, 3.0, None, 5.0, 6.0], 2),
                         [1.5, 2.5, None, None, 5.5])

    def test_all_missing_gives_no_value(self):
        self.assertEqual(stability.oadev([None] * 10, 1), (None, 0))
        self.assertEqual(stability.mdev([None] * 10, 1), (None, 0))


class TestMinuteSummaries(unittest.TestCase):
    def test_long_span_values_equal_the_one_second_calculation(self):
        """The minute summaries are exact inputs, not approximations: ADEV from
        each minute's last sample, MDEV from minute means, against the same
        statistics computed from every second."""
        rng = random.Random(11)
        seconds = 60 * 400
        walk, f = [], 0.0
        for _ in range(seconds):
            f += rng.gauss(0, 2e-9)
            walk.append(f)
        x = stability.phase_from_frequency(walk)[1:]
        last = [x[i * 60 + 59] for i in range(seconds // 60)]
        mean = [sum(x[i * 60:(i + 1) * 60]) / 60 for i in range(seconds // 60)]
        for m in (1, 5, 60):
            adev_min, _ = stability.oadev(last, m, 60.0)
            adev_sec, _ = stability.oadev(x[59::60], m, 60.0)
            self.assertEqual(adev_min, adev_sec)
            mdev_min, _ = stability.mdev_from_means(stability.window_means(mean, m), m, m * 60.0)
            # the 1 s definition, on the same non-overlapping minute grid
            means_1s = stability.window_means(x, m * 60)[::60]
            mdev_sec, _ = stability.mdev_from_means(means_1s, m, m * 60.0)
            self.assertAlmostEqual(mdev_min / mdev_sec, 1.0, places=9)


class TestRecorder(unittest.TestCase):
    def feed(self, rec, start, count, sigma=3e-7, selected=True, seed=5, skip=()):
        rng = random.Random(seed)
        for i in range(count):
            phase = rng.gauss(0, sigma)
            if i in skip:
                continue
            rec.add((start + i) * 1_000_000_000 + round(phase * 1e9), selected)

    def test_empty_recorder_reports_unknown_not_zero(self):
        rep = stability.Recorder(clock=lambda: 0.0).report()
        self.assertFalse(rep["available"])
        self.assertIn("No kernel PPS events", rep["reason"])
        self.assertEqual(rep["points"], [])
        self.assertTrue(all(k["point"] is None and k["reason"] for k in rep["key_points"]))

    def test_report_after_an_hour(self):
        rec = stability.Recorder(clock=lambda: 0.0)
        self.feed(rec, 1_790_000_000, 3600)
        rep = rec.report()
        self.assertTrue(rep["available"])
        self.assertEqual(rep["provenance"], "calculated")
        self.assertIn(rep["provenance"], PROVENANCE)
        self.assertIn("not the receiver's electrical pps", rep["measurement_layer"].lower())
        taus = [p["tau_s"] for p in rep["points"]]
        self.assertEqual(taus, [1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0])
        first = rep["points"][0]
        self.assertAlmostEqual(first["adev"] / (math.sqrt(3) * 3e-7), 1.0, delta=0.1)
        self.assertEqual(first["noise"], "white PM")
        self.assertLess(first["adev_low"], first["adev"])
        self.assertGreater(first["adev_high"], first["adev"])
        self.assertEqual(rep["series"]["seconds"]["samples"], 3600)
        self.assertEqual(rep["series"]["seconds"]["gaps"], 0)
        self.assertEqual(rep["series"]["seconds"]["pps_selected_fraction"], 1.0)
        self.assertEqual(rep["since_utc"], "2026-09-21T14:13:20+00:00")
        json.dumps(rep)

    def test_key_points_say_what_is_missing(self):
        rec = stability.Recorder(clock=lambda: 0.0)
        self.feed(rec, 1_790_000_000, 600)
        key = {k["label"]: k for k in rec.report()["key_points"]}
        self.assertEqual(list(key), ["1 s", "10 s", "100 s", "1000 s", "1 day"])
        self.assertIsNotNone(key["100 s"]["point"])
        self.assertIsNone(key["1000 s"]["point"])
        self.assertIn("50 min", key["1000 s"]["reason"])
        self.assertIn("3 days", key["1 day"]["reason"])

    def test_missed_seconds_are_gaps(self):
        rec = stability.Recorder(clock=lambda: 0.0)
        self.feed(rec, 1_790_000_000, 300, skip={100, 101, 200})
        rep = rec.report()
        self.assertEqual(rep["series"]["seconds"]["samples"], 297)
        self.assertEqual(rep["series"]["seconds"]["gaps"], 3)
        self.assertTrue(any("no PPS sample" in n for n in rep["notes"]))

    def test_the_same_second_twice_is_recorded_once(self):
        rec = stability.Recorder(clock=lambda: 0.0)
        for _ in range(3):
            rec.add(1_790_000_000_000_000_200, True)
        self.assertEqual(rec.report()["series"]["seconds"]["samples"], 1)

    def test_integer_ns_keep_phases_a_float_would_lose(self):
        # Near 1.79e9 s a float timestamp steps in about 238 ns; integer ns keep each phase exactly.
        rec = stability.Recorder(clock=lambda: 0.0)
        start = 1_790_000_000 * 1_000_000_000
        for i in range(600):
            rec.add(start + i * 1_000_000_000 + (37 if i % 2 else -37), True)
        with rec._lock:
            phases = list(rec._sec)
        self.assertEqual(sorted(set(round(p * 1e9) for p in phases)), [-37, 37])
        first = rec.report()["points"][0]
        # Alternating +/-37 ns: second differences are +/-148 ns, so ADEV(1 s) = 148e-9 / sqrt(2).
        self.assertAlmostEqual(first["adev"], 148e-9 / math.sqrt(2), delta=1e-12)

    def test_phase_is_found_in_integer_arithmetic(self):
        from gps_time_pi import pps
        ns = 1_000_000_000
        self.assertEqual(pps.phase_ns(1_790_000_000 * ns + 1), (1_790_000_000, 1))
        self.assertEqual(pps.phase_ns(1_790_000_000 * ns - 1), (1_790_000_000, -1))
        self.assertEqual(pps.phase_ns(1_790_000_000 * ns + ns // 2), (1_790_000_000, ns // 2))
        self.assertEqual(pps.phase_ns(1_790_000_000 * ns + ns // 2 + 1), (1_790_000_001, -(ns // 2) + 1))

    def test_a_float_timestamp_is_refused(self):
        rec = stability.Recorder(clock=lambda: 0.0)
        with self.assertRaises(TypeError):
            rec.add(1_790_000_000.0000002, True)
        with self.assertRaises(TypeError):
            rec.add(True, True)

    def test_clock_stepping_back_restarts_the_history(self):
        rec = stability.Recorder(clock=lambda: 0.0)
        self.feed(rec, 1_790_000_000, 100)
        rec.add(1_789_999_000 * 1_000_000_000, True)
        rep = rec.report()
        self.assertEqual(rep["series"]["seconds"]["samples"], 1)
        self.assertEqual(rep["history_resets"], 1)

    def test_rings_are_bounded(self):
        rec = stability.Recorder(ring_s=120, ring_minutes=3, clock=lambda: 0.0)
        self.feed(rec, 1_790_000_040, 600)
        rep = rec.report()
        self.assertEqual(rep["series"]["seconds"]["span_s"], 120)
        self.assertEqual(rep["series"]["minutes"]["span_s"], 180)

    def test_share_of_time_with_pps_selected_is_reported(self):
        rec = stability.Recorder(clock=lambda: 0.0)
        self.feed(rec, 1_790_000_000, 100, selected=True)
        self.feed(rec, 1_790_000_100, 300, selected=False, seed=6)
        rep = rec.report()
        self.assertEqual(rep["series"]["seconds"]["pps_selected_fraction"], 0.25)
        self.assertTrue(any("25%" in n for n in rep["notes"]))

    def test_minute_summaries_feed_the_long_averaging_times(self):
        rec = stability.Recorder(clock=lambda: 0.0)
        self.feed(rec, 1_790_000_040, 60 * 250)
        rep = rec.report()
        minutes = [p for p in rep["points"] if p["series"] == "minutes"]
        self.assertEqual([p["tau_s"] for p in minutes], [3600.0])
        self.assertIsNotNone(minutes[0]["mdev"])
        self.assertAlmostEqual(minutes[0]["tdev_s"], 3600 * minutes[0]["mdev"] / math.sqrt(3))
        self.assertEqual(rep["series"]["minutes"]["tau0_s"], 60.0)

    def test_report_is_cached_briefly(self):
        now = [1000.0]
        rec = stability.Recorder(clock=lambda: now[0])
        self.feed(rec, 1_790_000_000, 50)
        first = rec.report()
        self.feed(rec, 1_790_000_050, 50)
        self.assertIs(rec.report(), first)
        now[0] += stability.CACHE_S + 1
        self.assertEqual(rec.report()["series"]["seconds"]["samples"], 100)

    def test_nothing_is_written_to_disk(self):
        import inspect
        src = inspect.getsource(stability)
        self.assertNotIn("open(", src)
        self.assertNotIn("os.", src)


class TestService(unittest.TestCase):
    """The timing-chain service feeds the recorder; /api/stability serves it."""

    def setUp(self):
        from tests.test_timing_chain import Rig
        self.rig = Rig()
        self.addCleanup(self.rig.cleanup)

    def test_each_observed_pulse_becomes_one_phase_sample(self):
        self.rig.pulses(120)
        rep = self.rig.svc.stability.report()
        self.assertEqual(rep["series"]["seconds"]["samples"], 120)
        self.assertEqual(rep["series"]["seconds"]["gaps"], 0)
        self.assertEqual(rep["series"]["seconds"]["pps_selected_fraction"], 1.0)
        self.assertTrue(rep["available"])

    def test_polls_without_a_new_pulse_add_nothing(self):
        self.rig.pulses(10)
        self.rig.silence(30)
        self.assertEqual(self.rig.svc.stability.report()["series"]["seconds"]["samples"], 10)

    def test_samples_under_network_failover_are_marked(self):
        rig = self.rig
        rig.sources, rig.tracking = "sources_failover", "tracking_network"
        rig.pulses(20)
        self.assertEqual(rig.svc.stability.report()["series"]["seconds"]["pps_selected_fraction"], 0.0)

    def test_no_pps_device_reports_unavailable(self):
        from tests.test_timing_chain import Rig
        rig = Rig(device=False)
        self.addCleanup(rig.cleanup)
        rig.silence(5)
        rep = rig.svc.stability.report()
        self.assertFalse(rep["available"])
        self.assertEqual(rep["points"], [])

    def test_poll_grid_does_not_drift(self):
        from gps_time_pi import timing_chain as tc
        # a tick that ends at any point of the second waits until the next x.25
        for now in (100.0, 100.2, 100.26, 100.9, 101.249):
            wake = now + tc.next_tick_delay(now)
            self.assertAlmostEqual(wake % 1.0, 0.25, places=6)
            self.assertGreater(wake, now)
            self.assertLessEqual(wake - now, 1.0)

    def test_api_route_in_demo_mode(self):
        from unittest import mock
        from gps_time_pi import server
        with mock.patch.object(server, "DEMO_MODE", True):
            rep = server.stability_payload()
        self.assertTrue(rep["available"])
        self.assertEqual([k["label"] for k in rep["key_points"]], ["1 s", "10 s", "100 s", "1000 s", "1 day"])
        self.assertTrue(all(k["point"] for k in rep["key_points"]))
        self.assertEqual(rep["notes"], ["sample data"])
        json.dumps(rep)


if __name__ == "__main__":
    unittest.main()
