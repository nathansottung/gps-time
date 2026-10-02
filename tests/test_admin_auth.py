"""Administrative security (review GPS-014, GPS-017, GPS-019).

Over real HTTP against server.Handler: state changes are POST-only, need
application/json, a same-origin (or allowlisted) Origin, an allowed Host and,
outside demo mode, the admin token. Demo mode never runs host actions. Also
static checks of the service unit and polkit rule. No root, network or Pi.
"""

import http.client
import json
import os
import re
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401  (sets GTP_* paths before gps_time_pi is imported)
from gps_time_pi import admin_token, config, security, server, system

ROOT = Path(__file__).resolve().parent.parent
TOKEN = "correct-horse-battery-staple-0123456789"


class AuthBase(unittest.TestCase):
    demo = False
    with_token = True

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gps-time-auth-")
        self.token_file = os.path.join(self.tmp, "admin-token.sha256")
        if self.with_token:
            admin_token.write_token_hash(self.token_file, TOKEN)
        cfg_path = os.path.join(self.tmp, "config.json")
        Path(cfg_path).write_text(json.dumps({"location_display": "exact"}))
        self.calls = []
        patches = [
            mock.patch.dict(os.environ, {"GTP_ADMIN_TOKEN_FILE": self.token_file,
                                         "GTP_ALLOWED_HOSTS": "gpstime.example.lan",
                                         "GTP_ALLOWED_ORIGINS": "https://proxy.example.lan"}),
            mock.patch.object(server, "DEMO_MODE", self.demo),
            mock.patch.object(config, "_PATH", cfg_path),
            mock.patch.object(config, "_CACHE", None),
            mock.patch.object(system, "admin", lambda a: self.calls.append(a) or {"ok": True, "action": a, "detail": "stub"}),
            mock.patch.object(config, "reset_site", lambda: self.calls.append("reset_site")),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.host = f"127.0.0.1:{self.httpd.server_address[1]}"

    def req(self, method, path, body=None, headers=None, host=None, ctype="application/json", raw=None):
        c = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=10)
        self.addCleanup(c.close)
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        h = {"Host": host or self.host}
        if data is not None and ctype:
            h["Content-Type"] = ctype
        h.update(headers or {})
        c.request(method, path, body=data, headers=h)
        r = c.getresponse()
        payload = r.read()
        try:
            parsed = json.loads(payload)
        except ValueError:
            parsed = payload.decode(errors="replace")
        return r.status, dict(r.getheaders()), parsed

    def post(self, path, body, token=TOKEN, **kw):
        headers = dict(kw.pop("headers", {}))
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return self.req("POST", path, body, headers=headers, **kw)


class TestMethods(AuthBase):
    def test_get_on_mutation_routes_is_405_and_does_nothing(self):
        for path in ("/api/admin?action=reboot", "/api/setting?location_display=hidden", "/api/setting?reset_site=1"):
            status, headers, body = self.req("GET", path)
            self.assertEqual(status, 405, path)
            self.assertEqual(headers.get("Allow"), "POST")
            self.assertFalse(body["ok"])
        self.assertEqual(self.calls, [])
        self.assertEqual(config.load().get("location_display"), "exact")

    def test_text_plain_post_is_415(self):
        status, _, _ = self.post("/api/admin", {"action": "reboot"}, ctype="text/plain")
        self.assertEqual(status, 415)
        self.assertEqual(self.calls, [])

    def test_form_post_is_415(self):
        status, _, _ = self.post("/api/admin", None, raw=b"action=reboot", ctype="application/x-www-form-urlencoded")
        self.assertEqual(status, 415)
        self.assertEqual(self.calls, [])

    def test_bad_bodies(self):
        self.assertEqual(self.post("/api/admin", None, raw=b"{not json")[0], 400)
        self.assertEqual(self.post("/api/admin", ["reboot"])[0], 400)
        self.assertEqual(self.post("/api/admin", None, raw=b"", ctype="application/json")[0], 400)
        self.assertEqual(self.calls, [])

    def test_unknown_post_route_is_404(self):
        self.assertEqual(self.post("/api/nothing", {})[0], 404)


