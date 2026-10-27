"""PPS evidence capture script (scripts/capture-pps-evidence.sh) and its gpsd filter.

No root, gpsd, chrony or PPS hardware needed: the script runs against a fake
system tree and stub tools on PATH. The example position is the US Naval
Observatory.
"""

import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import gpsd_redact

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "capture-pps-evidence.sh"

TPV = {"class": "TPV", "device": "/dev/ttyAMA0", "mode": 3, "time": "2026-10-21T17:00:00.000Z",
       "lat": 38.9217, "lon": -77.0669, "altHAE": 59.0, "altMSL": 92.0, "alt": 92.0,
       "geoidSep": -33.0, "magvar": -10.9, "ecefx": 1115000.0, "ecefy": -4844000.0, "ecefz": 3986000.0,
       "epx": 2.1, "epy": 2.4, "speed": 0.0}
SKY = {"class": "SKY", "nSat": 2, "uSat": 1, "satellites": [
    {"PRN": 5, "gnssid": 0, "svid": 5, "az": 120.0, "el": 45.0, "ss": 40.0, "used": True},
    {"PRN": 12, "gnssid": 0, "svid": 12, "az": 300.0, "el": 10.0, "ss": 25.0, "used": False}]}
POLL = {"class": "POLL", "active": 1, "tpv": [TPV], "sky": [SKY]}
PPS = {"class": "PPS", "device": "/dev/pps0", "real_sec": 1792602000, "real_nsec": 0,
       "clock_sec": 1792602000, "clock_nsec": 812}
GPSD_LINES = [json.dumps(o) for o in (
    {"class": "VERSION", "release": "3.25"}, TPV, SKY, POLL, PPS)] + [
    "$GPGGA,170000.00,3855.30200,N,07704.01400,W,1,08,1.0,92.0,M,-33.0,M,,*00", "not json", "[1, 2]"]

# What would reveal the example position in any file of the archive.
POSITION_TEXT = re.compile(r"38\.92|77\.06|3855\.3|07704\.0|1115000|4844000|3986000|-10\.9")
# Wall-clock times in the script's output ("2026-10-27T02:11:38.921289162Z") can contain those
# digits by chance (a CI run failed on "…:38.92…"). They are replaced before the check: a
# position is never written as a time of day.
TIMES = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?|\d{2}:\d{2}:\d{2}(?:\.\d+)?")


def without_times(text):
    return TIMES.sub("<time>", text)


class TestPositionCheck(unittest.TestCase):
    def test_times_are_not_positions_but_positions_still_fail(self):
        self.assertNotRegex(without_times("2026-10-27T02:11:38.925960970Z pps0 1792602000.000000812#4711"), POSITION_TEXT)
        self.assertNotRegex(without_times("at 14:38:92.1150001"), POSITION_TEXT)
        self.assertRegex(without_times("2026-10-27T02:11:00Z lat 38.9217"), POSITION_TEXT)
        self.assertRegex(without_times('{"lon": -77.0669, "time": "2026-10-27T02:11:38.92Z"}'), POSITION_TEXT)


