"""
Rule-based Chinese text segmenter for SRT subtitles.

Serves two purposes:
1. Fallback segmenter when the LLM-based segmenter fails or is unavailable.
2. Post-processing enforcement of character limits on LLM segmentation results.

Splitting priority:
    sentence-ending punctuation (。！？) >
    clause-level punctuation (，、；：) >
    jieba word boundaries

All operations preserve the original text character-for-character.
Punctuation is kept at the END of the segment it belongs to.
"""

import logging
import re

import jieba

logger = logging.getLogger(__name__)

# Sentence-ending punctuation (highest split priority)
_SENTENCE_END = r"([。！？])"
# Clause-level punctuation (lower split priority)
_CLAUSE_PUNCT = r"([，、；：])"


def _split_at_pattern(text: str, pattern: str) -> list[str]:
    """Split text using a regex pattern with a capturing group.

    The punctuation mark captured by the group is appended to the
    preceding segment so that it stays at the end of the segment
    it belongs to.

    Returns a list of non-empty segments whose concatenation equals
    the original text.
    """
    parts = re.split(pattern, text)
    # re.split with a capturing group interleaves text and delimiters:
    # ["before", "。", "after", "！", "rest"] etc.
    segments: list[str] = []
    i = 0
    while i < len(parts):
        chunk = parts[i]
        # If the next part is a captured delimiter, attach it to this chunk
        if i + 1 < len(parts) and re.fullmatch(pattern, parts[i + 1]):
            chunk += parts[i + 1]
            i += 2
        else:
            i += 1
        if chunk:
            segments.append(chunk)
    return segments


def _split_by_jieba(text: str, max_chars: int) -> list[str]:
    """Split text at jieba word boundaries so that each segment <= max_chars.

    Words are greedily accumulated until adding the next word would exceed
    max_chars.  If a single word is longer than max_chars it is emitted
    as-is (we never break within a jieba token).
    """
    words = list(jieba.cut(text))
    segments: list[str] = []
    current = ""

    for word in words:
        if not current:
            current = word
            continue
        if len(current) + len(word) <= max_chars:
            current += word
        else:
            segments.append(current)
            current = word

    if current:
        segments.append(current)

    return segments


def _merge_short_segments(
    segments: list[str],
    min_chars: int,
    max_chars: int,
) -> list[str]:
    """Merge adjacent segments shorter than min_chars.

    Strategy: prefer merging with the previous segment.  If that would
    exceed max_chars, merge with the next segment instead.
    """
    if not segments:
        return segments

    merged: list[str] = [segments[0]]

    for seg in segments[1:]:
        if len(seg) < min_chars:
            # Try merging with previous
            candidate = merged[-1] + seg
            if len(candidate) <= max_chars:
                merged[-1] = candidate
                continue
        # Either the segment is long enough, or merging with previous
        # would exceed max_chars — just append.
        merged.append(seg)

    # Second pass: merge leading short segments forward
    if len(merged) > 1 and len(merged[0]) < min_chars:
        candidate = merged[0] + merged[1]
        if len(candidate) <= max_chars:
            merged = [candidate] + merged[2:]

    return merged


def split_by_rules(
    text: str,
    max_chars: int = 15,
    min_chars: int = 5,
) -> list[str]:
    """Split Chinese text into SRT-appropriate segments using rules.

    Args:
        text: The text to segment.
        max_chars: Maximum characters per segment (default 15).
        min_chars: Minimum preferred characters per segment (default 5).

    Returns:
        A list of segments whose concatenation equals the original text.
    """
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    logger.debug("split_by_rules: input %d chars, max=%d min=%d", len(text), max_chars, min_chars)

    # --- Stage 1: split at sentence-ending punctuation ---
    segments = _split_at_pattern(text, _SENTENCE_END)
    logger.debug("After sentence-end split: %s", segments)

    # --- Stage 2: split remaining long segments at clause punctuation ---
    expanded: list[str] = []
    for seg in segments:
        if len(seg) > max_chars:
            expanded.extend(_split_at_pattern(seg, _CLAUSE_PUNCT))
        else:
            expanded.append(seg)
    segments = expanded
    logger.debug("After clause-punct split: %s", segments)

    # --- Stage 3: split remaining long segments at jieba word boundaries ---
    expanded = []
    for seg in segments:
        if len(seg) > max_chars:
            expanded.extend(_split_by_jieba(seg, max_chars))
        else:
            expanded.append(seg)
    segments = expanded
    logger.debug("After jieba split: %s", segments)

    # --- Stage 4: merge short segments ---
    segments = _merge_short_segments(segments, min_chars, max_chars)
    logger.debug("After merge: %s", segments)

    # --- Final validation ---
    reconstructed = "".join(segments)
    if reconstructed != text:
        raise ValueError(
            f"Text reconstruction failed: "
            f"expected {len(text)} chars, got {len(reconstructed)} chars"
        )

    return segments


def enforce_segment_limits(
    segments: list[str],
    max_chars: int = 15,
    min_chars: int = 5,
) -> list[str]:
    """Enforce character limits on a list of pre-segmented text.

    Useful as a post-processing step after LLM-based segmentation to
    guarantee all segments respect the max/min character constraints.

    Args:
        segments: Pre-existing list of text segments.
        max_chars: Maximum characters per segment (default 15).
        min_chars: Minimum preferred characters per segment (default 5).

    Returns:
        A list of segments respecting the limits, whose concatenation
        equals the concatenation of the original segments.
    """
    if not segments:
        return []

    original_text = "".join(segments)

    # --- Pass 1: split oversized segments ---
    expanded: list[str] = []
    for seg in segments:
        if len(seg) > max_chars:
            logger.debug("enforce: splitting oversized segment (%d chars): %s", len(seg), seg)
            expanded.extend(split_by_rules(seg, max_chars, min_chars))
        else:
            expanded.append(seg)

    # --- Pass 2: merge undersized segments ---
    result = _merge_short_segments(expanded, min_chars, max_chars)

    # --- Final validation ---
    reconstructed = "".join(result)
    if reconstructed != original_text:
        raise ValueError(
            f"Text reconstruction failed after enforce_segment_limits: "
            f"expected {len(original_text)} chars, got {len(reconstructed)} chars"
        )

    logger.debug(
        "enforce_segment_limits: %d segments -> %d segments",
        len(segments),
        len(result),
    )

    return result
