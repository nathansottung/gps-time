"""Station migration: one encrypted file with config, keys, survey and oscillator (gps_time_pi/migrate.py).

Runs on temp folders standing in for /opt/gps-time-pi and /etc; never root, so ownership isn't
changed (modes are). The plain test run has no cryptography: these tests run in the station venv
in CI (.github/workflows/ci.yml), which fails if they're skipped there.
"""
import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

from gps_time_pi import migrate as mg

PASS = "a long enough passphrase"
# The project's example location (US Naval Observatory), standing in for a station's exact position.
CONFIG = {"site": {"lat": 38.9217, "lon": -77.0669, "alt_msl": 92.0, "survey": {"n": 12345}},
          "location_display": "hidden", "timezone": "America/New_York"}


def station(root):
    d = Path(root) / "opt" / "gps-time-pi"
    (d / "gps_time_pi").mkdir(parents=True)
    (d / "gps_time_pi" / "VERSION").write_text("1.6.0-rc.3\n")
    (d / "config.json").write_text(json.dumps(CONFIG))
    (d / "station-key").write_bytes(b"-----BEGIN PRIVATE KEY-----\nnot a real key\n-----END PRIVATE KEY-----\n")
    (d / "station-key.pub").write_text("ed25519 pub\n")
    (d / "admin-token.sha256").write_text("sha256:abc\n")
    (d / "oscillator-log.csv").write_text("# gps-time.oscillator-log/1; board_sha256=0123456789abcdef; model=x\nt,samples\n")
    (d / "timing-events.json").write_text("{}")
    (d / "sky-obstruction.json").write_text("{}")
    (d / "evidence").mkdir()
    e = Path(root) / "etc"
    (e / "gps-time-websdr").mkdir(parents=True)
    (e / "gps-time-websdr" / "password").write_text("radio:pbkdf2_sha256$1000$x$y\n")
    return d, e


