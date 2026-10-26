"""The station's module supervisor: python -m gps_time_pi.modkit.supervisor

Runs under gps-time-modules.service, which install.sh installs but does not
enable: a station runs no modules until the owner enables the service, turns
on experimental modules (Administration, or "modules_experimental") and
enables modules one by one ("modules_enabled"; settings.py).

- Runs as root with only CAP_SETUID/CAP_SETGID/CAP_CHOWN/CAP_DAC_READ_SEARCH
  (the unit), so it can read the station config and start each module as the
  unprivileged module user (gps-time-mod), which can't read the config, the
  admin token or the station key.
- Gives modules the site only through config.privacy_site (the privacy mode),
  and the timing quality as UNKNOWN until the web service publishes it.
- Keeps the latest items per module in RAM and publishes a status file in
  /run (RAM) every 10 s. Nothing is written to the SD card by the supervisor.
- Checks the config file at each publish (read only, when its mtime changes)
  and restarts the module set when the module settings changed, so the
  Administration switches take effect without restarting the service.
"""

import json
import os
import signal
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

from .. import config
from . import loader

MODULE_USER = os.environ.get("GTP_MODULE_USER", "gps-time-mod")
RUN_DIR = Path(os.environ.get("RUNTIME_DIRECTORY", "/run/gps-time-modules"))
STATE_DIR = Path(os.environ.get("STATE_DIRECTORY", "/var/lib/gps-time-modules"))
KEEP_ITEMS = 20
PUBLISH_S = 10.0


def deny_paths():
    """Paths no module may open (also protected by file permissions on the station)."""
    base = Path(config._PATH).parent
    return [config._PATH, config._PATH + ".prev", str(base / "admin-token.sha256"),
            str(base / "station-key"), "/etc/shadow"]


def publish(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(doc, f, sort_keys=True)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def module_settings(cfg):
    """The parts of the config that decide which modules run and how."""
    return (loader.enabled_from_config(cfg), cfg.get("module_config", {}), cfg.get("module_limits"))


def read_config():
    """A fresh read of the config file (never written here); None if unreadable."""
    try:
        return dict(config.DEFAULTS, **config._read_json(config._PATH))
    except (OSError, ValueError):
        return None


def config_mtime():
    try:
        return os.stat(config._PATH).st_mtime_ns
    except OSError:
        return None


def make_host(current, emit):
    """current() returns the config now in force, so a privacy change reaches running modules."""
    def site():
        cfg = current()
        s, mode = config.privacy_site(cfg, cfg.get("site"))
        return None if s is None else dict(s, privacy=mode)

    enabled, configs, limits = module_settings(current())
    host = loader.ModuleHost(enabled=enabled, emit=emit, site=site, user=MODULE_USER,
                             deny_read=deny_paths(), configs=configs,
                             storage_roots={"ram": str(RUN_DIR / "ram"), "disk": str(STATE_DIR)},
                             max_limits=limits)
    host.load()
    host.start()
    return host


def main():
    held = {"cfg": config.load()}
    mtime = config_mtime()
    latest = {}

    def emit(name, item):
        latest.setdefault(name, deque(maxlen=KEEP_ITEMS)).append(item)

    host = make_host(lambda: held["cfg"], emit)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *a: stop.set())
    signal.signal(signal.SIGINT, lambda *a: stop.set())
    while not stop.is_set():
        m = config_mtime()
        if m != mtime:
            mtime = m
            fresh = read_config()
            if fresh is not None and module_settings(fresh) != module_settings(held["cfg"]):
                host.stop()
                held["cfg"] = fresh
                keep = set(loader.enabled_from_config(fresh))
                for k in [k for k in latest if k not in keep]:
                    del latest[k]
                host = make_host(lambda: held["cfg"], emit)
            elif fresh is not None:
                held["cfg"] = fresh    # e.g. the privacy mode changed; site() reads it on the next push
        publish(RUN_DIR / "status.json", {"updated": time.time(), "enabled": loader.enabled_from_config(held["cfg"]),
                                          "modules": host.status(),
                                          "latest": {k: list(v) for k, v in latest.items()}})
        stop.wait(PUBLISH_S)
    host.stop()
    publish(RUN_DIR / "status.json", {"updated": time.time(), "enabled": loader.enabled_from_config(held["cfg"]),
                                      "modules": host.status(), "latest": {}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
