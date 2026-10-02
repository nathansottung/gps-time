"""CHG-002: a freshly extracted archive must not depend on preserved
execute bits for the logging scripts.

The reviewed failure: scripts/logsync.sh shipped as 0644 while systemd units
exec'd it directly (203/EXEC), aborting install.sh under `set -e`.
"""

import importlib.util
import re
import stat
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests import _env  # noqa: F401  (isolates config before package import)
from gps_time_pi import system

ROOT = Path(__file__).resolve().parents[1]
INTERPRETERS = ("/bin/bash", "/bin/sh", "/usr/bin/env")
EXEC_LINE = re.compile(r"^\s*(ExecStart|ExecStop|ExecStartPre|ExecStartPost|ExecReload)=\s*[-@+!:]*(\S+)(.*)$")


def _load_build_bundles():
    spec = importlib.util.spec_from_file_location("build_bundles", ROOT / "tools" / "build_bundles.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def unit_exec_problems(text):
    """ExecXxx= lines that execute a repository .sh script directly."""
    problems = []
    for line in text.splitlines():
        m = EXEC_LINE.match(line)
        if m and m.group(2).endswith(".sh") and m.group(2) not in INTERPRETERS:
            problems.append(line.strip())
    return problems


class TestStaticInvocation(unittest.TestCase):
    def test_checker_detects_the_reviewed_failure(self):
        reviewed = "ExecStart=/opt/gps-time-pi/scripts/logsync.sh restore\n"
        self.assertEqual(len(unit_exec_problems(reviewed)), 1)
        self.assertEqual(unit_exec_problems("ExecStart=/bin/bash /opt/x/logsync.sh restore"), [])

    def test_units_invoke_scripts_through_an_interpreter(self):
        units = sorted(ROOT.glob("system/*.service")) + [ROOT / "gps-time-pi.service"]
        self.assertTrue(units)
        for u in units:
            with self.subTest(unit=u.name):
                self.assertEqual(unit_exec_problems(u.read_text(encoding="utf-8")), [])

    def test_admin_actions_invoke_scripts_through_an_interpreter(self):
        for name, argv in system.ACTIONS.items():
            with self.subTest(action=name):
                if any(a.endswith(".sh") for a in argv):
                    self.assertIn(argv[0], INTERPRETERS)

    def test_installer_sets_script_permissions(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        copy = text.index("cp -r scripts $DEST/")
        chmod = re.search(r"chmod\s+(0?755|\+x)\s+\$DEST/scripts/", text)
        self.assertIsNotNone(chmod, "install.sh must chmod the installed scripts")
        self.assertGreater(chmod.start(), copy)
        enable = text.index("systemctl enable --now gps-time-pi-logsync.service")
        self.assertLess(chmod.start(), enable, "permissions must be set before units start")


class TestBuiltBundles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bb = _load_build_bundles()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.tar_path = Path(cls.tmp.name) / "pi.tar.gz"
        cls.zip_path = Path(cls.tmp.name) / "dev.zip"
        bb.build_pi_tar(cls.tar_path)
        bb.build_repo_zip(cls.zip_path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pi_tar_modes_and_units(self):
        with tarfile.open(self.tar_path) as t:
            members = {m.name: m for m in t.getmembers()}
            scripts = [n for n in members if n.endswith(".sh")]
            self.assertIn("gps-time/scripts/logsync.sh", scripts)
            for n in scripts:
                self.assertEqual(members[n].mode & 0o777, 0o755, n)
            for n, m in members.items():
                if not n.endswith(".sh"):
                    self.assertEqual(m.mode & 0o777, 0o644, n)
                self.assertEqual((m.uid, m.gid), (0, 0), n)
            for n in members:
                if n.endswith(".service"):
                    text = t.extractfile(members[n]).read().decode("utf-8")
                    self.assertEqual(unit_exec_problems(text), [], n)
            self.assertIn("chmod 0755 $DEST/scripts/*.sh",
                          t.extractfile(members["gps-time/install.sh"]).read().decode("utf-8"))

    def test_pi_tar_ships_the_requirements_install_sh_uses(self):
        with tarfile.open(self.tar_path) as t:
            names = t.getnames()
            self.assertIn("gps-time/requirements.txt", names)
            self.assertIn("-r requirements.txt",
                          t.extractfile("gps-time/install.sh").read().decode("utf-8"))

    def test_dev_zip_preserves_script_execute_bits(self):
        with zipfile.ZipFile(self.zip_path) as z:
            info = z.getinfo("gps-time/scripts/logsync.sh")
            mode = info.external_attr >> 16
            self.assertTrue(stat.S_ISREG(mode))
            self.assertEqual(mode & 0o777, 0o755)
            self.assertEqual((z.getinfo("gps-time/README.md").external_attr >> 16) & 0o777, 0o644)
            self.assertIsNone(z.testzip())


if __name__ == "__main__":
    unittest.main()
