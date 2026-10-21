"""One module, in its own process: python -m gps_time_pi.modkit.runner

Protocol (JSON lines):
- stdin, first line: the spec from the host (module folder, entry, config,
  permissions, limits, storage, user, context, denied paths).
- stdin, later: {"type": "stop"} and {"type": "context", "timing": ..., "site": ...}.
- stdout: {"type": "ready"}, {"type": "emit", "item": ...}, {"type": "exit", "state": "finished"},
  {"type": "error", "error": ...}. The module's own prints go to stderr.

Order: drop privileges, apply limits, install the guard, and only then import
the module's code (sandbox.py).
"""

import importlib
import json
import os
import sys
import threading

from . import sandbox
from .context import CappedStorage, ModuleContext
from .interfaces import TYPE_BASES, Observation, Result


def main():
    proto = os.fdopen(os.dup(1), "w", encoding="utf-8", buffering=1)
    os.dup2(2, 1)                      # module prints go to stderr, not into the protocol
    sys.stdout = sys.stderr
    lock = threading.Lock()

    def send(msg):
        line = json.dumps(msg, separators=(",", ":"))
        with lock:
            proto.write(line + "\n")
            proto.flush()

    try:
        spec = json.loads(sys.stdin.readline())
    except ValueError as e:
        send({"type": "error", "error": f"bad spec: {e}"})
        return 2

    try:
        user = sandbox.drop_privileges(spec.get("user"))
        if spec.get("enforce", True):
            sandbox.apply_limits(spec["limits"])
        storage = None
        st = spec.get("storage")
        if st:
            storage = CappedStorage(st["dir"], st["cap_bytes"], rate_bytes_per_hour=st.get("rate_bytes_per_hour"))
        roots = [st["dir"]] if st else []
        threading.stack_size(512 * 1024)
        sandbox.install_guard(spec["permissions"], roots, spec.get("deny_read", []))
    except Exception as e:
        send({"type": "error", "error": f"sandbox: {type(e).__name__}: {e}"})
        return 3

    ctx_state = {"timing": spec.get("timing") or {"state": "UNKNOWN", "offset_bound_s": None},
                 "site": spec.get("site")}

    def emit(item):
        d = item.to_dict() if isinstance(item, (Observation, Result)) else item
        send({"type": "emit", "item": d})

    ctx = ModuleContext(spec["name"], config=spec.get("config"), emit=emit,
                        timing_quality=lambda: dict(ctx_state["timing"]),
                        site=lambda: None if ctx_state["site"] is None else dict(ctx_state["site"]),
                        storage=storage)
    try:
        sys.path.insert(0, spec["module_dir"])
        modname, clsname = spec["entry"].split(":")
        cls = getattr(importlib.import_module(modname), clsname)
        base = TYPE_BASES[spec["kind"]]
        if not (isinstance(cls, type) and issubclass(cls, base)):
            raise TypeError(f"{spec['entry']} is not a {base.__name__}")
        src = cls()
    except Exception as e:
        send({"type": "error", "error": f"entry point failed: {type(e).__name__}: {e}"})
        return 4

    def control():
        for line in sys.stdin:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("type") == "stop":
                try:
                    src.stop()
                except Exception:
                    pass
                return
            if msg.get("type") == "context":
                ctx_state["timing"] = msg.get("timing") or ctx_state["timing"]
                ctx_state["site"] = msg.get("site")
    threading.Thread(target=control, daemon=True).start()

    send({"type": "ready", "user": user})
    try:
        src.start(ctx)
    except Exception as e:
        send({"type": "error", "error": f"{type(e).__name__}: {e}"})
        return 1
    send({"type": "exit", "state": "finished"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
