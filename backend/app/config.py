import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Whisper settings
    WHISPER_MODEL: str = "large-v3"
    WHISPER_LANGUAGE: str = "zh"

    # Buffer settings
    BUFFER_DURATION: float = 0.15

    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD: int = 85
    MEDIUM_CONFIDENCE_THRESHOLD: int = 65

    # Matching settings
    MATCH_WINDOW_TOLERANCE: float = 0.4

    # Frame rate
    DEFAULT_FRAME_RATE: float = 29.97

    # Long audio chunking
    LONG_AUDIO_CHUNK_MINUTES: int = 10

    # Pause thresholds (seconds)
    PAUSE_BREATH_THRESHOLD: float = 0.3
    PAUSE_NATURAL_THRESHOLD: float = 0.8
    PAUSE_THINKING_THRESHOLD: float = 2.0
    PAUSE_SHORTEN_TARGET: float = 0.5

    # Cloud provider settings
    ARK_API_KEY: str = ""
    CLOUD_PROVIDER: str = "volcengine"
    CLOUD_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/coding/v3"
    CLOUD_MODEL: str = "doubao-seed-2.0-lite"

    # Volcengine Caption API (cloud transcription)
    VOLCENGINE_CAPTION_APPID: str = ""
    VOLCENGINE_CAPTION_TOKEN: str = ""
    VOLCENGINE_CAPTION_BOOSTING_TABLE_ID: str = ""
    VOLCENGINE_CAPTION_CORRECT_TABLE_ID: str = ""

    # Data directories
    DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"
    UPLOAD_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "uploads"
    OUTPUT_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "outputs"
    DICTIONARY_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "dictionary"

    model_config = {
        "env_file": str(Path(__file__).resolve().parent.parent.parent / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        # Ensure directories exist
        _settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        _settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        _settings.DICTIONARY_DIR.mkdir(parents=True, exist_ok=True)
    return _settings
