"""Opt-in ADS-B feeders and the location-sharing list (gps_time_pi/feeders.py, scripts/feeders.sh).

The module runs on temp folders with a fake systemctl; the installer runs under bash with stub
commands and every path under a temp root. Nothing is sent anywhere and nothing on the host changes.
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

from gps_time_pi import feeders as fd

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = ROOT / "system"
SCRIPT = ROOT / "scripts" / "feeders.sh"
FPR = "56B6684E138929F4E7CF014BC3B2A470AAD5A173"


class FakeSystemctl:
    def __init__(self, active=None):
        self.calls, self.active = [], active or {}

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        if argv[1] == "show":
            units = argv[5:]
            out = "\n\n".join(f"Id={u}\nLoadState=loaded\nActiveState={self.active.get(u, 'inactive')}" for u in units)
            return mock.Mock(returncode=0, stdout=out + "\n", stderr="")
        return mock.Mock(returncode=0, stdout="", stderr="")


class Tree(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.conf = self.tmp / "etc-feeders"
        self.flags = self.tmp / "flags"
        self.dropin = self.tmp / "piaware.conf"
        self.conf.mkdir()
        for name, host in (("adsbfi", "feed.adsb.fi"), ("airplaneslive", "feed.airplanes.live"), ("custom", "feed.example.org")):
            (self.conf / f"{name}.conf").write_text(f"FEED_HOST={host}\nFEED_PORT=30004\n")
        self.dropin.write_text("[Unit]\n")
        for name, value in (("CONF_DIR", self.conf), ("FLAG_DIR", self.flags), ("PIAWARE_DROPIN", self.dropin)):
            p = mock.patch.object(fd, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.sysd = FakeSystemctl()

    def rows(self, cfg=None):
        return {r["name"]: r for r in fd.status(cfg or {}, run=self.sysd)["feeders"]}


class TestStatus(Tree):
    def test_installed_in_catalog_order_with_plain_words(self):
        rows = self.rows()
        self.assertEqual(list(rows), ["adsbfi", "airplaneslive", "custom", "piaware"])
        self.assertTrue(all(not r["on"] for r in rows.values()))
        self.assertIn("never gets the station's position", rows["adsbfi"]["shares"])
        self.assertEqual(rows["custom"]["confirm"], "feed.example.org")
        self.assertEqual(rows["custom"]["target"], "feed.example.org:30004")
        self.assertIn("PiAware never reads gpsd", rows["piaware"]["shares"])
        self.assertEqual(rows["piaware"]["unit"], "piaware.service")
        self.assertEqual(rows["adsbfi"]["unit"], "gps-time-feed@adsbfi.service")

    def test_not_installed(self):
        shutil.rmtree(self.conf)
        self.dropin.unlink()
        st = fd.status({}, run=self.sysd)
        self.assertFalse(st["installed"])
        self.assertEqual(st["feeders"], [])


class TestApply(Tree):
    def test_turning_on_needs_the_typed_name(self):
        with self.assertRaisesRegex(fd.FeederError, 'type "adsb.fi"'):
            fd.apply({}, {"feeder": "adsbfi", "enabled": True, "confirm": "adsbfi"}, run=self.sysd)
        self.assertFalse((self.flags / "adsbfi.on").exists())
        self.assertEqual([c for c in self.sysd.calls if c[1] != "show"], [])
        res = fd.apply({}, {"feeder": "adsbfi", "enabled": True, "confirm": "adsb.fi"}, run=self.sysd)
        self.assertTrue(res["ok"])
        self.assertTrue((self.flags / "adsbfi.on").is_file())
        self.assertIn(["systemctl", "start", "gps-time-feed@adsbfi.service"], self.sysd.calls)

    def test_several_feeders_run_at_once(self):
        (self.conf / "custom2.conf").write_text("FEED_HOST=feed2.example.org\nFEED_PORT=30005\n")
        for name, word in (("adsbfi", "adsb.fi"), ("airplaneslive", "airplanes.live"), ("custom", "feed.example.org"),
                           ("custom2", "feed2.example.org")):
            self.assertTrue(fd.apply({}, {"feeder": name, "enabled": True, "confirm": word}, run=self.sysd)["ok"], name)
        rows = self.rows()
        self.assertEqual({n for n, r in rows.items() if r["on"]}, {"adsbfi", "airplaneslive", "custom", "custom2"})
        self.assertEqual(rows["custom2"]["service"], "the custom aggregator feed2.example.org")
        self.assertEqual(rows["custom2"]["confirm"], "feed2.example.org")
        # Turning one off leaves the others running.
        fd.apply({}, {"feeder": "airplaneslive", "enabled": False}, run=self.sysd)
        self.assertEqual({n for n, r in self.rows().items() if r["on"]}, {"adsbfi", "custom", "custom2"})
        self.assertNotIn(["systemctl", "stop", "gps-time-feed@adsbfi.service"], self.sysd.calls)
        self.assertIn("any number", fd.status({}, run=self.sysd)["note"].lower())

    def test_turning_off_needs_no_confirmation(self):
        fd.apply({}, {"feeder": "adsbfi", "enabled": True, "confirm": "adsb.fi"}, run=self.sysd)
        fd.apply({}, {"feeder": "adsbfi", "enabled": False}, run=self.sysd)
        self.assertFalse((self.flags / "adsbfi.on").exists())
        self.assertIn(["systemctl", "stop", "gps-time-feed@adsbfi.service"], self.sysd.calls)

    def test_unknown_or_path_like_feeders_are_refused(self):
        for name in ("nope", "../../etc/passwd", "piaware;rm", None, 3):
            with self.subTest(name=name):
                with self.assertRaises(fd.FeederError) as e:
                    fd.apply({}, {"feeder": name, "enabled": True, "confirm": "x"}, run=self.sysd)
                self.assertEqual(e.exception.code, 404)
        self.assertFalse(self.flags.exists() and list(self.flags.iterdir()))

    def test_mlat_is_its_own_opt_in_and_refused_in_hidden_mode(self):
        with self.assertRaisesRegex(fd.FeederError, "share my exact location"):
            fd.apply({}, {"feeder": "piaware", "mlat": True, "confirm": "FlightAware"}, run=self.sysd)
        with self.assertRaises(fd.FeederError) as e:
            fd.apply({"location_display": "hidden"},
                     {"feeder": "piaware", "mlat": True, "confirm": "share my exact location"}, run=self.sysd)
        self.assertEqual(e.exception.code, 403)
        self.assertFalse((self.flags / "piaware.mlat").exists())
        with self.assertRaisesRegex(fd.FeederError, "PiAware only"):
            fd.apply({}, {"feeder": "adsbfi", "mlat": True, "confirm": "share my exact location"}, run=self.sysd)
        res = fd.apply({}, {"feeder": "piaware", "mlat": True, "confirm": "share my exact location"}, run=self.sysd)
        self.assertTrue(res["ok"])
        self.assertIn("Shares your exact location with FlightAware", self.rows()["piaware"]["shares"])

    def test_hidden_mode_turns_mlat_off_and_restarts_piaware(self):
        fd.apply({}, {"feeder": "piaware", "enabled": True, "confirm": "FlightAware"}, run=self.sysd)
        fd.apply({}, {"feeder": "piaware", "mlat": True, "confirm": "share my exact location"}, run=self.sysd)
        self.assertTrue(fd.privacy_hidden(run=self.sysd))
        self.assertFalse((self.flags / "piaware.mlat").exists())
        self.assertIn(["systemctl", "try-restart", "piaware.service"], self.sysd.calls)
        self.assertFalse(fd.privacy_hidden(run=self.sysd))       # nothing left to turn off

    def test_the_hidden_row_says_mlat_is_refused(self):
        row = self.rows({"location_display": "hidden"})["piaware"]
        self.assertFalse(row["mlat"]["allowed"])
        self.assertIn("refused", row["mlat"]["refused"])


class TestSharing(Tree):
    def test_one_list_with_every_kind_of_sharing(self):
        fd.apply({}, {"feeder": "adsbfi", "enabled": True, "confirm": "adsb.fi"}, run=self.sysd)
        cfg = {"location_display": "rounded", "sky_quality_share": True}
        sh = fd.location_sharing(cfg, fd.status(cfg, run=self.sysd))
        what = {r["what"]: r for r in sh["rows"]}
        self.assertTrue(what["Feeder: adsb.fi"]["active"])
        self.assertEqual(what["Feeder: adsb.fi"]["location"], "rough (from the aircraft)")
        self.assertFalse(what["FlightAware MLAT (PiAware)"]["active"])
        self.assertEqual(what["Capability record"]["location"], "rounded to 0.1°")
        self.assertTrue(what["Sky-quality summary"]["active"])
        self.assertFalse(sh["exact_location_shared"])

    def test_exact_location_is_flagged_when_mlat_runs(self):
        fd.apply({}, {"feeder": "piaware", "enabled": True, "confirm": "FlightAware"}, run=self.sysd)
        fd.apply({}, {"feeder": "piaware", "mlat": True, "confirm": "share my exact location"}, run=self.sysd)
        sh = fd.location_sharing({}, fd.status({}, run=self.sysd))
        self.assertTrue(sh["exact_location_shared"])


class TestServer(unittest.TestCase):
    def test_demo_routes_have_the_station_shape(self):
        from gps_time_pi import demo
        st = demo.feeders_status({})
        self.assertEqual(set(st), {"installed", "feeders", "location_display", "note", "sharing"})
        self.assertEqual(demo.feeder_apply({}, {"feeder": "adsbfi", "enabled": True, "confirm": "nope"})["ok"], False)
        self.assertEqual(demo.feeder_apply({"location_display": "hidden"},
                                           {"feeder": "piaware", "mlat": True, "confirm": "share my exact location"})["ok"], False)

    def test_hidden_mode_handler_calls_privacy_hidden(self):
        text = (ROOT / "gps_time_pi" / "server.py").read_text(encoding="utf-8")
        self.assertIn('feeders.privacy_hidden() if mode == "hidden" and not DEMO_MODE', text)


class TestUnits(unittest.TestCase):
    def test_readsb_keeps_no_outside_network_and_no_position(self):
        drop = (SYSTEM / "gps-time-readsb-feed.conf").read_text(encoding="utf-8")
        base = (SYSTEM / "gps-time-readsb.service").read_text(encoding="utf-8")
        start = re.search(r"^ExecStart=(/usr/bin/readsb.*)$", drop, re.M).group(1)
        base_start = re.search(r"^ExecStart=(.*)$", base, re.M).group(1)
        self.assertTrue(start.startswith(base_start))                # the same decoder, one output added
        self.assertIn("--net-bind-address 127.0.0.1 --net-bo-port 30005", start)
        for port in ("ri", "ro", "sbs", "bi"):
            self.assertIn(f"--net-{port}-port 0", start)
        self.assertNotRegex(start, r"--(lat|lon)\b")
        self.assertIn("IPAddressAllow=localhost", drop)
        self.assertIn("\nIPAddressDeny=any\n", base)                  # still there: localhost only

    def test_feeder_units_never_get_a_position_and_wait_for_the_owner(self):
        u = (SYSTEM / "gps-time-feed@.service").read_text(encoding="utf-8")
        start = re.search(r"^ExecStart=(.*)$", u, re.M).group(1)
        self.assertNotRegex(start, r"--(lat|lon|mlat)\b")
        self.assertIn("ConditionPathExists=/opt/gps-time-pi/feeders/%i.on", u)
        self.assertIn("--net-connector 127.0.0.1,30005,beast_in", start)
        self.assertIn("beast_reduce_plus_out", start)
        self.assertIn("DynamicUser=yes", u)

    def test_piaware_never_reads_gpsd_and_mlat_is_opt_in(self):
        h = (SYSTEM / "piaware-settings").read_text(encoding="utf-8")
        self.assertIn("piaware-config use-gpsd no", h)
        self.assertIn("piaware-config allow-auto-updates no", h)
        self.assertIn("piaware-config allow-manual-updates no", h)
        self.assertIn('if [ -f "$FLAGS/piaware.mlat" ]', h)
        self.assertIn('"location_display"', h)                        # hidden mode wins over the flag
        d = (SYSTEM / "piaware-gps-time.conf").read_text(encoding="utf-8")
        self.assertIn("ConditionPathExists=/opt/gps-time-pi/feeders/piaware.on", d)

    def test_script_pins_flightawares_key_and_never_touches_timing(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(f'FA_KEY_FPR="{FPR}"', text)
        self.assertIn("systemctl mask piaware.service dump1090-fa.service", text)
        self.assertLess(text.index("systemctl mask piaware.service"), text.index("apt-get install -y --no-install-recommends piaware"))
        code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
        for word in ("chrony", "gpsd.service", "/etc/default/gpsd", "pps-gpio", "/boot/"):
            self.assertNotIn(word, code)


STUB = """#!/bin/bash
echo "$(basename "$0") $*" >> "$STUB_LOG"
case "$(basename "$0")" in
  dpkg) [ "$1" = --print-architecture ] && { echo arm64; exit 0; }; exit 1 ;;
  chown) exit 0 ;;
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
        for cmd in ("apt-get", "systemctl", "dpkg", "chown", "curl", "gpg", "dpkg-deb"):
            p = self.bin / cmd
            p.write_text(STUB)
            p.chmod(p.stat().st_mode | stat.S_IXUSR)
        self.root = self.tmp / "root"
        self.log = self.tmp / "calls.log"

    def run_script(self, readsb=True, **env):
        if readsb:
            (self.root / "etc/systemd/system").mkdir(parents=True, exist_ok=True)
            (self.root / "etc/systemd/system/gps-time-readsb.service").write_text("[Unit]\n")
        base = {k: v for k, v in os.environ.items() if not k.startswith("GTP_")}
        base.update(PATH=f"{self.bin}:{os.environ['PATH']}", GTP_FEEDERS_TEST_ROOT=str(self.root), STUB_LOG=str(self.log))
        base.update(env)
        return subprocess.run(["bash", str(SCRIPT)], env=base, capture_output=True, text=True, timeout=60)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_unset_changes_nothing(self):
        r = self.run_script(readsb=False)
        self.assertEqual(r.returncode, 0)
        self.assertIn("not installed", r.stdout)
        self.assertEqual(self.calls(), [])

    def test_install_sets_up_every_feeder_off(self):
        r = self.run_script(GTP_FEEDERS="1", GTP_FEEDERS_CUSTOM="feed.example.org:30004")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        conf = self.root / "etc/gps-time-feeders"
        self.assertEqual(sorted(p.stem for p in conf.glob("*.conf")), ["adsbexchange", "adsbfi", "airplaneslive", "custom"])
        self.assertIn("FEED_HOST=feed.example.org", (conf / "custom.conf").read_text())
        uuids = {p.read_text().strip() for p in conf.glob("*.uuid")}
        self.assertEqual(len(uuids), 4)                               # one random UUID each
        for u in uuids:
            self.assertRegex(u, r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
        self.assertTrue((self.root / "etc/systemd/system/gps-time-readsb.service.d/gps-time-feed.conf").is_file())
        self.assertFalse(list((self.root / "opt/gps-time-pi/feeders").glob("*.on")))   # all off
        calls = self.calls()
        self.assertIn("systemctl enable gps-time-feed@adsbfi.service", calls)
        self.assertFalse([c for c in calls if c.startswith("systemctl start")])
        self.assertFalse([c for c in calls if "piaware" in c])         # not asked for

    def test_several_custom_aggregators(self):
        r = self.run_script(GTP_FEEDERS="1", GTP_FEEDERS_CUSTOM="feed.example.org:30004,feed2.example.org:31004")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        conf = self.root / "etc/gps-time-feeders"
        self.assertIn("FEED_HOST=feed2.example.org", (conf / "custom2.conf").read_text())
        self.assertIn("FEED_PORT=31004", (conf / "custom2.conf").read_text())
        self.assertIn("systemctl enable gps-time-feed@custom2.service", self.calls())
        # A shorter list takes the extra one out again; its UUID stays.
        r = self.run_script(GTP_FEEDERS="1", GTP_FEEDERS_CUSTOM="feed.example.org:30004")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((conf / "custom2.conf").exists())
        self.assertTrue((conf / "custom2.uuid").exists())
        self.assertTrue((conf / "custom.conf").exists())
        for bad in ("a:1,b:2,c:3,d:4,e:5", "ok.example:30004,bad host:1", "x.example:0", "x.example:70000"):
            with self.subTest(bad=bad):
                r = self.run_script(GTP_FEEDERS="1", GTP_FEEDERS_CUSTOM=bad)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("nothing changed", r.stderr)

    def test_uuids_are_kept_between_runs(self):
        self.run_script(GTP_FEEDERS="1")
        first = (self.root / "etc/gps-time-feeders/adsbfi.uuid").read_text()
        self.run_script(GTP_FEEDERS="1")
        self.assertEqual((self.root / "etc/gps-time-feeders/adsbfi.uuid").read_text(), first)

    def test_refusals(self):
        r = self.run_script(readsb=False, GTP_FEEDERS="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("gps-time-readsb.service isn't installed", r.stderr)
        for env in ({"GTP_FEEDERS_CUSTOM": "bad host; rm"}, {"GTP_FEEDERS_PIAWARE": "yes please"}, {"GTP_FEEDERS": "2"}):
            with self.subTest(env=env):
                r = self.run_script(**{"GTP_FEEDERS": "1", **env})
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("nothing changed", r.stderr)

    def test_a_wrong_flightaware_key_skips_piaware(self):
        osr = self.tmp / "os-release"
        osr.write_text("VERSION_CODENAME=trixie\n")
        r = self.run_script(GTP_FEEDERS="1", GTP_FEEDERS_PIAWARE="1", GTP_FEEDERS_OS_RELEASE=str(osr))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PiAware skipped", r.stderr)
        self.assertFalse((self.root / "etc/apt/sources.list.d/gps-time-flightaware.list").exists())
        self.assertFalse([c for c in self.calls() if c.startswith("apt-get install")])

    def test_off_removes_units_and_switches(self):
        self.run_script(GTP_FEEDERS="1")
        flags = self.root / "opt/gps-time-pi/feeders"
        (flags / "adsbfi.on").write_text("")
        r = self.run_script(GTP_FEEDERS="0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((flags / "adsbfi.on").exists())
        self.assertFalse((self.root / "etc/systemd/system/gps-time-feed@.service").exists())
        self.assertFalse((self.root / "etc/systemd/system/gps-time-readsb.service.d/gps-time-feed.conf").exists())
        self.assertTrue((self.root / "etc/gps-time-feeders/adsbfi.uuid").exists())
        self.assertIn("systemctl disable --now gps-time-feed@adsbfi.service", self.calls())


if __name__ == "__main__":
    unittest.main()
