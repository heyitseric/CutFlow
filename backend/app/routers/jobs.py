import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.jobs.manager import get_job_manager
from app.models.schemas import JobResponse, JobStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["jobs"])


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

            # Only send updates when something changed
            if job.state != last_state or abs(job.progress - last_progress) > 0.01:
                last_state = job.state
                last_progress = job.progress

                data = {
                    "job_id": job.job_id,
                    "state": job.state.value,
                    "progress": job.progress,
                    "message": job.message,
                    "updated_at": job.updated_at.isoformat(),
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
