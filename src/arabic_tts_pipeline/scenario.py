"""End-to-end SYNTHETIC two-voice scenario: policy -> synth -> technical check -> simulated judge -> gate -> batch guard -> review log -> delivery rules -> platform export.
Everything is offline and deterministic. Faults are injected from a JSON file so every branch (isolation, retry, human decision, incomplete pair) can be shown and tested."""
import csv
import hashlib
import json
from pathlib import Path
from . import delivery
from .audio import validate_wav
from .gate import evaluate, select_per_word
from .guard import BatchReport, Guard
from .judge import MockJudge
from .pausal import PronunciationPolicy, letters_preserved
from .reviewlog import ReviewLog
from .voices import VOICES, synth_for

POLICIES = {"voice_a": "waqf", "voice_b": "verbatim"}      # mirrors the original system: one voice got the pausal form, the other the verbatim text
MAX_ATTEMPTS = 2

def load_entries(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle: return list(csv.DictReader(handle))

def _faults_for(faults: dict, entry_id: str, voice: str, attempt: int) -> list[str]:
    return list(faults.get(f"{entry_id}/{voice}", [])) + list(faults.get(f"{entry_id}/{voice}@{attempt}", []))

def produce_slot(entry: dict, voice: str, policy: PronunciationPolicy, faults: dict, out: Path) -> dict:
    """Up to MAX_ATTEMPTS takes for one word x voice. The best passing take wins; if none passes the slot is ISOLATED (all takes are kept on disk)."""
    entry_id, lemma = entry["entry_id"], entry["lemma"]
    text_sent, rule = policy.prepare(entry_id, lemma)
    if not letters_preserved(lemma, text_sent, policy.letter_map_for(entry_id, lemma)):
        return {"entry_id": entry_id, "voice": voice, "blocked": True, "reason": "TEXT_POLICY_CHANGED_LETTERS", "takes": []}
    takes, results = {}, {}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        audio = synth_for(voice).synthesize(text_sent); quality = validate_wav(audio)
        sha = hashlib.sha256(audio).hexdigest() + f"-{attempt}" if attempt > 1 else hashlib.sha256(audio).hexdigest()
        path = out / "audio" / voice / f"{entry_id}_attempt{attempt}.wav"; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(audio)
        evidence = MockJudge({f"{entry_id}": _faults_for(faults, entry_id, voice, attempt)}).evaluate(entry_id, text_sent)
        res = evaluate(evidence, lemma, technical_ok=quality.valid, letter_map=policy.letter_map_for(entry_id, lemma))
        tid = f"{attempt}"; takes[tid] = {"attempt": attempt, "path": str(path), "sha256": sha, "gate": res}; results[tid] = res
        if res.status == "PASS_GATE": break                       # a passing take ends the loop: no further spend on this slot
    best = select_per_word(results)
    chosen = takes[best] if best else takes[str(len(takes))]      # when isolated, the last take is the one kept as "current"
    return {"entry_id": entry_id, "voice": voice, "blocked": False, "rule": rule, "text_sent": text_sent, "takes": list(takes.values()), "chosen": chosen, "attempts": len(takes)}

def run(entries_path: Path, faults_path: Path | None, reviews_path: Path | None, out: Path, guard_mode: str = "advisory", batch_size: int = 4, blocked: set[str] | None = None) -> dict:
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    entries = load_entries(entries_path); faults = json.loads(Path(faults_path).read_text(encoding="utf-8")) if faults_path else {}
    overrides = json.loads((Path(entries_path).parent / "pronunciation_overrides.json").read_text(encoding="utf-8")) if (Path(entries_path).parent / "pronunciation_overrides.json").exists() else {}
    guard, slots_info, guard_lines, stopped_at = Guard(guard_mode), [], [], None
    from .pausal import Override
    for voice in VOICES:
        policy = PronunciationPolicy(POLICIES[voice], {k: Override(v["lexical_text"], v["text_sent"], tuple(v["letter_map"]) if v.get("letter_map") else None) for k, v in overrides.get(voice, {}).items()})
        for i in range(0, len(entries), batch_size):
            batch = entries[i:i + batch_size]; produced = [produce_slot({**e}, voice, policy, faults, out) for e in batch if e["entry_id"] not in (blocked or set())]
            slots_info += produced
            iso = [p for p in produced if not p["blocked"] and p["chosen"]["gate"].status == "HOLD"]
            classes = {}
            for p in iso:
                for c in p["chosen"]["gate"].classes: classes[c] = classes.get(c, 0) + 1
            tw = sum(1 for p in iso if "AUDIBLE_TANWEEN" in p["chosen"]["gate"].hard)
            decision = guard.check(BatchReport(f"{voice}-batch-{i // batch_size + 1:02d}", voice, len(produced), len(iso), tw, classes))
            guard_lines.append(decision.line)
            if decision.stop: stopped_at = decision.line; break
        if stopped_at: break
    log = ReviewLog(out / "review_log.jsonl")
    if reviews_path:                                              # decisions refer to (entry_id, voice, attempt); resolved to the sha256 of the CURRENT take at import time
        cur = {(s["entry_id"], s["voice"]): s for s in slots_info if not s["blocked"]}
        for line in Path(reviews_path).read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            r = json.loads(line); s = cur.get((r["entry_id"], r["voice"]))
            if s: log.append(r["entry_id"], r["voice"], s["chosen"]["sha256"], r["decision"], r.get("note", ""), r.get("reviewer", "reviewer-1"))
    slots = [delivery.Slot(s["entry_id"], s["voice"], VOICES[s["voice"]].gender, s["chosen"]["sha256"] if not s["blocked"] else None, s["chosen"]["path"] if not s["blocked"] else None,
                           s["chosen"]["gate"].status if not s["blocked"] else None, s["blocked"], s.get("text_sent", "")) for s in slots_info]
    for e in entries:                                             # entries never produced (blocked set / guard stop) still appear as NO_RECORDING / BLOCKED
        for v in VOICES:
            if not any(s.entry_id == e["entry_id"] and s.voice == v for s in slots): slots.append(delivery.Slot(e["entry_id"], v, VOICES[v].gender, None, None, None, e["entry_id"] in (blocked or set())))
    lexical, senses = {e["entry_id"]: e["lemma"] for e in entries}, {e["entry_id"]: e.get("sense", "") for e in entries}
    result = delivery.build(slots, log.current(), lexical)
    tasks = delivery.platform_tasks(result, lexical, senses)
    delivery.write_csv(out / "delivery_two_voice.csv", result["pairs"]); delivery.write_csv(out / "incomplete_words.csv", result["incomplete"]); delivery.write_csv(out / "platform_tasks.csv", tasks)
    summary = {k: result[k] for k in ("words", "two_voice_words", "incomplete_words", "recordings_in_delivery", "counts_by_category", "human_accepted", "auto_ready_not_human_approved")}
    summary.update(guard_mode=guard_mode, guard_stopped=stopped_at, guard_log=guard_lines, note="AUTO_READY is production-complete, NOT human-approved.")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return summary
