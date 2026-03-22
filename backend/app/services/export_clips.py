from collections import defaultdict

from app.models.schemas import AlignedSegment, ExportClip, SegmentStatus


def build_export_clips(segments: list[AlignedSegment]) -> list[ExportClip]:
    """Build export-only clips from review alignment data."""
    active = [
        seg for seg in segments
        if seg.status not in (
            SegmentStatus.DELETED,
            SegmentStatus.UNMATCHED,
            SegmentStatus.REJECTED,
        )
    ]
    active.sort(key=lambda seg: seg.script_index)

    per_script_counts: defaultdict[int, int] = defaultdict(int)
    clips: list[ExportClip] = []
    for seg in active:
        clip_index = per_script_counts[seg.script_index]
        per_script_counts[seg.script_index] += 1
        clips.append(ExportClip(
            script_index=seg.script_index,
            clip_index=clip_index,
            start_time=seg.start_time,
            end_time=seg.end_time,
            script_text=seg.script_text,
            transcript_text=seg.transcript_text,
            is_reordered=seg.is_reordered,
            original_position=seg.original_position,
        ))
    return clips
