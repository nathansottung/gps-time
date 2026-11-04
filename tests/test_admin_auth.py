"""Administrative security (review GPS-014, GPS-017, GPS-019).

Over real HTTP against server.Handler: state changes are POST-only, need
application/json, a same-origin (or allowlisted) Origin, an allowed Host and,
outside demo mode, the admin token. Demo mode never runs host actions. Also
static checks of the service unit and polkit rule. No root, network or Pi.
"""

import base64
import contextlib
import http.client
import io
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
            mock.patch.object(security, "THROTTLE", security.AuthThrottle()),   # fresh per test
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

    def test_auth_endpoint_reports_state_without_secrets(self):
        _, _, anon = self.req("GET", "/api/auth")
        self.assertEqual(anon, {"demo": False, "auth_required": True, "admin_configured": True, "authenticated": False})
        _, _, ok = self.req("GET", "/api/auth", headers={"Authorization": f"Bearer {TOKEN}"})
        self.assertTrue(ok["authenticated"])
        stored = Path(self.token_file).read_text()
        self.assertNotIn(TOKEN, stored)                      # only the hash is stored
        self.assertNotIn(stored.strip()[7:], json.dumps(ok))


class TestOpenWebSdrActions(AuthBase):
    """Owner, rc.6: anyone on the LAN may start and stop the web SDR, with no token."""

    def test_start_and_stop_need_no_token(self):
        for a in ("websdr_start", "websdr_stop"):
            status, _, body = self.post("/api/admin", {"action": a}, token=None)
            self.assertEqual((status, body["ok"]), (200, True), a)
        self.assertEqual(self.calls, ["websdr_start", "websdr_stop"])

    def test_every_other_action_still_needs_the_token(self):
        for a in sorted(system.ADMIN_ACTIONS - system.OPEN_ACTIONS):
            self.assertIn(self.post("/api/admin", {"action": a}, token=None)[0], (401, 429), a)   # 429: the backoff
        self.assertIn(self.post("/api/admin", {"action": "websdr_signout_all"}, token=None)[0], (401, 429))
        self.assertIn(self.post("/api/setting", {"location_display": "hidden"}, token=None)[0], (401, 429))
        self.assertEqual(self.calls, [])
        self.assertEqual(system.OPEN_ACTIONS, {"websdr_start", "websdr_stop"})

    def test_another_site_still_cannot_start_it(self):
        status, _, _ = self.post("/api/admin", {"action": "websdr_start"}, token=None, headers={"Origin": "http://evil.example"})
        self.assertEqual(status, 403)
        self.assertEqual(self.post("/api/admin", {"action": "websdr_start"}, token=None, ctype="text/plain")[0], 415)
        self.assertEqual(self.post("/api/admin", {"action": "websdr_start"}, token=None, host="evil.example")[0], 403)
        self.assertEqual(self.calls, [])


