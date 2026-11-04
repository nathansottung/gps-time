"""Capped clip recording (gps_time_pi/clips.py): requests, rtl_tcp capture, SigMF with timing, the cap.

A fake rtl_tcp on the loopback streams synthetic cu8 (a 1 kHz AM tone at 240 kS/s); no dongle,
network or root. The audio tests need numpy (a station dependency): the plain run skips them and CI
runs them in the station venv, failing if they're skipped there.
"""
import json
import math
import os
import shutil
import socket
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from gps_time_pi import clips, obsformat

try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False

TQ_STATION = {"source": "refclock", "label": "refclock GPS, within ±12 µs (chrony's bound)",
              "max_error_s": {"value": 1.2e-5, "unit": "s", "provenance": "calculated"}}
TQ_NODE = {"source": "ntp", "label": "ntp from 192.0.2.10", "max_error_s": {"value": 4e-4, "unit": "s", "provenance": "calculated"}}
CFG = {"site": {"lat": 38.9217, "lon": -77.0669, "alt_msl": 92.0}, "location_display": "rounded"}


def am_tone_cu8(rate, seconds, tone_hz=1000.0):
    out = bytearray()
    for n in range(int(rate * seconds)):
        a = 0.5 * (1 + 0.6 * math.sin(2 * math.pi * tone_hz * n / rate))
        out += bytes((int(127.5 + 127 * a * math.cos(0.3 * n)), int(127.5 + 127 * a * math.sin(0.3 * n))))
    return bytes(out)


class FakeRtlTcp:
    """Sends the 12-byte header, records the 5-byte commands, then streams the given samples."""

    def __init__(self, payload):
        self.payload, self.commands = payload, []
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.addr = self.srv.getsockname()
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        conn, _ = self.srv.accept()
        conn.sendall(b"RTL0" + struct.pack(">II", 5, 29))
        conn.settimeout(0.3)
        try:
            while True:
                cmd = conn.recv(5)
                if len(cmd) < 5:
                    break
                self.commands.append(struct.unpack(">BI", cmd))
        except socket.timeout:
            pass
        try:
            conn.sendall(self.payload)
        except OSError:
            pass
        conn.close()
        self.srv.close()


