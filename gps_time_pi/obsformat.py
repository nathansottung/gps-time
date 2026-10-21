"""Observation files: SigMF with the gpstime: extension (writer, reader, validator).

Spec: docs/specs/SPEC-OBSERVATION-FORMAT-AND-TASKING.md, Part 1. Guide:
docs/modules/observation-format.md. Standard library only.

An observation is two files with the same base name:
  <base>.sigmf-data   samples (binary)
  <base>.sigmf-meta   metadata (JSON): global, captures, annotations

The rule the validator enforces: the UTC time of every sample that claims one
is computable from its capture's core:datetime, core:sample_start and sample
rate (gpstime:sample_rate on the capture when present, else core:sample_rate),
with the uncertainty in gpstime:sample_time_uncertainty_s. A capture with
"gpstime:time_valid": false marks samples that have no time (before the first
PPS marker, or across dropped samples); it carries no core:datetime.

Signatures: write(..., signer=station_key.load()) signs the metadata with the
station's Ed25519 key (gps_time_pi/station_key.py); the validator verifies any
signature and warns about unsigned files or a station not in a trusted list.
"""

import argparse
import calendar
import hashlib
import json
import math
import os
import re
import struct
import sys
import tempfile
import time
from pathlib import Path

from . import station_key
from .modkit import schema

SIGMF_VERSION = "1.2.0"
EXTENSION = {"name": "gpstime", "version": "1.0.0", "optional": False}
GPSTIME_SCHEMA = "1"

# datatype: (struct format of one sample, complex?)
DATATYPES = {
    "cf32_le": ("<ff", True),
    "ci16_le": ("<hh", True),
    "cu8": ("<BB", True),      # RTL-SDR native: raw counts 0..255
    "rf32_le": ("<f", False),
    "ri16_le": ("<h", False),
}
_DT_RE = re.compile(r"^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.(\d{1,9}))?Z$")
_NAME_SAFE = re.compile(r"[^A-Za-z0-9.-]+")


# ---------------------------------------------------------------- time strings

def format_ns(ns):
    """UTC nanoseconds -> ISO 8601 with 9 fraction digits, 'Z'."""
    sec, frac = divmod(int(ns), 1_000_000_000)
    t = time.gmtime(sec)
    return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}T{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}.{frac:09d}Z"


def parse_ns(text):
    """ISO 8601 UTC ('Z', up to 9 fraction digits) -> integer nanoseconds; ValueError otherwise."""
    m = _DT_RE.match(text if isinstance(text, str) else "")
    if not m:
        raise ValueError(f"not an ISO 8601 UTC time with 'Z': {text!r}")
    y, mo, d, h, mi, s = (int(x) for x in m.groups()[:6])
    frac = (m.group(7) or "").ljust(9, "0")
    return calendar.timegm((y, mo, d, h, mi, s, 0, 0, 0)) * 1_000_000_000 + int(frac)


def filename(station_id, sensor, start_ns):
    """<station>_<sensor>_<start-utc>, safe for any file system."""
    stamp = format_ns(start_ns).replace(":", "").replace("-", "")
    return f"{_NAME_SAFE.sub('-', station_id)}_{_NAME_SAFE.sub('-', sensor)}_{stamp}"


# ---------------------------------------------------------------- samples

def sample_size(datatype):
    return struct.calcsize(DATATYPES[datatype][0])


def encode(samples, datatype):
    """Samples -> bytes. Float types take floats (complex for c*); integer types take raw counts."""
    fmt, cplx = DATATYPES[datatype]
    pack = struct.Struct(fmt).pack
    integer = fmt[-1] in "hB"
    lo, hi = {"h": (-32768, 32767), "B": (0, 255)}.get(fmt[-1], (None, None))

    def conv(v):
        if not integer:
            return float(v)
        return max(lo, min(hi, int(round(v))))
    out = bytearray()
    for s in samples:
        out += pack(conv(s.real), conv(s.imag)) if cplx else pack(conv(s))
    return bytes(out)


def decode(data, datatype):
    fmt, cplx = DATATYPES[datatype]
    it = struct.iter_unpack(fmt, data)
    return [complex(a, b) for a, b in it] if cplx else [v for (v,) in it]


# ---------------------------------------------------------------- writing

