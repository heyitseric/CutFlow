import copy
import logging
import re
from typing import Protocol

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


class ChunkDecider(Protocol):
    async def decide(
        self,
        *,
        script_text: str,
        transcript_chunks: list[dict],
        prev_script: str = "",
        next_script: str = "",
    ) -> list[dict]:
        ...


def _clean_text(text: str) -> str:
    return _CLEAN_RE.sub("", text)


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


def _chunk_segment_words(
    all_words: list[dict],
    start_idx: int,
    end_idx: int,
) -> list[dict]:
    if start_idx >= end_idx:
        return []

    chunks: list[dict] = []
    chunk_start = start_idx
    clean_chars = 0

    for idx in range(start_idx, end_idx):
        clean_chars += max(1, len(_clean_text(all_words[idx]["word"])))
        is_last = idx == end_idx - 1
        gap_to_next = 0.0
        if not is_last:
            gap_to_next = all_words[idx + 1]["start"] - all_words[idx]["end"]

        duration = all_words[idx]["end"] - all_words[chunk_start]["start"]

        should_break = (
            is_last
            or gap_to_next >= 0.28
            or (clean_chars >= 10 and gap_to_next >= 0.12)
            or clean_chars >= 16
            or (duration >= 1.6 and gap_to_next >= 0.05)
        )

        if not should_break:
            continue

        chunk_end = idx + 1
        chunks.append(
            {
                "start_idx": chunk_start,
                "end_idx": chunk_end,
                "text": _join_words(all_words, chunk_start, chunk_end),
                "start_time": all_words[chunk_start]["start"],
                "end_time": all_words[chunk_end - 1]["end"],
            }
        )
        chunk_start = chunk_end
        clean_chars = 0

    if len(chunks) <= 1:
        return chunks

    merged: list[dict] = [chunks[0]]
    for chunk in chunks[1:]:
        prev = merged[-1]
        gap = chunk["start_time"] - prev["end_time"]
        if len(_clean_text(prev["text"])) < 4 and gap <= 0.12:
            prev["end_idx"] = chunk["end_idx"]
            prev["text"] += chunk["text"]
            prev["end_time"] = chunk["end_time"]
        else:
            merged.append(chunk)

    return merged


def _local_keep_remove(script_text: str, chunks: list[dict]) -> list[dict]:
    clean_script = _clean_text(script_text)
    decisions: list[dict] = []
    cursor = 0

    for chunk in chunks:
        chunk_text = _clean_text(chunk["text"])
        if not chunk_text:
            decisions.append({"idx": chunk["idx"], "action": "REMOVE"})
            continue

        min_window = max(1, len(chunk_text) - 3)
        max_window = min(len(clean_script), len(chunk_text) + 6)

        best_score = -1.0
        best_start = 0
        best_end = 0

        for window_size in range(min_window, max_window + 1):
            for start in range(0, max(1, len(clean_script) - window_size + 1)):
                end = start + window_size
                candidate = clean_script[start:end]
                ratio = fuzz.ratio(chunk_text, candidate)
                partial = (
                    fuzz.partial_ratio(chunk_text, candidate)
                    if len(candidate) >= len(chunk_text)
                    else ratio
                )
                distance_penalty = abs(start - cursor) * 2.0
                backward_penalty = max(0, cursor - end) * 5.0
                score = max(ratio, partial) - distance_penalty - backward_penalty

                if score > best_score:
                    best_score = score
                    best_start = start
                    best_end = end

        advances_script = best_end > cursor + 1
        near_cursor = best_start <= cursor + 4
        high_confidence = best_score >= 78
        very_high_confidence = best_score >= 88

        if advances_script and ((near_cursor and high_confidence) or very_high_confidence):
            decisions.append({"idx": chunk["idx"], "action": "KEEP"})
            cursor = max(cursor, best_end)
        else:
            decisions.append({"idx": chunk["idx"], "action": "REMOVE"})

    return decisions


def _is_suspicious_segment(seg: AlignedSegment, chunks: list[dict]) -> bool:
    if len(chunks) < 2:
        return False

    clean_script = _clean_text(seg.script_text)
    clean_transcript = _clean_text(seg.transcript_text)
    ratio = fuzz.partial_ratio(clean_script, clean_transcript) if clean_script and clean_transcript else 0.0

    return (
        len(clean_transcript) > len(clean_script) + 6
        or len(clean_transcript) > len(clean_script) * 1.12
        or ratio < 94
        or (seg.end_time - seg.start_time) > 3.0
    )


