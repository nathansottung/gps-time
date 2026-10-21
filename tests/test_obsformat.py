"""Observation files (SigMF + gpstime:): writer, reader, validator, sample times. No hardware or network."""

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tests import _env  # noqa: F401
from gps_time_pi import obsformat as of

T0 = 1_792_602_000 * 1_000_000_000 + 123_456_789     # 2026-10-21T...; a whole-ns UTC time


def gpstime(**over):
    g = {"station_id": "test-station", "sensor": "audio", "quantity": "pressure", "unit": "Pa",
         "channels": [{"name": "mic"}], "time_source": "pps", "time_offset_bound_s": 2e-6,
         "sample_time_uncertainty_s": 1e-6, "frequency_reference": {"state": "free", "error_ppm": None},
         "calibration": None, "position": {"privacy": "rounded", "lat": 38.9, "lon": -77.1, "alt_m": 90.0},
         "provenance": "observed", "request_id": None, "licence": "CC-BY-4.0"}
    g.update(over)
    return g


def simple(n=1000, rate=8000.0, **over):
    caps = [{"core:sample_start": 0, "core:datetime": of.format_ns(T0)}]
    meta = of.build_meta(datatype="rf32_le", sample_rate=rate, captures=caps, gpstime=gpstime(**over),
                         recorder="test", annotations=[{"core:sample_start": 10, "core:sample_count": 5, "core:label": "pick"}])
    return meta, of.encode([0.001 * i for i in range(n)], "rf32_le")


class TestTimeStrings(unittest.TestCase):
    def test_round_trip_to_the_nanosecond(self):
        for ns in (0, T0, T0 + 999, 1_792_602_000 * 10**9):
            self.assertEqual(of.parse_ns(of.format_ns(ns)), ns)
        self.assertTrue(of.format_ns(T0).endswith(".123456789Z"))

    def test_parse(self):
        self.assertEqual(of.parse_ns("1970-01-01T00:00:01Z"), 10**9)
        self.assertEqual(of.parse_ns("1970-01-01T00:00:00.5Z"), 500_000_000)
        for bad in ("2026-10-21 17:00:00Z", "2026-10-21T17:00:00", "2026-10-21T17:00:00.1234567891Z", None):
            with self.assertRaises(ValueError):
                of.parse_ns(bad)

    def test_filename(self):
        self.assertEqual(of.filename("st/1", "rf", 10**9), "st-1_rf_19700101T000001.000000000Z")


class TestSamples(unittest.TestCase):
    def test_encode_decode(self):
        c = [complex(0.5, -0.25), complex(-1, 1)]
        self.assertEqual(of.decode(of.encode(c, "cf32_le"), "cf32_le"), c)
        self.assertEqual(of.decode(of.encode([complex(100, -40000)], "ci16_le"), "ci16_le"), [complex(100, -32768)])
        self.assertEqual(of.decode(of.encode([complex(127.6, 300)], "cu8"), "cu8"), [complex(128, 255)])
        self.assertEqual(of.decode(of.encode([1.5, -2.0], "rf32_le"), "rf32_le"), [1.5, -2.0])
        self.assertEqual(of.sample_size("ci16_le"), 4)


