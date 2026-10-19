"""PPS reads on their own thread, and missed versus unread pulses (rc.9 item 3).

The rc.8 soak run counted 112,588 missed pulses (about 9 % of the run) while
the real outages on 2026-10-17 accounted for about 4,300 s. These tests pin
down what each counter means, that a slow chain evaluation can no longer
delay reading the PPS, that no HTTP request polls, and that outage detection
is unchanged. No hardware: a fake sysfs reader and manual clocks.
"""

import threading
import time
import unittest
from unittest import mock

from tests import _env  # noqa: F401
from tests.test_timing_chain import Rig, state
from gps_time_pi import pps, timing_chain as tc

T0 = 1_790_000_000.0


class Pulses:
    """A fake kernel PPS: assert timestamp and sequence, advanced by the test."""

    def __init__(self):
        self.ts, self.seq = 0.0, 0
        self.t = [T0]

    def pulse(self, at, count=1):
        """The kernel counts `count` pulses; the last one is stamped at `at`."""
        self.seq += count
        self.ts = at

    def read(self):
        return ("ok", self.ts, self.seq) if self.seq else ("ok", 0.0, 0)

    def monitor(self):
        return pps.PPSMonitor(device="/dev/pps-test", sysfs="/nonexistent", clock=lambda: self.t[0],
                              reader=self.read, device_state=lambda: (True, None))


def counters(m):
    s = m.snapshot()
    return s["missed_pulses"]["value"], s["unread_pulses"]["value"]


class TestMissedAndUnread(unittest.TestCase):
    def setUp(self):
        self.k = Pulses()
        self.m = self.k.monitor()

    def step(self, at, count=1, poll_at=None):
        self.k.pulse(at, count)
        self.k.t[0] = poll_at if poll_at is not None else at + 0.25
        self.m.poll()

    def test_every_pulse_read(self):
        for i in range(10):
            self.step(T0 + i)
        self.assertEqual(counters(self.m), (0, 0))

    def test_a_poll_that_skips_a_second_loses_nothing(self):
        # The kernel counted two pulses between polls: one was not read on its
        # own, but it arrived. Before rc.9 this was correctly not "missed"; it
        # is now visible as "unread".
        self.step(T0)
        self.step(T0 + 2, count=2, poll_at=T0 + 2.25)
        self.assertEqual(counters(self.m), (0, 1))

    def test_pulses_the_kernel_never_counted_are_missed(self):
        # Three seconds pass and the kernel counts one pulse: two never arrived.
        self.step(T0)
        self.step(T0 + 3, count=1)
        self.assertEqual(counters(self.m), (2, 0))

    def test_both_at_once(self):
        # Five seconds, the kernel counts three pulses, the station reads the last.
        self.step(T0)
        self.step(T0 + 5, count=3)
        self.assertEqual(counters(self.m), (2, 2))

    def test_a_real_outage_is_still_missed_pulses(self):
        self.step(T0)
        self.step(T0 + 3600, count=1)          # an hour without pulses, then one
        self.assertEqual(counters(self.m), (3599, 0))

    def test_late_polls_are_counted(self):
        self.step(T0)
        self.step(T0 + 1)
        self.step(T0 + 4, count=3, poll_at=T0 + 4.25)    # the station didn't read for three seconds
        s = self.m.snapshot()
        self.assertEqual(s["poller"]["polls"], 3)
        self.assertEqual(s["poller"]["late_polls"], 1)
        self.assertAlmostEqual(s["poller"]["max_poll_gap_s"], 3.0)
        self.assertEqual(counters(self.m), (0, 2))

    def test_labels_say_what_each_counter_means(self):
        s = self.m.snapshot()
        self.assertIn("never counted", s["missed_pulses"]["note"])
        self.assertIn("not lost", s["unread_pulses"]["note"])
        self.assertEqual(s["unread_pulses"]["provenance"], "calculated")


