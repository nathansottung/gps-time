"""python -m gps_time_pi.modkit list | check | demo <name>

list   every module found, with its state for this station's config
check  validate every manifest and interface version; exit 1 if any is invalid
demo   run one module, sandboxed, with {"demo": true} and print what it emits (JSON lines).
       Where the sandbox isn't available (Windows), the demo runs it unenforced and says so.
"""

import argparse
import json
import sys

from . import loader


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m gps_time_pi.modkit", description=__doc__.splitlines()[0])
    ap.add_argument("--dir", help="modules folder (default: GTP_MODULES_DIR or modules/)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("check")
    d = sub.add_parser("demo")
    d.add_argument("name")
    d.add_argument("--timeout", type=float, default=60.0)
    d.add_argument("--user", help="module user when run as root (default: none; root refuses)")
    a = ap.parse_args(argv)

    if a.cmd in ("list", "check"):
        found = loader.discover(a.dir)
        enabled = []
        if a.cmd == "list":
            from .. import config   # only here: reading the station config is the list's job
            enabled = loader.enabled_from_config(config.load())
        bad = 0
        for folder, m, errs in found:
            if errs:
                bad += 1
                print(f"{folder.name}: INVALID")
                for e in errs:
                    print(f"  {e}")
            elif a.cmd == "list":
                state = "enabled" if m.name in enabled else "disabled"
                print(f"{m.name} {m.version} [{m.maturity}] {'/'.join(m.types)}: {state}")
            else:
                print(f"{m.name}: ok (interface {m.interface})")
        if not found:
            print("no modules found")
        return 1 if (a.cmd == "check" and bad) else 0

    out = []
    from .sandbox import available
    unenforced = not available()
    if unenforced:
        print("warning: the module sandbox isn't available on this platform; running the demo unenforced",
              file=sys.stderr)
    host = loader.ModuleHost(a.dir, [a.name], configs={a.name: {"demo": True}}, user=a.user,
                             allow_unenforced=unenforced, emit=lambda name, item: out.append(item))
    host.load()
    host.start()
    host.join(a.timeout)
    host.stop()
    for item in out:
        print(json.dumps(item, sort_keys=True))
    st = next((s for s in host.status() if s["name"] == a.name), None)
    print(json.dumps({"status": st}), file=sys.stderr)
    return 0 if st and st["state"] in ("finished", "stopped") and st["emitted"] else 1


if __name__ == "__main__":
    sys.exit(main())
