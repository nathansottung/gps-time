"""analysis-tower-delay-check on synthetic marker-timed captures (fixtures/scenarios.json).

The waveforms are the real kinds: the ATSC A/53 field sync (checked against the standard's
printed sequences) and FM correlation against a reference capture. The truth is known
(synth.py), so the tests check the analysis recovers it: arrival times, the common offset,
site b's clock offset, the injected disagreements, the undetected tower, and the stated
uncertainty's coverage over many seeds. No SDR, no network.

Needs numpy (a station dependency). The plain test run skips these where numpy isn't installed;
CI runs them in the station's venv and fails if they are skipped.
"""

import contextlib
import importlib
import io
import json
import math
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:          # pragma: no cover - the station venv has it
    HAVE_NUMPY = False

if HAVE_NUMPY:
    from gps_time_pi import obsformat
    from gps_time_pi.modkit import schema
    from tower_delay_check import synth
    from tower_delay_check import waveform as wv
    from tower_delay_check.__main__ import main as cli
    from tower_delay_check.capture import Capture
    from tower_delay_check.check import TowerDelayCheck, common_offset, pick_capture, refine_peak
    SCEN = {s["name"]: s for s in synth.load_scenarios()["scenarios"]}
    RESULT = schema.load("result.v1")

MOD = Path(__file__).resolve().parents[1]
NEEDS = unittest.skipUnless(HAVE_NUMPY, "numpy is needed (a station dependency; CI runs these in the station venv)")


def run(name, mode=None, **over):
    sc = {**SCEN[name], **over}
    window, files, truth = synth.make(sc)
    res = TowerDelayCheck({"mode": mode or sc["mode"]}).run({**window, "capture_ids": [name], "time_ns": 1})
    return {r.values["transmitter"]["value"]: r for r in res[:-1]}, res[-1], truth, window


def sigma(r, key):
    return r.uncertainty[key]["value"]


@NEEDS
class TestA53(unittest.TestCase):
    def test_pn_sequences_match_their_generators(self):
        self.assertEqual((len(wv.PN511), len(wv.PN63)), (511, 63))
        self.assertEqual(wv.lfsr([7, 6, 4, 3, 1, 0], 9, "010000000", 511), wv.PN511)   # X9+X7+X6+X4+X3+X+1
        self.assertEqual(wv.lfsr([1, 0], 6, "100111", 63), wv.PN63)                    # X6+X+1
        self.assertTrue(wv.PN511.startswith("0000000101111111") and wv.PN63.startswith("1110010010"))

    def test_field_sync_layout(self):
        lv = wv.field_sync_levels()
        self.assertEqual(len(lv), 832)
        self.assertEqual(lv[:4], [5.0, -5.0, -5.0, 5.0])
        self.assertEqual(set(lv[:728]), {5.0, -5.0})
        inv = wv.field_sync_levels(middle_inverted=True)
        diff = [i for i in range(832) if lv[i] != inv[i]]
        self.assertEqual((diff[0], diff[-1], len(diff)), (4 + 511 + 63, 4 + 511 + 126 - 1, 63))
        tmpl = wv.template_levels()
        self.assertEqual(sum(1 for v in tmpl if v), 665)
        self.assertEqual(wv.VSB_MODE_8VSB[:8], "00001010")
        self.assertAlmostEqual(wv.SR, 10.762237762e6, delta=1)
        self.assertAlmostEqual(wv.FIELD_S, 24.2e-3, delta=0.02e-3)

    def test_spectrum_pilot_and_band(self):
        x, rate = wv.vsb_baseband([0.0] * 4096, pilot=True)                 # the pilot alone
        f = np.fft.fftfreq(len(x), 1 / rate)
        self.assertAlmostEqual(f[np.argmax(np.abs(np.fft.fft(x)))], -wv.SR / 4, delta=rate / len(x))
        rng = np.random.default_rng(1)
        x, rate = wv.vsb_baseband(list(rng.choice([-7, -5, -3, -1, 1, 3, 5, 7], 8192)), pilot=False)
        P = np.abs(np.fft.fft(x)) ** 2
        f = np.fft.fftfreq(len(x), 1 / rate)
        self.assertLess(P[np.abs(f) > 3.05e6].sum() / P.sum(), 1e-4)       # inside the 6 MHz channel
        self.assertGreater(P[np.abs(f) < 2.4e6].sum() / P.sum(), 0.75)     # flat across 5.38 MHz


