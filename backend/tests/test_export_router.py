from types import SimpleNamespace

from app.models.schemas import (
    AlignedSegment,
    ConfidenceLevel,
    SegmentStatus,
    TranscriptionResult,
)
from app.routers.export import _compute_export_audio_duration


def test_compute_export_audio_duration_uses_alignment_end_when_longer():
    job = SimpleNamespace(
        transcription=TranscriptionResult(segments=[], duration=9.5),
        alignment=[
            AlignedSegment(
                script_index=0,
                script_text="tail",
                transcript_text="tail",
                start_time=8.8,
                end_time=10.2,
                raw_start_time=8.8,
                raw_end_time=10.2,
                confidence=95.0,
                confidence_level=ConfidenceLevel.HIGH,
                status=SegmentStatus.MATCHED,
            )
        ],
    )

    assert _compute_export_audio_duration(job) == 10.2
