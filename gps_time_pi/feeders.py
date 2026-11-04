"""Opt-in ADS-B feeders, and everything the station shares about its location (docs/deploy/feeders.md).

Installed by scripts/feeders.sh (GTP_FEEDERS=1), off until the owner turns one on in Administration
with the admin token and a typed confirmation (the service's name). The web service then writes
<feeders>/<name>.on and starts the unit through polkit (start, stop, restart of these units only).
Turning it off removes the file and stops the unit. The units' ConditionPathExists keeps a feeder
off across reboots unless its file is there.

What each shares, in plain words on its card:
  - the Beast feeders (adsb.fi, airplanes.live, ADSBExchange, a custom one): the aircraft messages the
    station receives, with a random feeder UUID. Never the station's position; MLAT isn't offered
    for them. From the aircraft it hears, an aggregator can still tell roughly where it is.
  - PiAware: the same to FlightAware. With MLAT on (a separate opt-in, with its own typed
    confirmation, refused in hidden privacy mode): the station's exact location too.

location_sharing() lists everything that shares the station's location, active or not, in one place
for Administration: the feeders, MLAT, and the station's own records (capability record,
sky-quality summary), with where each goes.
"""
import os
import re
import subprocess
from pathlib import Path

from .labels import q

CONF_DIR = Path(os.environ.get("GTP_FEEDERS_CONF", "/etc/gps-time-feeders"))
FLAG_DIR = Path(os.environ.get("GTP_FEEDERS_FLAGS", "/opt/gps-time-pi/feeders"))
PIAWARE_DROPIN = Path(os.environ.get("GTP_PIAWARE_DROPIN", "/etc/systemd/system/piaware.service.d/gps-time.conf"))
NAME_RE = re.compile(r"^[a-z0-9]{1,32}$")
# The services the catalog names; a custom aggregator is "custom" and shows its host.
SERVICES = {"adsbfi": "adsb.fi", "airplaneslive": "airplanes.live", "adsbexchange": "ADSBExchange",
            "custom": "a custom aggregator", "piaware": "FlightAware"}


class FeederError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


def unit(name):
    return "piaware.service" if name == "piaware" else f"gps-time-feed@{name}.service"


def _conf(name):
    out = {}
    try:
        for line in (CONF_DIR / f"{name}.conf").read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() in ("FEED_HOST", "FEED_PORT"):
                out[k.strip()] = v.strip()
    except OSError:
        return None
    return out


def installed():
    """[name] of the feeders the installer set up, in catalog order."""
    names = []
    try:
        names = [p.stem for p in CONF_DIR.glob("*.conf") if NAME_RE.match(p.stem)]
    except OSError:
        pass
    if PIAWARE_DROPIN.is_file():
        names.append("piaware")
    order = list(SERVICES)
    return sorted(set(names), key=lambda n: (order.index(n) if n in order else len(order), n))


def is_on(name):
    return (FLAG_DIR / f"{name}.on").is_file()


def mlat_on():
    return (FLAG_DIR / "piaware.mlat").is_file()


def _service(name, conf):
    if name.startswith("custom") and conf and conf.get("FEED_HOST"):
        return f"the custom aggregator {conf['FEED_HOST']}"
    return SERVICES.get(name, name)


def _states(names, run=subprocess.run):
    from . import sdr
    props = sdr.show_units([unit(n) for n in names], run) if names else {}
    return {n: (props.get(unit(n)) or {}).get("ActiveState") for n in names} if props else {n: None for n in names}


def status(cfg, run=subprocess.run):
    """The /api/feeders answer."""
    names = installed()
    states = _states(names, run)
    hidden = (cfg or {}).get("location_display") == "hidden"
    rows = []
    for n in names:
        conf = _conf(n) if n != "piaware" else None
        service = _service(n, conf)
        on = is_on(n)
        row = {"name": n, "service": service, "unit": unit(n), "on": on,
               "active": q(states.get(n), None, "observed", "systemctl show ActiveState"),
               "target": f"{conf['FEED_HOST']}:{conf['FEED_PORT']}" if conf else None,
               "confirm": service.split()[-1] if n.startswith("custom") else service,
               "shares": f"Shares the aircraft your station receives with {service}. It never gets the station's "
                         "position, but from the aircraft it hears it can tell roughly where the station is."}
        if n == "piaware":
            m = mlat_on()
            row["mlat"] = {"on": m, "allowed": not hidden, "confirm": "share my exact location",
                           "refused": "MLAT is refused in hidden privacy mode" if hidden else None}
            if m:
                row["shares"] = "Shares your exact location with FlightAware (MLAT is on), and the aircraft your station receives."
            else:
                row["shares"] = ("Shares the aircraft your station receives with FlightAware. Your location only with "
                                 "MLAT, which is off; PiAware never reads gpsd.")
        rows.append(row)
    return {"installed": bool(names), "feeders": rows, "location_display": (cfg or {}).get("location_display"),
            "note": "Off unless turned on here, each with an admin sign-in and a typed confirmation. Any number "
                    "can run at once, each to its own aggregator (docs/deploy/feeders.md)."}


