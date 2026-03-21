import logging

from fastapi import APIRouter, HTTPException

from app.jobs.manager import get_job_manager
from app.models.schemas import (
    AlignmentPatchRequest,
    AlignmentResponse,
    ConfidenceLevel,
    JobState,
    SegmentStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["alignment"])


@router.get("/jobs/{job_id}/alignment", response_model=AlignmentResponse)
async def get_alignment(job_id: str):
    """Get alignment results for a job."""
    manager = get_job_manager()
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.alignment is None:
        if job.state == JobState.ERROR:
            raise HTTPException(
                status_code=400,
                detail=f"Job failed: {job.error or 'Unknown error'}",
            )
        raise HTTPException(
            status_code=400,
            detail=f"Alignment not ready. Job state: {job.state.value}",
        )

    matched = sum(
        1 for s in job.alignment
        if s.status in (SegmentStatus.MATCHED, SegmentStatus.COPY, SegmentStatus.APPROVED)
    )
    unmatched = sum(
        1 for s in job.alignment
        if s.status in (SegmentStatus.DELETED, SegmentStatus.UNMATCHED, SegmentStatus.REJECTED)
    )
    total_duration = sum(
        s.end_time - s.start_time
        for s in job.alignment
        if s.status not in (SegmentStatus.DELETED, SegmentStatus.UNMATCHED, SegmentStatus.REJECTED)
    )

    return AlignmentResponse(
        job_id=job_id,
        segments=job.alignment,
        total_duration=total_duration,
        matched_count=matched,
        unmatched_count=unmatched,
    )


@router.patch("/jobs/{job_id}/alignment")
async def patch_alignment(job_id: str, patch: AlignmentPatchRequest):
    """
    Manually edit alignment:
    - Approve/reject segments
    - Adjust timestamps
    - Update transcript text
    """
    manager = get_job_manager()
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.alignment is None:
        raise HTTPException(status_code=400, detail="Alignment not ready")

    if patch.segment_index < 0 or patch.segment_index >= len(job.alignment):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid segment index: {patch.segment_index}",
        )

    segment = job.alignment[patch.segment_index]

    if patch.status is not None:
        segment.status = patch.status
        logger.info(
            f"Job {job_id}: segment {patch.segment_index} status -> {patch.status.value}"
        )

    if patch.start_time is not None:
        segment.start_time = patch.start_time

    if patch.end_time is not None:
        segment.end_time = patch.end_time

    if patch.transcript_text is not None:
        segment.transcript_text = patch.transcript_text

    return {
        "message": "Segment updated",
        "segment_index": patch.segment_index,
        "segment": segment,
    }
