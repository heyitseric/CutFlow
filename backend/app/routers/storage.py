"""Storage management router – disk usage stats and selective cleanup."""

import logging
import shutil
from datetime import datetime, timezone
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
    """Return ``{filename: size}`` for each file under *path* (recursive)."""
    if not path.exists():
        return {}
    result: dict[str, int] = {}
    for f in path.rglob("*"):
        if f.is_file():
            try:
                result[f.name] = f.stat().st_size
            except OSError:
                pass
    return result


def _oldest_mtime(path: Path) -> Optional[datetime]:
    """Return the earliest mtime among files under *path*."""
    if not path.exists():
        return None
    earliest: Optional[float] = None
    for f in path.rglob("*"):
        if f.is_file():
            try:
                mt = f.stat().st_mtime
                if earliest is None or mt < earliest:
                    earliest = mt
            except OSError:
                pass
    if earliest is not None:
        return datetime.fromtimestamp(earliest)
    return None


def _safe_job_dir(parent: Path, job_id: str) -> Optional[Path]:
    """Return ``parent / job_id`` only if it stays inside *parent*."""
    candidate = (parent / job_id).resolve()
    root = parent.resolve()
    # Only allow strict descendants; the root directory itself is not a valid job dir.
    if candidate != root and root in candidate.parents:
        return candidate
    return None


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
    """Return per-job and total disk usage.

    Scans ALL directories under uploads/ and outputs/, including orphan
    directories that are no longer tracked by the job manager.
    """
    settings = get_settings()
    manager = get_job_manager()

    # Build a set of known job IDs from the manager
    known_jobs = {job.job_id: job for job in manager.list_jobs()}

    # Discover ALL job-ID directories on disk (uploads + outputs)
    all_job_ids: set[str] = set()
    for parent in (settings.UPLOAD_DIR, settings.OUTPUT_DIR):
        if parent.exists():
            for child in parent.iterdir():
                if child.is_dir() and not child.name.startswith("."):
                    all_job_ids.add(child.name)

    total = 0
    job_infos: list[StorageJobInfo] = []

    for job_id in all_job_ids:
        upload_dir = settings.UPLOAD_DIR / job_id
        output_dir = settings.OUTPUT_DIR / job_id

        upload_bytes = _dir_size(upload_dir)
        output_bytes = _dir_size(output_dir)
        job_total = upload_bytes + output_bytes

        # Skip empty directories
        if job_total == 0:
            continue

        total += job_total

        files: dict[str, int] = {}
        files.update(_dir_files(upload_dir))
        files.update(_dir_files(output_dir))

        # Use metadata from the job manager if available, otherwise infer
        job = known_jobs.get(job_id)
        if job:
            display_name = getattr(job, "display_name", "") or job.script_filename
            status = job.state.value
            created_at = job.created_at.isoformat()
        else:
            # Orphan directory — derive info from files on disk
            # Use the first recognizable filename as display name
            upload_files = list(_dir_files(upload_dir).keys())
            display_name = upload_files[0] if upload_files else job_id
            status = "orphan"
            # Use earliest file mtime as creation date
            mtime = _oldest_mtime(upload_dir) or _oldest_mtime(output_dir)
            created_at = mtime.isoformat() if mtime else ""

        job_infos.append(StorageJobInfo(
            job_id=job_id,
            display_name=display_name,
            status=status,
            created_at=created_at,
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

        # For tracked jobs, don't delete if currently processing
        if job and job.state.value not in ("review", "done", "error", "created"):
            continue

        upload_dir = _safe_job_dir(settings.UPLOAD_DIR, job_id)
        output_dir = _safe_job_dir(settings.OUTPUT_DIR, job_id)
        if upload_dir is None or output_dir is None:
            logger.warning("Rejected unsafe storage cleanup job_id: %s", job_id)
            continue

        if req.delete_uploads and upload_dir.exists():
            freed += _dir_size(upload_dir)
            shutil.rmtree(upload_dir, ignore_errors=True)

        if req.delete_outputs and output_dir.exists():
            freed += _dir_size(output_dir)
            shutil.rmtree(output_dir, ignore_errors=True)

        if req.delete_job:
            if job:
                manager.delete_job(job_id)
            deleted += 1

    # Persist changes
    manager.persist()

    return CleanupResponse(
        deleted_count=deleted,
        freed_bytes=freed,
        freed_display=_format_bytes(freed),
    )
