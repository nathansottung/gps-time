"""HTTP endpoints (JSON). Every write is a signed message (messages.py).

  GET  /v1/health   version and device counts; no device data
  POST /v1/join     a station asks to join; stays pending until the owner approves (CLI)
  POST /v1/events   an approved station sends events; seq must increase

Plain HTTP on the LAN: messages are signed, so they can't be forged or
replayed, but they are not encrypted. Put TLS in front (TrueNAS's reverse
proxy or another) before any traffic leaves the LAN.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__, messages, privacy


def make_handler(store, max_body):
    class Handler(BaseHTTPRequestHandler):
        server_version = "gps-time-coordinator"
        sys_version = ""

        def _json(self, code, obj):
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/v1/health":
                self._json(200, {"ok": True, "version": __version__, "devices": store.counts()})
            else:
                self._json(404, {"ok": False, "error": "not found"})

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if not 0 < length <= max_body:
                self.close_connection = True
                return self._json(413 if length > max_body else 400, {"ok": False, "error": f"body must be 1..{max_body} bytes"})
            raw = self.rfile.read(length)
            if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
                return self._json(415, {"ok": False, "error": "Content-Type must be application/json"})
            try:
                env = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                return self._json(400, {"ok": False, "error": "invalid JSON"})
            if self.path == "/v1/join":
                return self._join(env)
            if self.path == "/v1/events":
                return self._events(env)
            return self._json(404, {"ok": False, "error": "not found"})

        def _join(self, env):
            try:
                messages.verify(env)
                if env["type"] != "join":
                    raise messages.MessageError("expected type join")
                known = store.device(env["station_id"])
                if known and known["public_key"] != env["public_key"]:
                    raise messages.MessageError("public key differs from the one on record")
                body, _ = privacy.strip_positions(env["body"])
                name = body.get("name") if isinstance(body.get("name"), str) else None
                state = store.request_join(env["station_id"], env["public_key"], env["seq"],
                                           name=name[:64] if name else None, capability=body.get("capability"))
            except messages.MessageError as e:
                return self._json(400, {"ok": False, "error": str(e)})
            except ValueError as e:
                return self._json(409, {"ok": False, "error": str(e)})
            if state == "revoked":
                return self._json(403, {"ok": False, "state": state})
            return self._json(202 if state == "pending" else 200, {"ok": True, "state": state})

        def _events(self, env):
            try:
                messages.check_shape(env)
                d = store.device(env["station_id"])
                if d is None or d["state"] != "approved":
                    return self._json(403, {"ok": False, "error": "station not approved",
                                             "state": d["state"] if d else None})
                messages.verify(env, known_public_key=d["public_key"])
                if env["type"] != "events":
                    raise messages.MessageError("expected type events")
                events, removed = privacy.strip_positions(env["body"]["events"])
                store.add_events(env["station_id"], env["seq"], events)
            except messages.MessageError as e:
                return self._json(400, {"ok": False, "error": str(e)})
            except PermissionError as e:
                return self._json(403, {"ok": False, "error": str(e)})
            except ValueError as e:
                return self._json(409, {"ok": False, "error": str(e)})
            return self._json(200, {"ok": True, "accepted": len(events), "position_fields_removed": removed})

        def log_message(self, fmt, *args):
            pass

    return Handler


def serve(store, bind, port, max_body):
    httpd = ThreadingHTTPServer((bind, port), make_handler(store, max_body))
    return httpd
