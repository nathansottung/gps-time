"""Converters: observation files to WAV (with a SigMF sidecar) and miniSEED 2. No hardware or network."""

import io
import json
import shutil
import struct
import tempfile
import unittest
import wave
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tests import _env  # noqa: F401
from gps_time_pi import convert as cv
from gps_time_pi import obsformat as of

T0 = 1_792_602_000 * 1_000_000_000 + 123_456_789   # 2026-10-21T17:00:00.123456789Z


def gpstime(sensor="infrasound", time_source="pps", **over):
    g = {"station_id": "test-station", "sensor": sensor, "quantity": "pressure", "unit": "Pa",
         "channels": [{"name": "p"}], "time_source": time_source, "time_offset_bound_s": 2e-6,
         "sample_time_uncertainty_s": 1e-6, "frequency_reference": {"state": "free", "error_ppm": None},
         "calibration": None, "position": {"privacy": "hidden", "lat": None, "lon": None},
         "provenance": "observed", "request_id": None, "licence": "CC-BY-4.0"}
    g.update(over)
    return g


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def write(self, name, datatype, samples, captures, rate=100.0, **g):
        meta = of.build_meta(datatype=datatype, sample_rate=rate, captures=captures, gpstime=gpstime(**g),
                             recorder="test")
        base = self.dir / name
        of.write(base, meta, of.encode(samples, datatype))
        self.assertEqual(of.validate(base)[0], [])
        return base


class TestBtime(unittest.TestCase):
    def test_known_time(self):
        bt, usec = cv.btime(T0)
        self.assertEqual(struct.unpack(">HHBBBBH", bt), (2026, 294, 17, 0, 0, 0, 1235))
        self.assertEqual(usec, -44)          # .1235 s - 44 µs = .123456 s

    def test_rounding_carries_into_the_second(self):
        bt, usec = cv.btime(1_792_602_000 * 10**9 + 999_990_000)   # .99999 s
        self.assertEqual(struct.unpack(">HHBBBBH", bt)[4:], (1, 0, 0))
        self.assertEqual(usec, -10)


class TestWav(Base):
    def test_real_samples_round_trip_with_exact_times(self):
        samples = [0.5 * ((i % 40) - 20) / 20 for i in range(1000)]
        caps = [{"core:sample_start": 0, "gpstime:time_valid": False},
                {"core:sample_start": 100, "core:datetime": of.format_ns(T0), "gpstime:sample_rate": 100.002}]
        base = self.write("mic", "rf32_le", samples, caps, sensor="audio")
        wav_path, meta_path = cv.to_wav(base, self.dir / "mic-wav")
        with wave.open(str(wav_path)) as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()), (1, 2, 100, 1000))
        out = self.dir / "mic-wav"
        errs, warns = of.validate(out)
        self.assertEqual(errs, [])
        self.assertIn("unsigned", warns)
        m_src, _ = of.read(base)
        m_out, d_out = of.read(out)
        for j in (50, 100, 555, 999):
            self.assertEqual(of.sample_time(m_out, j), of.sample_time(m_src, j))
        g = m_out["global"]
        self.assertEqual((g["core:dataset"], g["core:datatype"]), ("mic-wav.wav", "ri16_le"))
        self.assertEqual(g["gpstime:derived_from"]["checksum"], m_src["global"]["gpstime:checksum"])
        scale = g["gpstime:calibration"]["wav_scale"]
        back = of.decode(d_out, "ri16_le")
        self.assertLess(max(abs(b / scale - a) for a, b in zip(samples, back)), 1 / scale)

    def test_iq_is_stereo(self):
        samples = [complex(0.1 * (i % 7), -0.05 * (i % 5)) for i in range(300)]
        base = self.write("iq", "cf32_le", samples,
                          [{"core:sample_start": 0, "core:datetime": of.format_ns(T0), "core:frequency": 100.1e6}],
                          rate=2400.0, sensor="rf")
        wav_path, _ = cv.to_wav(base, self.dir / "iq-wav")
        with wave.open(str(wav_path)) as w:
            self.assertEqual((w.getnchannels(), w.getnframes()), (2, 300))
        meta, data = of.read(self.dir / "iq-wav")
        self.assertEqual(meta["global"]["core:datatype"], "ci16_le")
        self.assertEqual(of.validate(self.dir / "iq-wav")[0], [])

    def test_cu8_is_recentred(self):
        base = self.write("rtl", "cu8", [complex(128, 127), complex(255, 0)],
                          [{"core:sample_start": 0, "core:datetime": of.format_ns(T0), "core:frequency": 1e8}],
                          rate=2.0, sensor="rf")
        cv.to_wav(base, self.dir / "rtl-wav")
        meta, data = of.read(self.dir / "rtl-wav")
        self.assertEqual(of.decode(data, "ci16_le"), [complex(128, -128), complex(32640, -32640)])
        self.assertEqual(meta["global"]["gpstime:calibration"]["wav_offset"], 127.5)

    def test_invalid_source_is_refused(self):
        base = self.write("bad", "rf32_le", [0.0] * 10, [{"core:sample_start": 0, "core:datetime": of.format_ns(T0)}])
        (self.dir / "bad.sigmf-data").write_bytes(b"\x01" * 40)
        with self.assertRaises(cv.ConvertError):
            cv.to_wav(base, self.dir / "x")


