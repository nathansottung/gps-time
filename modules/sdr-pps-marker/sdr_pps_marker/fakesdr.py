"""A stand-in for rtl_tcp: serves a synthetic RTL-SDR stream with PPS markers (tests, desktop trials).

    python -m sdr_pps_marker.fakesdr --port 1234        # then point the module's rtl_tcp config at it

It speaks rtl_tcp's protocol (rtltcp.py): the 12-byte header, 5-byte commands (recorded), then
cu8 samples. Each connection is a fresh stream, as with rtl_tcp: sample 0 of a connection is at
true UTC `start_utc` + the connection's offset. The stream is noise, a spike for each PPS rising
edge on the UTC second and its falling edge pulse_width_s later, a sample clock off by ppm,
and optional dropped blocks. SYNTHETIC: not a recording.

`true_utc(connection, sample)` gives the truth for tests; `clock_for(client)` gives a host clock
that reads the true time of the next byte the client will read (plus host_clock_error_s), i.e.
no USB or network delay.
"""

import argparse
import socket
import struct
import threading
import time

import numpy as np

from .fast import as_cu8
from .synth import SPIKE_SIGMA

SCALE = 100.0


class Stream:
    """Synthetic samples of one connection, made on demand in blocks."""

    def __init__(self, fs, start_utc, *, ppm=0.0, noise_rms=0.05, marker_amp=1.0, pulse_width_s=0.1,
                 drops=(), seed=1, tone_amp=0.0, tone_hz=0.0):
        self.fs, self.start, self.ppm = float(fs), float(start_utc), float(ppm)
        self.rate = self.fs * (1 + self.ppm * 1e-6)
        self.noise, self.amp, self.width = noise_rms, marker_amp, pulse_width_s
        self.drops = sorted(drops)                    # (raw sample index, count)
        self.rng = np.random.default_rng(seed)
        self.tone_amp, self.tone_hz = tone_amp, tone_hz
        self.raw_pos = 0                              # next raw (undropped) sample
        self.sent = 0                                 # samples sent

    def true_utc_raw(self, raw_index):
        return self.start + raw_index / self.rate

    def _next_drop(self, pos):
        """(start, end) of the first drop that ends after pos, or None."""
        for d0, dn in self.drops:
            if d0 + dn > pos:
                return d0, d0 + dn
        return None

    def raw_index(self, out_index):
        """Raw sample index of an output sample (undoing the drops)."""
        r = out_index
        for d0, dn in self.drops:
            if r >= d0:
                r += dn
        return r

    def true_utc(self, out_index):
        return self.true_utc_raw(self.raw_index(out_index))

    def _make(self, lo, hi):
        k = hi - lo
        idx = np.arange(lo, hi)
        x = self.noise / np.sqrt(2) * (self.rng.standard_normal(k) + 1j * self.rng.standard_normal(k))
        if self.tone_amp:
            x = x + self.tone_amp * np.exp(2j * np.pi * self.tone_hz * idx / self.rate)
        t0, t1 = self.true_utc_raw(lo), self.true_utc_raw(hi)
        for sec in range(int(np.floor(t0)) - 1, int(np.ceil(t1)) + 1):
            for edge in (sec, sec + self.width):
                p = (edge - self.start) * self.rate            # raw position of the edge
                c = int(round(p))
                if lo - 6 <= c < hi + 6:
                    j = np.arange(max(lo, c - 5), min(hi, c + 6))
                    if len(j):
                        ph = np.exp(2j * np.pi * ((sec * 0.618) % 1))
                        x[j - lo] += self.amp * ph * np.exp(-0.5 * ((j - p) / SPIKE_SIGMA) ** 2)
        return x

    def block(self, n):
        """The next n samples that survive the drops, as complex."""
        out, need = [], n
        while need > 0:
            d = self._next_drop(self.raw_pos)
            if d and d[0] <= self.raw_pos:
                self.raw_pos = d[1]
                continue
            hi = self.raw_pos + need if d is None else min(self.raw_pos + need, d[0])
            out.append(self._make(self.raw_pos, hi))
            need -= hi - self.raw_pos
            self.raw_pos = hi
        self.sent += n
        return np.concatenate(out) if len(out) > 1 else out[0]


class FakeRtlTcp:
    """A threaded rtl_tcp stand-in on 127.0.0.1 (port 0: any free port)."""

    def __init__(self, port=0, fs=2.4e6, start_utc=1_793_026_800.3, host_clock_error_s=0.01, chunk=1 << 15,
                 pace=0.0, **stream_kw):
        """start_utc None: each connection's stream starts at the host's time of the connection (a
        desktop trial with pace=1); a number: connection k starts at start_utc + 10 k (tests)."""
        self.fs, self.start_utc, self.err = fs, start_utc, host_clock_error_s
        self.chunk, self.pace, self.kw = chunk, pace, stream_kw
        self.commands = []                 # (connection, opcode, value)
        self.streams = []
        self.srv = socket.create_server(("127.0.0.1", port))
        self.port = self.srv.getsockname()[1]
        self._stop = threading.Event()
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        self.srv.settimeout(0.2)
        k = 0
        while not self._stop.is_set():
            try:
                conn, _ = self.srv.accept()
            except (socket.timeout, OSError):
                continue
            # each connection starts 10 s after the previous one's start, like a later dwell
            start = time.time() if self.start_utc is None else self.start_utc + 10.0 * k
            st = Stream(self.fs, start, seed=k + 1, **self.kw)
            self.streams.append(st)
            threading.Thread(target=self._serve, args=(conn, k, st), daemon=True).start()
            k += 1

    def _serve(self, conn, k, st):
        def commands():
            buf = b""
            try:
                while True:
                    d = conn.recv(64)
                    if not d:
                        return
                    buf += d
                    while len(buf) >= 5:
                        op, val = struct.unpack(">BI", buf[:5])
                        self.commands.append((k, op, val))
                        buf = buf[5:]
            except OSError:
                return
        threading.Thread(target=commands, daemon=True).start()
        try:
            conn.sendall(b"RTL0" + struct.pack(">II", 5, 29))
            while not self._stop.is_set():
                data, _ = as_cu8(st.block(self.chunk), SCALE)
                conn.sendall(data)
                if self.pace:
                    time.sleep(self.chunk / self.fs / self.pace)
        except OSError:
            pass
        finally:
            conn.close()

    def clock_for(self, client_box):
        """A host clock for the source: the true UTC of the next byte the current client reads.
        client_box: a list whose last item is the client being used."""
        def clock():
            if not client_box or not self.streams:
                return self.start_utc or time.time()
            c, st = client_box[-1], self.streams[len(client_box) - 1]
            return st.true_utc(c.bytes_read // 2) + self.err
        return clock

    def close(self):
        self._stop.set()
        self.srv.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=1234)
    ap.add_argument("--rate", type=float, default=2.4e6)
    ap.add_argument("--ppm", type=float, default=12.0)
    a = ap.parse_args(argv)
    srv = FakeRtlTcp(a.port, a.rate, start_utc=None, pace=1.0, ppm=a.ppm)
    print(f"fake rtl_tcp (SYNTHETIC) on 127.0.0.1:{srv.port}, {a.rate:g} S/s, clock {a.ppm:+g} ppm; Ctrl-C stops")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        srv.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
