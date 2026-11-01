from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import math
import struct
import wave

@dataclass(frozen=True)
class AudioQuality:
    valid: bool
    duration_seconds: float
    sample_rate: int
    channels: int
    sample_width: int
    peak: int
    rms: float
    errors: tuple[str, ...]

class DeterministicMockTTS:
    """Creates a synthetic tone. It is not speech and never calls a provider."""
    def __init__(self, base_hz: int = 300, spread_hz: int = 500):
        self.base_hz, self.spread_hz = base_hz, spread_hz          # defaults reproduce the original single-voice tones

    def synthesize(self, text: str) -> bytes:
        digest = sha256(text.encode("utf-8")).digest()
        sample_rate, duration = 24000, 0.35 + (digest[0] % 20) / 100
        frequency = self.base_hz + int.from_bytes(digest[1:3], "big") % self.spread_hz
        count = int(sample_rate * duration)
        pcm = bytearray()
        for i in range(count):
            fade = min(1.0, i / 300, (count - i) / 300)
            value = int(6000 * fade * math.sin(2 * math.pi * frequency * i / sample_rate))
            pcm.extend(struct.pack("<h", value))
        out = BytesIO()
        with wave.open(out, "wb") as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sample_rate); wav.writeframes(pcm)
        return out.getvalue()

def validate_wav(data: bytes) -> AudioQuality:
    errors = []
    try:
        with wave.open(BytesIO(data), "rb") as wav:
            channels, width, rate, frames = wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()
            raw = wav.readframes(frames)
    except (wave.Error, EOFError):
        return AudioQuality(False, 0, 0, 0, 0, 0, 0, ("INVALID_WAV",))
    duration = frames / rate if rate else 0
    if (channels, width, rate) != (1, 2, 24000): errors.append("UNEXPECTED_FORMAT")
    if not 0.15 <= duration <= 15: errors.append("DURATION_OUT_OF_RANGE")
    samples = struct.unpack(f"<{len(raw)//2}h", raw[:len(raw)//2*2]) if raw else ()
    peak = max((abs(x) for x in samples), default=0)
    rms = math.sqrt(sum(x*x for x in samples) / len(samples)) if samples else 0
    if rms < 58: errors.append("SILENT_AUDIO")
    if samples and sum(abs(x) >= 32760 for x in samples) / len(samples) > 0.005: errors.append("EXCESSIVE_CLIPPING")
    return AudioQuality(not errors, duration, rate, channels, width, peak, rms, tuple(errors))

