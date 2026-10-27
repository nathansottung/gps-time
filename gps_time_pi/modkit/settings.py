"""The Administration switch for experimental modules, and the per-module list.

Two settings in the station config, both off by default:

- "modules_experimental": the master switch. While it is off, no module runs,
  whatever "modules_enabled" says.
- "modules_enabled": the modules the owner turned on, one by one.

Turning the master switch on enables no module: every change of the switch
clears "modules_enabled", so after it each module is off until it is turned on
by itself.

The web service uses this to list and change the settings. It reads each
module's manifest (TOML) but never imports module code; the modules run only
under gps-time-modules.service (supervisor.py), which picks up a change within
its publish interval.
"""

import json
import os
import time
from pathlib import Path

from . import loader

MASTER = "modules_experimental"
ENABLED = "modules_enabled"
CONFIG = "module_config"
# A module's settings as set from Administration: bounded, and only the keys its manifest declares.
MAX_CONFIG_BYTES = 8192
CONFIG_TYPES = {"float": (int, float), "int": (int,), "string": (str,), "path": (str,), "table": (dict,),
                "bool": (bool,)}
STATUS_PATH = Path(os.environ.get("GTP_MODULES_STATUS", "/run/gps-time-modules/status.json"))
# The supervisor publishes every 10 s; older than this, its states are not shown as current.
STATUS_FRESH_S = 60.0
# A module's latest item as /api/modules shows it: bounded, labeled values only.
MAX_VALUES = 40
MAX_TEXT = 300
PROVENANCE = ("observed", "calculated", "modeled", "predicted", "inferred", "external")
# Never shown here, whatever a module emits: values that could carry a position. Modules get
# the site already privacy-filtered, but this page is not the place for any position at all.
POSITION_KEYS = {"lat", "lon", "latitude", "longitude", "alt", "alt_m", "alt_msl", "alt_hae", "height_m",
                 "position", "site", "location", "x_m", "y_m", "z_m"}


class SettingError(ValueError):
    """A request the station refuses; .code is the HTTP status."""

    def __init__(self, message, code=400):
        super().__init__(message)
        self.code = code


def master_on(cfg):
    return isinstance(cfg, dict) and cfg.get(MASTER) is True


def enabled_names(cfg):
    names = cfg.get(ENABLED, []) if isinstance(cfg, dict) else []
    return [n for n in names if isinstance(n, str)] if isinstance(names, list) else []


def _supervisor(status_path, now):
    """What the supervisor last published, and whether it is recent enough to show."""
    try:
        doc = json.loads(Path(status_path).read_text(encoding="utf-8"))
        updated = float(doc["updated"])
    except (OSError, ValueError, KeyError, TypeError):
        return {"reporting": False, "age_s": None, "detail": "no status from gps-time-modules (not running, or not readable)"}, {}
    age = max(0.0, now - updated)
    if age > STATUS_FRESH_S:
        return {"reporting": False, "age_s": round(age, 1),
                "detail": f"last status from gps-time-modules is {age:.0f} s old"}, {}
    states = {m.get("name"): m for m in doc.get("modules", []) if isinstance(m, dict)}
    latest = doc.get("latest") if isinstance(doc.get("latest"), dict) else {}
    for name, items in latest.items():
        if name in states and isinstance(items, list) and items:
            states[name] = {**states[name], "_latest": items[-1], "_kept": len(items)}
    return {"reporting": True, "age_s": round(age, 1), "detail": "gps-time-modules is reporting"}, states


def _text(v):
    return v if not isinstance(v, str) or len(v) <= MAX_TEXT else v[:MAX_TEXT - 1] + "…"


