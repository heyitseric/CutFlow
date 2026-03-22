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
from app.providers.cloud.volcengine_srt import SRTSegmentationError
from app.services.edl_generator import generate_edl
from app.services.export_clips import build_export_clips
from app.services.fcpxml_generator import generate_fcpxml
from app.services.srt_generator import generate_srt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["export"])


def _compute_export_audio_duration(job) -> float:
    transcription_duration = job.transcription.duration if job.transcription else 0.0
    aligned_end = max(
        (seg.end_time for seg in job.alignment or []),
        default=0.0,
    )
    return max(transcription_duration, aligned_end)


def _resolve_requested_formats(request: ExportRequest) -> set[ExportFormat]:
    if request.formats:
        return set(request.formats)
    if request.format == ExportFormat.ALL:
        return {ExportFormat.EDL, ExportFormat.FCPXML, ExportFormat.SRT}
    return {request.format}


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
    audio_duration = _compute_export_audio_duration(job)
    export_clips = build_export_clips(job.alignment)
    requested_formats = _resolve_requested_formats(request)

    # EDL
    if ExportFormat.EDL in requested_formats:
        edl_content = generate_edl(
            segments=export_clips,
            title=f"Job_{job_id}",
            frame_rate=request.frame_rate,
            audio_filename=job.audio_filename,
            video_filename=request.video_filename,
            buffer_duration=request.buffer_duration,
            audio_duration=audio_duration,
        )
        edl_path = output_dir / f"{job_id}.edl"
        edl_path.write_text(edl_content, encoding="utf-8")
        files.append(f"/api/downloads/{job_id}/{job_id}.edl")
        logger.info(f"Generated EDL: {edl_path}")

    # FCPXML
    if ExportFormat.FCPXML in requested_formats:
        fcpxml_content = generate_fcpxml(
            segments=export_clips,
            title=f"Job_{job_id}",
            frame_rate=request.frame_rate,
            audio_filename=job.audio_filename,
            audio_duration=audio_duration,
            video_filename=request.video_filename,
            buffer_duration=request.buffer_duration,
        )
        fcpxml_path = output_dir / f"{job_id}.fcpxml"
        fcpxml_path.write_text(fcpxml_content, encoding="utf-8")
        files.append(f"/api/downloads/{job_id}/{job_id}.fcpxml")
        logger.info(f"Generated FCPXML: {fcpxml_path}")

    # SRT
    if ExportFormat.SRT in requested_formats:
        try:
            srt_content = await generate_srt(
                segments=export_clips,
                text_source=request.subtitle_source if request.subtitle_source != "llm_corrected" else "script",
                segment_cache=job.srt_segment_cache,
            )
        except SRTSegmentationError as exc:
            logger.warning("Failed to generate SRT for job %s: %s", job_id, exc)
            raise HTTPException(status_code=502, detail=f"SRT 导出失败：{exc}") from exc
        srt_path = output_dir / f"{job_id}.srt"
        srt_path.write_text(srt_content, encoding="utf-8")
        files.append(f"/api/downloads/{job_id}/{job_id}.srt")
        logger.info(f"Generated SRT: {srt_path}")

    # Update job state
    manager.update_job(job_id, state=JobState.DONE, message="Export complete")
    job.export_files = files

    return ExportResponse(files=files)


@router.get("/jobs/{job_id}/export/download")
async def download_export(job_id: str, format: str):
    """Download a generated export file by format (edl, fcpxml, srt)."""
    settings = get_settings()
    allowed_formats = {"edl", "fcpxml", "srt"}
    if format not in allowed_formats:
        raise HTTPException(status_code=400, detail=f"Invalid format: {format}")

    filename = f"{job_id}.{format}"
    file_path = settings.OUTPUT_DIR / job_id / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Export file not found: {filename}")

    # Determine media type
    media_types = {
        "edl": "text/plain",
        "fcpxml": "application/xml",
        "srt": "text/plain; charset=utf-8",
    }
    media_type = media_types.get(format, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type,
    )


@router.get("/downloads/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    """Serve generated export files (legacy URL)."""
    # Security: prevent path traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if '..' in job_id or '/' in job_id or '\\' in job_id:
        raise HTTPException(status_code=400, detail="Invalid job ID")

    settings = get_settings()
    file_path = (settings.OUTPUT_DIR / job_id / filename).resolve()

    # Ensure resolved path stays within OUTPUT_DIR
    if not str(file_path).startswith(str(settings.OUTPUT_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")

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