class TestAdminDisabledByDefault(AuthBase):
    with_token = False

    def test_no_token_file_means_admin_disabled(self):
        status, _, body = self.post("/api/admin", {"action": "reboot"})
        self.assertEqual(status, 403)
        self.assertIn("admin is disabled", body["error"])
        self.assertEqual(self.post("/api/setting", {"location_display": "hidden"})[0], 403)
        self.assertEqual(self.calls, [])
        # The web SDR's Start and Stop work without any token, configured or not.
        self.assertEqual(self.post("/api/admin", {"action": "websdr_start"}, token=None)[0], 200)
        self.assertEqual(self.calls, ["websdr_start"])
        _, _, a = self.req("GET", "/api/auth")
        self.assertFalse(a["admin_configured"])

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
        self.assertEqual(system.ADMIN_ACTIONS, {"restart_chrony", "restart_gpsd", "flush_logs", "restart_web", "reboot",
                                                "websdr_start", "websdr_stop", "websdr_signout_all", "refresh_airband"})
        runs, spawns = [], []
        with mock.patch.object(system.subprocess, "run", lambda argv, **kw: runs.append((argv, kw)) or mock.Mock(returncode=0, stdout="", stderr="")), \
             mock.patch.object(system, "_spawn", lambda argv: spawns.append(argv)), \
             mock.patch.object(system.threading, "Timer", lambda d, f, args=(): mock.Mock(start=lambda: f(*args))):
            for a in ("restart_chrony", "restart_gpsd", "flush_logs", "websdr_start", "websdr_stop", "websdr_signout_all", "refresh_airband",
                      "restart_web", "reboot"):
                self.assertTrue(system.admin(a)["ok"], a)
            self.assertFalse(system.admin("reboot; rm -rf /")["ok"])
        self.assertEqual([r[0] for r in runs], [["systemctl", "restart", "chrony.service"],
                                               ["systemctl", "restart", "gpsd.service"],
                                               ["systemctl", "start", "gps-time-pi-logflush.service"],
                                               ["systemctl", "start", "gps-time-websdr.service"],
                                               ["systemctl", "stop", "gps-time-websdr.service"],
                                               ["systemctl", "start", "gps-time-websdr-signout.service"],
                                               ["systemctl", "start", "--no-block", "gps-time-airband-fetch.service"]])
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
        self.assertEqual(units, {"chrony.service", "gpsd.service", "gps-time-pi.service", "gps-time-pi-logflush.service",
                                 "gps-time-websdr.service", "gps-time-clip.service", "gps-time-airband-fetch.service",
                                 "gps-time-websdr-signout.service",
                                 "piaware.service"})
        self.assertEqual(set(re.findall(r'verb === "([^"]+)"', code)), {"restart", "start", "stop", "try-restart"})
        # stop is allowed for the web SDR and the opt-in feeders only, never for the timing core.
        self.assertRegex(code, r'\(verb === "start" \|\| verb === "stop"\) && unit === "gps-time-websdr.service"')
        self.assertIn('(verb === "start" || verb === "stop" || verb === "try-restart") &&\n'
                      '        (/^gps-time-feed@[a-z0-9]{1,32}\\.service$/.test(unit) || unit === "piaware.service")', code)
        self.assertEqual(code.count('verb === "stop"'), 2)
        self.assertEqual(code.count('verb === "try-restart"'), 1)
        self.assertEqual(code.count(".test(unit)"), 1)       # the one pattern: anchored, feeder units only
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



# ─── 1. token generation and comparison ─────────────────────────────────────

class TestTokenStrength(unittest.TestCase):
    def test_token_is_32_random_bytes_from_secrets(self):
        with mock.patch.object(admin_token.secrets, "token_urlsafe", wraps=admin_token.secrets.token_urlsafe) as gen:
            t = admin_token.new_token()
        gen.assert_called_once_with(32)
        raw = base64.urlsafe_b64decode(t + "=" * (-len(t) % 4))
        self.assertGreaterEqual(len(raw), 32)
        self.assertNotEqual(admin_token.new_token(), admin_token.new_token())

    def test_verification_uses_hmac_compare_digest(self):
        d = tempfile.mkdtemp(prefix="gps-time-token-")
        path = os.path.join(d, "admin-token.sha256")
        admin_token.write_token_hash(path, "abc")
        with mock.patch.dict(os.environ, {"GTP_ADMIN_TOKEN_FILE": path}), \
             mock.patch.object(security.hmac, "compare_digest", wraps=security.hmac.compare_digest) as cmp:
            self.assertTrue(security.verify_authorization("Bearer abc"))
            self.assertFalse(security.verify_authorization("Bearer abd"))
        self.assertEqual(cmp.call_count, 2)


# ─── 2. security headers ────────────────────────────────────────────────────

