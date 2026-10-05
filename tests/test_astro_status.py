"""Astronomy says *why* it is unavailable (ephemeris missing, unreadable,
truncated; a failed calculation), instead of a bare "unavailable"."""

import contextlib
import io
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import astro, server
from tests.test_location_privacy import PrivacyBase

ROOT = Path(__file__).resolve().parents[1]


class TestEphemerisProblem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "de440s.bsp")

    def test_missing(self):
        reason = astro.ephemeris_problem(self.path)
        self.assertIn("is missing", reason)
        self.assertIn(self.path, reason)
        self.assertIn("install.sh", reason)

    def test_truncated(self):
        Path(self.path).write_bytes(b"DAF")
        self.assertIn("empty or truncated", astro.ephemeris_problem(self.path))

    def test_present_and_readable(self):
        Path(self.path).write_bytes(b"DAF/SPK " + b"\0" * 64)
        self.assertIsNone(astro.ephemeris_problem(self.path))

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "needs POSIX permissions and a non-root user")
    def test_not_readable_by_this_user_is_not_called_missing(self):
        Path(self.path).write_bytes(b"DAF/SPK " + b"\0" * 64)
        os.chmod(self.path, 0)
        self.addCleanup(os.chmod, self.path, 0o600)
        reason = astro.ephemeris_problem(self.path)
        self.assertIn("not readable by the service user", reason)
        self.assertNotIn("is missing", reason)

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "needs POSIX permissions and a non-root user")
    def test_unsearchable_directory_is_not_called_missing(self):
        Path(self.path).write_bytes(b"DAF/SPK " + b"\0" * 64)
        os.chmod(self.tmp.name, 0)
        self.addCleanup(os.chmod, self.tmp.name, 0o700)
        self.assertIn("not readable by the service user", astro.ephemeris_problem(self.path))


class TestPortableLabel(unittest.TestCase):
    def test_midnight_label_has_no_padding_and_no_glibc_flag(self):
        self.assertEqual(astro._midnight_label(datetime(2026, 10, 5, tzinfo=timezone.utc)), "midnight → Oct 5")
        self.assertEqual(astro._midnight_label(datetime(2026, 12, 25, tzinfo=timezone.utc)), "midnight → Dec 25")
        src = (ROOT / "gps_time_pi" / "astro.py").read_text(encoding="utf-8")
        self.assertNotRegex(src, r"strftime\([^)\n]*%-", "a %-x flag inside a strftime call")


class TestFailureIsReported(PrivacyBase):
    def _raise(self, *a, **k):
        raise TypeError("only 0-dimensional arrays can be converted to Python scalars")

    def test_almanac_exception_becomes_a_reason(self):
        err = io.StringIO()
        with mock.patch.object(astro, "solar_day", self._raise), contextlib.redirect_stderr(err):
            d = self.almanac()
        self.assertIs(d["available"], False)
        self.assertIn("Astronomy calculation failed (TypeError: only 0-dimensional", d["reason"])
        self.assertNotIn("error", d)
        self.assertIn("Traceback", err.getvalue(), "the traceback goes to the journal")

    def test_object_exception_becomes_a_reason(self):
        with mock.patch.object(astro, "object_report", self._raise), contextlib.redirect_stderr(io.StringIO()):
            d = self.obj()
        self.assertIs(d["available"], False)
        self.assertIn("TypeError", d["reason"])

    def test_unavailable_status_reason_is_passed_through(self):
        with mock.patch.dict(astro.STATUS, {"available": False, "reason": "ephemeris is missing"}):
            self.assertEqual(self.almanac(), {"available": False, "reason": "ephemeris is missing"})

    def test_normal_answers_are_unchanged(self):
        self.assertTrue(self.almanac()["available"])
        self.assertEqual(server.object_api({"q": [""]}), {"error": "unparsed"})


class TestInstaller(unittest.TestCase):
    def test_installer_makes_code_and_ephemeris_readable_and_self_checks(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        chmod = text.index('chmod -R a+rX "$DEST/gps_time_pi" "$VENV"')
        self.assertLess(text.index('curl -L --fail -o "$EPH"'), chmod)
        check = text.index('runuser -u gps-time -- "$VENV/bin/python"')
        self.assertLess(text.index("systemctl restart gps-time-pi"), check)
        self.assertIn("Astronomy: UNAVAILABLE - ", text[check:])
        # never loosens the secrets or the state directory itself
        self.assertNotRegex(text, r'chmod -R a\+rX "\$DEST"(\s|$)')


if __name__ == "__main__":
    unittest.main()
