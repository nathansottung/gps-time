"""The password gate in front of the web SDR (OpenWebRX+), docs/deploy/websdr.md.

OpenWebRX+ protects its settings with a login but not its listening page. The gate is what
the LAN reaches (port 8073 by default): it asks for HTTP Basic credentials on every new
connection, and only a connection that passed is joined to OpenWebRX+ on 127.0.0.1:8074.
After the first request the bytes are passed through unchanged, so OpenWebRX+'s WebSockets
(audio, waterfall) work. Later requests on a connection that already passed are not asked
again; a browser sends the credentials on every request anyway.

Fails closed: with no password file every request gets 503 and nothing reaches OpenWebRX+.
Wrong credentials are logged (address only, never the password) and back off per address.
The password is kept as a salted PBKDF2-SHA256 hash, never in clear.

  sudo python3 -m gps_time_pi.websdr_gate passwd [--user radio]   set the password (asks twice)
  python3 -m gps_time_pi.websdr_gate serve                        run the gate (the systemd unit)
  python3 -m gps_time_pi.websdr_gate check http://<station>:8073/ [--user radio]
      from any LAN machine: the gate refuses no credentials, takes the password (asked), and
      OpenWebRX+ answers its WebSocket handshake through it; then it disconnects

Basic credentials are only base64 on the wire: the gate is for the LAN, which the unit
enforces (IPAddressAllow= private ranges only). Stdlib only, no compiler needed.
"""
import argparse
import asyncio
import base64
import getpass
import hashlib
import hmac
import logging
import os
import secrets
import socket
import struct
import sys
import time
from urllib.parse import urlparse

log = logging.getLogger("gps_time_pi.websdr_gate")

PASSWORD_FILE = "/etc/gps-time-websdr/password"
LISTEN_PORT = 8073
UPSTREAM = ("127.0.0.1", 8074)
ITERATIONS = 200_000
MAX_HEAD = 32 * 1024
HEAD_TIMEOUT_S = 15.0
CACHE_S = 900.0            # a checked Authorization header is trusted again for 15 min
MAX_CONNECTIONS = 64
FAIL_WINDOW_S = 300.0
FAIL_LIMIT = 5             # failures per address in the window before it has to wait
BACKOFF_S = 60.0
REALM = "GPS Time web SDR"
NO_PASSWORD = ("The web SDR has no password yet, so it is closed.\n"
               "On the station: sudo /opt/gps-time-pi/venv/bin/python -m gps_time_pi.websdr_gate passwd\n")


# ── the password file ──────────────────────────────────────────────────────

def hash_password(password, salt=None, iterations=ITERATIONS):
    salt = salt if salt is not None else secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return (f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}"
            f"${base64.b64encode(dk).decode()}")


def parse_line(line):
    """'user:pbkdf2_sha256$iter$salt$hash' -> (user, iterations, salt, hash); None if malformed."""
    user, sep, rest = line.strip().partition(":")
    parts = rest.split("$")
    if not sep or not user or len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return None
    try:
        iters = int(parts[1])
        salt, dk = base64.b64decode(parts[2], validate=True), base64.b64decode(parts[3], validate=True)
    except ValueError:
        return None
    if not (1000 <= iters <= 10_000_000) or len(salt) < 8 or len(dk) != 32:
        return None
    return user, iters, salt, dk