class TestSecurityHeaders(AuthBase):
    def assert_headers(self, headers, what):
        csp = headers.get("Content-Security-Policy", "")
        self.assertIn("default-src 'self'", csp, what)
        self.assertIn("frame-ancestors 'none'", csp, what)
        self.assertIn("object-src 'none'", csp, what)
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff", what)
        self.assertEqual(headers.get("Referrer-Policy"), "no-referrer", what)
        self.assertEqual(headers.get("X-Frame-Options"), "DENY", what)
        return csp

    def test_every_kind_of_response_has_the_headers(self):
        responses = {
            "api": self.req("GET", "/api/auth"),
            "app": self.req("GET", "/app/"),
            "static": self.req("GET", "/static/app.js"),
            "404": self.req("GET", "/nope"),
            "405": self.req("GET", "/api/admin"),
            "401": self.post("/api/admin", {"action": "reboot"}, token=None),
            "200 POST": self.post("/api/admin", {"action": "flush_logs"}),
            "host refused": self.req("GET", "/api", host="attacker.example"),
            "time": self.req("GET", "/time"),
        }
        for what, (_, headers, _) in responses.items():
            csp = self.assert_headers(headers, what)
            self.assertIn("script-src 'self'", csp, what)
            self.assertNotIn("unsafe-inline", csp, what)          # strict outside the legacy pages

    def test_one_strict_csp_everywhere_no_inline_exceptions(self):
        # The legacy pages and their style-src 'unsafe-inline' exception are gone.
        for path in ("/", "/legacy", "/zones", "/api", "/time", "/nope"):
            status, headers, _ = self.req("GET", path)
            csp = self.assert_headers(headers, f"{path} ({status})")
            self.assertEqual(csp, security.CSP_STRICT, path)
            self.assertNotIn("unsafe-inline", csp, path)
            self.assertNotIn("sha256-", csp, path)


# ─── 3. failed-token logging and backoff ────────────────────────────────────

class TestThrottle(unittest.TestCase):
    def test_backoff_grows_and_resets(self):
        now = [1000.0]
        t = security.AuthThrottle(clock=lambda: now[0])
        for _ in range(security.FREE_FAILURES):
            self.assertEqual(t.failure("10.0.0.1")[1], 0.0)
        self.assertEqual(t.retry_after("10.0.0.1"), 0.0)
        self.assertEqual(t.failure("10.0.0.1"), (4, 2.0))
        self.assertEqual(t.retry_after("10.0.0.1"), 2.0)
        self.assertEqual(t.retry_after("10.0.0.2"), 0.0)           # per IP
        self.assertEqual(t.failure("10.0.0.1")[1], 4.0)
        now[0] += 4.0
        self.assertEqual(t.retry_after("10.0.0.1"), 0.0)
        t.success("10.0.0.1")
        self.assertEqual(t.failure("10.0.0.1"), (1, 0.0))

    def test_backoff_is_capped_and_memory_bounded(self):
        t = security.AuthThrottle(clock=lambda: 0.0)
        for _ in range(40):
            _, backoff = t.failure("10.0.0.1")
        self.assertEqual(backoff, security.MAX_BACKOFF_S)
        with mock.patch.object(security, "MAX_TRACKED_IPS", 10):
            for i in range(50):
                t.failure(f"192.0.2.{i}")
        self.assertLessEqual(len(t._ips), 10)


class TestFailedAttemptLogging(AuthBase):
    SECRET_GUESS = "guess-DO-NOT-LOG-7f3a"

    def test_failures_are_logged_without_the_token(self):
        with self.assertLogs("gps_time_pi.security", "WARNING") as cm:
            self.post("/api/admin", {"action": "reboot"}, token=self.SECRET_GUESS)
            self.post("/api/admin", {"action": "reboot"}, token=None)
            self.req("POST", "/api/admin", {"action": "reboot"}, headers={"Authorization": "Basic " + self.SECRET_GUESS})
        text = "\n".join(cm.output)
        self.assertNotIn(self.SECRET_GUESS, text)
        self.assertNotIn(TOKEN, text)
        self.assertIn("ip=127.0.0.1", text)
        self.assertIn("route=/api/admin", text)
        for reason in ("reason=invalid", "reason=missing", "reason=malformed"):
            self.assertIn(reason, text)

    def test_backoff_returns_429_even_for_the_right_token(self):
        for _ in range(security.FREE_FAILURES + 1):
            self.assertEqual(self.post("/api/admin", {"action": "reboot"}, token="wrong")[0], 401)
        status, headers, body = self.post("/api/admin", {"action": "flush_logs"})
        self.assertEqual(status, 429)
        self.assertGreaterEqual(int(headers["Retry-After"]), 1)
        self.assertEqual(self.calls, [])
        security.THROTTLE.success("127.0.0.1")                      # backoff over
        self.assertEqual(self.post("/api/admin", {"action": "flush_logs"})[0], 200)

    def test_api_auth_guesses_count_too(self):
        for _ in range(security.FREE_FAILURES + 1):
            status, _, _ = self.req("GET", "/api/auth", headers={"Authorization": "Bearer wrong"})
            self.assertEqual(status, 401)
        self.assertEqual(self.req("GET", "/api/auth", headers={"Authorization": f"Bearer {TOKEN}"})[0], 429)
        self.assertEqual(self.req("GET", "/api/auth")[0], 200)     # without a token: no check, no penalty


