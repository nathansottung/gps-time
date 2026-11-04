"""The DVB-T driver blacklist (scripts/rtl-dvb-blacklist.sh, run by sdr-stack.sh and websdr.sh).

The TV driver claims an RTL2832U dongle as soon as it's plugged in, and SDR software then can't
open it (seen on the station on 2026-11-04). The script writes our own modprobe.d file and
unloads the driver now. It runs under bash with a stub modprobe, a temp root and a fake
/proc/modules, so nothing on the host changes.
"""
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rtl-dvb-blacklist.sh"
NAMED = ["rtl2832_sdr", "dvb_usb_rtl28xxu", "rtl2832", "rtl2830"]
# What /proc/modules showed on the station with a dongle plugged in (2026-11-04), trimmed.
PROC_WITH_DONGLE = """rtl2832_sdr 24576 0 - Live 0x0000000000000000
rtl2832 20480 1 - Live 0x0000000000000000
i2c_mux 12288 1 rtl2832, Live 0x0000000000000000
dvb_usb_rtl28xxu 28672 1 - Live 0x0000000000000000
dvb_usb_v2 24576 1 dvb_usb_rtl28xxu, Live 0x0000000000000000
dvb_core 135168 1 dvb_usb_v2, Live 0x0000000000000000
regmap_i2c 12288 2 rtl2832,rtc_rv3028, Live 0x0000000000000000
rtc_rv3028 12288 0 - Live 0x0000000000000000
"""


class TestStatic(unittest.TestCase):
    def test_names_only_the_dvb_t_modules(self):
        code = "\n".join(ln for ln in SCRIPT.read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith("#"))
        self.assertIn('MODULES="rtl2832_sdr dvb_usb_rtl28xxu rtl2832 rtl2830"', code)
        for shared in ("dvb_core", "dvb_usb_v2", "videodev", "regmap_i2c", "i2c_mux", "rtc"):
            self.assertNotIn(shared, code)
        for word in ("/boot", "initramfs", "chrony", "gpsd", "pps"):
            self.assertNotIn(word, code)
        self.assertNotIn("rmmod", code)

    def test_both_installers_run_it_and_keep_it_on_removal(self):
        for name in ("sdr-stack.sh", "websdr.sh"):
            text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            with self.subTest(name):
                self.assertIn('bash "$(dirname "$0")/rtl-dvb-blacklist.sh" "$ROOT"', text)
                self.assertNotIn("dvb_usb_rtl28xxu", text)          # no second, partial copy of the rule
                self.assertNotIn("gps-time-rtl-sdr.conf", text)      # never removed by GTP_*=0


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "POSIX bash needed")
class TestScript(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        modprobe = self.bin / "modprobe"
        modprobe.write_text('#!/bin/bash\necho "modprobe $*" >> "$STUB_LOG"\n'
                            '[ -n "${STUB_BUSY:-}" ] && [ "$2" = "$STUB_BUSY" ] && exit 1\nexit 0\n')
        modprobe.chmod(modprobe.stat().st_mode | stat.S_IXUSR)
        self.root = self.tmp / "root"
        self.proc = self.tmp / "modules"
        self.log = self.tmp / "calls.log"

    def run_script(self, proc_text, **env):
        self.proc.write_text(proc_text)
        e = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}", STUB_LOG=str(self.log), **env)
        return subprocess.run(["bash", str(SCRIPT), str(self.root), str(self.proc)], env=e,
                              capture_output=True, text=True, timeout=30)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def conf(self):
        return (self.root / "etc/modprobe.d/gps-time-rtl-sdr.conf").read_text()

    def test_blacklists_and_unloads_in_order(self):
        r = self.run_script(PROC_WITH_DONGLE)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(re.findall(r"^blacklist (\S+)$", self.conf(), re.M), NAMED)
        self.assertEqual(self.calls(), ["modprobe -r rtl2832_sdr", "modprobe -r dvb_usb_rtl28xxu", "modprobe -r rtl2832"])
        self.assertIn("unloaded now: rtl2832_sdr dvb_usb_rtl28xxu rtl2832", r.stdout)
        mode = stat.S_IMODE((self.root / "etc/modprobe.d/gps-time-rtl-sdr.conf").stat().st_mode)
        self.assertEqual(mode, 0o644)

    def test_nothing_loaded_means_no_modprobe(self):
        r = self.run_script("rtc_rv3028 12288 0 - Live 0x0\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.calls(), [])
        self.assertIn("not loaded now", r.stdout)
        self.assertIn("blacklist dvb_usb_rtl28xxu", self.conf())

    def test_a_busy_driver_says_reboot_and_still_succeeds(self):
        r = self.run_script(PROC_WITH_DONGLE, STUB_BUSY="dvb_usb_rtl28xxu")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("could not unload: dvb_usb_rtl28xxu", r.stdout)
        self.assertIn("Reboot", r.stdout)

    def test_running_twice_leaves_one_file(self):
        self.run_script("")
        self.run_script("")
        files = sorted(p.name for p in (self.root / "etc/modprobe.d").iterdir())
        self.assertEqual(files, ["gps-time-rtl-sdr.conf"])
