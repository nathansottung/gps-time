"""PPS timing chain (docs/specs/CHG-PPS-HEALTH-DIAGNOSTICS.md, TASK-PPS-CHAIN.md).

Tests 01-20 follow the numbered list in the CHG spec; test 21 is the extra
"NMEA refclock stale while PPS pulses arrive" case from the task. Everything
runs on fixtures: a temporary sysfs tree written by the test, captured
`chronyc -n` output under tests/fixtures/chrony, and a manual clock. No live
GNSS, chrony, Internet or root is needed.
"""

import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from tests import _env
from gps_time_pi import chrony, config, demo, labels, pps, timing_chain as tc

FIX = Path(__file__).parent / "fixtures" / "chrony"
T0 = 1_790_000_000.0
FORBIDDEN = ("JAMMING", "SPOOF", "INTERFERENCE", "ANTENNA")
REFCFG = {"pps": {"driver": "PPS", "param": "/dev/pps0", "refid": "GPS", "lock": "NMEA",
                  "noselect": False, "prefer": True, "poll": None},
          "nmea": {"driver": "SHM", "param": "0", "refid": "NMEA", "lock": None,
                   "noselect": True, "prefer": False, "poll": None},
          "source": "chrony.conf"}


def gnss_ok():
    sats = [{"id": i, "gnss": "GPS", "snr": s, "used": i < 9}
            for i, s in enumerate([43, 41, 38, 36, 34, 32, 31, 29, 27, 22])]
    return {"data_age_s": 0.5, "stale": False, "sky_stale": False, "sky_age_s": 0.5, "fix": "3D",
            "sats": sats, "tdop": 0.73, "hdop": 0.9,
            "live": {"lat": 38.9217123, "lon": -77.0669456, "alt_msl": 92.0, "alt_hae": 59.0}}


def gnss_no_signal():   # receiver talking, but no fix and nothing tracked
    sats = [{"id": i, "gnss": "GPS", "snr": 0, "used": False} for i in range(6)]
    return {"data_age_s": 0.5, "stale": False, "sky_stale": False, "sky_age_s": 0.5, "fix": None,
            "sats": sats, "tdop": None, "live": None}


def gnss_stale():
    return {"data_age_s": 45.0, "stale": True, "sky_stale": True, "sky_age_s": 45.0, "fix": None,
            "sats": [], "tdop": None, "live": None}


class Rig:
    """A TimingChainService wired to a temp sysfs tree, fixture chronyc output and a manual clock."""

    def __init__(self, sources="sources_pps_selected", tracking="tracking_pps", gnss=gnss_ok,
                 device=True, events_path=None, debounce=30, sysfs_root=True, refcfg=REFCFG,
                 boot=(T0 - 7200, "boot-test")):
        # default: service started 2 h after boot, so the post-boot ACQUIRING rule does not apply
        self.tmp = tempfile.mkdtemp(prefix="gtp-pps-")
        self.t = [T0]
        self.seq = 0
        self.sources, self.tracking, self.gnss = sources, tracking, gnss
        self.refcfg = refcfg
        root = os.path.join(self.tmp, "sys", "class", "pps")
        self.sysfs = os.path.join(root, "pps0")
        self.dev = os.path.join(self.tmp, "dev", "pps0")
        if sysfs_root:
            os.makedirs(root)
        if device:
            os.makedirs(self.sysfs)
            os.makedirs(os.path.dirname(self.dev))
            Path(self.dev).touch()
            Path(self.sysfs, "name").write_text("pps@12.-1\n")
            self.write_assert(0.0, 0)
        self.clock = lambda: self.t[0]
        self.monitor = pps.PPSMonitor(device=self.dev, sysfs=self.sysfs, clock=self.clock)
        self.tracker = tc.EventTracker(events_path, clock=self.clock, debounce_s=debounce, boot=boot)
        self.svc = tc.TimingChainService(
            monitor=self.monitor, tracker=self.tracker, chrony_reader=self.read_chrony,
            gnss_reader=lambda: self.gnss(), refclock_reader=lambda: self.refcfg,
            boot_config_reader=lambda: {"gpio": 18, "assert_edge": "rising", "source": "fixture"},
            clock=self.clock)

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_assert(self, ts, seq):
        Path(self.sysfs, "assert").write_text(f"{ts:.9f}#{seq}\n")

    def read_chrony(self):
        if self.sources is None:
            return {"tracking_ok": False, "tracking_text": "", "sources_ok": False,
                    "sources_text": "", "sourcestats_ok": False, "sourcestats_text": ""}
        return {"tracking_ok": True, "tracking_text": (FIX / f"{self.tracking}.txt").read_text(),
                "sources_ok": True, "sources_text": (FIX / f"{self.sources}.txt").read_text(),
                "sourcestats_ok": True, "sourcestats_text": (FIX / "sourcestats.txt").read_text()}

    def tick(self):
        return self.svc.tick(refresh_chrony=True)

    def pulses(self, n, gap=1.0):
        chain = None
        for _ in range(n):
            self.t[0] += gap
            self.seq += 1
            self.write_assert(self.t[0] - 0.3, self.seq)   # kernel stamp 0.3 s before the poll
            chain = self.tick()
        return chain

    def silence(self, seconds, step=1.0):
        chain = None
        for _ in range(int(seconds / step)):
            self.t[0] += step
            chain = self.tick()
        return chain


