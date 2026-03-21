import logging
from typing import Optional

from app.config import get_settings
from app.models.schemas import (
    PauseAction,
    PauseSegment,
    PauseType,
    ScriptSentence,
    TranscriptionResult,
)

logger = logging.getLogger(__name__)


def _classify_pause(duration: float) -> PauseType:
    """Classify pause by duration."""
    settings = get_settings()
    if duration < settings.PAUSE_BREATH_THRESHOLD:
        return PauseType.BREATH
    elif duration < settings.PAUSE_NATURAL_THRESHOLD:
        return PauseType.NATURAL
    elif duration < settings.PAUSE_THINKING_THRESHOLD:
        return PauseType.THINKING
    return PauseType.LONG


def _recommend_action(
    pause_type: PauseType,
    is_section_boundary: bool,
) -> PauseAction:
    """Recommend action based on pause type and context."""
    if pause_type == PauseType.BREATH:
        return PauseAction.REMOVE

    if pause_type == PauseType.NATURAL:
        if is_section_boundary:
            return PauseAction.KEEP
        return PauseAction.KEEP

    if pause_type == PauseType.THINKING:
        if is_section_boundary:
            return PauseAction.SHORTEN
        return PauseAction.SHORTEN

    # LONG pause
    if is_section_boundary:
        return PauseAction.SHORTEN
    return PauseAction.REMOVE


def detect_pauses(
    transcription: TranscriptionResult,
    script_sentences: Optional[list[ScriptSentence]] = None,
) -> list[PauseSegment]:
    """
    Identify pauses between words using word-level timestamps.

    Classifies each gap as:
    - breath: < 0.3s
    - natural: 0.3s - 0.8s
    - thinking: 0.8s - 2.0s
    - long: > 2.0s

    Context-aware: pauses near paragraph boundaries lean toward "keep".
    """
    pauses: list[PauseSegment] = []

    # Collect all words in order
    all_words = []
    for seg in transcription.segments:
        for w in seg.words:
            all_words.append(w)

    if len(all_words) < 2:
        return pauses

    # Build section boundary times from script sentences
    section_times: set[float] = set()
    if script_sentences:
        for s in script_sentences:
            if s.is_section_start:
                section_times.add(float(s.index))

    # Detect gaps between consecutive words
    for i in range(len(all_words) - 1):
        gap_start = all_words[i].end
        gap_end = all_words[i + 1].start
        duration = gap_end - gap_start

        if duration < 0.05:
            continue  # Ignore tiny gaps (rounding errors)

        pause_type = _classify_pause(duration)

        # Check if this pause is near a section boundary
        is_section_boundary = False
        if script_sentences:
            # Simple heuristic: check if this is between transcript segments
            # that align with different script sections
            for seg in transcription.segments:
                if abs(seg.start - gap_end) < 0.5 or abs(seg.end - gap_start) < 0.5:
                    is_section_boundary = True
                    break

        action = _recommend_action(pause_type, is_section_boundary)

        pauses.append(PauseSegment(
            start=gap_start,
            end=gap_end,
            duration=duration,
            pause_type=pause_type,
            action=action,
        ))

    return pauses
