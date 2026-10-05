"""GPS Time Pi web server.

Routes:
  /            main status page
  /almanac     sun/moon/object/sky page
  /history     offset + uncertainty convergence chart
  /zones       all IANA timezones with current offsets
  /time        plain-text UTC timestamp
  /api         core status JSON (never depends on the astronomy layer)
  /api/almanac /api/object /api/history
  /api/setting?location_display=exact|rounded|hidden
  /api/timing-chain  GNSS -> PPS -> chrony stage-by-stage status, PPS state, events (JSON)
  /api/diagnostics   copyable plain-text diagnostic snapshot (privacy mode applied)
  /static/*    css/js
  /app/        new web UI: the built React app from web/dist (GTP_WEB_DIST to override);
               the legacy pages above stay until the new UI reaches parity

Run: python3 -m gps_time_pi.server  (port 80 by default, GTP_PORT to override)
"""

import json
import logging
import math
import os
import re
import sys
import traceback
from datetime import date as _date
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse
from zoneinfo import ZoneInfo, available_timezones

import platform

from . import (__version__, astro, catalog, chrony, config, dashboard, demo, gps, localtime, security, system,
               timescales, timing_chain, units)

_HERE = os.path.dirname(__file__)
DEMO_MODE = os.environ.get("GTP_DEMO", "0").lower() in ("1", "true", "yes", "on")
PORT = int(os.environ.get("GTP_PORT", "8080" if DEMO_MODE else "80"))
BIND = os.environ.get("GTP_BIND", "127.0.0.1" if DEMO_MODE else "0.0.0.0")

_TPL = {}
for name in ("dashboard", "configure", "legacy", "almanac", "history", "admin"):
    with open(os.path.join(_HERE, "templates", name + ".html"), encoding="utf-8") as f:
        _TPL[name] = f.read()
# Per-page CSP: each legacy page's static inline scripts allowed by hash only.
_TPL_CSP = {name: security.csp_for_html(html) for name, html in _TPL.items()}


# Built web UI (cd web && corepack pnpm run build). Read per request, never written.
WEB_DIST = os.environ.get("GTP_WEB_DIST") or os.path.join(os.path.dirname(_HERE), "web", "dist")
WEB_PREFIX = "/app/"
_WEB_TYPES = {
    ".html": "text/html", ".js": "application/javascript", ".mjs": "application/javascript",
    ".css": "text/css", ".json": "application/json", ".map": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".webp": "image/webp",
    ".woff2": "font/woff2", ".woff": "font/woff", ".txt": "text/plain",
}
WEB_NOT_BUILT = ("The new web UI has not been built on this machine.\n"
                 "Build it with:  cd web && corepack pnpm install --frozen-lockfile && corepack pnpm run build\n"
                 "or set GTP_WEB_DIST to a directory containing a built index.html.\n"
                 "The legacy dashboard is still available at /.\n")


def web_file(rel):
    """Resolve rel inside WEB_DIST. Returns (path, ctype, cache_control), or None
    if the file does not exist, is not a regular file, or resolves outside the
    dist directory (path traversal, symlinks pointing out)."""
    root = os.path.realpath(WEB_DIST)
    full = os.path.realpath(os.path.join(root, rel))
    try:
        inside = os.path.commonpath([root, full]) == root
    except ValueError:                    # different drives on Windows
        inside = False
    if not inside or not os.path.isfile(full):
        return None
    ext = os.path.splitext(full)[1].lower()
    ctype = _WEB_TYPES.get(ext, "application/octet-stream")
    if os.path.basename(full) == "index.html":
        cache = "no-store"                # always pick up a rebuilt app
    elif os.path.relpath(full, root).replace(os.sep, "/").startswith("assets/"):
        cache = "public, max-age=31536000, immutable"   # Vite content-hashed names
    else:
        cache = "max-age=300"
    return full, ctype, cache


def cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read()) / 1000, 1)
    except Exception:  # noqa: BLE001
        return None


PRIVACY_HIDDEN_REASON = ("Location is hidden by the station's privacy setting. Sun, moon and sky "
                         "times would reveal the station's position, so they are not computed.")


