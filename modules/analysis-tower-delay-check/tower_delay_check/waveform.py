"""Known waveforms to look for in a capture, and the shared signal tools (numpy).

Two kinds, from real broadcasts:

- "atsc_field_sync": the ATSC 1.0 (8-VSB) Data Field Sync segment, from ATSC A/53 Part 2:2011
  §5.3. Of its 832 symbols, the 4 segment-sync symbols, PN511, the first and third PN63 and the
  24 VSB-mode symbols (8-VSB, trellis coded) are known: 665 symbols. The middle PN63 is left out
  of the template because it is inverted on every other field. The reserved and precode
  symbols are unknown. It repeats once per field (313 segments, about 24.2 ms). Stations
  flagged ATSC 3.0 in the tower cache don't carry it.
- "fm_reference": FM correlation. An FM broadcast has no known sequence: its program is the
  signal. So the template is cut from a reference capture of the same broadcast (another
  station's, in a TDOA comparison), isolated to ±100 kHz around the station's frequency.

The signal model (8-VSB): real symbol levels a_k (±1, ±3, ±5, ±7, sync ±5) plus the pilot's DC
1.25, at Sr = 4.5/286 × 684 MHz; the transmitter keeps the upper sideband with a root-raised
cosine edge (α = 0.1152) at both ends. Centred on the channel, that is the complex symbol stream
a_k·(−j)^k shaped by a low-pass root-raised cosine of Nyquist frequency Sr/4 (2.69 MHz), with the
pilot at −Sr/4 (309 kHz above the lower band edge). Derived from A/53 §5.4, not copied.

The capture side: a frequency offset (channel − the SDR's real tuning, which follows its sample
clock), the capture's sample rate and a passband model of the SDR's filter (flat to 80 % of
Nyquist, a raised-cosine edge to Nyquist). A real SDR's filter differs: its group delay is the
same for every signal at one tuning and rate, so it goes into the common offset (or cancels in
a TDOA between matched receivers), and its shape costs some correlation gain.
"""

import math

import numpy as np

SR = 4.5e6 / 286 * 684                  # ATSC symbol rate, Hz (A/53 Part 2 eq. 1)
ALPHA = 0.1152                          # root-raised cosine roll-off (A/53 Part 2 §5.4.3)
PILOT = 1.25                            # DC added to every symbol (A/53 Part 2 §5.4.2)
SEGMENT_SYMBOLS = 832
FIELD_SEGMENTS = 313
FIELD_S = FIELD_SEGMENTS * SEGMENT_SYMBOLS / SR
OS = 2                                  # internal rate = OS × SR
PASS_FLAT = 0.8                         # SDR passband model: flat to 0.8 × Nyquist
FM_HALF_BW_HZ = 100e3

# A/53 Part 2 §5.3.1-5.3.2.3, as printed there. Tests regenerate PN511 and PN63 from their polynomials.
SEGMENT_SYNC = "1001"                   # +5, −5, −5, +5
PN511 = ("0000 0001 0111 1111 1100 1010 1010 1110 0110 0110 1000 1000 1001 1110 0001 1101 "
         "0111 1101 0011 0101 0011 1011 0011 1010 0100 0101 1000 1111 0010 0001 0100 0111 "
         "1100 1111 0101 0001 0100 1100 0011 0001 0000 0100 0011 1111 0000 0101 0100 0000 "
         "1100 1111 1110 1110 1010 1001 0110 0110 0011 0111 0111 1011 0100 1010 0100 1110 "
         "0111 0001 0111 0100 0011 0100 1111 1011 0001 0101 1011 1100 1101 1010 1110 1101 "
         "1001 0110 1101 1100 1001 0010 1110 0011 1001 0111 1010 0011 0101 1000 0100 1101 "
         "1111 0001 0010 1011 1100 0110 0101 0000 1000 1100 0001 1110 1111 1101 0110 1010 "
         "1100 1001 1001 0001 1101 1100 0010 1101 0000 0110 1100 0000 1001 0000 0001 110").replace(" ", "")
