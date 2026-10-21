"""The station's module supervisor: python -m gps_time_pi.modkit.supervisor

Runs under gps-time-modules.service, which install.sh installs but does not
enable: a station runs no modules until the owner enables the service and
names modules in "modules_enabled".

- Runs as root with only CAP_SETUID/CAP_SETGID/CAP_CHOWN/CAP_DAC_READ_SEARCH
  (the unit), so it can read the station config and start each module as the
  unprivileged module user (gps-time-mod), which can't read the config, the
  admin token or the station key.
- Gives modules the site only through config.privacy_site (the privacy mode),
  and the timing quality as UNKNOWN until the web service publishes it.
- Keeps the latest items per module in RAM and publishes a status file in
  /run (RAM) every 10 s. Nothing is written to the SD card by the supervisor.
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


def main():
    cfg = config.load()
    enabled = loader.enabled_from_config(cfg)
    latest = {}

    def emit(name, item):
        latest.setdefault(name, deque(maxlen=KEEP_ITEMS)).append(item)

    def site():
        s, mode = config.privacy_site(cfg, cfg.get("site"))
        return None if s is None else dict(s, privacy=mode)

    host = loader.ModuleHost(enabled=enabled, emit=emit, site=site, user=MODULE_USER,
                             deny_read=deny_paths(), configs=cfg.get("module_config", {}),
                             storage_roots={"ram": str(RUN_DIR / "ram"), "disk": str(STATE_DIR)},
                             max_limits=cfg.get("module_limits"))
    host.load()
    host.start()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *a: stop.set())
    signal.signal(signal.SIGINT, lambda *a: stop.set())
    while not stop.is_set():
        publish(RUN_DIR / "status.json", {"updated": time.time(), "enabled": enabled, "modules": host.status(),
                                          "latest": {k: list(v) for k, v in latest.items()}})
        stop.wait(PUBLISH_S)
    host.stop()
    publish(RUN_DIR / "status.json", {"updated": time.time(), "enabled": enabled, "modules": host.status(),
                                      "latest": {}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
