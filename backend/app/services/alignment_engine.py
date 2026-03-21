import logging
from typing import Optional

from rapidfuzz import fuzz

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

# ---------------------------------------------------------------------------
# Hook / copy detection
# ---------------------------------------------------------------------------
# A "hook" is a script line near the beginning that is a textual copy of a
# line that appears later in the script.  Video editors place hooks at the
# start to grab viewer attention; the audio for the hook comes from the
# middle/end of the recording.
#
# Detection strategy:
#   1. For each of the first N script lines, compare its text against all
#      later script lines using fuzzy matching.
#   2. If a later line has >=THRESHOLD similarity, the early line is a hook
#      copy of the later (original) line.
#   3. Mark the early line as is_copy=True with copy_source_index pointing
#      to the later line's script index.
# ---------------------------------------------------------------------------

_HOOK_SCAN_RANGE = 10          # only check the first N script lines
_HOOK_SIMILARITY_THRESHOLD = 80  # rapidfuzz score 0-100


def detect_hooks(
    script_sentences: list[ScriptSentence],
) -> dict[int, int]:
    """
    Return a mapping of {hook_script_index: original_script_index} for
    script lines that are copies of later lines.

    Only the first ``_HOOK_SCAN_RANGE`` lines are candidates for being
    hooks, but the "original" can be anywhere after the hook.
    """
    hooks: dict[int, int] = {}  # hook_idx -> original_idx
    n = len(script_sentences)
    scan_end = min(_HOOK_SCAN_RANGE, n)

    for i in range(scan_end):
        hook_text = script_sentences[i].text
        best_score = 0.0
        best_j = -1

        for j in range(i + 1, n):
            candidate_text = script_sentences[j].text
            score = fuzz.token_set_ratio(hook_text, candidate_text)
            if score > best_score:
                best_score = score
                best_j = j

        if best_score >= _HOOK_SIMILARITY_THRESHOLD and best_j >= 0:
            hooks[script_sentences[i].index] = script_sentences[best_j].index
            logger.info(
                "Hook detected: script line %d is a copy of line %d "
                "(similarity %.0f%%)",
                script_sentences[i].index,
                script_sentences[best_j].index,
                best_score,
            )

    return hooks


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
    4. Detect hook/copy lines (early lines that duplicate later lines)
    5. For hook copies, reuse timecodes from the original's match
    6. Mark reordered segments as COPY
    7. Mark unmatched script sentences as DELETED
    8. Classify confidence levels
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

    # Step 0: Detect hooks (script-level, before matching)
    hooks = detect_hooks(script_sentences)
    if hooks:
        logger.info("Detected %d hook/copy lines: %s", len(hooks), hooks)

    # Step 1: Select best matches
    best_matches = _select_best_matches(match_results, len(script_sentences))

    # For hook lines: if the hook itself wasn't matched well but the original
    # was, copy the original's match result to the hook so it gets the same
    # audio timecodes.
    for hook_idx, orig_idx in hooks.items():
        orig_match = best_matches.get(orig_idx)
        if orig_match is not None:
            hook_match = best_matches.get(hook_idx)
            # Use original's match if hook has no match or a worse match
            if hook_match is None or hook_match.score < orig_match.score:
                best_matches[hook_idx] = MatchResult(
                    script_index=hook_idx,
                    transcript_start_word_idx=orig_match.transcript_start_word_idx,
                    transcript_end_word_idx=orig_match.transcript_end_word_idx,
                    score=orig_match.score,
                )

    # Step 2: DP alignment
    optimized = _dynamic_programming_alignment(
        best_matches, len(script_sentences), all_words
    )

    # Step 3: Detect reordering with LIS
    # Exclude hook copies from LIS computation so they don't distort the
    # chronological ordering of non-hook lines.
    matched_script_indices = sorted(
        si for si in optimized.keys() if si not in hooks
    )
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
        is_hook = si in hooks

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
                is_copy=False,
                copy_source_index=None,
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

        # Determine status
        if is_hook:
            # Hook copies get COPY status and is_copy flag
            status = SegmentStatus.COPY
            is_reordered = True
            original_pos = match.transcript_start_word_idx
            copy_source = hooks[si]
        else:
            # Non-hook: check if reordered via LIS
            is_reordered = si not in lis_script_indices and si in optimized
            original_pos = match.transcript_start_word_idx if is_reordered else None
            status = SegmentStatus.COPY if is_reordered else SegmentStatus.MATCHED
            copy_source = None

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
            is_copy=is_hook,
            copy_source_index=copy_source,
            pauses=segment_pauses,
        ))

    return aligned
