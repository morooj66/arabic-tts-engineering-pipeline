"""A deterministic SIMULATED audio judge with the same two-pass shape as the production judge (pass A: what was heard; pass B: yes/no questions).
It never listens to audio and never calls a provider: evidence is derived from the text that was sent plus a table of INJECTED faults, so the quality gate, guard and delivery logic can be exercised and tested offline.
In the original system this role was played by a multimodal LLM judge whose answers were treated as evidence for a human, never as an approval."""
from dataclasses import dataclass, field
from .pausal import strip_marks, SHADDA, SUKUN

FAULTS = {"tanween", "final_vowel", "letters", "extra_sound", "ab_conflict", "breath"}
LONG_VOWEL_LETTERS = ("ا", "ي", "و", "ى")

@dataclass(frozen=True)
class PassA:
    heard: str                 # transcription-like text of what was "heard"
    final_sound: str           # consonant | short_vowel | long_vowel | nasal_tanween | breath_or_h
    extra_sounds: tuple[str, ...] = ()
    unclear: bool = False

@dataclass(frozen=True)
class PassB:
    final_vowel_or_tanween: bool = False
    final_breath_or_h: bool = False
    sound_before_word: bool = False

@dataclass(frozen=True)
class Evidence:
    a: PassA
    b: PassB
    injected: tuple[str, ...] = field(default_factory=tuple)      # kept for transparency in reports; a real judge has no such field

def _drop_last_letter(text: str) -> str:
    i = len(text)
    while i > 0 and strip_marks(text[i - 1]) == "": i -= 1       # skip trailing marks
    return text[:i - 1] if i > 0 else text

class MockJudge:
    def __init__(self, faults: dict[str, list[str]] | None = None):
        self.faults = faults or {}
        bad = {f for fs in self.faults.values() for f in fs} - FAULTS
        if bad: raise ValueError(f"unknown injected faults: {sorted(bad)}")

    def evaluate(self, entry_id: str, text_sent: str) -> Evidence:
        faults = tuple(self.faults.get(entry_id, ()))
        bare = strip_marks(text_sent)
        final = "long_vowel" if bare.endswith(LONG_VOWEL_LETTERS) else "consonant"
        heard, extra = text_sent, ()
        if "tanween" in faults: final, heard = "nasal_tanween", text_sent + "ٌ"
        if "final_vowel" in faults: final, heard = "short_vowel", text_sent.rstrip(SUKUN) + "َ"
        if "letters" in faults:                                      # two letters differ: the first letter is replaced and the last letter is lost
            heard = heard.replace(bare[0], "س", 1) if bare else heard
            if "tanween" not in faults and len(bare) > 2: heard = _drop_last_letter(heard)
        if "extra_sound" in faults: extra = ("breath@end",)
        if "breath" in faults: final = "breath_or_h"
        a = PassA(heard, final, extra)
        b = PassB(final_vowel_or_tanween=final in ("short_vowel", "nasal_tanween") or "ab_conflict" in faults, final_breath_or_h=final == "breath_or_h")
        return Evidence(a, b, faults)
