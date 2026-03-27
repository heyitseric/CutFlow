import json
from types import SimpleNamespace

import pytest

from app.providers.cloud import volcengine_srt
from app.providers.cloud.volcengine_srt import (
    SRTSegmentationError,
    VolcEngineSRTSegmenter,
)


class _FakeCompletions:
    def __init__(self, payloads: list[str]):
        self.payloads = payloads
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.payloads.pop(0)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=payload)
                )
            ]
        )


@pytest.mark.asyncio
async def test_volcengine_srt_segmenter_batches_requests(monkeypatch):
    monkeypatch.setattr(
        volcengine_srt,
        "get_settings",
        lambda: SimpleNamespace(
            ARK_API_KEY="test-key",
            CLOUD_BASE_URL="https://example.com",
            SRT_SEGMENTATION_MODEL="doubao-seed-2.0-lite",
            SRT_SEGMENTATION_BATCH_SIZE=20,
            SRT_MAX_CHARS_PER_SEGMENT=15,
        ),
    )

    batch_one = json.dumps(
        [{"id": idx, "segments": [f"第{idx}句"]} for idx in range(20)],
        ensure_ascii=False,
    )
    batch_two = json.dumps(
        [{"id": 0, "segments": ["第20句"]}],
        ensure_ascii=False,
    )
    completions = _FakeCompletions([batch_one, batch_two])

    segmenter = VolcEngineSRTSegmenter()
    segmenter.client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )

    results = await segmenter.segment_texts([f"第{idx}句" for idx in range(21)])

    assert len(completions.calls) == 2
    assert results[0] == ["第0句"]
    assert results[-1] == ["第20句"]


@pytest.mark.asyncio
async def test_volcengine_srt_segmenter_rejects_missing_items(monkeypatch):
    monkeypatch.setattr(
        volcengine_srt,
        "get_settings",
        lambda: SimpleNamespace(
            ARK_API_KEY="test-key",
            CLOUD_BASE_URL="https://example.com",
            SRT_SEGMENTATION_MODEL="doubao-seed-2.0-lite",
            SRT_SEGMENTATION_BATCH_SIZE=20,
            SRT_MAX_CHARS_PER_SEGMENT=15,
        ),
    )

    completions = _FakeCompletions(
        [json.dumps([{"id": 0, "segments": ["第一句"]}], ensure_ascii=False)]
    )

    segmenter = VolcEngineSRTSegmenter()
    segmenter.client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )

    with pytest.raises(SRTSegmentationError):
        await segmenter.segment_texts(["第一句", "第二句"])
