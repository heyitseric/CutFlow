import logging
import unicodedata
from typing import Protocol

from app.config import get_settings
from app.models.schemas import ExportClip
from app.providers.cloud.volcengine_srt import (
    SRTSegmentationError,
    VolcEngineSRTSegmenter,
)
from app.services.srt_segmenter_rules import enforce_segment_limits, split_by_rules
from app.utils.timecode import seconds_to_srt_time

logger = logging.getLogger(__name__)


class SRTSegmenter(Protocol):
    async def segment_texts(self, texts: list[str]) -> list[list[str]]:
        ...


def _group_consecutive_sentence_clips(
    segments: list[ExportClip],
) -> list[tuple[list[ExportClip], float]]:
    """Group consecutive sub-clips that belong to the same script sentence.

    Silence optimization may split one sentence into multiple export clips.
    For subtitles we want one subtitle per sentence on the edited timeline,
    not the same full sentence repeated for every tiny sub-clip.
    """
    groups: list[tuple[list[ExportClip], float]] = []

    current_group: list[ExportClip] = []
    current_start = 0.0
    record_pos = 0.0

    for seg in segments:
        duration = seg.end_time - seg.start_time
        if duration <= 0:
            continue

        if (
            current_group
            and current_group[-1].script_index == seg.script_index
            and current_group[-1].script_text == seg.script_text
        ):
            current_group.append(seg)
        else:
            if current_group:
                groups.append((current_group, current_start))
            current_group = [seg]
            current_start = record_pos

        record_pos += duration

    if current_group:
        groups.append((current_group, current_start))

    return groups


def _group_text(group: list[ExportClip], text_source: str) -> str:
    if text_source == "transcript":
        pieces = [
            seg.transcript_text or seg.script_text for seg in group
        ]
        if pieces and len(set(pieces)) == 1:
            return pieces[0]
        return "".join(pieces)
    return group[0].script_text


