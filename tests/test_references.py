"""Independent references (SPEC-TIMING-METROLOGY section 4): the station
compared with NTP servers that are not steering its clock. Fixtures only: no
Internet, no chrony.
"""

import inspect
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import chrony, demo, labels, references as refs

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "chrony"
SCRIPT = ROOT / "scripts" / "chrony-independent-refs.sh"
FORBIDDEN = ("JAMMING", "SPOOF", "INTERFERENCE", "ANTENNA", "ATTACK", "FAULT", "BROKEN", "FAILED")
HDR = ("MS Name/IP address         Stratum Poll Reach LastRx Last sample\n"
       "===============================================================================\n")
PPS = "#* GPS                           0   4   377    13   +184ns[ +259ns] +/-  203ns\n"


def rows(*lines, local=()):
    return chrony.parse_sources(HDR + PPS + "".join(l + "\n" for l in lines), local_addrs=frozenset(local))


def src(addr, state="?", offset="+2ms", err="15ms", reach="377", last="30", poll=8, stratum=1):
    return f"^{state} {addr:<27} {stratum:>3} {poll:>3} {reach:>5} {last:>5} {offset:>8}[{offset:>8}] +/- {err:>6}"


class Rig:
    def __init__(self, ntp=None, threshold=None):
        self.t = [1_790_000_000.0]
        self.ntp = ntp
        self.tracker = refs.Tracker(clock=lambda: self.t[0], ntpdata_reader=lambda: self.ntp, threshold_s=threshold)

    def feed(self, source_rows, ok=True, advance=0.0):
        self.t[0] += advance
        self.tracker.update(source_rows, ok)
        return self.tracker.report()


class TestRoles(unittest.TestCase):
    def test_selected_and_combined_sources_are_not_independent(self):
        r = rows(src("192.0.2.10", "*"), src("192.0.2.11", "+"), src("192.0.2.12", "-"), src("192.0.2.13", "?"),
                 src("192.0.2.14", "x"))
        self.assertEqual([refs.role(x) for x in r],
                         [None, "steering", "steering", "independent", "independent", "independent"])

    def test_the_stations_own_address_is_never_a_reference(self):
        r = rows(src("192.0.2.50", "-"), local=("192.0.2.50",))
        self.assertEqual(refs.role(r[1]), "self")
        rep = Rig().feed(r)
        self.assertEqual(rep["references"], [])
        self.assertEqual(rep["excluded"][0]["why"], "this station's own address")
        self.assertEqual(rep["verdict"]["code"], "NONE_CONFIGURED")

    def test_usable_needs_reach_and_a_recent_sample(self):
        ok, no_reach, stale, never = rows(src("192.0.2.1"), src("192.0.2.2", reach="0"),
                                          src("192.0.2.3", last="3h"), src("192.0.2.4", last="-"))[1:]
        self.assertEqual([refs.usable(x) for x in (ok, no_reach, stale, never)], [True, False, False, False])


class TestAssessment(unittest.TestCase):
    def test_one_reference(self):
        self.assertEqual(refs.assess_one(0.004, 0.015, 0.05), "agrees")
        self.assertEqual(refs.assess_one(-0.180, 0.015, 0.05), "disagrees")
        # over the limit, but the server's own error bound is larger still
        self.assertEqual(refs.assess_one(0.080, 0.120, 0.05), "inconclusive")
        self.assertEqual(refs.assess_one(0.080, None, 0.05), "disagrees")

    def test_agree(self):
        rep = Rig().feed(rows(src("192.0.2.1"), src("192.0.2.2", offset="-3ms"), src("192.0.2.3", offset="+900us")))
        self.assertEqual(rep["verdict"]["code"], "AGREE")
        self.assertEqual((rep["verdict"]["usable"], rep["verdict"]["agreeing"]), (3, 3))

    def test_disagree_with_most(self):
        rep = Rig().feed(rows(src("192.0.2.1", offset="+180ms"), src("192.0.2.2", offset="+177ms"),
                              src("192.0.2.3", offset="+2ms")))
        v = rep["verdict"]
        self.assertEqual(v["code"], "DISAGREE")
        self.assertEqual((v["disagreeing"], v["usable"]), (2, 3))
        self.assertIn("2 of 3", v["detail"])
        self.assertIn("does not say which clock is wrong or why", v["detail"])

    def test_one_outlier_is_not_most(self):
        rep = Rig().feed(rows(src("192.0.2.1", offset="+180ms"), src("192.0.2.2"), src("192.0.2.3")))
        self.assertEqual(rep["verdict"]["code"], "AGREE")
        self.assertIn("1 differ by more", rep["verdict"]["detail"])

    def test_half_is_not_most(self):
        rep = Rig().feed(rows(src("192.0.2.1", offset="+180ms"), src("192.0.2.2")))
        self.assertEqual(rep["verdict"]["code"], "AGREE")

    def test_inconclusive_measurements_do_not_count_as_disagreement(self):
        rep = Rig().feed(rows(src("192.0.2.1", offset="+80ms", err="120ms"), src("192.0.2.2", offset="+90ms", err="150ms")))
        self.assertEqual(rep["verdict"]["code"], "AGREE")
        self.assertEqual(rep["verdict"]["inconclusive"], 2)
        self.assertIn("can't decide", rep["verdict"]["detail"])

    def test_threshold_is_configurable(self):
        r = rows(src("192.0.2.1", offset="+20ms", err="5ms"), src("192.0.2.2", offset="+22ms", err="5ms"))
        self.assertEqual(Rig().feed(r)["verdict"]["code"], "AGREE")
        self.assertEqual(Rig(threshold=0.010).feed(r)["verdict"]["code"], "DISAGREE")

    def test_a_single_reference_gives_no_majority(self):
        rep = Rig().feed(rows(src("192.0.2.1", offset="+180ms")))
        self.assertEqual(rep["verdict"]["code"], "ONE_REFERENCE")
        self.assertIn("disagrees", rep["verdict"]["detail"])

    def test_never_names_a_cause(self):
        for scenario in demo.REFERENCE_SCENARIOS:
            text = json.dumps(demo.references(scenario)["verdict"]).upper()
            for word in FORBIDDEN:
                self.assertNotIn(word, text, f"{scenario}: {word}")


