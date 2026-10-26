"""Known waveforms to look for in a capture. Pure, standard library only.

One kind so far, "prn": a pseudo-random ±1 chip sequence (seeded) with Gaussian chip pulses. It
stands in for the known parts of a real broadcast (an ATSC field sync segment, a pilot) on
synthetic data. `value(t)` evaluates the continuous waveform at any time, so a synthetic capture
can place it at a fractional-sample delay; `template(fs)` samples it for the correlator.
"""

import math
import random


class Prn:
    def __init__(self, seed, chips=255, chip_rate_hz=600e3, pulse_sigma_chips=0.45):
        rnd = random.Random(seed)
        self.seed, self.chips, self.chip_rate_hz = seed, chips, chip_rate_hz
        self.code = [1.0 if rnd.random() < 0.5 else -1.0 for _ in range(chips)]
        self.tc = 1.0 / chip_rate_hz
        self.sigma = pulse_sigma_chips * self.tc
        self.duration_s = chips * self.tc

    def value(self, t):
        """The waveform at t seconds after its start (0 outside, apart from pulse tails)."""
        k0 = math.floor(t / self.tc - 0.5)
        reach = math.ceil(3 * self.sigma / self.tc) + 1
        v = 0.0
        for k in range(k0 - reach, k0 + reach + 1):
            if 0 <= k < self.chips:
                d = t - (k + 0.5) * self.tc
                v += self.code[k] * math.exp(-0.5 * (d / self.sigma) ** 2)
        return v

    def template(self, fs):
        """The waveform sampled at fs from its start: a list of floats."""
        n = math.ceil(self.duration_s * fs)
        return [self.value(i / fs) for i in range(n)]


def from_spec(spec):
    """A waveform from its JSON description: {"kind": "prn", "seed", "chips", "chip_rate_hz"}."""
    if not isinstance(spec, dict) or spec.get("kind") != "prn":
        raise ValueError(f"unknown waveform {spec!r} (only kind 'prn' so far)")
    return Prn(int(spec["seed"]), int(spec.get("chips", 255)), float(spec.get("chip_rate_hz", 600e3)))


def rms_bandwidth(template):
    """RMS bandwidth of a sampled template, radians per sample (from its first difference)."""
    e = sum(v * v for v in template)
    d = sum((template[i + 1] - template[i]) ** 2 for i in range(len(template) - 1))
    return math.sqrt(d / e) if e > 0 else 0.0
