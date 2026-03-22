from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.schemas import (
    AlignedSegment,
    ConfidenceLevel,
    ExportRequest,
    SegmentStatus,
    TranscriptionResult,
)
from app.providers.cloud.volcengine_srt import SRTSegmentationError
from app.routers.export import _compute_export_audio_duration, _resolve_requested_formats
from app.routers import export as export_router


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


def test_resolve_requested_formats_prefers_explicit_format_list():
    request = ExportRequest(
        formats=["fcpxml"],
        videoFilename="demo.mp4",
    )

    assert _resolve_requested_formats(request) == {"fcpxml"}


@pytest.mark.asyncio
async def test_export_job_returns_clear_error_when_srt_segmentation_fails(
    monkeypatch,
    tmp_path,
):
    job = SimpleNamespace(
        transcription=TranscriptionResult(segments=[], duration=3.0),
        alignment=[
            AlignedSegment(
                script_index=0,
                script_text="大家好今天讲一本书",
                transcript_text="大家好今天讲一本书",
                start_time=0.0,
                end_time=3.0,
                raw_start_time=0.0,
                raw_end_time=3.0,
                confidence=95.0,
                confidence_level=ConfidenceLevel.HIGH,
                status=SegmentStatus.MATCHED,
            )
        ],
        audio_filename="demo.wav",
        export_files=[],
    )

    class _Manager:
        def get_job(self, job_id: str):
            assert job_id == "job123"
            return job

        def update_job(self, *_args, **_kwargs):
            return job

    async def _raise_srt_error(**_kwargs):
        raise SRTSegmentationError("Seed 超时")

    monkeypatch.setattr(
        export_router,
        "get_settings",
        lambda: SimpleNamespace(OUTPUT_DIR=tmp_path),
    )
    monkeypatch.setattr(export_router, "get_job_manager", lambda: _Manager())
    monkeypatch.setattr(export_router, "generate_edl", lambda **_kwargs: "edl")
    monkeypatch.setattr(export_router, "generate_fcpxml", lambda **_kwargs: "<xml />")
    monkeypatch.setattr(export_router, "generate_srt", _raise_srt_error)

    with pytest.raises(HTTPException) as exc_info:
        await export_router.export_job(
            "job123",
            ExportRequest(videoFilename="demo.mp4"),
        )

    assert exc_info.value.status_code == 502
    assert "SRT 导出失败" in exc_info.value.detail
    assert "Seed 超时" in exc_info.value.detail


@pytest.mark.asyncio
async def test_export_job_skips_srt_when_not_requested(
    monkeypatch,
    tmp_path,
):
    job = SimpleNamespace(
        transcription=TranscriptionResult(segments=[], duration=3.0),
        alignment=[
            AlignedSegment(
                script_index=0,
                script_text="大家好今天讲一本书",
                transcript_text="大家好今天讲一本书",
                start_time=0.0,
                end_time=3.0,
                raw_start_time=0.0,
                raw_end_time=3.0,
                confidence=95.0,
                confidence_level=ConfidenceLevel.HIGH,
                status=SegmentStatus.MATCHED,
            )
        ],
        audio_filename="demo.wav",
        export_files=[],
    )

    class _Manager:
        def get_job(self, job_id: str):
            assert job_id == "job123"
            return job

        def update_job(self, *_args, **_kwargs):
            return job

    async def _unexpected_srt(**_kwargs):
        raise AssertionError("SRT should not be generated")

    monkeypatch.setattr(
        export_router,
        "get_settings",
        lambda: SimpleNamespace(OUTPUT_DIR=tmp_path),
    )
    monkeypatch.setattr(export_router, "get_job_manager", lambda: _Manager())
    monkeypatch.setattr(export_router, "generate_edl", lambda **_kwargs: "edl")
    monkeypatch.setattr(export_router, "generate_fcpxml", lambda **_kwargs: "<xml />")
    monkeypatch.setattr(export_router, "generate_srt", _unexpected_srt)

    response = await export_router.export_job(
        "job123",
        ExportRequest(formats=["fcpxml"], videoFilename="demo.mp4"),
    )

    assert response.files == ["/api/downloads/job123/job123.fcpxml"]
    assert (tmp_path / "job123" / "job123.fcpxml").exists()
    assert not (tmp_path / "job123" / "job123.srt").exists()
