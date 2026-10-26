"""SQLite storage: devices (pending, approved, revoked) and events.

One file on the coordinator's dataset (TrueNAS: a host path mounted at /data).
Events older than the retention window are removed. Positions are never
stored: they are removed from events before insert (privacy.strip_positions).
"""

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
  station_id   TEXT PRIMARY KEY,
  public_key   TEXT NOT NULL,
  name         TEXT,
  state        TEXT NOT NULL CHECK (state IN ('pending', 'approved', 'revoked')),
  capability   TEXT,
  requested_utc TEXT NOT NULL,
  decided_utc  TEXT,
  last_seq     INTEGER NOT NULL DEFAULT -1
);
CREATE TABLE IF NOT EXISTS events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  station_id   TEXT NOT NULL REFERENCES devices(station_id),
  received_utc TEXT NOT NULL,
  kind         TEXT,
  time_utc     TEXT,
  body         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_station_time ON events(station_id, time_utc);
"""


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)
        self.lock = threading.RLock()     # one connection shared by the HTTP threads

    def device(self, station_id):
        with self.lock:
            r = self.db.execute("SELECT station_id, public_key, name, state, capability, requested_utc, decided_utc, last_seq "
                            "FROM devices WHERE station_id = ?", (station_id,)).fetchone()
        if not r:
            return None
        keys = ("station_id", "public_key", "name", "state", "capability", "requested_utc", "decided_utc", "last_seq")
        d = dict(zip(keys, r))
        d["capability"] = json.loads(d["capability"]) if d["capability"] else None
        return d

    def devices(self, state=None):
        q = "SELECT station_id FROM devices" + (" WHERE state = ?" if state else "") + " ORDER BY requested_utc"
        with self.lock:
            ids = [r[0] for r in self.db.execute(q, (state,) if state else ())]
            return [self.device(i) for i in ids]

    def counts(self):
        out = {"pending": 0, "approved": 0, "revoked": 0}
        with self.lock:
            for state, n in self.db.execute("SELECT state, COUNT(*) FROM devices GROUP BY state").fetchall():
                out[state] = n
        return out

    def request_join(self, station_id, public_key, seq, name=None, capability=None):
        """Record a join request; returns the device's state. A known key keeps its state."""
        with self.lock:
            d = self.device(station_id)
            if d is None:
                self.db.execute("INSERT INTO devices (station_id, public_key, name, state, capability, requested_utc, last_seq) "
                                "VALUES (?, ?, ?, 'pending', ?, ?, ?)",
                                (station_id, public_key, name, json.dumps(capability) if capability else None, utcnow(), seq))
                return "pending"
            if seq <= d["last_seq"]:
                raise ValueError("seq not increasing")
            if d["state"] == "pending":
                self.db.execute("UPDATE devices SET name = ?, capability = ?, last_seq = ? WHERE station_id = ?",
                                (name, json.dumps(capability) if capability else None, seq, station_id))
            else:
                self.db.execute("UPDATE devices SET last_seq = ? WHERE station_id = ?", (seq, station_id))
            return d["state"]

    def decide(self, station_id, state):
        if state not in ("approved", "revoked"):
            raise ValueError("state must be approved or revoked")
        with self.lock:
            n = self.db.execute("UPDATE devices SET state = ?, decided_utc = ? WHERE station_id = ?",
                                (state, utcnow(), station_id)).rowcount
        return bool(n)

    def add_events(self, station_id, seq, events):
        """Insert events and move last_seq, in one transaction; refuses a seq that isn't newer."""
        with self.lock:
            d = self.device(station_id)
            if d is None or d["state"] != "approved":
                raise PermissionError("not approved")
            if seq <= d["last_seq"]:
                raise ValueError("seq not increasing")
            now = utcnow()
            self.db.execute("BEGIN")
            try:
                for e in events:
                    self.db.execute("INSERT INTO events (station_id, received_utc, kind, time_utc, body) VALUES (?, ?, ?, ?, ?)",
                                    (station_id, now, e.get("kind"), e.get("time_utc"), json.dumps(e, sort_keys=True)))
                self.db.execute("UPDATE devices SET last_seq = ? WHERE station_id = ?", (seq, station_id))
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def events(self, station_id=None, limit=100):
        q = "SELECT station_id, received_utc, body FROM events" + (" WHERE station_id = ?" if station_id else "") + \
            " ORDER BY id DESC LIMIT ?"
        args = (station_id, limit) if station_id else (limit,)
        with self.lock:
            rows = self.db.execute(q, args).fetchall()
        return [{"station_id": s, "received_utc": r, "event": json.loads(b)} for s, r, b in rows]

    def prune(self, retention_days, now=None):
        now = now or datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=retention_days)).replace(microsecond=0).isoformat()
        with self.lock:
            return self.db.execute("DELETE FROM events WHERE received_utc < ?", (cutoff,)).rowcount
