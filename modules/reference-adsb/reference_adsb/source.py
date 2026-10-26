"""The module's Source for the loader: what the supervisor runs.

Every interval_s it reads the decoders' aircraft.json files through AdsbReference and emits:
  - one summary Observation: aircraft seen per band, accepted, rejected by reason, and whether
    a site was available (hidden privacy: counts only, nothing predicted);
  - one Observation per accepted aircraft (at most max_per_band per band, best-bounded first):
    its self-reported position (external) and the predicted delay, range and bound (calculated).

Demo mode (ctx.config["demo"]): one cycle over fixtures/aircraft-1090.json and
fixtures/aircraft-978.json (synthetic, not real traffic), from the example site (US Naval
Observatory) if the host gives none, then it finishes. Without a decoder file it emits the
counts (all zero) and nothing else: an enabled module never invents aircraft.
"""

import json
import threading
from pathlib import Path

from gps_time_pi.modkit import Observation, Source

from .feeds import parse
from .reference import REASONS, AdsbReference

NAME = "reference-adsb"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
EXAMPLE_SITE = {"lat": 38.9217, "lon": -77.0669, "alt_msl": 92.0, "alt_hae": 59.0, "privacy": "exact",
                "note": "example position (US Naval Observatory), demo only"}


def _fixture_reader(path, band):
    doc = json.loads((FIXTURES / f"aircraft-{band}.json").read_text(encoding="utf-8"))
    return parse(doc, band)


def _lv(value, unit, prov, note=None):
    d = {"value": value, "unit": unit, "provenance": prov}
    if note:
        d["note"] = note
    return d


class AdsbSource(Source):
    def __init__(self):
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def cycle(self, ctx, ref, site, now_ns):
        """One read: the observations to emit (pure apart from the feeds)."""
        txs = ref.list(site)
        out = []
        summary = {
            "aircraft_seen_1090": _lv(ref.seen[1090], None, "external", "entries in the decoder's aircraft.json"),
            "aircraft_seen_978": _lv(ref.seen[978], None, "external", "entries in the decoder's aircraft.json"),
            "references_accepted": _lv(len(txs), None, "calculated"),
            "site_available": _lv(site is not None, None, "calculated",
                                  None if site else "location hidden by the privacy setting: nothing predicted"),
        }
        for r in REASONS:
            summary[f"rejected_{r}"] = _lv(ref.rejected[r], None, "calculated")
        out.append(Observation(time_ns=now_ns, source=NAME, values=summary, timing=ctx.timing_quality()))
        if site is None:
            return out
        cap = int(ctx.config.get("max_per_band", 10))
        rows = []
        for tx in txs:
            pr = ref.predict(site, tx, now_ns)
            rows.append((pr["uncertainty_s"]["value"], tx, pr))
        rows.sort(key=lambda r: r[0])
        taken = {1090: 0, 978: 0}
        for _, tx, pr in rows:
            band = int(tx.id.split(":")[0])
            if taken[band] >= cap:
                continue
            taken[band] += 1
            p = tx.position
            values = {
                "transmitter": _lv(tx.id, None, "external", tx.position_source),
                "frequency_hz": _lv(tx.frequency_hz, "Hz", "external"),
                "lat": _lv(p["lat"], "deg", "external", "self-reported by the aircraft"),
                "lon": _lv(p["lon"], "deg", "external", "self-reported by the aircraft"),
                "alt_m": _lv(p["alt_m"], "m", "external", f"{p['alt_kind']} altitude, self-reported"),
                **pr,
            }
            out.append(Observation(time_ns=now_ns, source=NAME, values=values, timing=ctx.timing_quality()))
        return out

    def start(self, ctx):
        demo = bool(ctx.config.get("demo"))
        ref = AdsbReference(ctx.config, reader=_fixture_reader) if demo else AdsbReference(ctx.config)
        interval = float(ctx.config.get("interval_s", 10.0))
        while not self._stop.is_set():
            site = ctx.site()
            if demo and site is None:
                site = EXAMPLE_SITE
            now_ns = ctx.now_ns()
            if demo:
                # Fixture positions are relative to their own "now": predict at that moment.
                doc = json.loads((FIXTURES / "aircraft-1090.json").read_text(encoding="utf-8"))
                now_ns = int(doc["now"] * 1e9)
            for obs in self.cycle(ctx, ref, site, now_ns):
                ctx.emit(obs)
            if demo:
                return
            self._stop.wait(interval)
