"""The optional SDR stack (scripts/sdr-stack.sh, GTP_SDR=1): loopback only, no position, opt-in.

Static checks of the units run everywhere. The script itself runs under POSIX bash with stub
commands (apt-get, systemctl, git, make, ...) on PATH and every path under a temp root, so no
package is installed and nothing on the host changes.
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
SCRIPT = ROOT / "scripts" / "sdr-stack.sh"
SYSTEM = ROOT / "system"
UNITS = ["gps-time-rtl-tcp.service", "gps-time-readsb.service", "gps-time-dump978.service",
         "gps-time-skyaware978.service"]
COMMIT = "f40aa9a0d2d0a0067c0c628b44ba316f7049b8ce"


def unit(name):
    return (SYSTEM / name).read_text(encoding="utf-8")


def exec_line(text):
    m = re.search(r"^ExecStart=(.*(?:\\\n.*)*)", text, re.M)
    return m.group(1).replace("\\\n", " ")


class TestUnits(unittest.TestCase):
    def test_every_unit_is_fenced_to_the_loopback_or_no_network(self):
        for name in UNITS:
            text = unit(name)
            with self.subTest(name):
                self.assertIn("\nIPAddressDeny=any\n", text)
                allow = re.findall(r"^IPAddressAllow=(.*)$", text, re.M)
                self.assertTrue(all(a == "localhost" for a in allow), allow)
                self.assertIn("NoNewPrivileges=yes", text)
                self.assertIn("DynamicUser=yes", text)
                self.assertRegex(text, r"\nCPUQuota=\d+%\n")
                self.assertRegex(text, r"\nMemoryMax=\d+M\n")

    def test_listeners_bind_127_0_0_1_only(self):
        self.assertIn("-a 127.0.0.1 ", exec_line(unit("gps-time-rtl-tcp.service")))
        d = exec_line(unit("gps-time-dump978.service"))
        ports = re.findall(r"--(?:raw|json|raw-legacy)-port (\S+)", d)
        self.assertEqual(ports, ["127.0.0.1:30978", "127.0.0.1:30979"])
        self.assertIn("--connect 127.0.0.1:30978", exec_line(unit("gps-time-skyaware978.service")))

    def test_readsb_opens_no_listener(self):
        line = exec_line(unit("gps-time-readsb.service"))
        self.assertNotIn("--net", line)
        self.assertIn("--write-json /run/readsb", line)
        self.assertNotIn("AF_INET", unit("gps-time-readsb.service"))

    def test_no_decoder_is_given_a_position(self):
        for name in UNITS:
            line = exec_line(unit(name))
            with self.subTest(name):
                self.assertNotRegex(line, r"--(lat|lon|alt)\b")
        self.assertIn("--json-location-accuracy 0", exec_line(unit("gps-time-readsb.service")))

    def test_each_dongle_is_picked_by_serial(self):
        self.assertIn("-d ${GTP_SDR_PPS_SERIAL}", exec_line(unit("gps-time-rtl-tcp.service")))
        self.assertIn("--device ${GTP_SDR_1090_SERIAL}", exec_line(unit("gps-time-readsb.service")))
        self.assertIn("serial=${GTP_SDR_978_SERIAL}", exec_line(unit("gps-time-dump978.service")))

    def test_json_goes_to_ram_where_reference_adsb_looks(self):
        manifest = (ROOT / "modules" / "reference-adsb" / "module.toml").read_text(encoding="utf-8")
        self.assertIn('default = "/run/readsb/aircraft.json"', manifest)
        self.assertIn('default = "/run/skyaware978/aircraft.json"', manifest)
        self.assertIn("RuntimeDirectory=readsb\n", unit("gps-time-readsb.service"))
        self.assertIn("RuntimeDirectory=skyaware978\n", unit("gps-time-skyaware978.service"))

    def test_modules_drop_in_allows_localhost_only(self):
        text = (SYSTEM / "gps-time-modules-sdr.conf").read_text(encoding="utf-8")
        settings = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
        self.assertEqual(settings, ["[Service]", "IPAddressAllow=localhost"])

    def test_script_never_touches_the_timing_core(self):
        code = "\n".join(ln for ln in SCRIPT.read_text(encoding="utf-8").splitlines()
                         if not ln.lstrip().startswith("#"))
        for word in ("chrony", "gpsd", "pps-gpio", "/boot/", "config.txt"):
            self.assertNotIn(word, code)

    def test_installer_runs_it_without_failing_the_install(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn('bash scripts/sdr-stack.sh \\\n  || echo "Warning:', text)
        self.assertLess(text.index("gps-time-modules.service /etc/systemd/system/"), text.index("bash scripts/sdr-stack.sh"))

    def test_dump978_is_pinned_to_a_commit(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(f'DUMP978_COMMIT="{COMMIT}"', text)
        self.assertIn('rev-parse HEAD)" = "$DUMP978_COMMIT"', text)


STUB = """#!/bin/bash
echo "$(basename "$0") $*" >> "$STUB_LOG"
case "$(basename "$0")" in
  dpkg) exit "${STUB_DPKG_RC:-1}" ;;
  systemctl) [ "$1" = is-enabled ] && exit "${STUB_ENABLED_RC:-1}"; exit 0 ;;
  git)
    if [ "$1" = clone ]; then mkdir -p "${@: -1}"; exit 0; fi
    if [ "$3" = rev-parse ]; then echo "${STUB_COMMIT}"; exit 0; fi ;;
  make) d="$2"; touch "$d/dump978-fa" "$d/skyaware978"; chmod +x "$d/dump978-fa" "$d/skyaware978"; exit 0 ;;