class TestOffline(unittest.TestCase):
    def test_no_internet_is_not_a_failure(self):
        rep = Rig().feed(rows(src("192.0.2.1", reach="0", last="-", offset="+0ns", err="0ns"),
                              src("192.0.2.2", reach="0", last="-", offset="+0ns", err="0ns")))
        self.assertTrue(rep["available"])
        self.assertEqual(rep["verdict"]["code"], "NONE_REACHABLE")
        self.assertEqual(rep["verdict"]["headline"], "NO EXTERNAL REFERENCES REACHABLE")
        for r in rep["references"]:
            self.assertFalse(r["usable"])
            self.assertIsNone(r["offset_s"], "an unreachable server must not show a stale or zero offset")
            self.assertEqual(r["assessment"], "not usable")

    def test_no_network_sources_at_all(self):
        rep = Rig().feed(rows())
        self.assertEqual(rep["verdict"]["code"], "NONE_CONFIGURED")

    def test_only_steering_sources(self):
        rep = Rig().feed(rows(src("192.0.2.1", "*"), src("192.0.2.2", "+")))
        self.assertEqual(rep["verdict"]["code"], "NONE_CONFIGURED")
        self.assertEqual(len(rep["excluded"]), 2)
        self.assertIn("steering the clock", rep["excluded"][0]["why"])

    def test_chrony_unreadable_is_unknown(self):
        rep = Rig().feed([], ok=False)
        self.assertFalse(rep["available"])
        self.assertEqual(rep["verdict"]["code"], "UNKNOWN")

    def test_before_any_update(self):
        rep = refs.Tracker(clock=lambda: 0.0, ntpdata_reader=lambda: None).report()
        self.assertEqual(rep["verdict"]["code"], "UNKNOWN")
        self.assertIsNone(rep["as_of_utc"])


