import logging

from app.config import get_settings
from app.models.schemas import AlignedSegment, SegmentStatus

logger = logging.getLogger(__name__)


def apply_buffer(
    segments: list[AlignedSegment],
    buffer_duration: float = 0.0,
) -> list[AlignedSegment]:
    """
    Apply buffer to cut points for smoother transitions.

    - Extends start time backward and end time forward by buffer_duration
    - Prevents overlap between adjacent segments
    - Only applies to active (non-deleted) segments
    - Returns a NEW list of deep-copied segments (originals are not mutated)
    """
    if buffer_duration <= 0:
        settings = get_settings()
        buffer_duration = settings.BUFFER_DURATION

    # Deep-copy all segments so we never mutate the caller's data
    result = [seg.model_copy(deep=True) for seg in segments]

    # Filter to only active segments and sort by start time
    active = [
        s for s in result
        if s.status not in (SegmentStatus.DELETED, SegmentStatus.UNMATCHED)
    ]
    active.sort(key=lambda s: s.start_time)

    for i, seg in enumerate(active):
        # Apply buffer to start
        new_start = max(0.0, seg.raw_start_time - buffer_duration)

        # Apply buffer to end
        new_end = seg.raw_end_time + buffer_duration

        # Prevent overlap with previous segment
        if i > 0:
            prev = active[i - 1]
            if new_start < prev.end_time:
                # Split the overlap: give half to each
                midpoint = (prev.raw_end_time + seg.raw_start_time) / 2
                prev.end_time = midpoint
                new_start = midpoint

        seg.start_time = new_start
        seg.end_time = new_end

    # Prevent overlap with next segment for the last adjustment
    for i in range(len(active) - 1):
        if active[i].end_time > active[i + 1].start_time:
            midpoint = (active[i].raw_end_time + active[i + 1].raw_start_time) / 2
            active[i].end_time = midpoint
            active[i + 1].start_time = midpoint

    return result
