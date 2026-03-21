import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from app.models.schemas import (
    AlignedSegment,
    JobState,
    TranscriptionResult,
)

logger = logging.getLogger(__name__)


class JobData:
    """In-memory storage for a single job."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.state: JobState = JobState.CREATED
        self.progress: float = 0.0
        self.message: str = ""
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()

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

    def update(
        self,
        state: Optional[JobState] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
    ):
        if state is not None:
            self.state = state
        if progress is not None:
            self.progress = progress
        if message is not None:
            self.message = message
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
    ) -> Optional[JobData]:
        """Update job state."""
        job = self._jobs.get(job_id)
        if job:
            job.update(state=state, progress=progress, message=message)
        return job


# Global singleton
_job_manager: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager
