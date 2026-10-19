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

    def test_unreachable_exits_2(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = soak.main(["http://127.0.0.1:9", "--expect", "x"])
        self.assertEqual(code, 2)
        self.assertIn("not readable", out.getvalue())


if __name__ == "__main__":
    unittest.main()
