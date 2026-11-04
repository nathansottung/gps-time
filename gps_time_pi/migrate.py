"""Move a station's state to a new SD card or a new Pi: one encrypted file (docs/deploy/migrate.md).

  sudo /opt/gps-time-pi/venv/bin/python -m gps_time_pi.migrate export ~/station.gtpmig
  sudo /opt/gps-time-pi/venv/bin/python -m gps_time_pi.migrate import ~/station.gtpmig [--dry-run]

What moves (whichever exist):
  config        config.json: the site survey and exact position, privacy mode, time zone, module
                settings; config.json.prev
  keys          station-key and station-key.pub (the station's identity, which signs observation
                files), admin-token.sha256 (so the same admin token works), and the web SDR's
                password hash (/etc/gps-time-websdr/password)
  oscillator    oscillator-log.csv and the imported or reference profile files. The log is bound
                to its board by a serial hash: on the same Pi it carries on; on another Pi the
                station sets it aside at start and starts a new one (oscillator.py), and the
                profiles stay reference only. Nothing here overrides that.

What doesn't, on purpose: the event history and outage evidence (they describe the old install),
the learned sky-obstruction map (it describes the old antenna site), chrony's own files, and
anything outside the station's folder but the web SDR's password.

The file holds the station's exact position and its private key, so it is encrypted: AES-256-GCM,
with a key derived from a passphrase (scrypt, n=2^15, r=8, p=1). The passphrase is asked twice and
never taken from the command line or the environment. The file is written 0600 and given to the
user who ran sudo. It is never offered over HTTP.

Import refuses while gps-time-pi is running (the service would overwrite config.json when it
stops), checks every file's SHA-256 after decrypting, keeps whatever it replaces as
<name>.before-migrate-<time>, and writes each file with the owner and mode install.sh gives it.
A station must never run with another station's key: after moving the key, the old card isn't
used as a station again.
"""
import argparse
import base64
import getpass
import hashlib
import io
import json
import os
import secrets
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    AVAILABLE = True
except ImportError:          # the plain test run has no cryptography; the station venv does
    AVAILABLE = False

MAGIC = b"GPSTIME-MIGRATE/1\n"
FORMAT = "gps-time.migrate/1"
KDF = {"name": "scrypt", "n": 2 ** 15, "r": 8, "p": 1, "length": 32}
DEST = Path(os.environ.get("GTP_DEST", "/opt/gps-time-pi"))
ETC = Path("/etc")
MIN_PASSPHRASE = 12
MAX_FILE = 64 * 1024 * 1024

# name in the archive -> (where it lives, owner, group, mode, part). Owners and modes follow install.sh.
def files(dest=DEST, etc=ETC):
    d, e = Path(dest), Path(etc)
    return {
        "config.json": (d / "config.json", "gps-time", "gps-time", 0o600, "config"),
        "config.json.prev": (d / "config.json.prev", "gps-time", "gps-time", 0o600, "config"),
        "station-key": (d / "station-key", "gps-time", "gps-time", 0o600, "keys"),
        "station-key.pub": (d / "station-key.pub", "gps-time", "gps-time", 0o644, "keys"),
        "admin-token.sha256": (d / "admin-token.sha256", "root", "gps-time", 0o640, "keys"),
        "websdr-password": (e / "gps-time-websdr" / "password", "root", "root", 0o600, "keys"),
        "oscillator-log.csv": (d / "oscillator-log.csv", "gps-time", "gps-time", 0o640, "oscillator"),
        "oscillator-profile.json": (d / "oscillator-profile.json", "gps-time", "gps-time", 0o640, "oscillator"),
        "oscillator-profile-reference.json": (d / "oscillator-profile-reference.json", "gps-time", "gps-time", 0o640,
                                              "oscillator"),
    }


NOT_MOVED = ("timing-events.json and evidence/ (they describe the old install)",
             "sky-obstruction.json (it describes the old antenna site)")


class MigrateError(Exception):
    pass


def _need():
    if not AVAILABLE:
        raise MigrateError("the cryptography package is not installed: run this with the station's venv "
                           "(/opt/gps-time-pi/venv/bin/python)")


def _key(passphrase, salt, kdf=KDF):
    return Scrypt(salt=salt, length=kdf["length"], n=kdf["n"], r=kdf["r"], p=kdf["p"]).derive(passphrase.encode("utf-8"))


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def pack(contents, meta, passphrase):
    """contents: {name: bytes}. Returns the encrypted file's bytes."""
    _need()
    manifest = {"format": FORMAT, **meta,
                "files": {n: {"sha256": _sha(b), "bytes": len(b)} for n, b in sorted(contents.items())}}
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as t:
        for name, data in [("manifest.json", json.dumps(manifest, indent=1).encode())] + sorted(contents.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), 0o600, 0
            t.addfile(info, io.BytesIO(data))
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    header = {"kdf": KDF, "salt": base64.b64encode(salt).decode(), "nonce": base64.b64encode(nonce).decode(),
              "cipher": "AES-256-GCM"}
    head = json.dumps(header, separators=(",", ":")).encode() + b"\n"
    sealed = AESGCM(_key(passphrase, salt)).encrypt(nonce, buf.getvalue(), MAGIC + head)
    return MAGIC + head + sealed


def unpack(blob, passphrase):
    """(manifest, {name: bytes}); raises MigrateError on a wrong passphrase or a damaged file."""
    _need()
    if not blob.startswith(MAGIC):
        raise MigrateError("not a GPS Time migration file")
    head, sep, sealed = blob[len(MAGIC):].partition(b"\n")
    try:
        header = json.loads(head)
        kdf = header["kdf"]
        if kdf.get("name") != "scrypt" or not (2 ** 14 <= kdf["n"] <= 2 ** 20) or kdf["length"] != 32:
            raise ValueError("kdf")
        salt, nonce = base64.b64decode(header["salt"]), base64.b64decode(header["nonce"])
    except (ValueError, KeyError, TypeError):
        raise MigrateError("the file's header is damaged") from None
    from cryptography.exceptions import InvalidTag
    try:
        plain = AESGCM(_key(passphrase, salt, kdf)).decrypt(nonce, sealed, MAGIC + head + sep)
    except InvalidTag:
        raise MigrateError("wrong passphrase, or the file was changed or damaged") from None
    out, manifest = {}, None
    with tarfile.open(fileobj=io.BytesIO(plain), mode="r") as t:
        for m in t.getmembers():
            if not m.isfile() or "/" in m.name or m.name.startswith(".") or m.size > MAX_FILE:
                raise MigrateError(f"unexpected entry in the file: {m.name!r}")
            data = t.extractfile(m).read()
            if m.name == "manifest.json":
                manifest = json.loads(data)
            else:
                out[m.name] = data
    if not manifest or manifest.get("format") != FORMAT:
        raise MigrateError("the file has no manifest, or one of another format")
    want = manifest.get("files") or {}
    if set(want) != set(out):
        raise MigrateError("the files don't match the manifest")
    for name, data in out.items():
        if _sha(data) != want[name]["sha256"]:
            raise MigrateError(f"{name}: checksum mismatch")
    return manifest, out


def collect(dest=DEST, etc=ETC):
    contents = {}
    for name, (path, *_rest) in files(dest, etc).items():
        try:
            contents[name] = Path(path).read_bytes()
        except FileNotFoundError:
            continue
    if "config.json" not in contents:
        raise MigrateError(f"{Path(dest) / 'config.json'} not found: is this a station?")
    return contents


def _version(dest):
    try:
        return (Path(dest) / "gps_time_pi" / "VERSION").read_text().strip() or None
    except OSError:
        return None


def _as_root():
    return hasattr(os, "geteuid") and os.geteuid() == 0


def _ids(user, group):
    """(uid, gid) of the station's accounts; MigrateError when they don't exist yet."""
    import grp
    import pwd
    try:
        return pwd.getpwnam(user).pw_uid, grp.getgrnam(group).gr_gid
    except KeyError:
        raise MigrateError(f"user or group {user}:{group} doesn't exist: run install.sh on this Pi first") from None


def _chown(path, user, group):
    if _as_root():                               # tests run unprivileged: ownership stays the caller's
        os.chown(path, *_ids(user, group))


def _write(path, data, user, group, mode):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".migrate-tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    _chown(tmp, user, group)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def service_running():
    """True/False from systemctl; None where it can't be asked (not a station)."""
    try:
        r = subprocess.run(["systemctl", "is-active", "--quiet", "gps-time-pi.service"], timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.returncode == 0


def export(out, passphrase, dest=DEST, etc=ETC, now=None):
    contents = collect(dest, etc)
    meta = {"exported_utc": datetime.fromtimestamp(now or time.time(), timezone.utc).isoformat(timespec="seconds"),
            "software_version": _version(dest), "not_moved": list(NOT_MOVED)}
    blob = pack(contents, meta, passphrase)
    out = Path(out)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(blob)
    os.chmod(out, 0o600)
    owner = os.environ.get("SUDO_USER")
    if owner and _as_root():
        import pwd
        try:
            pw = pwd.getpwnam(owner)
            os.chown(out, pw.pw_uid, pw.pw_gid)
        except KeyError:
            pass
    return sorted(contents)


def import_(path, passphrase, dest=DEST, etc=ETC, dry_run=False, running=service_running, now=None):
    """[(name, action)] of what was (or, with dry_run, would be) done."""
    manifest, contents = unpack(Path(path).read_bytes(), passphrase)
    if not dry_run and running() is True:
        raise MigrateError("gps-time-pi is running: stop it first (sudo systemctl stop gps-time-pi), "
                           "or it would overwrite config.json when it stops")
    table = files(dest, etc)
    unknown = sorted(set(contents) - set(table))
    if unknown:
        raise MigrateError(f"the file has entries this version doesn't know: {', '.join(unknown)}")
    if not dry_run and _as_root():
        for name in contents:                    # before writing anything: the accounts must exist
            _ids(*table[name][1:3])
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now or time.time()))
    done = []
    for name in sorted(contents):
        target, user, group, mode, part = table[name]
        target = Path(target)
        exists = target.exists()
        same = exists and target.read_bytes() == contents[name]
        action = "unchanged" if same else ("replaced" if exists else "added")
        if not dry_run and not same:
            if exists:
                backup = target.with_name(f"{target.name}.before-migrate-{stamp}")
                os.replace(target, backup)
                action += f" (old one kept as {backup.name})"
            _write(target, contents[name], user, group, mode)
        done.append((name, part, action))
    return manifest, done


def _passphrase(confirm):
    pw = getpass.getpass("Passphrase for the migration file: ")
    if confirm:
        if len(pw) < MIN_PASSPHRASE:
            raise MigrateError(f"use at least {MIN_PASSPHRASE} characters")
        if getpass.getpass("Again: ") != pw:
            raise MigrateError("the two entries differ")
    return pw


def main(argv=None):
    ap = argparse.ArgumentParser(description="Move a GPS Time station's state to a new SD card or Pi (encrypted).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="write the station's config, keys, survey and oscillator log to one file")
    e.add_argument("out")
    i = sub.add_parser("import", help="restore them from a file made by export (stop gps-time-pi first)")
    i.add_argument("file")
    i.add_argument("--dry-run", action="store_true", help="show what would change; write nothing")
    for p in (e, i):
        p.add_argument("--dest", default=str(DEST), help=argparse.SUPPRESS)
        p.add_argument("--etc", default=str(ETC), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "export":
            print("The file will hold the station's exact position and its private key. It is encrypted with "
                  "the passphrase you give now; keep both safe, and delete the file once it's imported.")
            names = export(a.out, _passphrase(confirm=True), a.dest, a.etc)
            print(f"Wrote {a.out} (0600): {', '.join(names)}.")
            print("Not moved, on purpose: " + "; ".join(NOT_MOVED) + ".")
            return 0
        manifest, done = import_(a.file, _passphrase(confirm=False), a.dest, a.etc, dry_run=a.dry_run)
        print(f"From {manifest.get('exported_utc')} (software {manifest.get('software_version') or 'unknown'}):")
        for name, part, action in done:
            print(f"  {name} ({part}): {'would be ' if a.dry_run and action != 'unchanged' else ''}{action}")
        if not a.dry_run:
            print("Done. Start the station: sudo systemctl start gps-time-pi")
            print("The oscillator log carries on if this is the same Pi; on another Pi it is set aside at start.")
            print("Don't run the old card as a station again: it has the same station key.")
        return 0
    except MigrateError as err:
        print(f"Nothing changed: {err}.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
