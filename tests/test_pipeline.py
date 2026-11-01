import csv
import json
import tempfile
import unittest
from pathlib import Path
from arabic_tts_pipeline.audio import DeterministicMockTTS, validate_wav
from arabic_tts_pipeline.config import Config
from arabic_tts_pipeline.pipeline import Pipeline
from arabic_tts_pipeline.preprocess import prepare

class PipelineTests(unittest.TestCase):
    def test_preprocess_pausal_simplification(self):
        item = prepare("رِيَاضٌ")
        self.assertEqual(item.spoken_text, "رِيَاض")

    def test_mock_audio_passes_quality_gate(self):
        self.assertTrue(validate_wav(DeterministicMockTTS().synthesize("مَرْحَبًا")).valid)

    def test_pipeline_and_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / "input.csv"
            source.write_text("entry_id,text\na,مَرْحَبًا\nb,رِيَاضٌ\n", encoding="utf-8")
            cfg = Config(artifact_dir=root / "artifacts", state_db=root / "state.db")
            pipe = Pipeline(cfg); pipe.ingest_csv(source)
            first = pipe.run(); second = pipe.run()
            self.assertEqual(first["by_status"], {"READY_FOR_REVIEW": 2})
            self.assertEqual(second, first)
            self.assertEqual(first["paid_api_calls"], 0)

    def test_undiacritized_text_is_routed_to_linguistic_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / "input.csv"; source.write_text("entry_id,text\na,رياض\n", encoding="utf-8")
            pipe = Pipeline(Config(artifact_dir=root / "a", state_db=root / "s.db")); pipe.ingest_csv(source); result = pipe.run()
            self.assertEqual(result["by_status"], {"LINGUISTIC_REVIEW_REQUIRED": 1})

    def test_review_requires_ready_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); pipe = Pipeline(Config(artifact_dir=root / "a", state_db=root / "s.db"))
            pipe.store.upsert_source("x", "رياض")
            with self.assertRaisesRegex(ValueError, "ENTRY_NOT_READY"):
                pipe.store.review("x", "APPROVED")

    def test_human_approval_is_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / "input.csv"; source.write_text("entry_id,text\na,مَرْحَبًا\n", encoding="utf-8")
            pipe = Pipeline(Config(artifact_dir=root / "a", state_db=root / "s.db")); pipe.ingest_csv(source); pipe.run()
            self.assertEqual(pipe.store.row("a")["status"], "READY_FOR_REVIEW")
            pipe.store.review("a", "APPROVED", "synthetic fixture")
            self.assertEqual(pipe.store.row("a")["status"], "APPROVED")

if __name__ == "__main__": unittest.main()

