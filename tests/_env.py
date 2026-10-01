"""Test environment: point persistent state at a throwaway directory BEFORE
any gps_time_pi module is imported (config reads GTP_CONFIG at import and
registers an atexit writer)."""

import os
import tempfile

TMP = tempfile.mkdtemp(prefix="gps-time-tests-")
os.environ["GTP_CONFIG"] = os.path.join(TMP, "config.json")
os.environ["GTP_DASHBOARD_CONFIG"] = os.path.join(TMP, "dashboard.json")
os.environ.pop("GTP_DEMO", None)
# never read the host's chrony/boot configuration or write real event checkpoints
os.environ["GTP_CHRONY_CONF"] = os.path.join(TMP, "no-chrony.conf")
os.environ["GTP_BOOT_CONFIG"] = os.path.join(TMP, "no-config.txt")
os.environ["GTP_EVENTS_PATH"] = os.path.join(TMP, "timing-events.json")
