"""install.sh, run from an extracted Pi bundle, finishes (v1.6.0-rc.1 regression).

v1.6.0-rc.1's bundle had no modules/, so install.sh stopped at `cp -r modules`, after it had
copied the code and restarted chrony but before the service restart. This test builds the bundle
with tools/build_bundles.py, extracts it, and runs the bundle's own install.sh to the end.

No root, network or Pi: the test runs a copy of install.sh in which the station's destinations
(/etc/..., /opt/gps-time-pi) point into a temporary root, with stub commands on PATH for what
touches the system (systemctl, apt-get, useradd, chown, chronyc, curl, ...). Everything install.sh
reads from the bundle is read for real, so anything missing from the bundle fails here. A new
absolute path in install.sh fails the test too, until it's added below: then it can't write
outside the temporary root.
"""
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from tests.test_packaging import _load_build_bundles

ROOT = Path(__file__).resolve().parents[1]

# Absolute paths in install.sh. Destinations are moved under the test root; the rest are only
# read (and stubbed or absent), or are text written into chrony.conf, never paths opened.
REDIRECT = ("/etc/", "/opt/gps-time-pi")
KNOWN = {"/dev/null", "/dev/tty", "/usr/sbin/nologin", "/usr/sbin/gpsd", "/run/chrony-log", "/run/chrony-dhcp",
         "/etc/chrony/chrony.conf", "/etc/systemd/system/", "/etc/polkit-1/rules.d", "/opt/gps-time-pi",
         "/etc/systemd/system/gps-time-modules.service", "/etc/polkit-1/rules.d/50-gps-time-pi.rules",
         "/etc/chrony/sources.d", "/nonexistent"}
ABS = re.compile(r"(?<![\w$./-])/(?:etc|opt|var|usr|run|boot|lib|sys|proc|dev|tmp|nonexistent)[\w./-]*")

STUB = """#!/bin/bash
echo "$(basename "$0") $*" >> "$STUB_LOG"
case "$(basename "$0")" in
  id) [ "$1" = -u ] && { echo 0; exit 0; }; exit 1 ;;          # root; no gps-time user yet
  curl) out=""; while [ $# -gt 0 ]; do [ "$1" = -o ] && out="$2"; shift; done; echo ephemeris > "$out" ;;
  python3)
    case "$*" in *admin_token*) exit 1 ;; esac                # no terminal: install.sh says how to make one
    exec "$REAL_PYTHON" "$@" ;;
  hostname) echo 192.0.2.10 ;;
esac
exit 0
"""
# The station's venv: pip is skipped (no network), everything else runs on this interpreter.
VENV_PY = """#!/bin/bash
case "$*" in *"-m pip"*) exit 0 ;; esac
exec "$REAL_PYTHON" "$@"
"""
STUBS = ("apt-get", "systemctl", "chronyc", "getent", "id", "useradd", "chown", "curl", "python3",
         "runuser", "pkaction", "hostname", "modprobe", "systemd-tmpfiles")


def sandboxed(text, root):
    """install.sh with its destinations under root; refuses absolute paths it doesn't know."""
    code = "\n".join(ln.split("#", 1)[0] if not ln.lstrip().startswith("#!") else ln for ln in text.splitlines())
    unknown = sorted({p for p in ABS.findall(code) if p not in KNOWN})
    if unknown:
        raise AssertionError(f"install.sh has absolute paths this test doesn't know: {unknown}. "
                             "Add each to KNOWN, and to REDIRECT if install.sh writes there.")
    for prefix in REDIRECT:
        text = re.sub(rf"(?<![\w$./-]){re.escape(prefix)}", lambda m, p=prefix: root + p, text)
    return text


def built_ui(d):
    dist = Path(d) / "web-dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>GPS Time</title>\n", encoding="utf-8")
    (dist / "version.txt").write_text("9.8.7\n", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)\n", encoding="utf-8")
    return dist


