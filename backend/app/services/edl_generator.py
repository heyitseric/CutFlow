import logging

from app.models.schemas import ExportClip
from app.utils.timecode import seconds_to_timecode

logger = logging.getLogger(__name__)


def generate_edl(
    segments: list[ExportClip],
    title: str = "A-Roll Rough Cut",
    frame_rate: float = 29.97,
    audio_filename: str = "audio.mp3",
    video_filename: str | None = None,
    buffer_duration: float = 0.0,
    audio_duration: float = 0.0,
) -> str:
    """
    Generate CMX 3600 EDL for audio-only timeline.

    Format:
    TITLE: <title>
    FCM: NON-DROP FRAME (or DROP FRAME for 29.97)

    001  AX       AA     C        src_in   src_out  rec_in   rec_out
    * FROM CLIP NAME: <filename>
    """
    # Determine clip name — use video filename if provided
    clip_name = video_filename if video_filename else audio_filename

    # Determine FCM
    is_drop_frame = abs(frame_rate - 29.97) < 0.01 or abs(frame_rate - 59.94) < 0.01
    fcm = "DROP FRAME" if is_drop_frame else "NON-DROP FRAME"

    lines = [
        f"TITLE: {title}",
        f"FCM: {fcm}",
        "",
    ]

    # Build record timeline: segments placed sequentially
    record_pos = 0.0
    event_num = 1

    for seg in segments:
        # Buffer is already applied by apply_buffer() in the pipeline.
        # Just clamp to valid range — do NOT re-apply buffer_duration here.
        b_start = max(0.0, seg.start_time)
        b_end = (
            min(audio_duration, seg.end_time)
            if audio_duration > 0
            else seg.end_time
        )
        duration = b_end - b_start
        if duration <= 0:
            continue

        src_in = seconds_to_timecode(b_start, frame_rate)
        src_out = seconds_to_timecode(b_end, frame_rate)

        rec_in = seconds_to_timecode(record_pos, frame_rate)
        rec_out = seconds_to_timecode(record_pos + duration, frame_rate)

        # CMX 3600 format: event# reel track trans src_in src_out rec_in rec_out
        line = f"{event_num:03d}  AX       AA/V  C        {src_in} {src_out} {rec_in} {rec_out}"
        lines.append(line)
        lines.append(f"* FROM CLIP NAME: {clip_name}")

        # Include script text as comment for reference
        if seg.script_text:
            # Truncate long text for EDL comment
            text_preview = seg.script_text[:60]
            lines.append(f"* Segment {seg.script_index}: {text_preview}")

        if seg.is_reordered:
            lines.append(f"* COMMENT: REORDERED from original position {seg.original_position}")

        lines.append("")
        record_pos += duration
        event_num += 1

    return "\n".join(lines)
