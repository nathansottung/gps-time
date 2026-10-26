"""Module isolation: every module in its own process, with permissions and caps enforced.

The process tests need POSIX (resource limits, /proc); CI runs them on Linux.
The guard's rules are also tested directly, which runs everywhere. No root,
hardware or network needed: nothing here connects anywhere.
"""

import os
import re
import shutil
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi.modkit import loader, sandbox
from gps_time_pi.modkit.context import CappedStorage, StorageFull

ROOT = Path(__file__).resolve().parents[1]

MANIFEST = """
name = "{name}"
version = "0.1.0"
types = ["source"]
maturity = "experimental"
interface = "1.0"
summary = "isolation test"

[entry]
source = "{pkg}.src:S"

[hardware]
required = "none"

[timing]
needed = "s"
if_worse = "nothing"

[limits]
memory_mib = {memory}
cpu_percent = {cpu}

[permissions]
network = {network}
devices = {devices}
storage = "{storage}"

[licence]
code = "MIT"
"""

HEADER = """
import os, sys, time
from gps_time_pi.labels import q
from gps_time_pi.modkit import Observation, Source

def ok(ctx, note):
    ctx.emit(Observation(time_ns=ctx.now_ns(), source=ctx.name, values={{"ok": q(note, None, "observed")}}, timing={{}}))

class S(Source):
    def __init__(self):
        self.stopped = False
    def stop(self):
        self.stopped = True
    def start(self, ctx):
{body}
"""