esac
exit 0
"""


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "POSIX bash needed")
class TestScript(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        for cmd in ("apt-get", "systemctl", "dpkg", "modprobe", "git", "make", "runuser"):
            p = self.bin / cmd
            p.write_text(STUB)
            p.chmod(p.stat().st_mode | stat.S_IXUSR)
        self.root = self.tmp / "root"
        self.log = self.tmp / "calls.log"

    def run_script(self, **env):
        base = {k: v for k, v in os.environ.items() if not k.startswith("GTP_SDR")}
        base.update(PATH=f"{self.bin}:{os.environ['PATH']}", GTP_SDR_TEST_ROOT=str(self.root),
                    STUB_LOG=str(self.log), STUB_COMMIT=COMMIT)
        base.update(env)
        return subprocess.run(["bash", str(SCRIPT)], env=base, capture_output=True, text=True, timeout=60)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_unset_changes_nothing(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("not installed", r.stdout)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.root.exists())

    def test_install_enables_only_roles_with_a_serial(self):
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00001090")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        units = self.root / "etc/systemd/system"
        for u in UNITS:
            self.assertTrue((units / u).is_file(), u)
        self.assertTrue((units / "gps-time-modules.service.d/gps-time-sdr.conf").is_file())
        env = (self.root / "etc/default/gps-time-sdr").read_text()
        self.assertIn("GTP_SDR_1090_SERIAL=00001090\n", env)
        self.assertIn("GTP_SDR_PPS_SERIAL=\n", env)
        calls = self.calls()
        self.assertIn("systemctl mask readsb.service", calls)
        self.assertIn("systemctl enable gps-time-readsb.service", calls)
        self.assertIn("systemctl enable gps-time-modules.service", calls)   # runs nothing until the switch
        self.assertIn("systemctl disable --now gps-time-rtl-tcp.service", calls)
        self.assertIn("systemctl disable --now gps-time-dump978.service gps-time-skyaware978.service", calls)
        self.assertTrue((self.root / "usr/local/lib/gps-time-sdr/dump978-fa").is_file())
        self.assertFalse([c for c in calls if "chrony" in c or "gpsd" in c])
        self.assertIn("blacklist dvb_usb_rtl28xxu", (self.root / "etc/modprobe.d/gps-time-rtl-sdr.conf").read_text())

    def test_serials_are_kept_between_runs_and_none_clears_one(self):
        self.run_script(GTP_SDR="1", GTP_SDR_PPS_SERIAL="00000pps", GTP_SDR_978_SERIAL="00000978")
        r = self.run_script(GTP_SDR="1", GTP_SDR_978_SERIAL="none")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        env = (self.root / "etc/default/gps-time-sdr").read_text()
        self.assertIn("GTP_SDR_PPS_SERIAL=00000pps\n", env)
        self.assertIn("GTP_SDR_978_SERIAL=\n", env)
        self.assertIn("dump978 v11.1 already built", r.stdout)

    def test_bad_or_shared_serials_change_nothing(self):
        for env in ({"GTP_SDR_1090_SERIAL": "a b; rm -rf /"}, {"GTP_SDR_1090_SERIAL": "x1", "GTP_SDR_978_SERIAL": "x1"}):
            with self.subTest(env):
                r = self.run_script(GTP_SDR="1", **env)
                self.assertEqual(r.returncode, 1)
                self.assertFalse((self.root / "etc").exists())
                self.assertFalse([c for c in self.calls() if c.startswith("apt-get")])

    def test_a_commit_mismatch_keeps_978_off(self):
        r = self.run_script(GTP_SDR="1", GTP_SDR_978_SERIAL="00000978", STUB_COMMIT="0" * 40)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("978 MHz stays off", r.stderr)
        self.assertFalse((self.root / "usr/local/lib/gps-time-sdr/dump978-fa").exists())
        self.assertNotIn("systemctl enable gps-time-dump978.service gps-time-skyaware978.service", self.calls())

    def test_an_owners_own_readsb_is_left_alone(self):
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00001090", STUB_DPKG_RC="0", STUB_ENABLED_RC="0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = self.calls()
        self.assertNotIn("systemctl mask readsb.service", calls)
        self.assertNotIn("systemctl enable gps-time-readsb.service", calls)
        self.assertIn("left as it is", r.stdout)

    def test_off_removes_our_units_only(self):
        self.run_script(GTP_SDR="1")
        r = self.run_script(GTP_SDR="0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        units = self.root / "etc/systemd/system"
        for u in UNITS:
            self.assertFalse((units / u).exists(), u)
        self.assertFalse((units / "gps-time-modules.service.d").exists())
        self.assertTrue((self.root / "etc/default/gps-time-sdr").exists())


if __name__ == "__main__":
    unittest.main()
