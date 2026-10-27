"""The module's Source for the loader (gps_time_pi.modkit).

Demo mode (ctx.config["demo"]): runs the fixture scenarios through the synthetic generator,
detector and time model, and emits one Observation per scenario with the time model's labeled
health values.

Live mode (an "rtl_tcp" section in the module's config): an RTL-SDR served by rtl_tcp on this
host, with the station's PPS injected at its input (spec: Physical build). Every cycle_s the
source runs the capture plan: per entry, one dwell (capture.py), the snippets that have a time
written as observation files to the module's RAM storage (newest keep_files kept), and one
Observation with the dwell's health. A dwell without markers writes nothing and says why.

Without either, there is nothing to read: the source logs that and emits nothing, so an enabled
module never invents data.
"""

import json
import threading
from pathlib import Path

from gps_time_pi import obsformat
from gps_time_pi.modkit import Observation, Source

from . import synth
from .detector import detect
from .timemodel import TimeModel

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios.json"
NAME = "sdr-pps-marker"
LIVE_DEFAULTS = {"host": "127.0.0.1", "port": 1234, "sample_rate_hz": 2.4e6, "gain_tenth_db": None,
                 "settle_s": 0.3, "cycle_s": 600.0, "retry_s": 60.0, "keep_files": 40, "plan": []}


def _lv(value, unit, prov, note=None):
    d = {"value": value, "unit": unit, "provenance": prov}
    if note:
        d["note"] = note
    return d


