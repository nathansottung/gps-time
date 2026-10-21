"""The station's key pair: Ed25519, generated at install, used to sign observation files.

- Private key: /opt/gps-time-pi/station-key (PKCS#8 PEM), mode 0600, owned by
  the web service user (gps-time). Never leaves the station; the module user
  (gps-time-mod) can't read it, and the module guard denies the path too.
- Public key: station-key.pub next to it (base64 of the 32 raw bytes), 0644.
- Station ID: the public key's fingerprint, "ed25519:" + SHA-256 hex.
- Signature: Ed25519 over the canonical JSON of the observation's metadata
  (sorted keys, no spaces, gpstime:signature set to null). The metadata holds
  gpstime:checksum, the SHA-256 of the data file, so the signature covers the
  samples too.

python -m gps_time_pi.station_key generate | show | sign <base> | verify <base>

Needs the `cryptography` package (requirements.txt). Without it, signing
fails and verification reports that it couldn't check, rather than passing.
"""

import argparse
import base64
import copy
import hashlib
import json
import os
import sys
from pathlib import Path

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    AVAILABLE = True
except ImportError:          # the plain test run has no third-party packages
    AVAILABLE = False

DEFAULT_PATH = Path(os.environ.get("GTP_STATION_KEY", "/opt/gps-time-pi/station-key"))
SIG_PREFIX = "ed25519:"


class StationKeyError(Exception):
    pass


def _need():
    if not AVAILABLE:
        raise StationKeyError("the cryptography package is not installed")


def fingerprint(public_raw):
    return "ed25519:" + hashlib.sha256(public_raw).hexdigest()


def public_raw(private):
    return private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def generate(path=DEFAULT_PATH, owner=None):
    """Create the key pair unless it exists; returns the station ID. Never overwrites a key."""
    _need()
    path = Path(path)
    if path.exists():
        return fingerprint(public_raw(load(path)))
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
        f.flush()
        os.fsync(f.fileno())
    pub = path.with_name(path.name + ".pub")
    pub.write_text(base64.b64encode(public_raw(key)).decode("ascii") + "\n", encoding="ascii")
    os.chmod(pub, 0o644)
    if owner and os.name == "posix":
        import pwd
        pw = pwd.getpwnam(owner)
        os.chown(path, pw.pw_uid, pw.pw_gid)
        os.chown(pub, pw.pw_uid, pw.pw_gid)
    return fingerprint(public_raw(key))


def load(path=DEFAULT_PATH):
    _need()
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise StationKeyError(f"{path} is not an Ed25519 key")
    return key


def canonical(meta):
    """The bytes that are signed: the metadata with the signature cleared."""
    m = copy.deepcopy(meta)
    m["global"]["gpstime:signature"] = None
    return json.dumps(m, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sign_meta(meta, private):
    """Set station_id, public_key and signature in meta (in place, after the checksum is set)."""
    _need()
    if not meta["global"].get("gpstime:checksum"):
        raise StationKeyError("sign after the data checksum is set (obsformat.write / to_bytes)")
    raw = public_raw(private)
    meta["global"]["gpstime:station_id"] = fingerprint(raw)
    meta["global"]["gpstime:public_key"] = base64.b64encode(raw).decode("ascii")
    sig = private.sign(canonical(meta))
    meta["global"]["gpstime:signature"] = SIG_PREFIX + base64.b64encode(sig).decode("ascii")
    return meta


def verify_meta(meta, trusted=None):
    """(True, msg) valid; (False, msg) invalid; (None, msg) can't check (unsigned, or no library).

    trusted: station IDs you accept; a valid signature from another station is
    reported (True, "... not in the trusted list") so the caller can warn."""
    g = meta.get("global", {})
    sig = g.get("gpstime:signature")
    if sig is None:
        return None, "unsigned"
    if not AVAILABLE:
        return None, "signature not checked: the cryptography package is not installed"
    pub_b64 = g.get("gpstime:public_key")
    if not isinstance(sig, str) or not sig.startswith(SIG_PREFIX) or not isinstance(pub_b64, str):
        return False, "signature or public key missing or malformed"
    try:
        raw = base64.b64decode(pub_b64, validate=True)
        sig_raw = base64.b64decode(sig[len(SIG_PREFIX):], validate=True)
        pub = Ed25519PublicKey.from_public_bytes(raw)
    except ValueError as e:
        return False, f"signature or public key malformed ({e})"
    if fingerprint(raw) != g.get("gpstime:station_id"):
        return False, "gpstime:station_id is not the fingerprint of gpstime:public_key"
    try:
        pub.verify(sig_raw, canonical(meta))
    except InvalidSignature:
        return False, "signature does not match the metadata (changed after signing?)"
    if trusted is not None and g["gpstime:station_id"] not in trusted:
        return True, f"signed by {g['gpstime:station_id']}, which is not in the trusted list"
    return True, f"signed by {g['gpstime:station_id']}"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m gps_time_pi.station_key", description="The station's signing key.")
    ap.add_argument("--path", default=str(DEFAULT_PATH))
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--owner", help="user to own the key files (install.sh: gps-time)")
    sub.add_parser("show")
    s = sub.add_parser("sign")
    s.add_argument("base")
    v = sub.add_parser("verify")
    v.add_argument("base")
    v.add_argument("--trust", action="append", help="a station ID you accept (repeatable)")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "generate":
            existed = Path(a.path).exists()
            sid = generate(a.path, a.owner)
            print(("Existing station key kept: " if existed else "Station key created: ") + sid)
        elif a.cmd == "show":
            raw = public_raw(load(a.path))
            print(json.dumps({"station_id": fingerprint(raw), "public_key": base64.b64encode(raw).decode("ascii")}))
        elif a.cmd == "sign":
            from . import obsformat
            meta, data = obsformat.read(a.base)
            obsformat.write(a.base, meta, data, signer=load(a.path))
            print(f"signed {a.base}")
        else:
            from . import obsformat
            meta, data = obsformat.read(a.base)
            ok, msg = verify_meta(meta, a.trust)
            if ok and obsformat.checksum(data) != meta["global"].get("gpstime:checksum"):
                ok, msg = False, "data does not match gpstime:checksum"
            print(msg)
            return 0 if ok else 1
    except (StationKeyError, OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
