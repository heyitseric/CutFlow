import logging
import math
import time
import uuid
from datetime import datetime
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

        # Pipeline results
        self.transcription: Optional[TranscriptionResult] = None
        self.alignment: Optional[list[AlignedSegment]] = None
        self.script_text: str = ""

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

    def update(
        self,
        state: Optional[JobState] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        stage: Optional[int] = None,
        stage_name: Optional[str] = None,
        stage_detail: Optional[str] = None,
        estimated_remaining_seconds: Any = _UNSET,
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

        # Update elapsed time if pipeline has started
        if self.pipeline_start_time > 0:
            self.elapsed_seconds = time.monotonic() - self.pipeline_start_time

        self.updated_at = datetime.now()


class JobManager:
    """In-memory job state management."""

    def __init__(self):
        self._jobs: dict[str, JobData] = {}

    def create_job(self) -> JobData:
        """Create a new job and return it."""
        job_id = str(uuid.uuid4())[:8]
        job = JobData(job_id)
        self._jobs[job_id] = job
        logger.info(f"Created job {job_id}")
        return job

    def get_job(self, job_id: str) -> Optional[JobData]:
        """Get job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[JobData]:
        """List all jobs."""
        return list(self._jobs.values())

    def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

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
    ) -> Optional[JobData]:
        """Update job state."""
        job = self._jobs.get(job_id)
        if job:
            job.update(
                state=state,
                progress=progress,
                message=message,
                stage=stage,
                stage_name=stage_name,
                stage_detail=stage_detail,
                estimated_remaining_seconds=estimated_remaining_seconds,
            )
        return job


# Global singleton
_job_manager: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager
