"""Signed messages between a station and the coordinator.

Envelope (JSON):

    {"v": 1, "type": "join" | "events", "station_id": "ed25519:<sha256 hex>",
     "public_key": "<base64 of the 32 raw bytes>", "seq": <int, increasing per station>,
     "sent_utc": "<ISO 8601>", "body": {...}, "signature": "ed25519:<base64>"}

- station_id is the fingerprint of public_key, as in gps_time_pi/station_key.py,
  so a station signs with the key it already has.
- The signature is Ed25519 over the canonical JSON of the envelope with
  "signature" set to null (sorted keys, no spaces, UTF-8).
- seq must increase for each station; the coordinator refuses a repeat, so a
  captured message can't be replayed.

Needs the `cryptography` package; without it nothing is accepted as verified.
"""

import base64
import copy
import hashlib
import json

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    AVAILABLE = True
except ImportError:
    AVAILABLE = False

VERSION = 1
TYPES = ("join", "events")
SIG_PREFIX = "ed25519:"
MAX_EVENTS = 1000


class MessageError(ValueError):
    pass


def fingerprint(public_raw):
    return "ed25519:" + hashlib.sha256(public_raw).hexdigest()


def canonical(env):
    e = copy.deepcopy(env)
    e["signature"] = None
    return json.dumps(e, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sign(env, private):
    """Fill station_id, public_key and signature (in place). For stations, tests and the demo client."""
    if not AVAILABLE:
        raise MessageError("the cryptography package is not installed")
    raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    env["station_id"] = fingerprint(raw)
    env["public_key"] = base64.b64encode(raw).decode("ascii")
    env["signature"] = SIG_PREFIX + base64.b64encode(private.sign(canonical(env))).decode("ascii")
    return env


def new_key():
    if not AVAILABLE:
        raise MessageError("the cryptography package is not installed")
    return Ed25519PrivateKey.generate()


def check_shape(env):
    """Raise MessageError unless env has the envelope's fields and types."""
    if not isinstance(env, dict):
        raise MessageError("message must be a JSON object")
    if env.get("v") != VERSION:
        raise MessageError(f"unsupported version {env.get('v')!r}")
    if env.get("type") not in TYPES:
        raise MessageError(f"type must be one of {TYPES}")
    for k, t in (("station_id", str), ("public_key", str), ("sent_utc", str), ("signature", str), ("body", dict)):
        if not isinstance(env.get(k), t):
            raise MessageError(f"{k} missing or not a {t.__name__}")
    seq = env.get("seq")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
        raise MessageError("seq must be a non-negative integer")
    if env["type"] == "events":
        ev = env["body"].get("events")
        if not isinstance(ev, list) or not ev or len(ev) > MAX_EVENTS:
            raise MessageError(f"body.events must be a list of 1..{MAX_EVENTS} events")
        if not all(isinstance(e, dict) for e in ev):
            raise MessageError("every event must be an object")


def verify(env, known_public_key=None):
    """Raise MessageError unless the signature is valid and station_id matches the key.
    known_public_key: the base64 key on record; a different key is refused."""
    check_shape(env)
    if not AVAILABLE:
        raise MessageError("signature not checked: the cryptography package is not installed")
    sig = env["signature"]
    if not sig.startswith(SIG_PREFIX):
        raise MessageError("signature malformed")
    try:
        raw = base64.b64decode(env["public_key"], validate=True)
        pub = Ed25519PublicKey.from_public_bytes(raw)
        sig_raw = base64.b64decode(sig[len(SIG_PREFIX):], validate=True)
    except ValueError as e:
        raise MessageError(f"signature or public key malformed ({e})") from e
    if fingerprint(raw) != env["station_id"]:
        raise MessageError("station_id is not the fingerprint of public_key")
    if known_public_key is not None and known_public_key != env["public_key"]:
        raise MessageError("public key differs from the one on record")
    try:
        pub.verify(sig_raw, canonical(env))
    except InvalidSignature as e:
        raise MessageError("signature does not match the message") from e


def private_from_pem(pem_bytes):
    """Load a PKCS#8 PEM Ed25519 key, such as a station's station-key."""
    if not AVAILABLE:
        raise MessageError("the cryptography package is not installed")
    key = serialization.load_pem_private_key(pem_bytes, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise MessageError("not an Ed25519 key")
    return key
