"""Experimental modules switch (Administration) and per-module settings.

- Off by default; with the switch off no module runs, whatever modules_enabled says.
- Turning the switch on (or off) enables no module: each is off until turned on by itself.
- Changes need the admin token (POST /api/setting); GET /api/modules lists, read only.
- The listing reads manifests only; module code is never imported by the web service.
- The supervisor picks up a change from the config file without a restart.
No root, network or Pi.
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from tests.test_admin_auth import TOKEN, AuthBase
from gps_time_pi import config
from gps_time_pi.modkit import loader, settings, supervisor

ROOT = Path(__file__).resolve().parent.parent
REPO_MODULES = ROOT / "modules"


class ModulesDir(unittest.TestCase):
    """A temp modules dir: a copy of the repository's sdr-pps-marker, and one broken module."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="gps-time-modules-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        shutil.copytree(REPO_MODULES / "sdr-pps-marker", self.root / "sdr-pps-marker",
                        ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / "broken").mkdir()
        (self.root / "broken" / "module.toml").write_text("name = 'broken'\n", encoding="utf-8")
        self.status = self.root / "status.json"


class TestGate(unittest.TestCase):
    def test_off_by_default(self):
        self.assertEqual(loader.enabled_from_config({}), [])
        self.assertEqual(loader.enabled_from_config(dict(config.DEFAULTS)), [])

    def test_switch_off_means_nothing_runs(self):
        self.assertEqual(loader.enabled_from_config({"modules_enabled": ["a"]}), [])
        self.assertEqual(loader.enabled_from_config({"modules_experimental": False, "modules_enabled": ["a"]}), [])
        self.assertEqual(loader.enabled_from_config({"modules_experimental": "yes", "modules_enabled": ["a"]}), [])

    def test_switch_on_runs_only_what_was_enabled(self):
        self.assertEqual(loader.enabled_from_config({"modules_experimental": True}), [])
        self.assertEqual(loader.enabled_from_config({"modules_experimental": True, "modules_enabled": ["a", 3]}), ["a"])
        self.assertEqual(loader.enabled_from_config({"modules_experimental": True, "modules_enabled": "a"}), [])


class TestApply(ModulesDir):
    def apply(self, cfg, body):
        return settings.apply(cfg, body, root=self.root)

    def test_switch_on_enables_no_module(self):
        cfg = {"modules_enabled": ["sdr-pps-marker"]}      # e.g. set by hand earlier
        r = self.apply(cfg, {"modules_experimental": True})
        self.assertEqual(r, {"ok": True, "modules_experimental": True, "modules_enabled": []})
        self.assertEqual(loader.enabled_from_config(cfg), [])

    def test_one_by_one(self):
        cfg = {}
        self.apply(cfg, {"modules_experimental": True})
        r = self.apply(cfg, {"module": "sdr-pps-marker", "enabled": True})
        self.assertEqual(r["modules_enabled"], ["sdr-pps-marker"])
        self.apply(cfg, {"module": "sdr-pps-marker", "enabled": True})    # idempotent
        self.assertEqual(loader.enabled_from_config(cfg), ["sdr-pps-marker"])
        self.apply(cfg, {"module": "sdr-pps-marker", "enabled": False})
        self.assertEqual(loader.enabled_from_config(cfg), [])

    def test_switch_off_then_on_leaves_every_module_off(self):
        cfg = {}
        self.apply(cfg, {"modules_experimental": True})
        self.apply(cfg, {"module": "sdr-pps-marker", "enabled": True})
        self.apply(cfg, {"modules_experimental": False})
        self.assertEqual(cfg["modules_enabled"], [])
        self.apply(cfg, {"modules_experimental": True})
        self.assertEqual(loader.enabled_from_config(cfg), [])

    def test_refusals(self):
        cfg = {}
        with self.assertRaises(settings.SettingError) as e:
            self.apply(cfg, {"module": "sdr-pps-marker", "enabled": True})
        self.assertEqual(e.exception.code, 409)                     # switch is off
        self.apply(cfg, {"modules_experimental": True})
        for body, code in (({"module": "nope", "enabled": True}, 404),
                           ({"module": "broken", "enabled": True}, 409),
                           ({"module": "sdr-pps-marker", "enabled": "yes"}, 400),
                           ({"modules_experimental": 1}, 400),
                           ({"other": True}, 400)):
            with self.assertRaises(settings.SettingError) as e:
                self.apply(cfg, body)
            self.assertEqual(e.exception.code, code, body)
        self.assertEqual(cfg["modules_enabled"], [])

    def test_disabling_works_with_the_switch_off(self):
        cfg = {"modules_enabled": ["gone"]}
        self.apply(cfg, {"module": "gone", "enabled": False})
        self.assertEqual(cfg["modules_enabled"], [])