def load(path):
    """The stored credential, or None (missing, unreadable or malformed: the gate stays closed)."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    return parse_line(line)
    except OSError:
        return None
    return None


def check(cred, user, password):
    if cred is None:
        return False
    c_user, iters, salt, dk = cred
    got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    # Both comparisons always run, so the time doesn't say which one failed.
    ok_user = hmac.compare_digest(c_user.encode("utf-8"), user.encode("utf-8"))
    ok_pass = hmac.compare_digest(dk, got)
    return ok_user and ok_pass


def basic(header):
    """'Basic dXNlcjpwYXNz' -> (user, password); None if it isn't Basic credentials."""
    if not header:
        return None
    scheme, _, value = header.strip().partition(" ")
    if scheme.lower() != "basic":
        return None
    try:
        raw = base64.b64decode(value.strip(), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    user, sep, password = raw.partition(":")
    return (user, password) if sep else None


# ── the gate ───────────────────────────────────────────────────────────────

class Gate:
    def __init__(self, password_file=PASSWORD_FILE, upstream=UPSTREAM, clock=time.monotonic):
        self.password_file = password_file
        self.upstream = upstream
        self.clock = clock
        self._key = secrets.token_bytes(32)     # for the cache of checked headers; per process
        self._ok = {}                           # digest of a checked header -> expiry
        self._fails = {}                        # address -> [failure times]
        self._cred, self._cred_at = None, None
        self.connections = 0

    def credential(self):
        """Re-read the file at most every 10 s, so a new password applies without a restart."""
        now = self.clock()
        if self._cred_at is None or now - self._cred_at > 10.0:
            self._cred, self._cred_at = load(self.password_file), now
            self._ok.clear()
        return self._cred

    def retry_after(self, ip):
        now = self.clock()
        fails = [t for t in self._fails.get(ip, []) if now - t < FAIL_WINDOW_S]
        self._fails[ip] = fails
        if len(fails) >= FAIL_LIMIT:
            return max(0.0, fails[-1] + BACKOFF_S - now)
        return 0.0

    def decide(self, ip, auth_header):
        """(status, reason): 200 to pass the connection on, else the answer to send."""
        cred = self.credential()
        if cred is None:
            return 503, "no password set"
        wait = self.retry_after(ip)
        if wait > 0:
            return 429, f"retry in {int(wait) + 1} s"
        if auth_header:
            digest = hmac.new(self._key, auth_header.encode("latin-1", "replace"), hashlib.sha256).digest()
            exp = self._ok.get(digest)
            if exp is not None and exp > self.clock():
                return 200, "ok"
            pair = basic(auth_header)
            if pair and check(cred, *pair):
                if len(self._ok) > 256:
                    self._ok.clear()
                self._ok[digest] = self.clock() + CACHE_S
                return 200, "ok"
            self._fails.setdefault(ip, []).append(self.clock())
            log.warning("web SDR: wrong credentials from %s", ip)
            return 401, "wrong credentials"
        return 401, "credentials needed"


def split_head(data):
    """(head lines, rest) of an HTTP request head ending in CRLFCRLF."""
    head, _, rest = data.partition(b"\r\n\r\n")
    return head.decode("latin-1").split("\r\n"), rest


def strip_auth(lines):
    """The request head without Authorization: OpenWebRX+ never sees the password."""
    return [ln for ln in lines if not ln.lower().startswith("authorization:")]


def answer(status, reason):
    text = {401: "Credentials needed for the station's web SDR.\n", 429: "Too many wrong attempts; try again later.\n",
            503: NO_PASSWORD, 502: "The web SDR is not answering yet; reload in a few seconds.\n",
            400: "Bad request.\n"}.get(status, reason + "\n").encode()
    names = {400: "Bad Request", 401: "Unauthorized", 429: "Too Many Requests", 502: "Bad Gateway",
             503: "Service Unavailable"}
    head = [f"HTTP/1.1 {status} {names.get(status, 'Error')}", "Content-Type: text/plain; charset=utf-8",
            f"Content-Length: {len(text)}", "Cache-Control: no-store", "Connection: close"]
    if status == 401:
        head.append(f'WWW-Authenticate: Basic realm="{REALM}", charset="UTF-8"')
    if status == 429:
        head.append("Retry-After: 60")
    return ("\r\n".join(head) + "\r\n\r\n").encode() + text


async def _pipe(reader, writer):
    try:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        try:
            writer.close()
        except Exception:  # noqa: BLE001
            pass


async def handle(gate, reader, writer):
    peer = writer.get_extra_info("peername") or ("?",)
    ip = peer[0]
    gate.connections += 1
    try:
        if gate.connections > MAX_CONNECTIONS:
            return
        try:
            data = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), HEAD_TIMEOUT_S)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError):
            return
        lines, rest = split_head(data)
        if not lines or len(lines[0].split(" ")) != 3:
            writer.write(answer(400, "bad request"))
            await writer.drain()
            return
        auth = next((ln.split(":", 1)[1].strip() for ln in lines[1:] if ln.lower().startswith("authorization:")), None)
        status, reason = gate.decide(ip, auth)
        if status != 200:
            writer.write(answer(status, reason))
            await writer.drain()
            return
        try:
            up_r, up_w = await asyncio.wait_for(asyncio.open_connection(*gate.upstream), 5.0)
        except (OSError, asyncio.TimeoutError):
            writer.write(answer(502, "upstream"))
            await writer.drain()
            return
        up_w.write(("\r\n".join(strip_auth(lines)) + "\r\n\r\n").encode("latin-1") + rest)
        await up_w.drain()
        await asyncio.gather(_pipe(reader, up_w), _pipe(up_r, writer))
    finally:
        gate.connections -= 1
        try:
            writer.close()
        except Exception:  # noqa: BLE001
            pass


