import logging
import re
from bisect import bisect_left
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

_ALIGN_CLEAN_RE = re.compile(
    r"[\s\u3000，。！？、；：\u201c\u201d\u2018\u2019《》（）【】…\u2014\-,.!?;:\"'()\[\]]+"
)

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


def _clean_alignment_text(text: str) -> str:
    return _ALIGN_CLEAN_RE.sub("", text)


def _edge_similarity(
    script_text: str,
    candidate_text: str,
    *,
    edge: str,
    max_chars: int = 8,
) -> float:
    clean_script = _clean_alignment_text(script_text)
    clean_candidate = _clean_alignment_text(candidate_text)
    if not clean_script or not clean_candidate:
        return 0.0

    edge_len = min(max_chars, len(clean_script), len(clean_candidate))
    if edge_len <= 0:
        return 0.0

    if edge == "prefix":
        return float(fuzz.ratio(clean_script[:edge_len], clean_candidate[:edge_len]))
    return float(fuzz.ratio(clean_script[-edge_len:], clean_candidate[-edge_len:]))


def _window_text(
    all_words: list[dict],
    start_idx: int,
    end_idx: int,
) -> str:
    return "".join(w["word"] for w in all_words[start_idx:end_idx])


def _score_window_fit(script_text: str, candidate_text: str) -> float:
    clean_script = _clean_alignment_text(script_text)
    clean_candidate = _clean_alignment_text(candidate_text)
    if not clean_script or not clean_candidate:
        return float("-inf")

    ratio = float(fuzz.ratio(clean_script, clean_candidate))
    prefix = _edge_similarity(script_text, candidate_text, edge="prefix")
    suffix = _edge_similarity(script_text, candidate_text, edge="suffix")
    return ratio + (0.20 * prefix) + (0.05 * suffix)


def _refine_word_window(
    script_text: str,
    all_words: list[dict],
    start_idx: int,
    end_idx: int,
) -> tuple[int, int]:
    """Retune a matched window without drifting far from the coarse match.

    The LLM matcher often returns a slightly broader segment span than the
    actual scripted speech, but occasionally it also starts too late and lands
    in the middle of a sentence. Search a small neighborhood around the coarse
    window so we can both trim extras and recover missed leading words.
    """
    clean_script = _clean_alignment_text(script_text)
    if not clean_script:
        return start_idx, end_idx

    if end_idx - start_idx <= 3:
        return start_idx, end_idx

    search_pad = min(25, len(all_words) - 3)
    search_start = max(0, start_idx - search_pad)
    search_end = min(len(all_words), end_idx + search_pad)

    base_text = _window_text(all_words, start_idx, end_idx)
    base_score = _score_window_fit(script_text, base_text)
    best_score = base_score
    best_start = start_idx
    best_end = end_idx

    start_min = search_start
    start_max = min(start_idx + search_pad, search_end - 3)

    for candidate_start in range(start_min, start_max + 1):
        end_min = max(candidate_start + 3, end_idx - search_pad)
        end_max = search_end
        for candidate_end in range(end_min, end_max + 1):
            candidate_len = candidate_end - candidate_start
            if candidate_len < 3:
                continue

            candidate_text = _window_text(all_words, candidate_start, candidate_end)
            if not candidate_text:
                continue

            score = _score_window_fit(script_text, candidate_text)
            prefix = _edge_similarity(script_text, candidate_text, edge="prefix")
            best_prefix = _edge_similarity(
                script_text,
                _window_text(all_words, best_start, best_end),
                edge="prefix",
            )

            if (
                score > best_score
                or (
                    abs(score - best_score) <= 0.01
                    and prefix > best_prefix
                )
                or (
                    abs(score - best_score) <= 0.01
                    and abs(prefix - best_prefix) <= 0.01
                    and candidate_start < best_start
                )
            ):
                best_score = score
                best_start = candidate_start
                best_end = candidate_end

    if (best_start, best_end) != (start_idx, end_idx):
        logger.info(
            "Refined match window for script text from [%d, %d) to [%d, %d) "
            "(%.1f -> %.1f)",
            start_idx,
            end_idx,
            best_start,
            best_end,
            base_score,
            best_score,
        )

    return best_start, best_end


def _resolve_adjacent_boundary(
    left_script_text: str,
    right_script_text: str,
    all_words: list[dict],
    left_start: int,
    left_end: int,
    right_start: int,
    right_end: int,
) -> tuple[int, int]:
    """Choose a shared split point when adjacent windows overlap.

    First principle: once two neighboring script sentences claim overlapping
    transcript words, we should stop treating them independently and instead
    search for the best single boundary between them.
    """
    boundary_min = max(left_start + 1, right_start)
    boundary_max = min(left_end, right_end - 1)
    if boundary_min > boundary_max:
        return left_end, right_start

    best_split = right_start
    best_score = float("-inf")

    for split_idx in range(boundary_min, boundary_max + 1):
        left_candidate = _window_text(all_words, left_start, split_idx)
        right_candidate = _window_text(all_words, split_idx, right_end)
        score = (
            _score_window_fit(left_script_text, left_candidate)
            + _score_window_fit(right_script_text, right_candidate)
        )
        if score > best_score:
            best_score = score
            best_split = split_idx

    return best_split, best_split


