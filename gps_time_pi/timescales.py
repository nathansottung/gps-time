"""Time scales derived from the system clock: TAI, GPS time, MJD/JD, and the
leap-second table they depend on.

Every scale here is `calculated` from the station's UTC clock, so it is only as
good as that clock (see the timing chain for what disciplines it). The offsets
TAI-UTC and GPS-UTC come from a leap-second table, which is `external` data
(IERS, as packaged by the operating system) with an expiry date. Nothing here
uses the network, and nothing here sets or adjusts the clock.

UT1-UTC needs IERS Earth-orientation data. It is reported only when the
operator has placed a cached file on the station; the station never fetches it.
"""

import os
import re
from datetime import datetime, timedelta, timezone

from .labels import q

NTP_UNIX_OFFSET = 2208988800          # seconds from 1900-01-01 to 1970-01-01
GPS_EPOCH_UNIX = 315964800            # 1980-01-06T00:00:00Z
TAI_GPS_S = 19                        # TAI - GPS, fixed
MJD_UNIX_EPOCH = 40587                # MJD of 1970-01-01
JD_MJD = 2400000.5
EXPIRY_WARN_DAYS = float(os.environ.get("GTP_LEAP_EXPIRY_WARN_DAYS", "60"))

LEAP_FILES = [p for p in os.environ.get(
    "GTP_LEAP_SECONDS_FILE", "/usr/share/zoneinfo/leap-seconds.list").split(os.pathsep) if p]
IERS_FILE = os.environ.get("GTP_IERS_FILE", "/opt/gps-time-pi/iers/finals2000A.daily")
IERS_MAX_GAP_DAYS = 1.0

# TAI-UTC since 1972, as (first UTC day it applies, seconds). Used only when
# the operating system's leap-second file can't be read. It has no expiry
# information: a leap second announced after 2017-01-01 is not in it.
BUILTIN_LEAPS = (
    ("1972-01-01", 10), ("1972-07-01", 11), ("1973-01-01", 12), ("1974-01-01", 13),
    ("1975-01-01", 14), ("1976-01-01", 15), ("1977-01-01", 16), ("1978-01-01", 17),
    ("1979-01-01", 18), ("1980-01-01", 19), ("1981-07-01", 20), ("1982-07-01", 21),
    ("1983-07-01", 22), ("1985-07-01", 23), ("1988-01-01", 24), ("1990-01-01", 25),
    ("1991-01-01", 26), ("1992-07-01", 27), ("1993-07-01", 28), ("1994-07-01", 29),
    ("1996-01-01", 30), ("1997-07-01", 31), ("1999-01-01", 32), ("2006-01-01", 33),
    ("2009-01-01", 34), ("2012-07-01", 35), ("2015-07-01", 36), ("2017-01-01", 37),
)


def _iso(unix_s):
    # not fromtimestamp(): it rejects dates before 1970 on some platforms
    return (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=unix_s)).isoformat(timespec="seconds")


def _builtin_entries():
    return [(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp(), s)
            for d, s in BUILTIN_LEAPS]


def parse_leap_seconds_list(text):
    """NIST/IERS `leap-seconds.list` -> {'entries': [(unix_s, tai_utc_s)],
    'updated': unix_s|None, 'expires': unix_s|None}. Raises ValueError if the
    text has no entries."""
    entries, updated, expires = [], None, None
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^#([$@])\s+(\d+)", line)
        if m:
            value = int(m.group(2)) - NTP_UNIX_OFFSET
            if m.group(1) == "$":
                updated = value
            else:
                expires = value
            continue
        if not line or line.startswith("#"):
            continue
        f = line.split()
        if len(f) >= 2 and f[0].isdigit() and re.fullmatch(r"-?\d+", f[1]):
            entries.append((int(f[0]) - NTP_UNIX_OFFSET, int(f[1])))
    if not entries:
        raise ValueError("no leap-second entries")
    entries.sort()
    return {"entries": entries, "updated": updated, "expires": expires}


