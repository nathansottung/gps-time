"""Deploy scripts stop at the first failure and verify the upload (review GPS-021).

The scripts run against fake python3/ssh/scp/sudo on PATH: nothing leaves the
machine and no Pi is needed. The bash script is exercised on POSIX (CI), the
PowerShell script on Windows; static checks run everywhere.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SH = ROOT / "scripts" / "deploy-to-pi.sh"
PS1 = ROOT / "scripts" / "deploy-to-pi.ps1"


def _code(path):
    return "\n".join(l for l in path.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))


class TestStatic(unittest.TestCase):
    def test_no_fixed_tmp_upload(self):
        for p in (SH, PS1):
            with self.subTest(script=p.name):
                self.assertNotIn("/tmp/", _code(p))

    def test_archive_verified_before_install(self):
        for p in (SH, PS1):
            with self.subTest(script=p.name):
                code = _code(p)
                self.assertLess(code.index("sha256sum -c -"), code.index("sudo bash install.sh"))

    def test_powershell_checks_every_native_exit_code(self):
        code = _code(PS1)
        self.assertIn("$LASTEXITCODE -ne 0", code)
        # every python/scp/ssh call goes through Invoke-Native
        for line in code.splitlines():
            if re.search(r"^\s*&?\s*(python|scp|ssh|corepack)\b", line.strip()):
                self.fail(f"native call without an exit-code check: {line.strip()}")
        for exe in ("python", "scp", "ssh", "corepack"):
            self.assertRegex(code, rf"Invoke-Native {exe}\b")

    def test_web_ui_built_before_the_bundle(self):
        for p in (SH, PS1):
            with self.subTest(script=p.name):
                code = _code(p)
                self.assertLess(code.index("--frozen-lockfile"), code.index("build_bundles.py"))

    def test_stale_archive_removed_before_build(self):
        for p, rm in ((SH, 'rm -f "$ARCHIVE"'), (PS1, "Remove-Item $Archive")):
            with self.subTest(script=p.name):
                code = _code(p)
                self.assertLess(code.index(rm), code.index("build_bundles.py"))


def _install_command(sha):
    """The remote command both scripts send for the verify-and-install step."""
    return ("set -e; cd ~/gps-time-deploy && "
            f"echo '{sha}  gps-time-pi-deploy.tar.gz' | sha256sum -c - && "
            "tar -xzf gps-time-pi-deploy.tar.gz && cd gps-time && sudo bash install.sh")


class _FakeTree:
    """A copy of the script in a temp repo layout, plus a fake remote home."""

    def __init__(self, script):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        (self.repo / "dist").mkdir()
        (self.repo / "web").mkdir()
        shutil.copy2(script, self.repo / "scripts" / script.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.log = self.tmp / "calls.log"
        self.log.write_text("", encoding="utf-8")

    def calls(self):
        return self.log.read_text(encoding="utf-8").splitlines()

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


@unittest.skipIf(os.name == "nt" or not shutil.which("bash") or not shutil.which("sha256sum"),
                 "POSIX bash with sha256sum needed")
class TestBashScript(unittest.TestCase):
    def setUp(self):
        self.t = _FakeTree(SH)
        self.addCleanup(self.t.cleanup)
        fakes = {
            "python3": """
                echo "python3 $*" >> "$FAKE_LOG"
                if [ "$1" = tools/build_bundles.py ]; then
                  [ "${FAKE_BUILD_FAIL:-}" = 1 ] && exit 1
                  [ "${FAKE_BUILD_EMPTY:-}" = 1 ] && exit 0
                  d=$(mktemp -d); mkdir -p "$d/gps-time"; echo 'echo installed' > "$d/gps-time/install.sh"
                  tar -czf dist/gps-time-pi-deploy.tar.gz -C "$d" gps-time
                fi""",
            "corepack": """
                echo "corepack $*" >> "$FAKE_LOG"
                [ "${FAKE_WEB_FAIL:-}" = 1 ] && [ "$3" = build ] && exit 1
                exit 0""",
            "ssh": """
                # exact argv: one line per call, arguments separated by US (0x1f)
                { printf '%s\\037' "$@"; printf '\\n'; } >> "$FAKE_LOG.argv"
                [ "$1" = -t ] && shift
                echo "ssh $1" >> "$FAKE_LOG"
                HOME="$FAKE_HOME" bash -c "$2" """,
            "scp": """
                echo "scp $2" >> "$FAKE_LOG"
                cp "$1" "$FAKE_HOME/${2#*:}"
                [ "${FAKE_CORRUPT:-}" = 1 ] && printf x >> "$FAKE_HOME/${2#*:}"
                [ "${FAKE_SCP_FAIL:-}" = 1 ] && exit 1
                exit 0""",
            "sudo": """echo "sudo $*" >> "$FAKE_LOG" """,
        }
        for name, body in fakes.items():
            f = self.t.bin / name
            f.write_text("#!/usr/bin/env bash\n" + textwrap.dedent(body).strip() + "\n", encoding="utf-8")
            f.chmod(0o755)

    def run_script(self, **env):
        e = dict(os.environ, PATH=f"{self.t.bin}{os.pathsep}{os.environ['PATH']}",
                 FAKE_LOG=str(self.t.log), FAKE_HOME=str(self.t.home), **env)
        return subprocess.run(["bash", str(self.t.repo / "scripts" / SH.name), "pi.example", "pi"],
                              env=e, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)

    def ssh_argv(self):
        lines = Path(str(self.t.log) + ".argv").read_text(encoding="utf-8").splitlines()
        return [line.split("\x1f")[:-1] for line in lines]

    def test_exact_ssh_argv(self):
        for tty, flag in (("1", ["-t"]), ("0", [])):
            with self.subTest(tty=tty):
                Path(str(self.t.log) + ".argv").unlink(missing_ok=True)
                r = self.run_script(GTP_DEPLOY_TTY=tty)
                self.assertEqual(r.returncode, 0, r.stderr)
                sha = hashlib.sha256((self.t.repo / "dist" / "gps-time-pi-deploy.tar.gz").read_bytes()).hexdigest()
                prepare, install = self.ssh_argv()
                self.assertEqual(prepare, ["pi@pi.example", "rm -rf ~/gps-time-deploy && mkdir -m 0700 ~/gps-time-deploy"])
                self.assertEqual(install[:-1], flag + ["pi@pi.example"])
                self.assertEqual(" ".join(install[-1].split()), _install_command(sha))

    def test_success_verifies_then_installs(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self.t.calls()
        self.assertEqual(calls[:3], ["corepack pnpm install --frozen-lockfile", "corepack pnpm run build",
                                     "python3 tools/build_bundles.py"])
        self.assertIn("scp pi@pi.example:gps-time-deploy/gps-time-pi-deploy.tar.gz", calls)
        self.assertEqual(calls[-1], "sudo bash install.sh")
        self.assertIn("gps-time-pi-deploy.tar.gz: OK", r.stdout)

    def test_failed_build_uploads_nothing(self):
        (self.t.repo / "dist" / "gps-time-pi-deploy.tar.gz").write_bytes(b"stale")
        r = self.run_script(FAKE_BUILD_FAIL="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(any(c.startswith(("scp", "ssh", "sudo")) for c in self.t.calls()), self.t.calls())

    def test_failed_web_build_stops_before_the_bundle(self):
        (self.t.repo / "dist" / "gps-time-pi-deploy.tar.gz").write_bytes(b"stale")
        r = self.run_script(FAKE_WEB_FAIL="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(any(c.startswith(("python3", "scp", "ssh", "sudo")) for c in self.t.calls()), self.t.calls())

    def test_build_without_archive_uploads_nothing(self):
        (self.t.repo / "dist" / "gps-time-pi-deploy.tar.gz").write_bytes(b"stale")
        r = self.run_script(FAKE_BUILD_EMPTY="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(any(c.startswith(("scp", "ssh")) for c in self.t.calls()))

    def test_corrupted_upload_is_not_installed(self):
        r = self.run_script(FAKE_CORRUPT="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(any(c.startswith("sudo") for c in self.t.calls()), self.t.calls())

    def test_failed_upload_stops(self):
        r = self.run_script(FAKE_SCP_FAIL="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(any(c.startswith("sudo") for c in self.t.calls()))


@unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "Windows PowerShell needed")
class TestPowerShellScript(unittest.TestCase):
    def setUp(self):
        self.t = _FakeTree(PS1)
        self.addCleanup(self.t.cleanup)
        fakes = {
            "python": r"""
                echo python %*>> "%FAKE_LOG%"
                if not "%1"=="tools/build_bundles.py" exit /b 0
                if "%FAKE_BUILD_FAIL%"=="1" exit /b 1
                echo bundle> dist\gps-time-pi-deploy.tar.gz
                exit /b 0""",
            "corepack": r"""
                echo corepack %*>> "%FAKE_LOG%"
                if "%FAKE_WEB_FAIL%"=="1" if "%3"=="build" exit /b 1
                exit /b 0""",
            "scp": r"""
                echo scp %2>> "%FAKE_LOG%"
                if "%FAKE_SCP_FAIL%"=="1" exit /b 1
                exit /b 0""",
            # The real interpreter records the exact argv (parsed by the same C
            # runtime rules as ssh.exe); "python" on PATH is the fake above.
            "ssh": rf"""
                echo ssh %*>> "%FAKE_LOG%"
                "{sys.executable}" "%~dp0record_argv.py" %*
                exit /b 0""",
        }
        (self.t.bin / "record_argv.py").write_text(
            "import json, os, sys\n"
            "with open(os.environ['FAKE_LOG'] + '.argv', 'a', encoding='utf-8') as f:\n"
            "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n", encoding="utf-8")
        for name, body in fakes.items():
            (self.t.bin / f"{name}.cmd").write_text("@echo off\r\n" + textwrap.dedent(body).strip().replace("\n", "\r\n") + "\r\n",
                                                   encoding="ascii")

    def run_script(self, **env):
        e = dict(os.environ, PATH=f"{self.t.bin}{os.pathsep}{os.environ['PATH']}", FAKE_LOG=str(self.t.log), **env)
        return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                               str(self.t.repo / "scripts" / PS1.name), "-PiHost", "pi.example"],
                              env=e, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)

    def ssh_argv(self):
        lines = Path(str(self.t.log) + ".argv").read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines]

    def test_exact_ssh_argv(self):
        # With a terminal the install call is exactly: -t, user@host, command.
        # A joined "-tuser@host ..." makes ssh fail with "Bad configuration option".
        for tty, flag in (("1", ["-t"]), ("0", [])):
            with self.subTest(tty=tty):
                Path(str(self.t.log) + ".argv").unlink(missing_ok=True)
                r = self.run_script(GTP_DEPLOY_TTY=tty)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                sha = hashlib.sha256((self.t.repo / "dist" / "gps-time-pi-deploy.tar.gz").read_bytes()).hexdigest()
                prepare, install = self.ssh_argv()
                self.assertEqual(prepare, ["pi@pi.example", "rm -rf ~/gps-time-deploy && mkdir -m 0700 ~/gps-time-deploy"])
                self.assertEqual(install, flag + ["pi@pi.example", _install_command(sha)])

    def test_success_installs_with_the_archive_checksum(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        sha = hashlib.sha256((self.t.repo / "dist" / "gps-time-pi-deploy.tar.gz").read_bytes()).hexdigest()
        last = self.t.calls()[-1]
        self.assertTrue(last.startswith("ssh"), self.t.calls())
        self.assertIn(sha, last)
        self.assertIn("sudo bash install.sh", last)

    def test_failed_build_uploads_nothing(self):
        (self.t.repo / "dist" / "gps-time-pi-deploy.tar.gz").write_bytes(b"stale")
        r = self.run_script(FAKE_BUILD_FAIL="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(any(c.startswith(("scp", "ssh")) for c in self.t.calls()), self.t.calls())

    def test_failed_web_build_stops_before_the_bundle(self):
        (self.t.repo / "dist" / "gps-time-pi-deploy.tar.gz").write_bytes(b"stale")
        r = self.run_script(FAKE_WEB_FAIL="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(any(c.startswith(("python", "scp", "ssh")) for c in self.t.calls()), self.t.calls())

    def test_failed_upload_stops_before_install(self):
        r = self.run_script(FAKE_SCP_FAIL="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(any("install.sh" in c for c in self.t.calls()), self.t.calls())


if __name__ == "__main__":
    unittest.main()