class TestHistoryAndDelay(unittest.TestCase):
    NTP = {"192.0.2.1": {"peer_delay_s": 0.031, "root_delay_s": 0.0004}}

    def test_one_point_per_new_measurement(self):
        rig = Rig(ntp=self.NTP)
        rig.feed(rows(src("192.0.2.1", last="30")))
        rig.feed(rows(src("192.0.2.1", last="35")), advance=5)        # same measurement, 5 s later
        rep = rig.feed(rows(src("192.0.2.1", last="95")), advance=60)  # still the same measurement
        self.assertEqual(len(rep["references"][0]["history"]), 1)
        rep = rig.feed(rows(src("192.0.2.1", last="10", offset="+3ms")), advance=200)   # a new one
        hist = rep["references"][0]["history"]
        self.assertEqual(len(hist), 2)
        self.assertEqual(hist[-1]["offset_s"], 0.003)
        self.assertEqual(hist[-1]["delay_s"], 0.031)
        self.assertEqual(hist[-1]["t"], rig.t[0] - 10)

    def test_history_is_bounded(self):
        rig = Rig()
        for _ in range(refs.HISTORY_POINTS + 50):
            rig.feed(rows(src("192.0.2.1", last="5")), advance=120)
        self.assertEqual(len(rig.tracker.report()["references"][0]["history"]), refs.HISTORY_POINTS)

    def test_number_of_servers_is_bounded(self):
        rig = Rig()
        for i in range(refs.MAX_SOURCES + 5):
            rig.feed(rows(src(f"192.0.2.{i + 1}", last="5")), advance=120)
        self.assertEqual(len(rig.tracker._history), refs.MAX_SOURCES)

    def test_delay_comes_from_ntpdata(self):
        rep = Rig(ntp=self.NTP).feed(rows(src("192.0.2.1"), src("192.0.2.2")))
        by = {r["name"]: r for r in rep["references"]}
        self.assertEqual(by["192.0.2.1"]["delay_s"], 0.031)
        self.assertIsNone(by["192.0.2.2"]["delay_s"])
        self.assertTrue(rep["delay_available"])

    def test_without_the_helper_delay_is_unknown_and_offsets_still_work(self):
        rep = Rig(ntp=None).feed(rows(src("192.0.2.1"), src("192.0.2.2")))
        self.assertFalse(rep["delay_available"])
        self.assertIn("UNKNOWN", rep["delay_note"])
        self.assertEqual(rep["verdict"]["code"], "AGREE")
        self.assertIsNone(rep["references"][0]["delay_s"])

    def test_a_failing_ntpdata_reader_does_not_stop_the_tracker(self):
        def boom():
            raise OSError("no helper")
        t = refs.Tracker(clock=lambda: 100.0, ntpdata_reader=boom)
        t.update(rows(src("192.0.2.1"), src("192.0.2.2")), True)
        self.assertEqual(t.report()["verdict"]["code"], "AGREE")

    def test_labels(self):
        rep = Rig(ntp=self.NTP).feed(rows(src("192.0.2.1"), src("192.0.2.2")))
        self.assertEqual(rep["provenance"], "external")
        self.assertEqual(rep["references"][0]["provenance"], "external")
        self.assertEqual(rep["verdict"]["provenance"], "calculated")
        self.assertIn(rep["verdict"]["provenance"], labels.PROVENANCE)
        self.assertIn("positive means the station's clock is ahead", rep["sign"])
        json.dumps(rep)


