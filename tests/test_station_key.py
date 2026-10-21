"""Station key pair: generation, signing observation files, verification in the validator.

Needs the cryptography package (requirements.txt). The plain test run has no
third-party packages, so CI also runs this file in the station venv and fails
if anything is skipped there.
"""

import base64
import io
import json
import os
import shutil
import stat
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import obsformat as of
from gps_time_pi import station_key as sk

ROOT = Path(__file__).resolve().parents[1]
T0 = 1_792_602_000 * 1_000_000_000


def sample_meta():
    g = {"station_id": "unsigned-station", "sensor": "audio", "quantity": "pressure", "unit": "Pa",
         "channels": [{"name": "mic"}], "time_source": "pps", "time_offset_bound_s": 2e-6,
         "sample_time_uncertainty_s": 1e-6, "frequency_reference": {"state": "free", "error_ppm": None},
         "calibration": None, "position": {"privacy": "hidden", "lat": None, "lon": None},
         "provenance": "observed", "request_id": None, "licence": "CC-BY-4.0"}
    meta = of.build_meta(datatype="rf32_le", sample_rate=1000.0, recorder="test",
                         captures=[{"core:sample_start": 0, "core:datetime": of.format_ns(T0)}], gpstime=g)
    return meta, of.encode([0.25 * i for i in range(100)], "rf32_le")


class TestWithoutLibrary(unittest.TestCase):
    def test_unsigned_is_a_warning_and_signed_is_not_passed_unchecked(self):
        meta, data = sample_meta()
        _, mb = of.to_bytes(meta, data)
        m = json.loads(mb)
        self.assertEqual(of.validate_meta(m, data), ([], ["unsigned"]))
        m["global"]["gpstime:signature"] = "ed25519:AAAA"
        with mock.patch.object(sk, "AVAILABLE", False):
            errs, warns = of.validate_meta(m, data)
        self.assertEqual(errs, [])
        self.assertIn("signature not checked", warns[0])


@unittest.skipUnless(sk.AVAILABLE, "cryptography not installed (CI runs this in the station venv)")
class TestStationKey(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.key_path = self.dir / "station-key"

    def test_generate_once(self):
        sid = sk.generate(self.key_path)
        self.assertRegex(sid, r"^ed25519:[0-9a-f]{64}$")
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(self.key_path.stat().st_mode), 0o600)
        pub = base64.b64decode((self.dir / "station-key.pub").read_text(encoding="ascii"))
        self.assertEqual(sk.fingerprint(pub), sid)
        before = self.key_path.read_bytes()
        self.assertEqual(sk.generate(self.key_path), sid, "never overwrites an existing key")
        self.assertEqual(self.key_path.read_bytes(), before)

    def signed(self):
        sk.generate(self.key_path)
        meta, data = sample_meta()
        base = self.dir / "obs"
        of.write(base, meta, data, signer=sk.load(self.key_path))
        return base

    def test_signed_file_verifies(self):
        base = self.signed()
        errs, warns = of.validate(base)
        self.assertEqual((errs, warns), ([], []))
        meta, _ = of.read(base)
        g = meta["global"]
        self.assertEqual(g["gpstime:station_id"], sk.generate(self.key_path))
        self.assertTrue(g["gpstime:signature"].startswith("ed25519:"))

    def tampered(self, change):
        base = self.signed()
        meta, data = of.read(base)
        change(meta)
        return of.validate_meta(meta, data)[0]

    def test_tampering_is_caught(self):
        cases = {
            "time": lambda m: m["captures"][0].__setitem__("core:datetime", of.format_ns(T0 + 1)),
            "uncertainty": lambda m: m["global"].__setitem__("gpstime:sample_time_uncertainty_s", 1e-9),
            "annotation": lambda m: m["annotations"].append({"core:sample_start": 0, "core:sample_count": 1}),
        }
        for name, change in cases.items():
            with self.subTest(name):
                errs = self.tampered(change)
                self.assertTrue(any("signature does not match" in e for e in errs), errs)

    def test_changed_samples_are_caught(self):
        base = self.signed()
        meta, data = of.read(base)
        errs, _ = of.validate_meta(meta, data[:-4] + b"\0\0\0\0")
        self.assertTrue(any("checksum" in e for e in errs), errs)

    def test_swapped_public_key(self):
        sk.generate(self.dir / "other")
        other_pub = (self.dir / "other.pub").read_text(encoding="ascii").strip()
        errs = self.tampered(lambda m: m["global"].__setitem__("gpstime:public_key", other_pub))
        self.assertTrue(any("not the fingerprint" in e for e in errs), errs)

    def test_resigned_by_another_station_is_flagged_by_the_trusted_list(self):
        base = self.signed()
        mine = sk.generate(self.key_path)
        sk.generate(self.dir / "other")
        meta, data = of.read(base)
        of.write(base, meta, data, signer=sk.load(self.dir / "other"))
        errs, warns = of.validate(base, trusted=[mine])
        self.assertEqual(errs, [])
        self.assertTrue(any("not in the trusted list" in w for w in warns), warns)
        self.assertEqual(of.validate(base, trusted=[sk.generate(self.dir / "other")]), ([], []))

    def test_cli(self):
        def run(*args):
            o, e = io.StringIO(), io.StringIO()
            with redirect_stdout(o), redirect_stderr(e):
                code = sk.main(["--path", str(self.key_path), *args])
            return code, o.getvalue() + e.getvalue()

        code, out = run("generate")
        self.assertEqual(code, 0)
        self.assertIn("Station key created", out)
        self.assertIn("Existing station key kept", run("generate")[1])
        sid = json.loads(run("show")[1])["station_id"]
        meta, data = sample_meta()
        of.write(self.dir / "obs", meta, data)
        self.assertEqual(run("verify", str(self.dir / "obs")), (1, "unsigned\n"))
        self.assertEqual(run("sign", str(self.dir / "obs"))[0], 0)
        code, out = run("verify", str(self.dir / "obs"), "--trust", sid)
        self.assertEqual(code, 0)
        self.assertIn(sid, out)

    def test_sign_needs_the_checksum(self):
        sk.generate(self.key_path)
        meta, _ = sample_meta()
        with self.assertRaises(sk.StationKeyError):
            sk.sign_meta(meta, sk.load(self.key_path))


class TestInstall(unittest.TestCase):
    def test_installer_generates_the_key_for_the_service_user(self):
        install = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn('"$VENV/bin/python" -m gps_time_pi.station_key --path "$DEST/station-key" generate --owner gps-time',
                      install)

    def test_modules_are_denied_the_key(self):
        from gps_time_pi.modkit import supervisor
        self.assertTrue(any(p.endswith("station-key") for p in supervisor.deny_paths()))


if __name__ == "__main__":
    unittest.main()
