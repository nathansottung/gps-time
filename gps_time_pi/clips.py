"""Capped clip recording: audio and IQ from an RTL-SDR, as SigMF with timing (docs/deploy/clips.md).

Owner's rc.3 list and design (2026-11-04): audio and IQ (SigMF with timing); a capped RAM folder by
default, oldest dropped; optionally a USB drive or NAS mount the owner names, capped, never the SD
card; listed and downloadable on the Radio page; timestamps carry the station's timing quality.

  kinds    iq   raw samples (cu8, the RTL-SDR's own) at 1.024, 2.048 or 2.4 MS/s
           am, nfm, wfm   audio, demodulated from 240 kS/s IQ to 48 kHz (ri16_le)
  source   rtl_tcp on 127.0.0.1:1234 (the SDR stack's PPS-role dongle). It serves one client at a
           time: while sdr-pps-marker reads it, a clip waits for it or fails, and says so.
  timing   core:datetime is this Pi's clock when the first sample after the settle time arrived.
           gpstime:time_source comes from timequality: pps on the station (its clock follows its
           GNSS/PPS reference), ntp on an SDR node, free_running when chrony can't tell;
           gpstime:time_offset_bound_s is chrony's bound. gpstime:sample_time_uncertainty_s is the
           RTL-SDR's USB buffering, which dominates: one 256 KiB buffer at the byte rate, at least
           50 ms (modeled, from the buffer size; never measured here).
  storage  /run/gps-time-clips (RAM, cleared at boot) unless /etc/default/gps-time-clips names
           another folder, which must be on another file system than / (the SD card). Capped
           (GTP_CLIPS_MAX_MB, default 64): the oldest clips go first. A clip that would not fit the
           cap is refused before recording.

The web service only validates a request, writes it as <dir>/.pending.json and starts
gps-time-clip.service; that unit records (python -m gps_time_pi.clips record). One clip at a time.
Every clip is signed with the station key when it can be read, and carries the position at the
station's privacy mode. A download goes out at the current mode too (redacted_meta): a clip
recorded in exact mode and fetched after the switch to rounded or hidden has its position
reduced on the way out, and loses its signature, which no longer matches (security review,
2026-11-04, H1).
"""
import argparse
import json
import os
import re
import secrets
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

from . import config, obsformat, timequality
from .labels import q

ENVFILE = Path(os.environ.get("GTP_CLIPS_ENV", "/etc/default/gps-time-clips"))
DEFAULT_DIR = Path("/run/gps-time-clips")
DEFAULT_MAX_MB = 64
RTL_TCP = ("127.0.0.1", 1234)
KINDS = ("iq", "am", "nfm", "wfm")
IQ_RATES = (1_024_000, 2_048_000, 2_400_000)
AUDIO_IN, AUDIO_OUT = 240_000, 48_000
FREQ_RANGE = (24_000_000, 1_766_000_000)       # R820T/R860 tuners
MAX_SECONDS = 60
SETTLE_S = 0.25
USB_BUFFER = 256 * 1024
NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,160}$")
EXTS = ("sigmf-meta", "sigmf-data", "wav")


class ClipError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


# ── where clips go ─────────────────────────────────────────────────────────

def settings():
    out = {"dir": DEFAULT_DIR, "max_mb": DEFAULT_MAX_MB, "custom": False}
    try:
        for line in ENVFILE.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            v = v.strip()
            if k.strip() == "GTP_CLIPS_DIR" and v:
                out["dir"], out["custom"] = Path(v), True
            elif k.strip() == "GTP_CLIPS_MAX_MB" and v.isdigit() and 1 <= int(v) <= 100_000:
                out["max_mb"] = int(v)
    except OSError:
        pass
    return out


def storage_problem(d, root="/"):
    """Why clips can't go to d, or None. Never the SD card: d must be on another file system than /."""
    try:
        st = os.stat(d)
    except OSError:
        return f"{d} doesn't exist (a USB drive or NAS not mounted?)"
    if not os.path.isdir(d):
        return f"{d} isn't a folder"
    if st.st_dev == os.stat(root).st_dev:
        return f"{d} is on the SD card's file system: clips go to RAM or another drive only"
    return None


def _clip_files(d):
    """{base: [paths]} of the clips in d."""
    out = {}
    try:
        for p in Path(d).iterdir():
            if p.name.startswith("."):
                continue
            for ext in ("sigmf-meta", "sigmf-data"):
                if p.name.endswith("." + ext):
                    out.setdefault(p.name[: -len(ext) - 1], []).append(p)
    except OSError:
        pass
    return out