class Isolation(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def make(self, name, body, memory=192, cpu=50, network="false", devices="[]", storage="none"):
        pkg = name.replace("-", "_")
        d = self.root / name
        (d / pkg).mkdir(parents=True)
        (d / pkg / "__init__.py").write_text("", encoding="utf-8")
        (d / pkg / "src.py").write_text(HEADER.format(body=textwrap.indent(textwrap.dedent(body), " " * 8)),
                                        encoding="utf-8")
        (d / "module.toml").write_text(MANIFEST.format(name=name, pkg=pkg, memory=memory, cpu=cpu, network=network,
                                                       devices=devices, storage=storage), encoding="utf-8")

    def run_host(self, names, timeout=60, **kw):
        out = []
        h = loader.ModuleHost(self.root, names, emit=lambda n, item: out.append((n, item)),
                              allow_unenforced=os.name == "nt", **kw)
        h.load()
        h.start(wait=True, timeout=timeout)
        h.stop()
        return {s["name"]: s for s in h.status()}, out


@unittest.skipUnless(sandbox.available(), "POSIX sandbox (resource limits, /proc) needed")
class TestProcessIsolation(Isolation):
    def test_each_module_has_its_own_process(self):
        self.make("one", "ok(ctx, str(os.getpid()))")
        self.make("two", "ok(ctx, str(os.getpid()))")
        st, out = self.run_host(["one", "two"])
        pids = {item["values"]["ok"]["value"] for _, item in out}
        self.assertEqual(len(pids), 2)
        self.assertNotIn(str(os.getpid()), pids)
        self.assertTrue(all(s["enforced"] for s in st.values()))

    def test_memory_cap(self):
        self.make("hungry", "x = bytearray(600 * 1024 * 1024)\nok(ctx, 'allocated')", memory=96)
        st, out = self.run_host(["hungry"])
        self.assertIn(st["hungry"]["state"], ("failed", "killed"), st["hungry"])
        self.assertEqual(out, [])

    def test_cpu_share_cap(self):
        self.make("spinner", "t = time.monotonic()\nwhile time.monotonic() - t < 30 and not self.stopped:\n    pass",
                  cpu=10)
        t0 = time.monotonic()
        st, _ = self.run_host(["spinner"], cpu_window_s=1.5)
        self.assertEqual(st["spinner"]["state"], "killed", st["spinner"])
        self.assertIn("CPU share", st["spinner"]["reason"])
        self.assertLess(time.monotonic() - t0, 20)

    def test_network_needs_permission(self):
        body = "import socket\ntry:\n    socket.socket()\n    ok(ctx, 'socket')\nexcept PermissionError as e:\n    ok(ctx, 'denied: ' + str(e))"
        self.make("no-net", body)
        self.make("with-net", body, network="true")
        _, out = self.run_host(["no-net", "with-net"])
        got = {n: item["values"]["ok"]["value"] for n, item in out}
        self.assertIn("no network permission", got["no-net"])
        self.assertEqual(got["with-net"], "socket")

    def test_devices_need_permission(self):
        body = "try:\n    open('/dev/full', 'rb').close()\n    ok(ctx, 'opened')\nexcept PermissionError as e:\n    ok(ctx, 'denied')"
        self.make("no-dev", body)
        self.make("with-dev", body, devices='["/dev/full"]')
        _, out = self.run_host(["no-dev", "with-dev"])
        got = {n: item["values"]["ok"]["value"] for n, item in out}
        self.assertEqual(got, {"no-dev": "denied", "with-dev": "opened"})

    def test_writes_only_in_its_storage(self):
        outside = self.root / "outside.txt"
        body = f"""
        ctx.storage.write("inside.txt", b"fine")
        try:
            open({str(outside)!r}, "w").write("no")
            ok(ctx, "wrote outside")
        except PermissionError:
            ok(ctx, "denied")
        """
        self.make("writer", body, storage="disk:1MiB")
        st, out = self.run_host(["writer"], storage_roots={"disk": str(self.root / "store")})
        self.assertEqual(out[0][1]["values"]["ok"]["value"], "denied", st)
        self.assertFalse(outside.exists())
        self.assertTrue((self.root / "store" / "writer" / "inside.txt").is_file())

    def test_disk_cap(self):
        self.make("filler", 'ctx.storage.write("big", b"x" * (2 * 1024 * 1024))', storage="disk:1MiB")
        st, _ = self.run_host(["filler"], storage_roots={"disk": str(self.root / "store")})
        self.assertEqual(st["filler"]["state"], "failed")
        self.assertIn("StorageFull", st["filler"]["reason"])

    def test_file_size_limit_is_an_os_limit(self):
        # straight to a file in its own storage, around ctx.storage: the OS limit still holds
        body = 'p = os.path.join(os.environ["HOME"], "raw")\nwith open(p, "wb") as f:\n    f.write(b"x" * (3 * 1024 * 1024))\nok(ctx, "wrote")'
        self.make("raw-writer", body, storage="disk:1MiB")
        st, out = self.run_host(["raw-writer"], storage_roots={"disk": str(self.root / "store")})
        self.assertIn(st["raw-writer"]["state"], ("failed", "killed"), st["raw-writer"])
        self.assertEqual(out, [])

    def test_no_processes_no_ctypes_no_denied_reads(self):
        secret = self.root / "secret.json"
        secret.write_text("{}", encoding="utf-8")
        body = f"""
        import subprocess
        results = []
        for name, f in (("spawn", lambda: subprocess.run(["true"])),
                        ("ctypes", lambda: __import__("ctypes").CDLL(None)),
                        ("secret", lambda: open({str(secret)!r}).read()),
                        ("kill", lambda: os.kill(os.getppid(), 0))):
            try:
                f()
                results.append(name + ":allowed")
            except PermissionError:
                results.append(name + ":denied")
        ok(ctx, ",".join(results))
        """
        self.make("escaper", body)
        _, out = self.run_host(["escaper"], deny_read=[str(secret)])
        self.assertEqual(out[0][1]["values"]["ok"]["value"], "spawn:denied,ctypes:denied,secret:denied,kill:denied")

    def test_output_flood_is_killed(self):
        self.make("flood", "while not self.stopped:\n    ok(ctx, 'x')")
        st, _ = self.run_host(["flood"], max_emits_per_s=5)
        self.assertEqual(st["flood"]["state"], "killed")
        self.assertIn("items per second", st["flood"]["reason"])

    def test_crash_does_not_reach_the_host_or_other_modules(self):
        self.make("crash", "os._exit(9)")
        self.make("calm", "ok(ctx, 'still here')")
        st, out = self.run_host(["crash", "calm"])
        self.assertEqual(st["crash"]["state"], "failed")
        self.assertIn("exit code 9", st["crash"]["reason"])
        self.assertEqual(st["calm"]["state"], "finished")

    def test_stop(self):
        self.make("sleeper", "while not self.stopped:\n    time.sleep(0.05)\nok(ctx, 'stopped cleanly')")
        out = []
        h = loader.ModuleHost(self.root, ["sleeper"], emit=lambda n, i: out.append(i))
        h.load()
        h.start()
        time.sleep(1.0)
        st = {s["name"]: s for s in h.stop()}
        self.assertIn(st["sleeper"]["state"], ("finished", "stopped"))
        self.assertEqual(out[0]["values"]["ok"]["value"], "stopped cleanly")

    def test_site_comes_only_from_the_host(self):
        self.make("where", "s = ctx.site()\nok(ctx, 'none' if s is None else str(s['lat']))")
        _, out = self.run_host(["where"], site=lambda: {"lat": 38.9, "lon": -77.1, "privacy": "rounded"})
        self.assertEqual(out[0][1]["values"]["ok"]["value"], "38.9")

    def test_root_without_a_module_user_is_refused(self):
        self.make("rooty", "ok(ctx, 'ran')")
        with mock.patch.object(loader.os, "geteuid", return_value=0):
            st, out = self.run_host(["rooty"])
        self.assertEqual(st["rooty"]["state"], "refused")
        self.assertIn("no module user", st["rooty"]["reason"])


class TestPlatform(Isolation):
    def test_refused_where_the_sandbox_is_missing(self):
        self.make("plain", "ok(ctx, 'ran')")
        with mock.patch.object(sandbox, "available", return_value=False):
            h = loader.ModuleHost(self.root, ["plain"])
            h.load()
            st = {s["name"]: s for s in h.start(wait=True)}
        self.assertEqual(st["plain"]["state"], "refused")
        self.assertIn("sandbox isn't available", st["plain"]["reason"])

    def test_drop_privileges_refuses_root_without_a_user(self):
        if os.name != "posix":
            self.skipTest("POSIX")
        with mock.patch.object(sandbox.os, "geteuid", return_value=0):
            with self.assertRaises(sandbox.SandboxError):
                sandbox.drop_privileges(None)

    def test_limits_are_capped_by_the_host(self):
        m = mock.Mock(data={"limits": {"memory_mib": 4096, "cpu_percent": 90}})
        self.assertEqual(loader.effective_limits(m), {"memory_mib": 512, "cpu_percent": 50.0})
        self.assertEqual(loader.effective_limits(mock.Mock(data={})), loader.DEFAULT_LIMITS)


class TestGuardRules(unittest.TestCase):
    """The audit hook's decisions, called directly (no hook is installed in this process)."""

    def setUp(self):
        self.store = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.store, ignore_errors=True)
        self.secret = self.store.parent / "gtp-test-secret.json"

    def guard(self, **perm):
        return sandbox.make_guard(dict({"network": False, "devices": []}, **perm), [str(self.store)], [str(self.secret)])

    def test_writes(self):
        g = self.guard()
        g("open", (str(self.store / "a.txt"), "w", 0))
        g("open", (str(Path(__file__)), "r", 0))
        with self.assertRaises(PermissionError):
            g("open", (str(self.store.parent / "b.txt"), "w", 0))
        with self.assertRaises(PermissionError):
            g("open", (str(self.store.parent / "b.txt"), None, os.O_WRONLY | os.O_CREAT))
        with self.assertRaises(PermissionError):
            g("os.remove", (str(Path(__file__)), None))
        with self.assertRaises(PermissionError):
            g("os.rename", (str(self.store / "a"), str(self.store.parent / "a")))

    def test_denied_reads(self):
        with self.assertRaises(PermissionError):
            self.guard()("open", (str(self.secret), "r", 0))

    def test_network_processes_ctypes(self):
        g = self.guard()
        for ev in ("socket.__new__", "socket.connect", "subprocess.Popen", "os.system", "os.fork",
                   "ctypes.dlopen", "os.kill"):
            with self.assertRaises(PermissionError, msg=ev):
                g(ev, (None, None))
        self.guard(network=True)("socket.__new__", (None, 2, 1, 0))

    @unittest.skipUnless(os.name == "posix", "device paths")
    def test_devices(self):
        g = self.guard()
        g("open", ("/dev/urandom", "rb", 0))
        with self.assertRaises(PermissionError):
            g("open", ("/dev/ttyAMA0", "rb", 0))
        self.guard(devices=["/dev/ttyAMA0"])("open", ("/dev/ttyAMA0", "rb", 0))


