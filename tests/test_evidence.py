"""Outage evidence on the SD card under a size cap (rc.9 item 2; OBS §13).

Uses the timing-chain test rig (fake sysfs, fixture chronyc output, manual
clock) to produce real outage events, and a temporary tracking log. No
hardware, chrony or network.
"""

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from tests.test_timing_chain import Rig
from gps_time_pi import evidence as ev

T0 = 1_790_000_000.0


def tline(t, offset="1.741e-07"):
    s = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t))
    return f"{s} GPS              1     10.295      0.009  {offset} N  1  1.789e-07  1.281e-08  1.000e-09  7.005e-06  2.612e-05\n"


class World:
    """A timing-chain rig with an evidence store and a tracking log in a temp directory."""

    def __init__(self, test, max_bytes=None, max_files=ev.MAX_FILES):
        self.rig = Rig(debounce=30)
        test.addCleanup(self.rig.cleanup)
        self.dir = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.log = os.path.join(self.dir, "tracking.log")
        Path(self.log).write_text("", encoding="ascii")
        self.store = ev.Store(directory=os.path.join(self.dir, "evidence"), clock=self.rig.clock,
                              max_bytes=max_bytes, max_files=max_files, tracking_files=[self.log],
                              chrony_now=lambda: {"tracking": "Reference ID : GPS", "sources": "#* GPS"})
        self.rig.svc._evidence = self.store
        patch = mock.patch.object(ev, "WINDOW_S", 60.0)      # a 1-minute window keeps the tests short
        patch.start()
        test.addCleanup(patch.stop)

    def pulses(self, seconds, log_every=16):
        r = self.rig
        for _ in range(int(seconds)):
            r.t[0] += 1
            r.seq += 1
            r.write_assert(r.t[0] - 0.3, r.seq)
            if int(r.t[0]) % log_every == 0:
                with open(self.log, "a", encoding="ascii", newline="\n") as f:
                    f.write(tline(r.t[0]))
            r.svc.tick(refresh_chrony=True)

    def silence(self, seconds):
        r = self.rig
        r.sources, r.tracking = "sources_holdover", "tracking_holdover_last_gps"
        for _ in range(int(seconds)):
            r.t[0] += 1
            r.svc.tick(refresh_chrony=True)
        r.sources, r.tracking = "sources_pps_selected", "tracking_pps"

    def files(self):
        d = self.store.dir
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    def doc(self, name=None):
        name = name or self.files()[0]
        with open(os.path.join(self.store.dir, name), encoding="utf-8") as f:
            return json.load(f)


class TestLifecycle(unittest.TestCase):
    def test_quiet_station_writes_nothing(self):
        w = World(self)
        w.pulses(300)
        self.assertEqual(w.files(), [])

    def test_written_five_minutes_after_open_then_replaced_after_close(self):
        w = World(self)
        w.pulses(120)
        w.silence(50)                                      # opens after the 30 s debounce
        self.assertEqual(w.files(), [], "not before the window after the start")
        w.silence(30)
        self.assertEqual(len(w.files()), 1)
        first = w.doc()
        self.assertEqual(first["phase"], "open")
        self.assertTrue(first["event"]["open"])
        w.pulses(30)                                       # recovery closes the event
        self.assertEqual(w.doc()["phase"], "open", "the closed capture waits a window after the end")
        w.pulses(40)
        d = w.doc()
        self.assertEqual(len(w.files()), 1, "the closed capture replaces the open one")
        self.assertEqual(d["phase"], "closed")
        self.assertFalse(d["event"]["open"])
        self.assertIsNotNone(d["event"]["end_utc"])

    def test_contents(self):
        w = World(self)
        w.pulses(120)
        w.silence(120)
        w.pulses(100)
        d = w.doc()
        self.assertEqual(d["schema"], "gps-time.evidence/1")
        lo, hi = (time.mktime(time.strptime(x[:19], "%Y-%m-%dT%H:%M:%S")) for x in d["window_utc"])
        self.assertAlmostEqual(hi - lo, (d["event"]["duration_s"] or 0) + 120, delta=5)
        # timeline every 10 s across the window, before, during and after
        self.assertGreater(len(d["timeline"]), 15)
        states = {p["pps_state"] for p in d["timeline"]}
        self.assertIn("SELECTED", states)
        self.assertTrue(states - {"SELECTED"})
        # tracking lines only from inside the window, and some from before the start
        start = d["event"]["start_epoch"]
        self.assertTrue(d["chrony_tracking_lines"])
        first_line_t = time.mktime(time.strptime(d["chrony_tracking_lines"][0][:19], "%Y-%m-%d %H:%M:%S"))
        self.assertLess(first_line_t, start + 1e6)
        self.assertEqual(d["chrony_now"]["sources"], "#* GPS")
        self.assertIn("No position", d["privacy"])

    def test_no_position_anywhere(self):
        w = World(self)
        w.pulses(120)
        w.silence(120)
        text = json.dumps(w.doc()).lower()
        for key in ('"lat"', '"lon"', '"latitude"', '"longitude"', '"alt_hae"', '"alt_msl"', "38.92"):
            self.assertNotIn(key, text)

    def test_writes_are_one_per_phase_not_per_tick(self):
        w = World(self)
        w.pulses(120)
        with mock.patch.object(ev.Store, "write", wraps=w.store.write) as wr:
            w.silence(300)
            w.pulses(150)
        self.assertEqual(wr.call_count, 2)

    def test_restart_does_not_rewrite(self):
        w = World(self)
        w.pulses(120)
        w.silence(120)
        w.pulses(100)
        mtime = os.path.getmtime(os.path.join(w.store.dir, w.files()[0]))
        again = ev.Store(directory=w.store.dir, clock=w.rig.clock, tracking_files=[w.log])
        w.rig.svc._evidence = again
        w.pulses(30)
        self.assertEqual(os.path.getmtime(os.path.join(w.store.dir, w.files()[0])), mtime)

    def test_detection_is_unchanged(self):
        w = World(self)
        w.pulses(120)
        w.silence(60)
        self.assertIsNotNone(w.rig.svc.latest()["events"]["open"])


