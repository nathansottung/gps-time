"""analysis-tower-delay-check on synthetic marker-timed captures (fixtures/scenarios.json).

The truth is known (synth.py), so the tests check the analysis recovers it: arrival times, the
common offset, the injected disagreement, the undetected tower, and the stated uncertainty's
coverage over many seeds. No SDR, no network.
"""

import contextlib
import io
import json
import math
import shutil
import tempfile
import unittest
from pathlib import Path

from gps_time_pi import obsformat
from gps_time_pi.modkit import schema
from tower_delay_check import synth
from tower_delay_check.__main__ import main as cli
from tower_delay_check.capture import Capture
from tower_delay_check.check import TowerDelayCheck, common_offset, find_peak
from tower_delay_check.waveform import Prn, rms_bandwidth

PREDS = synth.load_predictions()
SCEN = {s["name"]: s for s in synth.load_scenarios()["scenarios"]}
RESULT = schema.load("result.v1")


def run(name, **over):
    sc = {**SCEN[name], **over}
    meta, data, ems, truth = synth.make(sc, PREDS)
    res = TowerDelayCheck({"mode": sc["mode"]}).run({"capture": Capture(meta, data), "predictions": PREDS,
                                                     "emissions": ems, "capture_id": name, "time_ns": 1})
    per = {r.values["transmitter"]["value"]: r for r in res[:-1]}
    return per, res[-1], truth


class TestPieces(unittest.TestCase):
    def test_waveform_is_deterministic_and_band_limited(self):
        a, b = Prn(101), Prn(101)
        self.assertEqual(a.code, b.code)
        self.assertNotEqual(a.code, Prn(102).code)
        t = a.template(2.4e6)
        self.assertEqual(len(t), math.ceil(255 / 600e3 * 2.4e6))
        self.assertGreater(rms_bandwidth(t), 0.1)
        self.assertLess(rms_bandwidth(t), 1.5)

    def test_parabolic_peak(self):
        p = [1.0, 4.0, 9.0, 4.0, 1.0]
        self.assertEqual(find_peak(p), (2, 0.0))
        k, frac = find_peak([v * v for v in (2.0, 3.0, 1.0)])
        self.assertEqual(k, 1)
        self.assertLess(frac, 0)              # the peak leans toward the larger neighbour (left)

    def test_common_offset_is_robust_to_one_tower(self):
        rows = [{"residual_s": r, "sigma_s": 1e-7} for r in (2.5e-6, 2.52e-6, 6.5e-6)]
        off, sig = common_offset(rows)
        self.assertEqual(off, 2.52e-6)        # the weighted median ignores the outlier
        two = [{"residual_s": 1e-6, "sigma_s": 1e-7}, {"residual_s": 3e-6, "sigma_s": 1e-7}]
        self.assertAlmostEqual(common_offset(two)[0], 2e-6)

    def test_only_marker_timed_captures(self):
        meta, data, _, _ = synth.make(SCEN["absolute-agree"], PREDS)
        meta["global"]["gpstime:time_source"] = "host_clock"
        with self.assertRaises(ValueError):
            Capture(meta, data)

    def test_marker_window_blanked_and_untimed_samples(self):
        meta, data, _, _ = synth.make(SCEN["absolute-agree"], PREDS)
        cap = Capture(meta, data)
        self.assertEqual(cap.blanked, 13)
        self.assertTrue(all(cap.samples[i] == 0 for i in range(294, 307)))
        self.assertIsNone(cap.time_ns(100))                       # before the marker: no time
        t0 = obsformat.parse_ns(SCEN["absolute-agree"]["t0_utc"])
        self.assertEqual(cap.time_ns(300), t0)
        idx, rate = cap.index_of(t0 + 1_000_000)
        self.assertAlmostEqual(idx, 300 + 1e-3 * rate, places=6)
        self.assertIsNone(cap.index_of(t0 - 1_000_000))