def build_meta(*, datatype, sample_rate, captures, gpstime, recorder, annotations=(), hw=None, description=None):
    """A .sigmf-meta document (checksum filled in by write()). gpstime: the gpstime:* fields, without the prefix."""
    g = {"core:datatype": datatype, "core:sample_rate": float(sample_rate), "core:version": SIGMF_VERSION,
         "core:recorder": recorder, "core:extensions": [dict(EXTENSION)], "gpstime:schema": GPSTIME_SCHEMA}
    if hw:
        g["core:hw"] = hw
    if description:
        g["core:description"] = description
    for k, v in gpstime.items():
        g[f"gpstime:{k}"] = v
    g.setdefault("gpstime:checksum", None)
    g.setdefault("gpstime:public_key", None)
    g.setdefault("gpstime:signature", None)
    return {"global": g, "captures": list(captures), "annotations": list(annotations)}


def _atomic_write(path, data):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def checksum(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def to_bytes(meta, data, signer=None):
    """(data bytes, meta bytes) with the checksum set and, given the station's key, signed."""
    meta = json.loads(json.dumps(meta))
    meta["global"]["gpstime:checksum"] = checksum(data)
    meta["global"]["gpstime:signature"] = None
    if signer is not None:
        station_key.sign_meta(meta, signer)
    return data, (json.dumps(meta, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write(base, meta, data, signer=None):
    """Write <base>.sigmf-data then <base>.sigmf-meta (each atomically), signed when given
    the station's key. Returns the two paths."""
    base = Path(base)
    data_b, meta_b = to_bytes(meta, data, signer)
    dp, mp = base.with_name(base.name + ".sigmf-data"), base.with_name(base.name + ".sigmf-meta")
    _atomic_write(dp, data_b)
    _atomic_write(mp, meta_b)
    return dp, mp


# ---------------------------------------------------------------- reading

def read(base):
    """(meta dict, sample bytes) of an observation.

    A sidecar for another file format (a WAV from gps_time_pi.convert) names its
    data file in core:dataset, with core:header_bytes on the first capture; the
    header is skipped, so the bytes are the samples either way."""
    base = Path(base)
    meta = json.loads(base.with_name(base.name + ".sigmf-meta").read_text(encoding="utf-8"))
    dataset = meta.get("global", {}).get("core:dataset")
    if dataset is None:
        return meta, base.with_name(base.name + ".sigmf-data").read_bytes()
    if not isinstance(dataset, str) or Path(dataset).name != dataset or dataset in ("", ".", ".."):
        raise ValueError(f"core:dataset must be a file name next to the metadata, not {dataset!r}")
    caps = meta.get("captures") or [{}]
    header = caps[0].get("core:header_bytes", 0)
    return meta, base.with_name(dataset).read_bytes()[header:]


def sample_count(meta, data):
    return len(data) // sample_size(meta["global"]["core:datatype"])


def sample_time(meta, index):
    """(UTC ns, sample_time_uncertainty_s) of a sample, or None where the file gives it no time.

    The uncertainty is the sample path's only; add the station's
    gpstime:time_offset_bound_s for the total."""
    g = meta["global"]
    caps = meta["captures"]
    cap = None
    for c in caps:
        if c["core:sample_start"] <= index:
            cap = c
        else:
            break
    if cap is None or cap.get("gpstime:time_valid") is False or "core:datetime" not in cap:
        return None
    rate = cap.get("gpstime:sample_rate", g["core:sample_rate"])
    ns = parse_ns(cap["core:datetime"]) + round((index - cap["core:sample_start"]) / rate * 1e9)
    return ns, g.get("gpstime:sample_time_uncertainty_s")


# ---------------------------------------------------------------- validation

def validate_meta(meta, data=None, trusted=None):
    """(errors, warnings) for a metadata document, and its data when given.
    trusted: station IDs you accept (warning for a valid signature from another)."""
    errs, warns = [], []
    if not isinstance(meta, dict) or not isinstance(meta.get("global"), dict):
        return ["metadata has no 'global' object"], warns
    g = meta["global"]
    errs += [f"global: {e[2:]}" if e.startswith("$.") else f"global: {e}"
             for e in schema.validate(g, schema.load("sigmf-gpstime.v1"))]
    if errs:
        return errs, warns
    if not any(isinstance(x, dict) and x.get("name") == "gpstime" for x in g["core:extensions"]):
        errs.append("global: core:extensions does not list gpstime")

    n = None
    if data is not None:
        size = sample_size(g["core:datatype"])
        if len(data) % size:
            errs.append(f"data: {len(data)} bytes is not a whole number of {g['core:datatype']} samples")
        n = len(data) // size
        if checksum(data) != g["gpstime:checksum"]:
            errs.append("data: checksum does not match gpstime:checksum")

    caps = meta.get("captures")
    if not isinstance(caps, list) or not caps:
        errs.append("captures: at least one capture is needed")
        caps = []
    prev = None
    for i, c in enumerate(caps):
        where = f"captures[{i}]"
        s = c.get("core:sample_start") if isinstance(c, dict) else None
        if not isinstance(s, int) or isinstance(s, bool) or s < 0:
            errs.append(f"{where}: core:sample_start must be a non-negative integer")
            continue
        if prev is not None and s <= prev["core:sample_start"]:
            errs.append(f"{where}: sample_start must increase")
        if n is not None and s >= max(n, 1):
            errs.append(f"{where}: sample_start {s} is past the last sample")
        rate = c.get("gpstime:sample_rate", g["core:sample_rate"])
        if not isinstance(rate, (int, float)) or rate <= 0:
            errs.append(f"{where}: gpstime:sample_rate must be positive")
            rate = None
        if g["gpstime:sensor"] == "rf" and not isinstance(c.get("core:frequency"), (int, float)):
            errs.append(f"{where}: core:frequency is required for RF observations")
        if c.get("gpstime:time_valid") is False:
            if "core:datetime" in c:
                errs.append(f"{where}: a capture without time must not carry core:datetime")
        else:
            try:
                t = parse_ns(c.get("core:datetime"))
            except ValueError as e:
                errs.append(f"{where}: {e} (every sample's time must be computable)")
                t = None
            if t is not None and prev is not None and prev.get("_t") is not None and rate:
                expect = (s - prev["core:sample_start"]) / prev["_rate"] * 1e9
                if abs((t - prev["_t"]) - expect) > 1e-3 * expect + 1000:
                    errs.append(f"{where}: core:datetime disagrees with the previous capture and the sample rate")
            c = dict(c, _t=t, _rate=rate)
        prev = dict(c, _t=c.get("_t"), _rate=rate)

    for i, a in enumerate(meta.get("annotations", [])):
        s, k = a.get("core:sample_start"), a.get("core:sample_count")
        if not isinstance(s, int) or s < 0 or not isinstance(k, int) or k < 0:
            errs.append(f"annotations[{i}]: needs non-negative integer core:sample_start and core:sample_count")
        elif n is not None and s + k > n:
            errs.append(f"annotations[{i}]: runs past the last sample")

    pos = g["gpstime:position"]
    if pos["privacy"] == "hidden" and (pos["lat"] is not None or pos["lon"] is not None):
        errs.append("global: gpstime:position is hidden but carries a position")
    if pos["privacy"] == "rounded":
        for k in ("lat", "lon"):
            v = pos[k]
            if v is not None and not math.isclose(v, round(v, 1), abs_tol=1e-9):
                errs.append(f"global: gpstime:position is rounded but {k} has more than 1 decimal")
        if pos.get("alt_m") is not None and not math.isclose(pos["alt_m"], round(pos["alt_m"], -1), abs_tol=1e-6):
            errs.append("global: gpstime:position is rounded but alt_m isn't rounded to 10 m")

    ok, msg = station_key.verify_meta(meta, trusted)
    if ok is False:
        errs.append(f"signature: {msg}")
    elif ok is None or "not in the trusted list" in msg:
        warns.append(msg)
    if g["gpstime:sample_time_uncertainty_s"] is None:
        warns.append("sample time uncertainty is unknown")
    if g["gpstime:time_offset_bound_s"] is None:
        warns.append("the station's clock offset bound is unknown")
    return errs, warns


def validate(base, trusted=None):
    """(errors, warnings) for the observation at <base>."""
    try:
        meta, data = read(base)
    except (OSError, ValueError) as e:
        return [f"cannot read {base}: {e}"], []
    return validate_meta(meta, data, trusted)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m gps_time_pi.obsformat", description="Check or describe an observation (SigMF + gpstime:).")
    ap.add_argument("cmd", choices=["validate", "info"])
    ap.add_argument("base", help="path without .sigmf-meta / .sigmf-data")
    a = ap.parse_args(argv)
    if a.cmd == "validate":
        errs, warns = validate(a.base)
        for e in errs:
            print(f"error: {e}")
        for w in warns:
            print(f"warning: {w}")
        print("valid" if not errs else "INVALID")
        return 1 if errs else 0
    meta, data = read(a.base)
    g = meta["global"]
    n = sample_count(meta, data)
    first = next((sample_time(meta, c["core:sample_start"]) for c in meta["captures"]
                  if c.get("gpstime:time_valid") is not False and "core:datetime" in c), None)
    print(json.dumps({"samples": n, "datatype": g["core:datatype"], "sample_rate": g["core:sample_rate"],
                      "sensor": g["gpstime:sensor"], "time_source": g["gpstime:time_source"],
                      "first_timed_sample_utc": format_ns(first[0]) if first else None,
                      "sample_time_uncertainty_s": g["gpstime:sample_time_uncertainty_s"],
                      "captures": len(meta["captures"]), "annotations": len(meta.get("annotations", []))}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