class TestCap(unittest.TestCase):
    def make(self, store, n, start=T0):
        for i in range(n):
            e = {"id": f"pps-outage-{int(start) + i}", "start_epoch": start + i * 1000,
                 "start_utc": "2026-09-21T14:13:20+00:00", "end_utc": None, "open": True}
            store.write(e, "open")
            os.utime(store_path(store, e["id"]), (start + i, start + i))

    def test_size_cap_removes_the_oldest(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        s = ev.Store(directory=d, clock=lambda: T0 + 10_000, max_bytes=2000, tracking_files=[])
        self.make(s, 8)
        idx = s.index()
        self.assertLessEqual(idx["total_bytes"], 2000 + 800)
        self.assertGreater(s.removed, 0)
        ids = [f["id"] for f in idx["files"]]
        self.assertIn(f"pps-outage-{int(T0) + 7}", ids, "the newest survives")
        self.assertNotIn(f"pps-outage-{int(T0)}", ids, "the oldest goes first")

    def test_file_count_cap(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        s = ev.Store(directory=d, clock=lambda: T0, max_files=3, tracking_files=[])
        self.make(s, 6)
        self.assertEqual(len(s.index()["files"]), 3)

    def test_tracking_lines_are_cut_at_the_limit(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        log = os.path.join(d, "t.log")
        Path(log).write_text("".join(tline(T0 + 16 * i) for i in range(400)), encoding="ascii")
        lines, cut = ev.tracking_lines(T0, T0 + 16 * 400, [log], limit=4000)
        self.assertTrue(cut)
        self.assertIn("lines omitted", " ".join(lines))
        self.assertLessEqual(sum(len(l) for l in lines), 4200)
        self.assertTrue(lines[0].startswith(time.strftime("%Y-%m-%d", time.gmtime(T0))))

    def test_window_filter(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        log = os.path.join(d, "t.log")
        Path(log).write_text("   Date (UTC) Time  header\n" + "".join(tline(T0 + 60 * i) for i in range(10)), encoding="ascii")
        lines, cut = ev.tracking_lines(T0 + 120, T0 + 300, [log, os.path.join(d, "missing")])
        self.assertEqual(len(lines), 4)
        self.assertFalse(cut)


class TestApi(unittest.TestCase):
    def test_ids_are_validated(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        s = ev.Store(directory=d, clock=lambda: T0, tracking_files=[])
        for bad in ("../config", "a/b", "x" * 80, "", None, "pps-outage-1.json"):
            self.assertIsNone(s.read(bad))
        self.assertIsNone(s.write({"id": "../../etc/x", "start_epoch": T0}, "open"))
        self.assertEqual(os.listdir(d), [])

    def test_routes(self):
        from gps_time_pi import server
        with mock.patch.object(server, "DEMO_MODE", True):
            idx = server.evidence_payload({})
            self.assertEqual(len(idx["files"]), 1)
            one = server.evidence_payload({"id": [idx["files"][0]["id"]]})
            self.assertEqual(one["schema"], "gps-time.evidence/1")
            self.assertFalse(server.evidence_payload({"id": ["nope"]})["available"])

    def test_live_route_uses_the_service_store(self):
        from gps_time_pi import server, timing_chain
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        fake = mock.Mock()
        fake.evidence = ev.Store(directory=d, clock=lambda: T0, tracking_files=[])
        with mock.patch.object(server, "DEMO_MODE", False), mock.patch.object(timing_chain, "service", lambda: fake):
            self.assertEqual(server.evidence_payload({})["files"], [])


def store_path(store, eid):
    return os.path.join(store.dir, eid + ".json")


if __name__ == "__main__":
    unittest.main()