def state(chain):
    return chain["pps_state"]["value"]


def stage(chain, sid):
    return next(s for s in chain["stages"] if s["id"] == sid)


class RigTest(unittest.TestCase):
    def rig(self, **kw):
        r = Rig(**kw)
        self.addCleanup(r.cleanup)
        return r

    def assertNoCauseClaims(self, chain):
        text = json.dumps(chain).upper()
        for word in FORBIDDEN:
            self.assertNotIn(word, text)


# ── 01-09: device, pulses, chrony views ─────────────────────────────────────

class TestPPSStates(RigTest):
    def test_01_device_absent(self):
        r = self.rig(device=False)
        c = r.tick()
        self.assertEqual(state(c), "DEVICE_MISSING")
        self.assertEqual(c["pps"]["pulse_health"], "MISSING")
        self.assertEqual(stage(c, "pps_device")["status"], "FAILED")
        self.assertEqual(c["classification"]["classification"], "PPS DEVICE MISSING")

    def test_01b_pps_subsystem_not_observable_is_unknown(self):
        r = self.rig(device=False, sysfs_root=False)
        c = r.tick()
        self.assertEqual(c["pps"]["pulse_health"], "UNKNOWN")
        self.assertEqual(stage(c, "pps_device")["status"], "UNKNOWN")

    def test_02_device_present_no_events(self):
        r = self.rig(sources="sources_failover", tracking="tracking_network")
        c = r.tick()
        self.assertEqual(state(c), "DEVICE_PRESENT_NO_EVENTS")
        self.assertEqual(c["pps"]["pulse_health"], "NO_EVENTS")
        self.assertEqual(stage(c, "kernel_events")["status"], "FAILED")

    def test_03_healthy_1hz(self):
        r = self.rig()
        c = r.pulses(10)
        p = c["pps"]
        self.assertEqual(p["pulse_health"], "HEALTHY")
        self.assertAlmostEqual(p["rate_hz"]["value"], 1.0, places=6)
        self.assertEqual(p["missed_pulses"]["value"], 0)
        self.assertEqual(p["consecutive_pulses"]["value"], 10)
        self.assertAlmostEqual(p["interval_stats"]["value"]["mean"], 1.0, places=6)
        self.assertEqual(p["interval_stats"]["provenance"], "calculated")
        self.assertEqual(p["last_event_utc"]["provenance"], "observed")
        self.assertIn("not receiver or electrical", p["measurement_layer"])
        self.assertEqual(state(c), "SELECTED")

    def test_04_single_missed_pulse(self):
        r = self.rig()
        r.pulses(5)
        r.t[0] += 2.0                      # no new pulse yet: 2.3 s since the last one
        c = r.tick()
        self.assertEqual(c["pps"]["pulse_health"], "DEGRADED")
        self.assertNotEqual(state(c), "LOST")
        r.seq += 1
        r.write_assert(r.t[0] - 0.3, r.seq)   # next pulse arrives 2 s after the previous one
        c = r.tick()
        self.assertEqual(c["pps"]["missed_pulses"]["value"], 1)
        self.assertEqual(c["pps"]["consecutive_pulses"]["value"], 1)
        self.assertEqual(c["pps"]["pulse_health"], "HEALTHY")

    def test_05_sustained_loss(self):
        r = self.rig()
        r.pulses(5)
        c = r.silence(10)
        self.assertEqual(state(c), "LOST")
        self.assertEqual(c["pps"]["pulse_health"], "LOST")
        self.assertEqual(stage(c, "kernel_events")["status"], "FAILED")

    def test_06_recovery(self):
        r = self.rig(sources="sources_failover", tracking="tracking_network")
        r.pulses(5)
        r.silence(10)
        r.sources = "sources_recovering"
        c = r.pulses(3)
        self.assertEqual(state(c), "RECOVERING")
        r.sources, r.tracking = "sources_pps_selected", "tracking_pps"
        c = r.pulses(1)
        self.assertEqual(state(c), "SELECTED")

    def test_07_visible_but_rejected(self):
        r = self.rig(sources="sources_pps_rejected", tracking="tracking_network")
        c = r.pulses(5)
        self.assertEqual(state(c), "CHRONY_REJECTED")
        pps_src = c["chrony"]["pps"]
        self.assertEqual(pps_src["state_symbol"]["value"], "x")
        self.assertEqual(pps_src["state_meaning"], chrony.STATE_MEANING["x"])
        cl = c["classification"]
        self.assertEqual(cl["classification"], "PPS NOT USED BY CHRONY")
        # reports chrony's symbol meaning, invents no further reason
        self.assertTrue(any("falseticker" in n for n in cl["notes"]))
        self.assertNotIn("lock_reference_stale", cl.get("evidence", {}))

    def test_08_accepted_not_selected(self):
        r = self.rig(sources="sources_pps_accepted", tracking="tracking_network")
        c = r.pulses(5)
        self.assertEqual(state(c), "CHRONY_ACCEPTED")
        self.assertEqual(stage(c, "chrony_pps_accepted")["status"], "OK")
        self.assertEqual(stage(c, "chrony_pps_selected")["status"], "FAILED")
        self.assertNotIn("GPS/PPS · STRATUM", c["status"]["banner"])

    def test_09_selected_normally(self):
        r = self.rig()
        c = r.pulses(5)
        self.assertEqual(state(c), "SELECTED")
        self.assertEqual(c["status"]["code"], "GPS_PPS")
        self.assertEqual(c["status"]["banner"], "SYNCHRONIZED · GPS/PPS · STRATUM 1")
        self.assertIsNone(c["classification"])
        self.assertIsNone(c["events"]["open"])
        self.assertTrue(all(s["status"] in ("OK", "NOT_OBSERVABLE", "NOT_APPLICABLE") for s in c["stages"]))