class TestToken(AuthBase):
    def test_missing_and_wrong_token_are_401(self):
        status, headers, body = self.post("/api/admin", {"action": "reboot"}, token=None)
        self.assertEqual(status, 401)
        self.assertIn("Bearer", headers.get("WWW-Authenticate", ""))
        self.assertEqual(self.post("/api/admin", {"action": "reboot"}, token="wrong")[0], 401)
        self.assertEqual(self.req("POST", "/api/admin", {"action": "reboot"}, headers={"Authorization": TOKEN})[0], 401)
        self.assertEqual(self.calls, [])

    def test_valid_token_runs_the_action(self):
        status, _, body = self.post("/api/admin", {"action": "restart_gpsd"})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(self.calls, ["restart_gpsd"])

    def test_settings_need_the_token(self):
        self.assertEqual(self.post("/api/setting", {"location_display": "hidden"}, token=None)[0], 401)
        self.assertEqual(config.load().get("location_display"), "exact")
        status, _, body = self.post("/api/setting", {"location_display": "hidden"})
        self.assertEqual((status, body), (200, {"ok": True, "location_display": "hidden"}))
        self.assertEqual(self.post("/api/setting", {"reset_site": "1"})[0], 400)   # must be JSON true
        self.assertEqual(self.post("/api/setting", {"reset_site": True})[2], {"ok": True, "reset_site": True})
        self.assertEqual(self.calls, ["reset_site"])

    def test_dashboard_writes_need_the_token(self):
        self.assertEqual(self.post("/api/dashboard/reset", {}, token=None)[0], 401)
        status, _, body = self.post("/api/dashboard/reset", {})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

    def test_auth_endpoint_reports_state_without_secrets(self):
        _, _, anon = self.req("GET", "/api/auth")
        self.assertEqual(anon, {"demo": False, "auth_required": True, "admin_configured": True, "authenticated": False})
        _, _, ok = self.req("GET", "/api/auth", headers={"Authorization": f"Bearer {TOKEN}"})
        self.assertTrue(ok["authenticated"])
        stored = Path(self.token_file).read_text()
        self.assertNotIn(TOKEN, stored)                      # only the hash is stored
        self.assertNotIn(stored.strip()[7:], json.dumps(ok))

    def test_dashboard_meta_reflects_auth(self):
        _, _, d = self.req("GET", "/api/dashboard")
        self.assertTrue(d["_meta"]["writable"])
        self.assertTrue(d["_meta"]["auth_required"])


class TestAdminDisabledByDefault(AuthBase):
    with_token = False

    def test_no_token_file_means_admin_disabled(self):
        status, _, body = self.post("/api/admin", {"action": "reboot"})
        self.assertEqual(status, 403)
        self.assertIn("admin is disabled", body["error"])
        self.assertEqual(self.post("/api/setting", {"location_display": "hidden"})[0], 403)
        self.assertEqual(self.calls, [])
        _, _, a = self.req("GET", "/api/auth")
        self.assertFalse(a["admin_configured"])
        _, _, d = self.req("GET", "/api/dashboard")
        self.assertFalse(d["_meta"]["writable"])

    def test_malformed_token_file_is_treated_as_absent(self):
        Path(self.token_file).write_text("not-a-hash\n")
        self.assertFalse(security.admin_configured())
        self.assertEqual(self.post("/api/admin", {"action": "reboot"})[0], 403)


class TestOriginAndHost(AuthBase):
    def test_cross_origin_post_is_403(self):
        for origin in ("http://evil.example", "null", f"http://{self.host}.evil.example", "https://127.0.0.1:1"):
            status, _, _ = self.post("/api/admin", {"action": "reboot"}, headers={"Origin": origin})
            self.assertEqual(status, 403, origin)
        self.assertEqual(self.calls, [])

    def test_same_origin_and_allowlisted_origin_pass(self):
        self.assertEqual(self.post("/api/admin", {"action": "flush_logs"}, headers={"Origin": f"http://{self.host}"})[0], 200)
        self.assertEqual(self.post("/api/admin", {"action": "flush_logs"}, headers={"Origin": "https://proxy.example.lan"})[0], 200)

    def test_rebinding_host_is_refused_for_reads_and_writes(self):
        status, _, body = self.req("GET", "/api", host="attacker.example:80")
        self.assertEqual(status, 403)
        self.assertIn("GTP_ALLOWED_HOSTS", body)
        self.assertEqual(self.req("GET", "/api/diagnostics", host="attacker.example")[0], 403)
        self.assertEqual(self.post("/api/admin", {"action": "reboot"}, host="attacker.example")[0], 403)
        self.assertEqual(self.calls, [])

    def test_allowed_hosts(self):
        for host in (self.host, "localhost:8080", "LOCALHOST", "[::1]:80", "192.0.2.5", "gpstime.example.lan", "x.localhost"):
            self.assertTrue(security.host_allowed(host), host)
        for host in ("", "attacker.example", "127.0.0.1.attacker.example", "gpstime.example.lan.evil"):
            self.assertFalse(security.host_allowed(host), host)
        self.assertEqual(self.req("GET", "/api/auth", host="gpstime.example.lan")[0], 200)


