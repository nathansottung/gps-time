"""/api/sdr (gps_time_pi/sdr.py): the SDR stack read from a temp sysfs/cgroup tree and a fake
systemctl. Read only, UNKNOWN when unreadable, no position from the feeds. No root, no SDR."""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import sdr

SHOW = """Id=gps-time-readsb.service
LoadState=loaded
ActiveState=active
SubState=running
UnitFileState=enabled
NRestarts=2
ActiveEnterTimestampMonotonic=1000000000
ControlGroup=/system.slice/gps-time-readsb.service

Id=gps-time-rtl-tcp.service
LoadState=loaded
ActiveState=inactive
SubState=dead
UnitFileState=disabled
NRestarts=0
ActiveEnterTimestampMonotonic=0
ControlGroup=

Id=gps-time-dump978.service
LoadState=not-found
ActiveState=inactive
SubState=dead
UnitFileState=
NRestarts=0
ActiveEnterTimestampMonotonic=0
ControlGroup=
"""


def fake_run(stdout=SHOW, rc=0, raises=None):
    def run(cmd, **kw):
        if raises:
            raise raises
        assert cmd[:2] == ["systemctl", "show"], cmd
        return subprocess.CompletedProcess(cmd, rc, stdout, "")
    return run


class Tree(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cg = self.tmp / "cgroup"
        cg = self.cg / "system.slice" / "gps-time-readsb.service"
        cg.mkdir(parents=True)
        (cg / "cpu.stat").write_text("usage_usec 30000000\nuser_usec 25000000\n")
        (cg / "memory.current").write_text(str(20 * 1048576))
        self.usb = self.tmp / "usb"
        self.links = True
        self.dev("1-1.2", "0bda", "2838", "00001090", driver=None)
        self.dev("1-1.3", "0bda", "2838", "00000978", driver="dvb_usb_rtl28xxu")
        self.dev("1-1.4", "046d", "c52b", "keyboard", driver="usbhid")
        try:
            (self.usb / "1-1.2:1.0").mkdir()      # an interface entry is never a device row
        except OSError:
            pass                                  # Windows: no ':' in names
        self.env = self.tmp / "gps-time-sdr"
        self.env.write_text("GTP_SDR_PPS_SERIAL=\nGTP_SDR_1090_SERIAL=00001090\nGTP_SDR_978_SERIAL=00000978\n")
        self.feed1090 = self.tmp / "readsb" / "aircraft.json"
        self.feed978 = self.tmp / "skyaware978" / "aircraft.json"
        self.feed1090.parent.mkdir()
        self.feed1090.write_text(json.dumps({"now": 1, "aircraft": [
            {"hex": "a1", "lat": 38.9217, "lon": -77.0669}, {"hex": "a2"}]}))
        self.web_env = self.tmp / "gps-time-websdr"
        self.model = self.tmp / "model"
        self.model.write_bytes(b"Raspberry Pi 4 Model B Rev 1.5\x00")
        for name, value in (("CGROUP", self.cg), ("USB", self.usb), ("ENVFILE", self.env),
                            ("WEB_ENVFILE", self.web_env), ("MODEL", self.model),
                            ("FEEDS", {"1090": self.feed1090, "978": self.feed978})):
            p = mock.patch.object(sdr, name, value)
            p.start()
            self.addCleanup(p.stop)

    def dev(self, port, vid, pid, serial, driver):
        d = self.usb / port
        d.mkdir(parents=True)
        (d / "idVendor").write_text(vid + "\n")
        (d / "idProduct").write_text(pid + "\n")
        (d / "serial").write_text(serial + "\n")
        (d / "product").write_text("RTL2838UHIDIR\n")
        (d / "speed").write_text("480\n")
        if driver:
            target = self.tmp / "drivers" / driver
            target.mkdir(parents=True, exist_ok=True)
            try:
                (d / f"{port}:1.0").mkdir()
                os.symlink(target, d / f"{port}:1.0" / "driver")
            except OSError:
                self.links = False            # Windows without symlink rights


class TestUnits(Tree):
    def test_installed_units_with_cpu_from_the_cgroup(self):
        rows = sdr.units(fake_run(), monotonic_us=1000000000 + 120e6)
        self.assertEqual([r["unit"] for r in rows], ["gps-time-rtl-tcp.service", "gps-time-readsb.service"])
        readsb = rows[1]
        self.assertEqual(readsb["active"]["value"], "active")
        self.assertEqual(readsb["restarts"]["value"], 2)
        self.assertEqual(readsb["cpu_s"], {"value": 30.0, "unit": "s", "provenance": "observed",
                                           "note": "CPU time since the unit started (cgroup cpu.stat)"})
        self.assertEqual(readsb["cpu_avg_pct"]["value"], 25.0)       # 30 s of CPU over 120 s
        self.assertEqual(readsb["cpu_avg_pct"]["provenance"], "calculated")
        self.assertEqual(readsb["memory_mib"]["value"], 20.0)
        rtl = rows[0]
        self.assertIsNone(rtl["cpu_s"]["value"])                     # not running: not read
        self.assertIsNone(rtl["cpu_avg_pct"]["value"])

    def test_unreadable_systemctl_is_unknown_not_empty(self):
        self.assertIsNone(sdr.units(fake_run(raises=FileNotFoundError())))
        self.assertIsNone(sdr.units(fake_run(rc=1)))
        st = sdr.status(fake_run(raises=FileNotFoundError()))
        self.assertIsNone(st["installed"])
        checks = sdr.readiness(st, {})
        self.assertIsNone(checks["sdr-pps-marker"][0]["ok"])

    def test_only_reads(self):
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, SHOW, "")
        sdr.status(run)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][:2], ["systemctl", "show"])


