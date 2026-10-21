"""Write a marker-timed SDR capture as an observation file (SigMF + gpstime:).

- gpstime:time_source = "pps_marker".
- One capture per interval between markers. Each carries the UTC time of its
  first sample (core:datetime, from the time model) and the interval's measured
  sample rate (gpstime:sample_rate), so every sample's time follows the time
  model exactly, drift included.
- Samples with no time (before the first marker, after the last, inside an
  interval with missing or extra samples) are in captures with
  "gpstime:time_valid": false.
- gpstime:sample_time_uncertainty_s is the time model's stated uncertainty
  (marker fit only); the station's own clock bound goes in
  gpstime:time_offset_bound_s.
- gpstime:frequency_reference: the SDR's sample clock, calibrated by the
  markers, with its measured error in ppm.
- Annotations: each marker window (to blank in analyses) and each interval
  with missing or extra samples.
"""

import math

from gps_time_pi import obsformat

RECORDER = "gps-time sdr-pps-marker"
MARKER_HALF_WINDOW = 6   # samples either side of a marker that carry its energy


def to_observation(samples, model, *, station_id, frequency_hz, timing=None, position=None,
                   datatype="cf32_le", hw=None, request_id=None, licence="CC-BY-4.0", version="0.2.0"):
    """(meta, data bytes) for obsformat.write / obsformat.to_bytes.

    timing: the station's timing quality (ctx.timing_quality()).
    position: the privacy-filtered position as {"privacy", "lat", "lon"[, "alt_m"]};
    None means hidden. datatype: cf32_le (as is) or ci16_le (scaled so the
    largest sample is full scale; the scale is in gpstime:calibration).
    Raises ValueError when the model can't time any sample."""
    if datatype not in ("cf32_le", "ci16_le"):
        raise ValueError(f"datatype {datatype!r}: use cf32_le or ci16_le for float IQ samples")
    summary = model.summary()
    if summary["state"] != "OK":
        raise ValueError("the time model has no time for these samples (state UNKNOWN); not writing an observation")
    n = len(samples)
    m = model.markers
    caps = [{"core:sample_start": 0, "core:frequency": float(frequency_hz), "gpstime:time_valid": False}]
    notes = []
    for iv in model.intervals:
        a, b = m[iv.first], m[iv.first + 1]
        start = math.ceil(a)
        if iv.flagged:
            caps.append({"core:sample_start": start, "core:frequency": float(frequency_hz), "gpstime:time_valid": False})
            diff = iv.count - iv.expected
            notes.append({"core:sample_start": start, "core:sample_count": max(0, math.floor(b) - start + 1),
                          "core:label": "samples_missing" if diff < 0 else "samples_extra",
                          "gpstime:samples": round(abs(diff))})
            continue
        t = model.utc(start)
        if t is None:
            caps.append({"core:sample_start": start, "core:frequency": float(frequency_hz), "gpstime:time_valid": False})
            continue
        caps.append({"core:sample_start": start, "core:frequency": float(frequency_hz),
                     "core:datetime": obsformat.format_ns(t.ns),
                     "gpstime:sample_rate": iv.count / iv.seconds})
    end = math.ceil(m[-1])
    if end < n:
        caps.append({"core:sample_start": end, "core:frequency": float(frequency_hz), "gpstime:time_valid": False})
    # a capture that starts where the next one does says nothing; keep the later one
    dedup = []
    for c in caps:
        if dedup and dedup[-1]["core:sample_start"] == c["core:sample_start"]:
            dedup[-1] = c
        else:
            dedup.append(c)

    for k, p in enumerate(m):
        s = max(0, math.floor(p) - MARKER_HALF_WINDOW)
        e = min(n, math.floor(p) + MARKER_HALF_WINDOW + 1)
        notes.append({"core:sample_start": s, "core:sample_count": e - s, "core:label": "pps_marker",
                      "core:comment": "PPS marker energy: blank before analysis",
                      "gpstime:utc_second": model.seconds[k]})
    notes.sort(key=lambda a: a["core:sample_start"])

    scale = 1.0
    if datatype == "ci16_le":
        peak = max((max(abs(z.real), abs(z.imag)) for z in samples), default=0.0)
        scale = 32767.0 / peak if peak > 0 else 1.0
        samples = [z * scale for z in samples]
    ppm = summary["clock_error_ppm"]["value"]
    pos = position or {"privacy": "hidden", "lat": None, "lon": None}
    meta = obsformat.build_meta(
        datatype=datatype, sample_rate=model.fs_nominal, captures=dedup, annotations=notes,
        recorder=f"{RECORDER} {version}", hw=hw,
        description="SDR capture timed by PPS markers in the samples (research)",
        gpstime={
            "station_id": station_id, "sensor": "rf", "quantity": "complex baseband voltage",
            "unit": "relative (full scale = 1)", "channels": [{"name": "IQ"}],
            "time_source": "pps_marker",
            "time_offset_bound_s": (timing or {}).get("offset_bound_s"),
            "sample_time_uncertainty_s": summary["sample_time_uncertainty_s"]["value"],
            "frequency_reference": {"state": "calibrated" if ppm is not None else "free",
                                    "error_ppm": ppm, "source": "pps_marker"},
            "calibration": {"marker_delay_s": model.marker_delay_s, "sample_scale": scale,
                            "note": "marker_delay_s: injection path delay, 0 until bench calibration (research step 2); "
                                    "sample_scale: stored value = sample x sample_scale"},
            "position": pos, "provenance": "observed", "request_id": request_id, "licence": licence,
        })
    return meta, obsformat.encode(samples, datatype)