def latest_item(item, kept, now):
    """A module's newest item, as the page shows it: its kind, time and age, and at most
    MAX_VALUES labeled scalar values. A value without one of the six provenance labels, a
    non-scalar value or a position-like name is left out and counted, never relabeled."""
    if not isinstance(item, dict) or not isinstance(item.get("values"), dict):
        return None
    t_ns = item.get("time_ns")
    t_ns = t_ns if isinstance(t_ns, int) and not isinstance(t_ns, bool) else None
    values, left_out = {}, 0
    for k, v in item["values"].items():
        ok = (isinstance(k, str) and k.lower() not in POSITION_KEYS and isinstance(v, dict)
              and v.get("provenance") in PROVENANCE
              and (v.get("value") is None or isinstance(v.get("value"), (bool, int, float, str))))
        if not ok or len(values) >= MAX_VALUES:
            left_out += 1
            continue
        d = {"value": _text(v.get("value")), "unit": _text(v.get("unit")) if isinstance(v.get("unit"), str) else None,
             "provenance": v["provenance"]}
        if isinstance(v.get("note"), str) and v["note"]:
            d["note"] = _text(v["note"])
        values[k] = d
    return {"kind": "result" if "analysis" in item else "observation",
            "time_ns": t_ns, "age_s": None if t_ns is None else round(max(0.0, now - t_ns / 1e9), 1),
            "items_kept": kept, "values": values, "left_out": left_out}


def config_schema(m):
    """The manifest's [config] table as the page shows it: type, unit, default, description."""
    out = {}
    for k, v in ((m.data.get("config") or {}) if m else {}).items():
        if isinstance(v, dict):
            out[k] = {f: v.get(f) for f in ("type", "unit", "default", "description") if f in v}
    return out


def module_config(cfg, name):
    mc = cfg.get(CONFIG) if isinstance(cfg, dict) else None
    v = mc.get(name) if isinstance(mc, dict) else None
    return v if isinstance(v, dict) else {}


def _position_key(v, path=""):
    """The first key, at any depth, that names a position; None when there is none."""
    if isinstance(v, dict):
        for k, x in v.items():
            if str(k).lower() in POSITION_KEYS:
                return f"{path}{k}"
            hit = _position_key(x, f"{path}{k}.")
            if hit:
                return hit
    elif isinstance(v, list):
        for i, x in enumerate(v):
            hit = _position_key(x, f"{path}{i}.")
            if hit:
                return hit
    return None


def check_config(m, value):
    """Raises SettingError unless value is a settings object the manifest allows."""
    if not isinstance(value, dict):
        raise SettingError("config must be an object, or null to clear it")
    if len(json.dumps(value)) > MAX_CONFIG_BYTES:
        raise SettingError(f"config is larger than {MAX_CONFIG_BYTES} bytes")
    schema = config_schema(m)
    unknown = sorted(k for k in value if k not in schema)
    if unknown:
        raise SettingError(f"{m.name} has no setting {', '.join(unknown)} (its manifest declares: "
                           f"{', '.join(schema) or 'none'})")
    pos = _position_key(value)
    if pos:
        raise SettingError(f"{pos}: positions are not set here; a module gets the station's site, "
                           "privacy-filtered, from the station")
    for k, v in value.items():
        want = CONFIG_TYPES.get(schema[k].get("type"))
        if v is None or want is None:
            continue
        if isinstance(v, bool) and bool not in want:
            raise SettingError(f"{k} must be a {schema[k]['type']}, not true/false")
        if not isinstance(v, want):
            raise SettingError(f"{k} must be a {schema[k]['type']}")
        if isinstance(v, str) and len(v) > MAX_TEXT:
            raise SettingError(f"{k} is longer than {MAX_TEXT} characters")