class TestMiniseed(Base):
    def make(self, datatype="rf32_le", n=500):
        samples = [float(i % 17) - 8.0 for i in range(n)] if datatype == "rf32_le" else [(i % 300) - 150 for i in range(n)]
        caps = [{"core:sample_start": 0, "core:datetime": of.format_ns(T0), "gpstime:sample_rate": 100.0005},
                {"core:sample_start": 200, "gpstime:time_valid": False},
                {"core:sample_start": 250, "core:datetime": of.format_ns(T0 + 2_500_000_000 + 7_000),
                 "gpstime:sample_rate": 99.9995}]
        return self.write("infra", datatype, samples, caps), samples

    def test_records_times_and_samples(self):
        base, samples = self.make()
        path, nrec = cv.to_miniseed(base, self.dir / "infra.mseed", network="XX", station="GTP01", location="00",
                                    channel="HDF")
        raw = path.read_bytes()
        self.assertEqual(len(raw), nrec * 512)
        recs = cv.read_miniseed(path)
        self.assertEqual(len(recs), nrec)
        self.assertEqual([r["sequence"] for r in recs], list(range(1, nrec + 1)))
        meta, _ = of.read(base)
        got, idx = [], []
        pos = [0, 96, 192, 250, 346, 442]          # 96 samples per record; gap 200-249 left out
        self.assertEqual(nrec, len(pos))
        for r, p in zip(recs, pos):
            self.assertEqual((r["network"], r["station"], r["location"], r["channel"], r["quality"]),
                             ("XX", "GTP01", "00", "HDF", "D"))
            self.assertEqual((r["encoding"], r["word_order"], r["record_exp"], r["data_offset"], r["blockettes"]),
                             (4, 1, 9, 128, 3))
            self.assertEqual((r["rate_factor"], r["rate_multiplier"]), (100, 1))
            self.assertEqual(r["io_flags"] & 0x20, 0x20, "clock locked (pps)")
            expect_ns = of.sample_time(meta, p)[0]
            self.assertLess(abs(r["start_ns"] - expect_ns), 1000, "record time to 1 µs")
            got += r["samples"]
            idx += range(p, p + r["samples_n"])
        self.assertEqual(got, [samples[i] for i in idx])
        self.assertNotIn(220, idx, "untimed samples are left out")
        self.assertAlmostEqual(recs[3]["actual_rate"], 99.9995, places=3)
        note = json.loads((self.dir / "infra.mseed.gpstime.json").read_text(encoding="utf-8"))
        self.assertEqual(note["source_checksum"], meta["global"]["gpstime:checksum"])
        self.assertEqual(note["records"], nrec)

    def test_int32_from_int16(self):
        base, samples = self.make("ri16_le", n=300)
        path, _ = cv.to_miniseed(base, self.dir / "i.mseed", network="XX", station="GTP01", location="",
                                 channel="HDF")
        recs = cv.read_miniseed(path)
        self.assertEqual(recs[0]["encoding"], 3)
        self.assertEqual(recs[0]["samples"], samples[:96])

    def test_refusals(self):
        base, _ = self.make()
        for bad in ({"network": "toolong"}, {"station": "TOOLONG"}, {"channel": "HD"}, {"location": "000"}):
            kw = dict(network="XX", station="GTP01", location="00", channel="HDF")
            kw.update(bad)
            with self.subTest(bad), self.assertRaises(cv.ConvertError):
                cv.to_miniseed(base, self.dir / "x.mseed", **kw)
        iq = self.write("iq", "cf32_le", [0j] * 10,
                        [{"core:sample_start": 0, "core:datetime": of.format_ns(T0), "core:frequency": 1e8}],
                        sensor="rf")
        with self.assertRaises(cv.ConvertError):
            cv.to_miniseed(iq, self.dir / "x.mseed", network="XX", station="A", location="", channel="HDF")
        odd = self.write("odd", "rf32_le", [0.0] * 10, [{"core:sample_start": 0, "core:datetime": of.format_ns(T0)}],
                         rate=99.5)
        with self.assertRaises(cv.ConvertError):
            cv.to_miniseed(odd, self.dir / "x.mseed", network="XX", station="A", location="", channel="HDF")

    def test_rate_factors(self):
        self.assertEqual(cv._rate_factor(100.0), (100, 1))
        self.assertEqual(cv._rate_factor(48000.0), (24000, 2))


