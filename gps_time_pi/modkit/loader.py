"""Find, check and run modules, each in its own sandboxed process.

- Discovery: every folder with a module.toml under the modules directory
  (GTP_MODULES_DIR, default modules/ next to gps_time_pi).
- Off by default: only modules named in "modules_enabled" run. The web
  service never loads modules; on a station they run only under
  gps-time-modules.service (supervisor.py), which is installed but not enabled.
- The host never imports a module's code. Each module runs in its own process
  (runner.py), which drops to the module user, applies resource limits and the
  permission guard, and only then imports the module (sandbox.py).
- Caps watched here, per module: CPU share over a sliding window, resident
  memory, output line size and rate. A module over a cap is killed, with the
  reason. Memory and file size are also OS limits in the module's process, and
  storage has a size cap and a write-rate cap.
- Refused, with the reason: an invalid manifest, an interface this station
  can't run, storage the host doesn't give, or a platform where the sandbox
  isn't available (unless allow_unenforced, for the desktop demo only).
- Everything a module emits is checked against schemas/; invalid items are
  dropped and counted. A module that fails or is killed never affects the host.
"""

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import manifest as mf
from . import sandbox, schema

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = Path(os.environ.get("GTP_MODULES_DIR") or ROOT / "modules")
RAM_CAP_BYTES = 16 * 1024 * 1024
DISK_RATE_BYTES_PER_HOUR = 4 * 1024 * 1024
DEFAULT_LIMITS = {"memory_mib": 256, "cpu_percent": 25.0}
MAX_LIMITS = {"memory_mib": 512, "cpu_percent": 50.0}
MAX_LINE_BYTES = 1024 * 1024
STDERR_LINES = 50


def enabled_from_config(cfg):
    """Module names the owner enabled; none by default."""
    names = cfg.get("modules_enabled", []) if isinstance(cfg, dict) else []
    return [n for n in names if isinstance(n, str)]


def discover(root=None):
    """[(folder, Manifest or None, errors)] for every folder with a module.toml."""
    root = Path(root or DEFAULT_DIR)
    if not root.is_dir():
        return []
    out = []
    for d in sorted(p for p in root.iterdir() if (p / "module.toml").is_file()):
        m, errs = mf.read(d)
        out.append((d, m, errs))
    return out


def effective_limits(manifest, max_limits=None):
    """The module's requested limits (or the defaults), capped by the host's maximum."""
    mx = dict(MAX_LIMITS, **(max_limits or {}))
    req = manifest.data.get("limits", {}) if manifest else {}
    return {k: min(req.get(k, DEFAULT_LIMITS[k]), mx[k]) for k in DEFAULT_LIMITS}


def _proc_cpu_s(pid):
    with open(f"/proc/{pid}/stat", encoding="ascii") as f:
        fields = f.read().rsplit(")", 1)[1].split()
    return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")


def _proc_rss_bytes(pid):
    with open(f"/proc/{pid}/status", encoding="ascii") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    return 0


@dataclass
class LoadedModule:
    name: str
    folder: Path
    manifest: object = None
    state: str = "disabled"        # disabled | refused | loaded | starting | running | finished | stopped | failed | killed
    reason: str = ""
    emitted: int = 0
    rejected: int = 0
    proc: object = None
    user: str = None
    limits: dict = field(default_factory=dict)
    enforced: bool = False
    stderr: list = field(default_factory=list)
    threads: list = field(default_factory=list)
    lock: object = field(default_factory=threading.Lock)

    def status(self):
        m = self.manifest
        return {"name": self.name, "state": self.state, "reason": self.reason,
                "version": m.version if m else None, "maturity": m.maturity if m else None,
                "types": list(m.types) if m else [], "permissions": m.permissions if m else None,
                "limits": self.limits, "enforced": self.enforced, "user": self.user,
                "pid": self.proc.pid if self.proc else None,
                "emitted": self.emitted, "rejected": self.rejected, "stderr_tail": self.stderr[-5:]}


