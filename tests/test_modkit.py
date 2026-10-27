"""Module kit: manifests, interface versions, schemas, ctx, storage, the loader and its CLI.

No hardware or network. Modules under test are written to temporary folders,
except the repository's own modules/sdr-pps-marker, the first module loaded.
"""

import io
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tests import _env  # noqa: F401
from gps_time_pi import modkit
from gps_time_pi.modkit import loader, schema
from gps_time_pi.modkit.__main__ import main as cli
from gps_time_pi.modkit.context import CappedStorage, StorageFull
from gps_time_pi.modkit.manifest import interface_compatible, read

ROOT = Path(__file__).resolve().parents[1]
REPO_MODULES = ROOT / "modules"
# Modules run sandboxed in their own process; on Windows (no sandbox) the tests run them unenforced.
HOST_KW = {"allow_unenforced": os.name == "nt"}

GOOD = """
name = "{name}"
version = "0.1.0"
types = ["source"]
maturity = "experimental"
interface = "{interface}"
summary = "test module"

[entry]
source = "{pkg}.src:S"

[hardware]
required = "none"

[timing]
needed = "s"
if_worse = "nothing"

[permissions]
network = false
devices = []
storage = "{storage}"

[licence]
code = "MIT"
"""

SRC_OK = """
from gps_time_pi.labels import q
from gps_time_pi.modkit import Observation, Source

class S(Source):
    def start(self, ctx):
        ctx.emit(Observation(time_ns=ctx.now_ns(), source=ctx.name, values={"v": q(1.0, "V", "observed")},
                             timing=ctx.timing_quality()))
        ctx.emit({"schema": "observation/1", "time_ns": 1, "source": ctx.name,
                  "values": {"v": {"value": 1, "unit": "V", "provenance": "guessed"}}, "timing": {}})
        if ctx.storage is not None:
            ctx.storage.write("state.json", b"{}")
        site = ctx.site()
        ctx.emit(Observation(time_ns=ctx.now_ns(), source=ctx.name,
                             values={"lat": q(None if site is None else site["lat"], "deg", "external")},
                             timing={}))
"""

SRC_CRASH = """
from gps_time_pi.modkit import Source

class S(Source):
    def start(self, ctx):
        raise RuntimeError("sensor on fire")
"""

SRC_NOT_A_SOURCE = """
class S:
    def start(self, ctx):
        pass
"""


