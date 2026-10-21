"""Convert observation files (SigMF + gpstime:) to WAV and miniSEED.

Converters, not replacements (SPEC-OBSERVATION-FORMAT-AND-TASKING, "Export to
domain formats"): the observation file stays the record.

WAV (audio and IQ), python -m gps_time_pi.convert wav <base> <out_base>
- 16-bit PCM: mono for real samples, stereo I/Q for complex. Floats are scaled
  so the largest sample is full scale; cu8 is re-centred; int16 is kept as is.
- A sidecar <out_base>.sigmf-meta points at <out_base>.wav (core:dataset, with
  core:header_bytes 44). Its captures are the original's, so every sample keeps
  its UTC time exactly. It records gpstime:derived_from (source checksum and
  method) and the scale in gpstime:calibration. The original signature doesn't
  carry over: --sign signs the sidecar with this station's key.
- WAV holds an integer sample rate; the sidecar keeps the exact one.

miniSEED (seismic, infrasound, other real samples), python -m gps_time_pi.convert miniseed <base> <out>
- miniSEED 2, 512-byte records, big-endian. ri16_le samples as INT32
  (encoding 3), rf32_le as FLOAT32 (encoding 4). Complex data is refused.
- Every record's start time comes from the observation's timing for its first
  sample, so drift and gaps are carried, not smoothed: samples without a time
  are left out (a gap). BTIME (0.1 ms) plus blockette 1001 gives the time to
  1 µs; finer resolution is lost. Blockette 100 carries the measured sample
  rate; the header carries the nominal (integer) rate.
- I/O flag "clock locked" is set when the time source is pps or pps_marker.
  Timing quality in blockette 1001 is left 0 (not set); the uncertainty stays
  in the observation file.
- A small JSON note, <out>.gpstime.json, keeps what miniSEED has no field for:
  station ID, source checksum and signature, uncertainties, provenance.
"""

import argparse
import calendar
import json
import math
import re
import struct
import sys
import time
import wave
from pathlib import Path

from . import obsformat as of

WAV_HEADER = 44
MSEED_RECORD = 512
MSEED_DATA_OFFSET = 128     # 48 header + B1000 (8) + B1001 (8) + B100 (12) = 76, data on a 64-byte boundary
_CODE = {"network": r"^[A-Z0-9]{1,2}$", "station": r"^[A-Z0-9]{1,5}$", "location": r"^[A-Z0-9]{0,2}$",
         "channel": r"^[A-Z0-9]{3}$"}


class ConvertError(Exception):
    pass


# ---------------------------------------------------------------- WAV

def _to_int16(meta, data):
    """(int16 samples flat, channels, scale): I and Q interleaved for complex."""
    dt = meta["global"]["core:datatype"]
    samples = of.decode(data, dt)
    cplx = of.DATATYPES[dt][1]
    flat = [v for z in samples for v in (z.real, z.imag)] if cplx else list(samples)
    if dt in ("ci16_le", "ri16_le"):
        scale, ints = 1.0, [int(v) for v in flat]
    elif dt == "cu8":
        scale, ints = 256.0, [max(-32768, min(32767, int(round((v - 127.5) * 256)))) for v in flat]
    else:
        peak = max((abs(v) for v in flat), default=0.0)
        scale = 32767.0 / peak if peak > 0 else 1.0
        ints = [max(-32768, min(32767, int(round(v * scale)))) for v in flat]
    return ints, (2 if cplx else 1), scale


def to_wav(base, out_base, signer=None):
    """Write <out_base>.wav and its sidecar <out_base>.sigmf-meta. Returns both paths."""
    meta, data = of.read(base)
    errs, _ = of.validate_meta(meta, data)
    if errs:
        raise ConvertError("source is not a valid observation: " + "; ".join(errs))
    ints, channels, scale = _to_int16(meta, data)
    out_base = Path(out_base)
    wav_path = out_base.with_name(out_base.name + ".wav")
    pcm = struct.pack(f"<{len(ints)}h", *ints)
    rate = meta["global"]["core:sample_rate"]
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(max(1, int(round(rate))))
        w.writeframes(pcm)
    if len(wav_path.read_bytes()) != WAV_HEADER + len(pcm):
        raise ConvertError("unexpected WAV header size")

    g = meta["global"]
    side = json.loads(json.dumps(meta))
    sg = side["global"]
    src_dt = g["core:datatype"]
    sg["core:datatype"] = "ci16_le" if channels == 2 else "ri16_le"
    sg["core:dataset"] = wav_path.name
    sg["gpstime:derived_from"] = {
        "checksum": g["gpstime:checksum"], "station_id": g["gpstime:station_id"],
        "signature": g.get("gpstime:signature"),
        "method": f"WAV 16-bit PCM from {src_dt}" + (f", samples x {scale:.9g}" if scale != 1.0 else ""),
    }
    cal = sg.get("gpstime:calibration") or {}
    cal = dict(cal, wav_scale=scale, wav_scale_note="stored value = sample x wav_scale")
    if src_dt == "cu8":
        cal["wav_offset"] = 127.5
    sg["gpstime:calibration"] = cal
    side["captures"][0]["core:header_bytes"] = WAV_HEADER
    sg["gpstime:public_key"] = None
    meta_path = out_base.with_name(out_base.name + ".sigmf-meta")
    _, meta_bytes = of.to_bytes(side, pcm, signer)
    of._atomic_write(meta_path, meta_bytes)
    return wav_path, meta_path


