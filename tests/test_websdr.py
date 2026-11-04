"""The optional web SDR (GTP_WEBSDR=1): the password gate, the usage log, the units, the installer.

No root, network, dongle or OpenWebRX+ is needed: the gate is tested against a local echo
server, the usage log with injected readers and a manual clock, the units statically, and the
script under POSIX bash with stub commands and every path under a temp root.
"""
import asyncio
import base64
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gps_time_pi import websdr, websdr_gate as gate

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = ROOT / "system"
SCRIPT = ROOT / "scripts" / "websdr.sh"
FPR = "82B2AC14962B3C75FAC97206B64EADD5CB69C981"


def unit(name):
    return (SYSTEM / name).read_text(encoding="utf-8")


def auth(user, pw):
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


class Clock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


# ── the gate ───────────────────────────────────────────────────────────────

class TestGateCredentials(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.file = self.tmp / "password"

    def write(self, user="radio", pw="correct horse battery"):
        self.file.write_text(f"# comment\n{user}:{gate.hash_password(pw, iterations=1000)}\n")

    def test_hash_round_trip_and_wrong_password(self):
        self.write()
        cred = gate.load(self.file)
        self.assertTrue(gate.check(cred, "radio", "correct horse battery"))
        self.assertFalse(gate.check(cred, "radio", "wrong"))
        self.assertFalse(gate.check(cred, "other", "correct horse battery"))
        self.assertNotIn("correct horse", self.file.read_text())

    def test_missing_or_placeholder_file_keeps_the_gate_closed(self):
        g = gate.Gate(self.file, clock=Clock())
        self.assertEqual(g.decide("192.168.1.5", auth("radio", "x"))[0], 503)
        self.file.write_text("# No password yet\n")
        self.assertIsNone(gate.load(self.file))
        self.file.write_text("radio:plain-text-password\n")
        self.assertIsNone(gate.load(self.file))

    def test_decide_asks_passes_and_backs_off(self):
        self.write()
        clock = Clock()
        g = gate.Gate(self.file, clock=clock)
        self.assertEqual(g.decide("192.168.1.5", None)[0], 401)
        self.assertEqual(g.decide("192.168.1.5", auth("radio", "correct horse battery"))[0], 200)
        with self.assertLogs("gps_time_pi.websdr_gate", "WARNING") as logs:
            for _ in range(gate.FAIL_LIMIT):
                self.assertEqual(g.decide("192.168.1.9", auth("radio", "guess"))[0], 401)
        self.assertFalse(any("guess" in m for m in logs.output))          # the password is never logged
        self.assertEqual(g.decide("192.168.1.9", auth("radio", "correct horse battery"))[0], 429)
        self.assertEqual(g.decide("192.168.1.5", auth("radio", "correct horse battery"))[0], 200)   # others unaffected
        clock.t += gate.BACKOFF_S + 1
        self.assertEqual(g.decide("192.168.1.9", auth("radio", "correct horse battery"))[0], 200)

    def test_basic_parsing(self):
        self.assertEqual(gate.basic(auth("a", "b:c")), ("a", "b:c"))
        self.assertIsNone(gate.basic("Bearer abc"))
        self.assertIsNone(gate.basic("Basic !!!"))
        self.assertIsNone(gate.basic(None))

    def test_authorization_is_stripped_before_openwebrx(self):
        lines = ["GET / HTTP/1.1", "Host: x", "Authorization: Basic abc", "authorization: Basic d"]
        self.assertEqual(gate.strip_auth(lines), ["GET / HTTP/1.1", "Host: x"])

    def test_401_asks_for_basic_credentials(self):
        a = gate.answer(401, "x").decode()
        self.assertIn("WWW-Authenticate: Basic realm=", a)
        self.assertTrue(a.startswith("HTTP/1.1 401 "))


class TestGateProxy(unittest.TestCase):
    """End to end on the loopback: the gate in front of a small upstream that records what it got."""

    def test_only_a_checked_connection_reaches_upstream(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "password").write_text(f"radio:{gate.hash_password('correct horse battery', iterations=1000)}\n")
        seen = []

        async def upstream(reader, writer):
            data = await reader.readuntil(b"\r\n\r\n")
            seen.append(data)
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
            await writer.drain()
            extra = await reader.read(5)      # bytes after the head pass through (WebSocket frames)
            writer.write(extra)
            await writer.drain()
            writer.close()

        async def request(port, headers):
            r, w = await asyncio.open_connection("127.0.0.1", port)
            w.write(("GET / HTTP/1.1\r\nHost: station\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
                     + "\r\n").encode() + b"hello")
            await w.drain()
            out = await asyncio.wait_for(r.read(), 5)
            w.close()
            return out

        async def main():
            up = await asyncio.start_server(upstream, "127.0.0.1", 0)
            g = gate.Gate(tmp / "password", ("127.0.0.1", up.sockets[0].getsockname()[1]))
            front = await asyncio.start_server(lambda r, w: gate.handle(g, r, w), "127.0.0.1", 0)
            port = front.sockets[0].getsockname()[1]
            async with up, front:
                denied = await request(port, {})
                wrong = await request(port, {"Authorization": auth("radio", "nope")})
                ok = await request(port, {"Authorization": auth("radio", "correct horse battery")})
            return denied, wrong, ok

        denied, wrong, ok = asyncio.run(main())
        self.assertTrue(denied.startswith(b"HTTP/1.1 401"))
        self.assertTrue(wrong.startswith(b"HTTP/1.1 401"))
        self.assertTrue(ok.startswith(b"HTTP/1.1 200 OK"))
        self.assertTrue(ok.endswith(b"hello"))
        self.assertEqual(len(seen), 1)                      # the refused ones never reached it
        self.assertNotIn(b"Authorization", seen[0])


# ── the usage log ──────────────────────────────────────────────────────────

class FakeHost:
    def __init__(self):
        self.active = False
        self.busy, self.total = 0, 0
        self.temp = 50.0
        self.unit_us = 0

    def cpu(self):
        return self.busy, self.total

    def step(self, busy_pct, unit_pct_of_core=0.0, dt=10.0):
        self.total += 400                      # 4 cores x 100 jiffies a second... per 10 s, simplified
        self.busy += int(400 * busy_pct / 100)
        if self.active:
            self.unit_us += int(unit_pct_of_core / 100 * dt * 1e6)


class TestUsageLog(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.clock = Clock(1_800_000_000.0)          # a whole minute
        self.mono = Clock(1000.0)
        self.host = FakeHost()
        self.log = websdr.UsageLog(path=str(self.tmp / "websdr-sessions.jsonl"), clock=self.clock,
                                   active=lambda: self.host.active, cpu=self.host.cpu, temp=lambda: self.host.temp,
                                   unit_cpu=lambda u: self.host.unit_us if u == websdr.UNIT else None,
                                   monotonic=self.mono)

    def run_minutes(self, n, busy, unit_pct=0.0, jitter_s=1e-6):
        for _ in range(n):
            for s in range(60):
                # PPS phase alternating +/- jitter: its standard deviation is about jitter_s.
                base = int(self.clock.t) * 1_000_000_000
                self.log.add_pps(base + round((jitter_s if s % 2 else -jitter_s) * 1e9))
                self.log.add_pps(base + 1000)                        # a repeat of the same second is ignored
                if s % 10 == 0:
                    self.host.step(busy, unit_pct)
                    self.log.sample()
                self.clock.t += 1
                self.mono.t += 1

    def test_a_session_has_a_before_a_during_and_one_line_on_disk(self):
        self.run_minutes(5, busy=10)
        self.host.active = True
        self.run_minutes(3, busy=40, unit_pct=120, jitter_s=3e-6)
        live = self.log.view()["session"]
        self.assertIsNotNone(live)
        self.assertEqual(live["before"]["minutes"], 5)
        self.assertFalse(live["partial"])
        self.assertFalse((self.tmp / "websdr-sessions.jsonl").exists())    # nothing written while it runs
        self.host.active = False
        self.run_minutes(1, busy=10)
        lines = (self.tmp / "websdr-sessions.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 1)
        doc = json.loads(lines[0])
        self.assertEqual(doc["format"], "gps-time.websdr-session/1")
        self.assertEqual(doc["during"]["minutes"], 3)
        self.assertAlmostEqual(doc["during"]["cpu_mean_pct"], 40, delta=1)
        self.assertAlmostEqual(doc["before"]["cpu_mean_pct"], 10, delta=1)
        self.assertAlmostEqual(doc["during"]["websdr_cpu_mean_pct"], 120, delta=2)
        # Integer ns end to end: +/-3 us alternating has a sample SD of 3000 * sqrt(60/59) ns.
        self.assertAlmostEqual(doc["during"]["pps_jitter_median_ns"], 3025.4, delta=0.2)
        self.assertAlmostEqual(doc["before"]["pps_jitter_median_ns"], 1008.4, delta=0.2)
        self.assertEqual(doc["during"]["pps_pulses"], 180)
        self.assertEqual(doc["during"]["pps_expected"], 180)
        self.assertNotIn("lat", lines[0])
        view = self.log.view()
        self.assertIsNone(view["session"])
        self.assertEqual(view["recent"][0]["during"]["pps_jitter_median_ns"]["provenance"], "calculated")
        self.assertEqual(view["recent"][0]["during"]["temp_max_c"]["provenance"], "observed")

    def test_a_session_running_when_the_service_starts_is_partial(self):
        self.host.active = True
        self.run_minutes(1, busy=30)
        self.assertTrue(self.log.view()["session"]["partial"])

    def test_missed_pulses_show(self):
        self.host.active = True
        for s in range(60):
            if s % 3:
                self.log.add_pps(int(self.clock.t) * 1_000_000_000)
            if s % 10 == 0:
                self.host.step(30)
                self.log.sample()
            self.clock.t += 1
        self.host.active = False
        self.log.sample()
        doc = json.loads((self.tmp / "websdr-sessions.jsonl").read_text())
        self.assertEqual(doc["during"]["pps_pulses"], 40)

    def test_the_file_is_capped(self):
        with mock.patch.object(websdr, "MAX_SESSIONS", 3):
            log = websdr.UsageLog(path=str(self.tmp / "s.jsonl"), clock=self.clock, active=lambda: self.host.active,
                                  cpu=self.host.cpu, temp=lambda: None, unit_cpu=lambda u: None, monotonic=self.mono)
            self.log = log
            for _ in range(5):
                self.host.active = True
                self.run_minutes(1, busy=20)
                self.host.active = False
                self.run_minutes(1, busy=5)
        self.assertEqual(len((self.tmp / "s.jsonl").read_text().splitlines()), 3)

    def test_unreadable_cgroups_mean_no_session(self):
        log = websdr.UsageLog(path=str(self.tmp / "x.jsonl"), clock=self.clock, active=lambda: None,
                              cpu=lambda: None, temp=lambda: None, unit_cpu=lambda u: None, monotonic=self.mono)
        log.sample()
        self.assertIsNone(log.view()["session"])


class TestStatus(unittest.TestCase):
    def test_settings_from_the_installer_file(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        f = tmp / "gps-time-websdr"
        f.write_text("# x\nGTP_WEBSDR_SERIAL=00001090\nGTP_WEBSDR_PORT=8073\nGTP_WEBSDR_MAX_HOURS=4\n")
        with mock.patch.object(websdr, "ENVFILE", f):
            self.assertEqual(websdr.settings(), {"port": 8073, "serial": "00001090", "max_hours": 4.0})
        with mock.patch.object(websdr, "ENVFILE", tmp / "missing"):
            self.assertEqual(websdr.settings(), {"port": None, "serial": None, "max_hours": None})

    def test_not_installed_and_unknown(self):
        usage = mock.Mock(view=lambda: {"session": None})
        out = mock.Mock(returncode=0, stdout="Id=gps-time-websdr.service\nLoadState=not-found\nActiveState=inactive\n")
        st = websdr.status(usage, run=lambda *a, **k: out)
        self.assertFalse(st["installed"])
        self.assertIsNone(st["active"]["value"])
        bad = mock.Mock(returncode=1, stdout="")
        self.assertIsNone(websdr.status(usage, run=lambda *a, **k: bad)["installed"])

    def test_demo_payload_has_the_station_shape(self):
        from gps_time_pi import demo
        d = demo.websdr_status()
        self.assertEqual(set(d), {"installed", "active", "port", "serial", "max_hours", "usage", "note"})
        self.assertEqual(set(d["usage"]), {"session", "baseline", "recent", "file", "note"})


# ── the units ──────────────────────────────────────────────────────────────

def keys(text, key):
    return re.findall(rf"^{key}=(.*)$", text, re.M)


class TestUnits(unittest.TestCase):
    def test_openwebrx_is_loopback_only_and_reaches_no_outside_host(self):
        u = unit("gps-time-websdr.service")
        self.assertEqual(keys(u, "IPAddressAllow"), ["localhost"])
        self.assertEqual(keys(u, "IPAddressDeny"), ["any"])
        conf = (SYSTEM / "openwebrx-gps-time.conf").read_text(encoding="utf-8")
        self.assertIn("bind_address = 127.0.0.1", conf)
        self.assertIn("port = 8074", conf)

    def test_gate_is_lan_only(self):
        u = unit("gps-time-websdr-gate.service")
        allow = " ".join(keys(u, "IPAddressAllow")).split()
        self.assertEqual(set(allow), {"localhost", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
                                      "169.254.0.0/16", "fc00::/7", "fe80::/10"})
        self.assertEqual(keys(u, "IPAddressDeny"), ["any"])
        self.assertIn("DynamicUser=yes", u)
        self.assertIn("BindsTo=gps-time-websdr.service", u)
        self.assertIn("LoadCredential=password:/etc/gps-time-websdr/password", u)

    def test_readsb_stops_while_it_runs_and_comes_back(self):
        u = unit("gps-time-websdr.service")
        self.assertIn("Conflicts=gps-time-readsb.service readsb.service", u)
        self.assertIn("After=network.target gps-time-readsb.service readsb.service", u)
        self.assertIn("ExecStopPost=+/usr/local/lib/gps-time-sdr/websdr-handoff", u)
        self.assertEqual(keys(u, "Restart"), ["no"])
        h = (SYSTEM / "websdr-handoff").read_text(encoding="utf-8")
        self.assertIn("systemctl --no-block start", h)
        self.assertIn("stopping) exit 0", h)

    def test_never_enabled_at_boot(self):
        for name in ("gps-time-websdr.service", "gps-time-websdr-gate.service"):
            self.assertNotIn("[Install]", unit(name), name)

    def test_nothing_touches_the_timing_core(self):
        for p in (SCRIPT, SYSTEM / "gps-time-websdr.service", SYSTEM / "gps-time-websdr-gate.service", SYSTEM / "websdr-handoff"):
            code = "\n".join(ln for ln in p.read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith("#"))
            for word in ("chrony", "gpsd", "pps-gpio", "/boot/", "config.txt"):
                self.assertNotIn(word, code, f"{p.name}: {word}")

    def test_installer_runs_it_without_failing_the_install(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn('bash scripts/websdr.sh \\\n  || echo "Warning:', text)
        self.assertLess(text.index("bash scripts/sdr-stack.sh"), text.index("bash scripts/websdr.sh"))

    def test_signing_key_is_pinned(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(f'KEY_FPR="{FPR}"', text)
        self.assertIn('[ "$GOT" = "$KEY_FPR" ]', text)


STUB = """#!/bin/bash
echo "$(basename "$0") $*" >> "$STUB_LOG"
case "$(basename "$0")" in
  dpkg) exit "${STUB_DPKG_RC:-1}" ;;
  systemctl) [ "$1" = is-enabled ] && exit "${STUB_ENABLED_RC:-1}"; exit 0 ;;
  curl) out=""; while [ $# -gt 0 ]; do [ "$1" = -o ] && out="$2"; shift; done; echo key > "$out"; exit 0 ;;
  gpg)
    if [ "$1" = --show-keys ]; then echo "pub:-:4096:1:B64EADD5CB69C981:::::"; echo "fpr:::::::::${STUB_FPR}:"; exit 0; fi
    out=""; while [ $# -gt 0 ]; do [ "$1" = -o ] && out="$2"; shift; done; echo binkey > "$out"; exit 0 ;;
  apt-get) exit "${STUB_APT_RC:-0}" ;;
esac
exit 0
"""


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "POSIX bash needed")
class TestScript(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        for cmd in ("apt-get", "systemctl", "dpkg", "modprobe", "curl", "gpg", "chown"):
            p = self.bin / cmd
            p.write_text(STUB)
            p.chmod(p.stat().st_mode | stat.S_IXUSR)
        self.root = self.tmp / "root"
        self.log = self.tmp / "calls.log"
        self.osr = self.tmp / "os-release"
        self.osr.write_text('PRETTY_NAME="Debian GNU/Linux 13 (trixie)"\nVERSION_CODENAME=trixie\n')

    def run_script(self, sdr_env=None, **env):
        if sdr_env is not None:
            p = self.root / "etc/default/gps-time-sdr"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(sdr_env)
        base = {k: v for k, v in os.environ.items() if not k.startswith("GTP_")}
        base.update(PATH=f"{self.bin}:{os.environ['PATH']}", GTP_WEBSDR_TEST_ROOT=str(self.root),
                    GTP_WEBSDR_OS_RELEASE=str(self.osr), GTP_WEBSDR_PYTHON=sys.executable,
                    STUB_LOG=str(self.log), STUB_FPR=FPR)
        base.update(env)
        return subprocess.run(["bash", str(SCRIPT)], env=base, capture_output=True, text=True, timeout=60)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_unset_changes_nothing(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("not installed", r.stdout)
        self.assertEqual(self.calls(), [])

    def test_install_uses_the_1090_dongle_and_enables_nothing(self):
        r = self.run_script("GTP_SDR_PPS_SERIAL=00000pps\nGTP_SDR_1090_SERIAL=00001090\n", GTP_WEBSDR="1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        env = (self.root / "etc/default/gps-time-websdr").read_text()
        self.assertIn("GTP_WEBSDR_SERIAL=00001090\n", env)
        self.assertIn("GTP_WEBSDR_PORT=8073\n", env)
        self.assertIn("RuntimeMaxSec=4h", (self.root / "etc/systemd/system/gps-time-websdr.service.d/gps-time-max.conf").read_text())
        settings = json.loads((self.root / "var/lib/openwebrx/settings.json").read_text())
        self.assertEqual(settings["version"], 8)
        self.assertEqual(settings["sdrs"]["rtlsdr"]["device"], "00001090")
        self.assertNotIn("receiver_gps", settings)                         # no position given
        self.assertIn("trixie ./", (self.root / "etc/apt/sources.list.d/gps-time-openwebrx-plus.list").read_text())
        pw = self.root / "etc/gps-time-websdr/password"
        self.assertTrue(pw.is_file())
        self.assertIsNone(gate.load(pw))                                    # closed until the owner sets one
        self.assertEqual(stat.S_IMODE(pw.stat().st_mode), 0o600)
        self.assertIn("no password yet", r.stdout)
        calls = self.calls()
        self.assertIn("systemctl mask openwebrx.service", calls)
        self.assertFalse([c for c in calls if c.startswith("systemctl enable") or c.startswith("systemctl start")])
        self.assertFalse([c for c in calls if "chrony" in c or "gpsd" in c])

    def test_an_existing_openwebrx_settings_file_keeps_its_profiles(self):
        data = self.root / "var/lib/openwebrx"
        data.mkdir(parents=True)
        (data / "settings.json").write_text(json.dumps({"version": 8, "receiver_name": "mine", "sdrs": {
            "a": {"type": "rtl_sdr", "device": "0", "profiles": {"x": {}}}, "b": {"type": "airspy"}}}))
        r = self.run_script(GTP_WEBSDR="1", GTP_WEBSDR_SERIAL="websdr1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = json.loads((data / "settings.json").read_text())
        self.assertEqual(doc["receiver_name"], "mine")
        self.assertEqual(doc["sdrs"]["a"]["device"], "websdr1")
        self.assertNotIn("device", doc["sdrs"]["b"])
        self.assertTrue((data / "settings.json.gps-time-prev").is_file())

    def test_refusals_change_nothing(self):
        cases = [
            ({}, None),                                                                      # no serial at all
            ({"GTP_WEBSDR_SERIAL": "a b; rm -rf /"}, None),
            ({}, "GTP_SDR_PPS_SERIAL=00000pps\nGTP_SDR_1090_SERIAL=00000pps\n"),             # the PPS dongle
            ({"GTP_WEBSDR_SERIAL": "00000978"}, "GTP_SDR_978_SERIAL=00000978\n"),
            ({"GTP_WEBSDR_SERIAL": "x1", "GTP_WEBSDR_PORT": "80"}, None),
            ({"GTP_WEBSDR_SERIAL": "x1", "GTP_WEBSDR_PORT": "8074"}, None),
            ({"GTP_WEBSDR_SERIAL": "x1", "GTP_WEBSDR_MAX_HOURS": "0"}, None),
            ({"GTP_WEBSDR_SERIAL": "x1", "STUB_FPR": "0" * 40}, None),                      # a different key
        ]
        for env, sdr_env in cases:
            with self.subTest(env=env, sdr=sdr_env):
                shutil.rmtree(self.root, True)
                self.log.unlink(missing_ok=True)
                r = self.run_script(sdr_env, GTP_WEBSDR="1", **env)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("nothing changed", r.stderr)
                self.assertFalse((self.root / "etc/systemd").exists())
                self.assertFalse([c for c in self.calls() if c.startswith("apt-get")])

    def test_an_unsupported_release_is_refused(self):
        self.osr.write_text("VERSION_CODENAME=bullseye\n")
        r = self.run_script(GTP_WEBSDR="1", GTP_WEBSDR_SERIAL="x1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("bookworm and trixie", r.stderr)

    def test_an_owners_own_openwebrx_is_left_alone(self):
        r = self.run_script(GTP_WEBSDR="1", GTP_WEBSDR_SERIAL="x1", STUB_DPKG_RC="0", STUB_ENABLED_RC="0")
        self.assertEqual(r.returncode, 1)
        self.assertIn("left as it is", r.stderr)
        self.assertNotIn("systemctl mask openwebrx.service", self.calls())

    def test_apt_failure_takes_the_repository_out_again(self):
        r = self.run_script(GTP_WEBSDR="1", GTP_WEBSDR_SERIAL="x1", STUB_APT_RC="100")
        self.assertEqual(r.returncode, 1)
        self.assertFalse((self.root / "etc/apt/sources.list.d/gps-time-openwebrx-plus.list").exists())
        self.assertFalse((self.root / "etc/systemd/system/gps-time-websdr.service").exists())

    def test_settings_are_kept_between_runs_and_off_removes_units(self):
        self.run_script(GTP_WEBSDR="1", GTP_WEBSDR_SERIAL="x1", GTP_WEBSDR_PORT="9073", GTP_WEBSDR_MAX_HOURS="2")
        r = self.run_script(GTP_WEBSDR="1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        env = (self.root / "etc/default/gps-time-websdr").read_text()
        self.assertIn("GTP_WEBSDR_SERIAL=x1\n", env)
        self.assertIn("GTP_WEBSDR_PORT=9073\n", env)
        r = self.run_script(GTP_WEBSDR="0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        units = self.root / "etc/systemd/system"
        self.assertFalse((units / "gps-time-websdr.service").exists())
        self.assertFalse((units / "gps-time-websdr-gate.service").exists())
        self.assertFalse((self.root / "etc/openwebrx/openwebrx.conf.d/gps-time.conf").exists())
        self.assertTrue((self.root / "etc/default/gps-time-websdr").exists())
        self.assertTrue((self.root / "etc/gps-time-websdr/password").exists())


if __name__ == "__main__":
    unittest.main()
