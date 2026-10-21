"""Find PPS markers in a stream of complex samples, to a fraction of a sample.

1. Candidates: a high-pass test, |x[i] - (x[i-4] + x[i+4]) / 2|, so a slow
   carrier doesn't hide a spike whose phase opposes it. The noise level comes
   from the test's median (Rayleigh: median = 1.1774 sigma), and the threshold
   is set for a chosen false-alarm rate (default one per hour of samples).
2. Refinement: around each candidate, remove the local carrier (a complex
   quadratic fitted to the flanks), apply a matched filter with the spike
   shape, and interpolate its peak with a parabola through the logarithm of
   three values (exact for a Gaussian peak without noise).
3. Edges: with pulse_width_s given, a spike one pulse width after another is
   a falling edge, and the one before it a confirmed rising edge. A lone spike
   (its partner too weak to see) is a falling edge when it sits one pulse
   width after the second-phase of the nearest confirmed rising edge. Lone
   spikes with no confirmed edge to compare with are kept; the time model
   flags any interval they make inconsistent. Only rising edges are markers.

Standard library only.
"""

import math
from dataclasses import dataclass

from .synth import SPIKE_SIGMA

HP_LAG = 4          # samples either side for the high-pass test
GROUP = 6           # candidates closer than this are one spike
FLANK = (5, 9)      # flank samples (inclusive) used to fit the local carrier
TAPS = 3            # matched filter half-length


@dataclass(frozen=True)
class Marker:
    sample: float     # position in the stream, in samples (sub-sample)
    amplitude: float  # matched-filter peak (arbitrary units)
    snr: float        # high-pass peak over the noise sigma


def _noise_sigma(values):
    """Rayleigh sigma of the high-pass test, from its median (robust to spikes)."""
    step = max(1, len(values) // 20000)
    sub = sorted(values[::step])
    return max(sub[len(sub) // 2] / 1.1774, 1e-30)


def _quad_fit(points):
    """Least-squares complex quadratic through (k, z) points symmetric about 0."""
    n = len(points)
    s2 = sum(k * k for k, _ in points)
    s4 = sum(k ** 4 for k, _ in points)
    b = sum(k * z for k, z in points) / s2
    sz = sum(z for _, z in points)
    s2z = sum(k * k * z for k, z in points)
    det = n * s4 - s2 * s2
    a = (sz * s4 - s2 * s2z) / det
    c = (n * s2z - s2 * sz) / det
    return lambda k: a + b * k + c * k * k


def _refine(x, c):
    """Sub-sample position and amplitude of the spike near index c, or None."""
    lo, hi = FLANK
    pts = [(k, x[c + k]) for k in list(range(-hi, -lo + 1)) + list(range(lo, hi + 1))]
    base = _quad_fit(pts)
    span = range(-lo + 1, lo)
    r = {k: x[c + k] - base(k) for k in span}
    taps = range(-TAPS, TAPS + 1)
    g = [math.exp(-0.5 * (t / SPIKE_SIGMA) ** 2) for t in taps]
    y = {}
    for j in range(-2, 3):
        acc = 0j
        for t, w in zip(taps, g):
            k = j + t
            if k in r:
                acc += r[k] * w
        y[j] = abs(acc)
    j0 = max(y, key=y.get)
    if j0 in (-2, 2):
        return None
    a, b, d = y[j0 - 1], y[j0], y[j0 + 1]
    if min(a, b, d) <= 0:
        return c + j0, b
    la, lb, ld = math.log(a), math.log(b), math.log(d)
    den = la - 2 * lb + ld
    off = 0.5 * (la - ld) / den if den < 0 else 0.0
    if abs(off) > 1:
        return None
    return c + j0 + off, b


def detect(samples, fs_nominal, *, false_alarms_per_hour=1.0, pulse_width_s=0.1,
           edge_tolerance_s=0.002):
    """Rising-edge PPS markers in the stream, in order.

    The threshold makes noise alone cross it about false_alarms_per_hour times
    per hour of samples (Rayleigh tail); spurious markers that still get through
    are discarded by the time model (less than half a second apart)."""
    x = samples
    n = len(x)
    lo, hi = FLANK
    edge = max(HP_LAG, hi) + 2
    hp = [0.0] * n
    for i in range(HP_LAG, n - HP_LAG):
        hp[i] = abs(x[i] - 0.5 * (x[i - HP_LAG] + x[i + HP_LAG]))
    sigma = _noise_sigma(hp[HP_LAG:n - HP_LAG])
    level = sigma * math.sqrt(2 * math.log(fs_nominal * 3600 / false_alarms_per_hour))

    spikes = []
    i = edge
    while i < n - edge:
        if hp[i] > level:
            j = i
            best = i
            while j < n - edge and j - best < GROUP:
                if hp[j] > hp[best]:
                    best = j
                j += 1
            ref = _refine(x, best)
            if ref is not None:
                pos, amp = ref
                spikes.append(Marker(pos, amp, hp[best] / sigma))
            i = max(j, best + 2 * HP_LAG + 2)   # past the high-pass echo at best + HP_LAG
        else:
            i += 1

    if not pulse_width_s:
        return spikes
    width = pulse_width_s * fs_nominal
    tol = edge_tolerance_s * fs_nominal
    trailing = set()
    confirmed = []
    for k, s in enumerate(spikes):
        for p in spikes[max(0, k - 3):k]:
            if abs((s.sample - p.sample) - width) <= tol:
                trailing.add(k)
                confirmed.append(p.sample)
    # samples per second from confirmed edges, so the phase test holds with a fast or slow clock
    rate = fs_nominal
    steps = [(b - a) / round((b - a) / fs_nominal) for a, b in zip(confirmed, confirmed[1:])
             if round((b - a) / fs_nominal) > 0]
    if steps:
        rate = sorted(steps)[len(steps) // 2]
    rising = []
    for k, s in enumerate(spikes):
        if k in trailing:
            continue
        if confirmed and s.sample not in confirmed:
            ref = min(confirmed, key=lambda c: abs(c - s.sample))
            phase = (s.sample - ref) % rate
            if abs(phase - width) <= tol:
                continue
        rising.append(s)
    return rising
