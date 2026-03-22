from app.models.schemas import (
    AlignedSegment,
    ConfidenceLevel,
    SegmentStatus,
)
from app.services import clip_optimizer


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
        confidence=95.0,
        confidence_level=ConfidenceLevel.HIGH,
        status=status,
        is_reordered=(status == SegmentStatus.COPY),
        is_copy=(status == SegmentStatus.COPY),
    )


def test_optimize_segments_preserves_order_and_updates_raw_times(monkeypatch):
    monkeypatch.setattr(
        clip_optimizer,
        "find_precise_start",
        lambda *_args, **_kwargs: _args[1],
    )
    monkeypatch.setattr(
        clip_optimizer,
        "find_precise_end",
        lambda *_args, **_kwargs: _args[1],
    )

    def _split(_audio_path: str, clip_start: float, clip_end: float, **_kwargs):
        if clip_start == 3.0 and clip_end == 7.0:
            return [(3.0, 4.0), (5.0, 7.0)]
        return [(clip_start, clip_end)]

    monkeypatch.setattr(clip_optimizer, "split_clip_at_silences", _split)

    segments = [
        _segment(0, SegmentStatus.COPY, 1.0, 2.0),
        _segment(1, SegmentStatus.DELETED, 0.0, 0.0),
        _segment(2, SegmentStatus.MATCHED, 3.0, 7.0),
    ]

    optimized = clip_optimizer.optimize_segments(segments, "dummy.wav")

    assert [
        (seg.script_index, seg.status)
        for seg in optimized
    ] == [
        (0, SegmentStatus.COPY),
        (1, SegmentStatus.DELETED),
        (2, SegmentStatus.MATCHED),
        (2, SegmentStatus.MATCHED),
    ]
    assert optimized[2].start_time == 3.0
    assert optimized[2].end_time == 4.0
    assert optimized[2].raw_start_time == 3.0
    assert optimized[2].raw_end_time == 4.0
    assert optimized[3].start_time == 5.0
    assert optimized[3].end_time == 7.0
    assert optimized[3].raw_start_time == 5.0
    assert optimized[3].raw_end_time == 7.0


def test_optimize_segments_trims_tiny_overlap_between_different_sentences(monkeypatch):
    monkeypatch.setattr(
        clip_optimizer,
        "find_precise_start",
        lambda *_args, **_kwargs: _args[1],
    )
    monkeypatch.setattr(
        clip_optimizer,
        "find_precise_end",
        lambda *_args, **_kwargs: _args[1],
    )
    monkeypatch.setattr(
        clip_optimizer,
        "split_clip_at_silences",
        lambda _audio_path, clip_start, clip_end, **_kwargs: [(clip_start, clip_end)],
    )

    segments = [
        _segment(8, SegmentStatus.MATCHED, 6.446, 10.2),
        _segment(9, SegmentStatus.MATCHED, 10.08, 15.294),
        _segment(9, SegmentStatus.MATCHED, 16.051, 20.388),
    ]

    optimized = clip_optimizer.optimize_segments(segments, "dummy.wav")

    assert optimized[0].end_time == 10.08
    assert optimized[0].raw_end_time == 10.08
    assert optimized[1].start_time == 10.08
    assert optimized[1].end_time == 15.294


def test_optimize_segments_keeps_tiny_overlap_for_same_sentence(monkeypatch):
    monkeypatch.setattr(
        clip_optimizer,
        "find_precise_start",
        lambda *_args, **_kwargs: _args[1],
    )
    monkeypatch.setattr(
        clip_optimizer,
        "find_precise_end",
        lambda *_args, **_kwargs: _args[1],
    )
    monkeypatch.setattr(
        clip_optimizer,
        "split_clip_at_silences",
        lambda _audio_path, clip_start, clip_end, **_kwargs: [(clip_start, clip_end)],
    )

    segments = [
        _segment(9, SegmentStatus.MATCHED, 10.0, 12.0),
        _segment(9, SegmentStatus.MATCHED, 11.9, 14.0),
    ]

    optimized = clip_optimizer.optimize_segments(segments, "dummy.wav")

    assert optimized[0].end_time == 12.0
    assert optimized[1].start_time == 11.9
