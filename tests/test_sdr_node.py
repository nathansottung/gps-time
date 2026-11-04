"""SDR node mode (scripts/node.sh) and where a Pi's clock gets its time (gps_time_pi/timequality.py).

The script runs under bash with stub commands and every path under a temp root; the time quality
uses canned `chronyc -n tracking` text. Addresses are documentation ones (192.0.2.0/24).
"""
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gps_time_pi import timequality as tq

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = ROOT / "system"
SCRIPT = ROOT / "scripts" / "node.sh"

TRACK_STATION = """Reference ID    : 47505300 (GPS)
Stratum         : 1
System time     : 0.000000213 seconds slow of NTP time
Root delay      : 0.000000001 seconds
Root dispersion : 0.000009500 seconds
Leap status     : Normal
"""
TRACK_NODE = """Reference ID    : C000020A (192.0.2.10)
Stratum         : 2
System time     : 0.000012000 seconds fast of NTP time
Root delay      : 0.000400000 seconds
Root dispersion : 0.000050000 seconds
Leap status     : Normal
"""
TRACK_UNSYNC = """Reference ID    : 00000000 ()
Stratum         : 0
Leap status     : Not synchronised
"""


class TestTimeQuality(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for name in ("NODE_ENV", "PEER_ENV"):
            p = mock.patch.object(tq, name, self.tmp / name)
            p.start()
            self.addCleanup(p.stop)

    def test_the_station_on_its_reference_clock(self):
        r = tq.current(run=lambda *a: (True, TRACK_STATION))
        self.assertEqual((r["role"], r["source"], r["reference"], r["stratum"]), ("station", "refclock", "GPS", 1))
        self.assertAlmostEqual(r["max_error_s"]["value"], 0.000000213 + 0.0000095 + 0.0000000005, places=12)
        self.assertEqual(r["max_error_s"]["provenance"], "calculated")
        self.assertIn("refclock GPS", r["label"])

    def test_a_node_is_labelled_ntp(self):
        (self.tmp / "NODE_ENV").write_text("GTP_NODE_STATION=192.0.2.10\n")
        r = tq.current(run=lambda *a: (True, TRACK_NODE))
        self.assertEqual((r["role"], r["station"], r["source"], r["reference"]), ("sdr-node", "192.0.2.10", "ntp", "192.0.2.10"))
        self.assertIn("ntp from 192.0.2.10, within ±", r["label"])

    def test_unknown_when_chrony_cant_tell(self):
        self.assertEqual(tq.current(run=lambda *a: (False, ""))["source"], "unknown")
        r = tq.current(run=lambda *a: (True, TRACK_UNSYNC))
        self.assertEqual(r["source"], "unknown")
        self.assertIn("UNKNOWN", r["label"])

    def test_the_station_knows_its_node(self):
        (self.tmp / "PEER_ENV").write_text("GTP_SDR_NODE=192.0.2.20\n")
        self.assertEqual(tq.role(), ("station", "192.0.2.20"))
        self.assertEqual(tq.current(run=lambda *a: (True, TRACK_STATION))["sdr_node"], "192.0.2.20")


class TestTemplates(unittest.TestCase):
    def test_lan_listeners_are_for_the_station_only(self):
        rtl = (SYSTEM / "gps-time-rtl-tcp-node.conf").read_text(encoding="utf-8")
        self.assertIn("-a 0.0.0.0 -p 1234", rtl)
        self.assertEqual(re.findall(r"^IPAddressAllow=(.*)$", rtl, re.M), ["@ADDR@"])
        rb = (SYSTEM / "gps-time-readsb-node.conf").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^IPAddressAllow=(.*)$", rb, re.M), ["localhost @ADDR@"])
        start = re.search(r"^ExecStart=(/usr/bin/readsb.*)$", rb, re.M).group(1)
        self.assertNotRegex(start, r"--(lat|lon)\b")
        for port in ("ri", "ro", "sbs", "bi"):
            self.assertIn(f"--net-{port}-port 0", start)

    def test_the_stations_reader_reaches_the_node_only(self):
        u = (SYSTEM / "gps-time-readsb-node.service").read_text(encoding="utf-8")
        self.assertIn("Conflicts=gps-time-readsb.service", u)
        self.assertEqual(re.findall(r"^IPAddressAllow=(.*)$", u, re.M), ["@ADDR@"])
        self.assertIn("\nIPAddressDeny=any\n", u)
        self.assertIn("--net-connector @ADDR@,30005,beast_in", u)
        self.assertIn("--write-json /run/readsb", u)

    def test_the_script_touches_no_station_timing(self):
        code = "\n".join(ln for ln in SCRIPT.read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith("#"))
        for word in ("gpsd", "pps", "/boot/", "refclock", "makestep"):
            self.assertNotIn(word, code)
        # chrony is changed on the node only, by one sources.d file, and only for GTP_NODE=1
        self.assertIn('CHRONY_SOURCES="$ROOT/etc/chrony/sources.d/gps-time-node.sources"', code)
        self.assertNotIn("chrony.conf\" >", code)


STUB = """#!/bin/bash
echo "$(basename "$0") $*" >> "$STUB_LOG"
exit 0
"""


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "POSIX bash needed")
class TestScript(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        for cmd in ("systemctl", "chronyc"):
            p = self.bin / cmd
            p.write_text(STUB)
            p.chmod(p.stat().st_mode | stat.S_IXUSR)
        self.root = self.tmp / "root"
        (self.root / "etc/chrony").mkdir(parents=True)
        (self.root / "etc/chrony/chrony.conf").write_text("pool 2.debian.pool.ntp.org iburst\nsourcedir /etc/chrony/sources.d\n")
        self.units = self.root / "etc/systemd/system"
        self.units.mkdir(parents=True)
        self.log = self.tmp / "calls.log"

    def run_script(self, **env):
        base = {k: v for k, v in os.environ.items() if not k.startswith("GTP_")}
        base.update(PATH=f"{self.bin}:{os.environ['PATH']}", GTP_NODE_TEST_ROOT=str(self.root), STUB_LOG=str(self.log))
        base.update(env)
        return subprocess.run(["bash", str(SCRIPT)], env=base, capture_output=True, text=True, timeout=60)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_unset_changes_nothing(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_a_node_follows_the_station_and_serves_it_only(self):
        (self.units / "gps-time-rtl-tcp.service").write_text("[Unit]\n")
        (self.units / "gps-time-readsb.service").write_text("[Unit]\n")
        r = self.run_script(GTP_NODE="1", GTP_NODE_STATION="192.0.2.10")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        src = (self.root / "etc/chrony/sources.d/gps-time-node.sources").read_text()
        self.assertIn("server 192.0.2.10 iburst minpoll 4 maxpoll 6 prefer", src)
        self.assertIn("chronyc reload sources", self.calls())
        rtl = (self.units / "gps-time-rtl-tcp.service.d/gps-time-node.conf").read_text()
        self.assertIn("IPAddressAllow=192.0.2.10", rtl)
        self.assertNotIn("@ADDR@", rtl)
        rb = (self.units / "gps-time-readsb.service.d/gps-time-node.conf").read_text()
        self.assertIn("IPAddressAllow=localhost 192.0.2.10", rb)
        self.assertEqual((self.root / "etc/chrony/chrony.conf").read_text(),
                         "pool 2.debian.pool.ntp.org iburst\nsourcedir /etc/chrony/sources.d\n")   # chrony.conf untouched

    def test_the_station_reads_its_node(self):
        r = self.run_script(GTP_SDR_NODE="192.0.2.20")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        u = (self.units / "gps-time-readsb-node.service").read_text()
        self.assertIn("--net-connector 192.0.2.20,30005,beast_in", u)
        self.assertIn("IPAddressAllow=192.0.2.20", u)
        self.assertIn("systemctl enable gps-time-readsb-node.service", self.calls())
        drop = (self.units / "gps-time-modules.service.d/gps-time-sdr-node.conf").read_text()
        self.assertEqual(re.findall(r"^IPAddressAllow=(.*)$", drop, re.M), ["192.0.2.20"])
        self.assertFalse([c for c in self.calls() if c.startswith("chronyc")])                # the station's chrony: never

    def test_refusals(self):
        for env in ({"GTP_NODE": "1"}, {"GTP_NODE": "1", "GTP_NODE_STATION": "station.lan"},
                    {"GTP_NODE": "1", "GTP_NODE_STATION": "192.0.2.300"}, {"GTP_SDR_NODE": "a; rm -rf /"},
                    {"GTP_NODE": "maybe"}):
            with self.subTest(env=env):
                r = self.run_script(**env)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("nothing changed", r.stderr)
        self.assertFalse((self.root / "etc/chrony/sources.d").exists())

    def test_a_node_cant_also_read_a_node(self):
        self.run_script(GTP_NODE="1", GTP_NODE_STATION="192.0.2.10")
        r = self.run_script(GTP_SDR_NODE="192.0.2.20")
        self.assertEqual(r.returncode, 1)
        self.assertIn("itself an SDR node", r.stderr)

    def test_undo_both_ways(self):
        self.run_script(GTP_NODE="1", GTP_NODE_STATION="192.0.2.10")
        r = self.run_script(GTP_NODE="0")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.root / "etc/chrony/sources.d/gps-time-node.sources").exists())
        self.assertFalse((self.root / "etc/default/gps-time-node").exists())
        self.run_script(GTP_SDR_NODE="192.0.2.20")
        r = self.run_script(GTP_SDR_NODE="none")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.units / "gps-time-readsb-node.service").exists())


if __name__ == "__main__":
    unittest.main()
