"""Boot rule (fix/pps-boot-acquiring).

Until PPS is first selected after a boot, report ACQUIRING, not an outage.
Open an outage only if PPS is not selected within 30 minutes of boot, and
backdate it to boot time. Fixtures and a manual clock only.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from tests.test_timing_chain import T0, RigTest, gnss_ok, stage, state
from gps_time_pi import timing_chain as tc

WINDOW = 1800


class TestBootRule(RigTest):
    def booted(self, ago_s=60, **kw):
        kw.setdefault("sources", "sources_failover")
        kw.setdefault("tracking", "tracking_network")
        return self.rig(boot=(T0 - ago_s, "boot-A"), **kw)

    def test_acquiring_until_window_then_outage_backdated_to_boot(self):
        r = self.booted(ago_s=60)
        boot = T0 - 60
        c = r.pulses(int((WINDOW - 60 - 30) / 15), gap=15)      # up to ~29.5 min after boot
        self.assertEqual(c["status"]["code"], "ACQUIRING")
        self.assertEqual(c["status"]["banner"], "ACQUIRING · PPS NOT YET SELECTED SINCE BOOT")
        self.assertEqual(c["status"]["underlying"]["code"], "DEGRADED")   # what disciplines the clock is still named
        self.assertIn("192.0.2.10", c["status"]["detail"])
        self.assertEqual(c["boot"]["phase"], "ACQUIRING")
        self.assertEqual(state(c), "CHRONY_VISIBLE")                    # detailed PPS state kept
        self.assertIsNone(c["events"]["open"])
        self.assertEqual(stage(c, "system_sync")["status"], "INFO")
        c = r.pulses(4, gap=15)                                         # cross the 30-minute deadline
        ev = c["events"]["open"]
        self.assertIsNotNone(ev)
        self.assertEqual(ev["start_epoch"], boot)
        self.assertEqual(ev["start_bound"], "boot")
        self.assertIn("backdated to boot", ev["notes"][0])
        self.assertEqual(c["status"]["code"], "DEGRADED")
        self.assertEqual(c["boot"]["phase"], "RUN")
        self.assertEqual(len(r.pulses(20, gap=15)["events"]["recent"]), 0)   # still one open event

    def test_first_selection_ends_acquiring_and_later_loss_uses_debounce(self):
        r = self.booted(ago_s=60)
        r.pulses(20, gap=15)                                            # 5 min acquiring
        r.sources, r.tracking = "sources_pps_selected", "tracking_pps"
        c = r.pulses(1)
        self.assertEqual(c["status"]["code"], "GPS_PPS")
        self.assertTrue(c["boot"]["pps_selected_this_boot"])
        self.assertEqual(c["boot"]["phase"], "RUN")
        r.sources, r.tracking = "sources_failover", "tracking_network"
        lost_at = r.t[0]
        c = r.silence(10)
        self.assertNotEqual(c["status"]["code"], "ACQUIRING")           # no return to ACQUIRING in this boot
        self.assertIsNone(c["events"]["open"])                          # still inside the 30 s debounce
        c = r.silence(30)
        ev = c["events"]["open"]
        self.assertGreater(ev["start_epoch"], lost_at)                  # starts at the loss, not at boot
        self.assertNotIn("start_bound", ev)

    def test_service_started_late_is_not_backdated_to_boot(self):
        r = self.booted(ago_s=2 * 3600)
        c = r.pulses(3)
        self.assertNotEqual(c["status"]["code"], "ACQUIRING")
        self.assertFalse(c["boot"]["boot_rule_applies"])
        c = r.pulses(40)
        ev = c["events"]["open"]
        self.assertEqual(ev["start_bound"], "service_start")
        self.assertGreater(ev["start_epoch"], T0 - 2 * 3600)

    def test_boot_time_unavailable_falls_back_to_debounce(self):
        r = self.rig(boot=(None, None), sources="sources_failover", tracking="tracking_network")
        c = r.pulses(3)
        self.assertNotEqual(c["status"]["code"], "ACQUIRING")
        self.assertIsNone(c["boot"]["boot_utc"])
        self.assertIsNotNone(r.pulses(40)["events"]["open"])

    def test_unsynchronized_is_never_masked_by_acquiring(self):
        r = self.booted(ago_s=30, tracking="tracking_unsync")
        c = r.pulses(3)
        self.assertEqual(c["status"]["code"], "UNSYNCHRONIZED")
        self.assertEqual(c["boot"]["phase"], "ACQUIRING")

    def test_acquiring_never_claims_gps_pps(self):
        for src in ("sources_failover", "sources_nmea_stale", "sources_holdover", "sources_nmea_selected"):
            r = self.booted(ago_s=60, sources=src, tracking="tracking_holdover_last_gps")
            st = r.pulses(3)["status"]
            self.assertNotIn("GPS/PPS · STRATUM", st["banner"], src)


class TestBootAcrossRestarts(RigTest):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="gtp-boot-")
        self.addCleanup(shutil.rmtree, self.d, True)
        self.path = os.path.join(self.d, "timing-events.json")

    def test_restart_in_same_boot_after_selection_is_not_acquiring(self):
        r = self.rig(boot=(T0 - 60, "boot-A"), events_path=self.path)
        c = r.pulses(3)
        self.assertEqual(c["status"]["code"], "GPS_PPS")
        self.assertTrue(os.path.exists(self.path))                     # first selection of this boot recorded
        # web service restarts 5 min later, same boot; PPS no longer selected
        r2 = self.rig(boot=(T0 - 60, "boot-A"), events_path=self.path,
                      sources="sources_failover", tracking="tracking_network")
        r2.t[0] = r.t[0] + 300
        c = r2.pulses(3)
        self.assertNotEqual(c["status"]["code"], "ACQUIRING")
        self.assertTrue(c["boot"]["pps_selected_this_boot"])
        self.assertIsNotNone(r2.pulses(40)["events"]["open"])          # normal debounce, not 30 min

    def test_new_boot_resets_the_selected_flag(self):
        r = self.rig(boot=(T0 - 60, "boot-A"), events_path=self.path)
        r.pulses(3)
        r2 = self.rig(boot=(T0 + 10_000, "boot-B"), events_path=self.path,
                      sources="sources_failover", tracking="tracking_network")
        r2.t[0] = T0 + 10_060
        c = r2.pulses(3)
        self.assertEqual(c["status"]["code"], "ACQUIRING")
        self.assertFalse(c["boot"]["pps_selected_this_boot"])

    def test_one_checkpoint_write_per_boot_for_selection(self):
        r = self.rig(boot=(T0 - 60, "boot-A"), events_path=self.path)
        with mock.patch.object(r.tracker, "_checkpoint", wraps=r.tracker._checkpoint) as cp:
            r.pulses(120)
        self.assertEqual(cp.call_count, 1)


class TestReadBoot(unittest.TestCase):
    def test_reads_uptime_and_boot_id(self):
        d = tempfile.mkdtemp(prefix="gtp-proc-")
        self.addCleanup(shutil.rmtree, d, True)
        Path(d, "uptime").write_text("3605.42 7000.10\n")
        Path(d, "boot_id").write_text("5c1a7c39-1111-2222-3333-444455556666\n")
        epoch, bid = tc.read_boot(os.path.join(d, "uptime"), os.path.join(d, "boot_id"), clock=lambda: T0)
        self.assertAlmostEqual(epoch, T0 - 3605.42)
        self.assertEqual(bid, "5c1a7c39-1111-2222-3333-444455556666")
        self.assertEqual(tc.read_boot(os.path.join(d, "missing"), os.path.join(d, "boot_id")), (None, None))
        epoch, bid = tc.read_boot(os.path.join(d, "uptime"), os.path.join(d, "missing"), clock=lambda: T0)
        self.assertIsNotNone(epoch)
        self.assertIsNone(bid)


class TestApiOverlay(unittest.TestCase):
    def test_overlay_applies_only_while_acquiring(self):
        base = tc.timing_status({"Leap status": "Normal", "Stratum": "3"},
                                [{"mode": "^", "state": "*", "name": "192.0.2.10", "stratum": 2}],
                                gnss=gnss_ok(), refclocks=None)
        acq = {"phase": "ACQUIRING", "since_boot_s": {"value": 300}, "acquire_window_s": WINDOW}
        self.assertEqual(tc.acquiring_status(base, acq)["code"], "ACQUIRING")
        self.assertIs(tc.acquiring_status(base, dict(acq, phase="RUN")), base)
        gps = dict(base, code="GPS_PPS")
        self.assertIs(tc.acquiring_status(gps, acq), gps)


if __name__ == "__main__":
    unittest.main()
