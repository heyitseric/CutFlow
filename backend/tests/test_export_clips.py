from app.models.schemas import (
    AlignedSegment,
    ConfidenceLevel,
    SegmentStatus,
)
from app.services.export_clips import build_export_clips


def _segment(
    script_index: int,
    status: SegmentStatus,
    start: float,
    end: float,
) -> AlignedSegment:
    return AlignedSegment(
        script_index=script_index,
        script_text=f"line {script_index}",
        transcript_text=f"spoken {script_index}",
        start_time=start,
        end_time=end,
        raw_start_time=start,
        raw_end_time=end,
        confidence=90.0,
        confidence_level=ConfidenceLevel.HIGH,
        status=status,
    )


def test_build_export_clips_filters_inactive_and_preserves_split_order():
    segments = [
        _segment(2, SegmentStatus.MATCHED, 4.0, 5.0),
        _segment(1, SegmentStatus.DELETED, 0.0, 0.0),
        _segment(2, SegmentStatus.MATCHED, 6.0, 7.0),
        _segment(0, SegmentStatus.COPY, 1.0, 2.0),
    ]

    clips = build_export_clips(segments)

    assert [
        (clip.script_index, clip.clip_index, clip.start_time, clip.end_time)
        for clip in clips
    ] == [
        (0, 0, 1.0, 2.0),
        (2, 0, 4.0, 5.0),
        (2, 1, 6.0, 7.0),
    ]
