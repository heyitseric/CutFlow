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


def _trim_tiny_cross_sentence_overlaps(
    segments: list[AlignedSegment],
    active_statuses: tuple[SegmentStatus, ...],
    max_overlap: float = 0.2,
) -> None:
    """Remove tiny overlaps between neighboring script sentences.

    Precise boundary snapping can occasionally make two adjacent sentences
    touch or overlap by a fraction of a second. That creates audible
    repetition in editors even though the overlap is tiny. We only trim when
    the overlap is small and the clips belong to different script sentences.
    """
    previous_active: AlignedSegment | None = None

    for seg in segments:
        if seg.status not in active_statuses:
            continue

        if previous_active is None:
            previous_active = seg
            continue

        if previous_active.script_index == seg.script_index:
            previous_active = seg
            continue

        overlap = previous_active.end_time - seg.start_time
        if 0 < overlap <= max_overlap:
            new_end = max(previous_active.start_time, seg.start_time)
            logger.info(
                "Trimmed tiny cross-sentence overlap %.3fs between "
                "script[%d] and script[%d]",
                overlap,
                previous_active.script_index,
                seg.script_index,
            )
            previous_active.end_time = new_end
            previous_active.raw_end_time = new_end

        previous_active = seg


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
    active_statuses = (
        SegmentStatus.MATCHED,
        SegmentStatus.COPY,
        SegmentStatus.APPROVED,
    )
    active_segments = [
        s for s in segments
        if s.status in active_statuses
    ]

    if not active_segments:
        logger.warning("No active segments to optimize")
        return [copy.deepcopy(seg) for seg in segments]

    total_before = sum(s.end_time - s.start_time for s in active_segments)
    optimized: list[AlignedSegment] = []
    split_count = 0

    for seg in segments:
        if seg.status not in active_statuses:
            optimized.append(copy.deepcopy(seg))
            continue

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

        if len(sub_clips) > 1:
            split_count += len(sub_clips) - 1

        for sub_start, sub_end in sub_clips:
            new_seg = copy.deepcopy(seg)
            # After waveform-based optimization, these become the source of truth.
            new_seg.start_time = sub_start
            new_seg.end_time = sub_end
            new_seg.raw_start_time = sub_start
            new_seg.raw_end_time = sub_end
            # Keep script_index the same for all sub-clips (same sentence).
            optimized.append(new_seg)

    _trim_tiny_cross_sentence_overlaps(optimized, active_statuses)

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

    return optimized