class TestSandbox(unittest.TestCase):
    def test_only_known_absolute_paths(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        out = sandboxed(text, "/tmp/r")
        self.assertIn("DEST=/tmp/r/opt/gps-time-pi", out)
        self.assertIn("/tmp/r/etc/chrony/chrony.conf", out)
        self.assertIn("logdir /run/chrony-log", out)                 # chrony.conf text stays as it is

    def test_an_unknown_path_is_refused(self):
        with self.assertRaises(AssertionError):
            sandboxed("cp x /var/lib/something\n", "/tmp/r")

    def test_bundle_lists_every_top_level_path_install_sh_reads(self):
        bb = _load_build_bundles()
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        for name in ("gps_time_pi", "schemas", "scripts", "system", "modules", "requirements.txt", "gps-time-pi.service"):
            with self.subTest(name):
                self.assertRegex(text, rf"(?<![\w/.-]){re.escape(name)}\b")
                self.assertIn(name, bb.PI_TOP)


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "POSIX bash needed")
class TestInstallFromBundle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="gtp-bundle-"))
        bb = _load_build_bundles()
        tar = cls.tmp / "gps-time-pi-deploy.tar.gz"
        bb.build_pi_tar(tar, version="9.8.7", web_dist=built_ui(cls.tmp))
        cls.extract = cls.tmp / "x"
        with tarfile.open(tar) as t:
            t.extractall(cls.extract, filter="data" if hasattr(tarfile, "data_filter") else None)
        cls.bundle = cls.extract / "gps-time"
        cls.root = cls.tmp / "root"
        cls.dest = cls.root / "opt" / "gps-time-pi"
        (cls.root / "etc" / "chrony").mkdir(parents=True)
        (cls.root / "etc" / "systemd" / "system").mkdir(parents=True)   # there on every Debian
        (cls.root / "etc" / "chrony" / "chrony.conf").write_text(
            "pool 2.debian.pool.ntp.org iburst\nsourcedir /run/chrony-dhcp\nmakestep 1 3\n", encoding="utf-8")
        venv = cls.dest / "venv" / "bin"
        venv.mkdir(parents=True)
        (venv / "python").write_text(VENV_PY)
        (venv / "python").chmod(0o755)
        bin_ = cls.tmp / "bin"
        bin_.mkdir()
        for name in STUBS:
            (bin_ / name).write_text(STUB)
            (bin_ / name).chmod(0o755)
        script = cls.bundle / "install.sandboxed.sh"
        script.write_text(sandboxed((cls.bundle / "install.sh").read_text(encoding="utf-8"), cls.root.as_posix()))
        cls.log = cls.tmp / "calls.log"
        env = {k: v for k, v in os.environ.items() if not k.startswith("GTP_")}
        env.update(PATH=f"{bin_}:{os.environ['PATH']}", STUB_LOG=str(cls.log), REAL_PYTHON=sys.executable,
                   GTP_SDR_TEST_ROOT=cls.root.as_posix(), GTP_WEBSDR_TEST_ROOT=cls.root.as_posix(),
                   GTP_NODE_TEST_ROOT=cls.root.as_posix(), GTP_CLIPS_TEST_ROOT=cls.root.as_posix())
        cls.result = subprocess.run(["bash", str(script)], cwd=cls.bundle, env=env, capture_output=True, text=True,
                                    timeout=300, stdin=subprocess.DEVNULL)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def test_install_runs_to_the_end(self):
        r = self.result
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])
        self.assertIn("Done. Open http://", r.stdout)
        self.assertNotIn("cannot stat", r.stderr)

    def test_everything_is_installed(self):
        d = self.dest
        for rel in ("gps_time_pi/server.py", "gps_time_pi/VERSION", "schemas", "scripts/logsync.sh",
                    "web/dist/index.html", "rollback/gps-time-pi-root-rollback.conf", "config.json"):
            self.assertTrue((d / rel).exists(), rel)
        self.assertEqual((d / "gps_time_pi" / "VERSION").read_text().strip(), "9.8.7")
        self.assertTrue(os.access(d / "scripts" / "logsync.sh", os.X_OK))
        units = self.root / "etc" / "systemd" / "system"
        for u in ("gps-time-pi.service", "gps-time-modules.service", "gps-time-pi-logsync.service",
                  "gps-time-pi-logflush.timer", "gps-time-pi-chrony-clients.service", "gps-time-clip.service"):
            self.assertTrue((units / u).is_file(), u)
        self.assertTrue((self.root / "etc/polkit-1/rules.d/50-gps-time-pi.rules").is_file())

    def test_every_bundled_module_is_installed(self):
        shipped = sorted(p.parent.name for p in (ROOT / "modules").glob("*/module.toml"))
        self.assertTrue(shipped)
        for name in shipped:
            with self.subTest(name):
                self.assertTrue((self.dest / "modules" / name / "module.toml").is_file())
        self.assertFalse(list((self.dest / "modules").rglob("__pycache__")))
        mode = stat.S_IMODE((self.dest / "modules").stat().st_mode)
        self.assertFalse(mode & 0o022, oct(mode))                    # not writable by group or others

    def test_chrony_conf_got_only_the_installers_edits(self):
        conf = (self.root / "etc/chrony/chrony.conf").read_text()
        self.assertIn("log tracking", conf)
        self.assertIn("logdir /run/chrony-log", conf)
        self.assertIn("makestep 1 3", conf)                          # untouched
        self.assertIn("pool 2.debian.pool.ntp.org iburst", conf)

    def test_the_service_is_restarted_last(self):
        calls = self.log.read_text().splitlines()
        self.assertIn("systemctl restart gps-time-pi", calls)
        self.assertLess(calls.index("systemctl restart chrony"), calls.index("systemctl restart gps-time-pi"))
        self.assertFalse([c for c in calls if c.startswith("systemctl enable") and "websdr" in c])
