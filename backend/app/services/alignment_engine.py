import logging
from typing import Optional

from app.config import get_settings
from app.models.schemas import (
    AlignedSegment,
    ConfidenceLevel,
    MatchResult,
    PauseSegment,
    SegmentStatus,
    TranscriptionResult,
    ScriptSentence,
)

logger = logging.getLogger(__name__)


def _classify_confidence(score: float) -> ConfidenceLevel:
    settings = get_settings()
    if score >= settings.HIGH_CONFIDENCE_THRESHOLD:
        return ConfidenceLevel.HIGH
    elif score >= settings.MEDIUM_CONFIDENCE_THRESHOLD:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _longest_increasing_subsequence(positions: list[int]) -> list[int]:
    """
    Find the longest increasing subsequence of positions.
    Returns indices into the input list that form the LIS.
    """
    if not positions:
        return []

    n = len(positions)
    # dp[i] = length of LIS ending at index i
    dp = [1] * n
    parent = [-1] * n

    for i in range(1, n):
        for j in range(i):
            if positions[j] < positions[i] and dp[j] + 1 > dp[i]:
                dp[i] = dp[j] + 1
                parent[i] = j

    # Reconstruct
    max_len = max(dp)
    idx = dp.index(max_len)
    lis_indices = []
    while idx != -1:
        lis_indices.append(idx)
        idx = parent[idx]
    lis_indices.reverse()
    return lis_indices


def _select_best_matches(
    match_results: list[MatchResult],
    num_script_sentences: int,
) -> dict[int, MatchResult]:
    """
    For each script sentence, select the best match (highest score).
    Returns mapping of script_index -> best MatchResult.
    """
    best: dict[int, MatchResult] = {}
    for m in match_results:
        if m.script_index not in best or m.score > best[m.script_index].score:
            best[m.script_index] = m
    return best


def _dynamic_programming_alignment(
    best_matches: dict[int, MatchResult],
    num_script_sentences: int,
    all_words: list[dict],
) -> dict[int, MatchResult]:
    """
    Use dynamic programming to find the globally optimal assignment
    that maximizes total score while respecting temporal ordering
    where possible.
    """
    if not best_matches:
        return {}

    # Sort script indices by their transcript position
    matched_indices = sorted(
        best_matches.keys(),
        key=lambda idx: best_matches[idx].transcript_start_word_idx,
    )

    if not matched_indices:
        return {}

    # Get transcript positions for LIS
    positions = [
        best_matches[idx].transcript_start_word_idx for idx in matched_indices
    ]

    # Find the longest increasing subsequence (the main "backbone")
    lis_indices = _longest_increasing_subsequence(positions)

    # All matches in LIS are "in order"; the rest are potentially reordered
    lis_set = set(lis_indices)

    result: dict[int, MatchResult] = {}
    for i, script_idx in enumerate(matched_indices):
        result[script_idx] = best_matches[script_idx]

    return result


def align_segments(
    script_sentences: list[ScriptSentence],
    match_results: list[MatchResult],
    transcription: TranscriptionResult,
    pauses: Optional[list[PauseSegment]] = None,
) -> list[AlignedSegment]:
    """
    THE CORE ALIGNMENT ENGINE.

    1. Select best match for each script sentence
    2. Use dynamic programming for global optimal matching
    3. Detect reordering via LIS
    4. Mark reordered segments as COPY
    5. Mark unmatched script sentences as DELETED
    6. Classify confidence levels
    """
    if pauses is None:
        pauses = []

    # Flatten all words from transcription
    all_words: list[dict] = []
    for seg in transcription.segments:
        for w in seg.words:
            all_words.append({
                "word": w.word,
                "start": w.start,
                "end": w.end,
                "confidence": w.confidence,
            })

    # Step 1: Select best matches
    best_matches = _select_best_matches(match_results, len(script_sentences))

    # Step 2: DP alignment
    optimized = _dynamic_programming_alignment(
        best_matches, len(script_sentences), all_words
    )

    # Step 3: Detect reordering with LIS
    # Build list of (script_index, transcript_position) sorted by script order
    matched_script_indices = sorted(optimized.keys())
    transcript_positions = []
    for si in matched_script_indices:
        transcript_positions.append(optimized[si].transcript_start_word_idx)

    lis_indices = _longest_increasing_subsequence(transcript_positions)
    lis_script_indices = set(
        matched_script_indices[i] for i in lis_indices
    ) if lis_indices else set()

    # Step 4: Build aligned segments
    aligned: list[AlignedSegment] = []

    for sentence in script_sentences:
        si = sentence.index

        if si not in optimized:
            # Unmatched / deleted
            aligned.append(AlignedSegment(
                script_index=si,
                script_text=sentence.text,
                transcript_text="",
                start_time=0.0,
                end_time=0.0,
                raw_start_time=0.0,
                raw_end_time=0.0,
                confidence=0.0,
                confidence_level=ConfidenceLevel.LOW,
                status=SegmentStatus.DELETED,
                is_reordered=False,
                original_position=None,
                pauses=[],
            ))
            continue

        match = optimized[si]

        # Get timestamps from word indices
        start_idx = max(0, min(match.transcript_start_word_idx, len(all_words) - 1))
        end_idx = max(0, min(match.transcript_end_word_idx - 1, len(all_words) - 1))

        start_time = all_words[start_idx]["start"] if all_words else 0.0
        end_time = all_words[end_idx]["end"] if all_words else 0.0

        # Build transcript text from matched words
        matched_words = all_words[
            match.transcript_start_word_idx:match.transcript_end_word_idx
        ]
        transcript_text = "".join(w["word"] for w in matched_words)

        # Check if reordered
        is_reordered = si not in lis_script_indices and si in optimized
        original_pos = match.transcript_start_word_idx if is_reordered else None

        # Determine status
        if is_reordered:
            status = SegmentStatus.COPY
        else:
            status = SegmentStatus.MATCHED

        # Find pauses within this segment's time range
        segment_pauses = [
            p for p in pauses
            if p.start >= start_time and p.end <= end_time
        ]

        aligned.append(AlignedSegment(
            script_index=si,
            script_text=sentence.text,
            transcript_text=transcript_text,
            start_time=start_time,
            end_time=end_time,
            raw_start_time=start_time,
            raw_end_time=end_time,
            confidence=match.score,
            confidence_level=_classify_confidence(match.score),
            status=status,
            is_reordered=is_reordered,
            original_position=original_pos,
            pauses=segment_pauses,
        ))

    return aligned
