"""Request checks for the station web server (review findings GPS-014, GPS-017).

- Host allowlist on every request: defeats DNS rebinding, where an attacker's
  domain resolves to the station and a page on that domain reads /api.
- Origin check on every POST: a browser always sends Origin on POST, so a
  cross-site form or fetch is refused. Clients without Origin (curl, scripts)
  still need the admin token.
- Admin token: state-changing actions need `Authorization: Bearer <token>`.
  Only a SHA-256 of the token is stored (GTP_ADMIN_TOKEN_FILE, default
  admin-token.sha256 next to config.json). No file means admin is disabled.
  Create or replace it with `python3 -m gps_time_pi.admin_token`.

Standard library only; nothing here touches timing behavior.
"""

import hashlib
import hmac
import ipaddress
import os
import socket
from urllib.parse import urlsplit

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