async def serve(port, password_file, upstream):
    gate = Gate(password_file, upstream)
    if gate.credential() is None:
        log.warning("web SDR: no password in %s; every request gets 503 until one is set", password_file)
    server = await asyncio.start_server(lambda r, w: handle(gate, r, w), host=None, port=port, limit=MAX_HEAD)
    async with server:
        await server.serve_forever()


# ── a minimal WebSocket client (RFC 6455), for `check` and the tests ───────

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OWRX_HELLO = "SERVER DE CLIENT client=openwebrx.js type=receiver"
OWRX_REPLY = "CLIENT DE SERVER"


def ws_accept(key):
    return base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()


def ws_request(host, path, key, authorization=None):
    lines = [f"GET {path} HTTP/1.1", f"Host: {host}", "Upgrade: websocket", "Connection: Upgrade",
             f"Sec-WebSocket-Key: {key}", "Sec-WebSocket-Version: 13"]
    if authorization:
        lines.append(f"Authorization: {authorization}")
    return ("\r\n".join(lines) + "\r\n\r\n").encode()


def ws_frame(payload, opcode=0x1, mask=True):
    """One final frame; a client's frames are masked (RFC 6455 5.3)."""
    data = payload.encode() if isinstance(payload, str) else payload
    head = bytes([0x80 | opcode])
    n = len(data)
    bit = 0x80 if mask else 0
    if n < 126:
        head += bytes([bit | n])
    elif n < 65536:
        head += bytes([bit | 126]) + struct.pack("!H", n)
    else:
        head += bytes([bit | 127]) + struct.pack("!Q", n)
    if not mask:
        return head + data
    key = secrets.token_bytes(4)
    return head + key + bytes(b ^ key[i % 4] for i, b in enumerate(data))


def ws_read_frame(read):
    """(opcode, payload) from read(n), which returns exactly n bytes."""
    b0, b1 = read(2)
    n = b1 & 0x7F
    if n == 126:
        n = struct.unpack("!H", read(2))[0]
    elif n == 127:
        n = struct.unpack("!Q", read(8))[0]
    key = read(4) if b1 & 0x80 else None
    data = read(n)
    if key:
        data = bytes(b ^ key[i % 4] for i, b in enumerate(data))
    return b0 & 0x0F, data