# ── 10-16: classification, failover, events ─────────────────────────────────

class TestOutages(RigTest):
    def lose_pps(self, r, **after):
        r.pulses(5)
        for k, v in after.items():
            setattr(r, k, v)
        return r.silence(40)

    def test_10_gnss_healthy_while_pps_fails(self):
        r = self.rig()
        c = self.lose_pps(r, sources="sources_failover", tracking="tracking_network")
        self.assertEqual(c["classification"]["classification"], "PPS PATH ANOMALY")
        self.assertEqual(c["status"]["banner"], "DEGRADED · GNSS HEALTHY · PPS NOT SELECTED")
        self.assertEqual(c["events"]["open"]["classification"], "PPS PATH ANOMALY")
        self.assertEqual(c["events"]["open"]["classification_provenance"], "inferred")
        self.assertNoCauseClaims(c)

    def test_11_gnss_and_pps_fail_together(self):
        r = self.rig()
        c = self.lose_pps(r, sources="sources_failover", tracking="tracking_network", gnss=gnss_no_signal)
        self.assertEqual(c["classification"]["classification"], "GNSS RECEPTION ANOMALY")
        self.assertIn("does not establish a cause", " ".join(c["classification"]["notes"]))
        self.assertNoCauseClaims(c)

    def test_12_network_failover_after_pps_loss(self):
        r = self.rig()
        c = self.lose_pps(r, sources="sources_failover", tracking="tracking_network", gnss=gnss_stale)
        st = c["status"]
        self.assertEqual(st["code"], "NETWORK_FAILOVER")
        self.assertIn("NETWORK FAILOVER", st["banner"])
        self.assertIn("192.0.2.10", st["detail"])
        self.assertEqual(st["source"]["name"], "192.0.2.10")
        dur = stage(c, "failover_duration")["evidence"]["duration_s"]
        self.assertEqual(dur["provenance"], "calculated")
        self.assertGreaterEqual(dur["value"], 40 - 30 - 1)

    def test_13_return_from_failover_to_pps(self):
        r = self.rig()
        self.lose_pps(r, sources="sources_failover", tracking="tracking_network", gnss=gnss_stale)
        r.gnss = gnss_ok
        r.sources = "sources_recovering"
        r.pulses(4)
        r.sources, r.tracking = "sources_pps_selected", "tracking_pps"
        c = r.pulses(1)
        self.assertEqual(c["status"]["code"], "GPS_PPS")
        self.assertIsNone(c["events"]["open"])
        rec = c["events"]["recent"][0]["recovery"]
        # pulses returned on the first of 4 recovering ticks; PPS selected on the 5th tick
        self.assertAlmostEqual(rec["time_to_select_s"]["value"], 4.0, places=1)
        self.assertAlmostEqual(rec["time_to_accept_s"]["value"], 4.0, places=1)
        self.assertEqual(rec["fallback_sources"], ["192.0.2.10"])

    def test_14_outage_event_created_once(self):
        r = self.rig()
        r.pulses(5)                                  # PPS selected
        r.sources, r.tracking = "sources_failover", "tracking_network"
        with mock.patch.object(r.tracker, "_checkpoint") as cp:
            r.silence(300)
        self.assertIsNotNone(r.tracker.open)
        self.assertEqual(r.tracker.recent, [])
        self.assertLessEqual(cp.call_count, 3)       # open + classification change at most; no 1 Hz writes

    def test_15_outage_event_closed(self):
        r = self.rig()
        r.pulses(5)                                  # PPS selected
        start_after = r.t[0]
        r.sources, r.tracking = "sources_failover", "tracking_network"
        r.silence(100)
        r.sources, r.tracking = "sources_pps_selected", "tracking_pps"
        c = r.pulses(1)
        ev = c["events"]["recent"][0]
        self.assertFalse(ev["open"])
        self.assertIsNotNone(ev["end_utc"])
        self.assertAlmostEqual(ev["duration_s"], r.t[0] - ev["start_epoch"], delta=1)
        self.assertGreaterEqual(ev["start_epoch"], start_after)
        self.assertEqual(len(c["events"]["recent"]), 1)

    def test_16_duration_survives_restart(self):
        path = os.path.join(tempfile.mkdtemp(prefix="gtp-ev-"), "timing-events.json")
        self.addCleanup(shutil.rmtree, os.path.dirname(path), True)
        r = self.rig(sources="sources_failover", tracking="tracking_network", events_path=path)
        r.pulses(5)
        r.silence(100)
        start = r.tracker.open["start_epoch"]
        self.assertTrue(os.path.exists(path))
        # restart one hour later: a new tracker reads the checkpoint
        later = [r.t[0] + 3600]
        t2 = tc.EventTracker(path, clock=lambda: later[0], debounce_s=30, boot=(T0 - 7200, "boot-test"))
        self.assertEqual(t2.open["start_epoch"], start)
        self.assertEqual(len(t2.open["restarts"]), 1)
        r2 = self.rig(sources="sources_pps_selected", tracking="tracking_pps", events_path=None)
        r2.t = later
        r2.svc.tracker = t2
        r2.tracker = t2
        r2.monitor.clock = r2.svc.clock = lambda: later[0]
        c = r2.pulses(1)
        ev = c["events"]["recent"][0]
        self.assertAlmostEqual(ev["duration_s"], later[0] - start, delta=2)
        self.assertIn("end_bounds_utc", ev["recovery"])

    def test_16b_corrupt_checkpoint_is_quarantined_not_lost(self):
        d = tempfile.mkdtemp(prefix="gtp-ev-")
        self.addCleanup(shutil.rmtree, d, True)
        path = os.path.join(d, "timing-events.json")
        Path(path).write_text('{"open": {"start')
        t = tc.EventTracker(path, clock=lambda: T0)
        self.assertIsNone(t.open)
        self.assertTrue(any(n.startswith("timing-events.json.corrupt-") for n in os.listdir(d)))


