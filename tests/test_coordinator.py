"""Coordinator skeleton (coordinator/gps_time_coordinator, ADR-0008).

Without the cryptography package (the plain CI run) the signature tests skip;
CI runs this file again in the station venv and fails if anything skips.
No network beyond 127.0.0.1, no root.
"""

import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests import _env  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "coordinator"))
from gps_time_coordinator import config, messages, privacy, server  # noqa: E402
from gps_time_coordinator.store import Store  # noqa: E402

needs_crypto = unittest.skipUnless(messages.AVAILABLE, "cryptography is not installed")
NOW = "2026-10-26T12:00:00+00:00"


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gtc-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.store = Store(str(self.tmp / "c.sqlite3"))
        self.addCleanup(self.store.db.close)


class TestConfig(Tmp):
    def test_defaults_and_overrides(self):
        self.assertEqual(config.load(self.tmp / "none.toml")["server"]["port"], 8090)
        f = self.tmp / "c.toml"
        f.write_text("[storage]\nretention_days = 30\n", encoding="utf-8")
        self.assertEqual(config.load(f)["storage"]["retention_days"], 30)

    def test_unknown_or_wrong_keys_refused(self):
        f = self.tmp / "c.toml"
        for text in ("[nope]\na = 1\n", "[server]\nporte = 1\n", "[server]\nport = \"80\"\n", "[storage]\nretention_days = 0\n"):
            f.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError, msg=text):
                config.load(f)

    def test_example_file_is_the_defaults(self):
        self.assertEqual(config.load(ROOT / "coordinator" / "coordinator.example.toml"), config.DEFAULTS)


class TestPrivacy(unittest.TestCase):
    def test_positions_removed_at_any_depth(self):
        ev = {"kind": "x", "lat": 38.9217, "data": {"Longitude": -77.0669, "site": {"a": 1}, "keep": [{"alt_hae": 59}, 2]}}
        out, n = privacy.strip_positions(ev)
        self.assertEqual(out, {"kind": "x", "data": {"keep": [{}, 2]}})
        self.assertEqual(n, 4)


class TestStore(Tmp):
    def test_join_approve_events_seq(self):
        s = self.store
        self.assertEqual(s.request_join("id1", "pk", 5, name="a"), "pending")
        with self.assertRaises(ValueError):
            s.request_join("id1", "pk", 5)
        with self.assertRaises(PermissionError):
            s.add_events("id1", 6, [{"kind": "k"}])
        self.assertTrue(s.decide("id1", "approved"))
        s.add_events("id1", 6, [{"kind": "k", "time_utc": NOW}])
        with self.assertRaises(ValueError):
            s.add_events("id1", 6, [{"kind": "k"}])                # replay
        self.assertEqual(s.counts(), {"pending": 0, "approved": 1, "revoked": 0})
        self.assertEqual(s.events("id1")[0]["event"]["kind"], "k")
        self.assertFalse(s.decide("nope", "approved"))

    def test_prune(self):
        self.store.request_join("id1", "pk", 0)
        self.store.decide("id1", "approved")
        self.store.add_events("id1", 1, [{"kind": "old"}])
        later = datetime.now(timezone.utc) + timedelta(days=91)
        self.assertEqual(self.store.prune(90, now=later), 1)


class TestShape(unittest.TestCase):
    def env(self, **kw):
        e = {"v": 1, "type": "events", "station_id": "ed25519:x", "public_key": "AA==", "seq": 1,
             "sent_utc": NOW, "body": {"events": [{"kind": "k"}]}, "signature": "ed25519:AA=="}
        e.update(kw)
        return e

    def test_shape(self):
        messages.check_shape(self.env())
        for bad in (self.env(v=2), self.env(type="other"), self.env(seq=-1), self.env(seq=True),
                    self.env(body={"events": []}), self.env(body={"events": [1]}), self.env(signature=None)):
            with self.assertRaises(messages.MessageError):
                messages.check_shape(bad)

    def test_unverifiable_without_the_library(self):
        from unittest import mock
        with mock.patch.object(messages, "AVAILABLE", False), self.assertRaises(messages.MessageError) as e:
            messages.verify(self.env())
        self.assertIn("not checked", str(e.exception))


