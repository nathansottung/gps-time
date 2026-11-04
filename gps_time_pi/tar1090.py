"""The live aircraft map: tar1090 on readsb's 1090 MHz data, served by the web service (docs/deploy/sdr-stack.md).

tar1090 is a static web page (wiedehopf/tar1090, pinned by commit in scripts/sdr-stack.sh) that
reads readsb's JSON files. The installer puts the page in HTML_DIR; this module serves it at
/tar1090/, on the station's own port, so the map needs no new listener and stays on the LAN like
the rest of the station (Host checks; no outside host is ever fetched by the station).

  /tar1090/<file>                  the page, from HTML_DIR (path-checked; nothing outside it)
  /tar1090/data/aircraft.json      readsb's live file from DATA_DIR (/run/readsb, RAM)
  /tar1090/data/history_<n>.json   readsb's history files, the same
  /tar1090/data/receiver.json      readsb's, with the station's position set by the privacy mode:
                                   exact, rounded to 0.1 degree, or none in hidden mode (no marker,
                                   no range rings). readsb itself is never given a position.

While the web SDR runs, readsb is stopped (it shares the dongle), so aircraft.json goes stale:
status() reports tracking as paused, and readsb comes back when the web SDR stops.

The browser loads map tiles from the tile servers the page names (OpenStreetMap by default):
that is the viewer's browser, not the station, and is said on the Aviation page.
"""
import base64
import hashlib
import json
import os
import re
import time

from . import config

HTML_DIR = os.environ.get("GTP_TAR1090_HTML", "/usr/local/share/gps-time-tar1090/html")
DATA_DIR = os.environ.get("GTP_READSB_JSON", "/run/readsb")
PREFIX = "/tar1090/"
DATA_RE = re.compile(r"^(aircraft|history_\d{1,3})\.json$")
STALE_S = 30.0
TYPES = {
    ".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".json": "application/json",
    ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon", ".gif": "image/gif",
    ".jpg": "image/jpeg", ".webp": "image/webp", ".woff2": "font/woff2", ".woff": "font/woff",
    ".txt": "text/plain", ".csv": "text/csv", ".geojson": "application/json",
}
INLINE_SCRIPT = re.compile(rb"<script>(.*?)</script>", re.S)
# The map page's own policy: its scripts from here (two inline ones by hash), its tiles from
# wherever the chosen layer lives (the viewer's browser fetches them), data from here only.
CSP_BASE = ("default-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; connect-src 'self' https:; "
            "worker-src 'self' blob:; font-src 'self' data:")


def installed():
    return os.path.isfile(os.path.join(HTML_DIR, "index.html"))


def static(rel):
    """(path, content type) for rel inside HTML_DIR, or None (missing, not a file, outside it)."""
    if "\x00" in rel:
        return None
    root = os.path.realpath(HTML_DIR)
    full = os.path.realpath(os.path.join(root, rel or "index.html"))
    try:
        inside = os.path.commonpath([root, full]) == root
    except ValueError:
        inside = False
    if not inside or not os.path.isfile(full):
        return None
    return full, TYPES.get(os.path.splitext(full)[1].lower(), "application/octet-stream")


def gzipped(rel, body):
    """True for a stored-gzipped database file (db-<version>/...), which goes out as Content-Encoding: gzip."""
    return rel.startswith("db-") and body[:2] == b"\x1f\x8b"


def csp_for(html):
    """The page's CSP: its inline scripts allowed by their SHA-256, nothing else inline."""
    hashes = " ".join("'sha256-" + base64.b64encode(hashlib.sha256(m).digest()).decode() + "'"
                      for m in INLINE_SCRIPT.findall(html))
    return CSP_BASE + "; script-src 'self'" + (" " + hashes if hashes else "")


def site_for_map(cfg):
    """{lat, lon} the map may show for the station, or None (hidden mode, no survey)."""
    site, _mode = config.privacy_site(cfg, (cfg or {}).get("site"))
    if not site or site.get("lat") is None or site.get("lon") is None:
        return None
    return {"lat": site["lat"], "lon": site["lon"]}


def receiver(cfg, data_dir=None):
    """readsb's receiver.json with the position replaced by what the privacy mode allows."""
    try:
        with open(os.path.join(data_dir or DATA_DIR, "receiver.json"), encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        doc = {"version": "unknown", "refresh": 1000, "history": 0}
    if not isinstance(doc, dict):
        doc = {}
    for k in ("lat", "lon", "latitude", "longitude"):
        doc.pop(k, None)
    site = site_for_map(cfg)
    if site:
        doc["lat"], doc["lon"] = site["lat"], site["lon"]
    return json.dumps(doc).encode()


def data(name, cfg, data_dir=None):
    """Bytes of a data file the page asks for, or None."""
    if name == "receiver.json":
        return receiver(cfg, data_dir)
    if not DATA_RE.match(name):
        return None
    try:
        with open(os.path.join(data_dir or DATA_DIR, name), "rb") as f:
            return f.read()
    except OSError:
        return None


def status(cfg, websdr_active=None, data_dir=None, now=None):
    """/api/aircraft-map: is the map installed, is readsb's data fresh, is tracking paused."""
    now = time.time() if now is None else now
    path = os.path.join(data_dir or DATA_DIR, "aircraft.json")
    age, count = None, None
    try:
        age = round(max(0.0, now - os.path.getmtime(path)), 1)
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        count = len(doc.get("aircraft") or []) if isinstance(doc, dict) else None
    except (OSError, ValueError):
        pass
    mode = (cfg or {}).get("location_display", "exact")
    if websdr_active:
        state = "paused"
    elif age is None:
        state = "no_data"
    elif age > STALE_S:
        state = "stale"
    else:
        state = "live"
    return {
        "installed": installed(), "url": PREFIX, "state": state,
        "aircraft_json_age_s": age, "aircraft": count,
        "station_marker": mode != "hidden" and site_for_map(cfg) is not None,
        "location_display": mode,
        "note": ("tar1090 on readsb's 1090 MHz data, served by the station on the LAN. While the web SDR runs it has the "
                 "dongle, so tracking pauses and resumes when it stops. The viewer's browser loads map tiles from the "
                 "chosen map layer's servers (OpenStreetMap by default)."),
    }
