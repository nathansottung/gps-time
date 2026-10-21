"""Research step 1: detector and time model on synthetic data. No hardware, numpy or network."""

import json
import math
import tomllib
import unittest
from functools import lru_cache
from pathlib import Path

from gps_time_pi.labels import PROVENANCE
from sdr_pps_marker import TIME_SOURCE, TimeModel, detect, synth

HERE = Path(__file__).resolve().parents[1]
FIX = json.loads((HERE / "fixtures" / "scenarios.json").read_text(encoding="utf-8"))
FS = FIX["fs_nominal"]
START = 1_792_602_000
OFFSET = 0.3   # synth default: sample 0 is at START + 0.3 s


@lru_cache(maxsize=None)
def run(name):
    sc = next(s for s in FIX["scenarios"] if s["name"] == name)
    params = dict(sc["params"])
    params["drops"] = tuple(tuple(d) for d in params.get("drops", ()))
    params["missing_seconds"] = tuple(params.get("missing_seconds", ()))
    x, truth = synth.generate(sc.get("seconds", FIX["seconds"]), FS, **params)
    markers = detect(x, FS)
    model = TimeModel(markers, FS, START + OFFSET + FIX["coarse_start_error_s"])
    return sc, x, truth, markers, model


def utc_error_samples(model, truth, j):
    u = model.utc(j)
    if u is None:
        return None, None
    ts, tf = truth["true_utc"](j)
    err_s = (u.second - ts) + (u.fraction - tf)
    return err_s * FS, u


class TestScenarios(unittest.TestCase):
    def test_every_fixture_scenario(self):
        for sc in FIX["scenarios"]:
            with self.subTest(sc["name"]):
                _, _, truth, markers, model = run(sc["name"])
                exp = sc["expect"]
                self.assertEqual(len(truth["markers"]), exp["markers"])
                self.assertEqual(len(markers), exp["markers"], "every rising edge found, no falling edges, no false alarms")
                for (p, _utc), m in zip(truth["markers"], markers):
                    self.assertLess(abs(m.sample - p), exp["max_marker_error"])
                events = model.events()
                self.assertEqual(len(events), exp["events"], events)
                if "dropped" in exp:
                    self.assertEqual(events[0]["type"], "samples_missing")
                    self.assertEqual(events[0]["samples"], exp["dropped"])
                ppm = model.summary()["clock_error_ppm"]["value"]
                true_ppm = sc["params"].get("ppm", 0.0) + sc["params"].get("drift_ppm_per_s", 0.0) * 3.5
                self.assertLess(abs(ppm - true_ppm), exp["max_ppm_error"])


class TestTimeModel(unittest.TestCase):
    def check_utc(self, name, max_err_samples, k_sigma=5.0):
        _, x, truth, markers, model = run(name)
        checked = 0
        for j in range(int(markers[0].sample) + 1, int(markers[-1].sample), 1777):
            err, u = utc_error_samples(model, truth, j)
            if u is None:
                continue
            checked += 1
            self.assertLess(abs(err), max_err_samples, (name, j))
            self.assertIsNotNone(u.uncertainty_s)
            self.assertLess(abs(err) / FS, k_sigma * u.uncertainty_s + 1e-12, "uncertainty covers the error")
        self.assertGreater(checked, 50)

    def test_utc_of_samples_clean(self):
        self.check_utc("clean", 0.05)

    def test_utc_of_samples_fast_clock(self):
        self.check_utc("fast-clock-drifting", 0.08)

    def test_utc_across_a_missed_marker(self):
        _, _, truth, markers, model = run("missed-marker")
        self.assertIn(2, [iv.seconds for iv in model.intervals])
        self.check_utc("missed-marker", 0.08)

    def test_no_time_in_an_interval_with_dropped_samples(self):
        _, x, truth, markers, model = run("usb-drop")
        ev = model.events()[0]
        inside = int((ev["from_sample"] + ev["to_sample"]) / 2)
        self.assertIsNone(model.utc(inside))
        self.assertEqual(ev["after_second"], START + 3)
        self.check_utc("usb-drop", 0.08)   # the rest keeps its time across the drop

    def test_no_time_outside_the_markers(self):
        _, x, _, markers, model = run("clean")
        self.assertIsNone(model.utc(0))
        self.assertIsNone(model.utc(len(x) - 1))
        self.assertIsNotNone(model.utc(markers[0].sample))

    def test_absolute_seconds_from_a_coarse_host_clock(self):
        _, _, truth, markers, _ = run("clean")
        for err in (-0.45, -0.3, 0.0, 0.004, 0.2, 0.45):
            model = TimeModel(markers, FS, START + OFFSET + err)
            self.assertEqual(model.seconds, [u for _, u in truth["markers"]], err)

    def test_whole_nanoseconds_at_unix_scale(self):
        _, _, truth, markers, model = run("clean")
        u = model.utc(markers[2].sample)
        self.assertEqual(u.second, truth["markers"][2][1])
        self.assertLess(abs(u.ns - u.second * 1_000_000_000), 1000)   # within 1 µs of the second
        self.assertIsInstance(u.ns, int)

    def test_marker_delay_is_applied(self):
        _, _, _, markers, _ = run("clean")
        a = TimeModel(markers, FS, START + OFFSET).utc(markers[3].sample + 100)
        b = TimeModel(markers, FS, START + OFFSET, marker_delay_s=250e-9).utc(markers[3].sample + 100)
        self.assertAlmostEqual((b.fraction - a.fraction) * 1e9, 250, places=3)

    def test_spurious_marker_is_discarded(self):
        _, _, _, markers, _ = run("clean")
        extra = sorted([m.sample for m in markers] + [markers[2].sample + 0.1 * FS])
        model = TimeModel(extra, FS, START + OFFSET)
        self.assertEqual(model.discarded, 1)
        self.assertEqual(model.events(), [])

    def test_falling_edge_taken_for_a_marker_is_flagged(self):
        _, _, _, markers, _ = run("clean")
        pos = [m.sample for m in markers]
        pos[3] += 0.1 * FS   # a lone falling edge where the rising one was missed
        model = TimeModel(pos, FS, START + OFFSET)
        flagged = [iv.first for iv in model.intervals if iv.flagged]
        self.assertEqual(flagged, [2, 3])
        self.assertIsNone(model.utc(pos[3] - 10))

    def test_lone_falling_edge_is_not_a_marker(self):
        x, truth = synth.generate(FIX["seconds"], FS, noise_rms=0.03, ppm=40.0, seed=8,
                                  missing_rising_seconds=(START + 4,))
        found = detect(x, FS)
        self.assertEqual(len(found), len(truth["markers"]))
        for (p, _), m in zip(truth["markers"], found):
            self.assertLess(abs(m.sample - p), 0.1)
        model = TimeModel(found, FS, START + OFFSET)
        self.assertEqual(model.events(), [])
        self.assertIn(2, [iv.seconds for iv in model.intervals])

    def test_unknown_with_too_few_markers(self):
        five = [1000.0 + k * FS for k in range(6)]   # 4 scatter checks: one short of MIN_CHECKS
        for markers in ([], [1000.0], [1000.0, 1000.0 + FS], five):
            model = TimeModel(markers, FS, START)
            s = model.summary()
            self.assertEqual(s["state"], "UNKNOWN")
            self.assertIsNone(s["sample_time_uncertainty_s"]["value"])
            self.assertIsNone(model.utc(1000.5))