def check_station(url, user, password, timeout=10.0):
    """[(step, ok, detail)] for the web SDR at url, through the gate. It changes nothing: it
    connects as one listener, says hello and disconnects (OpenWebRX+ may open the dongle briefly)."""
    u = urlparse(url if "://" in url else "http://" + url)
    host, port = u.hostname, u.port or LISTEN_PORT
    hostport = f"{host}:{port}"
    steps = []

    def connect():
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.settimeout(timeout)
        return sock

    def read_head(sock):
        buf = b""
        while b"\r\n\r\n" not in buf and len(buf) <= MAX_HEAD:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
        head, _, rest = buf.partition(b"\r\n\r\n")
        return head.decode("latin-1").split("\r\n"), rest

    key = base64.b64encode(secrets.token_bytes(16)).decode()
    try:
        with connect() as sock:
            sock.sendall(ws_request(hostport, "/ws/", key))
            lines, _ = read_head(sock)
    except OSError as e:
        return [("reach the gate", False, f"{hostport}: {e}")]
    status = lines[0] if lines else ""
    if " 503 " in status + " ":
        return [("password set on the station", False, "the gate has no password yet (websdr_gate passwd)")]
    steps.append(("no credentials refused", " 401 " in status + " ", status or "no answer"))
    auth = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
    try:
        with connect() as sock:
            sock.sendall(ws_request(hostport, "/ws/", key, auth))
            lines, rest = read_head(sock)
            status = lines[0] if lines else ""
            accept = next((ln.split(":", 1)[1].strip() for ln in lines[1:]
                           if ln.lower().startswith("sec-websocket-accept:")), None)
            upgraded = " 101 " in status + " " and accept == ws_accept(key)
            steps.append(("WebSocket upgrade through the gate", upgraded,
                          status if upgraded or not accept else f"{status}; wrong Sec-WebSocket-Accept"))
            if not upgraded:
                return steps
            buf = bytearray(rest)

            def read(n):
                while len(buf) < n:
                    chunk = sock.recv(65536)
                    if not chunk:
                        raise ConnectionError("closed by the server")
                    buf.extend(chunk)
                out = bytes(buf[:n])
                del buf[:n]
                return out
            sock.sendall(ws_frame(OWRX_HELLO))
            reply = None
            for _ in range(20):                       # binary frames may come before the reply
                op, data = ws_read_frame(read)
                if op == 0x1:
                    reply = data.decode("utf-8", "replace")
                    break
                if op == 0x8:
                    break
            ok = bool(reply and reply.startswith(OWRX_REPLY))
            steps.append(("OpenWebRX+ handshake", ok, reply[:120] if reply else "no text reply"))
            try:                                      # a clean close: send ours, wait for theirs
                sock.sendall(ws_frame(struct.pack("!H", 1000), opcode=0x8))
                for _ in range(50):
                    if ws_read_frame(read)[0] == 0x8:
                        break
            except (OSError, ConnectionError, ValueError):
                pass
    except (OSError, ConnectionError, ValueError) as e:
        steps.append(("WebSocket session", False, str(e)))
    return steps


def set_password(path, user):
    if not user or ":" in user or len(user) > 64:
        print("The user name must be 1 to 64 characters, without ':'.", file=sys.stderr)
        return 1
    pw = getpass.getpass("New web SDR password: ")
    if len(pw) < 10:
        print("Use at least 10 characters. Nothing changed.", file=sys.stderr)
        return 1
    if getpass.getpass("Again: ") != pw:
        print("The two entries differ. Nothing changed.", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("# The web SDR's login (gps_time_pi/websdr_gate.py): user and salted PBKDF2-SHA256 hash.\n")
        f.write(f"{user}:{hash_password(pw)}\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    print(f"Saved for user '{user}' in {path}. The gate picks it up within 10 s.")
    return 0


def main(argv=None):
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Password gate for the station's web SDR.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("passwd", help="set the web SDR password (asks twice)")
    p.add_argument("--user", default="radio")
    p.add_argument("--file", default=PASSWORD_FILE)
    s = sub.add_parser("serve", help="run the gate")
    s.add_argument("--port", type=int, default=int(os.environ.get("GTP_WEBSDR_PORT", LISTEN_PORT)))
    s.add_argument("--file", default=os.environ.get("GTP_WEBSDR_PASSWORD_FILE", PASSWORD_FILE))
    s.add_argument("--upstream-port", type=int, default=UPSTREAM[1])
    c = sub.add_parser("check", help="check the web SDR through the gate from a LAN machine (asks the password)")
    c.add_argument("url", help="e.g. http://192.0.2.10:8073/")
    c.add_argument("--user", default="radio")
    a = ap.parse_args(argv)
    if a.cmd == "passwd":
        return set_password(a.file, a.user)
    if a.cmd == "check":
        steps = check_station(a.url, a.user, getpass.getpass(f"Web SDR password for {a.user}: "))
        for step, ok, detail in steps:
            print(f"[{'OK' if ok else 'NO'}] {step}: {detail}")
        return 0 if steps and all(ok for _, ok, _ in steps) else 1
    asyncio.run(serve(a.port, a.file, ("127.0.0.1", a.upstream_port)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