class Tree(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dir = self.tmp / "clips"
        self.dir.mkdir()
        env = self.tmp / "gps-time-clips"
        env.write_text(f"GTP_CLIPS_DIR={self.dir}\nGTP_CLIPS_MAX_MB=4\n")
        p = mock.patch.object(clips, "ENVFILE", env)
        p.start()
        self.addCleanup(p.stop)
        # The temp folder stands in for a mounted drive: on another file system than /.
        real_stat = os.stat

        def fake_stat(path, *a, **k):
            st = real_stat(path, *a, **k)
            if str(path) == "/":
                return os.stat_result((st.st_mode, st.st_ino, st.st_dev + 1) + tuple(st)[3:])
            return st
        p2 = mock.patch.object(clips.os, "stat", fake_stat)
        p2.start()
        self.addCleanup(p2.stop)


class TestRequests(Tree):
    def test_validation(self):
        cap = 4 * 1024 * 1024
        ok = clips.validate({"kind": "am", "freq_hz": 119_100_000, "seconds": 10}, cap)
        self.assertEqual((ok["rate"], ok["gain_db"]), (240_000, None))
        for bad, msg in (({"kind": "fm"}, "kind"), ({"kind": "am", "freq_hz": 1e6, "seconds": 1}, "freq_hz"),
                         ({"kind": "am", "freq_hz": 1e8, "seconds": 0.5}, "seconds"),
                         ({"kind": "iq", "freq_hz": 1e8, "seconds": 1, "rate": 3_000_000}, "rate"),
                         ({"kind": "iq", "freq_hz": 1e9, "seconds": 60, "rate": 2_400_000}, "cap"),
                         ({"kind": "am", "freq_hz": 1e8, "seconds": 1, "gain_db": 99}, "gain_db")):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(clips.ClipError, msg):
                    clips.validate(bad, cap)

    def test_request_queues_and_starts_the_unit_one_at_a_time(self):
        calls = []
        run = lambda argv, **k: calls.append(argv) or mock.Mock(returncode=0, stdout="", stderr="")   # noqa: E731
        res = clips.request({"kind": "am", "freq_hz": 121_500_000, "seconds": 5}, run=run)
        self.assertTrue(res["ok"])
        self.assertEqual(calls, [["systemctl", "start", "--no-block", "gps-time-clip.service"]])
        self.assertEqual(json.loads((self.dir / ".pending.json").read_text())["freq_hz"], 121_500_000)
        with self.assertRaisesRegex(clips.ClipError, "already being recorded"):
            clips.request({"kind": "am", "freq_hz": 121_500_000, "seconds": 5}, run=run)

    def test_a_unit_that_wont_start_leaves_no_request(self):
        run = lambda argv, **k: mock.Mock(returncode=1, stdout="", stderr="Unit not found")   # noqa: E731
        with self.assertRaisesRegex(clips.ClipError, "Unit not found"):
            clips.request({"kind": "am", "freq_hz": 121_500_000, "seconds": 5}, run=run)
        self.assertFalse((self.dir / ".pending.json").exists())


class TestStorage(unittest.TestCase):
    def test_never_the_sd_card(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        self.assertIn("SD card", clips.storage_problem(d, root=d))
        self.assertIn("doesn't exist", clips.storage_problem(os.path.join(d, "nope")))

    def test_the_cap_drops_the_oldest(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        for i in range(4):
            for ext in ("sigmf-data", "sigmf-meta"):
                p = d / f"clip{i}.{ext}"
                p.write_bytes(b"x" * 500)
                os.utime(p, (1000 + i, 1000 + i))
        self.assertEqual(clips.enforce_cap(d, 2500), ["clip0", "clip1"])
        self.assertEqual(sorted(clips._clip_files(d)), ["clip2", "clip3"])


class TestRecord(Tree):
    def test_iq_clip_is_valid_sigmf_with_the_stations_timing(self):
        payload = bytes(range(256)) * 10600                    # 2.7 MB: 0.25 s settle + 1 s at 1.024 MS/s (2.56 MB)
        fake = FakeRtlTcp(payload)
        req = clips.validate({"kind": "iq", "freq_hz": 1_090_000_000, "seconds": 1, "rate": 1_024_000}, 4 << 20)
        cap = lambda f, r, s, g: clips.capture(f, r, s, g, addr=fake.addr)   # noqa: E731
        base, meta = clips.record(req, self.dir, cfg=CFG, tq=TQ_STATION, cap=cap, signer_info=("teststation", None),
                                  max_bytes=4 << 20)
        self.assertIn((0x02, 1_024_000), fake.commands)
        self.assertIn((0x01, 1_090_000_000), fake.commands)
        self.assertIn((0x03, 0), fake.commands)                  # automatic gain
        errs, _warn = obsformat.validate(base)
        self.assertEqual(errs, [])
        g = meta["global"]
        self.assertEqual((g["core:datatype"], g["gpstime:time_source"], g["gpstime:time_offset_bound_s"]), ("cu8", "pps", 1.2e-5))
        self.assertGreaterEqual(g["gpstime:sample_time_uncertainty_s"], 0.1)       # 256 KiB / 2.048 MB/s
        self.assertEqual(g["gpstime:position"]["privacy"], "rounded")
        self.assertEqual(g["gpstime:position"]["lat"], 38.9)
        self.assertEqual(Path(str(base) + ".sigmf-data").stat().st_size, 2_048_000)

    def test_a_nodes_clip_is_labelled_ntp(self):
        fake = FakeRtlTcp(bytes(2_700_000))
        req = clips.validate({"kind": "iq", "freq_hz": 100_000_000, "seconds": 1, "rate": 1_024_000}, 4 << 20)
        _b, meta = clips.record(req, self.dir, cfg={"location_display": "hidden"}, tq=TQ_NODE,
                                cap=lambda f, r, s, g: clips.capture(f, r, s, g, addr=fake.addr), signer_info=("node", None))
        self.assertEqual(meta["global"]["gpstime:time_source"], "ntp")
        self.assertEqual(meta["global"]["gpstime:position"], {"privacy": "hidden", "lat": None, "lon": None, "alt_m": None})

    def test_a_busy_rtl_tcp_is_said_so(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        addr = srv.getsockname()

        def close_at_once():
            c, _ = srv.accept()
            c.close()
            srv.close()
        threading.Thread(target=close_at_once, daemon=True).start()
        with self.assertRaisesRegex(clips.ClipError, "busy"):
            clips.capture(100_000_000, 1_024_000, 1, addr=addr)

    @unittest.skipUnless(HAVE_NUMPY, "numpy is needed (a station dependency; CI runs these in the station venv)")
    def test_am_audio_carries_the_tone(self):
        import numpy as np
        rate = clips.AUDIO_IN
        fake = FakeRtlTcp(am_tone_cu8(rate, clips.SETTLE_S + 1.1))
        req = clips.validate({"kind": "am", "freq_hz": 121_500_000, "seconds": 1}, 4 << 20)
        base, meta = clips.record(req, self.dir, cfg=CFG, tq=TQ_STATION,
                                  cap=lambda f, r, s, g: clips.capture(f, r, s, g, addr=fake.addr), signer_info=("t", None))
        self.assertEqual((meta["global"]["core:datatype"], meta["global"]["core:sample_rate"]), ("ri16_le", 48_000.0))
        pcm = np.frombuffer(Path(str(base) + ".sigmf-data").read_bytes(), dtype="<i2").astype(float)
        spec = np.abs(np.fft.rfft(pcm * np.hanning(len(pcm))))
        peak_hz = np.argmax(spec[10:]) + 10
        self.assertAlmostEqual(peak_hz * 48_000 / len(pcm), 1000, delta=20)
        name, ctype, body = clips.file_for(base.name, "wav")
        self.assertEqual((ctype, body[:4], body[8:12]), ("audio/wav", b"RIFF", b"WAVE"))
        self.assertEqual(struct.unpack("<I", body[24:28])[0], 48_000)


class TestApi(Tree):
    def test_status_lists_clips_and_storage(self):
        fake = FakeRtlTcp(bytes(2_700_000))
        req = clips.validate({"kind": "iq", "freq_hz": 100_000_000, "seconds": 1, "rate": 1_024_000}, 4 << 20)
        base, _m = clips.record(req, self.dir, cfg=CFG, tq=TQ_STATION,
                                cap=lambda f, r, s, g: clips.capture(f, r, s, g, addr=fake.addr), signer_info=("t", None))
        st = clips.status()
        self.assertEqual(st["storage"]["kind"], "custom")
        self.assertIsNone(st["storage"]["problem"])
        (row,) = st["clips"]
        self.assertEqual((row["name"], row["kind"], row["freq_hz"], row["seconds"], row["time_source"]),
                         (base.name, "iq", 100_000_000.0, 1.0, "pps"))
        self.assertEqual(row["files"], ["sigmf-meta", "sigmf-data"])

    def test_downloads_refuse_anything_but_a_clip(self):
        for name, ext in (("../config", "sigmf-meta"), ("x", "exe"), ("nope", "sigmf-meta"), ("", "wav"), (None, "wav")):
            with self.subTest(name=name, ext=ext):
                with self.assertRaises(clips.ClipError) as e:
                    clips.file_for(name, ext)
                self.assertEqual(e.exception.code, 404)

    def test_delete(self):
        (self.dir / "a.sigmf-meta").write_text("{}")
        (self.dir / "a.sigmf-data").write_bytes(b"")
        self.assertEqual(clips.delete("a"), {"ok": True, "deleted": "a"})
        self.assertEqual(list(self.dir.iterdir()), [])
        with self.assertRaises(clips.ClipError):
            clips.delete("../a")


class TestWiring(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_the_unit_reaches_localhost_only_and_writes_ram_only(self):
        u = (self.ROOT / "system" / "gps-time-clip.service").read_text(encoding="utf-8")
        self.assertIn("IPAddressAllow=localhost", u)
        self.assertIn("\nIPAddressDeny=any\n", u)
        self.assertIn("ReadWritePaths=-/run/gps-time-clips\n", u)
        self.assertNotIn("[Install]", u)

    def test_the_script_refuses_a_folder_outside_mnt_media_srv(self):
        s = (self.ROOT / "scripts" / "clips.sh").read_text(encoding="utf-8")
        self.assertIn("^/(mnt|media|srv)/", s)
        self.assertIn('[ "$(stat -c %d "$ROOT$DIR")" != "$(stat -c %d "$ROOT/")" ]', s)


if __name__ == "__main__":
    unittest.main()
