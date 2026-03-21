"""Storage management router – disk usage stats and selective cleanup."""

import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.jobs.manager import get_job_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["storage"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_bytes(n: int) -> str:
    """Human-readable byte size."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} TB"


def _dir_size(path: Path) -> int:
    """Recursively sum file sizes under *path*."""
    if not path.exists():
        return 0
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


def _dir_files(path: Path) -> dict[str, int]:
    """Return ``{filename: size}`` for each file directly under *path*."""
    if not path.exists():
        return {}
    result: dict[str, int] = {}
    for f in path.iterdir():
        if f.is_file():
            try:
                result[f.name] = f.stat().st_size
            except OSError:
                pass
    return result


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class StorageJobInfo(BaseModel):
    job_id: str
    display_name: str = ""
    status: str = ""
    created_at: str = ""
    upload_bytes: int = 0
    output_bytes: int = 0
    total_bytes: int = 0
    total_display: str = ""
    files: dict[str, int] = {}


class StorageStats(BaseModel):
    total_bytes: int = 0
    total_display: str = ""
    jobs: list[StorageJobInfo] = []


class CleanupRequest(BaseModel):
    job_ids: list[str]
    delete_uploads: bool = True
    delete_outputs: bool = True
    delete_job: bool = True


class CleanupResponse(BaseModel):
    deleted_count: int = 0
    freed_bytes: int = 0
    freed_display: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/storage/stats", response_model=StorageStats)
async def storage_stats():
    """Return per-job and total disk usage."""
    settings = get_settings()
    manager = get_job_manager()
    jobs = manager.list_jobs()

    total = 0
    job_infos: list[StorageJobInfo] = []

    for job in jobs:
        upload_dir = settings.UPLOAD_DIR / job.job_id
        output_dir = settings.OUTPUT_DIR / job.job_id

        upload_bytes = _dir_size(upload_dir)
        output_bytes = _dir_size(output_dir)
        job_total = upload_bytes + output_bytes
        total += job_total

        files: dict[str, int] = {}
        files.update(_dir_files(upload_dir))
        files.update(_dir_files(output_dir))

        job_infos.append(StorageJobInfo(
            job_id=job.job_id,
            display_name=getattr(job, "display_name", "") or job.script_filename,
            status=job.state.value,
            created_at=job.created_at.isoformat(),
            upload_bytes=upload_bytes,
            output_bytes=output_bytes,
            total_bytes=job_total,
            total_display=_format_bytes(job_total),
            files=files,
        ))

    # Sort by total_bytes descending
    job_infos.sort(key=lambda j: j.total_bytes, reverse=True)

    return StorageStats(
        total_bytes=total,
        total_display=_format_bytes(total),
        jobs=job_infos,
    )


@router.post("/storage/cleanup", response_model=CleanupResponse)
async def storage_cleanup(req: CleanupRequest):
    """Selectively delete job files and/or job metadata."""
    settings = get_settings()
    manager = get_job_manager()

    deleted = 0
    freed = 0

    for job_id in req.job_ids:
        job = manager.get_job(job_id)
        if not job:
            continue

        # Don't delete jobs that are currently processing
        if job.state.value not in ("review", "done", "error", "created"):
            continue

        upload_dir = settings.UPLOAD_DIR / job_id
        output_dir = settings.OUTPUT_DIR / job_id

        if req.delete_uploads and upload_dir.exists():
            freed += _dir_size(upload_dir)
            shutil.rmtree(upload_dir, ignore_errors=True)

        if req.delete_outputs and output_dir.exists():
            freed += _dir_size(output_dir)
            shutil.rmtree(output_dir, ignore_errors=True)

        if req.delete_job:
            manager.delete_job(job_id)
            deleted += 1

    # Persist changes
    manager.persist()

    return CleanupResponse(
        deleted_count=deleted,
        freed_bytes=freed,
        freed_display=_format_bytes(freed),
    )
