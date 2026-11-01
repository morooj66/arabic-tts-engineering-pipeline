"""Append-only human-decision log. A new decision for the same key SUPERSEDES the previous one by reference; nothing is ever rewritten or deleted, so the full history of every judgement stays recoverable.
The key is (entry_id, voice, recording_sha256): a decision about one recording never silently carries over to a newer recording of the same word."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

DECISIONS = {"accept", "reject", "recorrect", "regenerate", "linguistic_review", "withdrawn"}

class ReviewLog:
    def __init__(self, path: Path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)

    def events(self) -> list[dict]:
        if not self.path.exists(): return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def current(self) -> dict[tuple, dict]:
        cur = {}
        for e in self.events(): cur[(e["entry_id"], e["voice"], e["recording_sha256"])] = e
        return {k: e for k, e in cur.items() if e["decision"] != "withdrawn"}

    def append(self, entry_id: str, voice: str, recording_sha256: str, decision: str, note: str = "", reviewer: str = "") -> dict:
        if decision not in DECISIONS: raise ValueError(f"unknown decision: {decision}")
        prev = {(e["entry_id"], e["voice"], e["recording_sha256"]): e for e in self.events()}.get((entry_id, voice, recording_sha256))
        event = {"event_id": uuid.uuid4().hex, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "entry_id": entry_id, "voice": voice, "recording_sha256": recording_sha256,
                 "decision": decision, "note": note, "reviewer": reviewer, "supersedes": prev["event_id"] if prev else None}
        with self.path.open("a", encoding="utf-8") as handle: handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def history(self, entry_id: str, voice: str) -> list[dict]:
        return [e for e in self.events() if e["entry_id"] == entry_id and e["voice"] == voice]
