from dataclasses import dataclass
from pathlib import Path
import os

@dataclass(frozen=True)
class Config:
    provider: str = "mock"
    batch_size: int = 2
    max_attempts: int = 2
    artifact_dir: Path = Path("artifacts")
    state_db: Path = Path("artifacts/pipeline.db")

    @classmethod
    def from_env(cls) -> "Config":
        provider = os.getenv("TTS_PROVIDER", "mock")
        if provider != "mock":
            raise ValueError("This public repository intentionally supports TTS_PROVIDER=mock only")
        batch_size = int(os.getenv("BATCH_SIZE", "2"))
        attempts = int(os.getenv("MAX_ATTEMPTS", "2"))
        if batch_size < 1 or attempts < 1:
            raise ValueError("BATCH_SIZE and MAX_ATTEMPTS must be positive")
        return cls(provider, batch_size, attempts, Path(os.getenv("ARTIFACT_DIR", "artifacts")), Path(os.getenv("STATE_DB", "artifacts/pipeline.db")))