class TestDongles(Tree):
    def test_rtl_sdrs_only_with_their_roles(self):
        rows = sdr.dongles()
        self.assertEqual([(r["port"], r["serial"], r["role"]) for r in rows],
                         [("1-1.2", "00001090", "1090 MHz"), ("1-1.3", "00000978", "978 MHz")])
        self.assertEqual(rows[0]["speed_mbps"]["value"], 480)
        self.assertFalse(rows[0]["dvb_driver"]["value"])
        if self.links:
            self.assertTrue(rows[1]["dvb_driver"]["value"])

    def test_the_web_sdr_role_shares_or_adds_a_dongle(self):
        self.web_env.write_text("GTP_WEBSDR_SERIAL=00001090\nGTP_WEBSDR_PORT=8073\n")
        self.assertEqual(sdr.roles()["00001090"], "1090 MHz + web SDR")
        self.web_env.write_text("GTP_WEBSDR_SERIAL=0000web1\n")
        self.assertEqual(sdr.roles()["0000web1"], "web SDR")

    def test_the_limit_on_a_pi_4(self):
        lim = sdr.limit(sdr.dongles())
        self.assertEqual((lim["model"]["value"], lim["max"]), ("Raspberry Pi 4 Model B Rev 1.5", 3))
        self.assertEqual((lim["assigned"]["value"], lim["plugged"]["value"], lim["over"]), (2, 2, False))
        self.env.write_text("GTP_SDR_PPS_SERIAL=0000pps\nGTP_SDR_1090_SERIAL=00001090\nGTP_SDR_978_SERIAL=00000978\n")
        self.web_env.write_text("GTP_WEBSDR_SERIAL=0000web1\n")
        lim = sdr.limit(sdr.dongles())
        self.assertEqual((lim["assigned"]["value"], lim["over"]), (4, True))
        self.assertIn("owner", lim["rule"])

    def test_no_limit_elsewhere_and_unknown_model(self):
        self.model.write_text("Raspberry Pi 5 Model B Rev 1.0\n")
        self.assertIsNone(sdr.limit([])["max"])
        self.model.unlink()
        lim = sdr.limit(None)
        self.assertIsNone(lim["model"]["value"])
        self.assertIsNone(lim["plugged"]["value"])
        self.assertIn("can't be read", lim["rule"])

    def test_no_sysfs_is_unknown(self):
        with mock.patch.object(sdr, "USB", self.tmp / "nope"):
            self.assertIsNone(sdr.dongles())


class TestFeeds(Tree):
    def test_age_and_count_never_a_position(self):
        now = self.feed1090.stat().st_mtime + 3.0
        f = sdr.feed("1090", now)
        self.assertEqual((f["present"], f["fresh"], f["age_s"]["value"], f["aircraft"]["value"]), (True, True, 3.0, 2))
        text = json.dumps(f)
        self.assertNotIn("38.92", text)
        self.assertNotIn("77.06", text)
        missing = sdr.feed("978", now)
        self.assertEqual((missing["present"], missing["fresh"], missing["age_s"]["value"]), (False, False, None))

    def test_stale_and_unparsable(self):
        self.feed978.parent.mkdir()
        self.feed978.write_text("{not json")
        f = sdr.feed("978", time.time() + 600)
        self.assertEqual((f["present"], f["fresh"], f["aircraft"]["value"]), (True, False, None))


