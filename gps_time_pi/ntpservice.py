"""NTP service health from chrony's own counters (`chronyc -n serverstats`).

chronyd counts the NTP packets it received and the ones it dropped. This
module keeps a short RAM history of those counters and turns them into rates.
The counters are chrony's (`observed`); rates and shares are `calculated`.

What the counters do and don't say:
  - "dropped" is chrony's count of packets it dropped under its rate limit
    (the `ratelimit` directive). No other reason is inferred here.
  - chrony does not count replies. "Not dropped" (received - dropped) is the
    closest figure to "served", and is labeled as that calculation.
  - The counters start at zero when chronyd starts.
Nothing here talks to chronyd: the report is published by the helper service.
"""

import threading
import time
from collections import deque
from datetime import datetime, timezone

from . import chrony
from .labels import q

SAMPLE_INTERVAL_S = 60.0
HISTORY_POINTS = 1440          # 24 h at one sample a minute
READ_INTERVAL_S = 15.0

UNAVAILABLE = ("chrony's server statistics could not be read. They come from the chrony helper service "
               "(gps-time-pi-chrony-clients), which publishes `chronyc -n serverstats`.")


class Tracker:
    def __init__(self, clock=time.time, reader=None):
        self.clock = clock
        self.reader = reader or chrony.serverstats
        self._lock = threading.Lock()
        self._samples = deque(maxlen=HISTORY_POINTS + 1)   # (t, received, dropped)
        self._latest, self._read_at, self._ok_at = None, None, None
        self.counter_resets = 0

    def update(self):
        """Read the published counters (at most every READ_INTERVAL_S) and keep one sample a minute."""
        now = self.clock()
        if self._read_at is not None and now - self._read_at < READ_INTERVAL_S:
            return
        self._read_at = now
        try:
            stats = self.reader()
        except Exception:  # noqa: BLE001 — a helper problem must not stop the timing chain
            stats = None
        with self._lock:
            self._latest = stats
            if not stats or stats.get("ntp_received") is None:
                return
            self._ok_at = now
            received, dropped = stats["ntp_received"], stats.get("ntp_dropped") or 0
            if self._samples and received < self._samples[-1][1]:
                # the counter went down: chronyd restarted
                self._samples.clear()
                self.counter_resets += 1
            if not self._samples or now - self._samples[-1][0] >= SAMPLE_INTERVAL_S:
                self._samples.append((now, received, dropped))

    def _rate(self, samples, window_s, now):
        """Packets per second over the last `window_s`, from the stored samples; None if the history is shorter."""
        old = [s for s in samples if now - s[0] >= window_s]
        if not old or len(samples) < 2:
            return None, None
        a, b = old[-1], samples[-1]
        if b[0] <= a[0]:
            return None, None
        span = b[0] - a[0]
        return (b[1] - a[1]) / span, (b[2] - a[2]) / span

    def report(self):
        """The /api/ntp-service payload."""
        now = self.clock()
        with self._lock:
            stats, samples = self._latest, list(self._samples)
            ok_at, resets = self._ok_at, self.counter_resets
        if not stats or stats.get("ntp_received") is None:
            return {"available": False, "reason": UNAVAILABLE, "state": "UNKNOWN", "provenance": "observed",
                    "counters": None, "ntp": None, "rates": None, "history": [], "counter_resets": resets,
                    "as_of_utc": None}
        received, dropped = stats["ntp_received"], stats.get("ntp_dropped")
        not_dropped = None if dropped is None else received - dropped
        hour_rx, hour_drop = self._rate(samples, 3600.0, now)
        min_rx, min_drop = self._rate(samples, SAMPLE_INTERVAL_S, now)
        recent_rx, recent_drop = (hour_rx, hour_drop) if hour_rx is not None else (min_rx, min_drop)
        if recent_rx is None:
            state = "UNKNOWN" if not received else "SERVING"
            basis = "since chronyd started (no rate yet: less than a minute of history)"
        else:
            state = ("SERVING_WITH_DROPS" if recent_drop and recent_drop > 0 else
                     "SERVING" if recent_rx > 0 else "NO_REQUESTS")
            basis = "over the last hour" if hour_rx is not None else "over the last minute"
        history = [{"t": b[0], "received_per_min": round((b[1] - a[1]) * 60.0 / (b[0] - a[0]), 2),
                    "dropped_per_min": round((b[2] - a[2]) * 60.0 / (b[0] - a[0]), 2)}
                   for a, b in zip(samples, samples[1:]) if b[0] > a[0]]
        return {
            "available": True, "reason": None, "provenance": "observed",
            "state": state, "state_basis": basis, "state_provenance": "calculated",
            "as_of_utc": datetime.fromtimestamp(ok_at, timezone.utc).isoformat(timespec="seconds") if ok_at else None,
            "counters": stats,
            "ntp": {
                "received": q(received, "packets", "observed", "NTP packets received, since chronyd started"),
                "dropped": q(dropped, "packets", "observed", "NTP packets chrony dropped under its rate limit"),
                "not_dropped": q(not_dropped, "packets", "calculated",
                                 "received − dropped; chrony does not count the replies it sent"),
                "drop_fraction": q(None if dropped is None or not received else dropped / received, None, "calculated"),
            },
            "rates": {
                "last_minute": {"received_per_s": q(min_rx, "1/s", "calculated"), "dropped_per_s": q(min_drop, "1/s", "calculated")},
                "last_hour": {"received_per_s": q(hour_rx, "1/s", "calculated"), "dropped_per_s": q(hour_drop, "1/s", "calculated")},
            },
            "history": history,
            "history_info": {"interval_s": SAMPLE_INTERVAL_S, "max_points": HISTORY_POINTS,
                             "storage": "RAM only; lost when the service restarts"},
            "counter_resets": resets,
            "note": "Counters are chrony's and restart from zero when chronyd restarts.",
        }
