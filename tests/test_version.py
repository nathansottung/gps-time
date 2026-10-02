"""Version string read from the git tag (gps_time_pi/version.py) and shipped in bundles."""

import shutil
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

import gps_time_pi
from gps_time_pi import demo, version
from tests.test_packaging import _load_build_bundles


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
                   check=True, capture_output=True)


class TestNormalize(unittest.TestCase):
    def test_drops_leading_v_and_whitespace(self):
        self.assertEqual(version.normalize("v1.4.0-rc.1\n"), "1.4.0-rc.1")
        self.assertEqual(version.normalize("1.4.0-rc.1-3-gabc1234-dirty"), "1.4.0-rc.1-3-gabc1234-dirty")

    def test_rejects_non_versions(self):
        for bad in ("", "  ", "vx", "main", "1.0\n2.0", "9" * 65):
            with self.subTest(bad=bad):
                self.assertIsNone(version.normalize(bad))


class TestResolution(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_version_file_wins(self):
        f = self.tmp / "VERSION"
        f.write_text("1.4.0-rc.1\n", encoding="utf-8")
        self.assertEqual(version.app_version(path=f, repo=self.tmp), "1.4.0-rc.1")

    def test_unknown_without_file_or_checkout(self):
        self.assertIsNone(version.describe(self.tmp))
        self.assertEqual(version.app_version(path=self.tmp / "VERSION", repo=self.tmp), "unknown")

    def test_unreadable_file_falls_through(self):
        f = self.tmp / "VERSION"
        f.write_bytes(b"\xff\xfe")
        self.assertEqual(version.app_version(path=f, repo=self.tmp), "unknown")

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_describe_reads_the_tag(self):
        _git(self.tmp, "init", "-q")
        (self.tmp / "a").write_text("1", encoding="utf-8")
        _git(self.tmp, "add", "a")
        _git(self.tmp, "commit", "-qm", "one")
        self.assertIsNone(version.describe(self.tmp), "no tag yet")
        _git(self.tmp, "tag", "-a", "v9.8.7", "-m", "t")
        self.assertEqual(version.describe(self.tmp), "9.8.7")
        (self.tmp / "a").write_text("2", encoding="utf-8")
        self.assertEqual(version.describe(self.tmp), "9.8.7-dirty")
        _git(self.tmp, "commit", "-qam", "two")
        self.assertRegex(version.describe(self.tmp), r"^9\.8\.7-1-g[0-9a-f]+$")


class TestReported(unittest.TestCase):
    def test_demo_reports_the_real_app_version(self):
        self.assertEqual(demo.core_api()["versions"]["app"], gps_time_pi.__version__)


class TestBundlesCarryVersion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bb = _load_build_bundles()
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pi_tar_has_version_file(self):
        out = Path(self.tmp.name) / "pi.tar.gz"
        self.bb.build_pi_tar(out, version="9.8.7")
        with tarfile.open(out) as t:
            m = t.getmember("gps-time/gps_time_pi/VERSION")
            self.assertEqual(m.mode & 0o777, 0o644)
            self.assertEqual(t.extractfile(m).read(), b"9.8.7\n")
            self.assertEqual(t.getnames().count("gps-time/gps_time_pi/VERSION"), 1)

    def test_dev_zip_has_version_file(self):
        out = Path(self.tmp.name) / "dev.zip"
        self.bb.build_repo_zip(out, version="9.8.7")
        with zipfile.ZipFile(out) as z:
            self.assertEqual(z.read("gps-time/gps_time_pi/VERSION"), b"9.8.7\n")


if __name__ == "__main__":
    unittest.main()
