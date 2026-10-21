"""The module's Source for the loader (gps_time_pi.modkit).

Demo mode (ctx.config["demo"]): runs the fixture scenarios through the
synthetic generator, detector and time model, and emits one Observation per
scenario with the time model's labeled health values.

Without demo mode there is nothing to read yet: the hardware path (an SDR with
the injected PPS) is research step 2. The source logs that and emits nothing,
so an enabled module never invents data.
"""

import json
from pathlib import Path

from gps_time_pi.modkit import Observation, Source

from . import synth
from .detector import detect
from .timemodel import TimeModel

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios.json"
NAME = "sdr-pps-marker"


class MarkerSource(Source):
    def __init__(self):
        self._stop = False

    def stop(self):
        self._stop = True

    def start(self, ctx):
        if not ctx.config.get("demo"):
            ctx.log.info("no SDR input yet (research step 2); emitting nothing")
            return
        fix = json.loads(FIXTURES.read_text(encoding="utf-8"))
        fs = fix["fs_nominal"]
        names = ctx.config.get("scenarios") or [s["name"] for s in fix["scenarios"]]
        for sc in fix["scenarios"]:
            if self._stop:
                return
            if sc["name"] not in names:
                continue
            params = dict(sc["params"])
            params["drops"] = tuple(tuple(d) for d in params.get("drops", ()))
            params["missing_seconds"] = tuple(params.get("missing_seconds", ()))
            x, _ = synth.generate(sc.get("seconds", fix["seconds"]), fs, **params)
            start = 1_792_602_000 + params.get("start_offset_s", 0.3) + fix["coarse_start_error_s"]
            model = TimeModel(detect(x, fs), fs, start)
            summary = model.summary()
            values = {k: v for k, v in summary.items() if isinstance(v, dict)}
            values["scenario"] = {"value": sc["name"], "unit": None, "provenance": "calculated",
                                  "note": "synthetic demo data, not a measurement"}
            values["state"] = {"value": summary["state"], "unit": None, "provenance": "calculated"}
            ctx.emit(Observation(time_ns=ctx.now_ns(), source=NAME, values=values,
                                 timing=ctx.timing_quality()))
