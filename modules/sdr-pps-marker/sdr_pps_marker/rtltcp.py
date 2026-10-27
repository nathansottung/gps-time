"""A minimal client for rtl_tcp, the RTL-SDR's own sample server (osmocom rtl-sdr, rtl_tcp.c).

Why rtl_tcp: a module may not start processes or load native libraries (the permission guard),
so it can't run rtl_sdr or use librtlsdr through ctypes. rtl_tcp runs as its own service
(system/gps-time-rtl-tcp.service, installed but not enabled), owns the USB device, and serves
samples on 127.0.0.1. The module only connects. A systemd drop-in limits the module service's
network to localhost (README).

The protocol, from rtl_tcp.c:
  - on connect the server sends 12 bytes: "RTL0", then the tuner type and the number of gain
    steps, each a big-endian uint32;
  - then unsigned 8-bit samples, interleaved I and Q, without end;
  - commands are 5 bytes: an opcode, then a big-endian uint32 parameter. 0x01 centre frequency
    (Hz), 0x02 sample rate (Hz), 0x03 gain mode (0 automatic, 1 manual), 0x04 gain (tenths of a
    dB), 0x05 frequency correction (ppm), 0x08 RTL AGC (0/1), 0x0e bias tee (0/1).
"""

import socket
import struct

SET_FREQ, SET_RATE, SET_GAIN_MODE, SET_GAIN, SET_PPM, SET_AGC, SET_BIAS_TEE = 0x01, 0x02, 0x03, 0x04, 0x05, 0x08, 0x0E
TUNERS = {0: "unknown", 1: "E4000", 2: "FC0012", 3: "FC0013", 4: "FC2580", 5: "R820T", 6: "R828D"}


class RtlTcpError(Exception):
    pass


class RtlTcp:
    def __init__(self, host="127.0.0.1", port=1234, timeout_s=5.0, connect=socket.create_connection):
        try:
            self.sock = connect((host, int(port)), timeout=timeout_s)
        except OSError as e:
            raise RtlTcpError(f"rtl_tcp at {host}:{port} is not reachable: {e}") from e
        head = self.read(12)
        if head[:4] != b"RTL0":
            self.close()
            raise RtlTcpError(f"not an rtl_tcp server (header {head[:4]!r})")
        tuner, gains = struct.unpack(">II", head[4:])
        self.bytes_read = 0                 # samples bytes since the header
        self.tuner = TUNERS.get(tuner, f"type {tuner}")
        self.gain_steps = gains

    def command(self, op, value):
        self.sock.sendall(struct.pack(">BI", op, int(value) & 0xFFFFFFFF))

    def tune(self, center_hz, sample_rate_hz=None, gain_tenth_db=None, ppm=None):
        if sample_rate_hz is not None:
            self.command(SET_RATE, round(sample_rate_hz))
        self.command(SET_FREQ, round(center_hz))
        if ppm is not None:
            self.command(SET_PPM, int(ppm))
        if gain_tenth_db is None:
            self.command(SET_GAIN_MODE, 0)
        else:
            self.command(SET_GAIN_MODE, 1)
            self.command(SET_GAIN, int(gain_tenth_db))

    def read(self, n):
        """Exactly n bytes, or RtlTcpError."""
        buf = bytearray(n)
        view = memoryview(buf)
        got = 0
        while got < n:
            try:
                k = self.sock.recv_into(view[got:], n - got)
            except OSError as e:
                raise RtlTcpError(f"rtl_tcp read failed: {e}") from e
            if k == 0:
                raise RtlTcpError("rtl_tcp closed the connection")
            got += k
        if hasattr(self, "bytes_read"):
            self.bytes_read += n
        return bytes(buf)

    def skip(self, n, chunk=1 << 20):
        while n > 0:
            k = min(chunk, n)
            self.read(k)
            n -= k

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass
