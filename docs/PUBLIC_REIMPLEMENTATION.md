# Public reimplementation boundary

## Patterns retained

- stable entry identifiers and stateful resume;
- bounded batches and bounded retry attempts (in the reference code the retry is automatic; in the private project a retake was planned and authorized by a person);
- preprocessing before generation;
- technical WAV checks before human review;
- explicit review decisions and non-approval by default;
- persisted events/status and reproducible local tests.

## Reimplemented or simplified

- Real provider adapters were replaced by a deterministic synthetic-tone adapter.
- Production prompts, voice identifiers, model configuration, fingerprints, exceptions, and cost controls are absent.
- The production Arabic policy is represented only by safe Unicode/character checks and a narrow terminal-mark removal example.
- Internal spreadsheets, registries, recordings, reviewer data, and operational identifiers were replaced by four synthetic rows.
- Local SQLite and filesystem artifacts stand in for the internal orchestration and delivery environment.

These boundaries are intentional: the public code demonstrates engineering structure without exposing project assets or implying parity with production speech quality.

## Disclosure policy

Named in this repository because they are public technologies and used in the project: Python, SQLite, n8n, Google Gemini TTS, and the prebuilt voices Charon and Kore. Aggregate result counts are given in [RESULTS.md](RESULTS.md).

Deliberately omitted: the originating organization and project name, real words and meanings, recordings, storage locations, reviewer identities and decisions, secret configuration (hashes, prompts, per-word exception lists, exact gate weights and thresholds) and the original source code. The synthetic gate weights, guard thresholds and judge here are illustrative.

The case study discusses transferable engineering decisions drawn from the project record; it does not claim that this repository's simplified components equal the private ones.
