"""python -m tower_delay_check check | synth | demo   (run from the module's folder)

check  --capture BASE --predictions P.jsonl --emissions E.json [--mode absolute|common_offset]
       Read a marker-timed observation file (BASE.sigmf-meta/-data), the predictions emitted by
       reference-broadcast-towers (JSON lines) and the emissions (JSON list), and print one
       result/1 JSON line per tower and a summary line.
synth  --scenario NAME --out BASE
       Write a synthetic capture from fixtures/scenarios.json as an observation file, and its
       emissions as BASE.emissions.json. Synthetic: not a measurement.
demo   Run every fixture scenario through the check and print the results.
"""

import argparse
import json
import sys
import time

from gps_time_pi import obsformat
from gps_time_pi.modkit import schema

from . import synth
from .capture import Capture
from .check import TowerDelayCheck


def _print(results):
    for r in results:
        d = r.to_dict()
        errs = schema.validate(d, schema.load("result.v1"))
        if errs:
            raise SystemExit(f"internal error: a result doesn't match result/1: {errs}")
        print(json.dumps(d, sort_keys=True))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m tower_delay_check", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--capture", required=True)
    c.add_argument("--predictions", required=True)
    c.add_argument("--emissions", required=True)
    c.add_argument("--mode", choices=("absolute", "common_offset"), default="common_offset")
    s = sub.add_parser("synth")
    s.add_argument("--scenario", required=True)
    s.add_argument("--out", required=True)
    sub.add_parser("demo")
    a = ap.parse_args(argv)
    now = time.time_ns()

    if a.cmd == "check":
        cap = Capture.read(a.capture)
        with open(a.predictions, encoding="utf-8") as f:
            preds = [json.loads(line) for line in f if line.strip()]
        with open(a.emissions, encoding="utf-8") as f:
            ems = json.load(f)
        _print(TowerDelayCheck({"mode": a.mode}).run(
            {"capture": cap, "predictions": preds, "emissions": ems, "capture_id": a.capture, "time_ns": now}))
        return 0

    scenarios = {sc["name"]: sc for sc in synth.load_scenarios()["scenarios"]}
    preds = synth.load_predictions()
    if a.cmd == "synth":
        if a.scenario not in scenarios:
            ap.error(f"unknown scenario; one of: {', '.join(scenarios)}")
        meta, data, ems, _ = synth.make(scenarios[a.scenario], preds)
        obsformat.write(a.out, meta, data)
        with open(a.out + ".emissions.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(ems, f, indent=1)
        print(f"{a.out}.sigmf-meta, .sigmf-data, .emissions.json (synthetic: {a.scenario})")
        return 0

    for name, sc in scenarios.items():
        meta, data, ems, _ = synth.make(sc, preds)
        _print(TowerDelayCheck({"mode": sc["mode"]}).run(
            {"capture": Capture(meta, data), "predictions": preds, "emissions": ems,
             "capture_id": f"synthetic:{name}", "time_ns": now}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
