"""Get orbital elements (TLEs) into the station's offline cache.

This is the only part of the satellite layer that uses the network, and it
runs only when someone runs it. The web service never does.

    cd /opt/gps-time-pi
    sudo -u gps-time venv/bin/python -m gps_time_pi.tle_fetch --group stations
    sudo -u gps-time venv/bin/python -m gps_time_pi.tle_fetch --file /tmp/my.tle --name mine

--group NAME   download CelesTrak's group NAME (stations, visual, starlink, ...)
--file PATH    import a TLE file that is already on this machine (no network)
--name NAME    cache name for --file (default: the file's name)
--dir DIR      cache directory (default: GTP_TLE_DIR, else tle/ next to config.json)
--force        download even if this group was fetched less than two hours ago
--list         show what is in the cache and how old it is

The text is checked before it replaces anything: it must contain at least one
element set with valid checksums. The file is written beside the old one and
renamed, so a failed download never leaves the cache empty or half-written.
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

from . import satellites

URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=tle"
MAX_BYTES = 20 * 1024 * 1024
MIN_REFETCH_S = 2 * 3600       # CelesTrak updates a group at most every two hours
TIMEOUT_S = 30


def download(url, timeout=TIMEOUT_S, max_bytes=MAX_BYTES):
    req = urllib.request.Request(url, headers={"User-Agent": "gps-time-pi tle_fetch"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — fixed https URL
        data = r.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"more than {max_bytes} bytes; refused")
    return data.decode("ascii", errors="replace")


def _write_atomic(path, text):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding="ascii", errors="replace", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _manifest(directory):
    try:
        with open(os.path.join(directory, satellites.MANIFEST), encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def store(directory, name, text, source, now=None):
    """Validate TLE text and put it in the cache as <name>.tle.
    Returns the number of element sets. Raises ValueError if there are none."""
    if not satellites.valid_group(name):
        raise ValueError(f"'{name}' is not a usable cache name (lower-case letters, digits, hyphens)")
    sets, rejected = satellites.parse_tle_text(text)
    if not sets:
        raise ValueError("no valid element sets in the data (not a TLE file, or an error page); the cache is unchanged")
    now = datetime.now(timezone.utc) if now is None else now
    os.makedirs(directory, exist_ok=True)
    body = "".join(f"{s['name']}\n{s['line1']}\n{s['line2']}\n" for s in sets)
    _write_atomic(os.path.join(directory, name + ".tle"), body)
    manifest = _manifest(directory)
    manifest[name] = {"source": source, "fetched_utc": now.isoformat(timespec="seconds"),
                      "count": len(sets), "rejected": rejected,
                      "sha256": hashlib.sha256(body.encode("ascii", errors="replace")).hexdigest()}
    _write_atomic(os.path.join(directory, satellites.MANIFEST), json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return len(sets)


def fetch_group(directory, group, force=False, fetch=download, now=None):
    """Download one CelesTrak group into the cache. Returns the number of sets."""
    if not satellites.valid_group(group):
        raise ValueError(f"'{group}' is not a group name (lower-case letters, digits, hyphens)")
    now = datetime.now(timezone.utc) if now is None else now
    last = (_manifest(directory).get(group) or {}).get("fetched_utc")
    if last and not force:
        try:
            age = (now - datetime.fromisoformat(last)).total_seconds()
        except ValueError:
            age = None
        if age is not None and 0 <= age < MIN_REFETCH_S:
            raise ValueError(f"'{group}' was fetched {age / 60:.0f} minutes ago; the source updates at most every "
                             f"two hours. Use --force to fetch anyway.")
    url = URL.format(group=group)
    return store(directory, group, fetch(url), url, now)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m gps_time_pi.tle_fetch", description=__doc__.split("\n")[0])
    ap.add_argument("--group", action="append", default=[], help="CelesTrak group to download (repeatable)")
    ap.add_argument("--file", help="import a local TLE file instead of downloading")
    ap.add_argument("--name", help="cache name for --file")
    ap.add_argument("--dir", default=satellites.TLE_DIR, help="cache directory")
    ap.add_argument("--force", action="store_true", help="ignore the two-hour limit")
    ap.add_argument("--list", action="store_true", help="show the cache")
    a = ap.parse_args(argv)
    status = 0
    try:
        if a.file:
            name = a.name or os.path.splitext(os.path.basename(a.file))[0].lower()
            with open(a.file, encoding="ascii", errors="replace") as f:
                n = store(a.dir, name, f.read(), f"file:{os.path.basename(a.file)}")
            print(f"{name}: {n} element sets imported into {a.dir}")
        for group in a.group:
            try:
                n = fetch_group(a.dir, group, a.force)
                print(f"{group}: {n} element sets saved in {a.dir}")
            except (OSError, ValueError) as e:
                print(f"{group}: not updated: {e}", file=sys.stderr)
                status = 1
    except (OSError, ValueError) as e:
        print(f"not imported: {e}", file=sys.stderr)
        status = 1
    if a.list or not (a.file or a.group):
        cache = satellites.load_cache(a.dir)
        info = satellites.summary(cache, datetime.now(timezone.utc))
        print(f"Cache {info['dir']}: {info['satellites']} satellites")
        for g in info["groups"]:
            print(f"  {g['group']}: {g['count']} sets, newest epoch {g['newest_epoch_utc']}, "
                  f"fetched {g['fetched_utc'] or 'unknown'} from {g['source'] or 'unknown'}")
        if info["newest_age_days"] is not None:
            print(f"  newest elements are {info['newest_age_days']} days old")
        for p in info["problems"]:
            print(f"  problem: {p}")
    return status


if __name__ == "__main__":
    sys.exit(main())
