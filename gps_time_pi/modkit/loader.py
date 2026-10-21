"""Find, check, load and run modules.

- Discovery: every folder with a module.toml under the modules directory
  (GTP_MODULES_DIR, default modules/ next to gps_time_pi).
- Off by default: only modules named in the station config's
  "modules_enabled" list are loaded. A station with none enabled behaves
  exactly as before; the web service doesn't use this package yet.
- Refused, with the reason: an invalid manifest, an interface version this
  station can't run, an entry point that doesn't import or isn't the right
  kind of class.
- Running: each source runs in its own thread with its own ctx. An exception
  in a module marks that module failed and never reaches the host. Everything
  a module emits is checked against schemas/; invalid items are dropped and
  counted.

Not yet (SPEC-EXTENSIBILITY "Module safety"): modules run in the host's process,
so declared permissions are recorded but not enforced, and there are no CPU or
memory caps. Running each module as its own unprivileged process comes next.
"""

import importlib
import os
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

from . import manifest as mf
from . import schema
from .context import CappedStorage, ModuleContext
from .interfaces import TYPE_BASES, Observation, Result

DEFAULT_DIR = Path(os.environ.get("GTP_MODULES_DIR") or Path(__file__).resolve().parents[2] / "modules")
RAM_CAP_BYTES = 16 * 1024 * 1024


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


def import_entry(manifest, kind):
    """The class named by the manifest's entry for kind, checked against the interface."""
    spec = manifest.entry[kind]
    modname, clsname = spec.split(":")
    path = str(manifest.path)
    if path not in sys.path:
        sys.path.insert(0, path)
    cls = getattr(importlib.import_module(modname), clsname)
    if not (isinstance(cls, type) and issubclass(cls, TYPE_BASES[kind])):
        raise TypeError(f"{spec} is not a {TYPE_BASES[kind].__name__}")
    return cls


@dataclass
class LoadedModule:
    name: str
    folder: Path
    manifest: object = None
    state: str = "disabled"        # disabled | refused | loaded | running | finished | stopped | failed
    reason: str = ""
    instances: dict = field(default_factory=dict)
    emitted: int = 0
    rejected: int = 0
    thread: object = None

    def status(self):
        m = self.manifest
        return {"name": self.name, "state": self.state, "reason": self.reason,
                "version": m.version if m else None, "maturity": m.maturity if m else None,
                "types": list(m.types) if m else [], "permissions": m.permissions if m else None,
                "emitted": self.emitted, "rejected": self.rejected}


class ModuleHost:
    def __init__(self, root=None, enabled=(), *, emit=None, timing_quality=None, site=None,
                 configs=None, storage_roots=None, clock_ns=None):
        """emit(name, item_dict): receives every valid Observation/Result.
        site(): the privacy-filtered site (config.privacy_site), never the raw one.
        storage_roots: {"ram": folder, "disk": folder}; a module asking for storage
        without a root for its kind is refused."""
        self.root = Path(root or DEFAULT_DIR)
        self.enabled = set(enabled)
        self._emit = emit or (lambda name, item: None)
        self._timing = timing_quality
        self._site = site
        self.configs = configs or {}
        self.storage_roots = storage_roots or {}
        self._clock = clock_ns
        self.modules = {}
        self._schemas = {"observation/1": schema.load("observation.v1"), "result/1": schema.load("result.v1")}

    def load(self):
        for folder, m, errs in discover(self.root):
            lm = LoadedModule(folder.name, folder, m)
            self.modules[folder.name] = lm
            if errs:
                lm.state, lm.reason = "refused", "; ".join(errs)
                continue
            if m.name not in self.enabled:
                continue
            try:
                for kind in m.entry:
                    lm.instances[kind] = import_entry(m, kind)()
                lm.state = "loaded"
            except Exception as e:   # a module's import must never break the host
                lm.instances = {}
                lm.state, lm.reason = "refused", f"entry point failed: {type(e).__name__}: {e}"
        for name in self.enabled - set(self.modules):
            self.modules[name] = LoadedModule(name, self.root / name, None, "refused", "enabled but not found")
        return self.status()

    def _storage(self, lm):
        kind = lm.manifest.permissions["storage"]
        if kind == "none":
            return None
        if kind == "ram":
            root, cap = self.storage_roots.get("ram"), RAM_CAP_BYTES
        else:
            root, cap = self.storage_roots.get("disk"), int(kind[5:-3]) * 1024 * 1024
        if not root:
            raise PermissionError(f"storage {kind} requested but the host gives none")
        return CappedStorage(Path(root) / lm.name, cap)

    def _ctx(self, lm):
        def emit(item):
            d = item.to_dict() if isinstance(item, (Observation, Result)) else item
            sch = self._schemas.get(d.get("schema")) if isinstance(d, dict) else None
            if sch is None or schema.validate(d, sch):
                lm.rejected += 1
                return
            lm.emitted += 1
            self._emit(lm.name, d)
        kw = {}
        if self._clock:
            kw["clock_ns"] = self._clock
        return ModuleContext(lm.name, config=self.configs.get(lm.name), emit=emit,
                             timing_quality=self._timing, site=self._site, storage=self._storage(lm), **kw)

    def start(self, wait=False):
        for lm in self.modules.values():
            src = lm.instances.get("source")
            if lm.state != "loaded" or src is None:
                continue
            try:
                ctx = self._ctx(lm)
            except Exception as e:
                lm.state, lm.reason = "refused", str(e)
                continue

            def run(lm=lm, src=src, ctx=ctx):
                try:
                    src.start(ctx)
                    if lm.state == "running":
                        lm.state = "finished"
                except Exception as e:   # contained: the module fails, the host carries on
                    lm.state, lm.reason = "failed", f"{type(e).__name__}: {e}"

            lm.state = "running"
            lm.thread = threading.Thread(target=run, name=f"module-{lm.name}", daemon=True)
            lm.thread.start()
        if wait:
            self.join()
        return self.status()

    def join(self, timeout=None):
        for lm in self.modules.values():
            if lm.thread:
                lm.thread.join(timeout)

    def stop(self, timeout=5.0):
        for lm in self.modules.values():
            src = lm.instances.get("source")
            if src is not None and lm.state == "running":
                try:
                    src.stop()
                except Exception as e:
                    lm.state, lm.reason = "failed", f"stop: {type(e).__name__}: {e}"
                if lm.thread:
                    lm.thread.join(timeout)
                if lm.state == "running":
                    lm.state = "stopped"
        return self.status()

    def status(self):
        return [lm.status() for lm in sorted(self.modules.values(), key=lambda m: m.name)]