def sidereal_for(cfg, site):
    """Local sidereal time under the privacy mode (LST − GST is the longitude)."""
    s, _mode = config.privacy_site(cfg, site)
    return astro.sidereal(s) if (s and astro.STATUS["available"]) else None


def _clock_label(dt, with_date=False):
    """'10:00 PM' / '10:00 PM · Oct 1, 2026 · ' without the glibc-only %-I/%-d."""
    s = f"{dt.hour % 12 or 12}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"
    return s + (f" · {dt.strftime('%b')} {dt.day}, {dt.year} · " if with_date else "")


def core_api():
    if DEMO_MODE:
        d = demo.core_api()
        cfg = config.load()
        d["location"] = config.displayed_location(cfg, DEMO_SITE)   # demo honors the privacy mode too
        d["gps"] = {**d["gps"], "sats": config.privacy_sats(cfg, d["gps"].get("sats", []))}
        if cfg.get("location_display") == "hidden":
            d["sidereal"] = None
        d["timezone"] = localtime.display_zone(cfg, DEMO_SITE)
        return d
    now = datetime.now(timezone.utc)
    trk = chrony.tracking()
    srcs = chrony.sources()
    snap = gps.snapshot()
    q = chrony.quality(trk)
    status = timing_chain.timing_status(trk, srcs, gnss=snap, refclocks=chrony.refclock_config())
    if timing_chain.SERVICE is not None and timing_chain.SERVICE.running():
        status = timing_chain.SERVICE.apply_boot_phase(status)   # ACQUIRING after boot
    state = (status["headline"], status["banner"] + (" — " + status["detail"] if status["detail"] else ""))
    cfg = config.load()
    site, provenance = (snap["live"], "live") if snap["live"] else \
        ((cfg.get("site"), "stored") if cfg.get("site") else (None, "none"))
    err = q["root_dispersion_s"]
    return {
        "epoch_ms": now.timestamp() * 1000,
        "utc": now.strftime("%Y-%m-%d %H:%M:%S.%f UTC"),
        "state": state,
        "timing_status": status,
        "quality": q,
        "fmt": {
            "system_pair": units.fmt_pair(q["system_time_s"], None) if err is None
                           else units.fmt_pair(q["system_time_s"], err),
            "rms": units.fmt_seconds(q["rms_offset_s"]),
            "root_dispersion": units.fmt_seconds(q["root_dispersion_s"]),
            "root_delay": units.fmt_seconds(q["root_delay_s"]),
        },
        "sources": srcs,
        "sourcestats": chrony.sourcestats(),
        "clients": chrony.clients(),
        "gps": {**{k: snap[k] for k in ("fix", "used", "visible", "tdop", "hdop",
                                        "last_fix", "last_fix_time", "stale", "data_age_s",
                                        "sky_stale", "sky_age_s")},
                "sats": config.privacy_sats(cfg, snap["sats"])},
        "location": config.displayed_location(cfg, snap["live"]),
        "survey": config.site_stats(cfg),
        "position_provenance": provenance,
        "sidereal": sidereal_for(cfg, site),
        # Local-time display zone. The surveyed site is preferred over a single live fix.
        "timezone": localtime.display_zone(cfg, cfg.get("site") or snap["live"]),
        "astro_available": astro.STATUS["available"],
        "astro_reason": astro.STATUS["reason"],     # why not, when unavailable; None when available
        "cpu_temp_c": cpu_temp(),
        "versions": {
            "app": __version__,
            "chrony": chrony.version(),
            "gpsd": snap.get("gpsd_version"),
            "receiver": snap.get("receiver"),
            "python": platform.python_version(),
        },
    }


def _obs_datetime(d, tzname, at):
    tz = ZoneInfo(tzname)
    if at == "now":
        return datetime.now(tz)
    m = re.match(r"^(\d{1,2}):(\d{2})", at or "")
    h, mi = (int(m.group(1)), int(m.group(2))) if m else (22, 0)
    return datetime(d.year, d.month, d.day, h, mi, tzinfo=tz)


