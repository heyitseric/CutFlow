from abc import ABC, abstractmethod
from typing import Callable, Optional

from app.models.schemas import MatchResult, TranscriptionResult


class Transcriber(ABC):
    @abstractmethod
    async def transcribe(
        self,
        audio_path: str,
        language: str = "zh",
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> TranscriptionResult:
        """Transcribe an audio file and return word-level timestamps."""
        ...


class Matcher(ABC):
    @abstractmethod
    async def match_segments(
        self,
        script_sentences: list[str],
        transcript_segments: list[dict],
    ) -> list[MatchResult]:
        """Match script sentences to transcript segments, return scored matches."""
        ...
