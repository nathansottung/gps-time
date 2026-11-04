"""Runs the tests of every module under modules/ with the station's own tests.

Module tests live in modules/<name>/tests/ (layout in
docs/specs/SPEC-EXTENSIBILITY.md). Their folder is also called "tests", which
would clash with this package, so each file is loaded by path under its own
name. The module's directory goes on sys.path so its package imports.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "modules"


def module_dirs():
    return sorted(p for p in MODULES.iterdir() if (p / "module.toml").is_file()) if MODULES.is_dir() else []


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for mod_dir in module_dirs():
        if str(mod_dir) not in sys.path:
            sys.path.insert(0, str(mod_dir))
        for f in sorted((mod_dir / "tests").glob("test_*.py")):
            name = f"_module_tests.{mod_dir.name.replace('-', '_')}.{f.stem}"
            spec = importlib.util.spec_from_file_location(name, f)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            suite.addTests(loader.loadTestsFromModule(mod))
    suite.addTests(loader.loadTestsFromTestCase(TestModuleLayout))
    return suite


class TestModuleLayout(unittest.TestCase):
    def test_every_module_has_the_spec_layout(self):
        dirs = module_dirs()
        self.assertTrue(dirs, "at least one module")
        for d in dirs:
            with self.subTest(d.name):
                for part in ("module.toml", "README.md", "tests", "fixtures"):
                    self.assertTrue((d / part).exists(), f"{d.name}: {part}")
                self.assertTrue(list((d / "tests").glob("test_*.py")), f"{d.name}: no tests")

    def test_station_bundle_ships_the_modules_install_sh_installs(self):
        # install.sh copies modules/ (since #146; all off). v1.6.0-rc.1's bundle lacked it and the
        # install stopped there (#155). The full install from a bundle: tests/test_bundle_install.py.
        from tests.test_packaging import _load_build_bundles
        self.assertIn("modules", _load_build_bundles().PI_TOP)
        self.assertIn("cp -r modules", (ROOT / "install.sh").read_text(encoding="utf-8"))