PN63 = "1110 0100 1011 0111 0110 0110 1010 1111 1100 0001 0000 1100 0101 0011 1101 000".replace(" ", "")
VSB_MODE_8VSB = "000010100101111101011010"   # Table 5.3: 8 VSB (trellis coded)


def lfsr(lower_exponents, degree, preload, n):
    """Bits from a shift register (A/53 Figure 5.10): shift right, output the last stage; the
    feedback XORs stage (degree − 1 − e) for each lower exponent e of the generator (with 0)."""
    reg = [int(c) for c in preload]
    taps = [degree - 1 - e for e in lower_exponents]
    out = []
    for _ in range(n):
        out.append(reg[-1])
        fb = 0
        for t in taps:
            fb ^= reg[t]
        reg = [fb] + reg[:-1]
    return "".join(map(str, out))


def _levels(bits):
    return [5.0 if b == "1" else -5.0 for b in bits]


def field_sync_levels(middle_inverted=False, rng=None):
    """All 832 symbol levels of a Data Field Sync segment (no pilot). The reserved and precode
    symbols are random when rng is given (as data would be), else zero (unknown)."""
    mid = "".join("1" if b == "0" else "0" for b in PN63) if middle_inverted else PN63
    known = _levels(SEGMENT_SYNC + PN511 + PN63) + _levels(mid) + _levels(PN63 + VSB_MODE_8VSB)
    rest = SEGMENT_SYMBOLS - len(known)                         # 92 reserved + 12 precode
    if rng is None:
        return known + [0.0] * rest
    reserved = _levels("".join(rng.choice(["0", "1"], size=rest - 12)))
    return known + reserved + list(rng.choice([-7.0, -5.0, -3.0, -1.0, 1.0, 3.0, 5.0, 7.0], size=12))


def template_levels():
    """The known part of the field sync for the template: the middle PN63 and the unknown
    symbols are zero."""
    lv = field_sync_levels()
    a = 4 + 511
    lv[a + 63:a + 126] = [0.0] * 63
    return lv


def _rrc_mask(f, nyquist, alpha):
    """Root-raised cosine amplitude response at frequencies f (Hz)."""
    af = np.abs(f)
    lo, hi = (1 - alpha) * nyquist, (1 + alpha) * nyquist
    h = np.zeros_like(af)
    h[af <= lo] = 1.0
    mid = (af > lo) & (af < hi)
    h[mid] = np.sqrt(0.5 * (1 + np.cos(math.pi * (af[mid] - lo) / (hi - lo))))
    return h


def passband_mask(f, rate):
    """The SDR passband model: flat to PASS_FLAT × Nyquist, raised-cosine to zero at Nyquist."""
    af, ny = np.abs(f), rate / 2
    lo = PASS_FLAT * ny
    m = np.zeros_like(af)
    m[af <= lo] = 1.0
    mid = (af > lo) & (af < ny)
    m[mid] = 0.5 * (1 + np.cos(math.pi * (af[mid] - lo) / (ny - lo)))
    return m


def vsb_baseband(levels, pilot=True):
    """Complex baseband (centred on the channel) at OS × SR from symbol levels: (x, rate).
    Sample OS·k is symbol k's instant."""
    a = np.asarray(levels, dtype=float) + (PILOT if pilot else 0.0)
    k = np.arange(len(a))
    b = a * np.exp(-0.5j * math.pi * k)                         # a_k (−j)^k
    rate = OS * SR
    n = len(a) * OS
    x = np.zeros(n, dtype=complex)
    x[::OS] = b
    nfft = 1 << (n - 1).bit_length()
    f = np.fft.fftfreq(nfft, 1 / rate)
    X = np.fft.fft(x, nfft) * _rrc_mask(f, SR / 4, ALPHA)
    return np.fft.ifft(X)[:n], rate


def shift_and_limit(x, rate, shift_hz, out_rate):
    """Shift x (complex, at rate) by shift_hz and apply the capture's passband model."""
    n = len(x)
    t = np.arange(n) / rate
    y = x * np.exp(2j * math.pi * shift_hz * t)
    nfft = 1 << (n - 1).bit_length()
    f = np.fft.fftfreq(nfft, 1 / rate)
    return np.fft.ifft(np.fft.fft(y, nfft) * passband_mask(f, out_rate))[:n]


def resample(x, rate, times_s, half_taps=16):
    """x (sampled at rate, x[0] at t = 0) at the given times by windowed-sinc interpolation;
    zero outside x. x must be band-limited well inside rate / 2."""
    p = np.asarray(times_s, dtype=float) * rate
    base = np.floor(p).astype(np.int64)
    out = np.zeros(len(p), dtype=complex)
    for j in range(-half_taps + 1, half_taps + 1):
        idx = base + j
        d = p - idx
        w = np.sinc(d) * (0.5 + 0.5 * np.cos(math.pi * d / half_taps))
        ok = (idx >= 0) & (idx < len(x))
        out[ok] += w[ok] * x[idx[ok]]
    return out


def band_limited(x, rate, half_bw_hz):
    """x low-pass filtered to ±half_bw_hz (raised-cosine edge over the last 20 %)."""
    n = len(x)
    nfft = 1 << (n - 1).bit_length()
    f = np.abs(np.fft.fftfreq(nfft, 1 / rate))
    lo = 0.8 * half_bw_hz
    m = np.where(f <= lo, 1.0, np.where(f >= half_bw_hz, 0.0, 0.5 * (1 + np.cos(math.pi * (f - lo) / (half_bw_hz - lo)))))
    return np.fft.ifft(np.fft.fft(x, nfft) * m)[:n]


def rms_bandwidth(t):
    """Centred RMS bandwidth of a sampled template, radians per sample."""
    t = np.asarray(t, dtype=complex)
    T = np.fft.fft(t, 4 * len(t))
    w = np.fft.fftfreq(len(T)) * 2 * math.pi
    p = np.abs(T) ** 2
    e = p.sum()
    if e <= 0:
        return 0.0
    mean = (w * p).sum() / e
    return float(math.sqrt(((w - mean) ** 2 * p).sum() / e))


def mainlobe_samples(t):
    """Half-power half-width of a template's autocorrelation, samples."""
    t = np.asarray(t, dtype=complex)
    ac = np.abs(np.correlate(t, t, "full"))
    mid = len(t) - 1
    half = ac[mid] / math.sqrt(2)
    k = 1
    while mid + k < len(ac) and ac[mid + k] > half:
        k += 1
    return k


class AtscFieldSync:
    """The ATSC field sync segment on one channel (centre frequency, Hz)."""
    kind = "atsc_field_sync"
    PAD_SYMBOLS = 64                     # zero symbols each side, for the pulse tails

    def __init__(self, channel_hz):
        self.channel_hz = float(channel_hz)
        self._cache = {}

    def template(self, cap):
        """(complex template at the capture's rate, lead_s): lead_s is the time from the template's
        first sample to the first segment-sync symbol, the instant the arrival refers to."""
        key = (round(cap.rate, 3), round(cap.tune_hz, 3))
        if key not in self._cache:
            pad = self.PAD_SYMBOLS
            lv = [0.0] * pad + template_levels()[:4 + 511 + 63 * 3 + 24] + [0.0] * pad
            x, rate = vsb_baseband(lv, pilot=False)
            x = shift_and_limit(x, rate, self.channel_hz - cap.tune_hz, cap.rate)
            lead = pad / SR
            n = math.floor((len(lv) / SR) * cap.rate)
            tmpl = resample(x, rate, np.arange(n) / cap.rate)
            self._cache[key] = (tmpl, lead)
        return self._cache[key]


