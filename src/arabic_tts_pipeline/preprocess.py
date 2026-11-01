import re
import unicodedata
from dataclasses import dataclass

ARABIC = re.compile(r"^[\u0600-\u06ff ]+$")
DIACRITICS = re.compile(r"[\u064b-\u0652]")
FINAL_INFLECTION = re.compile(r"[\u064b-\u0650]+$")

@dataclass(frozen=True)
class PreparedText:
    original: str
    normalized: str
    spoken_text: str
    warnings: tuple[str, ...]

def prepare(text: str) -> PreparedText:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("EMPTY_TEXT")
    normalized = unicodedata.normalize("NFC", " ".join(text.split())).replace("ـ", "")
    if not ARABIC.fullmatch(normalized):
        raise ValueError("NON_ARABIC_CHARACTER")
    warnings = []
    if not DIACRITICS.search(normalized):
        warnings.append("NO_DIACRITICS_REVIEW_REQUIRED")
    # Public simplification of pausal handling: remove only terminal case/tanween marks.
    spoken = FINAL_INFLECTION.sub("", normalized)
    return PreparedText(text, normalized, spoken, tuple(warnings))

