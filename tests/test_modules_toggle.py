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


class TestListingRuns(ModulesDir):
    def test_an_analysis_only_module_is_never_listed_as_running(self):
        shutil.copytree(REPO_MODULES / "analysis-tower-delay-check", self.root / "analysis-tower-delay-check",
                        ignore=shutil.ignore_patterns("__pycache__"))
        cfg = {"modules_experimental": True, "modules_enabled": ["analysis-tower-delay-check", "sdr-pps-marker"]}
        rows = {r["name"]: r for r in settings.listing(cfg, root=self.root, status_path=self.status)["modules"]}
        self.assertTrue(rows["analysis-tower-delay-check"]["valid"])
        self.assertFalse(rows["analysis-tower-delay-check"]["runs"])
        self.assertFalse(rows["analysis-tower-delay-check"]["host_runs"])
        self.assertTrue(rows["sdr-pps-marker"]["runs"])
        self.assertTrue(rows["sdr-pps-marker"]["host_runs"])


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


class TestModuleConfig(ModulesDir):
    """A module's settings from Administration: only its manifest's keys and types, no position."""

    def apply(self, cfg, body):
        return settings.apply(cfg, body, root=self.root)

    def test_set_and_clear(self):
        cfg = {}
        live = {"fs_nominal": 2400000, "rtl_tcp": {"plan": [{"center_hz": 88800000, "dwell_s": 10}]}}
        r = self.apply(cfg, {"module": "sdr-pps-marker", "config": live})
        self.assertEqual(r, {"ok": True, "module": "sdr-pps-marker", "config": live})
        self.assertEqual(cfg["module_config"]["sdr-pps-marker"], live)
        self.assertNotIn("modules_enabled", cfg)                # settings never turn a module on
        self.apply(cfg, {"module": "sdr-pps-marker", "config": None})
        self.assertEqual(cfg["module_config"], {})

    def test_refusals(self):
        bad = [({"module": "sdr-pps-marker", "config": []}, 400),
               ({"module": "sdr-pps-marker", "config": {"nope": 1}}, 400),
               ({"module": "sdr-pps-marker", "config": {"fs_nominal": "fast"}}, 400),
               ({"module": "sdr-pps-marker", "config": {"fs_nominal": True}}, 400),
               ({"module": "sdr-pps-marker", "config": {"station_id": "x" * 301}}, 400),
               ({"module": "sdr-pps-marker", "config": {"rtl_tcp": "127.0.0.1"}}, 400),
               ({"module": "sdr-pps-marker", "config": {"rtl_tcp": {"plan": [{"lat": 38.9217}]}}}, 400),
               ({"module": "sdr-pps-marker", "config": {"station_id": "x", "rtl_tcp": {"p": "y" * 9000}}}, 400),
               ({"module": "nope", "config": {}}, 404),
               ({"module": "broken", "config": {}}, 409)]
        for body, code in bad:
            cfg = {}
            with self.subTest(body=str(body)[:80]):
                with self.assertRaises(settings.SettingError) as e:
                    self.apply(cfg, body)
                self.assertEqual(e.exception.code, code)
                self.assertEqual(cfg, {})

    def test_listing_shows_settings_schema_and_readiness(self):
        cfg = {"module_config": {"sdr-pps-marker": {"fs_nominal": 2400000}}}
        ready = {"sdr-pps-marker": [{"check": "rtl_tcp running", "ok": True, "detail": "active"}]}
        rows = {m["name"]: m for m in settings.listing(cfg, root=self.root, status_path=self.status,
                                                       readiness=ready)["modules"]}
        row = rows["sdr-pps-marker"]
        self.assertEqual(row["config"], {"fs_nominal": 2400000})
        self.assertEqual(row["config_schema"]["fs_nominal"], {"type": "float", "unit": "Hz",
                                                              "description": "SDR sample rate as set"})
        self.assertEqual(row["config_schema"]["pulse_width_s"]["default"], 0.1)
        self.assertEqual(row["readiness"], ready["sdr-pps-marker"])
        self.assertEqual((rows["broken"]["config_schema"], rows["broken"]["readiness"]), ({}, None))


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

    def status_with(self, items, updated=1000.0):
        self.status.write_text(json.dumps({"updated": updated, "modules": [
            {"name": "sdr-pps-marker", "state": "running", "reason": ""}],
            "latest": {"sdr-pps-marker": items}}), encoding="utf-8")

    def row(self, now=1005.0):
        return next(r for r in self.listing({}, now=now)["modules"] if r["name"] == "sdr-pps-marker")

    def test_latest_output_is_the_newest_item_with_its_labels(self):
        old = {"schema": "observation/1", "time_ns": 990_000_000_000, "values": {
            "markers": {"value": 3, "unit": None, "provenance": "observed"}}}
        new = {"schema": "observation/1", "time_ns": 1_002_000_000_000, "values": {
            "markers": {"value": 9, "unit": None, "provenance": "observed"},
            "clock_error_ppm": {"value": 23.1, "unit": "ppm", "provenance": "calculated", "note": "n" * 500},
            "state": {"value": "OK", "unit": None, "provenance": "calculated"}}}
        self.status_with([old, new])
        lt = self.row()["latest"]
        self.assertEqual((lt["kind"], lt["time_ns"], lt["age_s"], lt["items_kept"], lt["left_out"]),
                         ("observation", 1_002_000_000_000, 3.0, 2, 0))
        self.assertEqual(lt["values"]["markers"], {"value": 9, "unit": None, "provenance": "observed"})
        self.assertEqual(len(lt["values"]["clock_error_ppm"]["note"]), settings.MAX_TEXT)
        self.status_with([{"analysis": "x", "time_ns": 1, "values": {}}])
        self.assertEqual(self.row()["latest"]["kind"], "result")

    def test_no_position_and_no_unlabeled_value_passes(self):
        self.status_with([{"time_ns": 1_002_000_000_000, "values": {
            "lat": {"value": 38.9217, "unit": "deg", "provenance": "external"},
            "LON": {"value": -77.0669, "unit": "deg", "provenance": "external"},
            "alt_m": {"value": 92.0, "unit": "m", "provenance": "external"},
            "position": {"value": "38.9217,-77.0669", "unit": None, "provenance": "observed"},
            "unlabeled": {"value": 1, "unit": None},
            "relabeled": {"value": 1, "unit": None, "provenance": "measured"},
            "nested": {"value": {"a": 1}, "unit": None, "provenance": "observed"},
            "ok": {"value": 1.5, "unit": "s", "provenance": "calculated"}}}])
        lt = self.row()["latest"]
        self.assertEqual(list(lt["values"]), ["ok"])
        self.assertEqual(lt["left_out"], 7)
        self.assertNotIn("38.92", json.dumps(lt))
        self.assertNotIn("77.06", json.dumps(lt))

    def test_values_are_bounded_and_stale_status_shows_nothing(self):
        self.status_with([{"time_ns": 1, "values": {f"v{i}": {"value": i, "unit": None, "provenance": "observed"}
                                                    for i in range(settings.MAX_VALUES + 5)}}])
        lt = self.row()["latest"]
        self.assertEqual((len(lt["values"]), lt["left_out"]), (settings.MAX_VALUES, 5))
        self.assertIsNone(self.row(now=1000.0 + settings.STATUS_FRESH_S + 1)["latest"])
        self.status_with([])
        self.assertIsNone(self.row()["latest"])
        self.status_with(["not an item"])
        self.assertIsNone(self.row()["latest"])


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

    def test_settings_need_the_token_and_are_saved(self):
        live = {"fs_nominal": 2400000}
        if not self.demo:    # demo mode takes no token, as for every setting
            self.assertEqual(self.post("/api/setting", {"module": "sdr-pps-marker", "config": live}, token=None)[0], 401)
            self.assertNotIn("module_config", self.saved())
        status, _, body = self.post("/api/setting", {"module": "sdr-pps-marker", "config": live})
        self.assertEqual((status, body["config"]), (200, live))
        self.assertEqual(self.saved()["module_config"], {"sdr-pps-marker": live})
        status, _, body = self.req("GET", "/api/modules")
        row = body["modules"][0]
        self.assertEqual(row["config"], live)
        self.assertEqual([c["check"] for c in row["readiness"]][:2], ["rtl_tcp running", "live capture configured"])
        self.assertEqual(self.post("/api/setting", {"module": "sdr-pps-marker", "config": {"lat": 1.0}})[0], 400)

    def test_sdr_status_is_read_only_and_needs_no_token(self):
        status, _, body = self.req("GET", "/api/sdr")
        self.assertEqual(status, 200)
        self.assertEqual(set(body), {"installed", "units", "dongles", "feeds", "note"})

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