def load_leap_table(paths=None):
    """The leap-second table to use: the first readable file, else the
    built-in list. Never raises."""
    problems = []
    for path in LEAP_FILES if paths is None else paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                table = parse_leap_seconds_list(f.read())
        except OSError as e:
            problems.append(f"{path}: {e.strerror or e}")
            continue
        except ValueError as e:
            problems.append(f"{path}: {e}")
            continue
        return {**table, "source": "file", "path": path, "problems": problems}
    return {"entries": _builtin_entries(), "updated": None, "expires": None,
            "source": "builtin", "path": None, "problems": problems}


def tai_minus_utc(table, unix_s):
    """TAI-UTC in whole seconds at a UTC instant; None before the table starts."""
    value = None
    for start, seconds in table["entries"]:
        if unix_s >= start:
            value = seconds
        else:
            break
    return value


def leap_status(table, unix_s, chrony_leap=None, warn_days=None):
    """What is known about the leap-second table at `unix_s`."""
    warn_days = EXPIRY_WARN_DAYS if warn_days is None else warn_days
    entries = table["entries"]
    past = [e for e in entries if e[0] <= unix_s]
    future = [e for e in entries if e[0] > unix_s]
    expires = table["expires"]
    if table["source"] == "builtin":
        status = "UNKNOWN"
        warning = ("No leap-second file could be read; a built-in list ending 2017-01-01 is used. "
                   "It has no expiry date, so a later leap second would not be known.")
    elif expires is None:
        status, warning = "UNKNOWN", "The leap-second file has no expiry line."
    elif unix_s >= expires:
        status = "EXPIRED"
        warning = (f"The leap-second file expired on {_iso(expires)[:10]}. TAI and GPS time assume no leap "
                   f"second since then. Update the tzdata package.")
    elif (expires - unix_s) / 86400.0 <= warn_days:
        status = "EXPIRES_SOON"
        warning = (f"The leap-second file expires in {int((expires - unix_s) // 86400)} days "
                   f"({_iso(expires)[:10]}). Update the tzdata package before then.")
    else:
        status, warning = "OK", None

    nxt = None
    if future:
        start, seconds = future[0]
        before = past[-1][1] if past else None
        nxt = {"utc": _iso(start), "tai_utc_s": seconds,
               "kind": None if before is None else ("insert" if seconds > before else "delete"),
               "last_second_utc": _iso(start - 1)}
    if nxt:
        next_note = None
    elif status == "OK" or status == "EXPIRES_SOON":
        next_note = f"None scheduled in the table, which is valid until {_iso(expires)[:10]}."
    else:
        next_note = "UNKNOWN: the table can't say whether one is scheduled."
    return {
        "provenance": "external",
        "source": table["source"],
        "source_label": ("IERS leap-second list from the operating system" if table["source"] == "file"
                         else "built-in list (no file could be read)"),
        "path": table["path"],
        "updated_utc": _iso(table["updated"]) if table["updated"] is not None else None,
        "expires_utc": _iso(expires) if expires is not None else None,
        "days_to_expiry": round((expires - unix_s) / 86400.0, 1) if expires is not None else None,
        "status": status,
        "warning": warning,
        "warn_days": warn_days,
        "last": {"utc": _iso(past[-1][0]), "tai_utc_s": past[-1][1]} if past else None,
        "next": nxt,
        "next_note": next_note,
        "chrony_leap_status": q(chrony_leap, None, "observed", "chrony tracking: Leap status")
                              if chrony_leap else q(None, None, "observed", "not read from chrony"),
        "problems": table["problems"],
    }


def _clock(unix_s):
    """'YYYY-MM-DD HH:MM:SS' of a second count on a scale with no leap seconds."""
    return (datetime(1970, 1, 1) + timedelta(seconds=int(unix_s))).strftime("%Y-%m-%d %H:%M:%S")