class FmReference:
    """A segment of a reference capture, isolated around one FM station, as a template for another
    capture. Built by check.py from capture A: `source` is (Capture, start index, samples)."""
    kind = "fm_reference"

    def __init__(self, channel_hz, ref_cap, start_index, count):
        self.channel_hz = float(channel_hz)
        self.ref, self.start, self.count = ref_cap, int(start_index), int(count)
        seg = ref_cap.samples[self.start:self.start + self.count]
        # Bring the station to 0 Hz in the reference's own frame, then keep ±100 kHz.
        t = np.arange(len(seg)) / ref_cap.rate
        base = seg * np.exp(-2j * math.pi * (self.channel_hz - ref_cap.tune_hz) * t)
        self.base = band_limited(base, ref_cap.rate, FM_HALF_BW_HZ)
        self.duration_s = len(seg) / ref_cap.rate
        self._cache = {}

    def template(self, cap):
        """(template at cap's rate and offset, lead 0): the template's first sample is the instant
        of the reference's sample `start`."""
        key = (round(cap.rate, 3), round(cap.tune_hz, 3))
        if key not in self._cache:
            n = math.floor(self.duration_s * cap.rate)
            times = np.arange(n) / cap.rate
            y = resample(self.base, self.ref.rate, times)
            y = y * np.exp(2j * math.pi * (self.channel_hz - cap.tune_hz) * times)
            self._cache[key] = (y, 0.0)
        return self._cache[key]


def from_spec(spec, channel_hz):
    """A known waveform from its description (fm_reference is built by the check from capture A)."""
    kind = (spec or {}).get("kind")
    if kind == "atsc_field_sync":
        return AtscFieldSync(channel_hz)
    raise ValueError(f"waveform {spec!r}: atsc_field_sync, or fm_reference (TDOA modes only)")


# ----- synthetic emissions (synth.py) -----

def atsc_stream(rng, n_fields_symbols, field_sync_at, first_middle_inverted=False):
    """Symbol levels of an 8-VSB stream: random 8-level data, a segment sync every 832 symbols,
    a field sync segment at symbol index field_sync_at (and every field after it)."""
    data = rng.choice([-7.0, -5.0, -3.0, -1.0, 1.0, 3.0, 5.0, 7.0], size=n_fields_symbols)
    seg0 = field_sync_at % SEGMENT_SYMBOLS
    for s in range(seg0, n_fields_symbols, SEGMENT_SYMBOLS):
        data[s:s + 4] = [5.0, -5.0, -5.0, 5.0][:max(0, min(4, n_fields_symbols - s))]
    k, inv = field_sync_at, first_middle_inverted
    while k < n_fields_symbols:
        fs = field_sync_levels(inv, rng)
        m = min(SEGMENT_SYMBOLS, n_fields_symbols - k)
        data[k:k + m] = fs[:m]
        k += FIELD_SEGMENTS * SEGMENT_SYMBOLS
        inv = not inv
    return data


def fm_emission(rng, duration_s, rate=1.2e6, rms_dev_hz=22e3):
    """A synthetic FM broadcast at complex baseband (station at 0 Hz), (x, rate): program audio
    as band-limited noise (mono 50 Hz-15 kHz, a stereo difference on a 38 kHz DSB carrier) plus a
    19 kHz pilot at 9 % of 75 kHz. Not real program content."""
    n = int(math.ceil(duration_s * rate))
    nfft = 1 << (n - 1).bit_length()
    f = np.abs(np.fft.rfftfreq(nfft, 1 / rate))
    band = ((f >= 50) & (f <= 15e3)).astype(float)

    def audio():
        spec = (rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))) * band
        a = np.fft.irfft(spec, nfft)[:n]
        return a / (a.std() or 1.0)

    t = np.arange(n) / rate
    m = audio() + 0.6 * audio() * np.cos(2 * math.pi * 38e3 * t)
    m = m / m.std() * rms_dev_hz + 0.09 * 75e3 * np.cos(2 * math.pi * 19e3 * t)
    phase = 2 * math.pi * np.cumsum(m) / rate
    return np.exp(1j * phase), rate