class ModuleHost:
    def __init__(self, root=None, enabled=(), *, emit=None, timing_quality=None, site=None,
                 configs=None, storage_roots=None, user=None, deny_read=(), allow_unenforced=False,
                 max_limits=None, cpu_window_s=60.0, max_emits_per_s=50.0, context_interval_s=10.0,
                 python=None):
        """emit(name, item_dict): every valid Observation/Result.
        timing_quality(), site(): pushed to modules at start and every context_interval_s
        (site must already be privacy-filtered).
        storage_roots: {"ram": folder, "disk": folder}.
        user: the unprivileged user modules run as when the host is root (required then).
        deny_read: paths modules may never open (config, keys, tokens).
        allow_unenforced: run where the sandbox isn't available (desktop demo only)."""
        self.root = Path(root or DEFAULT_DIR)
        self.enabled = set(enabled)
        self._emit = emit or (lambda name, item: None)
        self._timing = timing_quality
        self._site = site
        self.configs = configs or {}
        self.storage_roots = storage_roots or {}
        self.user = user
        self.deny_read = list(deny_read)
        self.allow_unenforced = allow_unenforced
        self.max_limits = max_limits
        self.cpu_window_s = cpu_window_s
        self.max_emits_per_s = max_emits_per_s
        self.context_interval_s = context_interval_s
        self.python = python or sys.executable
        self.modules = {}
        self._schemas = {"observation/1": schema.load("observation.v1"), "result/1": schema.load("result.v1")}

    # ---------------------------------------------------------------- loading

    def load(self):
        """Check manifests and the enabled list. No module code is imported here."""
        for folder, m, errs in discover(self.root):
            lm = LoadedModule(folder.name, folder, m)
            self.modules[folder.name] = lm
            if errs:
                lm.state, lm.reason = "refused", "; ".join(errs)
            elif m.name in self.enabled:
                lm.state = "loaded"
                lm.limits = effective_limits(m, self.max_limits)
        for name in self.enabled - set(self.modules):
            self.modules[name] = LoadedModule(name, self.root / name, None, "refused", "enabled but not found")
        return self.status()

    # ---------------------------------------------------------------- running

    def _storage(self, lm):
        kind = lm.manifest.permissions["storage"]
        if kind == "none":
            return None
        if kind == "ram":
            root, cap, rate = self.storage_roots.get("ram"), RAM_CAP_BYTES, None
        else:
            root, cap, rate = self.storage_roots.get("disk"), int(kind[5:-3]) * 1024 * 1024, DISK_RATE_BYTES_PER_HOUR
        if not root:
            raise PermissionError(f"storage {kind} requested but the host gives none")
        d = Path(root) / lm.name
        d.mkdir(parents=True, exist_ok=True)
        if os.name == "posix" and os.geteuid() == 0 and self.user:
            import pwd
            pw = pwd.getpwnam(self.user)
            os.chown(d, pw.pw_uid, pw.pw_gid)
            os.chmod(d, 0o700)
        return {"dir": str(d), "cap_bytes": cap, "rate_bytes_per_hour": rate}

    def _env(self, lm, storage):
        if os.name == "nt":
            env = dict(os.environ)
        else:
            env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": storage["dir"] if storage else "/nonexistent",
                   # glibc reserves 64 MiB of address space per thread arena; keep the memory cap meaningful
                   "MALLOC_ARENA_MAX": "2"}
        env["PYTHONPATH"] = str(ROOT)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def _send(self, lm, msg):
        try:
            with lm.lock:
                lm.proc.stdin.write(json.dumps(msg) + "\n")
                lm.proc.stdin.flush()
        except (OSError, ValueError):
            pass

    def _kill(self, lm, reason):
        if lm.state in ("running", "starting"):
            lm.state, lm.reason = "killed", reason
        try:
            lm.proc.kill()
        except OSError:
            pass

    def _read_stdout(self, lm):
        window = []
        for raw in lm.proc.stdout:
            if len(raw) > MAX_LINE_BYTES:
                self._kill(lm, "output line too long")
                break
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            kind = msg.get("type")
            if kind == "ready":
                lm.state, lm.user = "running", msg.get("user")
            elif kind == "emit":
                now = time.monotonic()
                window = [t for t in window if now - t < 10] + [now]
                if len(window) > self.max_emits_per_s * 10:
                    self._kill(lm, f"more than {self.max_emits_per_s:g} items per second")
                    break
                d = msg.get("item")
                sch = self._schemas.get(d.get("schema")) if isinstance(d, dict) else None
                if sch is None or schema.validate(d, sch):
                    lm.rejected += 1
                    continue
                lm.emitted += 1
                self._emit(lm.name, d)
            elif kind == "error":
                if lm.state in ("starting", "running"):
                    lm.state, lm.reason = "failed", msg.get("error", "")
            elif kind == "exit":
                if lm.state == "running":
                    lm.state = "finished"

    def _read_stderr(self, lm):
        for line in lm.proc.stderr:
            lm.stderr.append(line.rstrip()[:500])
            del lm.stderr[:-STDERR_LINES]

    def _monitor(self, lm):
        samples = []
        last_ctx = time.monotonic()
        mem_cap = lm.limits["memory_mib"] * 1024 * 1024
        while lm.proc.poll() is None:
            time.sleep(0.25)
            now = time.monotonic()
            if lm.enforced:
                try:
                    cpu, rss = _proc_cpu_s(lm.proc.pid), _proc_rss_bytes(lm.proc.pid)
                except (OSError, ValueError, IndexError):
                    continue
                samples = [(t, c) for t, c in samples if now - t <= self.cpu_window_s] + [(now, cpu)]
                span = samples[-1][0] - samples[0][0]
                if span >= 0.8 * self.cpu_window_s:
                    share = 100 * (samples[-1][1] - samples[0][1]) / span
                    if share > lm.limits["cpu_percent"]:
                        self._kill(lm, f"CPU share {share:.0f} % over its cap of {lm.limits['cpu_percent']:g} %")
                        break
                if rss > mem_cap:
                    self._kill(lm, f"resident memory over its cap of {lm.limits['memory_mib']} MiB")
                    break
            if now - last_ctx >= self.context_interval_s and (self._timing or self._site):
                last_ctx = now
                self._send(lm, {"type": "context", "timing": self._timing() if self._timing else None,
                                "site": self._site() if self._site else None})
        rc = lm.proc.wait()
        for t in lm.threads[:2]:
            t.join(5)
        if lm.state in ("running", "starting"):
            lm.state = "failed"
            lm.reason = lm.reason or (f"exit code {rc}" if rc >= 0 else f"ended by signal {-rc}")

    def _spawn(self, lm):
        m = lm.manifest
        storage = self._storage(lm)
        lm.enforced = sandbox.available()
        spec = {
            "name": m.name, "module_dir": str(lm.folder), "kind": "source", "entry": m.entry["source"],
            "config": self.configs.get(m.name, {}), "permissions": m.permissions, "storage": storage,
            "user": self.user, "deny_read": self.deny_read, "enforce": lm.enforced,
            "limits": {"memory_bytes": lm.limits["memory_mib"] * 1024 * 1024,
                       "file_size_bytes": storage["cap_bytes"] if storage else 0, "open_files": 64},
            "timing": self._timing() if self._timing else None,
            "site": self._site() if self._site else None,
        }
        lm.proc = subprocess.Popen([self.python, "-s", "-m", "gps_time_pi.modkit.runner"], cwd=str(ROOT),
                                   env=self._env(lm, storage), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
        lm.state = "starting"
        self._send(lm, spec)
        lm.threads = [threading.Thread(target=f, args=(lm,), daemon=True, name=f"module-{lm.name}-{f.__name__}")
                      for f in (self._read_stdout, self._read_stderr, self._monitor)]
        for t in lm.threads:
            t.start()

    def start(self, wait=False, timeout=None):
        for lm in self.modules.values():
            if lm.state != "loaded":
                continue
            if "source" not in lm.manifest.entry:
                continue
            if not sandbox.available() and not self.allow_unenforced:
                lm.state, lm.reason = "refused", "the module sandbox isn't available on this platform"
                continue
            if os.name == "posix" and os.geteuid() == 0 and not self.user:
                lm.state, lm.reason = "refused", "the host is root and no module user is set"
                continue
            try:
                self._spawn(lm)
            except Exception as e:
                lm.state, lm.reason = "refused", f"{type(e).__name__}: {e}"
        if wait:
            self.join(timeout)
        return self.status()

    def join(self, timeout=None):
        end = None if timeout is None else time.monotonic() + timeout
        for lm in self.modules.values():
            if lm.threads:
                t = lm.threads[2]
                t.join(None if end is None else max(0.0, end - time.monotonic()))

    def stop(self, timeout=5.0):
        for lm in self.modules.values():
            if lm.proc is None or lm.proc.poll() is not None:
                continue
            self._send(lm, {"type": "stop"})
            try:
                lm.proc.wait(timeout)
            except subprocess.TimeoutExpired:
                lm.proc.terminate()
                try:
                    lm.proc.wait(2)
                except subprocess.TimeoutExpired:
                    lm.proc.kill()
            if lm.state == "running":
                lm.state = "stopped"
        self.join(5)
        return self.status()

    def status(self):
        return [lm.status() for lm in sorted(self.modules.values(), key=lambda m: m.name)]
