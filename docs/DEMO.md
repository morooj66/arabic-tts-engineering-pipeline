# Offline Demo

[← Back to README](../README.md#demo) · [Architecture](ARCHITECTURE.md) · [Workflow](WORKFLOW.md) · [Quality Assurance](QUALITY_ASSURANCE.md)

> **Synthetic Demo Data:** this walkthrough uses the four public fixtures in `examples/sample_entries.csv`. Output WAV files are deterministic tones, not Arabic speech.

## Run

```bash
PYTHONPATH=src python3 -m arabic_tts_pipeline run \
  --input examples/sample_entries.csv
```

Observed result:

```json
{
  "by_status": {
    "READY_FOR_REVIEW": 4
  },
  "paid_api_calls": 0,
  "provider": "mock",
  "total": 4
}
```

## Inspect generated artifacts

```text
artifacts/
├── audio/
│   ├── demo-001.wav
│   ├── demo-002.wav
│   ├── demo-003.wav
│   └── demo-004.wav
├── pipeline.db
└── review_queue.jsonl
```

The WAV files demonstrate deterministic generation, filesystem persistence, checksum capture, and technical validation. They cannot be used to assess Arabic pronunciation, prosody, speaker identity, or speech quality.

## Confirm resumability

Run the same command again. The summary remains unchanged because entries already at `READY_FOR_REVIEW` are terminal for pipeline execution and are not regenerated.

## Test

```bash
python3 -m unittest discover -s tests -v
```

Current documented result: 6 tests passed, using temporary directories and zero network calls.

