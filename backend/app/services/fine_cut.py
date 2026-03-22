import copy
import logging
import re

from rapidfuzz import fuzz

from app.models.schemas import AlignedSegment, SegmentStatus, TranscriptionResult

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = {
    SegmentStatus.MATCHED,
    SegmentStatus.COPY,
    SegmentStatus.APPROVED,
}

_CLEAN_RE = re.compile(
    r"[\s\u3000，。！？、；：\u201c\u201d\u2018\u2019《》（）【】…\u2014\-,.!?;:\"'()\[\]]+"
)
_CLAUSE_PUNCT = "，,；;：:。！？!?"


def _clean_text(text: str) -> str:
    return _CLEAN_RE.sub("", text)


def _split_script_clauses(text: str) -> list[str]:
    clauses: list[str] = []
    current = ""

    for ch in text:
        current += ch
        if ch in _CLAUSE_PUNCT:
            if current.strip():
                clauses.append(current.strip())
            current = ""

    if current.strip():
        clauses.append(current.strip())

    if not clauses:
        return [text.strip()] if text.strip() else []

    merged: list[str] = []
    for clause in clauses:
        clean_len = len(_clean_text(clause))
        if not merged:
            merged.append(clause)
            continue

        if clean_len < 8:
            merged[-1] += clause
        else:
            merged.append(clause)

    if len(merged) >= 2 and len(_clean_text(merged[-1])) < 8:
        merged[-2] += merged[-1]
        merged.pop()

    return [clause for clause in merged if _clean_text(clause)]


def _flatten_words(transcription: TranscriptionResult) -> list[dict]:
    words: list[dict] = []
    for seg in transcription.segments:
        for word in seg.words:
            words.append(
                {
                    "word": word.word,
                    "start": word.start,
                    "end": word.end,
                }
            )
    return words


def _time_range_to_word_indices(
    start_time: float,
    end_time: float,
    all_words: list[dict],
) -> tuple[int, int] | None:
    if not all_words:
        return None

    tolerance = 0.08
    start_idx = len(all_words)
    end_idx = 0

    for idx, word in enumerate(all_words):
        if word["start"] < end_time + tolerance and word["end"] > start_time - tolerance:
            start_idx = min(start_idx, idx)
            end_idx = max(end_idx, idx + 1)

    if start_idx >= end_idx:
        return None

    return start_idx, end_idx


def _join_words(all_words: list[dict], start_idx: int, end_idx: int) -> str:
    return "".join(word["word"] for word in all_words[start_idx:end_idx])


def _find_best_clause_window(
    clause_text: str,
    all_words: list[dict],
    search_start: int,
    search_end: int,
) -> tuple[int, int, float] | None:
    clean_clause = _clean_text(clause_text)
    if not clean_clause or search_start >= search_end:
        return None

    available = search_end - search_start
    clause_len = len(clean_clause)
    min_window = max(1, clause_len - 4)
    max_window = min(available, max(clause_len + 12, int(clause_len * 2.2)))

    if min_window > max_window:
        min_window = 1
        max_window = available

    best: tuple[int, int, float] | None = None

    for window_size in range(min_window, max_window + 1):
        for start_idx in range(search_start, search_end - window_size + 1):
            end_idx = start_idx + window_size
            candidate = _clean_text(_join_words(all_words, start_idx, end_idx))
            if not candidate:
                continue

            ratio = fuzz.ratio(clean_clause, candidate)
            partial = fuzz.partial_ratio(clean_clause, candidate)
            length_penalty = abs(len(candidate) - clause_len) * 1.5
            score = max(ratio, partial) - length_penalty

            if best is None or score > best[2]:
                best = (start_idx, end_idx, score)

    if best is None:
        return None

    start_idx, end_idx, score = best
    if score < 55:
        return None

    return best


def _merge_clause_matches(
    seg: AlignedSegment,
    clause_matches: list[tuple[str, int, int]],
    all_words: list[dict],
) -> list[AlignedSegment]:
    if not clause_matches:
        return [copy.deepcopy(seg)]

    merged_groups: list[dict] = []
    for clause_text, start_idx, end_idx in clause_matches:
        if not merged_groups:
            merged_groups.append(
                {
                    "script_texts": [clause_text],
                    "start_idx": start_idx,
                    "end_idx": end_idx,
                }
            )
            continue

        prev = merged_groups[-1]
        prev_end_time = all_words[prev["end_idx"] - 1]["end"]
        gap = all_words[start_idx]["start"] - prev_end_time

        if gap <= 0.22:
            prev["script_texts"].append(clause_text)
            prev["end_idx"] = end_idx
        else:
            merged_groups.append(
                {
                    "script_texts": [clause_text],
                    "start_idx": start_idx,
                    "end_idx": end_idx,
                }
            )

    refined: list[AlignedSegment] = []
    for group in merged_groups:
        start_idx = group["start_idx"]
        end_idx = group["end_idx"]
        new_seg = copy.deepcopy(seg)
        new_seg.script_text = "".join(group["script_texts"]).strip()
        new_seg.transcript_text = _join_words(all_words, start_idx, end_idx)
        new_seg.start_time = all_words[start_idx]["start"]
        new_seg.end_time = all_words[end_idx - 1]["end"]
        new_seg.raw_start_time = new_seg.start_time
        new_seg.raw_end_time = new_seg.end_time
        refined.append(new_seg)

    return refined


def fine_cut_segments(
    segments: list[AlignedSegment],
    transcription: TranscriptionResult,
) -> list[AlignedSegment]:
    """Trim coarse aligned segments down to script-faithful clause spans.

    First principle: the script is the source of truth for what should remain.
    This service only searches inside an already matched transcript window and
    keeps the best in-order clause spans that resemble the script.
    """
    if not segments or not transcription.segments:
        return [copy.deepcopy(seg) for seg in segments]

    all_words = _flatten_words(transcription)
    if not all_words:
        return [copy.deepcopy(seg) for seg in segments]

    refined: list[AlignedSegment] = []
    split_segments = 0

    for seg in segments:
        if seg.status not in _ACTIVE_STATUSES or not seg.transcript_text.strip():
            refined.append(copy.deepcopy(seg))
            continue

        clauses = _split_script_clauses(seg.script_text)
        if len(clauses) < 2 or len(_clean_text(seg.script_text)) < 24:
            refined.append(copy.deepcopy(seg))
            continue

        word_range = _time_range_to_word_indices(
            seg.raw_start_time,
            seg.raw_end_time,
            all_words,
        )
        if word_range is None:
            refined.append(copy.deepcopy(seg))
            continue

        search_start, search_end = word_range
        cursor = search_start
        clause_matches: list[tuple[str, int, int]] = []

        for clause in clauses:
            match = _find_best_clause_window(
                clause,
                all_words,
                cursor,
                search_end,
            )
            if match is None:
                continue

            start_idx, end_idx, _score = match
            clause_matches.append((clause, start_idx, end_idx))
            cursor = end_idx

        matched_chars = sum(len(_clean_text(clause)) for clause, _, _ in clause_matches)
        total_chars = len(_clean_text(seg.script_text))

        if len(clause_matches) < 2 or matched_chars / max(total_chars, 1) < 0.6:
            refined.append(copy.deepcopy(seg))
            continue

        new_segments = _merge_clause_matches(seg, clause_matches, all_words)
        split_segments += max(0, len(new_segments) - 1)
        refined.extend(new_segments)

    logger.info(
        "Fine cut refinement: %d -> %d segments (added %d clause splits)",
        len(segments),
        len(refined),
        split_segments,
    )

    return refined
