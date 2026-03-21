import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.config import get_settings
from app.jobs.manager import get_job_manager
from app.jobs.worker import run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload")
async def upload_files(
    background_tasks: BackgroundTasks,
    script: UploadFile = File(..., description="Markdown script file"),
    audio: UploadFile = File(..., description="Audio file (MP3/WAV)"),
    provider: str = Form("local", description="Transcription provider: local or cloud"),
):
    """
    Upload script (Markdown) and audio (MP3) files.
    Creates a job and starts background processing.
    """
    settings = get_settings()
    manager = get_job_manager()

    # Validate file types
    if script.filename and not script.filename.endswith((".md", ".txt", ".markdown")):
        raise HTTPException(
            status_code=400,
            detail="Script must be a Markdown file (.md, .txt, .markdown)",
        )

    audio_exts = (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac")
    if audio.filename and not audio.filename.lower().endswith(audio_exts):
        raise HTTPException(
            status_code=400,
            detail=f"Audio must be one of: {', '.join(audio_exts)}",
        )

    # Create job
    job = manager.create_job()
    job_dir = settings.UPLOAD_DIR / job.job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Save script file
    script_filename = script.filename or "script.md"
    script_path = job_dir / script_filename
    try:
        with open(script_path, "wb") as f:
            content = await script.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save script: {e}")

    # Save audio file
    audio_filename = audio.filename or "audio.mp3"
    audio_path = job_dir / audio_filename
    try:
        with open(audio_path, "wb") as f:
            content = await audio.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save audio: {e}")

    # Map frontend provider names to backend provider identifiers
    provider_map = {"cloud": "volcengine", "local": "local"}
    resolved_provider = provider_map.get(provider, provider)

    # Update job with file info
    job.script_path = str(script_path)
    job.audio_path = str(audio_path)
    job.script_filename = script_filename
    job.audio_filename = audio_filename
    job.provider = resolved_provider

    logger.info(
        f"Job {job.job_id}: uploaded script={script_filename}, audio={audio_filename}"
    )

    # Persist the newly created job immediately (before processing starts)
    manager.persist()

    # Kick off background processing
    background_tasks.add_task(run_pipeline, job)

    return {
        "job_id": job.job_id,
        "message": "Upload successful. Processing started.",
        "script_filename": script_filename,
        "audio_filename": audio_filename,
    }