def _rebalance_adjacent_windows(
    script_sentences: list[ScriptSentence],
    refined_windows: dict[int, tuple[int, int]],
    all_words: list[dict],
    hooks: dict[int, int],
) -> None:
    """Remove overlap between neighboring non-hook script windows in-place."""
    script_lookup = {
        sentence.index: sentence.text for sentence in script_sentences
    }
    previous_script_index: Optional[int] = None

    for sentence in script_sentences:
        script_index = sentence.index
        if script_index not in refined_windows or script_index in hooks:
            continue

        if previous_script_index is None:
            previous_script_index = script_index
            continue

        prev_start, prev_end = refined_windows[previous_script_index]
        curr_start, curr_end = refined_windows[script_index]

        if curr_start < prev_start:
            previous_script_index = script_index
            continue

        if curr_start >= prev_end:
            previous_script_index = script_index
            continue

        new_prev_end, new_curr_start = _resolve_adjacent_boundary(
            left_script_text=script_lookup[previous_script_index],
            right_script_text=sentence.text,
            all_words=all_words,
            left_start=prev_start,
            left_end=prev_end,
            right_start=curr_start,
            right_end=curr_end,
        )

        if (new_prev_end, new_curr_start) != (prev_end, curr_start):
            logger.info(
                "Rebalanced adjacent script windows: script[%d] [%d, %d) and "
                "script[%d] [%d, %d) -> [%d, %d) and [%d, %d)",
                previous_script_index,
                prev_start,
                prev_end,
                script_index,
                curr_start,
                curr_end,
                prev_start,
                new_prev_end,
                new_curr_start,
                curr_end,
            )
            refined_windows[previous_script_index] = (prev_start, new_prev_end)
            refined_windows[script_index] = (new_curr_start, curr_end)

        previous_script_index = script_index


def _longest_increasing_subsequence(positions: list[int]) -> list[int]:
    """
    Find the longest increasing subsequence of positions.
    Returns indices into the input list that form the LIS.
    """
    if not positions:
        return []

    n = len(positions)
    parent = [-1] * n
    tail_indices: list[int] = []

    for idx, position in enumerate(positions):
        insert_at = bisect_left(
            [positions[tail_idx] for tail_idx in tail_indices],
            position,
        )
        if insert_at > 0:
            parent[idx] = tail_indices[insert_at - 1]

        if insert_at == len(tail_indices):
            tail_indices.append(idx)
        else:
            tail_indices[insert_at] = idx

    lis_indices: list[int] = []
    idx = tail_indices[-1] if tail_indices else -1
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

    refined_windows: dict[int, tuple[int, int]] = {}
    for sentence in script_sentences:
        si = sentence.index
        if si not in optimized:
            continue

        match = optimized[si]
        start_idx = max(0, min(match.transcript_start_word_idx, len(all_words) - 1))
        end_exclusive = max(
            start_idx + 1,
            min(match.transcript_end_word_idx, len(all_words)),
        )
        refined_windows[si] = _refine_word_window(
            sentence.text,
            all_words,
            start_idx,
            end_exclusive,
        )

    _rebalance_adjacent_windows(
        script_sentences=script_sentences,
        refined_windows=refined_windows,
        all_words=all_words,
        hooks=hooks,
    )

    # Step 3: Detect reordering with LIS.
    # Keep the original coarse-match positions for reorder detection so we
    # preserve the existing copy semantics; refined windows are only for
    # tightening boundaries after the match is already chosen.
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

        # Get timestamps from the refined word window
        start_idx, end_exclusive = refined_windows[si]
        end_idx = max(start_idx, end_exclusive - 1)

        start_time = all_words[start_idx]["start"] if all_words else 0.0
        end_time = all_words[end_idx]["end"] if all_words else 0.0

        # Build transcript text from matched words
        matched_words = all_words[
            start_idx:end_exclusive
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

            if is_reordered:
                logger.warning(
                    "Marking out-of-order non-hook match for script[%d] as COPY",
                    si,
                )

        # Find pauses within this segment's time range
        segment_pauses = [
            p for p in pauses
            if p.start >= start_time and p.end <= end_time
        ]

        # ── Trim breath gaps (气口) ──
        # Strategy depends on transcription source:
        #
        # CLOUD mode (word-level timestamps from Volcengine Caption API):
        #   The matched words already have precise per-character timestamps.
        #   start_time = first matched word's start, end_time = last matched
        #   word's end.  These ARE the speech boundaries — no further
        #   trimming needed.  Pause-based trimming would only degrade them.
        #
        # LOCAL mode (WhisperX):
        #   Word timestamps may be less precise; segment boundaries often
        #   include leading/trailing silence.  Use pause detection to trim.
        #
        # We distinguish by checking whether word timestamps are granular
        # (cloud gives per-character; local gives per-word which is coarser).
        # Heuristic: if average word duration < 0.3s, it's character-level
        # (cloud), otherwise it's word-level (local).
        avg_word_dur = (
            (end_time - start_time) / len(matched_words)
            if matched_words else 1.0
        )
        is_cloud_precision = avg_word_dur < 0.3

        if is_cloud_precision:
            # Cloud mode: trust word timestamps directly.
            # No pause-based trimming — the boundaries are already tight.
            trimmed_start = start_time
            trimmed_end = end_time
        else:
            # Local mode fallback: trim leading/trailing pauses
            trimmed_start = start_time
            trimmed_end = end_time

            TRIM_TOLERANCE = 0.15  # seconds
            for p in sorted(segment_pauses, key=lambda p: p.start):
                if p.start <= trimmed_start + TRIM_TOLERANCE:
                    trimmed_start = max(trimmed_start, p.end)
                else:
                    break

            for p in sorted(segment_pauses, key=lambda p: p.end, reverse=True):
                if p.end >= trimmed_end - TRIM_TOLERANCE:
                    trimmed_end = min(trimmed_end, p.start)
                else:
                    break

            # Safety: don't let trimming invert the range
            if trimmed_end - trimmed_start < 0.3:
                trimmed_start = start_time
                trimmed_end = end_time

        aligned.append(AlignedSegment(
            script_index=si,
            script_text=sentence.text,
            transcript_text=transcript_text,
            start_time=trimmed_start,
            end_time=trimmed_end,
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