@NEEDS
class TestPieces(unittest.TestCase):
    def test_refine_peak_recovers_a_fractional_position(self):
        for true in (0.0, 0.23, -0.41, 0.5):
            k = np.arange(-40, 41)
            c = np.sinc(0.8 * (k - true)) * np.exp(0.7j)
            self.assertAlmostEqual(40 + refine_peak(c, 40), 40 + true, delta=0.01)

    def test_common_offset_is_robust_to_one_tower(self):
        rows = [{"residual_s": x, "sigma_s": 1e-7} for x in (1.00e-6, 1.02e-6, 0.98e-6, 5e-6)]
        off, _ = common_offset(rows)
        self.assertAlmostEqual(off, 1.0e-6, delta=0.03e-6)
        two = [{"residual_s": 1e-6, "sigma_s": 1e-7}, {"residual_s": 3e-6, "sigma_s": 1e-7}]
        self.assertAlmostEqual(common_offset(two)[0], 2e-6, delta=1e-12)

    def files(self, name="atsc-absolute-agree"):
        return synth.make(SCEN[name])[1]

    def test_only_marker_timed_captures(self):
        _s, _i, meta, data = self.files()[0]
        meta = json.loads(json.dumps(meta))
        meta["global"]["gpstime:time_source"] = "ntp"
        with self.assertRaises(ValueError):
            Capture(meta, data)

    def test_marker_blanked_tuning_follows_the_clock(self):
        _s, _i, meta, data = self.files()[0]
        cap = Capture(meta, data)
        self.assertEqual(cap.blanked, 13)
        self.assertEqual(float(np.abs(cap.samples[294:307]).max()), 0.0)
        self.assertIsNone(cap.time_ns(10.0))                                 # before the marker: no time
        self.assertAlmostEqual(cap.clock_ppm, 12.0, places=6)
        self.assertAlmostEqual(cap.tune_hz - 593e6, 593e6 * 12e-6, places=3)
        self.assertEqual(Capture(meta, data, lo_follows_clock=False).tune_hz, 593e6)

    def test_capture_choice_by_band(self):
        caps = [Capture(m, d) for _s, _i, m, d in self.files()]
        self.assertAlmostEqual(pick_capture(caps, 521e6, "atsc_field_sync").center_hz, 521.5e6)
        self.assertAlmostEqual(pick_capture(caps, 189e6, "atsc_field_sync").center_hz, 187.8e6)
        self.assertIsNone(pick_capture(caps, 300e6, "atsc_field_sync"))

    def test_fm_reference_isolates_its_station(self):
        _w, files, _t = synth.make(SCEN["fm-tdoa-agree"])
        cap = Capture(*next((m, d) for s, i, m, d in files if i == "a-88"))
        ref = wv.FmReference(88.5e6, cap, cap.timed_start + 1000, 4800)
        P = np.abs(np.fft.fft(ref.base)) ** 2
        f = np.fft.fftfreq(len(ref.base), 1 / cap.rate)
        self.assertLess(P[np.abs(f) > 110e3].sum() / P.sum(), 1e-3)
        tmpl, lead = ref.template(cap)
        self.assertEqual(lead, 0.0)
        self.assertEqual(len(tmpl), 4800)


