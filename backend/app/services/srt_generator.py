import logging

from app.models.schemas import AlignedSegment, SegmentStatus
from app.utils.text_normalize import break_chinese_lines
from app.utils.timecode import seconds_to_srt_time

logger = logging.getLogger(__name__)


def generate_srt(
    segments: list[AlignedSegment],
    text_source: str = "script",
    max_chars_per_line: int = 18,
) -> str:
    """
    Generate SRT subtitles based on the EDITED timeline (record timecode).

    CRITICAL: Timecodes are remapped so the first segment starts at 00:00:00
    and subsequent segments follow sequentially (matching the rough cut output).

    Args:
        segments: Aligned segments with timing info
        text_source: "script" (use script_text), "transcript" (use transcript_text)
        max_chars_per_line: Max characters per subtitle line (default 18 for Chinese)
    """
    # Filter to active segments, sorted by script order
    active = [
        s for s in segments
        if s.status not in (SegmentStatus.DELETED, SegmentStatus.UNMATCHED, SegmentStatus.REJECTED)
    ]
    active.sort(key=lambda s: s.script_index)

    if not active:
        return ""

    srt_lines: list[str] = []
    record_pos = 0.0
    subtitle_num = 1

    for seg in active:
        duration = seg.end_time - seg.start_time
        if duration <= 0:
            continue

        # Record timecodes (edited timeline)
        rec_start = record_pos
        rec_end = record_pos + duration

        # Choose text source
        if text_source == "transcript":
            text = seg.transcript_text or seg.script_text
        else:
            text = seg.script_text

        if not text.strip():
            record_pos = rec_end
            continue

        # Break long Chinese text into multiple lines
        lines = break_chinese_lines(text, max_chars_per_line)
        subtitle_text = "\n".join(lines)

        # SRT format
        srt_lines.append(str(subtitle_num))
        srt_lines.append(
            f"{seconds_to_srt_time(rec_start)} --> {seconds_to_srt_time(rec_end)}"
        )
        srt_lines.append(subtitle_text)
        srt_lines.append("")

        record_pos = rec_end
        subtitle_num += 1

    return "\n".join(srt_lines)
