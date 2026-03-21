from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Transcription ---

class TranscriptionWord(BaseModel):
    word: str
    start: float
    end: float
    confidence: float = 1.0


class TranscriptionSegment(BaseModel):
    text: str
    start: float
    end: float
    words: list[TranscriptionWord] = Field(default_factory=list)


class TranscriptionResult(BaseModel):
    segments: list[TranscriptionSegment]
    language: str = "zh"
    duration: float = 0.0


# --- Matching ---

class MatchResult(BaseModel):
    script_index: int
    transcript_start_word_idx: int
    transcript_end_word_idx: int
    score: float


# --- Alignment ---

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SegmentStatus(str, Enum):
    MATCHED = "matched"
    COPY = "copy"
    DELETED = "deleted"
    UNMATCHED = "unmatched"
    APPROVED = "approved"
    REJECTED = "rejected"


class PauseType(str, Enum):
    BREATH = "breath"
    NATURAL = "natural"
    THINKING = "thinking"
    LONG = "long"


class PauseAction(str, Enum):
    KEEP = "keep"
    SHORTEN = "shorten"
    REMOVE = "remove"


class PauseSegment(BaseModel):
    start: float
    end: float
    duration: float
    pause_type: PauseType
    action: PauseAction


class AlignedSegment(BaseModel):
    script_index: int
    script_text: str
    transcript_text: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    raw_start_time: float = 0.0
    raw_end_time: float = 0.0
    confidence: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    status: SegmentStatus = SegmentStatus.UNMATCHED
    is_reordered: bool = False
    original_position: Optional[int] = None
    pauses: list[PauseSegment] = Field(default_factory=list)


# --- Jobs ---

class JobState(str, Enum):
    CREATED = "created"
    TRANSCRIBING = "transcribing"
    MATCHING = "matching"
    ALIGNING = "aligning"
    REVIEW = "review"
    EXPORTING = "exporting"
    DONE = "done"
    ERROR = "error"


class JobCreate(BaseModel):
    script_filename: str = ""
    audio_filename: str = ""


class JobStatus(BaseModel):
    job_id: str
    state: JobState
    progress: float = 0.0
    message: str = ""
    created_at: datetime
    updated_at: datetime


class JobSummary(BaseModel):
    """Lightweight job info for the job list endpoint."""
    job_id: str
    status: str  # processing, completed, failed
    progress: float = 0.0
    stage_name: str = ""
    script_name: str = ""
    audio_name: str = ""
    created_at: datetime
    elapsed_seconds: float = 0.0


class JobResponse(BaseModel):
    job_id: str
    state: JobState
    progress: float = 0.0
    message: str = ""
    created_at: datetime
    updated_at: datetime
    script_filename: str = ""
    audio_filename: str = ""
    alignment: Optional[list[AlignedSegment]] = None
    transcription: Optional[TranscriptionResult] = None


# --- Alignment API ---

class AlignmentResponse(BaseModel):
    job_id: str
    segments: list[AlignedSegment]
    total_duration: float = 0.0
    matched_count: int = 0
    unmatched_count: int = 0


class AlignmentPatchRequest(BaseModel):
    segment_index: int
    status: Optional[SegmentStatus] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    transcript_text: Optional[str] = None


# --- Export ---

class ExportFormat(str, Enum):
    EDL = "edl"
    FCPXML = "fcpxml"
    SRT = "srt"
    ALL = "all"


class ExportRequest(BaseModel):
    format: ExportFormat = ExportFormat.ALL
    frame_rate: float = 29.97
    buffer_duration: float = 0.15


class ExportResponse(BaseModel):
    files: list[str] = Field(default_factory=list)


# --- Dictionary ---

class DictionaryEntry(BaseModel):
    wrong: str
    correct: str
    category: str = "general"
    added_at: datetime = Field(default_factory=datetime.now)
    frequency: int = 0


class DictionaryData(BaseModel):
    version: str = "1.0"
    entries: list[DictionaryEntry] = Field(default_factory=list)
    custom_terms: list[str] = Field(default_factory=list)


# --- Script parsing ---

class ScriptSentence(BaseModel):
    index: int
    text: str
    is_section_start: bool = False