@NEEDS
class TestScenarios(unittest.TestCase):
    def assertArrival(self, r, truth_ns, key="arrival_utc_ns", unc="measured_delay_s", k=4.0):
        err = (r.values[key]["value"] - truth_ns) / 1e9
        self.assertLessEqual(abs(err), k * sigma(r, unc), (err, sigma(r, unc)))

    def test_atsc_absolute_all_agree_and_arrivals_match_the_truth(self):
        per, summ, truth, _ = run("atsc-absolute-agree")
        self.assertEqual(summ.values["overall"]["value"], "consistent")
        for tx, r in per.items():
            self.assertEqual(r.values["verdict"]["value"], "agree", tx)
            self.assertEqual(r.values["waveform"]["value"], "atsc_field_sync")
            self.assertArrival(r, truth[tx]["arrival_a_ns"])
            self.assertLess(sigma(r, "measured_delay_s"), 60e-9)            # 417 ns per sample

    def test_atsc_common_offset_recovered_and_the_injected_tower_disagrees(self):
        per, summ, _t, _ = run("atsc-common-offset-one-disagrees")
        off, osig = summ.values["common_offset_s"]["value"], summ.uncertainty["common_offset_s"]["value"]
        self.assertLessEqual(abs(off - 2.5e-6), 3 * osig + 20e-9)
        self.assertEqual(per["ATSC:900012:189000"].values["verdict"]["value"], "disagree")
        self.assertGreater(per["ATSC:900012:189000"].values["z"]["value"], 10)
        for tx in ("ATSC:900010:593000", "ATSC:900011:521000"):
            self.assertEqual(per[tx].values["verdict"]["value"], "agree")
        self.assertEqual(summ.values["overall"]["value"], "inconsistent")

    def test_a_weak_tower_is_unknown_and_claims_nothing(self):
        per, summ, _t, _ = run("atsc-one-tower-too-weak")
        weak = per["ATSC:900011:521000"].values
        self.assertEqual((weak["detected"]["value"], weak["verdict"]["value"]), (False, "unknown"))
        self.assertIn("threshold", weak["detected"]["note"])
        self.assertNotIn("residual_s", weak)
        self.assertEqual(summ.values["detected"]["value"], 2)
        self.assertEqual(summ.values["overall"]["value"], "consistent")

    def test_fm_tdoa_agrees_with_the_truth(self):
        per, summ, truth, _ = run("fm-tdoa-agree")
        self.assertEqual(summ.values["overall"]["value"], "consistent")
        for tx, r in per.items():
            v = r.values
            self.assertEqual((v["waveform"]["value"], v["verdict"]["value"]), ("fm_reference", "agree"), tx)
            t = truth[tx]
            true_tdoa = t["delay_b_s"] - t["delay_a_s"]
            err = v["measured_tdoa_s"]["value"] - true_tdoa
            self.assertLessEqual(abs(err), 4 * sigma(r, "measured_tdoa_s"), (tx, err))
            self.assertLess(sigma(r, "measured_tdoa_s"), 150e-9)

    def test_mixed_tdoa_recovers_site_b_clock_and_flags_the_late_tower(self):
        per, summ, _t, _ = run("mixed-tdoa-common-offset-one-disagrees")
        off, osig = summ.values["common_offset_s"]["value"], summ.uncertainty["common_offset_s"]["value"]
        self.assertLessEqual(abs(off - 1.7e-6), 3 * osig + 20e-9)
        self.assertEqual(per["FM:900002:93900"].values["verdict"]["value"], "disagree")
        for tx in ("FM:900001:88500", "ATSC:900010:593000", "ATSC:900011:521000"):
            self.assertEqual(per[tx].values["verdict"]["value"], "agree", tx)
        self.assertIn("snr_a", per["ATSC:900010:593000"].values)

    def test_fm_needs_a_reference_capture(self):
        sc = dict(SCEN["fm-tdoa-agree"], mode="common_offset")
        sc["captures"] = [c for c in sc["captures"] if c["site"] == "a"]
        per, summ, _t, _ = run("fm-tdoa-agree", mode="common_offset", captures=sc["captures"])
        for r in per.values():
            self.assertIn("TDOA modes only", r.values["detected"]["note"])
        self.assertEqual(summ.values["overall"]["value"], "unknown")

    def test_missing_predictions(self):
        window, _f, _t = synth.make(SCEN["mixed-tdoa-common-offset-one-disagrees"])
        window["predictions_b"] = [p for p in window["predictions_b"]
                                   if p["values"]["transmitter"]["value"] != "FM:900001:88500"]
        window["predictions"] = [p for p in window["predictions"]
                                 if p["values"]["transmitter"]["value"] != "ATSC:900011:521000"]
        res = TowerDelayCheck({"mode": "tdoa_common_offset"}).run(window)
        per = {r.values["transmitter"]["value"]: r.values for r in res[:-1]}
        self.assertIn("site b", per["FM:900001:88500"]["detected"]["note"])
        self.assertIn("no prediction", per["ATSC:900011:521000"]["detected"]["note"])

    def test_results_match_the_schema_and_labels(self):
        for name in SCEN:
            per, summ, _t, _ = run(name)
            for r in list(per.values()) + [summ]:
                d = r.to_dict()
                self.assertEqual(schema.validate(d, RESULT), [], name)
                for v in list(d["values"].values()) + list(d.get("uncertainty", {}).values()):
                    self.assertIn(v["provenance"], ("observed", "calculated", "modeled", "predicted", "inferred", "external"))
                self.assertEqual(d["values"].get("verdict", d["values"].get("overall"))["provenance"], "inferred")

    def test_emitted_streams_are_declared(self):
        import tomllib
        declared = set(tomllib.loads((MOD / "module.toml").read_text(encoding="utf-8"))["emits"]["streams"])
        for name in SCEN:
            per, summ, _t, _ = run(name)
            for r in list(per.values()) + [summ]:
                self.assertLessEqual(set(r.values), declared, name)

    def test_stated_uncertainty_covers_the_error(self):
        for name, key, need in (("atsc-absolute-agree", "a", 0.9), ("fm-tdoa-agree", "tdoa", 0.85)):
            zs = []
            for seed in range(24):
                per, _s, truth, _ = run(name, seed=500 + seed)
                for tx, r in per.items():
                    v = r.values
                    if key == "a":
                        err = (v["arrival_utc_ns"]["value"] - truth[tx]["arrival_a_ns"]) / 1e9
                        zs.append(abs(err) / sigma(r, "measured_delay_s"))
                    else:
                        err = v["measured_tdoa_s"]["value"] - (truth[tx]["delay_b_s"] - truth[tx]["delay_a_s"])
                        zs.append(abs(err) / sigma(r, "measured_tdoa_s"))
            within = sum(z <= 1.96 for z in zs) / len(zs)
            self.assertGreaterEqual(within, need, (name, within, sorted(zs)[-5:]))