@needs_crypto
class TestSignatures(unittest.TestCase):
    def test_sign_verify_and_tamper(self):
        k = messages.new_key()
        e = messages.sign({"v": 1, "type": "join", "seq": 1, "sent_utc": NOW, "body": {"name": "a"}}, k)
        messages.verify(e)
        e2 = dict(e, body={"name": "b"})
        with self.assertRaises(messages.MessageError):
            messages.verify(e2)
        e3 = dict(e, station_id="ed25519:" + "0" * 64)
        with self.assertRaises(messages.MessageError):
            messages.verify(e3)
        other = messages.sign({"v": 1, "type": "join", "seq": 1, "sent_utc": NOW, "body": {}}, messages.new_key())
        with self.assertRaises(messages.MessageError):
            messages.verify(e, known_public_key=other["public_key"])

    def test_a_station_key_signs_messages(self):
        from gps_time_pi import station_key
        tmp = Path(tempfile.mkdtemp(prefix="gtc-key-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        sid = station_key.generate(tmp / "station-key")
        k = messages.private_from_pem((tmp / "station-key").read_bytes())
        e = messages.sign({"v": 1, "type": "join", "seq": 1, "sent_utc": NOW, "body": {}}, k)
        self.assertEqual(e["station_id"], sid)                        # same identity as the station's files
        messages.verify(e)


@needs_crypto
class TestHttp(Tmp):
    def setUp(self):
        super().setUp()
        self.httpd = server.serve(self.store, "127.0.0.1", 0, 65536)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.key = messages.new_key()
        self.seq = 0

    def call(self, method, path, body=None, ctype="application/json"):
        c = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=10)
        self.addCleanup(c.close)
        data = json.dumps(body).encode() if body is not None else None
        c.request(method, path, body=data, headers={"Content-Type": ctype} if data else {})
        r = c.getresponse()
        return r.status, json.loads(r.read() or b"{}")

    def msg(self, type_, body, key=None, seq=None):
        self.seq += 1
        return messages.sign({"v": 1, "type": type_, "seq": self.seq if seq is None else seq,
                              "sent_utc": NOW, "body": body}, key or self.key)

    def test_flow(self):
        status, body = self.call("POST", "/v1/join", self.msg("join", {"name": "station-a", "capability": {"pps": True}}))
        self.assertEqual((status, body["state"]), (202, "pending"))
        sid = self.store.devices()[0]["station_id"]
        status, _ = self.call("POST", "/v1/events", self.msg("events", {"events": [{"kind": "outage"}]}))
        self.assertEqual(status, 403)                                  # not approved yet
        self.store.decide(sid, "approved")
        ev = self.msg("events", {"events": [{"kind": "outage", "time_utc": NOW, "lat": 38.9217,
                                             "detail": {"lon": -77.0669, "seconds": 56}}]})
        status, body = self.call("POST", "/v1/events", ev)
        self.assertEqual((status, body["accepted"], body["position_fields_removed"]), (200, 1, 2))
        stored = self.store.events(sid)[0]["event"]
        self.assertEqual(stored, {"kind": "outage", "time_utc": NOW, "detail": {"seconds": 56}})
        self.assertEqual(self.call("POST", "/v1/events", ev)[0], 409)    # replay
        self.store.decide(sid, "revoked")
        self.assertEqual(self.call("POST", "/v1/events", self.msg("events", {"events": [{"kind": "x"}]}))[0], 403)
        self.assertEqual(self.call("POST", "/v1/join", self.msg("join", {}))[0], 403)
        status, body = self.call("GET", "/v1/health")
        self.assertEqual(body["devices"], {"pending": 0, "approved": 0, "revoked": 1})

    def test_forgery_and_bad_requests(self):
        j = self.msg("join", {"name": "a"})
        self.call("POST", "/v1/join", j)
        self.store.decide(j["station_id"], "approved")
        forged = self.msg("events", {"events": [{"kind": "x"}]}, key=messages.new_key())
        forged["station_id"] = j["station_id"]
        self.assertEqual(self.call("POST", "/v1/events", forged)[0], 400)
        tampered = self.msg("events", {"events": [{"kind": "x"}]})
        tampered["body"]["events"][0]["kind"] = "y"
        self.assertEqual(self.call("POST", "/v1/events", tampered)[0], 400)
        self.assertEqual(self.call("POST", "/v1/join", self.msg("join", {}), ctype="text/plain")[0], 415)
        self.assertEqual(self.call("POST", "/v1/nowhere", self.msg("join", {}))[0], 404)
        self.assertEqual(self.call("GET", "/v1/devices")[0], 404)       # no device data over HTTP
        self.assertEqual(len(self.store.events()), 0)


class TestPackaging(unittest.TestCase):
    def test_not_in_the_station_bundle(self):
        build = (ROOT / "tools" / "build_bundles.py").read_text(encoding="utf-8")
        self.assertNotIn('"coordinator"', build)

    def test_station_never_imports_it(self):
        for f in (ROOT / "gps_time_pi").rglob("*.py"):
            self.assertNotIn("gps_time_coordinator", f.read_text(encoding="utf-8"), f.name)

    def test_same_cryptography_pin_as_the_station(self):
        pin = lambda p: next(l for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("cryptography=="))
        self.assertEqual(pin(ROOT / "coordinator" / "requirements.txt"), pin(ROOT / "requirements.txt"))

    def test_compose_runs_unprivileged(self):
        text = (ROOT / "coordinator" / "compose.yaml").read_text(encoding="utf-8")
        for needle in ('user: "568:568"', "read_only: true", "- ALL", "no-new-privileges:true", ":/config:ro"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