def _astro_failure(e):
    """An astronomy calculation raised. Say so with the reason instead of a bare
    {"error": ...}, which the pages can't tell from "unavailable"; the traceback
    goes to the journal. Astronomy must never take the timing pages down."""
    traceback.print_exc()
    return {"available": False,
            "reason": f"Astronomy calculation failed ({e.__class__.__name__}: {str(e)[:200]}). "
                      "See journalctl -u gps-time-pi."}


def almanac_api(qs):
    try:
        return _almanac_api(qs)
    except Exception as e:  # noqa: BLE001
        return _astro_failure(e)


def _almanac_api(qs):
    cfg = config.load()
    if cfg.get("location_display") == "hidden":
        return {"available": False, "reason": PRIVACY_HIDDEN_REASON, "location_display": "hidden"}
    if DEMO_MODE:
        return {**demo.almanac_api(qs), "location_display": cfg.get("location_display", "exact")}
    if not astro.STATUS["available"]:
        return {"available": False, "reason": astro.STATUS["reason"]}
    try:
        d = _date.fromisoformat(qs.get("date", [""])[0])
    except ValueError:
        d = datetime.now(timezone.utc).date()
    tzname = qs.get("tz", ["UTC"])[0]
    if tzname not in available_timezones():
        tzname = "UTC"
    if not astro.date_supported(d):
        return {"available": False,
                "reason": f"Date outside supported range {astro.DATE_MIN} to {astro.DATE_MAX}"}
    site, provenance = gps.observing_site()
    if site is None:
        return {"available": False,
                "reason": "No valid location is available (no GPS fix yet and no stored site)."}
    site, mode = config.privacy_site(cfg, site)     # rounded mode: compute from the rounded site only
    obs_dt = _obs_datetime(d, tzname, qs.get("at", ["now"])[0])

    sun = astro.solar_day(d, site, tzname)
    sun_y = astro.solar_day(d - __import__("datetime").timedelta(days=1), site, tzname)
    sun_t = astro.solar_day(d + __import__("datetime").timedelta(days=1), site, tzname)
    dy, dt_ = astro.daylight_deltas(d, site, tzname)
    moon = astro.lunar_day(d, site, tzname)
    nite = astro.night(d, site, tzname)
    sky = astro.sky_snapshot(site, obs_dt, _LAST_TARGET.get("t"))

    age = None
    if provenance == "stored" and site.get("updated"):
        age = "last live fix " + str(site["updated"])
    def _neighbor(x):
        return {"sunrise": x.get("events", {}).get("sunrise"),
                "sunset": x.get("events", {}).get("sunset"),
                "noon": x.get("noon"),
                "daylight_s": x.get("daylight_s")} if x.get("available") else {}
    return {"available": True, "sun": sun, "moon": moon, "night": nite,
            "delta_yesterday": dy, "delta_tomorrow": dt_,
            "neighbors": {"yesterday": _neighbor(sun_y), "tomorrow": _neighbor(sun_t)},
            "sky": sky,
            "sky_when": _clock_label(obs_dt, with_date=True) + tzname,
            "position_provenance": provenance, "position_age": age,
            "location_display": mode}


_LAST_TARGET = {}


def object_api(qs):
    try:
        return _object_api(qs)
    except Exception as e:  # noqa: BLE001
        return _astro_failure(e)


