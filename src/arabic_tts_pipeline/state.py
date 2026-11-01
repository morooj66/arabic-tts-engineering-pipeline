import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs(entry_id TEXT PRIMARY KEY, source_text TEXT NOT NULL, spoken_text TEXT,
 status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, audio_path TEXT, quality_json TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, entry_id TEXT, kind TEXT, payload TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS reviews(entry_id TEXT PRIMARY KEY, decision TEXT NOT NULL, note TEXT, reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
"""

class StateStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def upsert_source(self, entry_id, text):
        self.conn.execute("INSERT INTO jobs(entry_id,source_text,status) VALUES(?,?,'PENDING') ON CONFLICT(entry_id) DO NOTHING", (entry_id, text)); self.conn.commit()

    def row(self, entry_id): return self.conn.execute("SELECT * FROM jobs WHERE entry_id=?", (entry_id,)).fetchone()
    def pending(self): return self.conn.execute("SELECT * FROM jobs WHERE status NOT IN ('READY_FOR_REVIEW','APPROVED') ORDER BY entry_id").fetchall()
    def all(self): return self.conn.execute("SELECT * FROM jobs ORDER BY entry_id").fetchall()

    def update(self, entry_id, status, **fields):
        allowed = {"spoken_text", "attempts", "audio_path", "quality_json", "error"}
        bad = set(fields) - allowed
        if bad: raise ValueError(f"Unsupported fields: {sorted(bad)}")
        values = {"status": status, **fields}; assignments = ",".join(f"{k}=?" for k in values)
        self.conn.execute(f"UPDATE jobs SET {assignments} WHERE entry_id=?", (*values.values(), entry_id))
        self.conn.execute("INSERT INTO events(entry_id,kind,payload) VALUES(?,?,?)", (entry_id, status, json.dumps(fields, ensure_ascii=False)))
        self.conn.commit()

    def review(self, entry_id, decision, note=""):
        if decision not in {"APPROVED", "REJECTED", "NEEDS_CORRECTION"}: raise ValueError("INVALID_REVIEW_DECISION")
        row = self.row(entry_id)
        if not row or row["status"] != "READY_FOR_REVIEW": raise ValueError("ENTRY_NOT_READY_FOR_REVIEW")
        self.conn.execute("INSERT INTO reviews(entry_id,decision,note) VALUES(?,?,?) ON CONFLICT(entry_id) DO UPDATE SET decision=excluded.decision,note=excluded.note,reviewed_at=CURRENT_TIMESTAMP", (entry_id, decision, note))
        self.conn.execute("UPDATE jobs SET status=? WHERE entry_id=?", (decision, entry_id)); self.conn.commit()