class TestSummary(unittest.TestCase):
    def test_every_value_labeled(self):
        _, _, _, _, model = run("usb-drop")
        s = model.summary()
        self.assertEqual(s["state"], "OK")
        self.assertEqual(s["time_source"], TIME_SOURCE)
        for k, v in s.items():
            if isinstance(v, dict):
                self.assertIn(v["provenance"], PROVENANCE, k)
        self.assertEqual(s["dropped_sample_events"]["value"], 1)
        self.assertIn("not included", s["sample_time_uncertainty_s"]["note"])
        self.assertAlmostEqual(s["markers_per_minute"]["value"], 60.0, delta=0.1)


class TestDetector(unittest.TestCase):
    def test_noise_alone_gives_no_markers(self):
        x, _ = synth.generate(FIX["seconds"], FS, marker_amp=0.0, noise_rms=0.05, seed=9)
        self.assertEqual(detect(x, FS), [])

    def test_carrier_alone_gives_no_markers(self):
        x, _ = synth.generate(FIX["seconds"], FS, marker_amp=0.0, noise_rms=0.05, tone_amp=3.0, tone_hz=350, seed=10)
        self.assertEqual(detect(x, FS), [])

    def test_sub_sample_accuracy_at_every_fraction(self):
        # markers land at many fractional positions; error stays small at all of them
        x, truth = synth.generate(FIX["seconds"], FS, noise_rms=0.001, ppm=13.7, seed=11)
        found = detect(x, FS)
        self.assertEqual(len(found), len(truth["markers"]))
        fracs = [p % 1 for p, _ in truth["markers"]]
        self.assertGreater(max(fracs) - min(fracs), 0.3)
        for (p, _), m in zip(truth["markers"], found):
            self.assertLess(abs(m.sample - p), 0.02)   # interpolation bias, ~8 ns at 2.4 MS/s

    def test_without_pulse_width_both_edges_are_returned(self):
        x, truth = synth.generate(FIX["seconds"], FS, noise_rms=0.02, seed=12)
        self.assertEqual(len(detect(x, FS, pulse_width_s=None)), 2 * len(truth["markers"]))


class TestManifest(unittest.TestCase):
    def test_manifest(self):
        m = tomllib.loads((HERE / "module.toml").read_text(encoding="utf-8"))
        self.assertEqual(m["name"], HERE.name)
        self.assertEqual(m["types"], ["source"])
        self.assertEqual(m["maturity"], "research")
        self.assertEqual(m["hardware"]["required"], "none")
        self.assertFalse(m["permissions"]["network"])
        self.assertEqual(m["emits"]["time_source"], TIME_SOURCE)
        self.assertEqual(m["licence"]["code"], "MIT")
        root = HERE.parents[1]
        self.assertTrue((root / m["spec"]).is_file())

    def test_standard_library_only(self):
        allowed = {"cmath", "math", "random", "dataclasses", "gps_time_pi"}
        for f in (HERE / "sdr_pps_marker").glob("*.py"):
            for line in f.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s.startswith("import ") or (s.startswith("from ") and " import " in s):
                    mod = s.split()[1].split(".")[0]
                    if mod:   # "from .x import" gives ""
                        self.assertIn(mod, allowed, f"{f.name}: {s}")


if __name__ == "__main__":
    unittest.main()