# ---------------------------------------------------------------- miniSEED

def _rate_factor(rate):
    r = round(rate)
    if r < 1 or abs(rate - r) > 1e-9 * max(1.0, rate):
        raise ConvertError(f"miniSEED needs an integer nominal sample rate, not {rate}")
    for m in range(1, 32768):
        if r % m == 0 and r // m <= 32767:
            return r // m, m
    raise ConvertError(f"sample rate {rate} can't be written as a miniSEED rate factor")


def btime(ns):
    """(BTIME bytes, microsecond offset for blockette 1001) of a UTC time in ns.
    BTIME holds 0.1 ms; the offset (-50..49 µs) carries the rest."""
    total_us = ns // 1000
    t100 = (total_us + 50) // 100
    usec = total_us - t100 * 100
    sec, frac = divmod(t100, 10_000)
    t = time.gmtime(sec)
    return struct.pack(">HHBBBBH", t.tm_year, t.tm_yday, t.tm_hour, t.tm_min, t.tm_sec, 0, frac), usec


def _record(seq, codes, start_ns, rate_fm, actual_rate, encoding, values, clock_locked):
    bt, usec = btime(start_ns)
    hdr = struct.pack(">6sc c5s2s3s2s", f"{seq:06d}".encode(), b"D", b" ",
                      codes["station"].ljust(5).encode(), codes["location"].ljust(2).encode(),
                      codes["channel"].encode(), codes["network"].ljust(2).encode())
    hdr += bt
    hdr += struct.pack(">HhhBBBBiHH", len(values), rate_fm[0], rate_fm[1], 0,
                       0x20 if clock_locked else 0, 0, 3, 0, MSEED_DATA_OFFSET, 48)
    b1000 = struct.pack(">HHBBBB", 1000, 56, encoding, 1, int(math.log2(MSEED_RECORD)), 0)
    b1001 = struct.pack(">HHBbBB", 1001, 64, 0, usec, 0, 0)
    b100 = struct.pack(">HHfb3s", 100, 0, float(actual_rate), 0, b"\0\0\0")
    head = hdr + b1000 + b1001 + b100
    body = struct.pack(f">{len(values)}{'i' if encoding == 3 else 'f'}", *values)
    rec = head + b"\0" * (MSEED_DATA_OFFSET - len(head)) + body
    return rec + b"\0" * (MSEED_RECORD - len(rec))


