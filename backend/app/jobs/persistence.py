"""JSON-file-based persistence for job metadata.

Persists lightweight job metadata to ``data/jobs.json`` so that job history
survives server restarts.  Large data (alignment, transcription) is NOT
stored here – it lives in per-job output directories.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_JOBS_FILE = "jobs.json"


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _dt_to_str(dt: datetime) -> str:
    return dt.isoformat()


def _str_to_dt(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return datetime.now()


def job_data_to_dict(job: Any) -> dict:
    """Serialize a *JobData* instance to a JSON-safe dict.

    Only lightweight metadata is stored – transient runtime fields
    (``pipeline_start_time``, ``sub_tasks``, ``elapsed_seconds``, …) and
    heavy data (``transcription``, ``alignment``) are excluded.
    """
    return {
        "job_id": job.job_id,
        "state": job.state.value,
        "progress": job.progress,
        "message": job.message,
        "created_at": _dt_to_str(job.created_at),
        "updated_at": _dt_to_str(job.updated_at),
        "provider": job.provider,
        "script_path": job.script_path,
        "audio_path": job.audio_path,
        "script_filename": job.script_filename,
        "audio_filename": job.audio_filename,
        "display_name": getattr(job, "display_name", ""),
        "export_files": list(job.export_files),
        "error": job.error,
        "script_text": job.script_text,
    }


def dict_to_job_data(d: dict, job_cls: type) -> Any:
    """Reconstruct a *JobData* from a persisted dict.

    For jobs that were mid-processing when the server shut down (non-terminal
    states), we mark them as *error* because in-progress pipelines cannot be
    resumed.
    """
    from app.models.schemas import JobState

    job = job_cls(d["job_id"])
    job.created_at = _str_to_dt(d.get("created_at", ""))
    job.updated_at = _str_to_dt(d.get("updated_at", ""))
    job.provider = d.get("provider", "")
    job.script_path = d.get("script_path", "")
    job.audio_path = d.get("audio_path", "")
    job.script_filename = d.get("script_filename", "")
    job.audio_filename = d.get("audio_filename", "")
    job.display_name = d.get("display_name", "")
    job.export_files = d.get("export_files", [])
    job.error = d.get("error")
    job.script_text = d.get("script_text", "")
    job.message = d.get("message", "")
    job.progress = d.get("progress", 0.0)

    # Restore state – mark interrupted jobs as error
    raw_state = d.get("state", "created")
    terminal = {"review", "done", "error"}
    if raw_state in terminal:
        job.state = JobState(raw_state)
    else:
        job.state = JobState.ERROR
        job.error = job.error or "服务器重启，任务中断"
        job.message = "服务器重启，任务中断"
        job.progress = 0.0

    return job


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def load_jobs(data_dir: Path) -> dict:
    """Read ``jobs.json`` and return a ``{job_id: dict}`` mapping."""
    path = data_dir / _JOBS_FILE
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data.get("jobs", {})
    except Exception as e:
        logger.warning("Failed to load jobs.json – starting fresh: %s", e)
        return {}


def save_jobs(data_dir: Path, jobs_dict: dict) -> None:
    """Atomically write job metadata to ``jobs.json``.

    Writes to a temporary file first, then renames to avoid corruption.
    """
    path = data_dir / _JOBS_FILE
    tmp_path = data_dir / f"{_JOBS_FILE}.tmp"
    payload = {
        "version": 1,
        "jobs": jobs_dict,
    }
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(str(tmp_path), str(path))
    except Exception as e:
        logger.error("Failed to save jobs.json: %s", e)