def _object_api(qs):
    q = qs.get("q", [""])[0]
    target = catalog.lookup(q)
    if target is None:
        return {"error": "unparsed"}
    cfg = config.load()
    if cfg.get("location_display") == "hidden":
        return {"available": False, "reason": PRIVACY_HIDDEN_REASON, "location_display": "hidden"}
    if not astro.STATUS["available"]:
        return {"available": False, "reason": astro.STATUS["reason"]}
    try:
        d = _date.fromisoformat(qs.get("date", [""])[0])
    except ValueError:
        d = datetime.now(timezone.utc).date()
    tzname = qs.get("tz", ["UTC"])[0]
    if tzname not in available_timezones():
        tzname = "UTC"
    site, _prov = gps.observing_site()
    if site is None:
        return {"available": False, "reason": "No valid location is available."}
    site, mode = config.privacy_site(cfg, site)
    obs_dt = _obs_datetime(d, tzname, qs.get("at", ["now"])[0])
    _LAST_TARGET["t"] = target

    rep = astro.object_report(target, d, site, tzname, obs_dt)
    if not rep.get("available"):
        return rep
    if target["kind"] == "planet":
        rep["name"], rep["meta"], rep["emphasis"] = target["name"], "planet", "dark"
    elif target["kind"] == "fixed":
        rep["name"] = target["name"]
        rep["meta"] = target["type"] + (f", mag {target['mag']}" if target["mag"] is not None else "") \
            + (f", in {target['con']}" if target.get("con") else "")
        rep["emphasis"] = "moonless" if target["deepsky"] else "dark"
    else:
        rep["name"] = f"RA {target['ra']:.4f}°, Dec {target['dec']:+.4f}° (J2000)"
        rep["meta"] = "coordinates"
        rep["emphasis"] = "both"
    rep["at_label"] = _clock_label(obs_dt)
    rep["location_display"] = mode
    return rep


def survey_api():
    """Position-survey convergence data for the History page: the persisted
    precision curve plus this session's fixes in meters around the mean."""
    import math
    cfg = config.load()
    site = cfg.get("site") or {}
    stats = config.site_stats(cfg)
    fixes = []
    if site.get("lat") is not None:
        mlat, mlon = site["lat"], site["lon"]
        k_lat = 111320.0
        k_lon = 111320.0 * max(math.cos(math.radians(mlat)), 0.01)
        for _t, la, lo in gps.recent_fixes():
            fixes.append([round((la - mlat) * k_lat, 2),
                          round((lo - mlon) * k_lon, 2)])
    return {"available": bool(site.get("history")),
            "history": site.get("history", []),
            "fixes": fixes, "stats": stats, "ingest": gps.ingest_status(),
            "persistence": config.persistence_status(),
            "note": None if site.get("history") else
                    "Survey history builds as 3D fixes arrive (about one per minute)."}


def zones_page():
    now = datetime.now(timezone.utc)
    rows = []
    for name in sorted(available_timezones()):
        if name.startswith(("Etc/", "SystemV", "posix", "right")) or ("/" not in name and name != "UTC"):
            continue
        local = now.astimezone(ZoneInfo(name))
        mins = int(local.utcoffset().total_seconds() // 60)
        sign = "+" if mins >= 0 else "-"
        rows.append((name, f"UTC{sign}{abs(mins) // 60:02d}:{abs(mins) % 60:02d}",
                     local.strftime("%H:%M"), mins))
    rows.sort(key=lambda r: (r[3], r[0]))
    body = "".join(f"<tr><td>{n}</td><td>{o}</td><td>{t}</td></tr>" for n, o, t, _ in rows)
    head = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            "<title>Timezones</title>"
            "<script>(function(){var t=new URLSearchParams(location.search).get('theme')||"
            "localStorage.getItem('gtp-theme')||'light';document.documentElement.dataset.theme=t;})();"
            '</script><link rel="stylesheet" href="/static/style.css">'
            '<link rel="stylesheet" href="/static/custom.css"></head><body><main>'
            '<nav><a href="/">Time</a><a href="/almanac">Almanac</a>'
            '<a href="/history">History</a><a class="here" href="/zones">Zones</a>'
            '<a href="/admin">Admin</a></nav>')
    return (head + f"<p class='dim small'>Offsets include DST where currently in effect. "
            f"As of {now.strftime('%Y-%m-%d %H:%M UTC')}.</p>"
            "<table><thead><tr><th>Zone</th><th>Offset</th><th>Local time</th></tr></thead>"
            f"<tbody>{body}</tbody></table></main></body></html>")


DEMO_SITE = {"lat": 38.9217, "lon": -77.0669, "alt_msl": 92.0, "alt_hae": 59.0}


def timing_chain_payload(qs):
    if DEMO_MODE:
        return demo.timing_chain(qs.get("scenario", ["pps_selected"])[0])
    return timing_chain.service().latest()