def to_miniseed(base, out, *, network, station, location, channel):
    """Write the observation's timed samples as miniSEED 2. Returns (path, records written)."""
    codes = {"network": network, "station": station, "location": location, "channel": channel}
    for k, v in codes.items():
        if not re.match(_CODE[k], v or ""):
            raise ConvertError(f"{k} code {v!r} isn't valid for miniSEED ({_CODE[k]})")
    meta, data = of.read(base)
    errs, _ = of.validate_meta(meta, data)
    if errs:
        raise ConvertError("source is not a valid observation: " + "; ".join(errs))
    g = meta["global"]
    dt = g["core:datatype"]
    if of.DATATYPES[dt][1]:
        raise ConvertError("miniSEED holds real samples; this observation is complex (IQ)")
    encoding = 3 if dt == "ri16_le" else 4
    per_rec = (MSEED_RECORD - MSEED_DATA_OFFSET) // 4
    samples = of.decode(data, dt)
    if encoding == 3:
        samples = [int(v) for v in samples]
    rate_fm = _rate_factor(g["core:sample_rate"])
    locked = g["gpstime:time_source"] in ("pps", "pps_marker")
    caps = meta["captures"]
    n = len(samples)
    out = Path(out)
    records = []
    for i, c in enumerate(caps):
        if c.get("gpstime:time_valid") is False or "core:datetime" not in c:
            continue
        start = c["core:sample_start"]
        end = caps[i + 1]["core:sample_start"] if i + 1 < len(caps) else n
        rate = c.get("gpstime:sample_rate", g["core:sample_rate"])
        for s in range(start, end, per_rec):
            chunk = samples[s:min(end, s + per_rec)]
            t_ns, _ = of.sample_time(meta, s)
            records.append(_record(len(records) + 1, codes, t_ns, rate_fm, rate, encoding, chunk, locked))
    if not records:
        raise ConvertError("no sample in the observation has a time; nothing to write")
    of._atomic_write(out, b"".join(records))
    note = {"source_checksum": g["gpstime:checksum"], "source_signature": g.get("gpstime:signature"),
            "station_id": g["gpstime:station_id"], "time_source": g["gpstime:time_source"],
            "time_offset_bound_s": g["gpstime:time_offset_bound_s"],
            "sample_time_uncertainty_s": g["gpstime:sample_time_uncertainty_s"],
            "provenance": g["gpstime:provenance"], "quantity": g["gpstime:quantity"], "unit": g["gpstime:unit"],
            "method": f"miniSEED 2, {MSEED_RECORD}-byte records, {'INT32' if encoding == 3 else 'FLOAT32'}; "
                      "record times from the observation's captures, to 1 µs; untimed samples left out",
            "records": len(records)}
    of._atomic_write(out.with_name(out.name + ".gpstime.json"), (json.dumps(note, indent=2) + "\n").encode())
    return out, len(records)


def read_miniseed(path):
    """Records of a file written by to_miniseed (for checks): codes, start ns, rates, samples."""
    raw = Path(path).read_bytes()
    out = []
    for off in range(0, len(raw), MSEED_RECORD):
        r = raw[off:off + MSEED_RECORD]
        seq, q, _, sta, loc, cha, net = struct.unpack(">6sc c5s2s3s2s", r[:20])
        year, doy, hh, mm, ss, _, frac = struct.unpack(">HHBBBBH", r[20:30])
        nsamp, fac, mul, act, io, dq, nblk, tcorr, dstart, blk = struct.unpack(">HhhBBBBiHH", r[30:48])
        rec = {"sequence": int(seq), "quality": q.decode(), "station": sta.decode().strip(),
               "location": loc.decode().strip(), "channel": cha.decode(), "network": net.decode().strip(),
               "samples_n": nsamp, "rate_factor": fac, "rate_multiplier": mul, "io_flags": io,
               "blockettes": nblk, "data_offset": dstart}
        usec = 0
        while blk:
            btype, nxt = struct.unpack(">HH", r[blk:blk + 4])
            if btype == 1000:
                rec["encoding"], rec["word_order"], rec["record_exp"] = struct.unpack(">BBB", r[blk + 4:blk + 7])
            elif btype == 1001:
                rec["timing_quality"], usec = struct.unpack(">Bb", r[blk + 4:blk + 6])
            elif btype == 100:
                rec["actual_rate"] = struct.unpack(">f", r[blk + 4:blk + 8])[0]
            blk = nxt
        start_s = calendar.timegm((year, 1, 1, hh, mm, ss, 0, 0, 0)) + (doy - 1) * 86400
        rec["start_ns"] = start_s * 1_000_000_000 + frac * 100_000 + usec * 1000
        fmt = ">%d%s" % (nsamp, "i" if rec["encoding"] == 3 else "f")
        rec["samples"] = list(struct.unpack(fmt, r[dstart:dstart + 4 * nsamp]))
        out.append(rec)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m gps_time_pi.convert", description="Observation files to WAV or miniSEED.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wav")
    w.add_argument("base")
    w.add_argument("out_base")
    w.add_argument("--sign", action="store_true", help="sign the sidecar with this station's key")
    m = sub.add_parser("miniseed")
    m.add_argument("base")
    m.add_argument("out")
    m.add_argument("--net", required=True)
    m.add_argument("--sta", required=True)
    m.add_argument("--loc", default="")
    m.add_argument("--cha", required=True)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "wav":
            signer = None
            if a.sign:
                from . import station_key
                signer = station_key.load()
            wav_path, meta_path = to_wav(a.base, a.out_base, signer)
            print(f"wrote {wav_path} and {meta_path}")
        else:
            path, n = to_miniseed(a.base, a.out, network=a.net, station=a.sta, location=a.loc, channel=a.cha)
            print(f"wrote {path} ({n} records)")
    except (ConvertError, OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