@unittest.skipUnless(mg.AVAILABLE, "cryptography not installed (CI runs this in the station venv)")
class TestMigrate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.old, self.old_etc = station(self.tmp / "old")
        self.new = self.tmp / "new" / "opt" / "gps-time-pi"
        self.new_etc = self.tmp / "new" / "etc"
        self.new.mkdir(parents=True)
        self.file = self.tmp / "station.gtpmig"

    def export(self):
        return mg.export(self.file, PASS, self.old, self.old_etc, now=1_793_800_000)

    def test_export_moves_config_keys_and_oscillator_only(self):
        names = self.export()
        self.assertEqual(names, ["admin-token.sha256", "config.json", "oscillator-log.csv", "station-key",
                                 "station-key.pub", "websdr-password"])
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(self.file.stat().st_mode), 0o600)

    def test_the_file_is_encrypted(self):
        self.export()
        blob = self.file.read_bytes()
        self.assertTrue(blob.startswith(mg.MAGIC))
        for secret in (b"38.9217", b"-77.0669", b"PRIVATE KEY", b"pbkdf2", b"board_sha256", b"config.json"):
            self.assertNotIn(secret, blob)

    def test_round_trip_into_a_new_station(self):
        self.export()
        (self.new / "station-key").write_bytes(b"the new card's own key\n")       # install.sh made one
        manifest, done = mg.import_(self.file, PASS, self.new, self.new_etc, running=lambda: False, now=1_793_900_000)
        self.assertEqual(manifest["software_version"], "1.6.0-rc.3")
        self.assertEqual(json.loads((self.new / "config.json").read_text()), CONFIG)   # survey and privacy mode
        self.assertEqual((self.new / "station-key").read_bytes(), (self.old / "station-key").read_bytes())
        (backup,) = self.new.glob("station-key.before-migrate-*")
        self.assertEqual(backup.read_bytes(), b"the new card's own key\n")
        self.assertTrue((self.new_etc / "gps-time-websdr" / "password").is_file())
        actions = {n: a for n, _p, a in done}
        self.assertTrue(actions["station-key"].startswith("replaced"))
        self.assertEqual(actions["config.json"], "added")
        for name in ("timing-events.json", "sky-obstruction.json", "evidence"):
            self.assertFalse((self.new / name).exists(), name)
        if os.name != "nt":
            for name, mode in (("config.json", 0o600), ("station-key", 0o600), ("station-key.pub", 0o644),
                               ("admin-token.sha256", 0o640), ("oscillator-log.csv", 0o640)):
                self.assertEqual(stat.S_IMODE((self.new / name).stat().st_mode), mode, name)

    def test_import_twice_changes_nothing_the_second_time(self):
        self.export()
        mg.import_(self.file, PASS, self.new, self.new_etc, running=lambda: False)
        _m, done = mg.import_(self.file, PASS, self.new, self.new_etc, running=lambda: False)
        self.assertEqual({a for _n, _p, a in done}, {"unchanged"})
        self.assertFalse(list(self.new.glob("*.before-migrate-*")))

    def test_dry_run_writes_nothing(self):
        self.export()
        _m, done = mg.import_(self.file, PASS, self.new, self.new_etc, dry_run=True, running=lambda: True)
        self.assertTrue(done)
        self.assertEqual(list(self.new.iterdir()), [])

    def test_a_running_service_is_refused(self):
        self.export()
        with self.assertRaisesRegex(mg.MigrateError, "stop it first"):
            mg.import_(self.file, PASS, self.new, self.new_etc, running=lambda: True)
        self.assertEqual(list(self.new.iterdir()), [])

    def test_wrong_passphrase_and_tampering_are_refused(self):
        self.export()
        with self.assertRaisesRegex(mg.MigrateError, "wrong passphrase"):
            mg.import_(self.file, "not the passphrase", self.new, self.new_etc, running=lambda: False)
        blob = bytearray(self.file.read_bytes())
        blob[-5] ^= 1
        self.file.write_bytes(bytes(blob))
        with self.assertRaisesRegex(mg.MigrateError, "wrong passphrase, or the file was changed"):
            mg.import_(self.file, PASS, self.new, self.new_etc, running=lambda: False)
        self.assertEqual(list(self.new.iterdir()), [])

    def test_header_tampering_is_refused(self):
        self.export()
        blob = self.file.read_bytes()
        head_end = blob.index(b"\n", len(mg.MAGIC))
        tampered = blob[:head_end].replace(b'"cipher":"AES-256-GCM"', b'"cipher":"AES-256-GCX"') + blob[head_end:]
        self.file.write_bytes(tampered)
        with self.assertRaises(mg.MigrateError):
            mg.import_(self.file, PASS, self.new, self.new_etc, running=lambda: False)

    def test_not_a_station_and_not_a_file(self):
        with self.assertRaisesRegex(mg.MigrateError, "is this a station"):
            mg.export(self.file, PASS, self.tmp / "nowhere", self.tmp / "etc")
        self.file.write_bytes(b"something else")
        with self.assertRaisesRegex(mg.MigrateError, "not a GPS Time migration file"):
            mg.import_(self.file, PASS, self.new, self.new_etc, running=lambda: False)

    def test_an_entry_this_version_does_not_know_is_refused(self):
        blob = mg.pack({"config.json": b"{}", "../../etc/shadow": b"x"}, {}, PASS)
        self.file.write_bytes(blob)
        with self.assertRaisesRegex(mg.MigrateError, "unexpected entry"):
            mg.import_(self.file, PASS, self.new, self.new_etc, running=lambda: False)
        blob = mg.pack({"config.json": b"{}", "authorized_keys": b"x"}, {}, PASS)
        self.file.write_bytes(blob)
        with self.assertRaisesRegex(mg.MigrateError, "doesn't know: authorized_keys"):
            mg.import_(self.file, PASS, self.new, self.new_etc, running=lambda: False)


class TestStatic(unittest.TestCase):
    def test_never_moved_on_purpose(self):
        names = set(mg.files())
        for name in ("timing-events.json", "sky-obstruction.json", "evidence"):
            self.assertNotIn(name, names)

    def test_owners_and_modes_follow_install_sh(self):
        f = mg.files()
        self.assertEqual(f["station-key"][1:4], ("gps-time", "gps-time", 0o600))
        self.assertEqual(f["admin-token.sha256"][1:4], ("root", "gps-time", 0o640))
        self.assertEqual(f["config.json"][1:4], ("gps-time", "gps-time", 0o600))

    def test_passphrase_is_never_an_argument_or_variable(self):
        text = (Path(mg.__file__)).read_text(encoding="utf-8")
        self.assertIn("getpass.getpass", text)
        self.assertNotIn("--passphrase", text)
        self.assertNotIn("environ.get(\"GTP_MIGRATE", text)


if __name__ == "__main__":
    unittest.main()
