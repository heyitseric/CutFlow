"""
Consolidate fine-grained transcript segments into sentence-level segments.

Cloud transcription APIs (e.g. Volcengine Caption) often return many small
segments (word or phrase level, e.g. 1242 segments for a 10-minute video).
The matching algorithms work much better when these are grouped into
sentence-level segments that naturally correspond to script sentences.

This module groups consecutive small segments based on:
  - Punctuation boundaries (。！？!? etc.)
  - Pause gaps between segments (> 0.7s)
  - Maximum segment duration (30s)
"""

import logging
import re

from app.models.schemas import (
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionWord,
)

logger = logging.getLogger(__name__)

# Chinese sentence-ending punctuation
_SENTENCE_END_RE = re.compile(r"[。！？!?]$")

# Maximum duration for a consolidated segment (seconds)
_MAX_SEGMENT_DURATION = 30.0

# Pause gap threshold to force a segment boundary (seconds)
_PAUSE_GAP_THRESHOLD = 0.7


def consolidate_segments(
    transcription: TranscriptionResult,
    *,
    pause_threshold: float = _PAUSE_GAP_THRESHOLD,
    max_duration: float = _MAX_SEGMENT_DURATION,
) -> TranscriptionResult:
    """
    Group fine-grained transcript segments into sentence-level segments.

    Each output segment's ``text`` is the concatenation of the grouped
    input segments' texts, and its ``words`` list is the concatenation
    of all the input segments' words (preserving word-level timestamps).

    Returns a *new* TranscriptionResult; the original is not mutated.
    """
    segments = transcription.segments
    if not segments:
        return transcription

    # If there are few segments already (likely already sentence-level),
    # skip consolidation to avoid unnecessary processing.
    if len(segments) <= 30:
        logger.info(
            "Transcript has %d segments (<=30), skipping consolidation",
            len(segments),
        )
        return transcription

    logger.info(
        "Consolidating %d fine-grained segments into sentence-level groups",
        len(segments),
    )

    consolidated: list[TranscriptionSegment] = []

    # Accumulator for the current group
    group_texts: list[str] = []
    group_words: list[TranscriptionWord] = []
    group_start: float = 0.0
    group_end: float = 0.0

    def _flush_group():
        """Emit the current accumulated group as a single segment."""
        if not group_texts:
            return
        text = "".join(group_texts)
        if text.strip():
            consolidated.append(
                TranscriptionSegment(
                    text=text,
                    start=group_start,
                    end=group_end,
                    words=list(group_words),
                )
            )

    for i, seg in enumerate(segments):
        if not group_texts:
            # Start a new group
            group_texts.append(seg.text)
            group_words.extend(seg.words)
            group_start = seg.start
            group_end = seg.end
        else:
            # Check whether to break here
            gap = seg.start - group_end
            duration = seg.end - group_start

            should_break = False

            # Break on punctuation at the end of the previous segment
            if group_texts and _SENTENCE_END_RE.search(group_texts[-1]):
                should_break = True

            # Break on long pause gap
            if gap >= pause_threshold:
                should_break = True

            # Break if group would exceed max duration
            if duration > max_duration:
                should_break = True

            if should_break:
                _flush_group()
                group_texts = [seg.text]
                group_words = list(seg.words)
                group_start = seg.start
                group_end = seg.end
            else:
                group_texts.append(seg.text)
                group_words.extend(seg.words)
                group_end = seg.end

    # Flush the last group
    _flush_group()

    logger.info(
        "Consolidation complete: %d -> %d segments",
        len(segments),
        len(consolidated),
    )

    return TranscriptionResult(
        segments=consolidated,
        language=transcription.language,
        duration=transcription.duration,
    )
