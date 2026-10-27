"""tools/soak_check.py: the read-only pre-release check. Fixture answers in the station's API
shapes; main() runs against a stub HTTP server on loopback (no station, no Internet)."""
import copy
import importlib.util
import io
import json
import threading
import time
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tests import _env  # noqa: F401

_spec = importlib.util.spec_from_file_location("soak_check", Path(__file__).parents[1] / "tools" / "soak_check.py")
soak = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(soak)

NOW = 1_800_000_000.0
DAY = 86400
START = NOW - 3.2 * DAY


def m(v):
    return {"value": v, "unit": None, "provenance": "observed"}


def event(start, classification, pulse="LOST", dur=60):
    return {"type": "PPS_OUTAGE", "start_epoch": start, "start_utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(start)),
            "duration_s": dur, "classification": classification, "evidence": {"at_start": {"pulse_health": pulse}}}


CLEAN = {
    "core": {"versions": {"app": "1.4.0-rc.11"}, "quality": {"stratum": "1", "reference": "47505300 (GPS)"}},
    "chain": {"status": {"code": "GPS_PPS"},
              "pps": {"missed_pulses": m(3), "unread_pulses": m(0),
                      "poller": {"polls": int(NOW - START), "late_polls": 2, "max_poll_gap_s": 1.05}},
              "events": {"open": None, "recent": [event(START + 4, "PPS NOT USED BY CHRONY", pulse="HEALTHY", dur=32),
                                                  event(START - 5 * DAY, "GNSS RECEPTION ANOMALY")]}},
    "stab": {"available": True,
             "series": {"seconds": {"samples": 14400, "gaps": 3, "pps_selected_fraction": 0.999}},
             "key_points": [{"label": l, "point": {"adev": a}} for l, a in
                            (("1 s", 1.7e-6), ("10 s", 2e-7), ("100 s", 2.1e-8), ("1000 s", 3e-9), ("1 day", None))]},
    "evid": {"files": [{"id": "a"}]},
    "idle": [12.0, 15.0, 20.0], "loaded": [18.0, 25.0, 60.0],
}


def run(d=None, expect="1.4.0-rc.11"):
    d = d or CLEAN
    res = soak.evaluate(d["core"], d["chain"], d["stab"], d["evid"], d["idle"], d["loaded"], expect, 3, now=NOW)
    return {name: ok for name, ok, _ in res}, res


class EvaluateTest(unittest.TestCase):
    def test_clean(self):
        ok, res = run()
        self.assertTrue(all(ok.values()), res)

    def test_installer_restart_is_the_only_excused_event(self):
        d = copy.deepcopy(CLEAN)
        d["chain"]["events"]["recent"].append(event(START + 3600, "PPS PATH ANOMALY"))
        self.assertFalse(run(d)[0]["outages"])
        d = copy.deepcopy(CLEAN)                                 # the same classification later in the run counts
        d["chain"]["events"]["recent"].append(event(START + 2 * 3600, "PPS NOT USED BY CHRONY", pulse="HEALTHY"))
        self.assertFalse(run(d)[0]["outages"])
        d = copy.deepcopy(CLEAN)                                 # at the start but pulses lost: real
        d["chain"]["events"]["recent"][0]["evidence"]["at_start"]["pulse_health"] = "LOST"
        self.assertFalse(run(d)[0]["outages"])

    def test_events_before_the_service_start_do_not_count(self):
        self.assertTrue(run()[0]["outages"])                     # the fixture's 5-days-old event

    def test_open_event_fails(self):
        d = copy.deepcopy(CLEAN)
        d["chain"]["events"]["open"] = event(NOW - 30, "PPS PATH ANOMALY")
        self.assertFalse(run(d)[0]["outages"])

    def test_each_criterion_can_fail(self):
        cases = {
            "version": lambda d: d["core"]["versions"].update(app="1.4.0-rc.10"),
            "runtime": lambda d: d["chain"]["pps"]["poller"].update(polls=2 * DAY),
            "timing": lambda d: d["chain"]["status"].update(code="HOLDOVER"),
            "pulses": lambda d: d["chain"]["pps"].update(missed_pulses=m(812)),
            "rtt": lambda d: d.update(loaded=[30.0, 2900.0, 3100.0]),
            "stability": lambda d: d["stab"]["key_points"][0]["point"].update(adev=2.1e-5),
        }
        for name, spoil in cases.items():
            d = copy.deepcopy(CLEAN)
            spoil(d)
            ok, _ = run(d)
            self.assertFalse(ok[name], name)
            self.assertEqual([k for k, v in ok.items() if not v], [name])

    def test_pulse_details(self):
        for change in ({"late_polls": 400}, {"max_poll_gap_s": 3.0}, {"max_poll_gap_s": None}):
            d = copy.deepcopy(CLEAN)
            d["chain"]["pps"]["poller"].update(change)
            self.assertFalse(run(d)[0]["pulses"], change)
        d = copy.deepcopy(CLEAN)
        d["chain"]["pps"]["unread_pulses"] = m(500)
        self.assertFalse(run(d)[0]["pulses"])

    def test_stability_details(self):
        for spoil in (lambda s: s.update(available=False),
                      lambda s: s["series"]["seconds"].update(pps_selected_fraction=0.97),
                      lambda s: s["series"]["seconds"].update(gaps=812),
                      lambda s: s["key_points"][3].update(point=None)):
            d = copy.deepcopy(CLEAN)
            spoil(d["stab"])
            self.assertFalse(run(d)[0]["stability"])

    def test_missing_data_is_not_clean(self):
        res = soak.evaluate({}, {}, {}, {}, [], [], "1.4.0-rc.11", 3, now=NOW)
        self.assertEqual(len(res), 7)
        self.assertFalse(any(ok for _, ok, _ in res))

    def test_report(self):
        text, clean = soak.report("http://station", run()[1], when=NOW)
        self.assertTrue(clean)
        self.assertTrue(text.endswith("CLEAN"))
        self.assertIn("[OK ] version", text)


