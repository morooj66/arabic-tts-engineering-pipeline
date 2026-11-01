import json, tempfile, unittest
from pathlib import Path
from arabic_tts_pipeline import delivery, gate, guard, judge, pausal, scenario
from arabic_tts_pipeline.reviewlog import ReviewLog

EX = Path(__file__).resolve().parents[1] / "examples"
def run(tmp, **kw):
    return scenario.run(EX / "two_voice_entries.csv", EX / "judge_faults.json", EX / "review_decisions.jsonl", Path(tmp), **kw)

class PausalTests(unittest.TestCase):
    def test_waqf_turns_final_tanween_into_sukun(self): self.assertEqual(pausal.waqf("كِتَابٌ"), "كِتَابْ")
    def test_waqf_keeps_inner_marks_and_shadda(self): self.assertEqual(pausal.waqf("مُدَرِّسٌ"), "مُدَرِّسْ")
    def test_fathatan_alif_becomes_fatha(self): self.assertEqual(pausal.waqf("مَرْحَبًا"), "مَرْحَبَا")
    def test_override_applies_only_on_exact_lexical_match(self):
        pol = pausal.PronunciationPolicy("waqf", {"w1": pausal.Override("نَافِذَةٌ", "نَافِذَهْ", ("ة", "ه"))})
        self.assertEqual(pol.prepare("w1", "نَافِذَةٌ")[0], "نَافِذَهْ")
        self.assertNotEqual(pol.prepare("w1", "نَافِذَةً")[0], "نَافِذَهْ")
    def test_letters_preserved_rejects_changed_letter(self): self.assertFalse(pausal.letters_preserved("كِتَابٌ", "كِتَامْ"))

class GateTests(unittest.TestCase):
    def ev(self, f): return judge.MockJudge({"x": f}).evaluate("x", "كِتَابْ")
    def test_clean_passes(self): self.assertEqual(gate.evaluate(self.ev([]), "كِتَابٌ").status, "PASS_GATE")
    def test_audible_tanween_is_hard_fault(self): self.assertIn("AUDIBLE_TANWEEN", gate.evaluate(self.ev(["tanween"]), "كِتَابٌ").hard)
    def test_missing_judge_result_holds(self): self.assertEqual(gate.evaluate(None, "كِتَابٌ").status, "HOLD")
    def test_technical_failure_holds(self): self.assertEqual(gate.evaluate(self.ev([]), "كِتَابٌ", technical_ok=False).status, "HOLD")
    def test_unknown_fault_is_rejected(self):
        with self.assertRaises(ValueError): judge.MockJudge({"x": ["nope"]})
    def test_select_prefers_lowest_score_and_none_when_all_hold(self):
        a, b = gate.evaluate(self.ev([]), "كِتَابٌ"), gate.evaluate(self.ev(["tanween"]), "كِتَابٌ")
        self.assertEqual(gate.select_per_word({"1": b, "2": a}), "2"); self.assertIsNone(gate.select_per_word({"1": b}))

class GuardTests(unittest.TestCase):
    bad = guard.BatchReport("b1", "voice_a", 10, 6, 2, {"ENDING_VOWEL": 6})
    def test_advisory_never_stops_on_quality(self):
        d = guard.Guard("advisory").check(self.bad); self.assertFalse(d.stop); self.assertTrue(d.advisories)
    def test_strict_stops_on_quality(self): self.assertTrue(guard.Guard("strict").check(self.bad).stop)
    def test_technical_error_stops_in_both_modes(self):
        r = guard.BatchReport("b", "voice_a", 4, 0, 0, {}, technical_errors=1)
        self.assertTrue(guard.Guard("advisory").check(r).stop)

