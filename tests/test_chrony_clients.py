"""NTP client list for the unprivileged web service.

chronyd answers `chronyc clients` only over its control socket. The web
service can't use it, so a helper (user _chrony) publishes the output to a
file in /run and gps_time_pi/chrony.py reads it. No chrony or root needed here.
"""

import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import chrony

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (ROOT / "tests" / "fixtures" / "chrony" / "clients.txt").read_text(encoding="utf-8")
UNIT = ROOT / "system" / "gps-time-pi-chrony-clients.service"
SCRIPT = ROOT / "scripts" / "chrony-clients.sh"
EXPECTED = [
    {"host": "192.0.2.10", "ntp_packets": 15, "dropped": "0", "last": "34"},
    {"host": "192.0.2.11", "ntp_packets": 3, "dropped": "0", "last": "512"},
    {"host": "2001:db8::5", "ntp_packets": 42, "dropped": "1", "last": "7"},
]


class TestParse(unittest.TestCase):
    def test_rows(self):
        self.assertEqual(chrony.parse_clients(FIXTURE), EXPECTED)

    def test_header_only_is_an_empty_list_not_unknown(self):
        self.assertEqual(chrony.parse_clients("\n".join(FIXTURE.splitlines()[:2]) + "\n"), [])


class TestPublishedFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "chrony-clients.txt")
        p = mock.patch.object(chrony, "CLIENTS_FILE", self.path)
        p.start()
        self.addCleanup(p.stop)

    def write(self, age_s=0.0):
        Path(self.path).write_text(FIXTURE, encoding="utf-8")
        t = time.time() - age_s
        os.utime(self.path, (t, t))

    def no_chronyc(self):
        return mock.patch.object(chrony, "run_chronyc", lambda *a: (False, ""))

    def test_fresh_file_is_used_without_running_chronyc(self):
        self.write()
        with mock.patch.object(chrony, "run_chronyc", side_effect=AssertionError("chronyc must not run")):
            self.assertEqual(chrony.clients(), EXPECTED)

    def test_stale_file_is_ignored(self):
        self.write(age_s=chrony.CLIENTS_MAX_AGE_S + 30)
        self.assertIsNone(chrony.published_clients())
        with self.no_chronyc():
            self.assertIsNone(chrony.clients(), "a stopped helper must read as UNKNOWN, not as an old list")

    def test_missing_file_falls_back_to_chronyc(self):
        with mock.patch.object(chrony, "run_chronyc", lambda *a: (True, FIXTURE)):
            self.assertEqual(chrony.clients(), EXPECTED)

    def test_missing_file_and_refused_chronyc_is_unknown(self):
        with self.no_chronyc():
            self.assertIsNone(chrony.clients())

    def test_file_from_the_future_is_ignored(self):
        self.write(age_s=-3600)
        self.assertIsNone(chrony.published_clients())


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "POSIX bash needed")
class TestHelperScript(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.out = self.tmp / "run"
        self.out.mkdir()
        self.argv = self.tmp / "argv"

    def fake_chronyc(self, body):
        f = self.bin / "chronyc"
        f.write_text(f'#!/bin/bash\necho "$*" >> "{self.argv}"\n{body}\n', encoding="utf-8")
        f.chmod(0o755)

    def run_once(self):
        env = dict(os.environ, PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                   RUNTIME_DIRECTORY=str(self.out), GTP_CLIENTS_ONCE="1")
        return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=30)

    def test_publishes_exactly_the_fixed_command(self):
        (self.tmp / "fixture").write_text(FIXTURE, encoding="utf-8")
        self.fake_chronyc(f'cat "{self.tmp / "fixture"}"')
        r = self.run_once()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.argv.read_text().splitlines(), ["-n clients"])
        published = (self.out / "chrony-clients.txt").read_text(encoding="utf-8")
        self.assertEqual(chrony.parse_clients(published), EXPECTED)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["chrony-clients.txt"])

    def test_failure_removes_the_old_list_and_logs(self):
        (self.out / "chrony-clients.txt").write_text(FIXTURE, encoding="utf-8")
        self.fake_chronyc('echo "501 Not authorised"; exit 1')
        r = self.run_once()
        self.assertFalse((self.out / "chrony-clients.txt").exists())
        self.assertIn("501 Not authorised", r.stderr)


class TestUnitAndInstaller(unittest.TestCase):
    def settings(self):
        out = {}
        for line in UNIT.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^([A-Za-z]+)=(.*)$", line)
            if m:
                out.setdefault(m.group(1), []).append(m.group(2))
        return out

    def test_helper_runs_as_chrony_never_root(self):
        s = self.settings()
        self.assertEqual(s["User"], ["_chrony"])
        self.assertEqual(s["Group"], ["gps-time"])
        self.assertEqual(s["NoNewPrivileges"], ["yes"])
        self.assertEqual(s["CapabilityBoundingSet"], [""])
        self.assertEqual(s["ProtectClock"], ["yes"])

    def test_helper_can_reach_the_socket_and_only_the_web_service_reads_the_list(self):
        s = self.settings()
        self.assertEqual(s["ReadWritePaths"], ["/run/chrony"])
        self.assertEqual(s["RuntimeDirectory"], ["gps-time-pi"])
        self.assertEqual(s["RuntimeDirectoryMode"], ["0750"])
        self.assertEqual(s["UMask"], ["0027"])
        self.assertEqual(chrony.CLIENTS_FILE.replace("\\", "/"), "/run/gps-time-pi/chrony-clients.txt")

    def test_helper_follows_chrony(self):
        s = self.settings()
        for key in ("Requires", "After", "PartOf"):
            self.assertEqual(s[key], ["chrony.service"], key)

    def test_script_is_run_through_an_interpreter_and_takes_no_input(self):
        self.assertEqual(self.settings()["ExecStart"], ["/bin/bash /opt/gps-time-pi/scripts/chrony-clients.sh"])
        code = "\n".join(l for l in SCRIPT.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
        self.assertEqual(re.findall(r"chronyc[^\n;)]*", code), ["chronyc -n clients 2>&1", "chronyc -n clients failed: $out\" >&2"])
        self.assertNotRegex(code, r"\bread\b|\$1|\$@|\beval\b")

    def test_web_service_does_not_get_the_control_socket(self):
        unit = (ROOT / "gps-time-pi.service").read_text(encoding="utf-8")
        self.assertIn("ReadWritePaths=/opt/gps-time-pi\n", unit)
        self.assertNotIn("/run/chrony", "\n".join(l for l in unit.splitlines() if not l.startswith("#")))

    def test_installer_installs_and_starts_the_helper_after_the_service_user(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        cp = text.index("cp system/gps-time-pi-chrony-clients.service /etc/systemd/system/")
        self.assertLess(text.index("useradd --system"), cp)
        self.assertLess(cp, text.index("systemctl enable gps-time-pi-chrony-clients.service"))
        self.assertIn("systemctl restart gps-time-pi-chrony-clients.service \\\n  || echo", text)


if __name__ == "__main__":
    unittest.main()