def scales(table, unix_s):
    """TAI, GPS time, MJD and JD at a UTC instant (Unix seconds). All calculated."""
    whole = int(unix_s // 1)
    tai_utc = tai_minus_utc(table, unix_s)
    note = "station UTC clock plus the leap-second table"
    out = {
        "provenance": "calculated",
        "utc": _iso(whole),
        "unix_s": whole,
        "tai_utc_s": q(tai_utc, "s", "calculated", "TAI − UTC from the leap-second table"),
        "gps_utc_s": q(None if tai_utc is None else tai_utc - TAI_GPS_S, "s", "calculated",
                       "GPS − UTC = (TAI − UTC) − 19 s"),
        "tai": None, "gps": None,
        "mjd": q(round(unix_s / 86400.0 + MJD_UNIX_EPOCH, 6), "d", "calculated", "UTC-based Modified Julian Date"),
        "jd": q(round(unix_s / 86400.0 + MJD_UNIX_EPOCH + JD_MJD, 6), "d", "calculated", "UTC-based Julian Date"),
    }
    if tai_utc is not None:
        out["tai"] = q(_clock(whole + tai_utc), None, "calculated", note)
        gps_s = whole + tai_utc - TAI_GPS_S - GPS_EPOCH_UNIX
        if gps_s >= 0:
            week = gps_s // 604800
            out["gps"] = {"time": q(_clock(whole + tai_utc - TAI_GPS_S), None, "calculated", note),
                          "week": q(week, None, "calculated", "weeks since 1980-01-06, not rolled over"),
                          "week_mod_1024": q(week % 1024, None, "calculated", "10-bit week number as broadcast on L1 C/A"),
                          "seconds_of_week": q(gps_s % 604800, "s", "calculated")}
    return out


# ── UT1-UTC from a cached IERS file ─────────────────────────────────────────

def parse_iers_finals(text):
    """IERS `finals2000A` fixed-width rows -> [(mjd, ut1_utc_s, 'I'|'P')],
    for rows that carry a UT1-UTC value (Bulletin A columns)."""
    rows = []
    for line in text.splitlines():
        if len(line) < 68:
            continue
        try:
            mjd = float(line[7:15])
            flag = line[57:58]
            value = float(line[58:68])
        except ValueError:
            continue
        if flag in ("I", "P"):
            rows.append((mjd, value, flag))
    return rows


def ut1(unix_s, path=None):
    """UT1-UTC at a UTC instant from the cached IERS file, if there is one.
    The file is external data; the station never downloads it."""
    path = IERS_FILE if path is None else path
    base = {"available": False, "provenance": "external", "path": path,
            "ut1_utc_s": None, "kind": None, "file_date_utc": None, "reason": None}
    try:
        mtime = os.stat(path).st_mtime
        with open(path, encoding="ascii", errors="replace") as f:
            rows = parse_iers_finals(f.read())
    except OSError:
        return {**base, "reason": "No cached IERS file on the station. UT1 − UTC needs IERS data from the "
                                  "Internet, which the station does not fetch."}
    base["file_date_utc"] = _iso(mtime)
    if not rows:
        return {**base, "reason": "The cached IERS file has no UT1 − UTC rows that could be read."}
    mjd = unix_s / 86400.0 + MJD_UNIX_EPOCH
    before = [r for r in rows if r[0] <= mjd]
    after = [r for r in rows if r[0] > mjd]
    if not before or not after or mjd - before[-1][0] > IERS_MAX_GAP_DAYS or after[0][0] - mjd > IERS_MAX_GAP_DAYS:
        return {**base, "reason": f"The cached IERS file (MJD {rows[0][0]:.0f} to {rows[-1][0]:.0f}) "
                                  f"does not cover today."}
    (m0, v0, f0), (m1, v1, f1) = before[-1], after[0]
    if abs(v1 - v0) > 0.5:
        # a leap second lies between the two rows: UT1-UTC jumps by 1 s, so don't interpolate across it
        value = v0
    else:
        value = v0 + (v1 - v0) * (mjd - m0) / (m1 - m0)
    predicted = "P" in (f0, f1)
    return {**base, "available": True, "ut1_utc_s": round(value, 7),
            "kind": "predicted by IERS" if predicted else "IERS determination",
            "note": "interpolated between the daily values in the cached file"}


def report(unix_s, chrony_leap=None, leap_paths=None, iers_path=None):
    """The /api/timescales payload."""
    table = load_leap_table(leap_paths)
    return {**scales(table, unix_s),
            "leap_seconds": leap_status(table, unix_s, chrony_leap),
            "ut1": ut1(unix_s, iers_path)}