try:
    import obspy  # noqa: F401  (optional: an independent miniSEED reader; not in CI)
    HAVE_OBSPY = True
except ImportError:
    HAVE_OBSPY = False


@unittest.skipUnless(HAVE_OBSPY, "ObsPy not installed (an optional independent check)")
class TestObspyReadsIt(Base):
    make = TestMiniseed.make

    def test_obspy(self):
        from obspy import read
        base, samples = self.make()
        path, _ = cv.to_miniseed(base, self.dir / "o.mseed", network="XX", station="GTP01", location="00",
                                 channel="HDF")
        st = read(str(path), format="MSEED")
        meta, _ = of.read(base)
        self.assertEqual(len(st), 2, "the untimed samples make a gap")
        for tr, first in zip(st, (0, 250)):
            s = tr.stats
            self.assertEqual((s.network, s.station, s.location, s.channel), ("XX", "GTP01", "00", "HDF"))
            expect = of.sample_time(meta, first)[0]
            self.assertLess(abs(s.starttime.ns - expect), 1000)
        self.assertEqual([v for tr in st for v in tr.data.tolist()], samples[:200] + samples[250:])


class TestCli(Base):
    def test_cli(self):
        base = self.write("cli", "rf32_le", [1.0, -1.0] * 100,
                          [{"core:sample_start": 0, "core:datetime": of.format_ns(T0)}])
        with redirect_stdout(io.StringIO()) as o:
            self.assertEqual(cv.main(["wav", str(base), str(self.dir / "cli-wav")]), 0)
            self.assertEqual(cv.main(["miniseed", str(base), str(self.dir / "cli.mseed"), "--net", "XX",
                                      "--sta", "GTP01", "--cha", "HDF"]), 0)
        self.assertIn("3 records", o.getvalue())
        with redirect_stderr(io.StringIO()):
            self.assertEqual(cv.main(["miniseed", str(base), str(self.dir / "c.mseed"), "--net", "XX",
                                      "--sta", "bad!", "--cha", "HDF"]), 1)


if __name__ == "__main__":
    unittest.main()