def apply(cfg, body, run=subprocess.run):
    """POST /api/setting {"feeder": name, "enabled": bool, "confirm": str} or {"feeder": "piaware", "mlat": bool,
    "confirm": str}. Turning something on needs the confirmation typed exactly; off needs none."""
    name = body.get("feeder")
    if not isinstance(name, str) or name not in installed():
        raise FeederError("unknown feeder (not installed: GTP_FEEDERS=1)", 404)
    st = {r["name"]: r for r in status(cfg, run)["feeders"]}[name]
    if "mlat" in body:
        if name != "piaware":
            raise FeederError("MLAT is offered for PiAware only")
        want = body.get("mlat")
        if not isinstance(want, bool):
            raise FeederError("mlat must be true or false")
        if want:
            if (cfg or {}).get("location_display") == "hidden":
                raise FeederError("MLAT is refused in hidden privacy mode: it shares the station's exact location", 403)
            if body.get("confirm") != st["mlat"]["confirm"]:
                raise FeederError(f"type \"{st['mlat']['confirm']}\" to turn MLAT on")
            _touch(FLAG_DIR / "piaware.mlat")
        else:
            _remove(FLAG_DIR / "piaware.mlat")
        restarted = _systemctl("try-restart", name, run) if is_on(name) else None
        return {"ok": True, "feeder": name, "mlat": want, "restarted": restarted}
    want = body.get("enabled")
    if not isinstance(want, bool):
        raise FeederError("enabled must be true or false")
    if want:
        if body.get("confirm") != st["confirm"]:
            raise FeederError(f"type \"{st['confirm']}\" to turn this feeder on")
        _touch(FLAG_DIR / f"{name}.on")
        started = _systemctl("start", name, run)
        return {"ok": True, "feeder": name, "enabled": True, "detail": started}
    _remove(FLAG_DIR / f"{name}.on")
    stopped = _systemctl("stop", name, run)
    return {"ok": True, "feeder": name, "enabled": False, "detail": stopped}


def privacy_hidden(run=subprocess.run):
    """Called when the privacy mode becomes hidden: MLAT goes off and PiAware restarts without it."""
    if mlat_on():
        _remove(FLAG_DIR / "piaware.mlat")
        if is_on("piaware"):
            _systemctl("try-restart", "piaware", run)
        return True
    return False


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
    os.close(fd)


def _remove(path):
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _systemctl(verb, name, run):
    """A fixed argv (the polkit rule allows these verbs on these units only); the station's answer."""
    try:
        r = run(["systemctl", verb, unit(name)], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as e:
        return f"{verb} failed: {e}"[:300]
    return "done" if r.returncode == 0 else (r.stderr or r.stdout or f"{verb} failed").strip()[:300]


def location_sharing(cfg, feeders_status, capability_note=None):
    """Everything that shares (or could share) the station's location, for one card on Administration."""
    mode = (cfg or {}).get("location_display")
    rows = []
    for f in feeders_status.get("feeders", []):
        if f["name"] == "piaware":
            rows.append({"what": "FlightAware MLAT (PiAware)", "to": "FlightAware",
                         "location": "exact", "active": bool(f["on"] and f["mlat"]["on"]),
                         "detail": "off" if not f["mlat"]["on"] else ("on, PiAware running" if f["on"] else "on, but PiAware is off")})
        rows.append({"what": f"Feeder: {f['service']}", "to": f["target"] or f["service"],
                     "location": "rough (from the aircraft)", "active": bool(f["on"]),
                     "detail": "on" if f["on"] else "off"})
    rows.append({"what": "Capability record", "to": "not sent anywhere yet",
                 "location": "rounded to 0.1°" if mode == "rounded" else "none",
                 "active": mode == "rounded", "detail": capability_note or f"privacy mode {mode or 'exact'}"})
    rows.append({"what": "Sky-quality summary", "to": "the capability record and the diagnostics export",
                 "location": "none (sectors only)", "active": bool((cfg or {}).get("sky_quality_share")),
                 "detail": "opted in" if (cfg or {}).get("sky_quality_share") else "off"})
    return {"rows": rows, "exact_location_shared": any(r["active"] and r["location"] == "exact" for r in rows),
            "location_display": mode}
