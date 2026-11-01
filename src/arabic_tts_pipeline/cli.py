import argparse
import csv
import json
from pathlib import Path
from .config import Config
from .pipeline import Pipeline

def export_review(pipe, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [dict(r) for r in pipe.store.all() if r["status"] == "READY_FOR_REVIEW"]
    path.write_text("\n".join(json.dumps({"entry_id": r["entry_id"], "audio_path": r["audio_path"], "decision": "", "note": ""}, ensure_ascii=False) for r in rows) + ("\n" if rows else ""), encoding="utf-8")

def import_reviews(pipe, path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line); pipe.store.review(row["entry_id"], row["decision"], row.get("note", ""))

def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline Arabic dictionary TTS reference pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run"); run.add_argument("--input", type=Path, required=True)
    review = sub.add_parser("import-reviews"); review.add_argument("--file", type=Path, required=True)
    sub.add_parser("report")
    demo = sub.add_parser("two-voice-demo", help="synthetic two-voice scenario: policy, judge, gate, guard, review log, delivery rules")
    demo.add_argument("--entries", type=Path, default=Path("examples/two_voice_entries.csv")); demo.add_argument("--faults", type=Path, default=Path("examples/judge_faults.json"))
    demo.add_argument("--reviews", type=Path, default=Path("examples/review_decisions.jsonl")); demo.add_argument("--out", type=Path, default=Path("artifacts/two_voice")); demo.add_argument("--guard-mode", choices=["advisory", "strict"], default="advisory")
    args = parser.parse_args(argv)
    if args.command == "two-voice-demo":
        from . import scenario
        print(json.dumps(scenario.run(args.entries, args.faults, args.reviews, args.out, args.guard_mode), ensure_ascii=False, indent=2, sort_keys=True)); return
    pipe = Pipeline(Config.from_env())
    if args.command == "run":
        pipe.ingest_csv(args.input); result = pipe.run(); export_review(pipe, pipe.config.artifact_dir / "review_queue.jsonl")
    elif args.command == "import-reviews": import_reviews(pipe, args.file); result = pipe.summary()
    else: result = pipe.summary()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))