def sdr_answer(cpu_readsb, cpu_rtl):
    def unit(name, cpu, avg):
        return {"unit": name, "active": m("active"), "cpu_s": m(cpu), "cpu_avg_pct": m(avg),
                "memory_mib": m(21.4), "restarts": m(0)}
    return {"installed": True,
            "units": [unit("gps-time-readsb.service", cpu_readsb, 22.8), unit("gps-time-rtl-tcp.service", cpu_rtl, 6.3)],
            "dongles": [{"serial": "00001090", "role": "1090 MHz", "speed_mbps": m(480), "dvb_driver": m(False)}],
            "feeds": []}


SYSTEM = {"load": [0.5, 0.4, 0.3], "throttled": {"raw": "0x50000", "any_now": False, "any_ever": True,
          "flags": [{"label": "Under-voltage occurred", "active": True}, {"label": "Throttled now", "active": False}]}}
CHAIN_PPS = dict(CLEAN["chain"], chrony={"pps": {"std_dev_s": m(3.42e-7)}})
CORE_T = dict(CLEAN["core"], cpu_temp_c=54.0, quality={"rms_offset_s": 2.09e-7})
STAB_T = dict(CLEAN["stab"], key_points=[{"label": "1 s", "point": {"adev": 1.57e-6, "tdev_s": 9.08e-7}}])


class RecordTest(unittest.TestCase):
    """The SDR load record: printed beside the criteria, never one of them."""

    def rec(self, sdr_a, sdr_b, dt=30.0, system=SYSTEM):
        return dict(soak.record(CORE_T, CHAIN_PPS, STAB_T, system, sdr_a, sdr_b, dt))

    def test_sdr_cpu_now_since_start_memory_restarts(self):
        r = self.rec(sdr_answer(100.0, 10.0), sdr_answer(106.0, 10.6))
        self.assertIn("2 of 2 units running; CPU of all of them 22.0 % of one core over the last 30 s", r["sdr"])
        self.assertIn("gps-time-readsb.service: active; CPU 20.0 % over the last 30 s, 22.8 % since its start; 21 MiB; restarts 0", r["sdr"])
        self.assertEqual(r["cpu"], "load averages 0.50 / 0.40 / 0.30 (1, 5, 15 min)")
        self.assertEqual(r["usb"], "1 RTL-SDR: 00001090 (1090 MHz) 480 Mb/s; throttled flags 0x50000: Under-voltage occurred")
        self.assertEqual(r["temperature"], "SoC 54.0 °C now")
        self.assertEqual(r["pps jitter"], "chrony PPS std dev 342 ns; RMS offset 209 ns; ADEV(1 s) 1.57e-06; TDEV(1 s) 908 ns")

    def test_a_station_without_the_sdr_status_is_unknown_not_zero(self):
        for sdr in (None, {"available": True}, {"units": None}):
            with self.subTest(sdr=sdr):
                r = self.rec(sdr, sdr, dt=0.0, system={})
                self.assertTrue(r["sdr"].startswith("UNKNOWN"))
                self.assertEqual(r["cpu"], "load averages UNKNOWN")
                self.assertEqual(r["usb"], "RTL-SDRs UNKNOWN; UNKNOWN")
        r = dict(soak.record({}, {}, {}, {}, None, None, 0.0))
        self.assertEqual(r["temperature"], "SoC UNKNOWN now")
        self.assertEqual(r["pps jitter"], "chrony PPS std dev UNKNOWN; RMS offset UNKNOWN; ADEV(1 s) UNKNOWN; TDEV(1 s) UNKNOWN")

    def test_a_unit_restarted_between_samples_has_no_rate(self):
        r = self.rec(sdr_answer(100.0, 10.0), sdr_answer(2.0, 10.6))
        self.assertIn("readsb.service: active; CPU UNKNOWN over the last 30 s", r["sdr"])

    def test_the_record_never_changes_clean(self):
        res = run()[1]
        plain, clean = soak.report("http://station", res, when=NOW)
        with_rec, clean_rec = soak.report("http://station", res, when=NOW,
                                          rec=soak.record(CORE_T, CHAIN_PPS, STAB_T, SYSTEM, None, None, 0.0))
        self.assertEqual((clean, clean_rec), (True, True))
        self.assertTrue(with_rec.startswith(plain))
        self.assertIn("Record (not criteria; no effect on CLEAN):", with_rec)
        self.assertIn("[REC] usb:", with_rec)

    def test_record_from_reads_twice_and_never_fails(self):
        calls = []
        answers = iter([SYSTEM, sdr_answer(100.0, 10.0), sdr_answer(103.0, 10.3)])

        def fetch(base, path, timeout=20):
            calls.append(path)
            return next(answers)
        rec = dict(soak.record_from("http://x", CORE_T, CHAIN_PPS, STAB_T, 0.0, fetch=fetch))
        self.assertEqual(calls, ["/api/system", "/api/sdr", "/api/sdr"])
        self.assertIn("2 of 2 units running", rec["sdr"])

        def broken(base, path, timeout=20):
            raise OSError("refused")
        rec = dict(soak.record_from("http://x", CORE_T, CHAIN_PPS, STAB_T, 0.0, fetch=broken))
        self.assertTrue(rec["sdr"].startswith("UNKNOWN"))


