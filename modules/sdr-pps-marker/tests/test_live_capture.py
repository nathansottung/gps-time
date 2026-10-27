"""sdr-pps-marker's live path: the numpy detector, the rtl_tcp client, dwells, timed windows.

Against fakesdr.FakeRtlTcp, a synthetic rtl_tcp on 127.0.0.1 (no SDR, no Internet). The truth
is known (each connection's stream), so the tests check the files' times against it.

Needs numpy (a station dependency); skipped where it isn't installed; CI runs these in the
station's venv and fails if they are skipped.
"""

import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:          # pragma: no cover - the station venv has it
    HAVE_NUMPY = False

from gps_time_pi import obsformat
from gps_time_pi.modkit import ModuleContext
from gps_time_pi.modkit.context import CappedStorage

if HAVE_NUMPY:
    from sdr_pps_marker import detector, fast, synth
    from sdr_pps_marker.capture import MAX_COARSE_ERROR_S, Plan
    from sdr_pps_marker.fakesdr import FakeRtlTcp, Stream
    from sdr_pps_marker.rtltcp import RtlTcp, RtlTcpError
    from sdr_pps_marker.source import MarkerSource

HERE = Path(__file__).resolve().parents[1]
FIX = json.loads((HERE / "fixtures" / "scenarios.json").read_text(encoding="utf-8"))
NEEDS = unittest.skipUnless(HAVE_NUMPY, "numpy is needed (a station dependency; CI runs these in the station venv)")
FS = 240e3          # a tenth of the real rate keeps the tests quick; errors are in samples either way


def scenario_stream(sc):
    p = dict(sc["params"])
    p["drops"] = tuple(tuple(d) for d in p.get("drops", ()))
    p["missing_seconds"] = tuple(p.get("missing_seconds", ()))
    return synth.generate(sc.get("seconds", FIX["seconds"]), FIX["fs_nominal"], **p)[0]


@NEEDS
class TestFastDetector(unittest.TestCase):
    def test_same_markers_as_the_reference_detector(self):
        fs = FIX["fs_nominal"]
        for sc in FIX["scenarios"]:
            x = scenario_stream(sc)
            ref = detector.detect(x, fs)
            for block_s in (1e9, 0.37):
                got = fast.detect(np.asarray(x), fs, block_s=block_s)
                self.assertEqual(len(got), len(ref), (sc["name"], block_s))
                for a, b in zip(got, ref):
                    self.assertAlmostEqual(a.sample, b.sample, delta=1e-9)

    def test_cu8_round_trip_and_detection_from_bytes(self):
        st = Stream(FS, 1_793_026_800.3, ppm=-15.0)
        x = st.block(int(4.5 * FS))
        raw, scale = fast.as_cu8(x, 100.0)
        y = fast.cu8_to_iq(raw)
        self.assertLess(float(np.max(np.abs(y * 127.5 / scale - x))), 0.01 + 1 / scale)
        m = fast.detect_cu8(raw, FS, block_s=0.3)
        true = [(s - st.start) * st.rate for s in range(1_793_026_801, 1_793_026_805)]
        self.assertEqual(len(m), 4)
        for mk, p in zip(m, true):
            self.assertLess(abs(mk.sample - p), 0.1)


@NEEDS
class TestRtlTcpClient(unittest.TestCase):
    def setUp(self):
        self.srv = FakeRtlTcp(fs=FS)
        self.addCleanup(self.srv.close)

    def test_header_commands_and_samples(self):
        c = RtlTcp("127.0.0.1", self.srv.port)
        self.addCleanup(c.close)
        self.assertEqual((c.tuner, c.gain_steps), ("R820T", 29))
        c.tune(521e6, 2.4e6, gain_tenth_db=296)
        c.tune(88.8e6)
        data = c.read(1000)
        self.assertEqual((len(data), c.bytes_read), (1000, 1000))
        deadline = time.time() + 5
        while len(self.srv.commands) < 6 and time.time() < deadline:
            time.sleep(0.02)
        self.assertEqual([(op, v) for _k, op, v in self.srv.commands],
                         [(2, 2_400_000), (1, 521_000_000), (3, 1), (4, 296), (1, 88_800_000), (3, 0)])

    def test_not_rtl_tcp_or_not_there(self):
        s = socket.create_server(("127.0.0.1", 0))
        self.addCleanup(s.close)

        def answer():
            conn, _ = s.accept()
            conn.sendall(b"HTTP/1.1 200 OK\r\n")
            conn.close()
        threading.Thread(target=answer, daemon=True).start()
        with self.assertRaises(RtlTcpError):
            RtlTcp("127.0.0.1", s.getsockname()[1])
        free = socket.socket()
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
        free.close()
        with self.assertRaises(RtlTcpError):
            RtlTcp("127.0.0.1", port, timeout_s=1)