class MarkerSource(Source):
    def __init__(self, connect=None, clock=None):
        self._stop = threading.Event()
        self._connect = connect          # tests: a function (host, port) -> client
        self._clock = clock

    def stop(self):
        self._stop.set()

    def start(self, ctx):
        if ctx.config.get("demo"):
            return self._demo(ctx)
        if ctx.config.get("rtl_tcp"):
            return self._live(ctx)
        ctx.log.info("no SDR input configured (rtl_tcp) and not in demo mode; emitting nothing")

    # ----- demo -----

    def _demo(self, ctx):
        fix = json.loads(FIXTURES.read_text(encoding="utf-8"))
        fs = fix["fs_nominal"]
        names = ctx.config.get("scenarios") or [s["name"] for s in fix["scenarios"]]
        for sc in fix["scenarios"]:
            if self._stop.is_set():
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
            values["time_source"] = {"value": summary["time_source"], "unit": None, "provenance": "calculated"}
            ctx.emit(Observation(time_ns=ctx.now_ns(), source=NAME, values=values,
                                 timing=ctx.timing_quality()))

    # ----- live -----

    def _client(self, cfg):
        from .rtltcp import RtlTcp
        if self._connect:
            return self._connect(cfg["host"], cfg["port"])
        return RtlTcp(cfg["host"], cfg["port"])

    def _status(self, ctx, problem, center=None):
        vals = {"state": _lv("UNKNOWN", None, "calculated", problem),
                "time_source": _lv("pps_marker", None, "calculated")}
        if center is not None:
            vals["center_hz"] = _lv(center, "Hz", "calculated", "the tuning commanded to rtl_tcp")
        ctx.emit(Observation(time_ns=ctx.now_ns(), source=NAME, values=vals, timing=ctx.timing_quality()))

    def _keep(self, ctx, keep):
        names = ctx.storage.names()
        bases = []
        for n in names:
            b = n.rsplit(".sigmf-", 1)[0]
            if b not in bases:
                bases.append(b)
        for b in bases[:max(0, len(bases) - keep)]:
            for ext in (".sigmf-meta", ".sigmf-data"):
                ctx.storage.delete(b + ext)

    def _write(self, ctx, meta, data, keep):
        from gps_time_pi.modkit.context import StorageFull
        first = next(c for c in meta["captures"] if "core:datetime" in c)
        base = obsformat.filename(meta["global"]["gpstime:station_id"], "rf", obsformat.parse_ns(first["core:datetime"]))
        base = base.rsplit(".sigmf", 1)[0]
        data_b, meta_b = obsformat.to_bytes(meta, data)
        for attempt in range(2):
            try:
                self._keep(ctx, keep - 1)
                ctx.storage.write(base + ".sigmf-data", data_b)
                ctx.storage.write(base + ".sigmf-meta", meta_b)
                return base
            except StorageFull:
                keep = max(1, keep // 2)         # make room: fewer older files
        raise StorageFull("RAM storage full even after removing older captures")

    def _live(self, ctx):
        from . import capture
        cfg = {**LIVE_DEFAULTS, **(ctx.config.get("rtl_tcp") or {})}
        plan = [capture.Plan.from_config(p) for p in cfg["plan"]]
        if not plan:
            self._status(ctx, "rtl_tcp is configured but its plan is empty: nothing to capture")
            return
        if ctx.storage is None:
            self._status(ctx, "no storage (the manifest asks for ram): nothing can be written")
            return
        clock = self._clock or (lambda: ctx.now_ns() / 1e9)
        station = str(ctx.config.get("station_id") or "gps-time-station")
        while not self._stop.is_set():
            t_cycle = clock()
            failed = False
            for p in plan:
                if self._stop.is_set():
                    break
                # one connection per dwell: rtl_tcp resets its buffer for a new client, so no
                # samples queued while the last dwell was being processed arrive with this one
                try:
                    client = self._client(cfg)
                except Exception as e:      # noqa: BLE001 — rtl_tcp down: report and retry later
                    self._status(ctx, str(e), p.center_hz)
                    failed = True
                    break
                try:
                    self._dwell(ctx, client, p, cfg, station, clock)
                except Exception as e:      # noqa: BLE001 — a lost connection ends the dwell, not the module
                    self._status(ctx, f"capture stopped: {e}", p.center_hz)
                finally:
                    client.close()
            wait = float(cfg["retry_s"]) if failed else float(cfg["cycle_s"]) - (clock() - t_cycle)
            self._stop.wait(max(0.0, wait))

    def _dwell(self, ctx, client, p, cfg, station, clock):
        from . import capture
        fs = float(cfg["sample_rate_hz"])
        raw, coarse = capture.record(client, p, fs, cfg["gain_tenth_db"], float(cfg["settle_s"]), clock=clock)
        site = ctx.site()
        position = None if site is None else {"privacy": site.get("privacy", "exact"), "lat": site.get("lat"),
                                              "lon": site.get("lon")}
        model, files, skipped = capture.process(
            raw, p, fs, coarse, station_id=station, timing=ctx.timing_quality(), position=position,
            marker_delay_s=float(ctx.config.get("marker_delay_s", 0.0)),
            pulse_width_s=float(ctx.config.get("pulse_width_s", 0.1)),
            false_alarms_per_hour=float(ctx.config.get("false_alarms_per_hour", 1.0)),
            gain_tenth_db=cfg["gain_tenth_db"], hw=f"RTL-SDR via rtl_tcp ({getattr(client, 'tuner', 'tuner unknown')})")
        del raw
        written = [self._write(ctx, meta, data, int(cfg["keep_files"])) for _w, meta, data in files]
        summary = model.summary()
        vals = {k: v for k, v in summary.items() if isinstance(v, dict)}
        vals["state"] = _lv(summary["state"], None, "calculated",
                            None if summary["state"] == "OK" else "too few PPS markers in the samples to time them")
        vals["time_source"] = _lv(summary["time_source"], None, "calculated")
        vals["center_hz"] = _lv(p.center_hz, "Hz", "calculated", "the tuning commanded to rtl_tcp")
        vals["dwell_s"] = _lv(p.dwell_s, "s", "calculated")
        off = capture.coarse_offset_s(model, coarse)
        vals["host_clock_offset_s"] = _lv(None if off is None else round(off, 4), "s", "calculated",
                                          "host clock at the first byte against the markers' whole seconds; "
                                          "includes the USB and network delay")
        vals["windows_written"] = _lv(len(written), None, "calculated", ", ".join(written) or None)
        vals["windows_skipped"] = _lv(len(skipped), None, "calculated", "; ".join(r for _w, r in skipped) or None)
        if p.label:
            vals["label"] = _lv(p.label, None, "calculated")
        ctx.emit(Observation(time_ns=ctx.now_ns(), source=NAME, values=vals, timing=ctx.timing_quality()))
