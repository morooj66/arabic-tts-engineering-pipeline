"""Pronunciation-text policies for Arabic dictionary entries (pure functions, no I/O).

Two policies exist because two voices were produced differently in the original system:
  * "waqf"     - the text sent to the TTS describes the PAUSAL form of the END of the entry only
                 (final short vowel / tanween -> sukun; written fathatan + alif -> plain fatha + alif).
  * "verbatim" - the lexical text is sent unchanged.
Per-word overrides are the only way to deviate, and they are deliberately narrow: an override applies to ONE entry id, ONE voice and only when the lexical text equals the recorded `lexical_text` exactly.
The lexical (dictionary) text is never modified; only the text sent to the provider can differ.
Inner letters, inner vowels and every shadda are never touched by the waqf policy."""
from dataclasses import dataclass, field
import re
import unicodedata

FATHATAN, DAMMATAN, KASRATAN, FATHA, DAMMA, KASRA, SHADDA, SUKUN = "ً", "ٌ", "ٍ", "َ", "ُ", "ِ", "ّ", "ْ"
TA_MARBUTA, HA, ALIF = "ة", "ه", "ا"
_TAIL = re.compile(r"[ً-ْ]+$")
_MARKS = re.compile(r"[ً-ْٰ]")

def strip_marks(text: str) -> str:
    return _MARKS.sub("", unicodedata.normalize("NFC", text))

def waqf(text: str) -> str:
    """Pausal form of the end of `text` (see module docstring)."""
    text = unicodedata.normalize("NFC", text)
    if text.endswith(FATHATAN + ALIF): return text[:-2] + FATHA + ALIF          # written fathatan + alif -> plain fatha + alif
    m = _TAIL.search(text)
    if not m: return text
    head, tail = text[:m.start()], m.group()
    if tail == SUKUN or tail == SHADDA or tail == SHADDA + SUKUN: return text
    if FATHATAN in tail and head.endswith(ALIF): return head + tail.replace(FATHATAN, FATHA)          # "...bً" + alif -> "...b" + fatha + alif
    keep = SHADDA if SHADDA in tail else ""
    if any(c in tail for c in (DAMMATAN, KASRATAN, FATHATAN, FATHA, DAMMA, KASRA)): return head + keep + SUKUN
    return text

def silent_ha(text: str) -> str | None:
    """Final ta marbuta -> ha + sukun (the written form of a silent 'h' at waqf). Returns None when the entry does not end in a bare ta marbuta."""
    return text[:-1] + HA + SUKUN if text.endswith(TA_MARBUTA) else None

@dataclass(frozen=True)
class Override:
    lexical_text: str                  # must equal the entry's lexical text exactly
    text_sent: str                     # what is sent to the provider for this voice
    letter_map: tuple[str, str] | None = None     # e.g. (TA_MARBUTA, HA): the ONE letter substitution allowed when comparing letters

@dataclass
class PronunciationPolicy:
    mode: str = "waqf"
    overrides: dict[str, Override] = field(default_factory=dict)       # entry_id -> Override (one voice's policy object)

    def letter_map_for(self, entry_id: str, lexical_text: str):
        ov = self.overrides.get(entry_id)
        return ov.letter_map if ov and ov.lexical_text == unicodedata.normalize("NFC", lexical_text) else None

    def prepare(self, entry_id: str, lexical_text: str) -> tuple[str, str]:
        """Returns (text_sent, rule). The lexical text is never changed."""
        ov = self.overrides.get(entry_id)
        if ov and ov.lexical_text == unicodedata.normalize("NFC", lexical_text): return ov.text_sent, f"override:{entry_id}"
        if self.mode == "verbatim": return lexical_text, "verbatim"
        if self.mode == "waqf":
            sent = waqf(lexical_text); return sent, ("waqf" if sent != unicodedata.normalize("NFC", lexical_text) else "waqf:unchanged")
        raise ValueError(f"unknown mode: {self.mode}")

def expected_letters(lexical_text: str, letter_map: tuple[str, str] | None = None) -> str:
    """Letters (no marks) the sent text must contain. Without an override this is the lexical letters; an override may map ONE letter (ta marbuta -> ha)."""
    base = strip_marks(lexical_text)
    return base.replace(*letter_map) if letter_map else base

def letters_preserved(lexical_text: str, text_sent: str, letter_map: tuple[str, str] | None = None) -> bool:
    """Batch-level safety check: only marks may differ between the lexical text and the text sent (plus the one mapped letter of an override)."""
    return strip_marks(text_sent) == expected_letters(lexical_text, letter_map)