class TestDongleMapping(Tree):
    def test_each_role_by_serial_and_none_is_no_dongle(self):
        a = sdr.assignments()
        self.assertEqual((a["1090"], a["978"], a["pps"], a["websdr"], a["websdr_band"]),
                         ("00001090", "00000978", None, None, None))
        self.env.write_text("GTP_SDR_1090_SERIAL=none\nGTP_SDR_978_SERIAL=00000978\n")
        self.assertIsNone(sdr.assignments()["1090"])
        self.assertNotIn("none", sdr.roles())

    def test_the_web_sdr_band_is_the_role_its_dongle_has(self):
        for web, band in (("00001090", "1090"), ("00000978", "978"), ("00000777", None)):
            with self.subTest(web):
                self.web_env.write_text(f'GTP_WEBSDR_SERIAL={web}\nGTP_WEBSDR_SHARES="x"\n')
                self.assertEqual(sdr.websdr_band(), band)

    def test_aircraft_decoders_with_serial_state_pause_and_map(self):
        self.web_env.write_text("GTP_WEBSDR_SERIAL=00000978\n")
        rows = sdr.units(fake_run(), monotonic_us=1_060_000_000)
        ac = sdr.aircraft(rows, [sdr.feed("1090"), sdr.feed("978")], websdr_on=True)
        d1090, d978 = ac["decoders"]
        self.assertEqual((d1090["serial"], d1090["units"][0]["state"], d1090["paused_by_websdr"]),
                         ("00001090", "active", False))
        self.assertTrue(d1090["serial_plugged"]["value"])
        self.assertEqual(d1090["map"]["url"], "/tar1090/")
        self.assertEqual((d978["serial"], d978["paused_by_websdr"]), ("00000978", True))   # only its dongle
        self.assertEqual(d978["units"][0]["state"], "not installed")
        self.assertEqual(d978["map"]["url"], "/skyaware978/")
        self.assertEqual(ac["websdr_band"], "978")
        unknown = sdr.aircraft(None, [sdr.feed("1090"), sdr.feed("978")], websdr_on=None)["decoders"][0]
        self.assertIsNone(unknown["units"][0]["state"])                 # systemctl unreadable: UNKNOWN
        self.assertIsNone(unknown["paused_by_websdr"])
        self.env.write_text("GTP_SDR_1090_SERIAL=00009999\n")
        gone = sdr.aircraft(rows, [], websdr_on=False)["decoders"][0]
        self.assertFalse(gone["serial_plugged"]["value"])               # no dongle has that serial

    def test_status_carries_the_aircraft_section(self):
        st = sdr.status(fake_run(), monotonic_us=1_060_000_000)
        self.assertEqual([d["band"] for d in st["aircraft"]["decoders"]], ["1090", "978"])


class TestMessageRate(Tree):
    def setUp(self):
        super().setUp()
        sdr._LAST_COUNT.clear()
        self.addCleanup(sdr._LAST_COUNT.clear)

    def write(self, now, messages):
        self.feed1090.write_text(json.dumps({"now": now, "messages": messages, "aircraft": [{}]}))

    def test_from_the_counter_between_two_reads(self):
        self.write(100.0, 5000)
        f = sdr.feed("1090", time.time())
        self.assertIsNone(f["messages_per_s"]["value"])                 # one read: no rate yet
        self.assertEqual(f["messages_per_s"]["provenance"], "calculated")
        self.write(110.0, 9000)
        self.assertEqual(sdr.feed("1090", time.time())["messages_per_s"]["value"], 400.0)
        self.write(111.0, 10)                                           # the decoder restarted
        self.assertIsNone(sdr.feed("1090", time.time())["messages_per_s"]["value"])

    def test_readsb_stats_json_first(self):
        self.write(100.0, 5000)
        (self.feed1090.parent / "stats.json").write_text(json.dumps(
            {"last1min": {"start": 1000.0, "end": 1060.0, "messages": 1800}}))
        self.assertEqual(sdr.feed("1090", time.time())["messages_per_s"]["value"], 30.0)

    def test_stale_file_has_no_rate(self):
        self.write(100.0, 5000)
        sdr.feed("1090", time.time())
        self.write(110.0, 9000)
        self.assertIsNone(sdr.feed("1090", time.time() + 600)["messages_per_s"]["value"])


class TestReadiness(Tree):
    def test_checks_follow_what_is_observed(self):
        st = sdr.status(fake_run(), now=self.feed1090.stat().st_mtime + 1)
        r = sdr.readiness(st, {})
        pps = {c["check"]: c["ok"] for c in r["sdr-pps-marker"]}
        self.assertEqual(pps, {"rtl_tcp running": False, "live capture configured": False,
                               "PPS injected at the dongle": None})
        adsb = {c["check"]: c["ok"] for c in r["reference-adsb"]}
        self.assertEqual(adsb, {"1090 MHz feed": True, "978 MHz feed": False, "at least one feed": True})
        cfg = {"module_config": {"sdr-pps-marker": {"fs_nominal": 2400000, "rtl_tcp": {"plan": [{}]}}}}
        live = {c["check"]: c["ok"] for c in sdr.readiness(st, cfg)["sdr-pps-marker"]}
        self.assertTrue(live["live capture configured"])


if __name__ == "__main__":
    unittest.main()
