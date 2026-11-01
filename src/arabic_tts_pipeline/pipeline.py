import csv
import json
from hashlib import sha256
from pathlib import Path
from .audio import DeterministicMockTTS, validate_wav
from .config import Config
from .pausal import letters_preserved
from .preprocess import prepare
from .state import StateStore

class Pipeline:
    def __init__(self, config: Config, synth=None, text_policy=None):
        self.config = config; self.store = StateStore(config.state_db); self.synth = synth or DeterministicMockTTS(); self.text_policy = text_policy          # optional PronunciationPolicy; None keeps the original single-policy behaviour

    def ingest_csv(self, path: Path):
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if not row.get("entry_id") or row.get("text") is None: raise ValueError("CSV requires entry_id,text")
                self.store.upsert_source(row["entry_id"], row["text"])

    def run(self):
        rows = list(self.store.pending())
        for start in range(0, len(rows), self.config.batch_size):
            for row in rows[start:start+self.config.batch_size]: self._process(row)
        return self.summary()

    def _process(self, row):
        try:
            prepared = prepare(row["source_text"])
        except ValueError as exc:
            self.store.update(row["entry_id"], "INPUT_INVALID", error=str(exc)); return
        if prepared.warnings:
            self.store.update(row["entry_id"], "LINGUISTIC_REVIEW_REQUIRED", spoken_text=prepared.spoken_text, error=",".join(prepared.warnings)); return
        spoken = prepared.spoken_text
        if self.text_policy is not None:
            spoken, rule = self.text_policy.prepare(row["entry_id"], row["source_text"])
            if not letters_preserved(row["source_text"], spoken, self.text_policy.letter_map_for(row["entry_id"], row["source_text"])):
                self.store.update(row["entry_id"], "INPUT_INVALID", error="TEXT_POLICY_CHANGED_LETTERS"); return
        last = None
        for attempt in range(row["attempts"] + 1, self.config.max_attempts + 1):
            try:
                audio = self.synth.synthesize(spoken); quality = validate_wav(audio)
                if not quality.valid: raise ValueError("AUDIO_VALIDATION_FAILED:" + ",".join(quality.errors))
                out = self.config.artifact_dir / "audio" / f"{row['entry_id']}.wav"; out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(audio)
                q = {**quality.__dict__, "sha256": sha256(audio).hexdigest()}
                self.store.update(row["entry_id"], "READY_FOR_REVIEW", spoken_text=spoken, attempts=attempt, audio_path=str(out), quality_json=json.dumps(q), error=None); return
            except Exception as exc:
                last = str(exc); self.store.update(row["entry_id"], "RETRYABLE_FAILURE", spoken_text=spoken, attempts=attempt, error=last)
        self.store.update(row["entry_id"], "FAILED", error=last)

    def summary(self):
        counts = {}; rows = self.store.all()
        for row in rows: counts[row["status"]] = counts.get(row["status"], 0) + 1
        return {"total": len(rows), "by_status": counts, "paid_api_calls": 0, "provider": "mock"}

