"""Serving the built web UI (web/dist) under /app/.

Uses a temporary dist tree, so no Node build, network or root is needed.
"""

import http.client
import os
import shutil
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

from tests import _env  # noqa: F401  (sets GTP_* paths before gps_time_pi is imported)
from gps_time_pi import server


class WebUiBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gps-time-web-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.dist = os.path.join(self.tmp, "dist")
        os.makedirs(os.path.join(self.dist, "assets"))
        self.write("index.html", "<!doctype html><title>GPS Time</title><div id=root></div>")
        self.write("assets/index-abc123.js", "console.log('app')")
        self.write("assets/index-abc123.css", "body{}")
        self.write("assets/inter-400.woff2", b"wOF2")
        self.write("favicon.svg", "<svg/>")
        # a file next to (not inside) dist that must never be reachable
        with open(os.path.join(self.tmp, "secret.txt"), "w") as f:
            f.write("outside dist")

        p = mock.patch.object(server, "WEB_DIST", self.dist)
        p.start()
        self.addCleanup(p.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def write(self, rel, body):
        path = os.path.join(self.dist, *rel.split("/"))
        with open(path, "wb" if isinstance(body, bytes) else "w") as f:
            f.write(body)

    def get(self, raw_path):
        """GET with the path sent verbatim (no client-side normalization)."""
        c = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=10)
        self.addCleanup(c.close)
        c.putrequest("GET", raw_path, skip_accept_encoding=True)
        c.endheaders()
        r = c.getresponse()
        return r.status, dict(r.getheaders()), r.read()


class TestWebUi(WebUiBase):
    def test_app_redirects_to_trailing_slash(self):
        status, headers, _ = self.get("/app?source=demo")
        self.assertEqual(status, 301)
        self.assertEqual(headers["Location"], "/app/?source=demo")

    def test_index_is_served_uncached(self):
        status, headers, body = self.get("/app/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn(b"<div id=root>", body)

    def test_hashed_assets_are_immutable_with_correct_types(self):
        for path, ctype in (("/app/assets/index-abc123.js", "application/javascript"),
                            ("/app/assets/index-abc123.css", "text/css"),
                            ("/app/assets/inter-400.woff2", "font/woff2")):
            status, headers, _ = self.get(path)
            self.assertEqual(status, 200, path)
            self.assertTrue(headers["Content-Type"].startswith(ctype), headers["Content-Type"])
            self.assertIn("immutable", headers["Cache-Control"])

    def test_non_asset_files_get_short_cache(self):
        status, headers, _ = self.get("/app/favicon.svg")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/svg+xml")
        self.assertEqual(headers["Cache-Control"], "max-age=300")

    def test_extensionless_path_falls_back_to_index(self):
        status, _, body = self.get("/app/timing")
        self.assertEqual(status, 200)
        self.assertIn(b"<div id=root>", body)

    def test_missing_file_with_extension_is_404(self):
        status, _, _ = self.get("/app/assets/missing.js")
        self.assertEqual(status, 404)

    def test_path_traversal_is_refused(self):
        for raw in ("/app/../secret.txt", "/app/%2e%2e/secret.txt", "/app/assets/..%2f..%2fsecret.txt",
                    "/app/..%5csecret.txt", "/app/%2e%2e%2f%2e%2e%2fgps_time_pi%2fserver.py"):
            status, _, body = self.get(raw)
            self.assertNotEqual(status, 200, raw)
            self.assertNotIn(b"outside dist", body, raw)

    def test_nul_byte_is_refused(self):
        status, _, _ = self.get("/app/index.html%00.js")
        self.assertEqual(status, 404)

    def test_unbuilt_ui_explains_how_to_build(self):
        os.remove(os.path.join(self.dist, "index.html"))
        status, headers, body = self.get("/app/")
        self.assertEqual(status, 503)
        self.assertIn("text/plain", headers["Content-Type"])
        self.assertIn(b"pnpm run build", body)

    def test_legacy_pages_are_unchanged(self):
        for path in ("/", "/legacy", "/almanac", "/history", "/admin", "/configure"):
            status, headers, _ = self.get(path)
            self.assertEqual(status, 200, path)
            self.assertIn("text/html", headers["Content-Type"])


class TestWebFile(WebUiBase):
    def test_web_file_rejects_paths_outside_dist(self):
        self.assertIsNone(server.web_file("../secret.txt"))
        self.assertIsNone(server.web_file(os.path.join(self.tmp, "secret.txt")))
        self.assertIsNotNone(server.web_file("index.html"))

    @unittest.skipIf(os.name == "nt", "symlinks need extra privileges on Windows")
    def test_symlink_out_of_dist_is_refused(self):
        os.symlink(os.path.join(self.tmp, "secret.txt"), os.path.join(self.dist, "link.txt"))
        self.assertIsNone(server.web_file("link.txt"))


if __name__ == "__main__":
    unittest.main()