def stability_payload():
    if DEMO_MODE:
        return demo.stability()
    return timing_chain.service().stability.report()


def timescales_payload():
    now = datetime.now(timezone.utc).timestamp()
    if DEMO_MODE:
        return demo.timescales(now)
    raw = (timing_chain.service().latest().get("raw") or {}).get("tracking")
    leap = chrony.parse_tracking(raw).get("Leap status") if raw else None
    return timescales.report(now, chrony_leap=leap)


def diagnostics_text(qs):
    chain = timing_chain_payload(qs)
    cfg = config.load()
    live = DEMO_SITE if DEMO_MODE else gps.snapshot()["live"]
    return timing_chain.diagnostic_snapshot(chain, config.displayed_location(cfg, live))


def writes_enabled():
    """Demo mode writes only under .dev/ and never runs host actions, so it needs
    no token. Otherwise every state-changing request needs the admin token, and
    admin is disabled until a token exists (security.admin_configured())."""
    return DEMO_MODE or security.admin_configured()


HOST_REFUSED = ("Host not allowed. Use the station's IP address or hostname, or add this "
                "name to GTP_ALLOWED_HOSTS (comma-separated) in the service environment.\n")
ADMIN_DISABLED = ("admin is disabled: no admin token is configured on the station "
                  "(create one with: sudo python3 -m gps_time_pi.admin_token)")
POST_ROUTES = ("/api/admin", "/api/setting", "/api/dashboard", "/api/dashboard/reset")
MAX_BODY = 256000


def auth_payload(authenticated):
    return {"demo": DEMO_MODE, "auth_required": not DEMO_MODE,
            "admin_configured": security.admin_configured(),
            "authenticated": DEMO_MODE or authenticated}


def dashboard_payload():
    cfg = dashboard.load()
    cfg["_meta"] = {
        "writable": writes_enabled(),
        "auth_required": not DEMO_MODE,
        "demo": DEMO_MODE,
        "path": str(dashboard.path()) if DEMO_MODE else None,
        "known_widgets": sorted(dashboard.KNOWN_WIDGETS),
    }
    return cfg


