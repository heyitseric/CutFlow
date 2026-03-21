import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import get_settings
from app.jobs.manager import get_job_manager
from app.models.schemas import (
    ExportFormat,
    ExportRequest,
    ExportResponse,
    JobState,
    SegmentStatus,
)
from app.services.edl_generator import generate_edl
from app.services.fcpxml_generator import generate_fcpxml
from app.services.srt_generator import generate_srt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["export"])


@router.post("/jobs/{job_id}/export", response_model=ExportResponse)
async def export_job(job_id: str, request: ExportRequest):
    """Generate EDL/FCPXML/SRT files for the job."""
    settings = get_settings()
    manager = get_job_manager()
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.alignment is None:
        raise HTTPException(status_code=400, detail="Alignment not ready")

    # Create output directory for this job
    output_dir = settings.OUTPUT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    files: list[str] = []
    audio_duration = job.transcription.duration if job.transcription else 0.0

    formats_to_generate = []
    if request.format == ExportFormat.ALL:
        formats_to_generate = [ExportFormat.EDL, ExportFormat.FCPXML, ExportFormat.SRT]
    else:
        formats_to_generate = [request.format]

    for fmt in formats_to_generate:
        if fmt == ExportFormat.EDL:
            edl_content = generate_edl(
                segments=job.alignment,
                title=f"Job_{job_id}",
                frame_rate=request.frame_rate,
                audio_filename=job.audio_filename,
            )
            edl_path = output_dir / f"{job_id}.edl"
            edl_path.write_text(edl_content, encoding="utf-8")
            files.append(f"/api/downloads/{job_id}/{job_id}.edl")
            logger.info(f"Generated EDL: {edl_path}")

        elif fmt == ExportFormat.FCPXML:
            fcpxml_content = generate_fcpxml(
                segments=job.alignment,
                title=f"Job_{job_id}",
                frame_rate=request.frame_rate,
                audio_filename=job.audio_filename,
                audio_duration=audio_duration,
            )
            fcpxml_path = output_dir / f"{job_id}.fcpxml"
            fcpxml_path.write_text(fcpxml_content, encoding="utf-8")
            files.append(f"/api/downloads/{job_id}/{job_id}.fcpxml")
            logger.info(f"Generated FCPXML: {fcpxml_path}")

        elif fmt == ExportFormat.SRT:
            srt_content = generate_srt(
                segments=job.alignment,
                text_source="script",
            )
            srt_path = output_dir / f"{job_id}.srt"
            srt_path.write_text(srt_content, encoding="utf-8")
            files.append(f"/api/downloads/{job_id}/{job_id}.srt")
            logger.info(f"Generated SRT: {srt_path}")

    # Update job state
    manager.update_job(job_id, state=JobState.DONE, message="Export complete")
    job.export_files = files

    return ExportResponse(files=files)


@router.get("/downloads/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    """Serve generated export files."""
    settings = get_settings()
    file_path = settings.OUTPUT_DIR / job_id / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Determine media type
    suffix = file_path.suffix.lower()
    media_types = {
        ".edl": "text/plain",
        ".fcpxml": "application/xml",
        ".srt": "text/plain; charset=utf-8",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type,
    )