def _normalize_for_validation(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    return "".join(normalized.split())


def _validate_llm_segments(
    original_text: str,
    llm_segments: list[str],
) -> list[str]:
    if not llm_segments:
        raise SRTSegmentationError("Seed 返回了空的 SRT 分段结果")

    cleaned: list[str] = []
    for segment in llm_segments:
        if not isinstance(segment, str):
            raise SRTSegmentationError("Seed 返回了非文本的 SRT 分段")
        stripped = segment.strip()
        if not stripped:
            raise SRTSegmentationError("Seed 返回了空白 SRT 分段")
        cleaned.append(stripped)

    joined = "".join(cleaned)
    if joined == original_text:
        return cleaned

    if (
        len(joined) == len(original_text)
        and _normalize_for_validation(joined) == _normalize_for_validation(original_text)
    ):
        rebuilt: list[str] = []
        cursor = 0
        for segment in cleaned:
            rebuilt_segment = original_text[cursor:cursor + len(segment)]
            if not rebuilt_segment.strip():
                raise SRTSegmentationError("Seed 返回的分段边界无法映射回原文")
            rebuilt.append(rebuilt_segment)
            cursor += len(segment)
        if cursor == len(original_text) and "".join(rebuilt) == original_text:
            return rebuilt

    raise SRTSegmentationError("Seed 返回的分段无法完整还原原文")


def _infer_clip_weights(group: list[ExportClip], text_source: str) -> list[float] | None:
    if len(group) <= 1:
        return [1.0]

    if text_source == "transcript":
        pieces = [(seg.transcript_text or seg.script_text).strip() for seg in group]
        if all(pieces) and len(set(pieces)) > 1:
            return [float(len(piece)) for piece in pieces]
        return None

    transcript_pieces = [seg.transcript_text.strip() for seg in group]
    if all(transcript_pieces) and len(set(transcript_pieces)) > 1:
        return [float(len(piece)) for piece in transcript_pieces]

    return None


def _build_clip_intervals(
    group: list[ExportClip],
    rec_start: float,
    total_chars: int,
    text_source: str,
) -> list[dict]:
    durations = [max(0.0, seg.end_time - seg.start_time) for seg in group]
    total_duration = sum(durations)
    if total_duration <= 0:
        return []

    weights = _infer_clip_weights(group, text_source)
    if not weights or len(weights) != len(group) or sum(weights) <= 0:
        weights = durations if sum(durations) > 0 else [1.0] * len(group)

    weight_total = sum(weights)
    intervals: list[dict] = []
    span_cursor = 0.0
    time_cursor = rec_start

    for index, (duration, weight) in enumerate(zip(durations, weights)):
        span_end = float(total_chars) if index == len(group) - 1 else (
            span_cursor + (float(total_chars) * weight / weight_total)
        )
        time_end = time_cursor + duration
        intervals.append(
            {
                "span_start": span_cursor,
                "span_end": span_end,
                "time_start": time_cursor,
                "time_end": time_end,
            }
        )
        span_cursor = span_end
        time_cursor = time_end

    intervals[-1]["span_end"] = float(total_chars)
    intervals[-1]["time_end"] = rec_start + total_duration
    return intervals


def _position_to_time(position: float, intervals: list[dict]) -> float:
    if not intervals:
        return 0.0

    if position <= intervals[0]["span_start"]:
        return intervals[0]["time_start"]

    for interval in intervals:
        if interval["span_start"] <= position <= interval["span_end"]:
            span = interval["span_end"] - interval["span_start"]
            if span <= 1e-9:
                return interval["time_start"]
            ratio = (position - interval["span_start"]) / span
            return interval["time_start"] + ratio * (
                interval["time_end"] - interval["time_start"]
            )

    return intervals[-1]["time_end"]


def _build_timed_subtitles(
    group: list[ExportClip],
    rec_start: float,
    full_text: str,
    segmented_texts: list[str],
    text_source: str,
) -> list[tuple[float, float, str]]:
    intervals = _build_clip_intervals(group, rec_start, len(full_text), text_source)
    total_duration = sum(max(0.0, seg.end_time - seg.start_time) for seg in group)
    rec_end = rec_start + total_duration
    timed: list[tuple[float, float, str]] = []
    cursor = 0.0

    for index, text in enumerate(segmented_texts):
        start = rec_start if index == 0 else timed[-1][1]
        next_cursor = cursor + len(text)
        end = rec_end if index == len(segmented_texts) - 1 else _position_to_time(
            next_cursor,
            intervals,
        )
        if end < start:
            end = start
        timed.append((start, end, text))
        cursor = next_cursor

    if timed:
        last_start, _last_end, last_text = timed[-1]
        timed[-1] = (last_start, rec_end, last_text)

    return timed


async def precompute_srt_segments(
    segments: list,
    segmenter: SRTSegmenter | None = None,
) -> dict[str, list[str]]:
    """Pre-compute SRT text segmentation during the pipeline.

    Calls the LLM segmenter for all unique script texts and returns a
    cache mapping original text -> segmented text list.  This cache can
    be passed to ``generate_srt()`` at export time so that no LLM calls
    are needed.
    """
    from app.models.schemas import SegmentStatus

    # Collect unique texts from active segments
    active_texts: list[str] = []
    seen: set[str] = set()
    for seg in segments:
        if seg.status in (SegmentStatus.DELETED, SegmentStatus.UNMATCHED, SegmentStatus.REJECTED):
            continue
        text = seg.script_text.strip()
        if text and text not in seen:
            active_texts.append(text)
            seen.add(text)

    if not active_texts:
        return {}

    if segmenter is None:
        segmenter = VolcEngineSRTSegmenter()

    segmented = await segmenter.segment_texts(active_texts)

    settings = get_settings()
    cache: dict[str, list[str]] = {}
    for text, segs in zip(active_texts, segmented):
        try:
            validated = _validate_llm_segments(text, segs)
            cache[text] = enforce_segment_limits(
                validated,
                max_chars=settings.SRT_MAX_CHARS_PER_SEGMENT,
                min_chars=settings.SRT_MIN_CHARS_PER_SEGMENT,
            )
        except (SRTSegmentationError, ValueError):
            cache[text] = split_by_rules(
                text,
                max_chars=settings.SRT_MAX_CHARS_PER_SEGMENT,
                min_chars=settings.SRT_MIN_CHARS_PER_SEGMENT,
            )

    logger.info("Pre-computed SRT segments for %d unique texts", len(cache))
    return cache


async def generate_srt(
    segments: list[ExportClip],
    text_source: str = "script",
    segmenter: SRTSegmenter | None = None,
    segment_cache: dict[str, list[str]] | None = None,
) -> str:
    """
    Generate SRT subtitles based on the EDITED timeline (record timecode).

    CRITICAL: Timecodes are remapped so the first segment starts at 00:00:00
    and subsequent segments follow sequentially (matching the rough cut output).

    Args:
        segments: Aligned segments with timing info
        text_source: "script" (use script_text), "transcript" (use transcript_text)
        segmenter: Async LLM segmenter used only for SRT subtitle splitting
        segment_cache: Pre-computed text -> segments mapping (skips LLM calls)
    """
    if not segments:
        return ""

    prepared_groups: list[tuple[list[ExportClip], float, str]] = []
    for group, rec_start in _group_consecutive_sentence_clips(segments):
        text = _group_text(group, text_source)
        if text.strip():
            prepared_groups.append((group, rec_start, text))

    if not prepared_groups:
        return ""

    # Use cache if available, otherwise fall back to LLM segmenter
    settings = get_settings()
    from_cache: set[str] = set()
    if segment_cache is not None:
        segmented_groups: list[list[str]] = []
        for _group, _rec_start, text in prepared_groups:
            cached = segment_cache.get(text.strip())
            if cached is not None:
                segmented_groups.append(cached)
                from_cache.add(text.strip())
            else:
                segmented_groups.append(split_by_rules(
                    text,
                    max_chars=settings.SRT_MAX_CHARS_PER_SEGMENT,
                    min_chars=settings.SRT_MIN_CHARS_PER_SEGMENT,
                ))
    else:
        if segmenter is None:
            segmenter = VolcEngineSRTSegmenter()
        segmented_groups = await segmenter.segment_texts(
            [text for _group, _rec_start, text in prepared_groups]
        )

    if len(segmented_groups) != len(prepared_groups):
        raise SRTSegmentationError("Seed 返回的 SRT 分段数量与输入不一致")

    srt_lines: list[str] = []
    subtitle_num = 1

    for (group, rec_start, text), raw_segments in zip(prepared_groups, segmented_groups):
        # Cache hits were already validated+enforced in precompute_srt_segments
        if text.strip() in from_cache:
            validated_segments = raw_segments
        else:
            try:
                validated_segments = _validate_llm_segments(text, raw_segments)
                validated_segments = enforce_segment_limits(
                    validated_segments,
                    max_chars=settings.SRT_MAX_CHARS_PER_SEGMENT,
                    min_chars=settings.SRT_MIN_CHARS_PER_SEGMENT,
                )
            except (SRTSegmentationError, ValueError):
                validated_segments = split_by_rules(
                    text,
                    max_chars=settings.SRT_MAX_CHARS_PER_SEGMENT,
                    min_chars=settings.SRT_MIN_CHARS_PER_SEGMENT,
                )
        for seg_start, seg_end, subtitle_text in _build_timed_subtitles(
            group,
            rec_start,
            text,
            validated_segments,
            text_source,
        ):
            srt_lines.append(str(subtitle_num))
            srt_lines.append(
                f"{seconds_to_srt_time(seg_start)} --> {seconds_to_srt_time(seg_end)}"
            )
            srt_lines.append(subtitle_text)
            srt_lines.append("")
            subtitle_num += 1

    return "\n".join(srt_lines)