class TestNtpdata(unittest.TestCase):
    TEXT = (FIX / "ntpdata.txt").read_text(encoding="utf-8")

    def test_parse(self):
        d = chrony.parse_ntpdata(self.TEXT)
        self.assertEqual(sorted(d), ["192.0.2.10", "2001:db8::5"])
        self.assertEqual(d["192.0.2.10"]["peer_delay_s"], 0.031175634)
        self.assertEqual(d["192.0.2.10"]["root_delay_s"], 0.000015)
        self.assertEqual(d["192.0.2.10"]["stratum"], 1)
        self.assertEqual(d["192.0.2.10"]["total_valid_rx"], 24)
        self.assertEqual(d["2001:db8::5"]["peer_delay_s"], 0.0182)

    def test_empty_and_garbage(self):
        self.assertEqual(chrony.parse_ntpdata(""), {})
        self.assertEqual(chrony.parse_ntpdata("501 Not authorised\n"), {})

    def test_published_file_is_used_and_a_stale_one_ignored(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        p = os.path.join(d, "chrony-ntpdata.txt")
        Path(p).write_text(self.TEXT, encoding="utf-8")
        with mock.patch.object(chrony, "NTPDATA_FILE", p), \
                mock.patch.object(chrony, "run_chronyc", side_effect=AssertionError("chronyc must not run")):
            self.assertIn("192.0.2.10", chrony.ntpdata())
        old = os.stat(p).st_mtime - chrony.CLIENTS_MAX_AGE_S - 30
        os.utime(p, (old, old))
        with mock.patch.object(chrony, "NTPDATA_FILE", p), mock.patch.object(chrony, "run_chronyc", lambda *a: (False, "")):
            self.assertIsNone(chrony.ntpdata(), "a stopped helper must read as UNKNOWN")


class TestService(unittest.TestCase):
    def test_timing_chain_feeds_the_tracker(self):
        from tests.test_timing_chain import Rig as ChainRig
        rig = ChainRig(sources="sources_pps_selected")
        self.addCleanup(rig.cleanup)
        with mock.patch.object(chrony, "local_addresses", lambda *a, **k: frozenset()):
            rig.pulses(3)
        rep = rig.svc.references.report()
        # fixture: 192.0.2.10 is '-' (independent), 198.51.100.7 is '+' (combined: steering)
        self.assertEqual([r["name"] for r in rep["references"]], ["192.0.2.10"])
        self.assertEqual([e["name"] for e in rep["excluded"]], ["198.51.100.7"])
        self.assertEqual(rep["verdict"]["code"], "ONE_REFERENCE")

    def test_route_in_demo_mode(self):
        from gps_time_pi import server
        with mock.patch.object(server, "DEMO_MODE", True):
            self.assertEqual(server.references_payload({})["verdict"]["code"], "AGREE")
            self.assertEqual(server.references_payload({"scenario": ["disagree"]})["verdict"]["code"], "DISAGREE")
            self.assertEqual(server.references_payload({"scenario": ["unreachable"]})["verdict"]["code"], "NONE_REACHABLE")
            self.assertEqual(server.references_payload({"scenario": ["bogus"]})["verdict"]["code"], "AGREE")

    def test_module_never_writes_chrony_or_contacts_a_server(self):
        src_text = inspect.getsource(refs)
        for word in ("open(", "socket", "urllib", "subprocess", "run_chronyc", "import requests"):
            self.assertFalse(word in src_text, f"references.py must not use {word}")


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "POSIX bash needed")
class TestInstallerScript(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.file = self.dir / "gps-time-independent.sources"
        (self.dir / "other.sources").write_text("server keep.example iburst\n", encoding="utf-8")

    def run_script(self, value=None, directory=None):
        env = {k: v for k, v in os.environ.items() if k != "GTP_INDEPENDENT_REFS"}
        if value is not None:
            env["GTP_INDEPENDENT_REFS"] = value
        return subprocess.run(["bash", str(SCRIPT), str(directory or self.dir)], env=env,
                              capture_output=True, text=True, timeout=30)

    def servers(self):
        return [l for l in self.file.read_text(encoding="utf-8").splitlines() if not l.startswith("#")]

    def test_off_by_default(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0)
        self.assertFalse(self.file.exists())
        self.assertIn("none added", r.stdout)

    def test_default_set_is_noselect_and_polls_slowly(self):
        r = self.run_script("1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.servers(), [f"server {h} noselect minpoll 8 maxpoll 10"
                                          for h in ("time.nist.gov", "tick.usno.navy.mil", "tock.usno.navy.mil")])

    def test_every_line_is_noselect(self):
        self.run_script("a.example 192.0.2.7 2001:db8::5")
        lines = self.servers()
        self.assertEqual(len(lines), 3)
        for line in lines:
            self.assertRegex(line, r"^server \S+ noselect minpoll 8 maxpoll 10$")

    def test_unset_keeps_an_existing_file(self):
        self.run_script("a.example")
        before = self.file.read_text(encoding="utf-8")
        r = self.run_script()
        self.assertEqual(self.file.read_text(encoding="utf-8"), before)
        self.assertIn("kept as it is", r.stdout)

    def test_zero_removes_only_its_own_file(self):
        self.run_script("1")
        r = self.run_script("0")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["other.sources"])

    def test_anything_but_a_host_name_is_refused(self):
        for bad in ("good.example bad;rm", "x$(id)", "-x", "a/b", "a.example,b.example", "'quoted'"):
            with self.subTest(bad=bad):
                r = self.run_script(bad)
                self.assertNotEqual(r.returncode, 0)
                self.assertFalse(self.file.exists())

    def test_extra_words_can_only_become_noselect_servers(self):
        # Each word is treated as a host; none can smuggle in another directive or option.
        self.run_script("a.example prefer\nserver evil iburst")
        for line in self.servers():
            self.assertRegex(line, r"^server [A-Za-z0-9.:-]+ noselect minpoll 8 maxpoll 10$")

    def test_missing_directory_fails_without_creating_it(self):
        r = self.run_script("1", directory=self.dir / "nope")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.dir / "nope").exists())


class TestInstaller(unittest.TestCase):
    def test_step_is_optional_and_runs_before_chrony_restarts(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        step = text.index("bash scripts/chrony-independent-refs.sh /etc/chrony/sources.d \\\n  || echo \"Warning:")
        self.assertLess(step, text.index("systemctl restart chrony\n"))

    def test_script_writes_only_its_own_file(self):
        code = "\n".join(l for l in SCRIPT.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
        self.assertNotIn("chrony.conf\"", code)
        for word in ("systemctl", "chronyc", "rm -rf", "sed -i"):
            self.assertNotIn(word, code)
        self.assertEqual(re.findall(r"> \"\$FILE[^\"]*\"", code), ['> "$FILE.tmp"'])

    def test_no_source_may_be_added_without_noselect(self):
        code = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'server \$host[^"]*', code), ["server $host noselect minpoll 8 maxpoll 10"])


if __name__ == "__main__":
    unittest.main()