def listing(cfg, root=None, status_path=None, now=None, readiness=None):
    """Master switch, every installed module with its manifest facts and setting,
    and the supervisor's state per module when it is reporting. readiness: {module: checks}
    from the station (sdr.py), shown as they are."""
    now = time.time() if now is None else now
    on = master_on(cfg)
    enabled = enabled_names(cfg)
    sup, states = _supervisor(status_path or STATUS_PATH, now)
    rows, seen = [], set()
    for folder, m, errs in loader.discover(root):
        name = m.name if m else folder.name
        seen.add(name)
        st = states.get(name)
        rows.append({
            "name": name,
            "installed": True,
            "valid": m is not None,
            "errors": errs,
            "version": m.version if m else None,
            "maturity": m.maturity if m else None,
            "types": list(m.types) if m else [],
            "summary": m.data.get("summary") if m else None,
            "permissions": m.permissions if m else None,
            "enabled": name in enabled,
            # the host runs only a module's source entry: an analysis-only module never runs under it
            "runs": on and name in enabled and m is not None and "source" in m.entry,
            "host_runs": bool(m and "source" in m.entry),
            # observed from the supervisor; None (UNKNOWN) when it isn't reporting
            "state": st.get("state") if st else None,
            "reason": st.get("reason") if st else None,
            # the newest item the module emitted (supervisor's RAM copy); None when it isn't reporting
            "latest": latest_item(st.get("_latest"), st.get("_kept", 0), now) if st else None,
            # settings: the owner's (module_config), and what the manifest declares
            "config": module_config(cfg, name),
            "config_schema": config_schema(m),
            "readiness": (readiness or {}).get(name),
        })
    for name in enabled:
        if name not in seen:
            rows.append({"name": name, "installed": False, "valid": False, "errors": [f"{name}: not installed"],
                         "version": None, "maturity": None, "types": [], "summary": None, "permissions": None,
                         "enabled": True, "runs": False, "host_runs": False, "state": None, "reason": None,
                         "latest": None, "config": module_config(cfg, name), "config_schema": {},
                         "readiness": (readiness or {}).get(name)})
    return {"experimental": on, "modules": rows, "supervisor": sup,
            "note": "Changes are read by gps-time-modules.service within about 10 s. Until that service runs, "
                    "no module runs: install.sh installs it, and GTP_SDR=1 enables it."}


def apply(cfg, body, root=None):
    """Change cfg in place from a POST body; returns the station's answer. Raises SettingError."""
    if MASTER in body:
        on = body[MASTER]
        if not isinstance(on, bool):
            raise SettingError(f"{MASTER} must be true or false")
        cfg[MASTER] = on
        cfg[ENABLED] = []          # on or off, every module starts off again
        return {"ok": True, MASTER: on, ENABLED: []}
    if "module" in body and "config" in body:
        name, value = body.get("module"), body.get("config")
        if not isinstance(name, str):
            raise SettingError("expected {\"module\": \"<name>\", \"config\": {...}|null}")
        found = {(m.name if m else f.name): m for f, m, _ in loader.discover(root)}
        if name not in found:
            raise SettingError(f"no module named {name!r} is installed", code=404)
        if found[name] is None:
            raise SettingError(f"{name}: the manifest is invalid, so it has no settings", code=409)
        mc = cfg.get(CONFIG) if isinstance(cfg.get(CONFIG), dict) else {}
        if value is None:
            mc.pop(name, None)
        else:
            check_config(found[name], value)
            mc[name] = value
        cfg[CONFIG] = mc
        return {"ok": True, "module": name, "config": mc.get(name, {})}
    if "module" in body:
        name, want = body.get("module"), body.get("enabled")
        if not isinstance(name, str) or not isinstance(want, bool):
            raise SettingError("expected {\"module\": \"<name>\", \"enabled\": true|false}")
        enabled = enabled_names(cfg)
        if want:
            if not master_on(cfg):
                raise SettingError("experimental modules are off; turn them on first", code=409)
            found = {(m.name if m else f.name): m for f, m, _ in loader.discover(root)}
            if name not in found:
                raise SettingError(f"no module named {name!r} is installed", code=404)
            if found[name] is None:
                raise SettingError(f"{name}: the manifest is invalid, so it can't be enabled", code=409)
            if name not in enabled:
                enabled.append(name)
        else:
            enabled = [n for n in enabled if n != name]
        cfg[ENABLED] = enabled
        return {"ok": True, "module": name, "enabled": want, ENABLED: enabled}
    raise SettingError(f"expected {MASTER} or module")
