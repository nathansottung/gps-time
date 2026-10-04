"""CHG-002: a freshly extracted archive must not depend on preserved
execute bits for the logging scripts.

The reviewed failure: scripts/logsync.sh shipped as 0644 while systemd units
exec'd it directly (203/EXEC), aborting install.sh under `set -e`.
"""

import importlib.util
import re
import shutil
import stat
import tarfile
import tempfile
import unittest
from unittest import mock
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

    def test_installer_uses_a_venv_not_system_pip(self):
        # Bookworm's system Python is externally managed (PEP 668); GPS-020.
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
        self.assertNotIn("--break-system-packages", code)
        self.assertNotRegex(code, r"(?m)^\s*pip3? install")
        self.assertIn('python3 -m venv "$VENV"', code)
        self.assertIn('"$VENV/bin/python" -m pip install', code)
        self.assertIn("-r requirements.txt", code)
        self.assertIn("VENV=$DEST/venv", code)

    def test_service_runs_the_venv_interpreter(self):
        unit = (ROOT / "gps-time-pi.service").read_text(encoding="utf-8")
        execs = re.findall(r"(?m)^ExecStart=(.*)$", unit)
        self.assertEqual(execs, ["/opt/gps-time-pi/venv/bin/python -m gps_time_pi.server"])


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

    def test_dev_zip_has_no_node_modules_or_build_output(self):
        with zipfile.ZipFile(self.zip_path) as z:
            bad = [n for n in z.namelist() if "/node_modules/" in n or "/web/dist/" in n]
            self.assertEqual(bad, [])

    def test_pi_tar_without_web_has_no_web_dir(self):
        with tarfile.open(self.tar_path) as t:
            self.assertEqual([n for n in t.getnames() if n.startswith("gps-time/web")], [])


class TestWebUiInBundle(unittest.TestCase):
    """The Pi bundle ships the built UI so /app/ works on a station without Node."""

    def setUp(self):
        self.bb = _load_build_bundles()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.dist = self.tmp / "dist"
        (self.dist / "assets").mkdir(parents=True)
        (self.dist / "index.html").write_text("<!doctype html>", encoding="utf-8")
        (self.dist / "assets" / "index-abc123.js").write_text("//js", encoding="utf-8")
        (self.dist / "version.txt").write_text("9.8.7\n", encoding="utf-8")

    def test_pi_tar_ships_the_built_ui(self):
        out = self.tmp / "pi.tar.gz"
        self.bb.build_pi_tar(out, version="9.8.7", web_dist=self.dist)
        with tarfile.open(out) as t:
            members = {m.name: m for m in t.getmembers()}
            for name in ("index.html", "assets/index-abc123.js", "version.txt"):
                m = members[f"gps-time/web/dist/{name}"]
                self.assertEqual(m.mode & 0o777, 0o644, name)
                self.assertEqual((m.uid, m.gid), (0, 0), name)

    def test_matching_built_ui_is_accepted(self):
        self.assertIsNone(self.bb.web_dist_problem(self.dist, "9.8.7"))
        self.assertIsNone(self.bb.web_dist_problem(self.dist, None))   # no tag reachable: nothing to compare

    def test_ui_built_from_another_version_is_refused(self):
        self.assertIn("built from 9.8.7", self.bb.web_dist_problem(self.dist, "9.8.8"))
        (self.dist / "version.txt").unlink()
        self.assertIn("unknown version", self.bb.web_dist_problem(self.dist, "9.8.7"))

    def test_unbuilt_ui_is_refused(self):
        (self.dist / "index.html").unlink()
        self.assertIn("not built", self.bb.web_dist_problem(self.dist, "9.8.7"))

    def test_main_stops_instead_of_shipping_a_bundle_without_the_ui(self):
        with mock.patch.object(self.bb, "WEB_DIST", self.tmp / "missing"), \
             mock.patch.object(self.bb, "DIST", self.tmp / "out"):
            with self.assertRaises(SystemExit) as cm:
                self.bb.main([])
            self.assertIn("--without-web", str(cm.exception))
            self.assertFalse((self.tmp / "out").exists(), "nothing is built when the UI is missing")

    def test_installer_installs_the_ui_and_removes_the_old_copy(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        rm = text.index('rm -rf "$DEST/web/dist"')
        cp = text.index('cp -r web/dist "$DEST/web/"')
        self.assertLess(rm, cp)
        self.assertLess(text.index("cp -r gps_time_pi $DEST/"), cp)
        self.assertLess(cp, text.index("systemctl restart gps-time-pi"))


if __name__ == "__main__":
    unittest.main()