class TestScenarios(unittest.TestCase):
    def test_absolute_all_agree_and_arrivals_match_the_truth(self):
        per, summ, truth = run("absolute-agree")
        self.assertEqual(summ.values["overall"]["value"], "consistent")
        for tx, r in per.items():
            v = r.values
            self.assertEqual(v["verdict"]["value"], "agree", tx)
            err = abs(v["arrival_utc_ns"]["value"] - truth[tx]["arrival_ns"])
            self.assertLess(err, 150, tx)                          # 0.36 sample at 2.4 MS/s
            self.assertLess(err * 1e-9, 2.5 * r.uncertainty["measured_delay_s"]["value"], tx)

    def test_common_offset_recovered_and_the_injected_tower_disagrees(self):
        per, summ, _ = run("common-offset-one-disagrees")
        self.assertAlmostEqual(summ.values["common_offset_s"]["value"], 2.5e-6, delta=60e-9)
        self.assertEqual(summ.values["overall"]["value"], "inconsistent")
        self.assertIn("1 of 3", summ.values["overall"]["note"])
        bad = per["ATSC:900012:189000"].values
        self.assertEqual(bad["verdict"]["value"], "disagree")
        self.assertAlmostEqual(bad["residual_after_offset_s"]["value"], 4e-6, delta=150e-9)
        self.assertIn("names no cause", bad["verdict"]["note"])
        for tx in ("FM:900001:88500", "ATSC:900011:521000"):
            self.assertEqual(per[tx].values["verdict"]["value"], "agree")

    def test_a_weak_tower_is_unknown_and_claims_nothing(self):
        per, summ, _ = run("one-tower-too-weak")
        weak = per["ATSC:900011:521000"].values
        self.assertIs(weak["detected"]["value"], False)
        self.assertEqual(weak["verdict"]["value"], "unknown")
        self.assertNotIn("residual_s", weak)
        self.assertEqual(summ.values["detected"]["value"], 2)
        self.assertEqual(summ.values["overall"]["value"], "consistent")
        self.assertAlmostEqual(summ.values["common_offset_s"]["value"], -1.2e-6, delta=60e-9)

    def test_one_tower_with_an_unknown_offset_says_nothing(self):
        sc = SCEN["one-tower-too-weak"]
        towers = [dict(t, amplitude=0.02) if t["transmitter"] != "FM:900001:88500" else t for t in sc["towers"]]
        per, summ, _ = run("one-tower-too-weak", towers=towers)
        self.assertEqual(summ.values["detected"]["value"], 1)
        self.assertEqual(summ.values["overall"]["value"], "unknown")
        self.assertEqual(per["FM:900001:88500"].values["verdict"]["value"], "unknown")

    def test_missing_prediction(self):
        sc = SCEN["absolute-agree"]
        meta, data, ems, _ = synth.make(sc, PREDS)
        res = TowerDelayCheck({"mode": "absolute"}).run({"capture": Capture(meta, data), "predictions": PREDS[:1],
                                                         "emissions": ems})
        unknown = [r for r in res[:-1] if r.values["verdict"]["value"] == "unknown"]
        self.assertEqual(len(unknown), 2)
        self.assertIn("no prediction", unknown[0].values["detected"]["note"])

    def test_results_match_the_schema_and_labels(self):
        for name in SCEN:
            per, summ, _ = run(name)
            for r in [*per.values(), summ]:
                d = r.to_dict()
                self.assertEqual(schema.validate(d, RESULT), [], name)
                self.assertEqual(d["values"]["verdict" if r is not summ else "overall"]["provenance"], "inferred")

    def test_stated_uncertainty_covers_the_error(self):
        """Over 24 seeds, the arrival error stays inside 1.96 × the stated correlator sigma ≥ 90 % of the time."""
        inside = total = 0
        for seed in range(100, 124):
            per, _, truth = run("absolute-agree", seed=seed, clock_ppm=(seed % 7) * 5.0 - 15.0)
            for tx, r in per.items():
                if not r.values["detected"]["value"]:
                    continue
                total += 1
                err = abs(r.values["arrival_utc_ns"]["value"] - truth[tx]["arrival_ns"]) * 1e-9
                inside += err <= 1.96 * r.uncertainty["measured_delay_s"]["value"]
        self.assertEqual(total, 72)
        self.assertGreaterEqual(inside / total, 0.9)


class TestCli(unittest.TestCase):
    def test_synth_validate_check_round_trip(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        base = str(Path(d, "cap"))
        with contextlib.redirect_stdout(io.StringIO()):
            cli(["synth", "--scenario", "common-offset-one-disagrees", "--out", base])
        errs, warns = obsformat.validate(base)
        self.assertEqual(errs, [])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli(["check", "--capture", base, "--predictions", str(synth.FIXTURES / "predictions.jsonl"),
                 "--emissions", base + ".emissions.json"])
        lines = [json.loads(x) for x in out.getvalue().splitlines()]
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[-1]["values"]["overall"]["value"], "inconsistent")

    def test_demo(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli(["demo"])
        self.assertEqual(len(out.getvalue().splitlines()), 12)

    def test_fixtures_are_synthetic(self):
        self.assertIn("SYNTHETIC", synth.load_scenarios()["comment"])
        self.assertTrue(all(json.loads(x)["source"] == "reference-broadcast-towers"
                            for x in (synth.FIXTURES / "predictions.jsonl").read_text(encoding="utf-8").splitlines()))


if __name__ == "__main__":
    unittest.main()
