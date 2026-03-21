import logging

from app.models.schemas import AlignedSegment, SegmentStatus
from app.utils.timecode import seconds_to_timecode

logger = logging.getLogger(__name__)


def generate_edl(
    segments: list[AlignedSegment],
    title: str = "A-Roll Rough Cut",
    frame_rate: float = 29.97,
    audio_filename: str = "audio.mp3",
) -> str:
    """
    Generate CMX 3600 EDL for audio-only timeline.

    Format:
    TITLE: <title>
    FCM: NON-DROP FRAME (or DROP FRAME for 29.97)

    001  AX       AA     C        src_in   src_out  rec_in   rec_out
    * FROM CLIP NAME: <filename>
    """
    # Determine FCM
    is_drop_frame = abs(frame_rate - 29.97) < 0.01 or abs(frame_rate - 59.94) < 0.01
    fcm = "DROP FRAME" if is_drop_frame else "NON-DROP FRAME"

    lines = [
        f"TITLE: {title}",
        f"FCM: {fcm}",
        "",
    ]

    # Filter to active segments, sorted by script order
    active = [
        s for s in segments
        if s.status not in (SegmentStatus.DELETED, SegmentStatus.UNMATCHED, SegmentStatus.REJECTED)
    ]
    active.sort(key=lambda s: s.script_index)

    # Build record timeline: segments placed sequentially
    record_pos = 0.0
    event_num = 1

    for seg in active:
        src_in = seconds_to_timecode(seg.start_time, frame_rate)
        src_out = seconds_to_timecode(seg.end_time, frame_rate)

        duration = seg.end_time - seg.start_time
        rec_in = seconds_to_timecode(record_pos, frame_rate)
        rec_out = seconds_to_timecode(record_pos + duration, frame_rate)

        # CMX 3600 format: event# reel track trans src_in src_out rec_in rec_out
        line = f"{event_num:03d}  AX       AA     C        {src_in} {src_out} {rec_in} {rec_out}"
        lines.append(line)
        lines.append(f"* FROM CLIP NAME: {audio_filename}")

        if seg.is_reordered:
            lines.append(f"* COMMENT: REORDERED from original position {seg.original_position}")

        lines.append("")
        record_pos += duration
        event_num += 1

    return "\n".join(lines)