class StubStation(BaseHTTPRequestHandler):
    answers = {}

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        body = self.answers.get(path, {"server_receive_epoch_ms": 0, "server_send_epoch_ms": 0}
                                if path == "/api/ping" else {"available": True})
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):  # noqa: N802 - the check must never POST
        raise AssertionError("soak_check sent a POST")

    def log_message(self, *a):
        pass


class MainTest(unittest.TestCase):
    def setUp(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), StubStation)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"
        soak.time.sleep = lambda s: None          # no pauses between pings in the test
        self.addCleanup(setattr, soak.time, "sleep", time.sleep)

    def main(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = soak.main([self.base, *args])
        return code, out.getvalue()

    def test_not_clean_station_exits_1(self):
        StubStation.answers = {"/api": CLEAN["core"], "/api/timing-chain": CLEAN["chain"],
                               "/api/stability": CLEAN["stab"], "/api/evidence": CLEAN["evid"]}
        code, out = self.main("--expect", "1.4.0-rc.11")
        self.assertEqual(code, 1)                 # the stub's poll count is from its own past, not 3 days here
        self.assertIn("[OK ] version", out)
        self.assertIn("NOT CLEAN", out)
        self.assertIn("[REC] sdr: UNKNOWN", out)  # the stub has no SDR status: recorded as UNKNOWN

    def test_the_record_reads_the_sdr_status_and_keeps_the_exit_code(self):
        StubStation.answers = {"/api": CORE_T, "/api/timing-chain": CHAIN_PPS, "/api/stability": STAB_T,
                               "/api/evidence": CLEAN["evid"], "/api/system": SYSTEM, "/api/sdr": sdr_answer(100.0, 10.0)}
        code, out = self.main("--expect", "1.4.0-rc.11", "--window", "0")
        self.assertEqual(code, 1)
        self.assertIn("[REC] sdr: 2 of 2 units running", out)
        self.assertIn("[REC] pps jitter: chrony PPS std dev 342 ns", out)

    def test_unreachable_exits_2(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = soak.main(["http://127.0.0.1:9", "--expect", "x"])
        self.assertEqual(code, 2)
        self.assertIn("not readable", out.getvalue())


if __name__ == "__main__":
    unittest.main()


class RuleDocTest(unittest.TestCase):
    """docs/releases/README.md (the soak rule) lists exactly the criteria the tool checks."""

    def test_rule_lists_the_tools_criteria(self):
        import re
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        tool = (root / "tools" / "soak_check.py").read_text(encoding="utf-8")
        checked = set(re.findall(r'check\("([a-z]+)"', tool))
        rule = (root / "docs" / "releases" / "README.md").read_text(encoding="utf-8")
        table = rule.split("| Criterion | Clean when |", 1)[1].split("\n\n", 1)[0]
        listed = set(re.findall(r"^\| ([a-z]+) \|", table, re.M))
        self.assertEqual(listed, checked)
        self.assertIn("--expect", rule)