def used_bytes(d):
    return sum(p.stat().st_size for paths in _clip_files(d).values() for p in paths if p.exists())


def enforce_cap(d, max_bytes):
    """Drop the oldest clips until the folder is within the cap. Returns the bases dropped."""
    clips = _clip_files(d)
    order = sorted(clips, key=lambda b: min(p.stat().st_mtime for p in clips[b]))
    dropped, total = [], used_bytes(d)
    for base in order:
        if total <= max_bytes:
            break
        for p in clips[base]:
            try:
                total -= p.stat().st_size
                p.unlink()
            except OSError:
                pass
        dropped.append(base)
    return dropped


# ── requests ───────────────────────────────────────────────────────────────

def estimate_bytes(req):
    if req["kind"] == "iq":
        return int(req["rate"] * 2 * req["seconds"]) + 8192
    return int(AUDIO_OUT * 2 * req["seconds"]) + 8192


def validate(body, max_bytes):
    """A clip request from the page: {kind, freq_hz, seconds, rate?, gain_db?}. ClipError when not."""
    if not isinstance(body, dict):
        raise ClipError("clip must be an object")
    kind = body.get("kind")
    if kind not in KINDS:
        raise ClipError(f"kind must be one of {', '.join(KINDS)}")
    try:
        freq = int(body.get("freq_hz"))
        seconds = float(body.get("seconds"))
    except (TypeError, ValueError):
        raise ClipError("freq_hz and seconds must be numbers") from None
    if not FREQ_RANGE[0] <= freq <= FREQ_RANGE[1]:
        raise ClipError(f"freq_hz must be {FREQ_RANGE[0]}..{FREQ_RANGE[1]}")
    if not 1 <= seconds <= MAX_SECONDS:
        raise ClipError(f"seconds must be 1..{MAX_SECONDS}")
    rate = AUDIO_IN
    if kind == "iq":
        rate = int(body.get("rate") or IQ_RATES[0])
        if rate not in IQ_RATES:
            raise ClipError(f"rate must be one of {', '.join(str(r) for r in IQ_RATES)}")
    gain = body.get("gain_db")
    if gain is not None:
        try:
            gain = float(gain)
        except (TypeError, ValueError):
            raise ClipError("gain_db must be a number or null (automatic)") from None
        if not 0 <= gain <= 50:
            raise ClipError("gain_db must be 0..50")
    req = {"id": secrets.token_hex(6), "kind": kind, "freq_hz": freq, "seconds": seconds, "rate": rate, "gain_db": gain}
    if estimate_bytes(req) > max_bytes:
        raise ClipError(f"about {estimate_bytes(req) / 1e6:.0f} MB, more than the {max_bytes / 1e6:.0f} MB cap: "
                        "record fewer seconds or a lower rate")
    return req


def request(body, run=subprocess.run):
    """POST /api/setting {"clip": {...}}: check it, queue it, start the recorder unit."""
    s = settings()
    problem = storage_problem(s["dir"])
    if problem:
        raise ClipError(problem, 409)
    pending = Path(s["dir"]) / ".pending.json"
    if pending.exists():
        raise ClipError("a clip is already being recorded; wait for it to finish", 409)
    req = validate(body, s["max_mb"] * 1024 * 1024)
    tmp = pending.with_name(".pending.tmp")
    tmp.write_text(json.dumps(req), encoding="utf-8")
    os.replace(tmp, pending)
    try:
        r = run(["systemctl", "start", "--no-block", "gps-time-clip.service"], capture_output=True, text=True, timeout=15)
        ok = r.returncode == 0
        detail = (r.stderr or r.stdout).strip()[:300]
    except (OSError, subprocess.SubprocessError) as e:
        ok, detail = False, str(e)[:300]
    if not ok:
        pending.unlink(missing_ok=True)
        raise ClipError(f"the recorder didn't start: {detail or 'systemctl failed'}", 502)
    return {"ok": True, "clip": req}


def delete(name):
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ClipError("not a clip name", 404)
    d = settings()["dir"]
    paths = _clip_files(d).get(name)
    if not paths:
        raise ClipError("no such clip", 404)
    for p in paths:
        p.unlink(missing_ok=True)
    return {"ok": True, "deleted": name}


