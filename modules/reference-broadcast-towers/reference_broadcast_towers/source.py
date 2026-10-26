"""The module's Source for the loader: what the supervisor runs.

Towers don't move, so it runs rarely (interval_s, default an hour; the cache is read again only
when its file changes) and emits:
  - one summary Observation: transmitters in the cache and accepted per service, rejections by
    reason, the cache's age and whether it is older than max_cache_age_days, any problem reading
    it, and whether a site was available (hidden privacy: counts only, nothing predicted);
  - one Observation per accepted transmitter (at most max_per_service per service, best-bounded
    first): its licence position (external) and the predicted delay, range, bound and elevation
    (calculated), and whether the path is likely line of sight (inferred).

Demo mode (ctx.config["demo"]): one cycle over fixtures/towers-cache.json (synthetic, not real
stations), from the example site (US Naval Observatory) if the host gives none, then it ends.
Without a cache it emits the summary with the problem and nothing else: an enabled module never
invents transmitters.
"""

import threading
from pathlib import Path

from gps_time_pi.modkit import Observation, Source

from . import cache
from .reference import REASONS, TowerReference

NAME = "reference-broadcast-towers"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FIXTURE_CACHE = FIXTURES / "towers-cache.json"
EXAMPLE_SITE = {"lat": 38.9217, "lon": -77.0669, "alt_msl": 92.0, "alt_hae": 59.0, "privacy": "exact",
                "note": "example position (US Naval Observatory), demo only"}


def _lv(value, unit, prov, note=None):
    d = {"value": value, "unit": unit, "provenance": prov}
    if note:
        d["note"] = note
    return d


class TowerSource(Source):
    def __init__(self):
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def cycle(self, ctx, ref, site, now_ns):
        """One pass: the observations to emit (pure apart from reading the cache)."""
        txs = ref.list(site)
        doc = ref.doc or {}
        towers = doc.get("towers", [])
        age = ref.cache_age_days(now_ns / 1e9)
        limit = float(ctx.config.get("max_cache_age_days", 365.0))
        summary = {
            "cache_available": _lv(ref.doc is not None, None, "calculated", ref.problem),
            "cache_built_utc": _lv(doc.get("built_utc"), None, "external", "when the cache was built from the records"),
            "cache_age_days": _lv(None if age is None else round(age, 2), "d", "calculated"),
            "cache_stale": _lv(None if age is None else age > limit, None, "calculated",
                               f"older than {limit:g} days: licence records change; rebuild the cache"),
            "references_accepted": _lv(len(txs), None, "calculated"),
            "site_available": _lv(site is not None, None, "calculated",
                                  None if site else "location hidden by the privacy setting: nothing predicted"),
        }
        for s in cache.SERVICES:
            summary[f"in_cache_{s.lower()}"] = _lv(sum(1 for t in towers if t.get("service") == s), None, "external")
            summary[f"accepted_{s.lower()}"] = _lv(sum(1 for t in txs if t.id.startswith(s + ":")), None, "calculated")
        for r in REASONS:
            summary[f"rejected_{r}"] = _lv(ref.rejected[r], None, "calculated")
        out = [Observation(time_ns=now_ns, source=NAME, values=summary, timing=ctx.timing_quality())]
        if site is None:
            return out
        cap = int(ctx.config.get("max_per_service", 10))
        rows = []
        for tx in txs:
            pr = ref.predict(site, tx, now_ns)
            rows.append((pr["uncertainty_s"]["value"], tx, pr))
        rows.sort(key=lambda r: (r[0], r[1].id))
        taken = {s: 0 for s in cache.SERVICES}
        for _, tx, pr in rows:
            svc = tx.id.split(":")[0]
            if taken[svc] >= cap:
                continue
            taken[svc] += 1
            p = tx.position
            values = {
                "transmitter": _lv(tx.id, None, "external", tx.position_source),
                "frequency_hz": _lv(tx.frequency_hz, "Hz", "external"),
                "bandwidth_hz": _lv(tx.bandwidth_hz, "Hz", "external"),
                "lat": _lv(p["lat"], "deg", "external", "licence record"),
                "lon": _lv(p["lon"], "deg", "external", "licence record"),
                "alt_m": _lv(p["alt_m"], "m", "external", p["alt_kind"] or "not in the record"),
                **pr,
            }
            out.append(Observation(time_ns=now_ns, source=NAME, values=values, timing=ctx.timing_quality()))
        return out

    def start(self, ctx):
        demo = bool(ctx.config.get("demo"))
        cfg = {**ctx.config, "cache_path": str(FIXTURE_CACHE)} if demo else ctx.config
        ref = TowerReference(cfg)
        interval = float(ctx.config.get("interval_s", 3600.0))
        while not self._stop.is_set():
            site = ctx.site()
            if demo and site is None:
                site = EXAMPLE_SITE
            for obs in self.cycle(ctx, ref, site, ctx.now_ns()):
                ctx.emit(obs)
            if demo:
                return
            self._stop.wait(interval)
