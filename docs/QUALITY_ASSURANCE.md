# Quality assurance

The automated gate verifies RIFF/WAV readability, mono 16-bit PCM at 24 kHz, duration from 0.15 to 15 seconds, minimum RMS energy, and excessive clipping. It records a SHA-256 checksum with the result.

These checks detect technical corruption; they do not establish correct pronunciation, speaker identity, naturalness, completeness, or suitability. Valid audio moves only to `READY_FOR_REVIEW`. Human approval is a separate state transition and cannot be inferred from isolation, generation success, or a passing WAV check.

Tests cover pausal preprocessing, deterministic audio validation, idempotent reruns, linguistic-review routing, and the approval gate. They use temporary directories and make no network calls.


## Test scope
34 Python tests (6 single-voice pipeline, 26 two-voice layer, 2 parity checks) plus 9 JavaScript tests for the interactive explorer's rule engine. A parity test checks the JavaScript gate against the Python gate on every one- and two-fault combination. `make test` runs them with no network and no API key.
