"""
Clip optimizer — precise cut points + internal silence removal.

Two-step optimization after alignment, before export:
1. Precise boundary detection via ffmpeg silencedetect
2. Internal silence splitting (remove dead air > 0.3s)

Reference: video-rough-cut v3 skill's optimize_clips.py
"""
import copy
import logging

from app.models.schemas import AlignedSegment, SegmentStatus
from app.services.silence_utils import (
    find_precise_end,
    find_precise_start,
    split_clip_at_silences,
)

logger = logging.getLogger(__name__)


def optimize_segments(
    segments: list[AlignedSegment],
    audio_path: str,
    min_silence: float = 0.3,
    noise_boundary: float = -35,
    noise_internal: float = -30,
) -> list[AlignedSegment]:
    """Optimize aligned segments with precise cuts and silence removal.

    Args:
        segments: Aligned segments from the pipeline
        audio_path: Path to the source audio file
        min_silence: Minimum internal silence duration to trigger split (seconds)
        noise_boundary: dB threshold for boundary detection (more sensitive)
        noise_internal: dB threshold for internal silence detection (more aggressive)

    Returns:
        Optimized list of segments (may be longer due to splits)
    """
    active_segments = [
        s for s in segments
        if s.status in (SegmentStatus.MATCHED, SegmentStatus.APPROVED)
    ]

    if not active_segments:
        logger.warning("No active segments to optimize")
        return segments

    total_before = sum(s.end_time - s.start_time for s in active_segments)
    optimized = []
    split_count = 0

    for seg in active_segments:
        # Step 1: Precise boundary detection
        precise_start = find_precise_start(
            audio_path, seg.start_time, noise_db=noise_boundary
        )
        precise_end = find_precise_end(
            audio_path, seg.end_time, noise_db=noise_boundary
        )

        # Sanity check: don't let precise adjustment shrink segment too much
        raw_duration = seg.end_time - seg.start_time
        precise_duration = precise_end - precise_start
        if precise_duration < raw_duration * 0.5:
            # Fallback: precision adjustment shrunk too much, use original
            precise_start = seg.start_time
            precise_end = seg.end_time

        # Step 2: Internal silence splitting
        sub_clips = split_clip_at_silences(
            audio_path, precise_start, precise_end,
            min_silence_duration=min_silence,
            noise_db=noise_internal,
        )

        if len(sub_clips) == 1:
            # No internal splits — just update times
            new_seg = copy.deepcopy(seg)
            new_seg.start_time = sub_clips[0][0]
            new_seg.end_time = sub_clips[0][1]
            optimized.append(new_seg)
        else:
            # Split into sub-segments
            split_count += len(sub_clips) - 1
            for i, (sub_start, sub_end) in enumerate(sub_clips):
                new_seg = copy.deepcopy(seg)
                new_seg.start_time = sub_start
                new_seg.end_time = sub_end
                # Keep script_index same for all sub-clips (they're the same sentence)
                optimized.append(new_seg)

    total_after = sum(s.end_time - s.start_time for s in optimized)
    removed = total_before - total_after

    logger.info(
        "Clip optimization: %d → %d segments, "
        "duration %.1fs → %.1fs (removed %.1fs / %.1f%%)",
        len(active_segments),
        len(optimized),
        total_before,
        total_after,
        removed,
        (removed / total_before * 100) if total_before > 0 else 0,
    )

    # Replace active segments with optimized ones, keep deleted/unmatched as-is
    inactive = [
        s for s in segments
        if s.status not in (SegmentStatus.MATCHED, SegmentStatus.APPROVED)
    ]
    return optimized + inactive