class TestListing(ModulesDir):
    def listing(self, cfg, now=None):
        return settings.listing(cfg, root=self.root, status_path=self.status, now=now)

    def test_lists_manifests_without_importing_code(self):
        sys.modules.pop("sdr_pps_marker", None)
        doc = self.listing({})
        self.assertFalse(doc["experimental"])
        rows = {r["name"]: r for r in doc["modules"]}
        m = rows["sdr-pps-marker"]
        self.assertEqual((m["valid"], m["maturity"], m["enabled"], m["runs"]), (True, "research", False, False))
        self.assertIn("SDR", m["summary"])
        self.assertFalse(rows["broken"]["valid"])
        self.assertTrue(rows["broken"]["errors"])
        self.assertNotIn("sdr_pps_marker", sys.modules)

    def test_runs_only_with_the_switch(self):
        on = {"modules_experimental": True, "modules_enabled": ["sdr-pps-marker"]}
        off = {"modules_enabled": ["sdr-pps-marker"]}
        self.assertTrue(next(r for r in self.listing(on)["modules"] if r["name"] == "sdr-pps-marker")["runs"])
        row = next(r for r in self.listing(off)["modules"] if r["name"] == "sdr-pps-marker")
        self.assertEqual((row["enabled"], row["runs"]), (True, False))

    def test_enabled_but_not_installed_is_listed(self):
        doc = self.listing({"modules_experimental": True, "modules_enabled": ["elsewhere"]})
        row = next(r for r in doc["modules"] if r["name"] == "elsewhere")
        self.assertEqual((row["installed"], row["runs"]), (False, False))

    def test_supervisor_state_only_when_reporting(self):
        doc = self.listing({})
        self.assertFalse(doc["supervisor"]["reporting"])
        self.assertIsNone(doc["modules"][0]["state"])                # UNKNOWN, not "stopped"
        self.status.write_text(json.dumps({"updated": 1000.0, "modules": [
            {"name": "sdr-pps-marker", "state": "running", "reason": ""}]}), encoding="utf-8")
        doc = self.listing({}, now=1005.0)
        self.assertTrue(doc["supervisor"]["reporting"])
        self.assertEqual(next(r for r in doc["modules"] if r["name"] == "sdr-pps-marker")["state"], "running")
        doc = self.listing({}, now=1000.0 + settings.STATUS_FRESH_S + 1)
        self.assertFalse(doc["supervisor"]["reporting"])
        self.assertIsNone(next(r for r in doc["modules"] if r["name"] == "sdr-pps-marker")["state"])