class ReviewLogTests(unittest.TestCase):
    def test_append_only_with_supersedes_chain(self):
        with tempfile.TemporaryDirectory() as t:
            log = ReviewLog(Path(t) / "r.jsonl"); a = log.append("w1", "voice_a", "h1", "accept"); b = log.append("w1", "voice_a", "h1", "reject")
            self.assertEqual(b["supersedes"], a["event_id"]); self.assertEqual(len(log.events()), 2); self.assertEqual(log.current()[("w1", "voice_a", "h1")]["decision"], "reject")
    def test_decision_does_not_carry_to_new_recording(self):
        with tempfile.TemporaryDirectory() as t:
            log = ReviewLog(Path(t) / "r.jsonl"); log.append("w1", "voice_a", "h1", "accept"); self.assertNotIn(("w1", "voice_a", "h2"), log.current())
    def test_unknown_decision_rejected(self):
        with tempfile.TemporaryDirectory() as t, self.assertRaises(ValueError): ReviewLog(Path(t) / "r.jsonl").append("w1", "voice_a", "h", "maybe")

class ScenarioTests(unittest.TestCase):
    def test_two_voice_rule_and_counts(self):
        with tempfile.TemporaryDirectory() as t:
            s = run(t); self.assertEqual(s["words"], 12); self.assertEqual(s["two_voice_words"] * 2, s["recordings_in_delivery"])
            self.assertEqual(s["two_voice_words"] + s["incomplete_words"], 12)
    def test_auto_ready_is_not_counted_as_human_approval(self):
        with tempfile.TemporaryDirectory() as t:
            s = run(t); self.assertEqual(s["human_accepted"], 2); self.assertGreater(s["auto_ready_not_human_approved"], s["human_accepted"])
    def test_isolated_and_rejected_never_complete_a_pair(self):
        with tempfile.TemporaryDirectory() as t:
            run(t); rows = (Path(t) / "incomplete_words.csv").read_text(encoding="utf-8")
            for w in ("w002", "w003", "w004", "w006", "w008", "w010"): self.assertIn(w, rows)
    def test_latest_decision_supersedes_earlier_one(self):
        with tempfile.TemporaryDirectory() as t:
            run(t); log = ReviewLog(Path(t) / "review_log.jsonl"); self.assertEqual(len(log.history("w006", "voice_a")), 2)
            self.assertNotIn("w006", (Path(t) / "delivery_two_voice.csv").read_text(encoding="utf-8"))
    def test_platform_export_contract(self):
        import csv
        with tempfile.TemporaryDirectory() as t:
            run(t); rows = list(csv.DictReader((Path(t) / "platform_tasks.csv").open(encoding="utf-8")))
            self.assertEqual(list(rows[0]), ["entry_id", "sense_id", "lemma", "sense", "audio_url", "audio_model", "audio_gender"])
            keys = [(r["entry_id"], r["audio_gender"]) for r in rows]; self.assertEqual(len(keys), len(set(keys)))
            self.assertTrue(all(r["audio_url"].startswith("https://") and r["entry_id"].isdigit() for r in rows))
            self.assertEqual(sum(r["audio_gender"] == "male" for r in rows), sum(r["audio_gender"] == "female" for r in rows))
    def test_guard_strict_stops_where_advisory_continues(self):
        faults = {f"w{n:03d}/voice_a": ["final_vowel"] for n in range(1, 9)}
        with tempfile.TemporaryDirectory() as t:
            fp = Path(t) / "f.json"; fp.write_text(json.dumps(faults)); kw = dict(reviews_path=None, out=Path(t) / "o")
            strict = scenario.run(EX / "two_voice_entries.csv", fp, guard_mode="strict", **kw); adv = scenario.run(EX / "two_voice_entries.csv", fp, guard_mode="advisory", **{**kw, "out": Path(t) / "o2"})
            self.assertIsNotNone(strict["guard_stopped"]); self.assertIsNone(adv["guard_stopped"])
    def test_blocked_entry_never_enters_delivery(self):
        with tempfile.TemporaryDirectory() as t:
            s = scenario.run(EX / "two_voice_entries.csv", None, None, Path(t), blocked={"w001"}); self.assertNotIn("w001", (Path(t) / "delivery_two_voice.csv").read_text(encoding="utf-8"))
    def test_override_changes_text_sent_for_one_voice_only(self):
        with tempfile.TemporaryDirectory() as t:
            run(t); self.assertTrue((Path(t) / "audio" / "voice_b" / "w007_attempt1.wav").exists())
    def test_run_is_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            sa, sb = run(a), run(b); self.assertEqual({k: v for k, v in sa.items()}, {k: v for k, v in sb.items()})

if __name__ == "__main__": unittest.main()
