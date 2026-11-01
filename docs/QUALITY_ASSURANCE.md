# Quality assurance

The automated gate verifies RIFF/WAV readability, mono 16-bit PCM at 24 kHz, duration from 0.15 to 15 seconds, minimum RMS energy, and excessive clipping. It records a SHA-256 checksum with the result.

These checks detect technical corruption; they do not establish correct pronunciation, speaker identity, naturalness, completeness, or suitability. Valid audio moves only to `READY_FOR_REVIEW`. Human approval is a separate state transition and cannot be inferred from isolation, generation success, or a passing WAV check.

Tests cover pausal preprocessing, deterministic audio validation, idempotent reruns, linguistic-review routing, and the approval gate. They use temporary directories and make no network calls.


## Test scope
32 offline tests: 6 for the single-voice pipeline and 26 for the two-voice layer (pausal policy, gate, guard, review log, delivery rules, platform export contract, determinism). `make test` runs them with no network and no API key.