# ── rtl_tcp and demodulation ───────────────────────────────────────────────

def _cmd(sock, code, value):
    sock.sendall(struct.pack(">BI", code, value & 0xFFFFFFFF))


def capture(freq_hz, rate, seconds, gain_db=None, addr=RTL_TCP, clock=time.time_ns, timeout=10.0):
    """(cu8 bytes, first-sample time in ns). Reads rtl_tcp: its 12-byte header, then samples."""
    sock = socket.create_connection(addr, timeout=timeout)
    sock.settimeout(timeout)
    try:
        head = b""
        while len(head) < 12:
            chunk = sock.recv(12 - len(head))
            if not chunk:
                raise ClipError("rtl_tcp closed the connection (busy with another client?)", 503)
            head += chunk
        if head[:4] != b"RTL0":
            raise ClipError("not an rtl_tcp server", 502)
        _cmd(sock, 0x02, rate)
        _cmd(sock, 0x01, freq_hz)
        if gain_db is None:
            _cmd(sock, 0x03, 0)                 # automatic gain
        else:
            _cmd(sock, 0x03, 1)
            _cmd(sock, 0x04, int(round(gain_db * 10)))
        settle = int(rate * 2 * SETTLE_S)
        want = int(rate * 2 * seconds)
        buf, got_settle, start_ns = bytearray(), 0, None
        while got_settle < settle:
            chunk = sock.recv(min(65536, settle - got_settle))
            if not chunk:
                raise ClipError("rtl_tcp stopped sending", 503)
            got_settle += len(chunk)
        while len(buf) < want:
            chunk = sock.recv(min(262144, want - len(buf)))
            if not chunk:
                raise ClipError("rtl_tcp stopped sending", 503)
            if start_ns is None:
                start_ns = clock()
            buf += chunk
        return bytes(buf[: want - want % 2]), start_ns
    finally:
        sock.close()


def demodulate(cu8, kind):
    """240 kS/s cu8 -> 48 kHz int16 PCM bytes (AM: envelope; NFM/WFM: phase difference)."""
    import numpy as np
    raw = np.frombuffer(cu8, dtype=np.uint8).astype(np.float32)
    iq = (raw[0::2] - 127.5) / 127.5 + 1j * (raw[1::2] - 127.5) / 127.5
    if kind == "am":
        x = np.abs(iq)
        x = x - x.mean()
    else:
        x = np.angle(iq[1:] * np.conj(iq[:-1])).astype(np.float32)
    factor = AUDIO_IN // AUDIO_OUT
    cutoff = (15_000 if kind == "wfm" else 5_000) / AUDIO_IN
    taps = 101
    n = np.arange(taps) - (taps - 1) / 2
    h = np.sinc(2 * cutoff * n) * np.hamming(taps)
    h /= h.sum()
    y = np.convolve(x, h, mode="same")[::factor]
    peak = float(np.max(np.abs(y))) or 1.0
    pcm = np.clip(y / peak * 0.9 * 32767, -32768, 32767).astype("<i2")
    return pcm.tobytes()


# ── recording one clip ─────────────────────────────────────────────────────

def _station_id_and_signer():
    try:
        from . import station_key
        key = station_key.load()
        return station_key.fingerprint(station_key.public_raw(key)), key
    except Exception:  # noqa: BLE001 - no key (or no cryptography): an unsigned clip, and it says so
        return "unknown-station", None


def _position(cfg):
    site, mode = config.privacy_site(cfg, cfg.get("site"))
    if not site:
        return {"privacy": "hidden", "lat": None, "lon": None, "alt_m": None}
    return {"privacy": mode, "lat": site.get("lat"), "lon": site.get("lon"), "alt_m": site.get("alt_msl")}


_STRICTNESS = {"exact": 0, "rounded": 1, "hidden": 2}


