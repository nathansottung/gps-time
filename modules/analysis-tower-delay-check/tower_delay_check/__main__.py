"""python -m tower_delay_check check | synth | demo   (run from the module's folder; needs numpy)

check  --window W.json [--mode MODE]
       W.json lists the inputs, paths relative to it:
         {"mode": "tdoa", "captures": ["a-88", ...], "captures_b": ["b-88", ...],
          "predictions": "predictions.jsonl", "predictions_b": "predictions-b.jsonl",
          "emissions": [{"transmitter": ..., "waveform": {...}, "emission_utc_ns": ...}, ...]}
       captures are observation-file bases (BASE.sigmf-meta/-data), marker-timed; predictions are
       reference-broadcast-towers' observations (JSON lines), one file per site. Prints one
       result/1 JSON line per tower and a summary line.
synth  --scenario NAME --out DIR
       Write a synthetic scenario from fixtures/scenarios.json: its captures as observation
       files, DIR/window.json for `check`, and DIR/truth.json. Synthetic: not a measurement.
demo   Run every fixture scenario through the check and print the results.
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from gps_time_pi import obsformat
from gps_time_pi.modkit import schema

from . import synth
from .capture import Capture
from .check import MODES, TowerDelayCheck


def _print(results):
    for r in results:
        d = r.to_dict()
        errs = schema.validate(d, schema.load("result.v1"))
        if errs:
            raise SystemExit(f"internal error: a result doesn't match result/1: {errs}")
        print(json.dumps(d, sort_keys=True))


def _jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_window(path):
    """The check's window from a window.json file (paths relative to it)."""
    p = Path(path)
    w = json.loads(p.read_text(encoding="utf-8"))
    rel = lambda x: str(p.parent / x)   # noqa: E731
    ems = w["emissions"]
    if isinstance(ems, str):
        ems = json.loads(Path(rel(ems)).read_text(encoding="utf-8"))
    return w.get("mode"), {
        "captures": [Capture.read(rel(b)) for b in w["captures"]],
        "captures_b": [Capture.read(rel(b)) for b in w.get("captures_b", [])],
        "predictions": _jsonl(rel(w["predictions"])),
        "predictions_b": _jsonl(rel(w["predictions_b"])) if w.get("predictions_b") else [],
        "emissions": ems,
        "capture_ids": list(w["captures"]) + list(w.get("captures_b", [])),
    }


def write_scenario(sc, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    window, files, truth = synth.make(sc)
    names = {"a": [], "b": []}
    for site, cid, meta, data in files:
        obsformat.write(str(out / cid), meta, data)
        names[site].append(cid)
    for name in (sc.get("predictions", "predictions.jsonl"), sc.get("predictions_b", "predictions-b.jsonl")):
        if (synth.FIXTURES / name).exists():
            shutil.copyfile(synth.FIXTURES / name, out / name)
    w = {"mode": sc["mode"], "captures": names["a"], "captures_b": names["b"],
         "predictions": sc.get("predictions", "predictions.jsonl"),
         "predictions_b": sc.get("predictions_b", "predictions-b.jsonl") if names["b"] else None,
         "emissions": window["emissions"], "comment": f"SYNTHETIC scenario {sc['name']}"}
    (out / "window.json").write_text(json.dumps(w, indent=1) + "\n", encoding="utf-8")
    (out / "truth.json").write_text(json.dumps(truth, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return out / "window.json"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m tower_delay_check", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--window", required=True)
    c.add_argument("--mode", choices=MODES, default=None, help="overrides the window's mode")
    s = sub.add_parser("synth")
    s.add_argument("--scenario", required=True)
    s.add_argument("--out", required=True)
    sub.add_parser("demo")
    a = ap.parse_args(argv)
    now = time.time_ns()

    if a.cmd == "check":
        mode, window = load_window(a.window)
        _print(TowerDelayCheck({"mode": a.mode or mode or "common_offset"}).run({**window, "time_ns": now}))
        return 0

    scenarios = {sc["name"]: sc for sc in synth.load_scenarios()["scenarios"]}
    if a.cmd == "synth":
        if a.scenario not in scenarios:
            ap.error(f"unknown scenario; one of: {', '.join(scenarios)}")
        path = write_scenario(scenarios[a.scenario], a.out)
        print(f"{path} (synthetic: {a.scenario})")
        return 0

    for name, sc in scenarios.items():
        window, _files, _truth = synth.make(sc)
        _print(TowerDelayCheck({"mode": sc["mode"]}).run({**window, "capture_ids": [f"synthetic:{name}"], "time_ns": now}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
