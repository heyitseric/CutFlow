import logging

from app.models.schemas import ExportClip
from app.utils.text_normalize import break_chinese_lines
from app.utils.timecode import seconds_to_srt_time

logger = logging.getLogger(__name__)


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


def generate_srt(
    segments: list[ExportClip],
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
    if not segments:
        return ""

    srt_lines: list[str] = []
    subtitle_num = 1

    for group, rec_start in _group_consecutive_sentence_clips(segments):
        rec_end = rec_start + sum(
            seg.end_time - seg.start_time for seg in group
        )

        text = _group_text(group, text_source)

        if not text.strip():
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
        subtitle_num += 1

    return "\n".join(srt_lines)
