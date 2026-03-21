import asyncio
import logging
from typing import Callable, Optional

from app.models.schemas import (
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionWord,
)
from app.providers.base import Transcriber

logger = logging.getLogger(__name__)


def _get_whisper_backend() -> str:
    """Detect which Whisper backend is available."""
    try:
        import whisperx  # noqa: F401
        return "whisperx"
    except ImportError:
        pass

    try:
        import stable_whisper  # noqa: F401
        return "stable_ts"
    except ImportError:
        pass

    try:
        import whisper  # noqa: F401
        return "openai_whisper"
    except ImportError:
        pass

    return "none"


# Module-level model cache for singleton behaviour across instances.
_cached_models: dict[str, object] = {}


class LocalWhisperTranscriber(Transcriber):
    def __init__(self, model_name: str = "large-v3", device: str = "auto"):
        self.model_name = model_name
        self.device = device
        self.backend = _get_whisper_backend()
        # Re-use a previously loaded model for the same (backend, model_name)
        cache_key = f"{self.backend}:{model_name}"
        self._model = _cached_models.get(cache_key)

    def _ensure_model(self):
        if self._model is not None:
            return

        cache_key = f"{self.backend}:{self.model_name}"

        if self.backend == "whisperx":
            import whisperx
            import torch

            device = self.device
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            self._model = whisperx.load_model(
                self.model_name, device, compute_type=compute_type
            )
            self._device = device

        elif self.backend == "stable_ts":
            import stable_whisper

            try:
                import mlx_whisper  # noqa: F401
                self._model = stable_whisper.load_model(self.model_name, backend="mlx")
            except ImportError:
                self._model = stable_whisper.load_model(self.model_name)

        elif self.backend == "openai_whisper":
            import whisper

            self._model = whisper.load_model(self.model_name)

        else:
            raise ImportError(
                "No Whisper backend found. Install one of:\n"
                "  pip install whisperx          (recommended, GPU)\n"
                "  pip install stable-ts mlx-whisper  (Apple Silicon)\n"
                "  pip install openai-whisper    (CPU fallback)\n"
            )

        # Store in module-level cache so subsequent instances reuse it
        _cached_models[cache_key] = self._model
        logger.info(f"Model cached: {cache_key}")

    async def transcribe(
        self,
        audio_path: str,
        language: str = "zh",
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> TranscriptionResult:
        self._ensure_model()

        if progress_callback:
            progress_callback(0.1, "Loading audio...")

        result = await asyncio.to_thread(
            self._transcribe_sync, audio_path, language, progress_callback
        )
        return result

    def _transcribe_sync(
        self,
        audio_path: str,
        language: str,
        progress_callback: Optional[Callable[[float, str], None]],
    ) -> TranscriptionResult:
        if self.backend == "whisperx":
            return self._transcribe_whisperx(audio_path, language, progress_callback)
        elif self.backend == "stable_ts":
            return self._transcribe_stable_ts(audio_path, language, progress_callback)
        elif self.backend == "openai_whisper":
            return self._transcribe_openai(audio_path, language, progress_callback)
        else:
            raise ImportError("No Whisper backend available.")

    def _transcribe_whisperx(
        self, audio_path: str, language: str, progress_callback
    ) -> TranscriptionResult:
        import whisperx

        if progress_callback:
            progress_callback(0.2, "Transcribing with WhisperX...")

        audio = whisperx.load_audio(audio_path)
        result = self._model.transcribe(audio, batch_size=16, language=language)

        if progress_callback:
            progress_callback(0.6, "Aligning words...")

        model_a, metadata = whisperx.load_align_model(
            language_code=language, device=self._device
        )
        result = whisperx.align(
            result["segments"], model_a, metadata, audio, self._device,
            return_char_alignments=False,
        )

        if progress_callback:
            progress_callback(0.9, "Building result...")

        return self._convert_whisperx_result(result, audio_path)

    def _transcribe_stable_ts(
        self, audio_path: str, language: str, progress_callback
    ) -> TranscriptionResult:
        if progress_callback:
            progress_callback(0.2, "Transcribing with stable-ts...")

        result = self._model.transcribe(audio_path, language=language)

        if progress_callback:
            progress_callback(0.9, "Building result...")

        return self._convert_stable_ts_result(result)

    def _transcribe_openai(
        self, audio_path: str, language: str, progress_callback
    ) -> TranscriptionResult:
        import whisper

        if progress_callback:
            progress_callback(0.2, "Transcribing with openai-whisper...")

        result = whisper.transcribe(self._model, audio_path, language=language)

        if progress_callback:
            progress_callback(0.9, "Building result...")

        return self._convert_openai_result(result)

    def _convert_whisperx_result(self, result: dict, audio_path: str) -> TranscriptionResult:
        segments = []
        total_duration = 0.0

        for seg in result.get("segments", []):
            words = []
            for w in seg.get("words", []):
                word = TranscriptionWord(
                    word=w.get("word", ""),
                    start=w.get("start", 0.0),
                    end=w.get("end", 0.0),
                    confidence=w.get("score", 1.0),
                )
                words.append(word)

            segment = TranscriptionSegment(
                text=seg.get("text", ""),
                start=seg.get("start", 0.0),
                end=seg.get("end", 0.0),
                words=words,
            )
            segments.append(segment)
            total_duration = max(total_duration, seg.get("end", 0.0))

        return TranscriptionResult(
            segments=segments,
            language=result.get("language", "zh"),
            duration=total_duration,
        )

    def _convert_stable_ts_result(self, result) -> TranscriptionResult:
        segments = []
        total_duration = 0.0

        for seg in result.segments:
            words = []
            for w in seg.words:
                word = TranscriptionWord(
                    word=w.word.strip(),
                    start=w.start,
                    end=w.end,
                    confidence=getattr(w, "probability", 1.0),
                )
                words.append(word)

            segment = TranscriptionSegment(
                text=seg.text.strip(),
                start=seg.start,
                end=seg.end,
                words=words,
            )
            segments.append(segment)
            total_duration = max(total_duration, seg.end)

        return TranscriptionResult(
            segments=segments,
            language="zh",
            duration=total_duration,
        )

    def _convert_openai_result(self, result: dict) -> TranscriptionResult:
        segments = []
        total_duration = 0.0

        for seg in result.get("segments", []):
            words = []
            for w in seg.get("words", []):
                word = TranscriptionWord(
                    word=w.get("word", "").strip(),
                    start=w.get("start", 0.0),
                    end=w.get("end", 0.0),
                    confidence=w.get("probability", 1.0),
                )
                words.append(word)

            segment = TranscriptionSegment(
                text=seg.get("text", "").strip(),
                start=seg.get("start", 0.0),
                end=seg.get("end", 0.0),
                words=words,
            )
            segments.append(segment)
            total_duration = max(total_duration, seg.get("end", 0.0))

        return TranscriptionResult(
            segments=segments,
            language=result.get("language", "zh"),
            duration=total_duration,
        )
