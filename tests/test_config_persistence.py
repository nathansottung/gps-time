"""Survey/config persistence (fix/survey-persistence).

Requirements: flush on SIGTERM, fsync on save, set a corrupt config.json aside
instead of overwriting it, keep a previous checkpoint. No root needed; the real
SIGTERM test runs on POSIX (CI) and is skipped on Windows, where the handler is
exercised directly instead.
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import config

REPO = Path(__file__).resolve().parents[1]


class PersistenceBase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gtp-cfg-")
        self.path = os.path.join(self.dir, "config.json")
        self.prev = self.path + config.PREV_SUFFIX
        for attr, value in (("_PATH", self.path), ("_CACHE", None), ("_LAST_WRITE", 0.0)):
            p = mock.patch.object(config, attr, value)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.dict(config._STATUS, {k: None for k in config._STATUS})
        p.start()
        self.addCleanup(p.stop)

    def write(self, path, text):
        Path(path).write_text(text, encoding="utf-8")

    def read(self, path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def survey(self, n):
        return {"location_display": "hidden",
                "site": {"lat": 38.9217, "lon": -77.0669, "n_lat": n, "n_lon": n}}

    def corrupt_files(self):
        return sorted(f for f in os.listdir(self.dir) if f.startswith("config.json.corrupt-"))


class TestFsync(PersistenceBase):
    def test_file_is_fsynced_before_rename_and_dir_after(self):
        calls = []
        real_fsync, real_replace = os.fsync, os.replace
        with mock.patch.object(config.os, "fsync", side_effect=lambda fd: (calls.append("fsync"), real_fsync(fd))[1]), \
                mock.patch.object(config.os, "replace", side_effect=lambda a, b: (calls.append(("replace", os.path.basename(b))), real_replace(a, b))[1]):
            config.save(self.survey(1))
        i = calls.index(("replace", "config.json"))
        self.assertEqual(calls[i - 1], "fsync", calls)          # data on disk before the rename
        if os.name == "posix":
            self.assertEqual(calls[i + 1], "fsync", calls)      # rename itself made durable
        self.assertEqual(self.read(self.path)["site"]["n_lat"], 1)

    def test_failed_serialization_leaves_existing_file_and_no_temp(self):
        config.save(self.survey(1))
        before = Path(self.path).read_bytes()
        with mock.patch.object(config.json, "dumps", side_effect=TypeError("boom")):
            with self.assertRaises(TypeError):
                config.save(self.survey(2))
        self.assertEqual(Path(self.path).read_bytes(), before)
        self.assertEqual([f for f in os.listdir(self.dir) if f.startswith(".config-")], [])
        self.assertIn("boom", config.persistence_status()["last_write_error"])


class TestCorruptConfig(PersistenceBase):
    def test_corrupt_config_is_set_aside_not_overwritten(self):
        bad = '{"site": {"lat": 38.9, "n_lat": 500'          # truncated JSON
        self.write(self.path, bad)
        cfg = config.load()
        self.assertIsNone(cfg["site"])                       # no checkpoint to fall back to
        moved = self.corrupt_files()
        self.assertEqual(len(moved), 1)
        self.assertEqual(Path(self.dir, moved[0]).read_text(encoding="utf-8"), bad)   # bytes preserved
        st = config.persistence_status()
        self.assertEqual(st["loaded_from"], "defaults")
        self.assertTrue(st["corrupt_moved_to"].endswith(moved[0]))
        config.save(cfg)                                     # a later save must not touch the set-aside copy
        self.assertEqual(Path(self.dir, moved[0]).read_text(encoding="utf-8"), bad)

    def test_corrupt_config_recovers_from_previous_checkpoint(self):
        self.write(self.prev, json.dumps(self.survey(480)))
        self.write(self.path, "\x00\x00\x00")                # garbage after a bad power cut
        cfg = config.load()
        self.assertEqual(cfg["site"]["n_lat"], 480)
        self.assertEqual(config.persistence_status()["loaded_from"], "previous_checkpoint")
        self.assertEqual(len(self.corrupt_files()), 1)

    def test_non_object_json_is_treated_as_corrupt(self):
        self.write(self.path, "[1, 2, 3]")
        config.load()
        self.assertEqual(len(self.corrupt_files()), 1)

    def test_missing_config_with_checkpoint_loads_checkpoint(self):
        self.write(self.prev, json.dumps(self.survey(7)))
        self.assertEqual(config.load()["site"]["n_lat"], 7)
        self.assertEqual(self.corrupt_files(), [])

    def test_missing_config_without_checkpoint_is_defaults_and_not_an_error(self):
        cfg = config.load()
        self.assertEqual(cfg, config.DEFAULTS)
        st = config.persistence_status()
        self.assertEqual(st["loaded_from"], "defaults")
        self.assertIsNone(st["corrupt_moved_to"])


class TestPreviousCheckpoint(PersistenceBase):
    def test_previous_good_file_is_kept(self):
        config.save(self.survey(1))
        self.assertFalse(os.path.exists(self.prev))           # nothing to keep yet
        config.save(self.survey(2))
        self.assertEqual(self.read(self.prev)["site"]["n_lat"], 1)
        self.assertEqual(self.read(self.path)["site"]["n_lat"], 2)
        config.save(self.survey(3))
        self.assertEqual(self.read(self.prev)["site"]["n_lat"], 2)

    def test_identical_save_does_not_discard_the_older_checkpoint(self):
        config.save(self.survey(1))
        config.save(self.survey(2))
        config.save(self.survey(2))
        self.assertEqual(self.read(self.prev)["site"]["n_lat"], 1)

    def test_corrupt_current_file_never_becomes_the_checkpoint(self):
        config.save(self.survey(1))
        config.save(self.survey(2))                          # prev = 1
        self.write(self.path, "{not json")
        with mock.patch.object(config, "_CACHE", self.survey(3)):
            config.save(self.survey(3))
        self.assertEqual(self.read(self.prev)["site"]["n_lat"], 1)
        self.assertEqual(self.read(self.path)["site"]["n_lat"], 3)


class TestSigterm(PersistenceBase):
    def test_handler_flushes_unsaved_survey_and_exits(self):
        config.save(self.survey(1))                          # on disk: n = 1
        config.save(self.survey(14), force=False)            # batched: only in memory
        self.assertEqual(self.read(self.path)["site"]["n_lat"], 1)
        with self.assertRaises(SystemExit) as cm:
            config._handle_sigterm(signal.SIGTERM, None)
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(self.read(self.path)["site"]["n_lat"], 14)

    @unittest.skipUnless(threading.current_thread() is threading.main_thread(), "needs main thread")
    def test_install_registers_sigterm_handler(self):
        previous = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, previous)
        config.install_signal_handlers()
        self.assertIs(signal.getsignal(signal.SIGTERM), config._handle_sigterm)

    @unittest.skipUnless(os.name == "posix", "real SIGTERM delivery needs POSIX")
    def test_real_sigterm_flushes_batched_survey(self):
        child = textwrap.dedent(f"""
            import sys, time
            sys.path.insert(0, {str(REPO)!r})
            from gps_time_pi import config
            config.install_signal_handlers()
            config.save({{"site": {{"n_lat": 1}}}})
            config.save({{"site": {{"n_lat": 14}}}}, force=False)   # batched, not yet on disk
            print("ready", flush=True)
            time.sleep(30)
        """)
        env = dict(os.environ, GTP_CONFIG=self.path, PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.Popen([sys.executable, "-c", child], env=env, stdout=subprocess.PIPE, text=True)
        self.addCleanup(p.stdout.close)
        self.assertEqual(p.stdout.readline().strip(), "ready")
        self.assertEqual(self.read(self.path)["site"]["n_lat"], 1)
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=10), 0)
        self.assertEqual(self.read(self.path)["site"]["n_lat"], 14)


if __name__ == "__main__":
    unittest.main()
