import logging
from typing import Callable, Optional

from app.config import get_settings
from app.models.schemas import TranscriptionResult
from app.providers.base import Transcriber
from app.services.dictionary import DictionaryService

logger = logging.getLogger(__name__)


class TranscriptionService:
    def __init__(
        self,
        transcriber: Transcriber,
        dictionary_service: Optional[DictionaryService] = None,
    ):
        self.transcriber = transcriber
        self.dictionary_service = dictionary_service

    async def transcribe(
        self,
        audio_path: str,
        language: str = "zh",
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> TranscriptionResult:
        """
        Run full transcription pipeline:
        1. Transcribe audio with selected provider
        2. Apply dictionary corrections
        3. Optionally use cloud for correction
        """
        settings = get_settings()

        # Step 1: Transcribe
        result = await self.transcriber.transcribe(
            audio_path, language, progress_callback
        )

        # Step 2: Apply dictionary corrections
        if self.dictionary_service:
            result = self._apply_dictionary_corrections(result)

        # Step 3: Cloud correction if configured
        if settings.CLOUD_PROVIDER == "volcengine" and settings.ARK_API_KEY:
            try:
                from app.providers.cloud.volcengine import VolcEngineTranscriber

                cloud = VolcEngineTranscriber()
                result = await cloud.correct_transcription(result)
                if progress_callback:
                    progress_callback(0.95, "Cloud correction applied")
            except Exception as e:
                logger.warning(f"Cloud correction skipped: {e}")

        if progress_callback:
            progress_callback(1.0, "Transcription complete")

        return result

    def _apply_dictionary_corrections(
        self, result: TranscriptionResult
    ) -> TranscriptionResult:
        """Apply dictionary word corrections to transcription segments."""
        if not self.dictionary_service:
            return result

        dict_data = self.dictionary_service.load()
        if not dict_data.entries:
            return result

        correction_map = {
            entry.wrong: entry.correct for entry in dict_data.entries
        }

        for segment in result.segments:
            for wrong, correct in correction_map.items():
                if wrong in segment.text:
                    segment.text = segment.text.replace(wrong, correct)
                    # Update word-level if applicable
                    for word in segment.words:
                        if wrong in word.word:
                            word.word = word.word.replace(wrong, correct)
                    # Track frequency
                    self.dictionary_service.increment_frequency(wrong)

        return result
