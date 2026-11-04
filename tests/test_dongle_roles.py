"""Dongle roles by serial and the owner's limit of 3 RTL-SDRs on a Pi 4 (scripts/dongle-roles.sh).

The helper is sourced by sdr-stack.sh and websdr.sh. It runs here under bash with a temp root
for the device-tree model, and both installers run with their own test stubs (tests/test_sdr_stack.py,
tests/test_websdr.py), so nothing on the host changes.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import test_sdr_stack, test_websdr

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "dongle-roles.sh"
PI4 = b"Raspberry Pi 4 Model B Rev 1.5\x00"


def set_model(root, model):
    p = Path(root) / "proc" / "device-tree" / "model"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(model)


class TestStatic(unittest.TestCase):
    def test_both_installers_source_it_before_changing_anything(self):
        for name, before in (("sdr-stack.sh", 'echo "== SDR stack: packages =="'),
                             ("websdr.sh", 'echo "== Web SDR: OpenWebRX+ repository')):
            text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            with self.subTest(name):
                self.assertIn('. "$(dirname "$0")/dongle-roles.sh"', text)
                self.assertLess(text.index("dongle_check"), text.index(before))

    def test_the_limit_is_three_on_the_pi_4_family_only(self):
        text = HELPER.read_text(encoding="utf-8")
        self.assertIn("DONGLE_MAX_PI4=3", text)
        self.assertIn('"Raspberry Pi 4"*|"Raspberry Pi 400"*|"Raspberry Pi Compute Module 4"*', text)
        from gps_time_pi import sdr
        self.assertEqual(sdr.MAX_PI4, 3)
        self.assertEqual(sdr.LIMITED_MODELS, ("Raspberry Pi 4", "Raspberry Pi 400", "Raspberry Pi Compute Module 4"))


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "POSIX bash needed")
class TestHelper(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)

    def check(self, *serials):
        args = " ".join(f"'{s}'" for s in serials)
        return subprocess.run(["bash", "-c", f'. "{HELPER}"; dongle_check "{self.root}" {args}'],
                              capture_output=True, text=True, timeout=30)

    def test_three_distinct_on_a_pi_4_is_fine_four_is_not(self):
        set_model(self.root, PI4)
        r = self.check("a", "b", "c", "")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("3 of at most 3", r.stdout)
        r = self.check("a", "b", "c", "d")
        self.assertEqual(r.returncode, 1)
        self.assertIn("at most 3 on a Raspberry Pi 4 Model B Rev 1.5", r.stderr)

    def test_a_shared_serial_counts_once(self):
        set_model(self.root, PI4)
        self.assertEqual(self.check("a", "b", "c", "b").returncode, 0)

    def test_no_limit_on_other_boards_or_an_unknown_model(self):
        set_model(self.root, b"Raspberry Pi 5 Model B Rev 1.0\x00")
        r = self.check("a", "b", "c", "d")
        self.assertEqual(r.returncode, 0)
        self.assertIn("no limit for a Raspberry Pi 5", r.stdout)
        (self.root / "proc" / "device-tree" / "model").unlink()
        r = self.check("a", "b", "c", "d")
        self.assertEqual(r.returncode, 0)
        self.assertIn("can't be read", r.stdout)


class TestWebSdrInstaller(test_websdr.TestScript):
    """websdr.sh counts the SDR stack's roles when the stack is installed."""

    def sdr_installed(self, env_text):
        units = self.root / "etc/systemd/system"
        units.mkdir(parents=True, exist_ok=True)
        (units / "gps-time-rtl-tcp.service").write_text("[Unit]\n")
        set_model(self.root, PI4)
        return env_text

    def test_a_fourth_dongle_on_a_pi_4_is_refused(self):
        sdr_env = self.sdr_installed("GTP_SDR_PPS_SERIAL=0000pps\nGTP_SDR_1090_SERIAL=00001090\nGTP_SDR_978_SERIAL=00000978\n")
        r = self.run_script(sdr_env, GTP_WEBSDR="1", GTP_WEBSDR_SERIAL="0000web1")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("one too many", r.stderr)
        self.assertIn("nothing changed", r.stderr)
        self.assertFalse([c for c in self.calls() if c.startswith("apt-get")])

    def test_sharing_the_1090_dongle_is_fine(self):
        sdr_env = self.sdr_installed("GTP_SDR_PPS_SERIAL=0000pps\nGTP_SDR_1090_SERIAL=00001090\nGTP_SDR_978_SERIAL=00000978\n")
        r = self.run_script(sdr_env, GTP_WEBSDR="1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class TestSdrStackInstaller(test_sdr_stack.TestScript):
    """sdr-stack.sh counts the web SDR's dongle when the web SDR is installed."""

    def test_three_roles_plus_a_separate_web_sdr_dongle_is_refused(self):
        units = self.root / "etc/systemd/system"
        units.mkdir(parents=True, exist_ok=True)
        (units / "gps-time-websdr.service").write_text("[Unit]\n")
        (self.root / "etc/default").mkdir(parents=True, exist_ok=True)
        (self.root / "etc/default/gps-time-websdr").write_text("GTP_WEBSDR_SERIAL=0000web1\n")
        set_model(self.root, PI4)
        r = self.run_script(GTP_SDR="1", GTP_SDR_PPS_SERIAL="0000pps", GTP_SDR_1090_SERIAL="00001090",
                            GTP_SDR_978_SERIAL="00000978")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("at most 3", r.stderr)
        self.assertFalse([c for c in self.calls() if c.startswith("apt-get")])

    def test_three_roles_alone_are_fine(self):
        set_model(self.root, PI4)
        r = self.run_script(GTP_SDR="1", GTP_SDR_PPS_SERIAL="0000pps", GTP_SDR_1090_SERIAL="00001090",
                            GTP_SDR_978_SERIAL="00000978")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("3 of at most 3", r.stdout)


# The installers' own tests run in their modules; only the new ones run here.
for _cls in (TestWebSdrInstaller, TestSdrStackInstaller):
    for _name in [n for n in dir(_cls.__mro__[1]) if n.startswith("test_")]:
        setattr(_cls, _name, None)
del _cls, _name