class TestPollerThread(unittest.TestCase):
    def setUp(self):
        self.rig = Rig()
        self.addCleanup(self.rig.cleanup)

    def test_tick_without_polling_does_not_read_the_pps(self):
        with mock.patch.object(self.rig.monitor, "poll", side_effect=AssertionError("tick must not poll")):
            self.rig.svc.tick(refresh_chrony=True, poll_pps=False)

    def test_standalone_tick_still_polls(self):
        with mock.patch.object(self.rig.monitor, "poll", wraps=self.rig.monitor.poll) as p:
            self.rig.svc.tick(refresh_chrony=True)
        p.assert_called_once()

    def test_the_poller_feeds_the_stability_history(self):
        rig = self.rig
        rig.tick()                                   # status known: PPS selected
        for i in range(1, 6):
            rig.t[0] += 1
            rig.seq += 1
            rig.write_assert(rig.t[0] - 0.3, rig.seq)
            rig.svc.poll_pps()
        s = rig.svc.stability.report()["series"]["seconds"]
        self.assertEqual(s["samples"], 5)
        self.assertEqual(s["pps_selected_fraction"], 1.0)

    def test_a_slow_evaluation_does_not_delay_reading_the_pps(self):
        """With the service running, a chain evaluation that blocks for a while
        must not stop the PPS from being read."""
        rig = self.rig
        clock = rig.t
        gate = threading.Event()
        real_tick = rig.svc.tick
        reads = []

        def slow_tick(*a, **k):
            if k.get("poll_pps") is False and not gate.is_set():
                gate.wait(1.5)                       # the evaluation hangs for 1.5 s
            return real_tick(*a, **k)

        def reader():
            reads.append(time.monotonic())
            return ("ok", clock[0] - 0.3, len(reads))

        rig.monitor._reader = reader
        with mock.patch.object(rig.svc, "tick", side_effect=slow_tick), \
                mock.patch.object(tc, "next_tick_delay", lambda now, interval=1.0, phase=0.25: 0.05):
            rig.svc.start(interval=0.05)
            try:
                time.sleep(0.6)
                during = len(reads)
            finally:
                gate.set()
                rig.svc.stop()
        self.assertGreaterEqual(during, 5, "the poller kept reading while the evaluation was blocked")

    def test_running_service_never_evaluates_on_the_request_thread(self):
        rig = self.rig
        with mock.patch.object(tc, "next_tick_delay", lambda now, interval=1.0, phase=0.25: 0.05):
            rig.svc.start(interval=0.05)
            try:
                first = rig.svc.latest()
                self.assertIsNotNone(first, "start() evaluates once before serving")
                with mock.patch.object(rig.svc, "tick", side_effect=AssertionError("request thread must not tick")), \
                        mock.patch.object(rig.svc, "poll_pps", side_effect=AssertionError("request thread must not poll")):
                    for _ in range(3):
                        self.assertIsNotNone(rig.svc.latest())
            finally:
                rig.svc.stop()

    def test_both_threads_stop(self):
        with mock.patch.object(tc, "next_tick_delay", lambda now, interval=1.0, phase=0.25: 0.05):
            self.rig.svc.start(interval=0.05)
            names = {t.name for t in threading.enumerate()}
            self.assertTrue({"pps-poller", "timing-chain"} <= names)
            self.rig.svc.stop()
        self.assertFalse(self.rig.svc.running())

    def test_grids(self):
        self.assertAlmostEqual((100.0 + tc.next_tick_delay(100.0, 1.0, tc.POLL_PHASE_S)) % 1.0, 0.25)
        self.assertAlmostEqual((100.0 + tc.next_tick_delay(100.0, 1.0, tc.TICK_PHASE_S)) % 1.0, 0.45)


class TestOutageDetectionUnchanged(unittest.TestCase):
    """The owner's rule: the Oct 17 outages were real; detection must not get weaker."""

    def test_loss_is_still_detected_when_the_poller_reads_the_pps(self):
        rig = Rig(debounce=30)
        self.addCleanup(rig.cleanup)
        for _ in range(60):                          # healthy, with the poller doing the reading
            rig.t[0] += 1
            rig.seq += 1
            rig.write_assert(rig.t[0] - 0.3, rig.seq)
            rig.svc.poll_pps()
            chain = rig.svc.tick(refresh_chrony=True, poll_pps=False)
        self.assertEqual(state(chain), "SELECTED")
        for _ in range(40):                          # pulses stop
            rig.t[0] += 1
            rig.svc.poll_pps()
            chain = rig.svc.tick(refresh_chrony=True, poll_pps=False)
        self.assertEqual(chain["events"]["open"]["type"], "PPS_OUTAGE")
        self.assertIn(chain["pps"]["pulse_health"], ("LOST",))

    def test_snapshot_and_diagnostics_carry_the_new_counters(self):
        rig = Rig()
        self.addCleanup(rig.cleanup)
        chain = rig.pulses(3)
        self.assertIn("unread_pulses", chain["pps"])
        self.assertIn("poller", chain["pps"])
        text = tc.diagnostic_snapshot(chain, {"mode": "hidden"})
        self.assertIn("Unread pulses", text)
        self.assertIn("never counted by the kernel", text)


if __name__ == "__main__":
    unittest.main()
