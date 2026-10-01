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

Run: python3 -m gps_time_pi.server  (port 80 by default, GTP_PORT to override)
"""

import json
import os
import re
from datetime import date as _date
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo, available_timezones

import platform

from . import __version__, astro, catalog, chrony, config, dashboard, demo, gps, system, timing_chain, units

_HERE = os.path.dirname(__file__)
DEMO_MODE = os.environ.get("GTP_DEMO", "0").lower() in ("1", "true", "yes", "on")
PORT = int(os.environ.get("GTP_PORT", "8080" if DEMO_MODE else "80"))
BIND = os.environ.get("GTP_BIND", "127.0.0.1" if DEMO_MODE else "0.0.0.0")

_TPL = {}
for name in ("dashboard", "configure", "legacy", "almanac", "history", "admin"):
    with open(os.path.join(_HERE, "templates", name + ".html")) as f:
        _TPL[name] = f.read()


def cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read()) / 1000, 1)
    except Exception:  # noqa: BLE001
        return None


def core_api():
    if DEMO_MODE:
        return demo.core_api()
    now = datetime.now(timezone.utc)
    trk = chrony.tracking()
    srcs = chrony.sources()
    snap = gps.snapshot()
    q = chrony.quality(trk)
    status = timing_chain.timing_status(trk, srcs, gnss=snap, refclocks=chrony.refclock_config())
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
        "gps": {k: snap[k] for k in ("fix", "sats", "used", "visible", "tdop", "hdop",
                                     "last_fix", "last_fix_time", "stale", "data_age_s",
                                     "sky_stale", "sky_age_s")},
        "location": config.displayed_location(cfg, snap["live"]),
        "survey": config.site_stats(cfg),
        "position_provenance": provenance,
        "sidereal": astro.sidereal(site) if (site and astro.STATUS["available"]) else None,
        "astro_available": astro.STATUS["available"],
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


def almanac_api(qs):
    if DEMO_MODE:
        return demo.almanac_api(qs)
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
                "daylight_s": x.get("daylight_s")} if x.get("available") else {}
    return {"available": True, "sun": sun, "moon": moon, "night": nite,
            "delta_yesterday": dy, "delta_tomorrow": dt_,
            "neighbors": {"yesterday": _neighbor(sun_y), "tomorrow": _neighbor(sun_t)},
            "sky": sky,
            "sky_when": obs_dt.strftime("%-I:%M %p · %b %-d, %Y · ") + tzname,
            "position_provenance": provenance, "position_age": age}


_LAST_TARGET = {}


def object_api(qs):
    q = qs.get("q", [""])[0]
    target = catalog.lookup(q)
    if target is None:
        return {"error": "unparsed"}
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
    rep["at_label"] = obs_dt.strftime("%-I:%M %p")
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


def diagnostics_text(qs):
    chain = timing_chain_payload(qs)
    cfg = config.load()
    live = DEMO_SITE if DEMO_MODE else gps.snapshot()["live"]
    return timing_chain.diagnostic_snapshot(chain, config.displayed_location(cfg, live))


def dashboard_writable(remote_ip):
    if DEMO_MODE:
        return True
    mode = os.environ.get("GTP_ALLOW_CONFIG_WRITE", "").lower()
    if mode in ("1", "true", "yes", "on", "lan"):
        return True
    return remote_ip in ("127.0.0.1", "::1")


def dashboard_payload(remote_ip):
    cfg = dashboard.load()
    cfg["_meta"] = {
        "writable": dashboard_writable(remote_ip),
        "demo": DEMO_MODE,
        "path": str(dashboard.path()) if DEMO_MODE else None,
        "known_widgets": sorted(dashboard.KNOWN_WIDGETS),
    }
    return cfg


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype, code=200):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") or "json" in ctype else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store" if "json" in ctype or ctype.startswith("text/html") else "max-age=300")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj):
        self._send(json.dumps(obj), "application/json")

    def do_GET(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        p = u.path
        try:
            if p == "/":
                self._send(_TPL["dashboard"], "text/html")
            elif p == "/configure":
                self._send(_TPL["configure"], "text/html")
            elif p == "/legacy":
                self._send(_TPL["legacy"], "text/html")
            elif p == "/almanac":
                self._send(_TPL["almanac"], "text/html")
            elif p == "/history":
                self._send(_TPL["history"], "text/html")
            elif p == "/admin":
                self._send(_TPL["admin"], "text/html")
            elif p == "/api/system":
                self._json(demo.system_diagnostics() if DEMO_MODE else system.diagnostics())
            elif p == "/api/admin":
                self._json(system.admin(qs.get("action", [""])[0]))
            elif p == "/zones":
                self._send(zones_page(), "text/html")
            elif p == "/time":
                self._send(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f UTC\n"),
                           "text/plain")
            elif p == "/api":
                self._json(core_api())
            elif p == "/api/dashboard":
                self._json(dashboard_payload(self.client_address[0]))
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
            elif p == "/api/diagnostics":
                self._send(diagnostics_text(qs), "text/plain")
            elif p == "/api/survey":
                self._json(survey_api())
            elif p == "/api/setting":
                mode = qs.get("location_display", [None])[0]
                if mode in ("exact", "rounded", "hidden"):
                    cfg = config.load()
                    cfg["location_display"] = mode
                    config.save(cfg)
                    self._json({"ok": True, "location_display": mode})
                elif qs.get("reset_site", [None])[0] == "1":
                    config.reset_site()
                    self._json({"ok": True, "reset_site": True})
                else:
                    self._json({"ok": False})
            elif p == "/static/custom.css":
                custom = os.path.join(os.path.dirname(
                    os.environ.get("GTP_CONFIG", "/opt/gps-time-pi/config.json")), "custom.css")
                body = open(custom).read() if os.path.exists(custom) else "/* create custom.css next to config.json to override styles */"
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
        u = urlparse(self.path)
        p = u.path
        if p not in ("/api/dashboard", "/api/dashboard/reset"):
            self.send_error(404)
            return
        if not dashboard_writable(self.client_address[0]):
            self._json({"ok": False, "error": "dashboard configuration writes are disabled"})
            return
        try:
            if p == "/api/dashboard/reset":
                cfg = dashboard.default_layout()
                cfg = dashboard.save(cfg)
                self._json({"ok": True, "dashboard": cfg})
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 256000:
                raise ValueError("invalid dashboard payload size")
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            cfg = dashboard.save(data)
            self._json({"ok": True, "dashboard": cfg})
        except Exception as e:  # noqa: BLE001
            self._json({"ok": False, "error": str(e)})

    def log_message(self, *args):
        pass


def main():
    if not DEMO_MODE:
        # GNSS sampling and survey ingestion run on their own schedule,
        # independent of how many pages or API clients are polling.
        gps.start_collector()
        timing_chain.service().start()
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
