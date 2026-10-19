"""RAM-log flush with caps (rc.9 item 1; GPS-011, GPS-012).

The rc.8 soak run showed the hourly flush copying the whole RAM log (10 MB,
growing) to the SD card every hour, with logrotate keeping rotated full copies.
The script tests run scripts/logsync.sh against temporary directories with a
fake chronyc; they need POSIX bash and coreutils and run in CI.
"""

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import chrony, system

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "logsync.sh"
HDR = "   Date (UTC) Time     IP Address   St   Freq ppm   Skew ppm     Offset L Co  Offset sd Rem. corr. Root delay Root disp. Max. error\n"


def line(i):
    """One tracking.log line, about 140 bytes."""
    s = 1_790_000_000 + 16 * i
    t = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(s))
    return f"{t} GPS              1     10.295      0.009  {i % 7 + 1}.741e-07 N  1  1.789e-07  1.281e-08  1.000e-09  7.005e-06  2.612e-05\n"


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "POSIX bash needed")
class TestFlushScript(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.ram, self.disk = self.tmp / "run", self.tmp / "var"
        self.ram.mkdir()
        self.calls = self.tmp / "chronyc-calls"
        fake = self.tmp / "chronyc"
        fake.write_text(f'#!/bin/bash\necho "$*" >> "{self.calls}"\n', encoding="utf-8")
        fake.chmod(0o755)
        self.env = dict(os.environ, GTP_LOG_RAM=str(self.ram), GTP_LOG_DISK=str(self.disk),
                        GTP_LOG_RAM_MAX="20000", GTP_LOG_DISK_MAX="50000", GTP_CHRONYC=str(fake))
        self.n = 0

    def write(self, count):
        with open(self.ram / "tracking.log", "a", encoding="ascii", newline="\n") as f:
            for _ in range(count):
                f.write(line(self.n))
                self.n += 1

    def run_script(self, action="flush"):
        r = subprocess.run(["bash", str(SCRIPT), action], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def sd(self):
        p = self.disk / "station-tracking.txt"
        return p.read_text(encoding="ascii") if p.exists() else ""

    def test_only_new_lines_are_appended(self):
        self.write(10)
        self.run_script()
        first = self.sd()
        self.assertEqual(first.count("\n"), 10)
        self.run_script()                                   # nothing new
        self.assertEqual(self.sd(), first)
        self.write(5)
        self.run_script()
        self.assertEqual(self.sd().count("\n"), 15)
        self.assertEqual(self.sd(), (self.ram / "tracking.log").read_text(encoding="ascii"))

    def test_bytes_written_per_flush_are_the_new_bytes_only(self):
        self.write(100)
        self.run_script()
        before = os.path.getsize(self.disk / "station-tracking.txt")
        self.write(3)
        self.run_script()
        grown = os.path.getsize(self.disk / "station-tracking.txt") - before
        self.assertEqual(grown, sum(len(line(i)) for i in range(100, 103)))

    def test_ram_cap_rotates_and_tells_chrony(self):
        self.write(200)                                     # about 28 kB > 20 kB
        self.run_script()
        self.assertFalse((self.ram / "tracking.log").exists())
        self.assertTrue((self.ram / "tracking.log.1").exists())
        self.assertEqual(self.calls.read_text().split(), ["cyclelogs"])
        self.assertEqual(self.sd().count("\n"), 200, "nothing is lost at the rotation")
        self.write(10)                                      # chrony reopened a new file
        self.run_script()
        self.assertEqual(self.sd().count("\n"), 210)

    def test_ram_rotation_keeps_one_previous_file(self):
        for _ in range(3):
            self.write(200)
            self.run_script()
        self.assertEqual(sorted(p.name for p in self.ram.iterdir()), ["tracking.log.1"])

    def test_disk_cap_keeps_one_previous_copy(self):
        for _ in range(4):
            self.write(140)                                  # about 20 kB a round
            self.run_script()
        names = sorted(p.name for p in self.disk.iterdir() if not p.name.startswith("."))
        self.assertEqual(names, ["station-tracking.txt", "station-tracking.txt.prev"])
        total = sum(os.path.getsize(self.disk / n) for n in names)
        self.assertLess(total, 2 * 50000 + 30000)

    def test_sd_copy_is_not_a_logrotate_target(self):
        self.write(5)
        self.run_script()
        self.assertFalse(any(p.name.endswith(".log") for p in self.disk.iterdir()),
                         "Debian's rule rotates /var/log/chrony/*.log; the SD copy must not match")

    def test_new_ram_file_after_a_reboot_starts_from_zero(self):
        self.write(10)
        self.run_script()
        (self.ram / "tracking.log").unlink()                 # RAM is lost at a reboot
        self.write(4)
        self.run_script()
        self.assertEqual(self.sd().count("\n"), 14)

    def test_no_ram_log_is_not_an_error(self):
        self.run_script()
        self.assertEqual(self.sd(), "")

    def test_restore_puts_the_newest_part_back_and_does_not_duplicate_it(self):
        self.write(300)
        self.run_script()                                    # rotates; SD has 300 lines
        shutil.rmtree(self.ram)                              # reboot
        self.run_script("restore")
        restored = (self.ram / "tracking.log").read_text(encoding="ascii")
        self.assertLessEqual(len(restored), 10000)
        self.assertTrue(restored.endswith(line(299)), "the newest lines come back")
        self.assertTrue(restored.splitlines()[0].startswith("20"), "no cut line at the start")
        before = self.sd()
        self.run_script()                                    # flush right after boot: nothing new
        self.assertEqual(self.sd(), before)
        self.write(2)
        self.run_script()
        self.assertEqual(self.sd().count("\n"), 302)

    def test_first_restore_after_the_upgrade_reads_the_old_copy(self):
        self.disk.mkdir()
        (self.disk / "tracking.log").write_bytes((HDR + "".join(line(i) for i in range(20))).encode("ascii"))
        shutil.rmtree(self.ram)
        self.run_script("restore")
        self.assertEqual((self.ram / "tracking.log").read_text(encoding="ascii").count("\n"), 21)
        self.assertTrue((self.disk / "tracking.log").exists(), "the old copy is left to age out, not deleted")

    def test_restore_leaves_an_existing_ram_log_alone(self):
        self.write(3)
        before = (self.ram / "tracking.log").read_text(encoding="ascii")
        self.run_script("restore")
        self.assertEqual((self.ram / "tracking.log").read_text(encoding="ascii"), before)


class TestScriptText(unittest.TestCase):
    def test_no_whole_file_copy(self):
        code = "\n".join(l for l in SCRIPT.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
        self.assertNotIn('cp -p "$RAM/tracking.log"', code)
        self.assertIn('tail -c +$((from + 1))', code)
        self.assertIn("cyclelogs", code)

    def test_units_unchanged(self):
        svc = (ROOT / "system" / "gps-time-pi-logflush.service").read_text(encoding="utf-8")
        self.assertIn("ExecStart=/bin/bash /opt/gps-time-pi/scripts/logsync.sh flush", svc)
        timer = (ROOT / "system" / "gps-time-pi-logflush.timer").read_text(encoding="utf-8")
        self.assertIn("OnUnitActiveSec=1h", timer)


class TestPythonSide(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_path_is_resolved_on_every_call(self):
        ram = self.tmp / "tracking.log"
        sd = self.tmp / "station-tracking.txt"
        with mock.patch.object(chrony, "TRACKING_CANDIDATES", (str(ram), str(sd))), \
                mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GTP_TRACKING_LOG", None)
            self.assertEqual(chrony.tracking_log_path(), str(ram), "nothing yet: the RAM path")
            sd.write_text(line(0), encoding="ascii")
            self.assertEqual(chrony.tracking_log_path(), str(sd))
            ram.write_text(line(1), encoding="ascii")
            self.assertEqual(chrony.tracking_log_path(), str(ram), "the RAM log, once chrony writes it")

    def test_history_reads_the_rotated_part_first(self):
        ram = self.tmp / "tracking.log"
        (self.tmp / "tracking.log.1").write_bytes((HDR + "".join(line(i) for i in range(5))).encode("ascii"))
        ram.write_text("".join(line(i) for i in range(5, 8)), encoding="ascii")
        with mock.patch.object(chrony, "TRACKING_LOG", str(ram)):
            h = chrony.history()
        self.assertEqual(len(h["points"]), 8)
        ts = [p["t"] for p in h["points"]]
        self.assertEqual(ts, sorted(ts))

    @unittest.skipIf(os.name == "nt", "system.diagnostics() reads Linux interfaces")
    def test_ramlog_reports_the_sd_copy(self):
        ram = self.tmp / "tracking.log"
        ram.write_text(line(0), encoding="ascii")
        sd = self.tmp / "station-tracking.txt"
        sd.write_text(line(0) * 10, encoding="ascii")
        with mock.patch.object(chrony, "TRACKING_LOG", str(ram)), \
                mock.patch.object(chrony, "SD_COPIES", (str(sd), str(self.tmp / "tracking-old.log"))):
            d = system.diagnostics()
        r = d["ramlog"]
        self.assertEqual(r["sd_copy"], str(sd))
        self.assertIsNotNone(r["flushed_age_s"])
        self.assertGreater(r["sd_size_kb"], 1)


if __name__ == "__main__":
    unittest.main()
