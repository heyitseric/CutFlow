import asyncio
import json
import logging
import math
import time

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.jobs.manager import get_job_manager
from app.models.schemas import JobResponse, JobStatus, JobSummary


def _safe_round(value, ndigits=1):
    """Round a float, returning 0.0 for NaN/Inf/None."""
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return 0.0
    return round(value, ndigits)


def _safe_round_or_none(value, ndigits=1):
    """Round a float, returning None for NaN/Inf/None."""
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    return round(value, ndigits)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["jobs"])


def _job_status_label(state_value: str) -> str:
    """Map internal JobState values to simplified status labels."""
    if state_value in ("review", "done", "exporting"):
        return "completed"
    elif state_value == "error":
        return "failed"
    else:
        return "processing"


@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs():
    """Return all jobs (active and completed), newest first."""
    manager = get_job_manager()
    jobs = manager.list_jobs()
    # Sort newest first
    jobs.sort(key=lambda j: j.created_at, reverse=True)

    summaries = []
    for job in jobs:
        summaries.append(
            JobSummary(
                job_id=job.job_id,
                status=_job_status_label(job.state.value),
                progress=round(job.progress * 100, 1),
                stage_name=job.stage_name,
                script_name=job.script_filename,
                audio_name=job.audio_filename,
                created_at=job.created_at,
                elapsed_seconds=round(job.elapsed_seconds, 1),
            )
        )
    return summaries


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get full job state including alignment results."""
    manager = get_job_manager()
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobResponse(
        job_id=job.job_id,
        state=job.state,
        progress=job.progress,
        message=job.message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        script_filename=job.script_filename,
        audio_filename=job.audio_filename,
        alignment=job.alignment,
        transcription=job.transcription,
    )


@router.get("/jobs/{job_id}/status")
async def job_status_stream(job_id: str, request: Request):
    """SSE stream for real-time progress updates."""
    manager = get_job_manager()
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    async def event_generator():
        last_state = None
        last_progress = -1.0

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            job = manager.get_job(job_id)
            if not job:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "Job not found"}),
                }
                break

            # Recalculate elapsed_seconds live from pipeline_start_time
            # so it updates every tick even when the worker hasn't called update()
            live_elapsed = job.elapsed_seconds
            if job.pipeline_start_time > 0:
                live_elapsed = time.monotonic() - job.pipeline_start_time

            # Recalculate estimated remaining from live elapsed + current progress
            live_remaining = job.estimated_remaining_seconds
            if job.pipeline_start_time > 0 and job.progress > 0.05:
                total_est = live_elapsed / job.progress
                live_remaining = max(0.0, total_est - live_elapsed)

            # Send updates when state/progress changed OR periodically for elapsed time
            state_changed = job.state != last_state or abs(job.progress - last_progress) > 0.001
            if state_changed or True:  # Always send — elapsed_seconds changes every tick
                last_state = job.state
                last_progress = job.progress

                data = {
                    "job_id": job.job_id,
                    "state": job.state.value,
                    "progress": job.progress,
                    "message": job.message,
                    "updated_at": job.updated_at.isoformat(),
                    # Granular progress fields
                    "stage": job.stage,
                    "stage_name": job.stage_name,
                    "stage_detail": job.stage_detail,
                    "elapsed_seconds": _safe_round(live_elapsed),
                    "estimated_remaining_seconds": _safe_round_or_none(
                        live_remaining
                    ),
                }

                yield {
                    "event": "status",
                    "data": json.dumps(data),
                }

                # Terminal states
                if job.state.value in ("review", "done", "error"):
                    yield {
                        "event": "complete",
                        "data": json.dumps(data),
                    }
                    break

            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())
