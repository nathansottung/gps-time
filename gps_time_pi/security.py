"""Request checks for the station web server (review findings GPS-014, GPS-017).

- Host allowlist on every request: defeats DNS rebinding, where an attacker's
  domain resolves to the station and a page on that domain reads /api.
- Origin check on every POST: a browser always sends Origin on POST, so a
  cross-site form or fetch is refused. Clients without Origin (curl, scripts)
  still need the admin token.
- Admin token: state-changing actions need `Authorization: Bearer <token>`, or the sign-in
  cookie the token buys (POST /api/login): a signed, HttpOnly, SameSite=Strict cookie that lasts
  until the browser closes (at most SESSION_S) or, with "Remember this browser", REMEMBER_DAYS.
  Its key is a random file next to config.json bound to the stored token hash, so a new token
  signs every browser out, and "Sign out all browsers" (a new key) does it without one.
  Only a SHA-256 of the token is stored (GTP_ADMIN_TOKEN_FILE, default
  admin-token.sha256 next to config.json). No file means admin is disabled.
  Create or replace it with `python3 -m gps_time_pi.admin_token`.

- Failed token attempts are logged (journal via stderr; never the token or
  header) and throttled per client IP: after FREE_FAILURES misses, further
  attempts get 429 for an exponentially growing time, capped at MAX_BACKOFF_S.
- Security headers: a strict Content-Security-Policy plus nosniff,
  no-referrer and frame denial on every response (CSP_STRICT; no per-page exceptions).

Standard library only; nothing here touches timing behavior.
"""

import collections
import hashlib
import hmac
import ipaddress
import logging
import os
import socket
import threading
import time
from urllib.parse import urlsplit

log = logging.getLogger("gps_time_pi.security")

TOKEN_PREFIX = "sha256:"


def _env_list(name):
    return [x.strip().lower() for x in os.environ.get(name, "").split(",") if x.strip()]


def token_path():
    configured = os.environ.get("GTP_ADMIN_TOKEN_FILE")
    if configured:
        return configured
    cfg = os.environ.get("GTP_CONFIG", "/opt/gps-time-pi/config.json")
    return os.path.join(os.path.dirname(os.path.abspath(cfg)), "admin-token.sha256")


def hash_token(token):
    return TOKEN_PREFIX + hashlib.sha256(token.encode("utf-8")).hexdigest()


def _stored_hash():
    try:
        with open(token_path(), encoding="utf-8") as f:
            value = f.read().strip()
    except OSError:
        return None
    return value if value.startswith(TOKEN_PREFIX) and len(value) == len(TOKEN_PREFIX) + 64 else None


def admin_configured():
    """True when a valid token hash exists. Without one, admin is disabled."""
    return _stored_hash() is not None


def verify_authorization(header):
    """Check an `Authorization: Bearer <token>` header against the stored hash."""
    stored = _stored_hash()
    if stored is None or not header:
        return False
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return False
    return hmac.compare_digest(hash_token(token.strip()), stored)


# ─── sign-in sessions (the admin login page) ─────────────────────────────────

SESSION_COOKIE = "gtp_admin"
REMEMBER_DAYS = 30
SESSION_S = 12 * 3600


def session_key_path():
    configured = os.environ.get("GTP_ADMIN_SESSION_KEY")
    if configured:
        return configured
    return os.path.join(os.path.dirname(os.path.abspath(token_path())), "admin-session.key")


def _session_key(create=True):
    path = session_key_path()
    try:
        with open(path, encoding="utf-8") as f:
            key = bytes.fromhex(f.read().strip())
        if len(key) >= 32:
            return key
    except (OSError, ValueError):
        pass
    return rotate_session_key() if create else None


