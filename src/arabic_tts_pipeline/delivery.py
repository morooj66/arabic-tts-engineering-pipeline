"""Delivery rules - the part that keeps "production finished" apart from "humans approved".
Categories of ONE recording slot (word x voice):
  HUMAN_ACCEPTED  a human accepted this exact recording        (the only category that counts as human approval)
  AUTO_READY      passed the automatic gate, no human decision   (valid for review/delivery, NOT approved)
  ISOLATED        failed the automatic gate, no human accept     (kept, never deleted, never retried automatically)
  REJECTED        a human rejected / sent it back                (a human decision always overrides the gate)
  BLOCKED         the entry is excluded (cannot be produced yet) NO_RECORDING  nothing was produced
Two-voice rule: a word is delivered only if BOTH voices have a VALID slot (HUMAN_ACCEPTED or AUTO_READY). A blocked or isolated slot never completes a pair."""
from dataclasses import dataclass
import csv
from pathlib import Path

HUMAN_ACCEPTED, AUTO_READY, ISOLATED, REJECTED, BLOCKED, NO_RECORDING = "HUMAN_ACCEPTED", "AUTO_READY", "ISOLATED", "REJECTED", "BLOCKED", "NO_RECORDING"
VALID = {HUMAN_ACCEPTED, AUTO_READY}

@dataclass(frozen=True)
class Slot:
    entry_id: str
    voice: str
    gender: str
    sha256: str | None
    audio_path: str | None
    gate_status: str | None          # PASS_GATE | HOLD | None
    blocked: bool = False
    text_sent: str = ""

def categorize(slot: Slot, decision: str | None) -> str:
    if slot.blocked: return BLOCKED
    if slot.sha256 is None: return NO_RECORDING
    if decision in {"reject", "recorrect", "regenerate", "linguistic_review"}: return REJECTED
    if decision == "accept": return HUMAN_ACCEPTED
    return AUTO_READY if slot.gate_status == "PASS_GATE" else ISOLATED

def build(slots: list[Slot], decisions: dict[tuple, dict], lexical: dict[str, str]) -> dict:
    """decisions: (entry_id, voice, sha256) -> event (ReviewLog.current())."""
    by_word: dict[str, dict[str, tuple[Slot, str]]] = {}
    for s in slots:
        d = decisions.get((s.entry_id, s.voice, s.sha256)); by_word.setdefault(s.entry_id, {})[s.voice] = (s, categorize(s, d["decision"] if d else None))
    pairs, incomplete, counts = [], [], {}
    for entry_id in sorted(by_word):
        cats = {v: c for v, (s, c) in by_word[entry_id].items()}
        for c in cats.values(): counts[c] = counts.get(c, 0) + 1
        row = {"entry_id": entry_id, "lemma": lexical.get(entry_id, ""), **{f"{v}_category": c for v, c in cats.items()}}
        (pairs if len(cats) >= 2 and all(c in VALID for c in cats.values()) else incomplete).append(row)
    return {"words": len(by_word), "two_voice_words": len(pairs), "incomplete_words": len(incomplete), "recordings_in_delivery": 2 * len(pairs), "counts_by_category": dict(sorted(counts.items())),
            "human_accepted": counts.get(HUMAN_ACCEPTED, 0), "auto_ready_not_human_approved": counts.get(AUTO_READY, 0), "pairs": pairs, "incomplete": incomplete, "slots": by_word}

def platform_tasks(delivery: dict, lexical: dict, senses: dict, base_url: str = "https://storage.example.invalid/audio") -> list[dict]:
    """Seven-column import sheet for a review platform (synthetic URLs). Only complete pairs; one row per (entry_id, gender); the key must be unique inside the batch."""
    rows, seen = [], set()
    for pair in delivery["pairs"]:
        eid = pair["entry_id"]
        for voice, (slot, _cat) in delivery["slots"][eid].items():
            key = (eid, slot.gender)
            if key in seen: raise ValueError(f"DUPLICATE_KEY:{key}")
            seen.add(key); n = int(eid[1:]) if eid[1:].isdigit() else eid
            rows.append({"entry_id": n, "sense_id": n, "lemma": lexical[eid], "sense": senses.get(eid, ""), "audio_url": f"{base_url}/{eid}/{slot.gender}/{slot.sha256[:12]}.wav", "audio_model": "synthetic-mock", "audio_gender": slot.gender})
    if any(not r["audio_url"].startswith("https://") for r in rows): raise ValueError("NON_HTTPS_URL")
    if {g for _, g in seen} - {"male", "female"}: raise ValueError("BAD_GENDER")
    return rows

def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows: path.write_text("", encoding="utf-8"); return
    with path.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
