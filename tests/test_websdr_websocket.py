"""The web SDR's WebSockets through the password gate (owner's rc.3 list).

OpenWebRX+ streams audio and the waterfall over a WebSocket (/ws/). The gate checks the first
request of each connection and then pipes bytes both ways, so the upgrade, masked client frames,
large server frames and the close have to pass through it unchanged. A small fake OpenWebRX+
(the real handshake text; RFC 6455 framing) runs behind the real gate on the loopback, and the
gate's own `check` client (check_station) drives it. It also guards the gate's password check: an
earlier draft shadowed websdr_gate.check, and every login crashed. No OpenWebRX+, dongle or network is needed.
"""
import asyncio
import base64
import os
import secrets
import shutil
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from gps_time_pi import websdr_gate as gate

PASSWORD = "correct horse battery"
BIG = bytes(range(256)) * 300            # 76,800 bytes: a 64-bit length, like a waterfall line burst


class FakeOpenWebRX:
    """Answers the upgrade, then the OpenWebRX+ hello, then echoes frames; records what it saw."""

    def __init__(self):
        self.heads, self.received = [], []

    async def handle(self, reader, writer):
        head = await reader.readuntil(b"\r\n\r\n")
        self.heads.append(head)
        lines = head.decode("latin-1").split("\r\n")
        key = next(ln.split(":", 1)[1].strip() for ln in lines if ln.lower().startswith("sec-websocket-key:"))
        writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {gate.ws_accept(key)}\r\n\r\n").encode())
        await writer.drain()

        async def read(n):
            return await reader.readexactly(n)
        try:
            while True:
                op, data = await self.read_frame(read)
                self.received.append((op, data))
                if op == 0x8:
                    writer.write(gate.ws_frame(data, opcode=0x8, mask=False))
                    await writer.drain()
                    break
                if op == 0x1 and data.decode().startswith("SERVER DE CLIENT"):
                    writer.write(gate.ws_frame(BIG, opcode=0x2, mask=False))       # binary first, as a stream would
                    writer.write(gate.ws_frame("CLIENT DE SERVER server=openwebrx version=v1.2.x", mask=False))
                else:
                    writer.write(gate.ws_frame(data, opcode=op, mask=False))
                await writer.drain()
        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()

    @staticmethod
    async def read_frame(read):
        head = await read(2)
        n = head[1] & 0x7F
        ext = b""
        if n == 126:
            ext = await read(2)
        elif n == 127:
            ext = await read(8)
        key = await read(4) if head[1] & 0x80 else b""
        size = int.from_bytes(ext, "big") if ext else n
        body = await read(size)
        chunks = iter([head + ext + key + body])
        return gate.ws_read_frame(_Reader(next(chunks)))


class _Reader:
    def __init__(self, data):
        self.buf = bytearray(data)

    def __call__(self, n):
        out = bytes(self.buf[:n])
        del self.buf[:n]
        return out


