"""Two synthetic voice slots. They differ only by the base pitch of the deterministic tone, so a pair of recordings per entry can be produced, judged and delivered offline.
The names are neutral on purpose: in the original production system the two slots were two different provider voices (one male, one female); here nothing is speech."""
from dataclasses import dataclass
from .audio import DeterministicMockTTS

@dataclass(frozen=True)
class VoiceProfile:
    voice_id: str
    gender: str            # delivery column: "male" or "female"
    base_hz: int

VOICES = {
    "voice_a": VoiceProfile("voice_a", "male", 170),
    "voice_b": VoiceProfile("voice_b", "female", 330),
}

def synth_for(voice_id: str) -> DeterministicMockTTS:
    profile = VOICES[voice_id]
    return DeterministicMockTTS(base_hz=profile.base_hz, spread_hz=60)