# ── 17-21: snapshot, privacy, demo, banner honesty, NMEA stale ──────────────

class TestReporting(RigTest):
    def test_17_diagnostic_snapshot_contains_state(self):
        r = self.rig(sources="sources_failover", tracking="tracking_network")
        r.pulses(5)
        c = r.silence(60)
        text = tc.diagnostic_snapshot(c, {"mode": "hidden", "lat": None, "lon": None})
        for expected in ("DEGRADED · GNSS HEALTHY · PPS NOT SELECTED", "PPS state: LOST",
                         "Pulse health: LOST", "Selected source: 192.0.2.10", "PPS source status: VISIBLE_NO_SAMPLES",
                         "PPS_OUTAGE", "PPS PATH ANOMALY", "Configured GPIO: 18", "RAW chronyc -n sources",
                         "^* 192.0.2.10"):
            self.assertIn(expected, text)

    def test_18_privacy_mode_does_not_leak_coordinates(self):
        r = self.rig()
        c = r.pulses(3)
        blob = json.dumps(c)
        self.assertNotIn("38.92", blob)          # chain never carries position
        self.assertNotIn("77.06", blob)
        live = gnss_ok()["live"]
        hidden = tc.diagnostic_snapshot(c, config.displayed_location({"location_display": "hidden"}, live))
        rounded = tc.diagnostic_snapshot(c, config.displayed_location({"location_display": "rounded"}, live))
        exact = tc.diagnostic_snapshot(c, config.displayed_location({"location_display": "exact"}, live))
        self.assertIn("Hidden (privacy mode)", hidden)
        self.assertNotIn("38.9", hidden)
        self.assertIn("38.9", rounded)
        self.assertNotIn("38.92", rounded)
        self.assertIn("38.9217", exact)

    def test_19_demo_mode_still_works(self):
        from gps_time_pi import server
        cfg_path = os.path.join(_env.TMP, "demo-config.json")
        Path(cfg_path).write_text(json.dumps({"location_display": "hidden"}))
        with mock.patch.object(server, "DEMO_MODE", True), \
                mock.patch.object(config, "_PATH", cfg_path), mock.patch.object(config, "_CACHE", None):
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            self.addCleanup(httpd.server_close)
            self.addCleanup(httpd.shutdown)
            base = f"http://127.0.0.1:{httpd.server_address[1]}"
            expect = {"pps_selected": "GPS_PPS", "pps_path_anomaly": "DEGRADED", "network_failover": "NETWORK_FAILOVER",
                      "holdover": "HOLDOVER", "chrony_unknown": "UNKNOWN", "recovering": "DEGRADED"}
            for scenario in demo.TIMING_SCENARIOS:
                with urllib.request.urlopen(f"{base}/api/timing-chain?scenario={scenario}", timeout=10) as resp:
                    chain = json.loads(resp.read())
                self.assertEqual(chain["demo"]["scenario"], scenario)
                if scenario in expect:
                    self.assertEqual(chain["status"]["code"], expect[scenario], scenario)
                self.assertNoCauseClaims(chain)
            with urllib.request.urlopen(f"{base}/api", timeout=10) as resp:
                self.assertTrue(json.loads(resp.read())["demo"])
            with urllib.request.urlopen(f"{base}/api/diagnostics?scenario=pps_path_anomaly", timeout=10) as resp:
                text = resp.read().decode("utf-8")
            self.assertIn("PPS PATH ANOMALY", text)
            self.assertIn("Hidden (privacy mode)", text)
            self.assertNotIn("38.92", text)

    def test_20_never_stratum1_gps_pps_unless_pps_selected(self):
        source_fixtures = sorted(p.stem for p in FIX.glob("sources_*.txt"))
        tracking_fixtures = sorted(p.stem for p in FIX.glob("tracking_*.txt"))
        checked = 0
        for refcfg in (REFCFG, {"pps": None, "source": "chrony.conf",
                                "nmea": {"driver": "SHM", "param": "0", "refid": "GPS", "lock": None}}):
            pps_refid = (refcfg["pps"] or {}).get("refid")
            for sf in source_fixtures:
                rows = chrony.parse_sources((FIX / f"{sf}.txt").read_text())
                selected = next((r["name"] for r in rows if r["state"] == "*"), None)
                for tf in tracking_fixtures:
                    trk = chrony.parse_tracking((FIX / f"{tf}.txt").read_text())
                    for g in (gnss_ok(), gnss_stale(), gnss_no_signal()):
                        st = tc.timing_status(trk, rows, gnss=g, refclocks=refcfg)
                        claims = "GPS/PPS · STRATUM" in st["banner"] or st["code"] == "GPS_PPS"
                        legacy_green = st["headline"] == "SYNCHRONIZED" and "GPS/PPS" in st["banner"]
                        pps_selected = pps_refid is not None and selected == pps_refid
                        self.assertEqual(claims, pps_selected and "Not synchronised" not in trk.get("Leap status", ""),
                                         (sf, tf, st["banner"]))
                        if legacy_green:
                            self.assertTrue(pps_selected, (sf, tf))
                        checked += 1
        self.assertGreater(checked, 200)
        # holdover trap: tracking still says GPS / stratum 1, but nothing is selected
        st = tc.timing_status(chrony.parse_tracking((FIX / "tracking_holdover_last_gps.txt").read_text()),
                              chrony.parse_sources((FIX / "sources_holdover.txt").read_text()),
                              gnss=gnss_ok(), refclocks=REFCFG)
        self.assertEqual(st["code"], "HOLDOVER")

    def test_20b_chrony_unavailable_is_unknown_not_an_outage(self):
        r = self.rig(sources=None)
        c = r.pulses(60)
        self.assertEqual(c["status"]["code"], "UNKNOWN")
        self.assertEqual(state(c), "EVENTS_PRESENT")
        self.assertEqual(c["classification"]["classification"], "UNKNOWN")
        self.assertIsNone(c["events"]["open"])           # can't tell whether PPS is used: no outage claimed
        self.assertEqual(stage(c, "chrony_pps_selected")["status"], "UNKNOWN")

    def test_21_nmea_refclock_stale_while_pps_pulses_arrive(self):
        r = self.rig(sources="sources_nmea_stale", tracking="tracking_network")
        c = r.pulses(40)
        self.assertEqual(c["pps"]["pulse_health"], "HEALTHY")
        self.assertEqual(stage(c, "kernel_events")["status"], "OK")
        self.assertEqual(c["chrony"]["nmea_status"], "STALE")
        self.assertEqual(stage(c, "nmea_refclock")["status"], "FAILED")
        self.assertEqual(state(c), "CHRONY_VISIBLE")
        cl = c["classification"]
        self.assertEqual(cl["classification"], "PPS NOT USED BY CHRONY")
        self.assertTrue(cl["evidence"]["lock_reference_stale"])
        self.assertTrue(any("lock NMEA" in n for n in cl["notes"]))
        self.assertEqual(c["events"]["open"]["classification"], "PPS NOT USED BY CHRONY")
        notes = " ".join(cl["notes"]).lower()
        for word in ("because", "caused", "due to"):
            self.assertNotIn(word, notes)        # observation, not causation
        self.assertNoCauseClaims(c)