# ─── 4. installer shows the token on the terminal only ──────────────────────

class TestTokenOnTerminalOnly(unittest.TestCase):
    def run_tool(self, argv, tty_path):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = admin_token.main(argv, tty_path=tty_path)
        return rc, out.getvalue(), err.getvalue()

    def test_tty_only_writes_token_to_terminal_not_stdout(self):
        d = tempfile.mkdtemp(prefix="gps-time-tty-")
        tty, path = os.path.join(d, "tty"), os.path.join(d, "admin-token.sha256")
        rc, out, err = self.run_tool(["--tty-only", "--path", path], tty)
        self.assertEqual(rc, 0)
        shown = Path(tty).read_text()
        token = re.search(r"^ {4}(\S+)$", shown, re.M).group(1)
        self.assertNotIn(token, out + err)
        self.assertEqual(Path(path).read_text().strip(), security.hash_token(token))

    def test_no_terminal_creates_nothing(self):
        d = tempfile.mkdtemp(prefix="gps-time-tty-")
        path = os.path.join(d, "admin-token.sha256")
        rc, out, err = self.run_tool(["--tty-only", "--path", path], os.path.join(d, "no", "such", "tty"))
        self.assertEqual(rc, 2)
        self.assertFalse(os.path.exists(path))
        self.assertIn("NOT created", err)

    def test_installer_and_deploy_scripts_use_the_terminal(self):
        self.assertIn("admin_token --tty-only", (ROOT / "install.sh").read_text())
        sh = (ROOT / "scripts" / "deploy-to-pi.sh").read_text(encoding="utf-8")
        self.assertIn("if [ -t 0 ] && [ -t 1 ]; then TTY_OPT=(-t); fi", sh)
        self.assertIn('ssh ${TTY_OPT[@]+"${TTY_OPT[@]}"} "$REMOTE"', sh)
        self.assertIn("IsOutputRedirected", (ROOT / "scripts" / "deploy-to-pi.ps1").read_text())


# ─── 5. rollback drop-in stays in sync with the unit ────────────────────────

class TestRollbackDropIn(unittest.TestCase):
    NOT_PRIVILEGE = {"WorkingDirectory", "Environment", "ExecStart", "Restart"}

    def test_rollback_resets_every_privilege_and_hardening_setting(self):
        unit = (ROOT / "gps-time-pi.service").read_text()
        service = unit.split("[Service]", 1)[1].split("[Install]", 1)[0]
        keys = set(re.findall(r"^([A-Za-z]+)=", service, re.M)) - self.NOT_PRIVILEGE
        rollback = (ROOT / "system" / "gps-time-pi-root-rollback.conf").read_text()
        reset = dict(re.findall(r"^([A-Za-z]+)=(.*)$", rollback, re.M))
        self.assertEqual(keys - set(reset), set(), "settings the rollback does not reset")
        self.assertEqual(reset["User"], "")                      # empty = root
        self.assertIn('"$DEST/rollback/gps-time-pi-root-rollback.conf"', (ROOT / "install.sh").read_text())

if __name__ == "__main__":
    unittest.main()
