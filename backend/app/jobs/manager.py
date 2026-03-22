import logging
import math
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.models.schemas import (
    AlignedSegment,
    JobState,
    TranscriptionResult,
)

logger = logging.getLogger(__name__)

# Sentinel value to distinguish "not provided" from explicit None
_UNSET = object()


def _sanitize_float(value: Optional[float]) -> Optional[float]:
    """Replace NaN/Inf with None to prevent JSON serialization issues."""
    if value is None:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


class JobData:
    """In-memory storage for a single job."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.state: JobState = JobState.CREATED
        self.progress: float = 0.0
        self.message: str = ""
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()

        # Provider (local / volcengine)
        self.provider: str = ""

        # File paths
        self.script_path: str = ""
        self.audio_path: str = ""
        self.script_filename: str = ""
        self.audio_filename: str = ""

        # User-customisable display name (falls back to script_filename)
        self.display_name: str = ""

        # Pipeline results
        self.transcription: Optional[TranscriptionResult] = None
        self.alignment: Optional[list[AlignedSegment]] = None
        self.script_text: str = ""

        # Pre-computed SRT segmentation cache (text -> segmented list)
        self.srt_segment_cache: Optional[dict[str, list[str]]] = None

        # Export results
        self.export_files: list[str] = []

        # Error
        self.error: Optional[str] = None

        # --- Granular progress tracking ---
        self.pipeline_start_time: float = 0.0  # monotonic clock
        self.stage: int = 0
        self.stage_name: str = ""
        self.stage_detail: str = ""
        self.elapsed_seconds: float = 0.0
        self.estimated_remaining_seconds: Optional[float] = None

        # --- Sub-task tracking ---
        # Dict mapping sub-task key -> status ("pending" | "in_progress" | "completed")
        self.sub_tasks: dict[str, str] = {}

    def update(
        self,
        state: Optional[JobState] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        stage: Optional[int] = None,
        stage_name: Optional[str] = None,
        stage_detail: Optional[str] = None,
        estimated_remaining_seconds: Any = _UNSET,
        sub_tasks: Optional[dict[str, str]] = None,
    ):
        if state is not None:
            self.state = state
        if progress is not None:
            self.progress = _sanitize_float(progress) or 0.0
        if message is not None:
            self.message = message
        if stage is not None:
            self.stage = stage
        if stage_name is not None:
            self.stage_name = stage_name
        if stage_detail is not None:
            self.stage_detail = stage_detail
        if estimated_remaining_seconds is not _UNSET:
            self.estimated_remaining_seconds = _sanitize_float(
                estimated_remaining_seconds
            )
        if sub_tasks is not None:
            self.sub_tasks.update(sub_tasks)

        # Update elapsed time if pipeline has started
        if self.pipeline_start_time > 0:
            self.elapsed_seconds = time.monotonic() - self.pipeline_start_time

        self.updated_at = datetime.now()


class JobManager:
    """In-memory job state management with JSON-file persistence."""

    def __init__(self, data_dir: Optional[Path] = None):
        self._jobs: dict[str, JobData] = {}
        self._data_dir = data_dir

        # Restore persisted jobs on startup
        if data_dir:
            self._restore()

    # ── Persistence ──

    def _restore(self) -> None:
        """Load job metadata from disk on startup."""
        if not self._data_dir:
            return
        from app.jobs.persistence import dict_to_job_data, load_jobs

        saved = load_jobs(self._data_dir)
        for job_id, d in saved.items():
            try:
                job = dict_to_job_data(d, JobData)
                self._jobs[job_id] = job
            except Exception as e:
                logger.warning("Failed to restore job %s: %s", job_id, e)
        if saved:
            logger.info("Restored %d jobs from disk", len(self._jobs))

    def persist(self) -> None:
        """Flush current job metadata to disk."""
        if not self._data_dir:
            return
        from app.jobs.persistence import job_data_to_dict, save_jobs

        jobs_dict = {
            jid: job_data_to_dict(j) for jid, j in self._jobs.items()
        }
        save_jobs(self._data_dir, jobs_dict)

    # ── CRUD ──

    def create_job(self) -> JobData:
        """Create a new job and return it."""
        job_id = str(uuid.uuid4())[:8]
        job = JobData(job_id)
        self._jobs[job_id] = job
        logger.info(f"Created job {job_id}")
        self.persist()
        return job

    def get_job(self, job_id: str) -> Optional[JobData]:
        """Get job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[JobData]:
        """List all jobs."""
        return list(self._jobs.values())

    def delete_job(self, job_id: str) -> bool:
        """Delete a job from the in-memory store."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            self.persist()
            return True
        return False

    def rename_job(self, job_id: str, new_name: str) -> bool:
        """Set the user-visible display name for a job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.display_name = new_name
        job.updated_at = datetime.now()
        self.persist()
        return True

    def update_job(
        self,
        job_id: str,
        state: Optional[JobState] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        stage: Optional[int] = None,
        stage_name: Optional[str] = None,
        stage_detail: Optional[str] = None,
        estimated_remaining_seconds: Any = _UNSET,
        sub_tasks: Optional[dict[str, str]] = None,
    ) -> Optional[JobData]:
        """Update job state."""
        job = self._jobs.get(job_id)
        if job:
            old_state = job.state
            job.update(
                state=state,
                progress=progress,
                message=message,
                stage=stage,
                stage_name=stage_name,
                stage_detail=stage_detail,
                estimated_remaining_seconds=estimated_remaining_seconds,
                sub_tasks=sub_tasks,
            )
            # Persist on terminal state transitions (not on every progress tick)
            if state is not None and state != old_state:
                terminal = {JobState.REVIEW, JobState.DONE, JobState.ERROR}
                if state in terminal:
                    self.persist()
        return job


# Global singleton
_job_manager: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    global _job_manager
    if _job_manager is None:
        from app.config import get_settings
        settings = get_settings()
        _job_manager = JobManager(data_dir=settings.DATA_DIR)
    return _job_manager
