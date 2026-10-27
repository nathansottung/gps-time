"""One RTL-SDR dwell: tune, record, find the markers, time the samples, keep short windows.

A dwell (one entry of the capture plan):
  1. tune rtl_tcp (centre, sample rate, gain), then read and drop settle_s of samples: what was
     already buffered at the old tuning;
  2. read dwell_s of samples into RAM as the raw cu8 bytes (2 bytes per sample: 6 s at
     2.4 MS/s is 29 MB), noting the host clock at the first byte (it only has to pick the right
     UTC second: within 0.5 s);
  3. find the PPS markers (fast.detect_cu8, block by block) and build the time model;
  4. cut each requested window (snippet) out as an observation file (cu8, as the dongle
     delivers it). A window gets a file only if some of its samples have a time: the module
     never writes an untimed capture. The rest of the dwell is dropped from RAM.

Nothing is written for samples the model can't time, and nothing at all without markers: the
dwell then reports state UNKNOWN and the reason.

The UTC second of each marker comes from the host clock (the time model rounds). That is safe only
while the host clock places the markers near whole seconds: if the first marker falls more than
MAX_COARSE_ERROR_S from one, the second is ambiguous and nothing is written. One connection per
dwell (source.py) keeps rtl_tcp's buffer from holding old samples: it resets its buffer for each
new client, so the host clock at the first byte is close to the time of the first sample.
"""

import time
from dataclasses import dataclass, field

from .fast import detect_cu8
from .observation import window_observation
from .timemodel import TimeModel

MAX_COARSE_ERROR_S = 0.25


@dataclass
class Window:
    at_s: float              # start, seconds after the dwell's first sample
    duration_s: float


@dataclass
class Plan:
    center_hz: float
    dwell_s: float = 10.0
    windows: list = field(default_factory=lambda: [Window(3.0, 0.03)])
    label: str = ""

    @classmethod
    def from_config(cls, d):
        wins = [Window(float(w.get("at_s", 3.0)), float(w.get("duration_s", 0.03))) for w in d.get("windows", [{}])]
        return cls(float(d["center_hz"]), float(d.get("dwell_s", 10.0)), wins, str(d.get("label", "")))


def record(client, plan, sample_rate_hz, gain_tenth_db=None, settle_s=0.3, clock=time.time, chunk=1 << 18):
    """(raw cu8 bytes, coarse UTC of the first sample) for one dwell."""
    client.tune(plan.center_hz, sample_rate_hz, gain_tenth_db)
    client.skip(2 * int(settle_s * sample_rate_hz))
    want = 2 * int(plan.dwell_s * sample_rate_hz)
    buf = bytearray()
    first = client.read(min(chunk, want))
    t0 = clock()
    buf += first
    while len(buf) < want:
        buf += client.read(min(chunk, want - len(buf)))
    # the first chunk took len(first)/2 samples to arrive: its first sample is that much earlier
    return bytes(buf), t0 - (len(first) // 2) / sample_rate_hz


def coarse_offset_s(model, coarse_start_utc):
    """How far the host clock puts the first marker from a whole second (s), or None."""
    if not model.markers:
        return None
    t = coarse_start_utc + model.markers[0] / model.fs_nominal - model.marker_delay_s
    return t - round(t)


def process(raw, plan, sample_rate_hz, coarse_start_utc, *, station_id, timing=None, position=None,
            marker_delay_s=0.0, pulse_width_s=0.1, false_alarms_per_hour=1.0, gain_tenth_db=None, hw=None):
    """(time model, [(window, meta, data) ...], [(window, reason) ...]) for one recorded dwell."""
    markers = detect_cu8(raw, sample_rate_hz, pulse_width_s=pulse_width_s, false_alarms_per_hour=false_alarms_per_hour)
    model = TimeModel(markers, sample_rate_hz, coarse_start_utc, marker_delay_s=marker_delay_s)
    files, skipped = [], []
    off = coarse_offset_s(model, coarse_start_utc)
    if off is not None and abs(off) > MAX_COARSE_ERROR_S:
        why = (f"the host clock puts the PPS markers {off:+.3f} s from whole seconds (limit "
               f"{MAX_COARSE_ERROR_S} s): their UTC second is ambiguous; nothing written")
        return model, [], [(w, why) for w in plan.windows]
    for w in plan.windows:
        start = int(round(w.at_s * sample_rate_hz))
        count = int(round(w.duration_s * sample_rate_hz))
        try:
            meta, data = window_observation(raw, model, start, count, station_id=station_id,
                                            frequency_hz=plan.center_hz, timing=timing, position=position,
                                            hw=hw, gain=gain_tenth_db)
        except ValueError as e:
            skipped.append((w, str(e)))
            continue
        files.append((w, meta, data))
    return model, files, skipped