class TestWriteRead(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def test_round_trip_and_valid(self):
        meta, data = simple()
        base = self.dir / of.filename("test-station", "audio", T0)
        dp, mp = of.write(base, meta, data)
        self.assertTrue(dp.name.endswith(".sigmf-data") and mp.name.endswith(".sigmf-meta"))
        m2, d2 = of.read(base)
        self.assertEqual(d2, data)
        self.assertEqual(m2["global"]["gpstime:checksum"], of.checksum(data))
        self.assertEqual(m2["global"]["core:extensions"][0]["name"], "gpstime")
        errs, warns = of.validate(base)
        self.assertEqual(errs, [])
        self.assertEqual(warns, ["unsigned"])
        self.assertEqual([p.name for p in self.dir.iterdir() if p.name.startswith(".tmp")], [])

    def test_sample_times(self):
        meta, data = simple(rate=8000.0)
        _, mb = of.to_bytes(meta, data)
        m = json.loads(mb)
        self.assertEqual(of.sample_time(m, 0), (T0, 1e-6))
        self.assertEqual(of.sample_time(m, 8000)[0], T0 + 10**9)
        self.assertEqual(of.sample_time(m, 1)[0], T0 + 125_000)

    def test_capture_rate_and_no_time_captures(self):
        caps = [{"core:sample_start": 0, "gpstime:time_valid": False},
                {"core:sample_start": 100, "core:datetime": of.format_ns(T0), "gpstime:sample_rate": 1000.5},
                {"core:sample_start": 600, "gpstime:time_valid": False}]
        meta = of.build_meta(datatype="rf32_le", sample_rate=1000.0, captures=caps, gpstime=gpstime(), recorder="t")
        data = of.encode([0.0] * 1000, "rf32_le")
        self.assertEqual(of.validate_meta(json.loads(of.to_bytes(meta, data)[1]), data)[0], [])
        self.assertIsNone(of.sample_time(meta, 50))
        self.assertEqual(of.sample_time(meta, 599)[0], T0 + round(499 / 1000.5 * 1e9))
        self.assertIsNone(of.sample_time(meta, 700))


class TestValidator(unittest.TestCase):
    def check(self, mutate, expect, data_mutate=None):
        meta, data = simple()
        data, mb = of.to_bytes(meta, data)
        meta = json.loads(mb)
        mutate(meta)
        if data_mutate:
            data = data_mutate(data)
        errs, _ = of.validate_meta(meta, data)
        self.assertTrue(any(expect in e for e in errs), (expect, errs))

    def test_rejections(self):
        g = lambda k, v: (lambda m: m["global"].__setitem__(k, v))
        cases = [
            (g("gpstime:time_source", "sundial"), "time_source"),
            (lambda m: m["global"].pop("gpstime:station_id"), "missing gpstime:station_id"),
            (g("core:datatype", "cf64_le"), "core:datatype"),
            (g("gpstime:position", {"privacy": "hidden", "lat": 38.9, "lon": -77.1}), "hidden but carries"),
            (g("gpstime:position", {"privacy": "rounded", "lat": 38.9217, "lon": -77.1}), "more than 1 decimal"),
            (lambda m: m["captures"][0].pop("core:datetime"), "every sample's time must be computable"),
            (lambda m: m["captures"].append({"core:sample_start": 0, "core:datetime": of.format_ns(T0)}), "must increase"),
            (lambda m: m["captures"].append({"core:sample_start": 800, "core:datetime": of.format_ns(T0 + 5 * 10**9)}), "disagrees"),
            (lambda m: m["captures"].append({"core:sample_start": 5000, "core:datetime": of.format_ns(T0 + 10**9)}), "past the last sample"),
            (lambda m: m["annotations"].append({"core:sample_start": 990, "core:sample_count": 50}), "past the last sample"),
            (g("gpstime:sensor", "rf"), "core:frequency is required"),
            (lambda m: m["global"]["core:extensions"].clear(), "does not list gpstime"),
            (lambda m: m["captures"].__setitem__(0, {"core:sample_start": 0, "gpstime:time_valid": False,
                                                    "core:datetime": of.format_ns(T0)}), "must not carry core:datetime"),
        ]
        for mutate, expect in cases:
            with self.subTest(expect):
                self.check(mutate, expect)

    def test_data_checks(self):
        self.check(lambda m: None, "checksum does not match", lambda d: d[:-4] + b"\0\0\0\1")
        self.check(lambda m: None, "whole number", lambda d: d + b"\0")

    def test_warnings_for_unknowns(self):
        meta, data = simple(time_offset_bound_s=None, sample_time_uncertainty_s=None)
        data, mb = of.to_bytes(meta, data)
        errs, warns = of.validate_meta(json.loads(mb), data)
        self.assertEqual(errs, [])
        self.assertEqual(len(warns), 3)


class TestCli(unittest.TestCase):
    def test_validate_and_info(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        meta, data = simple()
        of.write(d / "obs", meta, data)
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(of.main(["validate", str(d / "obs")]), 0)
        self.assertIn("valid", out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out):
            of.main(["info", str(d / "obs")])
        info = json.loads(out.getvalue())
        self.assertEqual((info["samples"], info["time_source"]), (1000, "pps"))
        (d / "obs.sigmf-data").write_bytes(b"\0" * 4000)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(of.main(["validate", str(d / "obs")]), 1)


if __name__ == "__main__":
    unittest.main()
