import logging

from app.config import get_settings
from app.providers.base import Matcher, Transcriber

logger = logging.getLogger(__name__)


def get_transcriber(provider: str = "") -> Transcriber:
    """Get transcriber based on provider config."""
    settings = get_settings()
    provider = provider or settings.CLOUD_PROVIDER

    if provider == "local":
        from app.providers.local.whisper_transcriber import LocalWhisperTranscriber
        return LocalWhisperTranscriber(model_name=settings.WHISPER_MODEL)

    elif provider == "volcengine":
        # Prefer cloud Caption API if credentials are configured
        if settings.VOLCENGINE_CAPTION_APPID and settings.VOLCENGINE_CAPTION_TOKEN:
            from app.providers.cloud.volcengine_caption import (
                VolcengineCaptionTranscriber,
            )
            logger.info("Using Volcengine Caption API for transcription")
            return VolcengineCaptionTranscriber(
                appid=settings.VOLCENGINE_CAPTION_APPID,
                token=settings.VOLCENGINE_CAPTION_TOKEN,
            )

        # Fall back to local Whisper if no caption credentials
        logger.warning(
            "VOLCENGINE_CAPTION_APPID / TOKEN not set, "
            "falling back to local Whisper transcriber"
        )
        try:
            from app.providers.local.whisper_transcriber import LocalWhisperTranscriber
            return LocalWhisperTranscriber(model_name=settings.WHISPER_MODEL)
        except ImportError:
            logger.warning(
                "No local Whisper backend available. "
                "Cloud-only transcription is not supported."
            )
            raise

    else:
        raise ValueError(f"Unknown provider: {provider}")


def get_matcher(provider: str = "") -> Matcher:
    """Get matcher based on provider config."""
    settings = get_settings()
    provider = provider or settings.CLOUD_PROVIDER

    if provider == "local":
        from app.providers.local.rapidfuzz_matcher import RapidFuzzMatcher
        return RapidFuzzMatcher(dictionary_dir=settings.DICTIONARY_DIR)

    elif provider == "volcengine":
        if settings.ARK_API_KEY:
            from app.providers.cloud.volcengine import VolcEngineMatcher
            return VolcEngineMatcher()
        else:
            logger.info("No ARK_API_KEY configured, falling back to local matcher")
            from app.providers.local.rapidfuzz_matcher import RapidFuzzMatcher
            return RapidFuzzMatcher(dictionary_dir=settings.DICTIONARY_DIR)

    else:
        raise ValueError(f"Unknown provider: {provider}")


def get_local_matcher() -> Matcher:
    """Always return local matcher (for hybrid workflows)."""
    settings = get_settings()
    from app.providers.local.rapidfuzz_matcher import RapidFuzzMatcher
    return RapidFuzzMatcher(dictionary_dir=settings.DICTIONARY_DIR)
