"""tools/new_module.py: every type it creates is valid, loads, and its generated tests pass as created."""

import importlib.util
import io
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tests import _env  # noqa: F401
from gps_time_pi.modkit import loader
from gps_time_pi.modkit.manifest import read

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("new_module", ROOT / "tools" / "new_module.py")
new_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(new_module)


class TestScaffold(unittest.TestCase):
    def setUp(self):
        self.dest = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dest, ignore_errors=True)
        self.added = []
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        sys.path[:] = [p for p in sys.path if not p.startswith(str(self.dest))]
        for pkg in self.added:
            for k in [k for k in sys.modules if k == pkg or k.startswith(pkg + ".") or k.startswith("_gen_")]:
                del sys.modules[k]

    def run_generated_tests(self, d):
        sys.path.insert(0, str(d))
        suite = unittest.TestSuite()
        for f in (d / "tests").glob("test_*.py"):
            sp = importlib.util.spec_from_file_location(f"_gen_{d.name.replace('-', '_')}_{f.stem}", f)
            mod = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(mod)
            suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(mod))
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        return result

    def test_every_type_passes_out_of_the_box(self):
        for kind in new_module.TYPES:
            with self.subTest(kind):
                name = f"my-{kind}-module"
                self.added.append(name.replace("-", "_"))
                d = new_module.scaffold(name, kind, self.dest)
                for part in ("module.toml", "README.md", "fixtures/sample.json", "web/Card.tsx",
                             f"tests/test_{name.replace('-', '_')}.py"):
                    self.assertTrue((d / part).is_file(), part)
                m, errs = read(d)
                self.assertEqual(errs, [], errs)
                self.assertEqual(m.types, (kind,))
                r = self.run_generated_tests(d)
                self.assertTrue(r.wasSuccessful(), [str(x) for x in r.failures + r.errors])
                self.assertGreaterEqual(r.testsRun, 2)

    def test_generated_source_runs_under_the_loader(self):
        d = new_module.scaffold("my-sensor", "source", self.dest)
        self.added.append("my_sensor")
        out = []
        h = loader.ModuleHost(self.dest, ["my-sensor"], configs={"my-sensor": {"demo": True}},
                              emit=lambda name, item: out.append(item))
        h.load()
        h.start(wait=True)
        st = h.status()[0]
        self.assertEqual((st["state"], st["emitted"], st["rejected"]), ("finished", 2, 0), st)

    def test_refuses_bad_names_types_and_existing_folders(self):
        for name, kind in (("Bad_Name", "source"), ("x", "source"), ("ok-name", "teleport")):
            with self.assertRaises(SystemExit):
                new_module.scaffold(name, kind, self.dest)
        new_module.scaffold("twice", "ui", self.dest)
        with self.assertRaises(SystemExit):
            new_module.scaffold("twice", "ui", self.dest)

    def test_cli(self):
        o = io.StringIO()
        with redirect_stdout(o), redirect_stderr(io.StringIO()):
            self.assertEqual(new_module.main(["cli-made", "--type", "analysis", "--dest", str(self.dest)]), 0)
        self.added.append("cli_made")
        self.assertIn("created", o.getvalue())
        self.assertTrue((self.dest / "cli-made" / "cli_made" / "analysis.py").is_file())


if __name__ == "__main__":
    unittest.main()
