"""Durable at-most-once intent journal. Uncertain sends are never retried."""

import json
import sqlite3
from datetime import UTC, datetime


class Journal:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS intents(key TEXT PRIMARY KEY, day TEXT, status TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS events(time TEXT, kind TEXT, payload TEXT);
        """)

    def event(self, kind, payload):
        with self.db:
            self.db.execute(
                "INSERT INTO events VALUES(?,?,?)",
                (datetime.now(UTC).isoformat(), kind, json.dumps(payload, default=str)),
            )

    def seen(self, key):
        return self.db.execute("SELECT 1 FROM intents WHERE key=?", (key,)).fetchone() is not None

    def count(self, day):
        return self.db.execute("SELECT COUNT(*) FROM intents WHERE day=?", (day,)).fetchone()[0]

    def reserve(self, proposal, day):
        with self.db:
            self.db.execute(
                "INSERT INTO intents VALUES(?,?,?,?)",
                (proposal.key, day, "UNKNOWN", json.dumps(proposal.__dict__, default=str)),
            )

    def status(self, key, status):
        with self.db:
            self.db.execute("UPDATE intents SET status=? WHERE key=?", (status, key))

    def unresolved(self):
        return self.db.execute(
            "SELECT key,status FROM intents WHERE status NOT IN ('Filled','Cancelled','ApiCancelled','Rejected')"
        ).fetchall()
