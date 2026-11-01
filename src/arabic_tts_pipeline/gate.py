"""Rule-based quality gate over judge evidence (illustrative weights; the production gate used the same structure, with its threshold frozen from development data before any hold-out test).
 * HARD faults block a recording at once (audible tanween, 2+ letter differences, technical failure, no judge result).
 * SOFT risks add weighted points; a recording passes only if it has no hard fault and its score is <= MAX_SCORE.
 * PASS_GATE means "no blocking fault found by the available checks" - evidence for a human, NEVER an approval.
 * A word whose every take is HOLD is ISOLATED: kept, never deleted, never retried automatically."""
from dataclasses import dataclass
from .judge import Evidence, LONG_VOWEL_LETTERS
from .pausal import strip_marks, expected_letters

WEIGHTS = {"final_short_vowel_heard": 2, "final_vowel_both_passes": 1, "extra_sounds": 2, "b_final_breath": 1, "ab_conflict": 1, "letter_mismatch_minor": 1}
MAX_SCORE = 2
CLASS_OF = {"AUDIBLE_TANWEEN": "ENDING_VOWEL", "final_short_vowel_heard": "ENDING_VOWEL", "final_vowel_both_passes": "ENDING_VOWEL", "LETTERS_DIFFER": "LETTER", "letter_mismatch_minor": "LETTER", "extra_sounds": "EXTRA_SOUND", "b_final_breath": "STOP_STRENGTH", "ab_conflict": "UNKNOWN", "score>max": "UNKNOWN", "TECHNICAL_FAIL": "TECHNICAL", "NO_JUDGE_RESULT": "TECHNICAL"}

@dataclass(frozen=True)
class GateResult:
    status: str                    # PASS_GATE | HOLD
    hard: tuple[str, ...]
    soft: tuple[str, ...]
    score: int
    classes: tuple[str, ...]

def _distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1): cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

def evaluate(evidence: Evidence | None, lexical_text: str, technical_ok: bool = True, letter_map=None) -> GateResult:
    hard, soft = [], []
    if not technical_ok: hard.append("TECHNICAL_FAIL")
    if evidence is None: hard.append("NO_JUDGE_RESULT")
    else:
        a, b = evidence.a, evidence.b
        if a.final_sound == "nasal_tanween": hard.append("AUDIBLE_TANWEEN")
        dist = _distance(strip_marks(a.heard), expected_letters(lexical_text, letter_map)) if a.heard else 9
        if dist >= 2: hard.append("LETTERS_DIFFER")
        elif dist == 1: soft.append("letter_mismatch_minor")
        ends_long = strip_marks(lexical_text).endswith(LONG_VOWEL_LETTERS)
        if a.final_sound == "short_vowel" and not ends_long: soft.append("final_short_vowel_heard")
        if a.final_sound == "short_vowel" and b.final_vowel_or_tanween and not ends_long: soft.append("final_vowel_both_passes")
        if a.extra_sounds: soft.append("extra_sounds")
        if b.final_breath_or_h and a.final_sound != "breath_or_h": soft.append("b_final_breath")
        if a.final_sound != "short_vowel" and a.final_sound != "nasal_tanween" and b.final_vowel_or_tanween: soft.append("ab_conflict")
    score = sum(WEIGHTS[s] for s in soft)
    reasons = list(hard) + soft + (["score>max"] if not hard and score > MAX_SCORE else [])
    status = "PASS_GATE" if not hard and score <= MAX_SCORE else "HOLD"
    return GateResult(status, tuple(hard), tuple(soft), score, tuple(sorted({CLASS_OF.get(r, "UNKNOWN") for r in reasons})) if status == "HOLD" else ())

def select_per_word(results: dict[str, GateResult]) -> str | None:
    """results: take_id -> GateResult for ONE word. The passing take with the lowest score wins (first on a tie); None = isolated."""
    passing = [(r.score, tid) for tid, r in results.items() if r.status == "PASS_GATE"]
    return min(passing)[1] if passing else None