def redacted_meta(meta, cfg):
    """(meta, changed): the metadata with its position no more precise than the current privacy mode."""
    mode = (cfg or {}).get("location_display", "exact")
    g = meta.get("global") or {}
    pos = g.get("gpstime:position")
    if not isinstance(pos, dict):
        return meta, False
    stored = pos.get("privacy") if pos.get("privacy") in _STRICTNESS else "exact"
    if _STRICTNESS.get(mode, 2) <= _STRICTNESS[stored]:
        return meta, False
    if mode == "rounded":
        alt = pos.get("alt_m")
        new = {"privacy": "rounded",
               "lat": None if pos.get("lat") is None else round(pos["lat"], 1),
               "lon": None if pos.get("lon") is None else round(pos["lon"], 1),
               "alt_m": None if alt is None else round(alt, -1)}
    else:
        new = {"privacy": "hidden", "lat": None, "lon": None, "alt_m": None}
    meta = json.loads(json.dumps(meta))
    meta["global"]["gpstime:position"] = new
    meta["global"]["gpstime:signature"] = None
    meta["global"]["gpstime:position_note"] = (
        f"Recorded in {stored} mode; the position was reduced to the station's current mode ({mode}) when "
        "downloaded, so the station's signature, which covered the original, was removed.")
    return meta, True


def record(req, d, cfg=None, tq=None, cap=capture, signer_info=None, max_bytes=None):
    """Record one clip into d. Returns (base path, meta)."""
    cfg = config.load() if cfg is None else cfg
    tq = tq or timequality.current()
    station_id, signer = signer_info or _station_id_and_signer()
    raw, start_ns = cap(req["freq_hz"], req["rate"], req["seconds"], req.get("gain_db"))
    source = {"refclock": "pps", "ntp": "ntp"}.get(tq.get("source"), "free_running")
    bound = (tq.get("max_error_s") or {}).get("value")
    byte_rate = req["rate"] * 2
    uncertainty = max(0.05, USB_BUFFER / byte_rate)
    if req["kind"] == "iq":
        data, datatype, rate = raw, "cu8", req["rate"]
        quantity, unit, channels = "complex baseband voltage", "raw counts (cu8, offset 127.5)", [{"name": "IQ"}]
        calibration = {"sample_scale": 127.5, "sample_offset": 127.5, "gain_db": req.get("gain_db")}
    else:
        data, datatype, rate = demodulate(raw, req["kind"]), "ri16_le", AUDIO_OUT
        quantity, unit, channels = f"{req['kind'].upper()} audio", "relative (full scale = 32767)", [{"name": "audio"}]
        calibration = {"demodulation": req["kind"], "from_rate": AUDIO_IN, "gain_db": req.get("gain_db"),
                       "level": "normalised to 90 % of full scale"}
    note = (f"This Pi's clock when the first sample after {SETTLE_S:.2f} s arrived, labelled from chrony "
            f"({tq.get('label')}). The RTL-SDR's USB buffering dominates the sample time uncertainty "
            "(modeled from its 256 KiB buffer, not measured).")
    meta = obsformat.build_meta(
        datatype=datatype, sample_rate=rate,
        captures=[{"core:sample_start": 0, "core:frequency": float(req["freq_hz"]),
                   "core:datetime": obsformat.format_ns(start_ns)}],
        gpstime={"station_id": station_id, "sensor": "rf" if req["kind"] == "iq" else "audio",
                 "quantity": quantity, "unit": unit, "channels": channels, "time_source": source,
                 "time_offset_bound_s": bound, "sample_time_uncertainty_s": uncertainty,
                 "frequency_reference": {"state": "free", "error_ppm": None, "source": "the dongle's own crystal"},
                 "calibration": calibration, "position": _position(cfg), "provenance": "observed",
                 "request_id": req.get("id"), "licence": "CC-BY-4.0", "time_note": note},
        recorder="gps-time-pi clips", description=f"{req['kind']} clip at {req['freq_hz'] / 1e6:.4f} MHz, {req['seconds']:g} s")
    base = Path(d) / obsformat.filename(station_id[:16], req["kind"], start_ns)
    obsformat.write(base, meta, data, signer=signer)
    if max_bytes:
        enforce_cap(d, max_bytes)
    return base, meta