@NEEDS
class TestCliAndFixtures(unittest.TestCase):
    def test_synth_validate_check_round_trip(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        with contextlib.redirect_stdout(io.StringIO()):
            cli(["synth", "--scenario", "mixed-tdoa-common-offset-one-disagrees", "--out", d])
        w = json.loads(Path(d, "window.json").read_text(encoding="utf-8"))
        for base in w["captures"] + w["captures_b"]:
            errs, _warns = obsformat.validate(str(Path(d, base)))
            self.assertEqual(errs, [], base)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli(["check", "--window", str(Path(d, "window.json"))])
        lines = [json.loads(x) for x in buf.getvalue().splitlines()]
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[-1]["values"]["mode"]["value"], "tdoa_common_offset")
        self.assertEqual(lines[-1]["values"]["overall"]["value"], "inconsistent")

    def test_demo(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(cli(["demo"]), 0)
        self.assertEqual(len(buf.getvalue().splitlines()), sum(len(s["towers"]) + 1 for s in SCEN.values()))

    def test_fixtures_are_synthetic(self):
        self.assertIn("SYNTHETIC", synth.load_scenarios()["comment"])
        for f in ("predictions.jsonl", "predictions-b.jsonl"):
            for o in synth.load_predictions(f):
                self.assertIn("SYN", o["values"]["transmitter"]["note"])

    def test_prediction_fixtures_match_reference_broadcast_towers(self):
        towers = MOD.parent / "reference-broadcast-towers"
        if str(towers) not in sys.path:
            sys.path.insert(0, str(towers))
        ref_mod = importlib.import_module("reference_broadcast_towers.reference")
        src = importlib.import_module("reference_broadcast_towers.source")
        site_b = {"lat": 38.8895, "lon": -77.0353, "alt_msl": 12.0, "alt_hae": -21.0, "privacy": "exact"}
        for f, site in (("predictions.jsonl", dict(src.EXAMPLE_SITE)), ("predictions-b.jsonl", site_b)):
            ref = ref_mod.TowerReference({"cache_path": str(src.FIXTURE_CACHE)})
            txs = {t.id: t for t in ref.list(site)}
            for o in synth.load_predictions(f):
                tx = o["values"]["transmitter"]["value"]
                p = ref.predict(site, txs[tx], 0)
                self.assertAlmostEqual(p["delay_s"]["value"], o["values"]["delay_s"]["value"], delta=1e-15, msg=(f, tx))


if __name__ == "__main__":
    unittest.main()