# ── parsers and helpers ─────────────────────────────────────────────────────

class TestParsers(unittest.TestCase):
    def test_parse_sources(self):
        rows = {r["name"]: r for r in chrony.parse_sources((FIX / "sources_nmea_stale.txt").read_text())}
        self.assertEqual(rows["NMEA"]["lastrx_s"], 17 * 60)
        self.assertEqual(rows["NMEA"]["reach_int"], 0)
        self.assertIsNone(rows["GPS"]["lastrx_s"])
        net = rows["192.0.2.10"]
        self.assertEqual((net["mode"], net["state"], net["stratum"], net["poll"]), ("^", "*", 2, 6))
        self.assertAlmostEqual(net["offset_s"], 781e-6)
        self.assertAlmostEqual(net["measured_offset_s"], 822e-6)
        self.assertAlmostEqual(net["error_bound_s"], 14e-3)
        self.assertEqual(rows["198.51.100.7"]["reach_bits"], 8)

    def test_parse_sourcestats(self):
        st = chrony.parse_sourcestats((FIX / "sourcestats.txt").read_text())
        self.assertEqual(st["NMEA"]["span_s"], 480)
        self.assertAlmostEqual(st["NMEA"]["std_dev_s"], 1271e-6)
        self.assertAlmostEqual(st["GPS"]["skew_ppm"], 0.012)

    def test_parse_tracking(self):
        t = chrony.parse_tracking((FIX / "tracking_network.txt").read_text())
        self.assertEqual(t["reference_name"], "192.0.2.10")
        self.assertEqual(t["Stratum"], "3")

    def test_refclock_config_from_files(self):
        d = tempfile.mkdtemp(prefix="gtp-conf-")
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(os.path.join(d, "conf.d"))
        Path(d, "chrony.conf").write_text(
            "# comment\n! also a comment\npool 2.pool.ntp.org iburst\n"
            f"confdir {os.path.join(d, 'conf.d')}\n")
        Path(d, "conf.d", "gps.conf").write_text(
            "refclock SHM 0 refid NMEA offset 0.1 delay 0.2 noselect\n"
            "refclock PPS /dev/pps0 lock NMEA refid GPS prefer\n")
        cfg = chrony.refclock_config(os.path.join(d, "chrony.conf"))
        self.assertEqual(cfg["source"], "chrony.conf")
        self.assertEqual((cfg["pps"]["refid"], cfg["pps"]["lock"]), ("GPS", "NMEA"))
        self.assertTrue(cfg["nmea"]["noselect"])
        Path(d, "conf.d", "gps.conf").write_text("refclock PPS /dev/pps0\n")
        self.assertEqual(chrony.refclock_config(os.path.join(d, "chrony.conf"))["pps"]["refid"], "PPS0")
        self.assertEqual(chrony.refclock_config(os.path.join(d, "missing.conf"))["source"], "unavailable")

    def test_refclock_config_closes_its_files(self):
        import gc
        import warnings
        d = tempfile.mkdtemp(prefix="gtp-conf-")
        self.addCleanup(shutil.rmtree, d, True)
        Path(d, "chrony.conf").write_text("refclock PPS /dev/pps0 lock NMEA refid GPS" + chr(10))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            chrony.refclock_config(os.path.join(d, "chrony.conf"))
            gc.collect()
        self.assertEqual([w for w in caught if issubclass(w.category, ResourceWarning)], [])

    def test_tests_do_not_read_host_chrony_conf(self):
        self.assertTrue(chrony.CHRONY_CONF.startswith(_env.TMP))

    def test_read_assert_formats(self):
        d = tempfile.mkdtemp(prefix="gtp-sys-")
        self.addCleanup(shutil.rmtree, d, True)
        self.assertEqual(pps.read_assert(d)[0], "missing")
        Path(d, "assert").write_text("1790000000.000000123#42\n")
        status, ts, seq = pps.read_assert(d)
        self.assertEqual((status, seq), ("ok", 42))
        self.assertAlmostEqual(ts, 1790000000.000000123, places=6)
        Path(d, "assert").write_text("garbage")
        self.assertEqual(pps.read_assert(d)[0], "unreadable")

    def test_boot_config_gpio(self):
        d = tempfile.mkdtemp(prefix="gtp-boot-")
        self.addCleanup(shutil.rmtree, d, True)
        p = Path(d, "config.txt")
        p.write_text("enable_uart=1\ndtoverlay=pps-gpio,gpiopin=18\n")
        self.assertEqual(pps.boot_pps_config([str(p)])["gpio"], 18)
        p.write_text("dtoverlay=pps-gpio,gpiopin=4,assert_falling_edge=1\n")
        self.assertEqual(pps.boot_pps_config([str(p)])["assert_edge"], "falling")

    def test_labels_reject_unknown_provenance(self):
        self.assertEqual(labels.q(1, "s", "predicted")["provenance"], "predicted")
        with self.assertRaises(ValueError):
            labels.q(1, "s", "measured")


if __name__ == "__main__":
    unittest.main()
