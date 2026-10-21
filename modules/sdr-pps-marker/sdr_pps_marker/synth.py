"""Synthetic SDR sample streams with PPS markers, for tests and the demo.

Models what research step 1 needs, nothing more:

- complex baseband samples (RTL-SDR style IQ) with Gaussian noise and an
  optional slow tone standing in for a broadcast carrier;
- a short band-limited spike for each PPS edge: the rising edge on the UTC
  second and, optionally, the falling edge one pulse width later;
- a sample clock that runs fast or slow (ppm) and drifts (ppm per second);
- samples dropped in blocks, as a USB transfer would lose them;
- seconds whose marker is too weak to see.

Everything is deterministic for a given seed. No hardware, numpy or I/O.
"""

import cmath
import math
import random

# Spike shape after the SDR's filters: a Gaussian, sigma in samples.
SPIKE_SIGMA = 0.7


def spike_value(x):
    """Spike amplitude at a distance x samples from its centre."""
    return math.exp(-0.5 * (x / SPIKE_SIGMA) ** 2)


def raw_position(tau, fs_nominal, ppm=0.0, drift_ppm_per_s=0.0):
    """Raw sample position (before drops) of the instant tau seconds after sample 0.

    The sample clock runs at fs_nominal * (1 + (ppm + drift * t) * 1e-6), so the
    position is the integral of that rate."""
    return fs_nominal * (tau + 1e-6 * (ppm * tau + 0.5 * drift_ppm_per_s * tau * tau))


def raw_to_tau(p, fs_nominal, ppm=0.0, drift_ppm_per_s=0.0):
    """Inverse of raw_position (Newton's method)."""
    tau = p / fs_nominal
    for _ in range(8):
        f = raw_position(tau, fs_nominal, ppm, drift_ppm_per_s) - p
        rate = fs_nominal * (1 + 1e-6 * (ppm + drift_ppm_per_s * tau))
        tau -= f / rate
    return tau


def generate(seconds, fs_nominal, *, start_utc=1_792_602_000, start_offset_s=0.3,
             ppm=0.0, drift_ppm_per_s=0.0, marker_amp=1.0, noise_rms=0.05,
             tone_amp=0.0, tone_hz=0.0, pulse_width_s=0.1, falling_edge=True,
             drops=(), missing_seconds=(), missing_rising_seconds=(), seed=1):
    """Generate a stream. Returns (samples, truth).

    start_utc + start_offset_s is the true UTC time of raw sample 0.
    drops: (raw_index, count) blocks removed from the stream.
    missing_seconds: UTC seconds whose marker (both edges) is left out.
    missing_rising_seconds: UTC seconds whose rising edge alone is left out.
    truth: markers (output position, UTC second) of every rising edge that
    survived, the drops, and a function giving the true UTC of any output index.
    """
    rng = random.Random(seed)
    n_raw = int(raw_position(seconds, fs_nominal, ppm, drift_ppm_per_s))
    raw = [complex(rng.gauss(0, noise_rms), rng.gauss(0, noise_rms)) for _ in range(n_raw)]
    if tone_amp:
        w = 2 * math.pi * tone_hz / fs_nominal
        for i in range(n_raw):
            raw[i] += tone_amp * cmath.exp(1j * w * i)

    rising = []
    first = math.ceil(start_offset_s)
    for k in range(first, int(start_offset_s + seconds) + 1):
        utc = start_utc + k
        tau = k - start_offset_s
        edges = [(tau, True)] + ([(tau + pulse_width_s, False)] if falling_edge else [])
        for t, is_rising in edges:
            p = raw_position(t, fs_nominal, ppm, drift_ppm_per_s)
            if p < 4 or p > n_raw - 5:
                continue
            if utc in missing_seconds or (is_rising and utc in missing_rising_seconds):
                continue
            phase = cmath.exp(1j * rng.uniform(0, 2 * math.pi))
            c = int(round(p))
            for i in range(c - 4, c + 5):
                raw[i] += marker_amp * phase * spike_value(i - p)
            if is_rising:
                rising.append((p, utc))

    drops = sorted(drops)
    keep = []
    cut = 0
    removed = []
    for start, count in drops:
        keep.extend(raw[cut:start])
        removed.append((start, count))
        cut = start + count
    keep.extend(raw[cut:])

    def out_index(p):
        shift = 0
        for start, count in removed:
            if p >= start + count:
                shift += count
            elif p >= start:
                return None
        return p - shift

    def raw_index(j):
        for start, count in removed:
            if j >= start:
                j += count
        return j

    def true_utc(j):
        """True UTC of output index j, as (second, fraction)."""
        tau = raw_to_tau(raw_index(j), fs_nominal, ppm, drift_ppm_per_s)
        t = start_offset_s + tau
        s = math.floor(t)
        return start_utc + s, t - s

    markers = []
    for p, utc in rising:
        j = out_index(p)
        if j is not None:
            markers.append((j, utc))
    truth = {"markers": markers, "drops": removed, "true_utc": true_utc,
             "fs_true_at_start": fs_nominal * (1 + 1e-6 * ppm)}
    return keep, truth