class Rig:
    """The real gate in front of the fake, both on 127.0.0.1, in a background event loop."""

    def __init__(self, password=True):
        self.tmp = Path(tempfile.mkdtemp())
        self.pwfile = self.tmp / "password"
        self.pwfile.write_text(f"radio:{gate.hash_password(PASSWORD, iterations=1000)}\n" if password
                               else "# No password yet\n")
        self.fake = FakeOpenWebRX()
        self.loop = asyncio.new_event_loop()
        ready = threading.Event()

        async def start():
            self.up = await asyncio.start_server(self.fake.handle, "127.0.0.1", 0)
            g = gate.Gate(self.pwfile, ("127.0.0.1", self.up.sockets[0].getsockname()[1]))
            self.front = await asyncio.start_server(lambda r, w: gate.handle(g, r, w), "127.0.0.1", 0)
            self.port = self.front.sockets[0].getsockname()[1]
            ready.set()

        self.thread = threading.Thread(target=lambda: (self.loop.run_until_complete(start()), self.loop.run_forever()),
                                       daemon=True)
        self.thread.start()
        ready.wait(10)

    def close(self):
        async def stop():
            self.front.close()
            self.up.close()
        asyncio.run_coroutine_threadsafe(stop(), self.loop).result(5)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(5)
        shutil.rmtree(self.tmp, True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/"


def auth(pw=PASSWORD):
    return "Basic " + base64.b64encode(f"radio:{pw}".encode()).decode()


class TestFraming(unittest.TestCase):
    def test_accept_key_is_rfc_6455s(self):
        self.assertEqual(gate.ws_accept("dGhlIHNhbXBsZSBub25jZQ=="), "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")

    def test_frames_round_trip_at_every_length_size(self):
        for payload in (b"", b"x" * 125, b"y" * 126, b"z" * 65535, BIG):
            for mask in (True, False):
                with self.subTest(n=len(payload), mask=mask):
                    op, data = gate.ws_read_frame(_Reader(gate.ws_frame(payload, opcode=0x2, mask=mask)))
                    self.assertEqual((op, data), (0x2, payload))

    def test_client_frames_are_masked(self):
        frame = gate.ws_frame("hello")
        self.assertTrue(frame[1] & 0x80)
        self.assertNotIn(b"hello", frame)


class TestThroughTheGate(unittest.TestCase):
    def setUp(self):
        self.rig = Rig()
        self.addCleanup(self.rig.close)

    def test_check_passes_and_openwebrx_never_sees_the_password(self):
        steps = gate.check_station(self.rig.url, "radio", PASSWORD)
        self.assertEqual([(s, ok) for s, ok, _ in steps], [("no credentials refused", True),
                                                          ("WebSocket upgrade through the gate", True),
                                                          ("OpenWebRX+ handshake", True)])
        self.assertIn("server=openwebrx", steps[-1][2])
        self.assertEqual(len(self.rig.fake.heads), 1)                       # the refused one never reached it
        self.assertNotIn(b"Authorization", self.rig.fake.heads[0])
        self.assertIn(b"Upgrade: websocket", self.rig.fake.heads[0])
        self.assertEqual(self.rig.fake.received[-1][0], 0x8)                # a clean close

    def test_a_wrong_password_never_upgrades(self):
        steps = gate.check_station(self.rig.url, "radio", "guess")
        self.assertFalse(steps[-1][1])
        self.assertIn("401", steps[-1][2])
        self.assertEqual(self.rig.fake.heads, [])

    def test_frames_pass_both_ways_unchanged(self):
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        with socket.create_connection(("127.0.0.1", self.rig.port), timeout=10) as s:
            s.sendall(gate.ws_request(f"127.0.0.1:{self.rig.port}", "/ws/", key, auth()))
            buf = bytearray()
            while b"\r\n\r\n" not in buf:
                buf += s.recv(4096)
            head, _, rest = bytes(buf).partition(b"\r\n\r\n")
            self.assertTrue(head.startswith(b"HTTP/1.1 101"))
            self.assertIn(f"Sec-WebSocket-Accept: {gate.ws_accept(key)}".encode(), head)
            buf = bytearray(rest)

            def read(n):
                while len(buf) < n:
                    chunk = s.recv(65536)
                    if not chunk:
                        raise ConnectionError("closed")
                    buf.extend(chunk)
                out = bytes(buf[:n])
                del buf[:n]
                return out
            s.sendall(gate.ws_frame(gate.OWRX_HELLO))
            self.assertEqual(gate.ws_read_frame(read), (0x2, BIG))           # 76,800 bytes, in one piece
            op, text = gate.ws_read_frame(read)
            self.assertTrue(text.startswith(b"CLIENT DE SERVER"))
            # A client frame split across writes still arrives whole.
            frame = gate.ws_frame(BIG[:5000], opcode=0x2)
            s.sendall(frame[:3])
            s.sendall(frame[3:])
            self.assertEqual(gate.ws_read_frame(read), (0x2, BIG[:5000]))
            s.sendall(gate.ws_frame(b"\x03\xe8", opcode=0x8))
            self.assertEqual(gate.ws_read_frame(read)[0], 0x8)
        self.assertEqual(self.rig.fake.received[1], (0x2, BIG[:5000]))


class TestNoPassword(unittest.TestCase):
    def test_check_says_the_gate_has_no_password(self):
        rig = Rig(password=False)
        self.addCleanup(rig.close)
        steps = gate.check_station(rig.url, "radio", PASSWORD)
        self.assertEqual(steps, [("password set on the station", False,
                                  "the gate has no password yet (websdr_gate passwd)")])
        self.assertEqual(rig.fake.heads, [])


if __name__ == "__main__":
    unittest.main()
