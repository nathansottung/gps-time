"""The detector at real sample rates (numpy): the same markers as detector.detect, faster.

detector.detect is pure Python: fine for the synthetic tests, far too slow for 2.4 MS/s. Here
the high-pass test, the noise level and the threshold crossings are vectorized, then the few
crossings go through the same grouping, refinement and edge rules (detector.spikes_from and
classify_edges). On one block it returns exactly what detector.detect returns (a test checks).

Long streams go in blocks with an overlap, so memory stays bounded; each block sets its own
noise level, and a spike belongs to the block its position falls in.

Also: cu8_to_iq, the RTL-SDR's unsigned 8-bit samples as complex.
"""

import numpy as np

from .detector import FLANK, HP_LAG, classify_edges, noise_level, spikes_from

BLOCK_S = 0.5
OVERLAP = 64


def cu8_to_iq(raw):
    """Interleaved unsigned 8-bit I/Q (RTL-SDR) as complex64, centred: (v − 127.5) / 127.5."""
    a = np.frombuffer(raw, dtype=np.uint8)
    a = a[:len(a) - (len(a) % 2)].astype(np.float32)
    a = (a - 127.5) / 127.5
    return (a[0::2] + 1j * a[1::2]).astype(np.complex64)


def _noise_sigma(hp_valid):
    step = max(1, len(hp_valid) // 20000)
    sub = hp_valid[::step]
    k = len(sub) // 2
    return max(float(np.partition(sub, k)[k]) / 1.1774, 1e-30)


def spikes_block(x, fs_nominal, false_alarms_per_hour=1.0):
    """Spikes (not yet sorted into edges) in one block of complex samples."""
    x = np.asarray(x, dtype=np.complex128)
    n = len(x)
    hp = np.zeros(n)
    if n <= 2 * HP_LAG:
        return []
    hp[HP_LAG:n - HP_LAG] = np.abs(x[HP_LAG:n - HP_LAG] - 0.5 * (x[:n - 2 * HP_LAG] + x[2 * HP_LAG:]))
    sigma = _noise_sigma(hp[HP_LAG:n - HP_LAG])
    level = noise_level(sigma, fs_nominal, false_alarms_per_hour)
    edge = max(HP_LAG, FLANK[1]) + 2
    cand = np.flatnonzero(hp[edge:n - edge] > level) + edge
    return spikes_from(x, hp, cand.tolist(), level, sigma, n)


def detect(samples, fs_nominal, *, false_alarms_per_hour=1.0, pulse_width_s=0.1, edge_tolerance_s=0.002,
           block_s=BLOCK_S):
    """Rising-edge markers in a complex sample array (any length), in order."""
    n = len(samples)
    block = max(4096, int(block_s * fs_nominal))
    spikes = []
    for b0 in range(0, n, block):
        lo, hi = max(0, b0 - OVERLAP), min(n, b0 + block + OVERLAP)
        for s in spikes_block(samples[lo:hi], fs_nominal, false_alarms_per_hour):
            pos = s.sample + lo
            if b0 <= pos < b0 + block:
                spikes.append(type(s)(pos, s.amplitude, s.snr))
    return classify_edges(spikes, fs_nominal, pulse_width_s, edge_tolerance_s)


def detect_cu8(raw, fs_nominal, **kw):
    """Markers in raw cu8 bytes, converting one block at a time (bounded memory)."""
    n = len(raw) // 2
    block = max(4096, int(kw.pop("block_s", BLOCK_S) * fs_nominal))
    spikes = []
    for b0 in range(0, n, block):
        lo, hi = max(0, b0 - OVERLAP), min(n, b0 + block + OVERLAP)
        x = cu8_to_iq(raw[2 * lo:2 * hi])
        for s in spikes_block(x, fs_nominal, kw.get("false_alarms_per_hour", 1.0)):
            pos = s.sample + lo
            if b0 <= pos < b0 + block:
                spikes.append(type(s)(pos, s.amplitude, s.snr))
    return classify_edges(spikes, fs_nominal, kw.get("pulse_width_s", 0.1), kw.get("edge_tolerance_s", 0.002))


def as_cu8(x, scale=None):
    """Complex samples as RTL-SDR-style cu8 bytes (for synthetic streams): (v·scale + 127.5), clipped."""
    x = np.asarray(x)
    if scale is None:
        peak = float(max(np.abs(x.real).max(initial=0), np.abs(x.imag).max(initial=0)))
        scale = 127.0 / peak if peak > 0 else 1.0
    out = np.empty(2 * len(x), dtype=np.float64)
    out[0::2], out[1::2] = x.real * scale + 127.5, x.imag * scale + 127.5
    return np.clip(np.round(out), 0, 255).astype(np.uint8).tobytes(), scale
