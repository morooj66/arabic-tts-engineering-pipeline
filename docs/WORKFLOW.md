# Pipeline Workflow

[← Back to README](../README.md#workflow) · [Architecture](ARCHITECTURE.md) · [Demo](DEMO.md) · [Quality Assurance](QUALITY_ASSURANCE.md)

## Processing sequence

1. `ingest_csv()` validates the `entry_id,text` contract and inserts unseen jobs as `PENDING`.
2. `run()` reads non-terminal work in stable `entry_id` order and slices it into configured batches.
3. `prepare()` normalizes text and reports invalid or undiacritized input without inventing pronunciation.
4. `DeterministicMockTTS.synthesize()` creates a reproducible non-speech tone.
5. `validate_wav()` checks the technical WAV contract.
6. Failures are recorded and retried up to `MAX_ATTEMPTS`; exhausted work becomes `FAILED`.
7. Passing artifacts are written locally and marked `READY_FOR_REVIEW`.
8. The CLI exports a JSONL review queue.
9. A separate import accepts only `APPROVED`, `REJECTED`, or `NEEDS_CORRECTION` for entries currently ready for review.

## Status contract

| Status | Meaning | Terminal for `run()`? |
|---|---|---|
| `PENDING` | Ingested, not yet processed | No |
| `INPUT_INVALID` | Empty or unsupported input | No; visible for correction |
| `LINGUISTIC_REVIEW_REQUIRED` | Arabic text lacks diacritics | No; requires review |
| `RETRYABLE_FAILURE` | Attempt failed and may be retried | No |
| `FAILED` | Configured attempts exhausted | No; visible for recovery |
| `READY_FOR_REVIEW` | Technical QA passed | Yes |
| `APPROVED` | Explicit human approval imported | Yes |
| `REJECTED` | Explicit human rejection imported | No; visible for correction |
| `NEEDS_CORRECTION` | Explicit human correction request imported | No |

Technical validity is deliberately separate from human approval.