def run_live(srv, plan, *, keep_files=40, cycles=1, extra_cfg=None, clock=None):
    box = []

    def connect(host, port):
        c = RtlTcp(host, port)
        box.append(c)
        return c
    d = tempfile.mkdtemp()
    out = []
    cfg = {"rtl_tcp": {"port": srv.port, "sample_rate_hz": FS, "settle_s": 0.3, "cycle_s": 3600, "retry_s": 3600,
                       "keep_files": keep_files, "plan": plan}, "station_id": "test", **(extra_cfg or {})}
    ctx = ModuleContext("sdr-pps-marker", config=cfg, emit=out.append, storage=CappedStorage(d, 16 << 20),
                        timing_quality=lambda: {"state": "LOCKED", "offset_bound_s": 2e-8},
                        site=lambda: {"lat": 38.9, "lon": -77.1, "privacy": "rounded"})
    src = MarkerSource(connect=connect, clock=clock or srv.clock_for(box))
    t = threading.Thread(target=src.start, args=(ctx,), daemon=True)
    t.start()
    deadline = time.time() + 120
    while len(out) < len(plan) * cycles and time.time() < deadline:
        time.sleep(0.05)
    src.stop()
    t.join(10)
    return out, ctx, d


@NEEDS
class TestLiveCapture(unittest.TestCase):
    def setUp(self):
        self.srv = FakeRtlTcp(fs=FS, ppm=23.0, drops=[(int(FS * 7.4), 12)])
        self.addCleanup(self.srv.close)

    def test_dwells_write_timed_windows_that_match_the_truth(self):
        plan = [{"center_hz": 521e6, "dwell_s": 10, "windows": [{"at_s": 2.5, "duration_s": 0.02},
                                                                {"at_s": 4.39, "duration_s": 0.03}]},
                {"center_hz": 88.8e6, "dwell_s": 10, "windows": [{"at_s": 7.39, "duration_s": 0.03}], "label": "fm"}]
        out, ctx, d = run_live(self.srv, plan)
        vals = [o.to_dict()["values"] for o in out]
        self.assertEqual([v["state"]["value"] for v in vals], ["OK", "OK"])
        self.assertEqual([v["windows_written"]["value"] for v in vals], [2, 1])
        self.assertEqual(vals[0]["dropped_sample_events"]["value"], 1)
        self.assertAlmostEqual(vals[0]["clock_error_ppm"]["value"], 23.0, delta=0.5)
        self.assertEqual(vals[1]["label"]["value"], "fm")
        bases = sorted({n.rsplit(".sigmf-", 1)[0] for n in ctx.storage.names()})
        self.assertEqual(len(bases), 3)
        settle = int(0.3 * FS)
        # (connection, window start in the dwell, base)
        for conn, at, base in ((0, 2.5, bases[0]), (0, 4.39, bases[1]), (1, 7.39, bases[2])):
            errs, _w = obsformat.validate(f"{d}/{base}")
            self.assertEqual(errs, [], base)
            meta, data = obsformat.read(f"{d}/{base}")
            g = meta["global"]
            self.assertEqual((g["core:datatype"], g["gpstime:time_source"]), ("cu8", "pps_marker"))
            self.assertEqual(g["gpstime:position"], {"privacy": "rounded", "lat": 38.9, "lon": -77.1})
            st = self.srv.streams[conn]
            unc = g["gpstime:sample_time_uncertainty_s"]
            for c in meta["captures"]:
                if "core:datetime" not in c:
                    continue
                idx = settle + int(round(at * FS)) + c["core:sample_start"]
                true = st.true_utc(idx)
                got = obsformat.parse_ns(c["core:datetime"]) / 1e9
                # compare as offsets from a whole second (floats near 1.8e9 s lose ns)
                err = (got - int(true)) - (true - int(true))
                self.assertLess(abs(err), max(4 * unc, 5e-7), (base, err, unc))
        # the window across the drop is annotated, its samples after the drop have no time
        meta, _ = obsformat.read(f"{d}/{bases[2]}")
        labels = [a["core:label"] for a in meta["annotations"]]
        self.assertIn("samples_missing", labels)
        self.assertIn("pps_marker", labels)
        self.assertTrue(any(c.get("gpstime:time_valid") is False for c in meta["captures"]))
        # the commands each dwell sent
        cmds = [(k, op, v) for k, op, v in self.srv.commands if op == 1]
        self.assertEqual(cmds, [(0, 1, 521_000_000), (1, 1, 88_800_000)])

    def test_the_analysis_reads_the_windows(self):
        out, ctx, d = run_live(self.srv, [{"center_hz": 521e6, "dwell_s": 10,
                                           "windows": [{"at_s": 3.0, "duration_s": 0.02}]}])
        base = ctx.storage.names()[0].rsplit(".sigmf-", 1)[0]
        mod = HERE.parent / "analysis-tower-delay-check"
        if str(mod) not in sys.path:
            sys.path.insert(0, str(mod))
        from tower_delay_check.capture import Capture
        cap = Capture.read(f"{d}/{base}")
        self.assertLess(abs(complex(np.mean(cap.samples))), 0.05)            # centred, not 127.5
        self.assertAlmostEqual(cap.clock_ppm, 23.0, delta=0.5)
        meta, _ = obsformat.read(f"{d}/{base}")
        self.assertEqual(cap.time_ns(0), obsformat.parse_ns(meta["captures"][0]["core:datetime"]))

    def test_no_markers_no_files(self):
        srv = FakeRtlTcp(fs=FS, marker_amp=0.0)
        self.addCleanup(srv.close)
        out, ctx, d = run_live(srv, [{"center_hz": 521e6, "dwell_s": 6}])
        v = out[0].to_dict()["values"]
        self.assertEqual((v["state"]["value"], v["windows_written"]["value"]), ("UNKNOWN", 0))
        self.assertIn("too few PPS markers", v["state"]["note"])
        self.assertEqual(ctx.storage.names(), [])

    def test_host_clock_off_by_half_a_second_writes_nothing(self):
        srv = FakeRtlTcp(fs=FS, host_clock_error_s=0.45)
        self.addCleanup(srv.close)
        out, ctx, d = run_live(srv, [{"center_hz": 521e6, "dwell_s": 10}])
        v = out[0].to_dict()["values"]
        self.assertEqual(v["windows_written"]["value"], 0)
        self.assertIn("ambiguous", v["windows_skipped"]["note"])
        self.assertGreater(abs(v["host_clock_offset_s"]["value"]), MAX_COARSE_ERROR_S)
        self.assertEqual(ctx.storage.names(), [])

    def test_only_the_newest_windows_are_kept(self):
        plan = [{"center_hz": 521e6, "dwell_s": 10, "windows": [{"at_s": a, "duration_s": 0.01} for a in (2.0, 3.0, 5.0)]}]
        out, ctx, d = run_live(self.srv, plan, keep_files=2)
        self.assertEqual(out[0].to_dict()["values"]["windows_written"]["value"], 3)
        bases = sorted({n.rsplit(".sigmf-", 1)[0] for n in ctx.storage.names()})
        self.assertEqual(len(bases), 2)
        self.assertEqual(len(ctx.storage.names()), 4)

    def test_rtl_tcp_down_is_reported(self):
        free = socket.socket()
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
        free.close()
        out = []
        ctx = ModuleContext("sdr-pps-marker", emit=out.append, storage=CappedStorage(tempfile.mkdtemp(), 1 << 20),
                            config={"rtl_tcp": {"port": port, "retry_s": 3600, "plan": [{"center_hz": 1e8}]}})
        src = MarkerSource()
        t = threading.Thread(target=src.start, args=(ctx,), daemon=True)
        t.start()
        deadline = time.time() + 20
        while not out and time.time() < deadline:
            time.sleep(0.05)
        src.stop()
        t.join(10)
        v = out[0].to_dict()["values"]
        self.assertEqual(v["state"]["value"], "UNKNOWN")
        self.assertIn("not reachable", v["state"]["note"])

    def test_plan_from_config(self):
        p = Plan.from_config({"center_hz": 521e6})
        self.assertEqual((p.dwell_s, len(p.windows), p.windows[0].duration_s), (10.0, 1, 0.03))


if __name__ == "__main__":
    unittest.main()
