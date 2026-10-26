"""python -m gps_time_coordinator serve | devices | approve ID | revoke ID | events [ID] | demo-client URL

In the TrueNAS container: `docker exec -it gps-time-coordinator python -m gps_time_coordinator devices`.
"""

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from . import config, messages, server
from .store import Store


def _post(url, env):
    req = urllib.request.Request(url, data=json.dumps(env).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def demo_client(base, key=None):
    """Join, then try to send one synthetic event; prints what the coordinator answered."""
    key = key or messages.new_key()
    seq = int(time.time() * 1000)
    now = datetime.now(timezone.utc).isoformat()
    join = messages.sign({"v": 1, "type": "join", "seq": seq, "sent_utc": now,
                          "body": {"name": "demo-client", "capability": {"demo": True}}}, key)
    print("join:", *_post(base.rstrip("/") + "/v1/join", join))
    ev = messages.sign({"v": 1, "type": "events", "seq": seq + 1, "sent_utc": now,
                        "body": {"events": [{"kind": "demo", "time_utc": now, "note": "synthetic, not a measurement"}]}}, key)
    print("events:", *_post(base.rstrip("/") + "/v1/events", ev))
    print("station_id:", join["station_id"])
    return join["station_id"]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m gps_time_coordinator")
    ap.add_argument("--config")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve")
    d = sub.add_parser("devices")
    d.add_argument("--state", choices=("pending", "approved", "revoked"))
    for name in ("approve", "revoke"):
        sub.add_parser(name).add_argument("station_id")
    e = sub.add_parser("events")
    e.add_argument("station_id", nargs="?")
    e.add_argument("--limit", type=int, default=20)
    sub.add_parser("demo-client").add_argument("url")
    a = ap.parse_args(argv)

    if a.cmd == "demo-client":
        demo_client(a.url)
        return 0
    cfg = config.load(a.config)
    store = Store(cfg["storage"]["database"])
    if a.cmd == "devices":
        for dev in store.devices(a.state):
            print(json.dumps(dev, sort_keys=True))
    elif a.cmd in ("approve", "revoke"):
        ok = store.decide(a.station_id, "approved" if a.cmd == "approve" else "revoked")
        print(f"{a.station_id}: {a.cmd}d" if ok else f"{a.station_id}: no such device")
        return 0 if ok else 1
    elif a.cmd == "events":
        for ev in store.events(a.station_id, a.limit):
            print(json.dumps(ev, sort_keys=True))
    elif a.cmd == "serve":
        if not messages.AVAILABLE:
            print("the cryptography package is not installed; no message can be verified", file=sys.stderr)
            return 2
        days = cfg["storage"]["retention_days"]

        def prune_daily():
            while True:
                store.prune(days)
                time.sleep(86400)

        threading.Thread(target=prune_daily, daemon=True).start()
        httpd = server.serve(store, cfg["server"]["bind"], cfg["server"]["port"], cfg["server"]["max_body_bytes"])
        print(f"gps-time-coordinator listening on {cfg['server']['bind']}:{cfg['server']['port']}", flush=True)
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
