"""Installer step: chrony stops taking NTP servers from DHCP, so the station
never polls its own address (spec SPEC-TIMING-METROLOGY item 6).

The script is run against a temp copy of a Debian chrony.conf. No chrony or
root needed here.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "chrony-no-dhcp-sources.sh"
FIXTURE = ROOT / "tests" / "fixtures" / "chrony" / "chrony.conf.debian"
DISABLED = "# sourcedir /run/chrony-dhcp # disabled by gps-time-pi: the station must not poll itself"


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "POSIX bash needed")
class TestScript(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.conf = self.tmp / "chrony.conf"
        shutil.copyfile(FIXTURE, self.conf)
        self.original = FIXTURE.read_text(encoding="utf-8")

    def run_script(self, **env):
        return subprocess.run(["bash", str(SCRIPT), str(self.conf)], env=dict(os.environ, **env),
                              capture_output=True, text=True, timeout=30)

    def lines(self):
        return self.conf.read_text(encoding="utf-8").splitlines()

    def test_only_the_dhcp_sourcedir_line_changes(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        before, after = self.original.splitlines(), self.lines()
        self.assertEqual(len(before), len(after))
        changed = [(b, a) for b, a in zip(before, after) if b != a]
        self.assertEqual(changed, [("sourcedir /run/chrony-dhcp", DISABLED)])
        self.assertIn("Disabled 'sourcedir /run/chrony-dhcp'", r.stdout)

    def test_other_sources_stay_active(self):
        self.run_script()
        active = [l for l in self.lines() if l and not l.lstrip().startswith("#")]
        self.assertIn("pool 2.debian.pool.ntp.org iburst", active)
        self.assertIn("sourcedir /etc/chrony/sources.d", active)
        self.assertIn("refclock PPS /dev/pps0 lock NMEA refid GPS prefer", active)
        self.assertFalse([l for l in active if "chrony-dhcp" in l])

    def test_original_is_kept_once(self):
        self.run_script()
        backup = Path(str(self.conf) + ".before-gps-time-pi")
        self.assertEqual(backup.read_text(encoding="utf-8"), self.original)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["chrony.conf", "chrony.conf.before-gps-time-pi"])

    def test_second_run_changes_nothing(self):
        self.run_script()
        first = self.conf.read_text(encoding="utf-8")
        backup = Path(str(self.conf) + ".before-gps-time-pi")
        backup.write_text("marker\n", encoding="utf-8")
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.conf.read_text(encoding="utf-8"), first)
        self.assertEqual(backup.read_text(encoding="utf-8"), "marker\n", "the first backup must not be overwritten")
        self.assertIn("nothing changed", r.stdout)

    def test_indented_line_with_trailing_slash_is_disabled(self):
        self.conf.write_text("pool example.invalid iburst\n  sourcedir   /run/chrony-dhcp/\n", encoding="utf-8")
        self.run_script()
        self.assertEqual(self.lines()[0], "pool example.invalid iburst")
        self.assertTrue(self.lines()[1].startswith("#"))

    def test_similar_paths_are_left_alone(self):
        text = "sourcedir /run/chrony-dhcp-other\nsourcedir /etc/chrony/sources.d\n"
        self.conf.write_text(text, encoding="utf-8")
        r = self.run_script()
        self.assertEqual(self.conf.read_text(encoding="utf-8"), text)
        self.assertIn("nothing changed", r.stdout)

    def test_opt_out_leaves_the_file(self):
        r = self.run_script(GTP_KEEP_DHCP_NTP="1")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.conf.read_text(encoding="utf-8"), self.original)
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["chrony.conf"])

    def test_missing_file_fails_without_creating_one(self):
        self.conf.unlink()
        r = self.run_script()
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(list(self.tmp.iterdir()), [])


class TestInstaller(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "install.sh").read_text(encoding="utf-8")

    def test_step_runs_before_chrony_is_restarted(self):
        step = self.text.index("bash scripts/chrony-no-dhcp-sources.sh /etc/chrony/chrony.conf")
        self.assertLess(step, self.text.index("systemctl restart chrony\n"))

    def test_a_failed_step_is_a_warning_not_a_failed_install(self):
        self.assertIn("bash scripts/chrony-no-dhcp-sources.sh /etc/chrony/chrony.conf \\\n  || echo \"Warning:", self.text)

    def test_script_touches_nothing_but_the_named_file(self):
        code = "\n".join(l for l in SCRIPT.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
        for word in ("systemctl", "chronyc", "rm -rf", "/etc/default", "/boot"):
            self.assertNotIn(word, code)

    def test_fixture_has_the_line_debian_ships(self):
        self.assertIn("\nsourcedir /run/chrony-dhcp\n", FIXTURE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