class ModuleDir(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.addCleanup(self._unimport)
        self.pkgs = []

    def _unimport(self):
        for pkg in self.pkgs:
            for k in [k for k in sys.modules if k == pkg or k.startswith(pkg + ".")]:
                del sys.modules[k]
        sys.path[:] = [p for p in sys.path if not p.startswith(str(self.root))]

    def make(self, name, src=SRC_OK, interface="1.0", storage="none", manifest=None):
        pkg = name.replace("-", "_")
        self.pkgs.append(pkg)
        d = self.root / name
        (d / pkg).mkdir(parents=True)
        (d / pkg / "__init__.py").write_text("", encoding="utf-8")
        (d / pkg / "src.py").write_text(textwrap.dedent(src), encoding="utf-8")
        text = manifest if manifest is not None else GOOD.format(name=name, pkg=pkg, interface=interface, storage=storage)
        (d / "module.toml").write_text(text, encoding="utf-8")
        return d


class TestManifest(ModuleDir):
    def test_valid(self):
        m, errs = read(self.make("good-one"))
        self.assertEqual(errs, [])
        self.assertEqual((m.name, m.types, m.entry["source"]), ("good-one", ("source",), "good_one.src:S"))

    def test_invalid_cases(self):
        cases = {
            "wrong-name": GOOD.format(name="other", pkg="x", interface="1.0", storage="none"),
            "no-entry": GOOD.format(name="no-entry", pkg="x", interface="1.0", storage="none").replace('[entry]\nsource = "x.src:S"\n', ""),
            "bad-maturity": GOOD.format(name="bad-maturity", pkg="x", interface="1.0", storage="none").replace("experimental", "stable"),
            "bad-storage": GOOD.format(name="bad-storage", pkg="x", interface="1.0", storage="lots"),
            "not-toml": "name = ",
            "new-interface": GOOD.format(name="new-interface", pkg="x", interface="1.9", storage="none"),
        }
        for name, text in cases.items():
            with self.subTest(name):
                m, errs = read(self.make(name, manifest=text))
                self.assertIsNone(m)
                self.assertTrue(errs)

    def test_interface_versions(self):
        self.assertEqual(modkit.INTERFACE_VERSION, "1.0.0")
        self.assertTrue(interface_compatible("1.0", "1.0.0"))
        self.assertTrue(interface_compatible("1.0", "1.3.2"))
        self.assertFalse(interface_compatible("1.4", "1.3.2"))
        self.assertFalse(interface_compatible("2.0", "1.3.2"))
        self.assertFalse(interface_compatible("one", "1.0.0"))

    def test_repository_modules_are_valid(self):
        found = loader.discover(REPO_MODULES)
        self.assertIn("sdr-pps-marker", [d.name for d, _, _ in found])
        for d, m, errs in found:
            self.assertEqual(errs, [], d.name)


class TestHost(ModuleDir):
    def host(self, enabled, **kw):
        out = []
        h = loader.ModuleHost(self.root, enabled, emit=lambda name, item: out.append((name, item)), **HOST_KW, **kw)
        h.load()
        return h, out

    def state(self, h, name):
        return next(s for s in h.status() if s["name"] == name)

    def test_off_by_default(self):
        self.make("quiet")
        h, out = self.host([])
        h.start(wait=True)
        self.assertEqual(self.state(h, "quiet")["state"], "disabled")
        self.assertEqual(out, [])
        self.assertNotIn("quiet", sys.modules)

    def test_enabled_module_runs_and_invalid_items_are_dropped(self):
        self.make("runs")
        h, out = self.host(["runs"], site=lambda: {"lat": 38.9, "lon": -77.1})
        h.start(wait=True)
        st = self.state(h, "runs")
        self.assertEqual((st["state"], st["emitted"], st["rejected"]), ("finished", 2, 1))
        for _, item in out:
            self.assertEqual(schema.validate(item, schema.load("observation.v1")), [])
        self.assertEqual(out[1][1]["values"]["lat"]["value"], 38.9, "ctx.site() is what the host gives")

    def test_crash_is_contained(self):
        self.make("crashes", SRC_CRASH)
        self.make("fine")
        h, out = self.host(["crashes", "fine"])
        h.start(wait=True)
        self.assertEqual(self.state(h, "crashes")["state"], "failed")
        self.assertIn("sensor on fire", self.state(h, "crashes")["reason"])
        self.assertEqual(self.state(h, "fine")["state"], "finished")

    def test_refusals(self):
        self.make("not-a-source", SRC_NOT_A_SOURCE)
        self.make("broken-import", "import no_such_package_here\n")
        self.make("too-new", interface="2.0")
        h, _ = self.host(["not-a-source", "broken-import", "too-new", "missing"])
        for name in ("too-new", "missing"):
            self.assertEqual(self.state(h, name)["state"], "refused", name)
        self.assertIn("interface", self.state(h, "too-new")["reason"])
        # module code is only imported in the module's own process, so these fail when started
        h.start(wait=True)
        for name in ("not-a-source", "broken-import"):
            self.assertEqual(self.state(h, name)["state"], "failed", name)
            self.assertIn("entry point failed", self.state(h, name)["reason"])
        self.assertNotIn("broken_import", sys.modules, "the host never imports module code")

    def test_storage_needs_a_host_root_and_is_capped(self):
        self.make("wants-disk", storage="disk:1MiB")
        h, _ = self.host(["wants-disk"])
        h.start(wait=True)
        self.assertEqual(self.state(h, "wants-disk")["state"], "refused")
        h2, _ = self.host(["wants-disk"], storage_roots={"disk": str(self.root / "store")})
        h2.start(wait=True)
        self.assertEqual(self.state(h2, "wants-disk")["state"], "finished")
        self.assertTrue((self.root / "store" / "wants-disk" / "state.json").is_file())

    def test_capped_storage(self):
        s = CappedStorage(self.root / "cap", 10)
        s.write("a", b"12345")
        s.write("a", b"1234567890")       # replacing counts only the difference
        with self.assertRaises(StorageFull):
            s.write("b", b"1")
        for bad in ("", "../x", "a/b", ".hidden"):
            with self.assertRaises(ValueError):
                s.write(bad, b"")
        self.assertEqual(s.read("a"), b"1234567890")
        self.assertEqual([p.name for p in (self.root / "cap").iterdir()], ["a"], "no temporary files left")

    def test_capped_storage_names_and_delete(self):
        s = CappedStorage(self.root / "cap2", 100)
        s.write("old", b"1")
        os.utime(self.root / "cap2" / "old", ns=(1_000_000_000, 1_000_000_000))
        s.write("new", b"22")
        self.assertEqual(s.names(), ["old", "new"])          # oldest first
        self.assertTrue(s.delete("old"))
        self.assertFalse(s.delete("old"))
        self.assertEqual(s.names(), ["new"])
        s.write("x", b"1" * 98)                               # the space came back
        with self.assertRaises(ValueError):
            s.delete("../new")


class TestFirstModule(unittest.TestCase):
    """sdr-pps-marker is the first module the loader loads."""

    def test_loads_and_runs_its_demo(self):
        out = []
        ram = tempfile.mkdtemp(prefix="gtp-ram-")
        self.addCleanup(shutil.rmtree, ram, ignore_errors=True)
        h = loader.ModuleHost(REPO_MODULES, ["sdr-pps-marker"],
                              configs={"sdr-pps-marker": {"demo": True, "scenarios": ["clean", "usb-drop"]}},
                              emit=lambda name, item: out.append(item),
                              storage_roots={"ram": ram}, **HOST_KW)
        h.load()
        h.start(wait=True)
        st = next(s for s in h.status() if s["name"] == "sdr-pps-marker")
        self.assertEqual((st["state"], st["emitted"], st["rejected"]), ("finished", 2, 0), st)
        self.assertEqual([o["values"]["scenario"]["value"] for o in out], ["clean", "usb-drop"])
        self.assertEqual(out[1]["values"]["dropped_sample_events"]["value"], 1)
        self.assertEqual({o["values"]["time_source"]["value"] for o in out}, {"pps_marker"})
        self.assertEqual(out[0]["timing"]["state"], "UNKNOWN", "no host timing given: UNKNOWN, not invented")

    def test_without_demo_it_emits_nothing(self):
        out = []
        h = loader.ModuleHost(REPO_MODULES, ["sdr-pps-marker"], emit=lambda name, item: out.append(item), **HOST_KW)
        h.load()
        h.start(wait=True)
        self.assertEqual(out, [])


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        o, e = io.StringIO(), io.StringIO()
        with redirect_stdout(o), redirect_stderr(e):
            code = cli(list(args))
        return code, o.getvalue(), e.getvalue()

    def test_check_and_list(self):
        code, out, _ = self.run_cli("--dir", str(REPO_MODULES), "check")
        self.assertEqual(code, 0)
        self.assertIn("sdr-pps-marker: ok", out)
        code, out, _ = self.run_cli("--dir", str(REPO_MODULES), "list")
        self.assertIn("sdr-pps-marker 0.2.0 [research] source: disabled", out)

    def test_check_fails_on_an_invalid_manifest(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "bad").mkdir()
        (d / "bad" / "module.toml").write_text('name = "bad"\n', encoding="utf-8")
        code, out, _ = self.run_cli("--dir", str(d), "check")
        self.assertEqual(code, 1)
        self.assertIn("bad: INVALID", out)

    def test_demo(self):
        code, out, err = self.run_cli("--dir", str(REPO_MODULES), "demo", "sdr-pps-marker")
        self.assertEqual(code, 0, err)
        items = [json.loads(l) for l in out.splitlines()]
        self.assertGreaterEqual(len(items), 7)
        self.assertEqual({i["source"] for i in items}, {"sdr-pps-marker"})


class TestNoBehaviourChange(unittest.TestCase):
    def test_web_service_does_not_load_modules(self):
        # Only the settings part of the kit (manifests, the Administration switch); never a host.
        server = (ROOT / "gps_time_pi" / "server.py").read_text(encoding="utf-8")
        self.assertEqual([l for l in server.splitlines() if "modkit" in l and "import" in l],
                         ["from .modkit import settings as modsettings"])
        self.assertNotIn("ModuleHost", server)

    def test_bundle_ships_the_kit_and_schemas_but_no_modules(self):
        build = (ROOT / "tools" / "build_bundles.py").read_text(encoding="utf-8")
        self.assertIn('"schemas"', build)
        self.assertNotIn('"modules"', build)

    def test_schemas_parse(self):
        for f in (ROOT / "schemas").glob("*.json"):
            self.assertIn("$id", json.loads(f.read_text(encoding="utf-8")), f.name)


if __name__ == "__main__":
    unittest.main()