class TestConfigMode(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def mode_of(self, text):
        p = self.tmp / "config.json"
        p.write_text(text, encoding="utf-8")
        return gpsd_redact.config_mode(str(p))

    def test_modes(self):
        for m in gpsd_redact.MODES:
            self.assertEqual(self.mode_of(json.dumps({"location_display": m})), m)
        self.assertEqual(self.mode_of("{}"), "exact", "the station's own default")

    def test_unreadable_or_unknown_is_hidden(self):
        self.assertEqual(gpsd_redact.config_mode(str(self.tmp / "missing.json")), "hidden")
        self.assertEqual(self.mode_of("{not json"), "hidden")
        self.assertEqual(self.mode_of("[]"), "hidden")
        self.assertEqual(self.mode_of(json.dumps({"location_display": "fuzzy"})), "hidden")


class TestRedact(unittest.TestCase):
    def test_position_removed_by_default_in_every_mode(self):
        for m in gpsd_redact.MODES:
            for obj in (TPV, POLL):
                text = json.dumps(gpsd_redact.redact(obj, m))
                self.assertNotRegex(without_times(text), POSITION_TEXT, m)
            out = gpsd_redact.redact(TPV, m)
            self.assertEqual({k: out[k] for k in ("time", "mode", "epx", "speed")},
                             {k: TPV[k] for k in ("time", "mode", "epx", "speed")}, "timing fields stay")

    def test_include_position_follows_the_privacy_mode(self):
        self.assertEqual(gpsd_redact.redact(TPV, "exact", True), TPV)
        r = gpsd_redact.redact(TPV, "rounded", True)
        self.assertEqual((r["lat"], r["lon"], r["altMSL"]), (38.9, -77.1, 90.0))
        for k in ("altHAE", "alt", "geoidSep", "magvar", "ecefx"):
            self.assertNotIn(k, r, "rounded mode shows no ellipsoidal height or finer detail")
        self.assertNotRegex(without_times(json.dumps(gpsd_redact.redact(TPV, "hidden", True))), POSITION_TEXT)

    def test_satellite_directions_only_hidden_in_hidden_mode(self):
        sats = gpsd_redact.redact(SKY, "hidden")["satellites"]
        self.assertTrue(all(s["az"] is None and s["el"] is None for s in sats))
        self.assertEqual([s["ss"] for s in sats], [40.0, 25.0])
        self.assertEqual(gpsd_redact.redact(SKY, "rounded"), SKY)
        self.assertIsNone(gpsd_redact.redact(POLL, "hidden")["sky"][0]["satellites"][0]["az"])

    def test_input_not_changed(self):
        before = json.dumps(POLL)
        gpsd_redact.redact(POLL, "hidden")
        self.assertEqual(json.dumps(POLL), before)

    def test_cli_drops_lines_that_are_not_json_objects(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdin", io.StringIO("\n".join(GPSD_LINES) + "\n")), \
                redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(gpsd_redact.main(["--mode", "rounded"]), 0)
        rows = [json.loads(l) for l in out.getvalue().splitlines()]
        self.assertEqual([r["class"] for r in rows], ["VERSION", "TPV", "SKY", "POLL", "PPS"])
        self.assertNotRegex(without_times(out.getvalue()), POSITION_TEXT)
        self.assertIn("kept: 5; dropped (not JSON objects): 3", err.getvalue())

    def test_cli_prints_the_config_mode(self):
        out = io.StringIO()
        with redirect_stdout(out):
            gpsd_redact.main(["--config", os.path.join(tempfile.gettempdir(), "no-such-gtp-config.json")])
        self.assertEqual(out.getvalue().strip(), "hidden")


class TestScriptText(unittest.TestCase):
    """The script only reads: fixed read-only reports, no sudo, no service changes."""

    code = "\n".join(l for l in SCRIPT.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))

    def test_chronyc_runs_only_read_only_reports(self):
        self.assertEqual(re.findall(r"chronyc -n (\S+)", self.code), ["$r"])
        self.assertEqual(re.findall(r'for r in ([^;]*);', self.code),
                         ['tracking "sources -v" "sourcestats -v" activity'])

    def test_no_privilege_or_state_changes(self):
        self.assertIsNone(re.search(r"(^|[;&|({]\s*)(sudo|su|doas)\b|\beval\b", self.code, re.M), "no privilege escalation")
        self.assertIsNone(re.search(r"systemctl (start|stop|restart|reload|enable|disable|kill)", self.code))
        self.assertEqual(re.findall(r"systemctl (\w+)", self.code), ["show"])
        self.assertNotRegex(self.code, r"chronyc[^\n]*\b(makestep|settime|burst|offline|online|reselect|local|manual)\b")
        # writes go only to the temporary directory and the archive
        for target in re.findall(r"(?<![0-9&])>>? *(?!&)(\"?[^ \n|;)]+)", self.code):
            self.assertRegex(target, r'^"\$d/|^"?/dev/null', target)

    def test_gpsd_output_always_goes_through_the_filter(self):
        line = next(l for l in self.code.splitlines() if "gpspipe -w" in l)
        nxt = self.code.splitlines()[self.code.splitlines().index(line) + 1]
        self.assertIn('| python3 -I "$REDACT" --mode "$mode"', nxt)

    def test_shipped_in_the_pi_bundle(self):
        build = (ROOT / "tools" / "build_bundles.py").read_text(encoding="utf-8")
        self.assertRegex(build, r'PI_TOP = \[[^\]]*"gps_time_pi"[^\]]*"scripts"')


@unittest.skipIf(os.name == "nt" or not shutil.which("bash") or not shutil.which("python3"),
                 "POSIX bash and python3 needed")
class TestScriptRun(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.bin = self.tmp / "bin"
        self.out = self.tmp / "out"
        for p in (self.bin, self.out):
            p.mkdir()
        self.calls = self.tmp / "calls"
        sys_pps = self.tmp / "sys" / "class" / "pps" / "pps0"
        sys_pps.mkdir(parents=True)
        for f, v in {"name": "pps@12.-1", "path": "", "mode": "4369", "echo": "0",
                     "assert": "1792602000.000000812#4711", "clear": "0.000000000#0"}.items():
            (sys_pps / f).write_text(v + "\n", encoding="utf-8")
        (self.tmp / "dev").mkdir()
        (self.tmp / "dev" / "pps0").write_text("", encoding="utf-8")
        etc = self.tmp / "etc"
        (etc / "chrony" / "conf.d").mkdir(parents=True)
        (etc / "default").mkdir()
        (etc / "chrony" / "chrony.conf").write_text(
            "# comment\nrefclock PPS /dev/pps0 lock NMEA refid PPS\nrefclock SHM 0 refid NMEA noselect\n"
            "pool 2.debian.pool.ntp.org iburst\nallow 192.0.2.0/24\nmakestep 1 3\n", encoding="utf-8")
        (etc / "default" / "gpsd").write_text('DEVICES="/dev/ttyAMA0 /dev/pps0"\nGPSD_OPTIONS="-n"\n', encoding="utf-8")
        boot = self.tmp / "boot" / "firmware"
        boot.mkdir(parents=True)
        (boot / "config.txt").write_text("arm_64bit=1\ndtoverlay=pps-gpio,gpiopin=18\nenable_uart=1\n", encoding="utf-8")
        (boot / "cmdline.txt").write_text("console=tty1 root=PARTUUID=0000 rootwait\n", encoding="utf-8")
        (self.tmp / "gpsd.txt").write_text("\n".join(GPSD_LINES) + "\n", encoding="utf-8")
        self.stub("chronyc", 'echo "chronyc output for: $*"')
        self.stub("gpspipe", f'cat "{self.tmp / "gpsd.txt"}"')
        self.stub("systemctl", 'echo "Id=${@: -1}"; echo "ActiveState=active"')
        self.stub("journalctl", 'echo "2026-10-21T17:00:00+0000 pi kernel: pps pps0: new PPS source pps@12.-1"; '
                                'echo "2026-10-21T17:00:00+0000 pi kernel: eth0: link up"')
        self.stub("ppstest", "echo ppstest must not run without root; exit 9")

    def stub(self, name, body):
        f = self.bin / name
        f.write_text(f'#!/bin/bash\necho "{name} $*" >> "{self.calls}"\n{body}\n', encoding="utf-8")
        f.chmod(0o755)

    def run_script(self, mode, *args):
        cfg = self.tmp / "config.json"
        cfg.write_text(json.dumps({"location_display": mode}), encoding="utf-8")
        env = dict(os.environ, PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}", GTP_CONFIG=str(cfg),
                   GTP_SYSFS_ROOT=str(self.tmp / "sys"), GTP_DEV_ROOT=str(self.tmp / "dev"),
                   GTP_ETC_ROOT=str(self.tmp / "etc"), GTP_BOOT_ROOT=str(self.tmp / "boot"),
                   GTP_PPS_SAMPLES="2", GTP_GPSD_SECONDS="1")
        r = subprocess.run(["bash", str(SCRIPT), "--out", str(self.out), *args],
                           env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        archive = Path(r.stdout.strip())
        self.assertEqual(archive.parent, self.out)
        self.assertRegex(archive.name, r"^pps-evidence-\d{8}T\d{6}Z\.tar\.gz$")
        with tarfile.open(archive) as t:
            return {Path(m.name).name: t.extractfile(m).read().decode("utf-8")
                    for m in t.getmembers() if m.isfile()}

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "run as a normal user")
    def test_archive_contents(self):
        files = self.run_script("exact")
        self.assertEqual(sorted(files), sorted([
            "meta.txt", "pps-devices.txt", "pps-sysfs.txt", "ppstest.txt", "chrony.txt", "kernel.txt",
            "config.txt", "services.txt", "gpsd.json", "gpsd-note.txt"]))
        self.assertIn("assert: 1792602000.000000812#4711", files["pps-sysfs.txt"])
        self.assertEqual(files["pps-sysfs.txt"].count(" pps0 1792602000.000000812#4711"), 2)
        self.assertIn("skipped: ppstest needs root", files["ppstest.txt"])
        for report in ("tracking", "sources -v", "sourcestats -v", "activity"):
            self.assertIn(f"chronyc output for: -n {report}", files["chrony.txt"])
        self.assertIn("new PPS source", files["kernel.txt"])
        self.assertNotIn("eth0", files["kernel.txt"], "only PPS, GPIO, serial and voltage messages")
        self.assertIn("refclock PPS /dev/pps0", files["config.txt"])
        self.assertIn("dtoverlay=pps-gpio,gpiopin=18", files["config.txt"])
        self.assertIn('DEVICES="/dev/ttyAMA0 /dev/pps0"', files["config.txt"])
        self.assertIn("console=tty1", files["config.txt"])
        self.assertNotIn("allow 192.0.2.0/24", files["config.txt"])
        self.assertNotIn("PARTUUID", files["config.txt"])
        self.assertIn("Id=gps-time-pi.service", files["services.txt"])
        self.assertIn("location privacy mode: exact", files["meta.txt"])
        self.assertIn("position in gpsd output: removed", files["meta.txt"])
        self.assertIn("skipped: ppstest", files["meta.txt"])
        calls = (self.calls).read_text(encoding="utf-8")
        self.assertNotIn("ppstest", calls)
        self.assertTrue(all(l.split()[1] == "show" for l in calls.splitlines() if l.startswith("systemctl")))

    def test_no_position_in_any_mode_by_default(self):
        for mode in gpsd_redact.MODES:
            files = self.run_script(mode)
            classes = [json.loads(l)["class"] for l in files["gpsd.json"].splitlines()]
            self.assertEqual(classes, ["VERSION", "TPV", "SKY", "POLL", "PPS"], mode)
            for name, text in files.items():
                self.assertNotRegex(without_times(text), POSITION_TEXT, f"{mode}: {name}")

    def test_include_position_follows_the_mode(self):
        rounded = self.run_script("rounded", "--include-position")
        tpv = json.loads(rounded["gpsd.json"].splitlines()[1])
        self.assertEqual((tpv["lat"], tpv["lon"]), (38.9, -77.1))
        hidden = self.run_script("hidden", "--include-position")
        for name, text in hidden.items():
            self.assertNotRegex(without_times(text), POSITION_TEXT, name)
        sats = json.loads(hidden["gpsd.json"].splitlines()[2])["satellites"]
        self.assertIsNone(sats[0]["az"])

    def test_without_gpspipe_gpsd_output_is_skipped(self):
        (self.bin / "gpspipe").unlink()
        env_path = f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin"
        with mock.patch.dict(os.environ, {"PATH": env_path}):
            if shutil.which("gpspipe", path=env_path):
                self.skipTest("gpspipe installed on this machine")
            files = self.run_script("exact")
        self.assertNotIn("gpsd.json", files)
        self.assertIn("skipped: needs gpspipe", files["gpsd-note.txt"])

    def test_bad_option_and_unwritable_out(self):
        r = subprocess.run(["bash", str(SCRIPT), "--bogus"], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 2)
        r = subprocess.run(["bash", str(SCRIPT), "--out", str(self.tmp / "missing")],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