def rotate_session_key():
    """A new random session key, written atomically (0600): every sign-in cookie stops working."""
    import secrets
    import tempfile
    path = session_key_path()
    key = secrets.token_bytes(32)
    fd, tmp = tempfile.mkstemp(prefix=".admin-session.", dir=os.path.dirname(path) or ".")
    try:
        os.fchmod(fd, 0o600) if hasattr(os, "fchmod") else None
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(key.hex() + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return key


def _session_secret():
    stored = _stored_hash()
    if stored is None:
        return None
    return hmac.new(_session_key(), b"gps-time-admin-session/1|" + stored.encode(), hashlib.sha256).digest()


def _mac(secret, body):
    return hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()


def new_session(remember, now=None, days=REMEMBER_DAYS):
    """(Set-Cookie value, expiry unix time) for a browser that just signed in with the token."""
    import secrets
    now = time.time() if now is None else now
    secret = _session_secret()
    if secret is None:
        return None, None
    life = int(days * 86400) if remember else SESSION_S
    exp = int(now + life)
    body = f"1.{exp}.{1 if remember else 0}.{secrets.token_hex(12)}"
    value = f"{body}.{_mac(secret, body)}"
    cookie = f"{SESSION_COOKIE}={value}; Path=/; HttpOnly; SameSite=Strict" + (f"; Max-Age={life}" if remember else "")
    return cookie, exp


def session_from(cookie_header, now=None):
    """{expires, remembered} for a valid sign-in cookie in a Cookie header, else None."""
    if not cookie_header:
        return None
    secret = _session_secret()
    if secret is None:
        return None
    now = time.time() if now is None else now
    for part in cookie_header.split(";"):
        name, sep, value = part.strip().partition("=")
        if not sep or name != SESSION_COOKIE:
            continue
        bits = value.split(".")
        if len(bits) != 5 or bits[0] != "1" or not bits[1].isdigit() or bits[2] not in ("0", "1"):
            continue
        body = ".".join(bits[:4])
        if hmac.compare_digest(_mac(secret, body), bits[4]) and int(bits[1]) > now:
            return {"expires": int(bits[1]), "remembered": bits[2] == "1"}
    return None


SIGNED_OUT_COOKIE = f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"


def _split_host(value):
    """'Host' header value -> lowercase hostname without port or brackets."""
    value = (value or "").strip().lower()
    if not value:
        return ""
    if value.startswith("["):                      # [ipv6]:port
        return value[1:value.find("]")] if "]" in value else ""
    if value.count(":") == 1:                      # name:port or ipv4:port
        return value.split(":", 1)[0]
    return value                                   # bare name / ipv4 / bare ipv6


def _is_ip(name):
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        return False


def allowed_host_names():
    names = {"localhost"}
    try:
        h = socket.gethostname().lower()
        if h:
            names.update({h, h + ".local", h.split(".")[0]})
    except OSError:
        pass
    names.update(_env_list("GTP_ALLOWED_HOSTS"))
    return names


def host_allowed(host_header):
    """IP literals, localhost / *.localhost, this machine's hostname (and
    <hostname>.local) and names in GTP_ALLOWED_HOSTS are accepted. A rebinding
    attacker's domain is not, because its name is what the browser sends."""
    name = _split_host(host_header)
    if not name:
        return False
    if _is_ip(name) or name.endswith(".localhost"):
        return True
    return name in allowed_host_names()


def origin_allowed(origin_header, host_header):
    """None (no Origin, non-browser client) is allowed; the token still applies.
    Otherwise the Origin must be same-origin with Host, or listed in
    GTP_ALLOWED_ORIGINS (e.g. a reverse proxy's public origin)."""
    if origin_header is None:
        return True
    origin = origin_header.strip().lower()
    if origin in ("", "null"):
        return False
    if origin.rstrip("/") in {o.rstrip("/") for o in _env_list("GTP_ALLOWED_ORIGINS")}:
        return True
    parts = urlsplit(origin)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return False
    return parts.netloc == (host_header or "").strip().lower()


# ─── failed-token logging and per-IP backoff ─────────────────────────────────

FREE_FAILURES = 3          # misses allowed before backoff starts
BASE_BACKOFF_S = 2.0       # 2, 4, 8, ... seconds
MAX_BACKOFF_S = 300.0
MAX_TRACKED_IPS = 1024     # bounded memory; oldest entries dropped


class AuthThrottle:
    """Per-IP failure counter with exponential backoff. In memory only (resets
    on restart); behind a reverse proxy all clients share one IP, so one
    attacker can lock everyone out for up to MAX_BACKOFF_S. That trade-off is
    documented in docs/api/README.md."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._ips = collections.OrderedDict()     # ip -> [failures, blocked_until]

    def retry_after(self, ip):
        """Seconds until this IP may try again (0 = allowed now)."""
        with self._lock:
            entry = self._ips.get(ip)
            return max(0.0, entry[1] - self._clock()) if entry else 0.0

    def failure(self, ip):
        """Record a miss; returns (failures, backoff_s)."""
        with self._lock:
            n, _ = self._ips.pop(ip, (0, 0.0))
            n += 1
            backoff = 0.0 if n <= FREE_FAILURES else min(MAX_BACKOFF_S, BASE_BACKOFF_S ** (n - FREE_FAILURES))
            self._ips[ip] = [n, self._clock() + backoff]
            while len(self._ips) > MAX_TRACKED_IPS:
                self._ips.popitem(last=False)
            return n, backoff

    def success(self, ip):
        with self._lock:
            self._ips.pop(ip, None)


THROTTLE = AuthThrottle()


def note_auth_failure(ip, route, header):
    """Log a failed attempt and apply backoff. Logs the reason, never the token."""
    reason = "missing" if not header else "malformed" if not header.lower().startswith("bearer ") else "invalid"
    n, backoff = THROTTLE.failure(ip)
    log.warning("admin token rejected: ip=%s route=%s reason=%s failures=%d backoff_s=%g",
                ip, route, reason, n, backoff)
    return backoff


# ─── security headers ────────────────────────────────────────────────────────

_CSP_BASE = ("default-src 'self'; object-src 'none'; base-uri 'none'; "
             "form-action 'self'; frame-ancestors 'none'")
# Every response: /app/, the API. Everything from this station, nothing inline (no exceptions
# since the legacy pages were removed after v1.4.0).
CSP_STRICT = _CSP_BASE + "; script-src 'self'; style-src 'self'"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",          # frame-ancestors for older browsers
}