class TestStorageRate(unittest.TestCase):
    def test_write_rate_cap(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        now = [0.0]
        s = CappedStorage(d, 10_000, rate_bytes_per_hour=100, clock=lambda: now[0])
        s.write("a", b"x" * 60)
        with self.assertRaises(StorageFull):
            s.write("b", b"x" * 60)
        now[0] = 3601
        s.write("b", b"x" * 60)


class TestStationService(unittest.TestCase):
    unit = (ROOT / "system" / "gps-time-modules.service").read_text(encoding="utf-8")
    install = (ROOT / "install.sh").read_text(encoding="utf-8")

    def settings(self):
        out = {}
        for line in self.unit.splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out.setdefault(k, []).append(v)
        return out

    def test_unit_hardening(self):
        s = self.settings()
        for k, v in {"NoNewPrivileges": "yes", "ProtectSystem": "strict", "PrivateDevices": "yes",
                     "IPAddressDeny": "any", "ProtectClock": "yes", "RestrictNamespaces": "yes"}.items():
            self.assertEqual(s.get(k), [v], k)
        self.assertEqual(s["CapabilityBoundingSet"], ["CAP_SETUID CAP_SETGID CAP_CHOWN CAP_DAC_READ_SEARCH"])
        self.assertEqual(s["Environment"][-1], "GTP_MODULE_USER=gps-time-mod")
        for k in ("MemoryMax", "CPUQuota", "TasksMax"):
            self.assertIn(k, s)

    def test_installed_but_not_enabled(self):
        self.assertIn("useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin gps-time-mod",
                      self.install)
        self.assertIn("install -m 0644 system/gps-time-modules.service /etc/systemd/system/gps-time-modules.service",
                      self.install)
        code = "\n".join(l for l in self.install.splitlines() if not l.lstrip().startswith("#"))
        self.assertNotRegex(code, r"systemctl (enable|start|restart)[^\n]*gps-time-modules")

    def test_web_service_still_never_loads_modules(self):
        # The web service may read manifests (modkit.settings) for the Administration
        # switch, but never runs a host or imports module code.
        src = (ROOT / "gps_time_pi" / "server.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^from \.modkit.*$", src, re.M), ["from .modkit import settings as modsettings"])
        self.assertNotRegex(src, r"ModuleHost|modkit\.(loader|runner|sandbox|supervisor)")
        settings_src = (ROOT / "gps_time_pi" / "modkit" / "settings.py").read_text(encoding="utf-8")
        self.assertNotRegex(settings_src, r"ModuleHost|import (runner|sandbox|supervisor)|subprocess")


if __name__ == "__main__":
    unittest.main()
