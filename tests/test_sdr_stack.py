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
READSB_COMMIT = "321931802d89f1695a38f6dfb0a64ba5c1211be4"
HELPER = ROOT / "scripts" / "sdr-decoders.sh"

# What readsb prints for "--device-type rtlsdr --gtp-check-only": Debian 13's package (no RTL-SDR),
# and a build with RTL-SDR support (the device type is accepted, the made-up option is not).
READSB_NO_RTLSDR = """#!/bin/sh
echo "ERROR: Unknown device type:rtlsdr" >&2
echo "Error parsing the given command line parameters, check readsb --usage and readsb --help for valid parameters." >&2
exit 1
"""
READSB_RTLSDR = """#!/bin/sh
echo "readsb: unrecognized option '--gtp-check-only'" >&2
echo "Try 'readsb --help' or 'readsb --usage' for more information." >&2
exit 1
"""


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

    def test_installer_checks_it_first_then_runs_it_without_failing_the_install(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        # Preflight: a bad or empty serial stops the install before anything changes.
        check = text.index("bash scripts/sdr-stack.sh check")
        self.assertLess(check, text.index('printf "Cannot install:'))
        self.assertLess(check, text.index("apt-get update"))
        # The install itself: a failure is a warning; a failed check after it (exit 3) is said again at the end.
        self.assertIn("bash scripts/sdr-stack.sh || SDR_RC=$?", text)
        self.assertIn("CHECK FAILED", text[text.rindex('if [ "$SDR_RC" = 3 ]'):])
        self.assertLess(text.index("gps-time-modules.service /etc/systemd/system/"), text.index("bash scripts/sdr-stack.sh ||"))

    def test_an_empty_serial_never_starts_a_decoder(self):
        # rc.7: readsb with an empty serial exited 1 and restarted for ever. ExecCondition skips the
        # start instead ($$ so that the shell, not systemd, reads the variable), and a start limit
        # ends any other loop.
        for name, var in (("gps-time-readsb.service", "GTP_SDR_1090_SERIAL"),
                          ("gps-time-dump978.service", "GTP_SDR_978_SERIAL"),
                          ("gps-time-rtl-tcp.service", "GTP_SDR_PPS_SERIAL")):
            text = unit(name)
            with self.subTest(name):
                cond = re.search(r"^ExecCondition=(.*)$", text, re.M).group(1)
                self.assertIn(f'"$${var}" in ""|none) ', cond)
                self.assertIn("exit 1", cond)
                self.assertLess(text.index("ExecCondition="), text.index("ExecStart="))
        for name in ("gps-time-readsb.service", "gps-time-dump978.service"):
            self.assertRegex(unit(name), r"\[Unit\][^\[]*\nStartLimitBurst=5\n")

    def test_the_condition_refuses_empty_and_none_and_passes_a_serial(self):
        if not shutil.which("sh") or os.name == "nt":
            self.skipTest("POSIX sh needed")
        cond = re.search(r"^ExecCondition=/bin/sh -c '(.*)'$", unit("gps-time-readsb.service"), re.M).group(1)
        cond = cond.replace("$$", "$")                     # what systemd hands the shell
        for value, rc in (("", 1), ("none", 1), ("00000001", 0), ("1090", 0)):
            with self.subTest(value):
                r = subprocess.run(["sh", "-c", cond], env={"GTP_SDR_1090_SERIAL": value, "PATH": os.environ["PATH"]},
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, rc, r.stderr)

    def test_readsb_is_built_from_a_pinned_tag_with_rtlsdr(self):
        # rc.8: Debian 13's readsb has no RTL-SDR support ("Unknown device type:rtlsdr").
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(f'READSB_COMMIT="{READSB_COMMIT}"', text)
        self.assertIn('READSB_TAG="v3.16.21"', text)
        self.assertIn('rev-parse HEAD)" = "$READSB_COMMIT"', text)
        self.assertIn("make -C \"$RB/readsb\" -j2 RTLSDR=yes readsb", text)
        self.assertNotRegex(text, r"apt-get install[^\n]* readsb")
        for name in ("gps-time-readsb.service", "gps-time-readsb-feed.conf", "gps-time-readsb-node.conf",
                     "gps-time-readsb-node.service", "gps-time-feed@.service"):
            with self.subTest(name):
                self.assertIn("ExecStart=/usr/local/bin/readsb ", unit(name))
                self.assertNotIn("/usr/bin/readsb", unit(name))

    def test_dump978_is_pinned_to_a_commit(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(f'DUMP978_COMMIT="{COMMIT}"', text)
        self.assertIn('rev-parse HEAD)" = "$DUMP978_COMMIT"', text)


STUB = """#!/bin/bash
echo "$(basename "$0") $*" >> "$STUB_LOG"
case "$(basename "$0")" in
  dpkg) exit "${STUB_DPKG_RC:-1}" ;;
  systemctl)
    [ "$1" = is-enabled ] && exit "${STUB_ENABLED_RC:-1}"
    if [ "$1" = is-active ]; then
      [ "$2" = --quiet ] && { [ "$3" = gps-time-websdr.service ] && exit "${STUB_WEBSDR_RC:-3}"; exit 0; }
      echo "${STUB_ACTIVE:-active}"; [ "${STUB_ACTIVE:-active}" = active ]; exit $?
    fi
    exit 0 ;;
  git)
    if [ "$1" = clone ]; then
      d="${@: -1}"; mkdir -p "$d/skyaware"; echo "<html>skyaware</html>" > "$d/skyaware/index.html"; exit 0
    fi
    if [ "$1" = init ]; then mkdir -p "${@: -1}"; exit 0; fi
    if [ "$3" = fetch ]; then
      d="$2"; mkdir -p "$d/html" "$d/db"
      printf '<html><script>let databaseFolder = "db2";</script><span id="webinterface_version"></span></html>\n' > "$d/html/index.html"
      echo "GPL" > "$d/LICENSE"; echo "{}" > "$d/db/aircraft.csv"; exit 0
    fi
    if [ "$3" = rev-parse ]; then
      case "$2" in
        */tar1090) echo "${STUB_TAR_COMMIT:-$STUB_COMMIT}" ;;
        */db) echo "${STUB_DB_COMMIT:-$STUB_COMMIT}" ;;
        */readsb) echo "${STUB_READSB_COMMIT}" ;;
        *) echo "${STUB_COMMIT}" ;;
      esac
      exit 0
    fi ;;
  make)
    d="$2"
    case "$d" in
      */readsb) cp "$STUB_READSB" "$d/readsb"; chmod +x "$d/readsb" ;;
      *) touch "$d/dump978-fa" "$d/skyaware978"; chmod +x "$d/dump978-fa" "$d/skyaware978" ;;
    esac
    exit 0 ;;
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
        for cmd in ("apt-get", "systemctl", "dpkg", "modprobe", "git", "make", "runuser", "journalctl",
                    "udevadm", "getent", "groupadd"):
            p = self.bin / cmd
            p.write_text(STUB)
            p.chmod(p.stat().st_mode | stat.S_IXUSR)
        self.root = self.tmp / "root"
        self.log = self.tmp / "calls.log"
        self.readsb_good = self.tmp / "readsb-rtlsdr"
        self.readsb_good.write_text(READSB_RTLSDR)
        self.readsb_debian = self.tmp / "readsb-debian"
        self.readsb_debian.write_text(READSB_NO_RTLSDR)
        self.soapy = self.root / "usr/lib/aarch64-linux-gnu/SoapySDR/modules0.8/librtlsdrSupport.so"
        self.soapy.parent.mkdir(parents=True)
        self.soapy.write_text("")

    def run_script(self, *args, decoders_write=True, **env):
        """decoders_write: the decoders' aircraft.json files are there, as after a good start."""
        if decoders_write:
            for d in ("run/readsb", "run/skyaware978"):
                (self.root / d).mkdir(parents=True, exist_ok=True)
                (self.root / d / "aircraft.json").write_text('{"now": 1, "aircraft": []}')
        base = {k: v for k, v in os.environ.items() if not k.startswith("GTP_SDR")}
        base.update(PATH=f"{self.bin}:{os.environ['PATH']}", GTP_SDR_TEST_ROOT=str(self.root),
                    STUB_LOG=str(self.log), STUB_COMMIT=COMMIT, GTP_SDR_WAIT_S="0",
                    STUB_READSB=str(self.readsb_good), STUB_READSB_COMMIT=READSB_COMMIT)
        base.update(env)
        return subprocess.run(["bash", str(SCRIPT), *args], env=base, capture_output=True, text=True, timeout=60)

    def fake_dongle(self, name, serial):
        d = self.root / "sys/bus/usb/devices" / name
        d.mkdir(parents=True)
        for k, v in {"idVendor": "0bda", "idProduct": "2838", "serial": serial}.items():
            (d / k).write_text(v + "\n")

    def saved(self, text):
        p = self.root / "etc/default/gps-time-sdr"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_unset_changes_nothing(self):
        r = self.run_script(decoders_write=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("not installed", r.stdout)
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.root / "etc").exists())

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
        self.run_script(GTP_SDR="1", GTP_SDR_PPS_SERIAL="00000pps", GTP_SDR_978_SERIAL="00000978",
                        GTP_SDR_1090_SERIAL="none")
        r = self.run_script(GTP_SDR="1", GTP_SDR_978_SERIAL="none")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        env = (self.root / "etc/default/gps-time-sdr").read_text()
        self.assertIn("GTP_SDR_PPS_SERIAL=00000pps\n", env)
        self.assertIn("GTP_SDR_978_SERIAL=\n", env)
        self.assertIn("GTP_SDR_1090_SERIAL=none\n", env)               # kept as "none", not empty
        self.assertIn("dump978 v11.1 already built", r.stdout)

    def test_bad_or_shared_serials_change_nothing(self):
        for env in ({"GTP_SDR_1090_SERIAL": "a b; rm -rf /"}, {"GTP_SDR_1090_SERIAL": "x1", "GTP_SDR_978_SERIAL": "x1"}):
            with self.subTest(env):
                r = self.run_script(GTP_SDR="1", **env)
                self.assertEqual(r.returncode, 1)
                self.assertFalse((self.root / "etc").exists())
                self.assertFalse([c for c in self.calls() if c.startswith("apt-get")])

    def test_a_commit_mismatch_keeps_978_off(self):
        r = self.run_script(GTP_SDR="1", GTP_SDR_978_SERIAL="00000978", GTP_SDR_1090_SERIAL="none", STUB_COMMIT="0" * 40)
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

    def tar_env(self):
        text = SCRIPT.read_text(encoding="utf-8")
        t = re.search(r'^TAR1090_COMMIT="([0-9a-f]{40})"', text, re.M).group(1)
        d = re.search(r'^TAR1090_DB_COMMIT="([0-9a-f]{40})"', text, re.M).group(1)
        return {"STUB_TAR_COMMIT": t, "STUB_DB_COMMIT": d}, t, d

    def test_the_aircraft_map_comes_with_the_1090_role_by_default(self):
        env, t, d = self.tar_env()
        html = self.root / "usr/local/share/gps-time-tar1090/html"
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00001090", **env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("aircraft map: tar1090", r.stdout)
        index = (html / "index.html").read_text()
        self.assertIn(f'let databaseFolder = "db-{d[:7]}";', index)
        self.assertIn(f'id="webinterface_version">({t[:7]})', index)
        self.assertTrue((html / f"db-{d[:7]}").is_dir())
        self.assertIn(t[:7], (html / "version.json").read_text())
        self.assertIn("GTP_TAR1090=1\n", (self.root / "etc/default/gps-time-sdr").read_text())
        calls = self.calls()
        self.assertTrue([c for c in calls if c.startswith("git -C") and f"fetch --quiet --depth 1 https://github.com/wiedehopf/tar1090.git {t}" in c])
        self.assertFalse([c for c in calls if "tar1090" in c and ("systemctl" in c or "lighttpd" in c or "nginx" in c)])
        r = self.run_script(GTP_SDR="1", **env)
        self.assertIn("already installed", r.stdout)
        r = self.run_script(GTP_SDR="1", GTP_TAR1090="0", **env)
        self.assertIn("aircraft map off", r.stdout)
        self.assertFalse(html.exists())
        self.assertIn("GTP_TAR1090=0\n", (self.root / "etc/default/gps-time-sdr").read_text())
        r = self.run_script(GTP_SDR="1", **env)            # kept off between runs
        self.assertFalse(html.exists())

    def test_the_aircraft_map_needs_1090_and_a_verified_commit(self):
        env, t, d = self.tar_env()
        html = self.root / "usr/local/share/gps-time-tar1090/html"
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="none", **env)
        self.assertIn("needs the 1090 MHz role", r.stdout)
        self.assertFalse(html.exists())
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00001090", STUB_TAR_COMMIT="0" * 40, STUB_DB_COMMIT=d)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)        # the rest of the stack installs
        self.assertIn("could not be fetched or verified", r.stderr)
        self.assertFalse(html.exists())
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00001090", GTP_TAR1090="maybe")
        self.assertEqual(r.returncode, 1)

    def test_off_removes_the_aircraft_map_too(self):
        env, _t, _d = self.tar_env()
        self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00001090", **env)
        self.assertTrue((self.root / "usr/local/share/gps-time-tar1090/html/index.html").is_file())
        self.run_script(GTP_SDR="0")
        self.assertFalse((self.root / "usr/local/share/gps-time-tar1090").exists())

    def test_off_removes_our_units_only(self):
        self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="none")
        r = self.run_script(GTP_SDR="0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        units = self.root / "etc/systemd/system"
        for u in UNITS:
            self.assertFalse((units / u).exists(), u)
        self.assertFalse((units / "gps-time-modules.service.d").exists())
        self.assertTrue((self.root / "etc/default/gps-time-sdr").exists())

    # ── rc.8: the 1090 MHz serial, the check after the install, two dongles ──

    def test_an_empty_1090_serial_stops_before_anything_changes(self):
        # The owner's Pi on rc.7: the env file had an empty 1090 MHz serial.
        self.saved("GTP_SDR_PPS_SERIAL=\nGTP_SDR_1090_SERIAL=\nGTP_SDR_978_SERIAL=\nGTP_TAR1090=1\n")
        self.fake_dongle("1-1.2", "00000001")
        self.fake_dongle("1-1.3", "00000978")
        for args in ((), ("check",)):
            with self.subTest(args):
                self.log.unlink(missing_ok=True)
                r = self.run_script(*args, GTP_SDR="1", decoders_write=False)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("GTP_SDR_1090_SERIAL is empty", r.stderr)
                self.assertIn("RTL-SDRs on USB now: 00000001 00000978", r.stderr)
                self.assertIn("GTP_SDR_1090_SERIAL=none", r.stderr)
                self.assertEqual(self.calls(), [])
                self.assertFalse((self.root / "etc/systemd").exists())

    def test_check_mode_changes_nothing(self):
        self.fake_dongle("1-1.2", "1090")
        r = self.run_script("check", GTP_SDR="1", GTP_SDR_1090_SERIAL="1090", decoders_write=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("settings checked: 1090 MHz 1090, 978 MHz none", r.stdout)
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.root / "etc").exists())
        r = self.run_script("check", GTP_SDR="1", GTP_SDR_1090_SERIAL="a;b", decoders_write=False)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.run_script("check", decoders_write=False).returncode, 0)   # GTP_SDR unset

    def test_the_check_after_the_install_finds_a_running_readsb(self):
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00000001")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("check: gps-time-readsb.service is active (dongle 00000001).", r.stdout)
        self.assertIn("check: /run/readsb/aircraft.json exists.", r.stdout)
        self.assertIn("systemctl reset-failed gps-time-readsb.service", self.calls())

    def test_the_check_after_the_install_catches_a_crash_loop(self):
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00000001", STUB_ACTIVE="activating",
                            decoders_write=False)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)          # install.sh: installed, check failed
        self.assertIn("CHECK FAILED: gps-time-readsb.service is activating", r.stderr)
        self.assertIn("CHECK FAILED: /run/readsb/aircraft.json does not exist", r.stderr)
        self.assertIn("journalctl -u gps-time-readsb.service -n 12 --no-pager", self.calls())

    def test_the_check_says_paused_when_the_web_sdr_has_the_dongle(self):
        (self.root / "etc/systemd/system").mkdir(parents=True)
        (self.root / "etc/systemd/system/gps-time-websdr.service").write_text("[Unit]\n")
        (self.root / "etc/default").mkdir(parents=True)
        (self.root / "etc/default/gps-time-websdr").write_text("GTP_WEBSDR_SERIAL=00000001\n")
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00000001", STUB_WEBSDR_RC="0",
                            STUB_ACTIVE="inactive", decoders_write=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("paused: the web SDR has dongle 00000001", r.stdout)

    def test_two_dongles_by_serial_and_the_978_map(self):
        self.fake_dongle("1-1.2", "1090")
        self.fake_dongle("1-1.3", "978")
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="1090", GTP_SDR_978_SERIAL="978")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        env = (self.root / "etc/default/gps-time-sdr").read_text()
        self.assertIn("GTP_SDR_1090_SERIAL=1090\n", env)
        self.assertIn("GTP_SDR_978_SERIAL=978\n", env)
        calls = self.calls()
        self.assertIn("systemctl enable gps-time-readsb.service", calls)
        self.assertIn("systemctl enable gps-time-dump978.service gps-time-skyaware978.service", calls)
        self.assertIn("check: gps-time-dump978.service is active (dongle 978).", r.stdout)
        self.assertIn("check: gps-time-skyaware978.service is active (dongle 978).", r.stdout)
        self.assertEqual((self.root / "usr/local/share/gps-time-skyaware978/html/index.html").read_text(),
                         "<html>skyaware</html>\n")
        self.assertNotIn("warning", r.stdout)
        # The dongles go to plugdev here too, not only with the web SDR.
        self.assertTrue((self.root / "etc/udev/rules.d/61-gps-time-rtl-sdr.rules").is_file())
        self.assertIn("udevadm trigger --subsystem-match=usb --attr-match=idVendor=0bda", calls)
        # Off removes the 978 map with the rest.
        self.run_script(GTP_SDR="0")
        self.assertFalse((self.root / "usr/local/share/gps-time-skyaware978").exists())

    def test_an_upgrade_from_rc7_fetches_the_978_page_once(self):
        self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="1090", GTP_SDR_978_SERIAL="978")
        page = self.root / "usr/local/share/gps-time-skyaware978/html"
        shutil.rmtree(page)                                             # as built by rc.7: binaries only
        r = self.run_script(GTP_SDR="1")
        self.assertNotIn("dump978 v11.1 already built", r.stdout)
        self.assertTrue((page / "index.html").is_file())
        r = self.run_script(GTP_SDR="1")
        self.assertIn("dump978 v11.1 already built", r.stdout)

    def test_serial_warnings(self):
        self.fake_dongle("1-1.2", "00000001")
        self.fake_dongle("1-1.3", "00000978")
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00000001", GTP_SDR_978_SERIAL="00005555")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("serial 00000001 (1090 MHz) could be read as device index 1 with 2 RTL-SDRs", r.stdout)
        self.assertIn("no RTL-SDR on USB has serial 00005555 (978 MHz)", r.stdout)
        self.assertNotIn("00000978 (", r.stdout)

    # ── rc.9: readsb with RTL-SDR support, SoapySDR's driver for dump978-fa ──

    def test_readsb_is_built_with_rtlsdr_and_installed_in_usr_local(self):
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00001090")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rb = self.root / "usr/local/bin/readsb"
        self.assertEqual(rb.read_text(), READSB_RTLSDR)
        self.assertEqual((self.root / "usr/local/lib/gps-time-sdr/readsb.commit").read_text().strip(), READSB_COMMIT)
        calls = self.calls()
        self.assertTrue([c for c in calls if c.startswith("git clone") and "--branch v3.16.21 https://github.com/wiedehopf/readsb.git" in c])
        self.assertTrue([c for c in calls if c.startswith("make -C") and c.endswith("RTLSDR=yes readsb")])
        self.assertFalse([c for c in calls if c.startswith("apt-get install") and " readsb " in c + " "])
        self.assertIn("systemctl enable gps-time-readsb.service", calls)
        self.assertIn("built with RTL-SDR support", r.stdout)
        r = self.run_script(GTP_SDR="1")
        self.assertIn("readsb v3.16.21 already built", r.stdout)

    def test_a_readsb_without_rtlsdr_is_never_installed_or_enabled(self):
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00001090", STUB_READSB=str(self.readsb_debian))
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)          # install.sh reports it at the end
        self.assertIn("refuses --device-type rtlsdr", r.stderr)
        self.assertIn("CHECK FAILED: no readsb with RTL-SDR support, so 1090 MHz stays off", r.stderr)
        self.assertFalse((self.root / "usr/local/bin/readsb").exists())
        self.assertNotIn("systemctl enable gps-time-readsb.service", self.calls())
        self.assertIn("systemctl disable --now gps-time-readsb.service", self.calls())

    def test_an_rc8_readsb_is_rebuilt(self):
        # An install with a readsb in /usr/local/bin that lacks RTL-SDR support, or no commit file.
        rb = self.root / "usr/local/bin/readsb"
        rb.parent.mkdir(parents=True)
        rb.write_text(READSB_NO_RTLSDR)
        rb.chmod(0o755)
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00001090")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("readsb v3.16.21 already built", r.stdout)
        self.assertEqual(rb.read_text(), READSB_RTLSDR)

    def test_a_readsb_commit_mismatch_keeps_1090_off(self):
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00001090", STUB_READSB_COMMIT="0" * 40)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("could not be fetched, verified", r.stderr)
        self.assertFalse((self.root / "usr/local/bin/readsb").exists())

    def test_978_needs_soapysdrs_rtlsdr_driver(self):
        self.soapy.unlink()
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00001090", GTP_SDR_978_SERIAL="00000978")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("CHECK FAILED: SoapySDR's RTL-SDR driver (librtlsdrSupport.so", r.stderr)
        calls = self.calls()
        self.assertNotIn("systemctl enable gps-time-dump978.service gps-time-skyaware978.service", calls)
        self.assertIn("systemctl enable gps-time-readsb.service", calls)     # 1090 MHz is unaffected
        # Without a 978 MHz role the driver isn't needed.
        r = self.run_script(GTP_SDR="1", GTP_SDR_978_SERIAL="none")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("needed only for 978 MHz", r.stdout)

    def test_check_mode_reports_the_decoders_and_changes_nothing(self):
        self.soapy.unlink()
        r = self.run_script("check", GTP_SDR="1", GTP_SDR_1090_SERIAL="00001090", GTP_SDR_978_SERIAL="00000978",
                            decoders_write=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("the install builds readsb v3.16.21 (make RTLSDR=yes)", r.stdout)
        self.assertIn("the install adds soapysdr-module-rtlsdr", r.stdout)
        self.assertEqual(self.calls(), [])

    def test_the_owners_new_serials_give_no_index_warning(self):
        self.fake_dongle("1-1.2", "00001090")
        self.fake_dongle("1-1.3", "00000978")
        r = self.run_script(GTP_SDR="1", GTP_SDR_1090_SERIAL="00001090", GTP_SDR_978_SERIAL="00000978")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("warning", r.stdout)
        self.assertIn("check: gps-time-readsb.service is active (dongle 00001090).", r.stdout)
        self.assertIn("check: gps-time-dump978.service is active (dongle 00000978).", r.stdout)


@unittest.skipIf(os.name == "nt" or not shutil.which("bash") or not shutil.which("timeout"), "POSIX bash needed")
class TestDecoderChecks(unittest.TestCase):
    """scripts/sdr-decoders.sh on its own: the check never runs the decoder."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def check(self, func, arg):
        r = subprocess.run(["bash", "-c", f'. "$1"; {func} "$2"', "x", str(HELPER), str(arg)],
                           capture_output=True, text=True, timeout=30)
        return r.returncode

    def fake_readsb(self, text):
        p = self.tmp / "readsb"
        p.write_text(text)
        p.chmod(0o755)
        return p

    def test_debians_readsb_fails_and_a_rtlsdr_build_passes(self):
        self.assertEqual(self.check("decoder_readsb_rtlsdr", self.fake_readsb(READSB_NO_RTLSDR)), 1)
        self.assertEqual(self.check("decoder_readsb_rtlsdr", self.fake_readsb(READSB_RTLSDR)), 0)

    def test_a_missing_or_silent_readsb_fails(self):
        self.assertEqual(self.check("decoder_readsb_rtlsdr", self.tmp / "nothing"), 1)
        self.assertEqual(self.check("decoder_readsb_rtlsdr", self.fake_readsb("#!/bin/sh\nexit 0\n")), 1)

    def test_the_check_asks_with_an_option_that_stops_readsb(self):
        # readsb --help runs readsb unless --help is the first argument, so the check passes a
        # made-up option after --device-type instead; the argument list is checked here.
        args = self.tmp / "readsb.args"
        self.fake_readsb('#!/bin/sh\necho "$*" > "$0.args"\necho "unrecognized option" >&2\nexit 1\n')
        self.check("decoder_readsb_rtlsdr", self.tmp / "readsb")
        self.assertEqual(args.read_text().strip(), "--device-type rtlsdr --gtp-check-only")

    def test_soapysdr_driver_is_found_by_file(self):
        self.assertEqual(self.check("decoder_soapy_rtlsdr", self.tmp), 1)
        mod = self.tmp / "usr/lib/aarch64-linux-gnu/SoapySDR/modules0.8/librtlsdrSupport.so"
        mod.parent.mkdir(parents=True)
        mod.write_text("")
        self.assertEqual(self.check("decoder_soapy_rtlsdr", self.tmp), 0)


if __name__ == "__main__":
    unittest.main()