def _apply_decisions(
    seg: AlignedSegment,
    chunks: list[dict],
    decisions: list[dict],
    all_words: list[dict],
) -> list[AlignedSegment]:
    decision_map = {item["idx"]: item["action"] for item in decisions}
    kept = [chunk for chunk in chunks if decision_map.get(chunk["idx"], "KEEP") == "KEEP"]

    if not kept or len(kept) == len(chunks):
        return [copy.deepcopy(seg)]

    clean_script = _clean_text(seg.script_text)
    kept_text = _clean_text("".join(chunk["text"] for chunk in kept))
    if not kept_text:
        return [copy.deepcopy(seg)]

    keep_score = fuzz.partial_ratio(clean_script, kept_text)
    if keep_score < 78:
        logger.warning(
            "Semantic fine cut rejected low-confidence trim for script[%d] (score %.1f)",
            seg.script_index,
            keep_score,
        )
        return [copy.deepcopy(seg)]

    groups: list[dict] = []
    for chunk in kept:
        if not groups:
            groups.append(chunk.copy())
            continue

        prev = groups[-1]
        gap = chunk["start_time"] - prev["end_time"]
        if gap <= 0.18:
            prev["end_idx"] = chunk["end_idx"]
            prev["text"] += chunk["text"]
            prev["end_time"] = chunk["end_time"]
        else:
            groups.append(chunk.copy())

    refined: list[AlignedSegment] = []
    for group in groups:
        new_seg = copy.deepcopy(seg)
        new_seg.transcript_text = group["text"]
        new_seg.start_time = group["start_time"]
        new_seg.end_time = group["end_time"]
        new_seg.raw_start_time = group["start_time"]
        new_seg.raw_end_time = group["end_time"]
        refined.append(new_seg)

    return refined


class SemanticFineCutService:
    def __init__(
        self,
        decider: ChunkDecider | None = None,
        max_llm_segments: int = 24,
    ):
        self.decider = decider
        self.max_llm_segments = max_llm_segments

    async def refine(
        self,
        segments: list[AlignedSegment],
        transcription: TranscriptionResult,
    ) -> list[AlignedSegment]:
        if not segments or not transcription.segments:
            return [copy.deepcopy(seg) for seg in segments]

        all_words = _flatten_words(transcription)
        if not all_words:
            return [copy.deepcopy(seg) for seg in segments]

        refined: list[AlignedSegment] = []
        llm_calls = 0
        trimmed_groups = 0

        for index, seg in enumerate(segments):
            if seg.status not in _ACTIVE_STATUSES or not seg.transcript_text.strip():
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

            chunks = _chunk_segment_words(all_words, word_range[0], word_range[1])
            if len(chunks) < 2:
                refined.append(copy.deepcopy(seg))
                continue

            for chunk_idx, chunk in enumerate(chunks):
                chunk["idx"] = chunk_idx

            decisions = _local_keep_remove(seg.script_text, chunks)

            if self.decider and _is_suspicious_segment(seg, chunks) and llm_calls < self.max_llm_segments:
                try:
                    prev_script = segments[index - 1].script_text if index > 0 else ""
                    next_script = segments[index + 1].script_text if index + 1 < len(segments) else ""
                    llm_decisions = await self.decider.decide(
                        script_text=seg.script_text,
                        transcript_chunks=[
                            {
                                "idx": chunk["idx"],
                                "text": chunk["text"],
                                "start_time": chunk["start_time"],
                                "end_time": chunk["end_time"],
                            }
                            for chunk in chunks
                        ],
                        prev_script=prev_script,
                        next_script=next_script,
                    )
                except Exception as exc:
                    logger.warning("Semantic fine cut LLM failed, falling back to local: %s", exc)
                else:
                    if llm_decisions:
                        decisions = llm_decisions
                        llm_calls += 1

            new_segments = _apply_decisions(seg, chunks, decisions, all_words)
            trimmed_groups += max(0, len(new_segments) - 1)
            refined.extend(new_segments)

        logger.info(
            "Semantic fine cut: %d -> %d segments, LLM calls=%d, added splits=%d",
            len(segments),
            len(refined),
            llm_calls,
            trimmed_groups,
        )
        return refined