class Handler(BaseHTTPRequestHandler):
    _csp = None      # per-response CSP override (legacy pages); reset for every request

    def end_headers(self):
        # Security headers on every response, including send_error() pages.
        self.send_header("Content-Security-Policy", self._csp or security.CSP_STRICT)
        for k, v in security.SECURITY_HEADERS.items():
            self.send_header(k, v)
        super().end_headers()

    def _page(self, name):
        self._csp = _TPL_CSP[name]
        self._send(_TPL[name], "text/html")

    def _check_token(self, route):
        """True if the Authorization header holds the admin token. Otherwise this
        sends 429 (backoff active) or 401, logs the failure (never the token)
        and returns False."""
        ip = self.client_address[0]
        wait = security.THROTTLE.retry_after(ip)
        if wait > 0:
            security.log.warning("admin token attempt refused (backoff): ip=%s route=%s retry_after_s=%d",
                                 ip, route, math.ceil(wait))
            self._json({"ok": False, "error": "too many failed attempts; try again later"}, code=429,
                       headers={"Retry-After": str(math.ceil(wait))})
            return False
        header = self.headers.get("Authorization")
        if security.verify_authorization(header):
            security.THROTTLE.success(ip)
            return True
        security.note_auth_failure(ip, route, header)
        self._json({"ok": False, "error": "admin token required"}, code=401,
                   headers={"WWW-Authenticate": 'Bearer realm="gps-time"'})
        return False

    def _send(self, body, ctype, code=200, cache=None):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        charset = ctype.startswith("text") or "json" in ctype or ctype == "application/javascript"
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if charset else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache or ("no-store" if "json" in ctype or ctype.startswith("text/html") else "max-age=300"))
        self.end_headers()
        self.wfile.write(data)

    def _web(self, u):
        """Serve the built web UI under /app/. Unknown extensionless paths get
        index.html so client-side routes survive a reload."""
        if u.path == WEB_PREFIX.rstrip("/"):
            self.send_response(301)
            self.send_header("Location", WEB_PREFIX + (("?" + u.query) if u.query else ""))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if not os.path.isfile(os.path.join(WEB_DIST, "index.html")):
            self._send(WEB_NOT_BUILT, "text/plain", code=503)
            return
        rel = unquote(u.path[len(WEB_PREFIX):]) or "index.html"
        if "\x00" in rel:
            self.send_error(404)
            return
        hit = web_file(rel)
        if hit is None and "." not in rel.rsplit("/", 1)[-1]:
            hit = web_file("index.html")
        if hit is None:
            self.send_error(404)
            return
        full, ctype, cache = hit
        with open(full, "rb") as f:
            self._send(f.read(), ctype, cache=cache)

    def _json(self, obj, code=200, headers=None):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        if security.host_allowed(self.headers.get("Host")):
            return True
        self._send(HOST_REFUSED, "text/plain", code=403)
        return False

    def do_GET(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        p = u.path
        self._csp = None
        if not self._host_ok():
            return
        try:
            if p in ("/api/admin", "/api/setting"):
                # State changes are POST-only (GPS-014): a GET can be triggered by any page.
                self._json({"ok": False, "error": "method not allowed: use POST with a JSON body"},
                           code=405, headers={"Allow": "POST"})
            elif p == "/api/auth":
                # A sent token is checked with the same logging/backoff as POSTs, so
                # this read-only route can't be used to guess tokens faster.
                if self.headers.get("Authorization") and not DEMO_MODE and security.admin_configured():
                    if self._check_token("/api/auth"):
                        self._json(auth_payload(True))
                else:
                    self._json(auth_payload(False))
            elif p == WEB_PREFIX.rstrip("/") or p.startswith(WEB_PREFIX):
                self._web(u)
            elif p == "/":
                self._page("dashboard")
            elif p == "/configure":
                self._page("configure")
            elif p == "/legacy":
                self._page("legacy")
            elif p == "/almanac":
                self._page("almanac")
            elif p == "/history":
                self._page("history")
            elif p == "/admin":
                self._page("admin")
            elif p == "/api/system":
                self._json(demo.system_diagnostics() if DEMO_MODE else system.diagnostics())
            elif p == "/zones":
                html = zones_page()
                self._csp = security.csp_for_html(html)
                self._send(html, "text/html")
            elif p == "/time":
                self._send(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f UTC\n"),
                           "text/plain")
            elif p == "/api":
                self._json(core_api())
            elif p == "/api/dashboard":
                self._json(dashboard_payload())
            elif p == "/api/ping":
                t2 = datetime.now(timezone.utc).timestamp() * 1000
                # Keep the endpoint tiny: the browser uses t2/t3 as the server side
                # of an NTP-like four timestamp exchange.
                t3 = datetime.now(timezone.utc).timestamp() * 1000
                self._json({"server_receive_epoch_ms": t2, "server_send_epoch_ms": t3})
            elif p == "/api/almanac":
                self._json(almanac_api(qs))
            elif p == "/api/object":
                self._json(object_api(qs))
            elif p == "/api/history":
                self._json(demo.history() if DEMO_MODE else chrony.history())
            elif p == "/api/timing-chain":
                self._json(timing_chain_payload(qs))
            elif p == "/api/stability":
                self._json(stability_payload())
            elif p == "/api/timescales":
                self._json(timescales_payload())
            elif p == "/api/diagnostics":
                self._send(diagnostics_text(qs), "text/plain")
            elif p == "/api/survey":
                self._json(survey_api())
            elif p == "/static/custom.css":
                custom = os.path.join(os.path.dirname(
                    os.environ.get("GTP_CONFIG", "/opt/gps-time-pi/config.json")), "custom.css")
                body = open(custom, encoding="utf-8").read() if os.path.exists(custom) else "/* create custom.css next to config.json to override styles */"
                self._send(body, "text/css")
            elif p.startswith("/static/"):
                fn = os.path.basename(p)
                full = os.path.join(_HERE, "static", fn)
                if os.path.exists(full):
                    ct = "text/css" if fn.endswith(".css") else "application/javascript"
                    with open(full, "rb") as f:
                        self._send(f.read(), ct)
                else:
                    self.send_error(404)
            else:
                self.send_error(404)
        except BrokenPipeError:
            pass
        except Exception as e:  # noqa: BLE001
            try:
                self._json({"error": str(e)})
            except Exception:  # noqa: BLE001
                pass

    def do_POST(self):
        """State-changing requests (GPS-014, GPS-017, GPS-019). Checks, in order:
        Host allowlist -> route -> Origin (same-origin or GTP_ALLOWED_ORIGINS) ->
        Content-Type application/json -> body size -> admin token (not in demo)."""
        p = urlparse(self.path).path
        self._csp = None
        # Read (bounded) the body before any refusal, so an early error doesn't
        # leave unread request bytes on the socket (the client would see a reset).
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        raw = self.rfile.read(length) if 0 < length <= MAX_BODY else None
        if raw is None:
            self.close_connection = True
        if not self._host_ok():
            return
        if p not in POST_ROUTES:
            self.send_error(404)
            return
        if not security.origin_allowed(self.headers.get("Origin"), self.headers.get("Host")):
            self._json({"ok": False, "error": "cross-origin request refused"}, code=403)
            return
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._json({"ok": False, "error": "Content-Type must be application/json"}, code=415)
            return
        if raw is None:
            self._json({"ok": False, "error": f"request body must be 1..{MAX_BODY} bytes of JSON"}, code=400)
            return
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self._json({"ok": False, "error": "invalid JSON"}, code=400)
            return
        if not isinstance(body, dict):
            self._json({"ok": False, "error": "JSON body must be an object"}, code=400)
            return
        if not DEMO_MODE:
            if not security.admin_configured():
                self._json({"ok": False, "error": ADMIN_DISABLED}, code=403)
                return
            if not self._check_token(p):
                return
        try:
            if p == "/api/admin":
                action = body.get("action")
                if DEMO_MODE:
                    # Never touch the host from demo mode (GPS-019).
                    known = action in system.ADMIN_ACTIONS
                    self._json({"ok": known, "action": action, "simulated": True,
                                "detail": f"demo mode: {action} was not executed" if known else "unknown action"})
                else:
                    self._json(system.admin(action))
            elif p == "/api/setting":
                mode = body.get("location_display")
                if mode in ("exact", "rounded", "hidden"):
                    cfg = config.load()
                    cfg["location_display"] = mode
                    config.save(cfg)
                    self._json({"ok": True, "location_display": mode})
                elif "timezone" in body:
                    # Display only: the system clock and every API timestamp stay on UTC.
                    tz = body.get("timezone") or None
                    if tz is not None and not localtime.valid_zone(tz):
                        self._json({"ok": False, "error": "unknown time zone (expected an IANA name such as "
                                                          "America/New_York, or null for automatic)"}, code=400)
                    else:
                        cfg = config.load()
                        cfg["timezone"] = tz
                        config.save(cfg)
                        self._json({"ok": True, "timezone": tz})
                elif body.get("reset_site") is True:
                    config.reset_site()
                    self._json({"ok": True, "reset_site": True})
                else:
                    self._json({"ok": False, "error": "expected location_display, timezone or reset_site"}, code=400)
            elif p == "/api/dashboard/reset":
                cfg = dashboard.save(dashboard.default_layout())
                self._json({"ok": True, "dashboard": cfg})
            else:
                self._json({"ok": True, "dashboard": dashboard.save(body)})
        except Exception as e:  # noqa: BLE001
            self._json({"ok": False, "error": str(e)})

    def log_message(self, *args):
        pass


def main():
    # Warnings (failed admin-token attempts) go to stderr, i.e. the systemd journal.
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(levelname)s %(name)s: %(message)s")
    # Flush survey/config state on SIGTERM (systemctl stop/restart, reboot).
    config.install_signal_handlers()
    if not DEMO_MODE:
        # GNSS sampling and survey ingestion run on their own schedule,
        # independent of how many pages or API clients are polling.
        gps.start_collector()
        timing_chain.service().start()
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