class TestHttp(AuthBase):
    def setUp(self):
        super().setUp()
        self.root = Path(self.tmp) / "modules"
        shutil.copytree(REPO_MODULES / "sdr-pps-marker", self.root / "sdr-pps-marker",
                        ignore=shutil.ignore_patterns("__pycache__"))
        p = mock.patch.object(loader, "DEFAULT_DIR", self.root)
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(settings, "STATUS_PATH", Path(self.tmp) / "no-status.json")
        p.start()
        self.addCleanup(p.stop)

    def saved(self):
        return json.loads(Path(config._PATH).read_text(encoding="utf-8"))

    def test_listing_is_read_only_and_needs_no_token(self):
        status, _, body = self.req("GET", "/api/modules")
        self.assertEqual(status, 200)
        self.assertFalse(body["experimental"])
        self.assertEqual([m["name"] for m in body["modules"]], ["sdr-pps-marker"])

    def test_changes_need_the_token(self):
        self.assertEqual(self.post("/api/setting", {"modules_experimental": True}, token=None)[0], 401)
        self.assertEqual(self.post("/api/setting", {"modules_experimental": True}, token="wrong")[0], 401)
        self.assertNotIn("modules_experimental", self.saved())

    def test_switch_then_one_module(self):
        status, _, body = self.post("/api/setting", {"module": "sdr-pps-marker", "enabled": True})
        self.assertEqual((status, body["ok"]), (409, False))
        status, _, body = self.post("/api/setting", {"modules_experimental": True})
        self.assertEqual((status, body), (200, {"ok": True, "modules_experimental": True, "modules_enabled": []}))
        status, _, body = self.post("/api/setting", {"module": "sdr-pps-marker", "enabled": True})
        self.assertEqual((status, body["modules_enabled"]), (200, ["sdr-pps-marker"]))
        saved = self.saved()
        self.assertEqual((saved["modules_experimental"], saved["modules_enabled"]), (True, ["sdr-pps-marker"]))
        self.assertEqual(saved["location_display"], "exact")      # other settings untouched
        self.assertEqual(self.post("/api/setting", {"module": "nope", "enabled": True})[0], 404)
        self.post("/api/setting", {"modules_experimental": False})
        self.assertEqual(self.saved()["modules_enabled"], [])

    def test_get_on_setting_still_405(self):
        self.assertEqual(self.req("GET", "/api/setting?modules_experimental=true")[0], 405)
        self.assertNotIn("modules_experimental", self.saved())


class TestDemoHttp(TestHttp):
    demo = True

    def test_changes_need_the_token(self):
        pass   # demo mode takes no token, as for every setting


class FakeHost:
    made = []

    def __init__(self, enabled=(), site=None, **kw):
        self.enabled, self.site, self.stopped = list(enabled), site, False
        FakeHost.made.append(self)

    def load(self):
        pass

    def start(self):
        pass

    def stop(self):
        self.stopped = True

    def status(self):
        return [{"name": n, "state": "running"} for n in self.enabled]


class TestSupervisorReload(unittest.TestCase):
    def test_module_settings_follow_the_switch(self):
        a = {"modules_enabled": ["x"]}
        b = dict(a, modules_experimental=True)
        self.assertNotEqual(supervisor.module_settings(a), supervisor.module_settings(b))
        self.assertEqual(supervisor.module_settings(a), supervisor.module_settings(dict(a, location_display="hidden")))

    def test_read_config_never_writes(self):
        tmp = Path(tempfile.mkdtemp(prefix="gps-time-sup-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        f = tmp / "config.json"
        f.write_text("{not json", encoding="utf-8")
        with mock.patch.object(config, "_PATH", str(f)):
            self.assertIsNone(supervisor.read_config())
            self.assertEqual(f.read_text(encoding="utf-8"), "{not json")     # not set aside
            f.write_text(json.dumps({"modules_experimental": True}), encoding="utf-8")
            self.assertTrue(supervisor.read_config()["modules_experimental"])

    def test_site_follows_the_current_privacy_mode(self):
        FakeHost.made.clear()
        held = {"cfg": {"location_display": "exact", "site": {"lat": 38.9217, "lon": -77.0669, "n": 10}}}
        with mock.patch.object(loader, "ModuleHost", FakeHost):
            h = supervisor.make_host(lambda: held["cfg"], emit=lambda *a: None)
        self.assertIsNotNone(h.site())
        held["cfg"] = dict(held["cfg"], location_display="hidden")
        self.assertIsNone(h.site())


if __name__ == "__main__":
    unittest.main()