class TestDemoIsolation(AuthBase):
    demo = True
    with_token = False

    def test_demo_admin_actions_are_simulated(self):
        status, _, body = self.post("/api/admin", {"action": "reboot"}, token=None)
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True, "action": "reboot", "simulated": True, "detail": "demo mode: reboot was not executed"})
        self.assertEqual(self.post("/api/admin", {"action": "rm -rf /"}, token=None)[2]["ok"], False)
        self.assertEqual(self.calls, [])                    # system.admin never called

    def test_demo_still_enforces_method_origin_and_type(self):
        self.assertEqual(self.req("GET", "/api/admin?action=reboot")[0], 405)
        self.assertEqual(self.post("/api/admin", {"action": "reboot"}, token=None, headers={"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.post("/api/admin", {"action": "reboot"}, token=None, ctype="text/plain")[0], 415)
        self.assertEqual(self.calls, [])


class TestSystemAdmin(unittest.TestCase):
    def test_actions_are_fixed_argv_without_shell(self):
        self.assertEqual(system.ADMIN_ACTIONS, {"restart_chrony", "restart_gpsd", "flush_logs", "restart_web", "reboot"})
        runs, spawns = [], []
        with mock.patch.object(system.subprocess, "run", lambda argv, **kw: runs.append((argv, kw)) or mock.Mock(returncode=0, stdout="", stderr="")), \
             mock.patch.object(system, "_spawn", lambda argv: spawns.append(argv)), \
             mock.patch.object(system.threading, "Timer", lambda d, f, args=(): mock.Mock(start=lambda: f(*args))):
            for a in ("restart_chrony", "restart_gpsd", "flush_logs", "restart_web", "reboot"):
                self.assertTrue(system.admin(a)["ok"], a)
            self.assertFalse(system.admin("reboot; rm -rf /")["ok"])
        self.assertEqual([r[0] for r in runs], [["systemctl", "restart", "chrony.service"],
                                               ["systemctl", "restart", "gpsd.service"],
                                               ["systemctl", "start", "gps-time-pi-logflush.service"]])
        self.assertTrue(all("shell" not in kw for _, kw in runs))
        self.assertEqual(spawns, [["systemctl", "restart", "gps-time-pi.service"], ["systemctl", "reboot"]])


class TestDeploymentFiles(unittest.TestCase):
    def test_service_is_unprivileged_and_hardened(self):
        unit = (ROOT / "gps-time-pi.service").read_text()
        kv = dict(re.findall(r"^([A-Za-z]+)=(.*)$", unit, re.M))
        self.assertEqual(kv.get("User"), "gps-time")
        self.assertNotEqual(kv.get("User"), "root")
        self.assertEqual(kv.get("CapabilityBoundingSet"), "CAP_NET_BIND_SERVICE")
        self.assertEqual(kv.get("NoNewPrivileges"), "yes")
        self.assertEqual(kv.get("ProtectClock"), "yes")         # can never set the clock
        self.assertEqual(kv.get("ProtectSystem"), "strict")
        self.assertEqual(kv.get("ReadWritePaths"), "/opt/gps-time-pi")
        self.assertNotIn("PrivateDevices", kv)                 # must still see /dev/pps0

    def test_polkit_rule_allows_only_the_admin_actions(self):
        rule = (ROOT / "system" / "50-gps-time-pi.rules").read_text()
        code = re.sub(r"//.*", "", rule)
        self.assertIn('subject.user !== "gps-time"', code)
        units = set(re.findall(r'unit === "([^"]+)"', code))
        self.assertEqual(units, {"chrony.service", "gpsd.service", "gps-time-pi.service", "gps-time-pi-logflush.service"})
        self.assertEqual(set(re.findall(r'verb === "([^"]+)"', code)), {"restart", "start"})
        self.assertEqual(set(re.findall(r'action\.id === "([^"]+)"', code)),
                         {"org.freedesktop.systemd1.manage-units", "org.freedesktop.login1.reboot",
                          "org.freedesktop.login1.reboot-multiple-sessions"})

    def test_installer_creates_user_rule_and_token(self):
        sh = (ROOT / "install.sh").read_text()
        self.assertIn("useradd --system", sh)
        self.assertIn("/etc/polkit-1/rules.d/50-gps-time-pi.rules", sh)
        self.assertIn("python3 -m gps_time_pi.admin_token", sh)
        self.assertIn('chmod 1775 "$DEST"', sh)


class TestTokenFile(unittest.TestCase):
    def test_write_and_verify(self):
        d = tempfile.mkdtemp(prefix="gps-time-token-")
        path = os.path.join(d, "admin-token.sha256")
        admin_token.write_token_hash(path, "abc")
        with mock.patch.dict(os.environ, {"GTP_ADMIN_TOKEN_FILE": path}):
            self.assertTrue(security.admin_configured())
            self.assertTrue(security.verify_authorization("Bearer abc"))
            self.assertTrue(security.verify_authorization("bearer  abc "))
            self.assertFalse(security.verify_authorization("Bearer abd"))
            self.assertFalse(security.verify_authorization("Basic abc"))
            self.assertFalse(security.verify_authorization(None))
        self.assertEqual(Path(path).read_text().strip(), security.hash_token("abc"))
        if os.name == "posix":
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o640)


if __name__ == "__main__":
    unittest.main()