def run_pending(now=time.time):
    """The recorder unit: the queued request, recorded; .pending.json is removed whatever happens."""
    s = settings()
    d = Path(s["dir"])
    pending = d / ".pending.json"
    result = d / ".last.json"
    try:
        req = json.loads(pending.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    try:
        problem = storage_problem(d)
        if problem:
            raise ClipError(problem)
        base, _meta = record(req, d, max_bytes=s["max_mb"] * 1024 * 1024)
        doc = {"ok": True, "id": req.get("id"), "clip": base.name, "at": now()}
    except (ClipError, OSError) as e:
        doc = {"ok": False, "id": req.get("id"), "error": str(e), "at": now()}
    finally:
        pending.unlink(missing_ok=True)
    result.write_text(json.dumps(doc), encoding="utf-8")
    return 0 if doc["ok"] else 1


# ── the API ────────────────────────────────────────────────────────────────

def _summary(base, paths):
    try:
        meta = json.loads(next(p for p in paths if p.name.endswith(".sigmf-meta")).read_text(encoding="utf-8"))
    except (StopIteration, OSError, ValueError):
        return None
    g, c = meta.get("global", {}), (meta.get("captures") or [{}])[0]
    data = next((p for p in paths if p.name.endswith(".sigmf-data")), None)
    size = sum(p.stat().st_size for p in paths if p.exists())
    rate = g.get("core:sample_rate") or 0
    n = (data.stat().st_size // obsformat.sample_size(g["core:datatype"])) if data and g.get("core:datatype") in obsformat.DATATYPES else None
    kind = (g.get("core:description") or "").split(" ", 1)[0] or None
    return {"name": base, "kind": kind, "freq_hz": c.get("core:frequency"), "start_utc": c.get("core:datetime"),
            "seconds": round(n / rate, 2) if n and rate else None, "bytes": size,
            "time_source": g.get("gpstime:time_source"), "time_offset_bound_s": g.get("gpstime:time_offset_bound_s"),
            "sample_time_uncertainty_s": g.get("gpstime:sample_time_uncertainty_s"),
            "signed": bool(g.get("gpstime:signature")),
            "files": ["sigmf-meta", "sigmf-data"] + (["wav"] if g.get("core:datatype") == "ri16_le" else [])}


def status():
    """The /api/clips answer."""
    s = settings()
    d = s["dir"]
    problem = storage_problem(d)
    clips = []
    if not problem:
        for base, paths in _clip_files(d).items():
            row = _summary(base, paths)
            if row:
                clips.append(row)
    clips.sort(key=lambda r: r["start_utc"] or "", reverse=True)
    pending = None
    last = None
    try:
        pending = json.loads((Path(d) / ".pending.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    try:
        last = json.loads((Path(d) / ".last.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    used = None if problem else used_bytes(d)
    return {"storage": {"dir": str(d), "kind": "custom" if s["custom"] else "ram", "max_mb": s["max_mb"],
                        "used": q(used, "bytes", "observed"), "problem": problem},
            "pending": pending, "last": last, "clips": clips,
            "kinds": list(KINDS), "iq_rates": list(IQ_RATES), "max_seconds": MAX_SECONDS, "freq_range_hz": list(FREQ_RANGE),
            "note": "Recorded from rtl_tcp (the SDR stack's PPS-role dongle), one at a time; the oldest go first at the cap."}


def file_for(name, ext):
    """(path, content type, bytes or None for the file itself) for a download; ClipError 404 otherwise."""
    if not isinstance(name, str) or not NAME_RE.match(name) or ext not in EXTS:
        raise ClipError("no such file", 404)
    d = Path(settings()["dir"])
    paths = _clip_files(d).get(name)
    if not paths:
        raise ClipError("no such clip", 404)
    if ext == "wav":
        meta = json.loads((d / f"{name}.sigmf-meta").read_text(encoding="utf-8"))
        if meta["global"].get("core:datatype") != "ri16_le":
            raise ClipError("only audio clips have a WAV", 404)
        pcm = (d / f"{name}.sigmf-data").read_bytes()
        rate = int(meta["global"]["core:sample_rate"])
        head = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16) \
            + b"data" + struct.pack("<I", len(pcm))
        return f"{name}.wav", "audio/wav", head + pcm
    p = d / f"{name}.{ext}"
    if not p.is_file():
        raise ClipError("no such file", 404)
    if ext == "sigmf-meta":
        body = p.read_bytes()
        try:
            meta, changed = redacted_meta(json.loads(body.decode("utf-8")), config.load())
        except (UnicodeDecodeError, ValueError):
            raise ClipError("unreadable metadata", 404) from None
        if changed:
            body = (json.dumps(meta, indent=2, sort_keys=True) + "\n").encode("utf-8")
        return p.name, "application/json", body
    return p.name, "application/octet-stream", p.read_bytes()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Capped clip recording (the recorder unit runs `record`).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("record", help="record the queued clip (gps-time-clip.service)")
    a = ap.parse_args(argv)
    if a.cmd == "record":
        return run_pending()
    return 2


if __name__ == "__main__":
    sys.exit(main())
