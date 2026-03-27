import re

import pytest

from app.models.schemas import ExportClip
from app.providers.cloud.volcengine_srt import SRTSegmentationError
from app.services.srt_generator import generate_srt


class _EchoSegmenter:
    async def segment_texts(self, texts: list[str]) -> list[list[str]]:
        return [[text] for text in texts]


class _StaticSegmenter:
    def __init__(self, responses: list[list[str]]):
        self.responses = responses

    async def segment_texts(self, texts: list[str]) -> list[list[str]]:
        assert len(texts) == len(self.responses)
        return self.responses


def _extract_timecodes(srt: str) -> list[tuple[str, str]]:
    return re.findall(r"(\d\d:\d\d:\d\d,\d{3}) --> (\d\d:\d\d:\d\d,\d{3})", srt)


@pytest.mark.asyncio
async def test_generate_srt_merges_split_clips_for_same_sentence():
    segments = [
        ExportClip(
            script_index=0,
            clip_index=0,
            start_time=10.0,
            end_time=11.0,
            script_text="第一句台词",
        ),
        ExportClip(
            script_index=0,
            clip_index=1,
            start_time=12.0,
            end_time=13.5,
            script_text="第一句台词",
        ),
        ExportClip(
            script_index=1,
            clip_index=0,
            start_time=20.0,
            end_time=21.0,
            script_text="第二句台词",
        ),
    ]

    srt = await generate_srt(segments, segmenter=_EchoSegmenter())

    assert srt.count("第一句台词") == 1
    assert "00:00:00,000 --> 00:00:02,500" in srt
    assert "00:00:02,500 --> 00:00:03,500" in srt


@pytest.mark.asyncio
async def test_generate_srt_keeps_fine_cut_clauses_separate():
    segments = [
        ExportClip(
            script_index=0,
            clip_index=0,
            start_time=10.0,
            end_time=11.0,
            script_text="第一句，",
        ),
        ExportClip(
            script_index=0,
            clip_index=1,
            start_time=12.0,
            end_time=13.0,
            script_text="第二句。",
        ),
    ]

    srt = await generate_srt(segments, segmenter=_EchoSegmenter())

    assert "00:00:00,000 --> 00:00:01,000" in srt
    assert "00:00:01,000 --> 00:00:02,000" in srt
    assert srt.count("第一句，") == 1
    assert srt.count("第二句。") == 1


@pytest.mark.asyncio
async def test_generate_srt_joins_transcript_text_across_split_clips():
    segments = [
        ExportClip(
            script_index=0,
            clip_index=0,
            start_time=10.0,
            end_time=11.0,
            script_text="第一句台词",
            transcript_text="第一句",
        ),
        ExportClip(
            script_index=0,
            clip_index=1,
            start_time=11.0,
            end_time=12.5,
            script_text="第一句台词",
            transcript_text="台词",
        ),
    ]

    srt = await generate_srt(
        segments,
        text_source="transcript",
        segmenter=_EchoSegmenter(),
    )

    assert srt.count("第一句台词") == 1
    assert "第一句\n台词" not in srt
    assert "第一句台词" in srt
    assert "00:00:00,000 --> 00:00:02,500" in srt


@pytest.mark.asyncio
async def test_generate_srt_deduplicates_identical_transcript_text_for_split_clips():
    segments = [
        ExportClip(
            script_index=0,
            clip_index=0,
            start_time=10.0,
            end_time=11.0,
            script_text="第一句台词",
            transcript_text="第一句台词",
        ),
        ExportClip(
            script_index=0,
            clip_index=1,
            start_time=11.0,
            end_time=12.0,
            script_text="第一句台词",
            transcript_text="第一句台词",
        ),
    ]

    srt = await generate_srt(
        segments,
        text_source="transcript",
        segmenter=_EchoSegmenter(),
    )

    assert srt.count("第一句台词") == 1
    assert "00:00:00,000 --> 00:00:02,000" in srt


@pytest.mark.asyncio
async def test_generate_srt_splits_long_sentence_into_multiple_subtitles():
    segments = [
        ExportClip(
            script_index=0,
            clip_index=0,
            start_time=0.0,
            end_time=4.0,
            script_text="今天我们来讲一下如何通过饮食和作息调整改善睡眠质量。",
        )
    ]
    segmenter = _StaticSegmenter(
        [["今天我们来讲一下", "如何通过饮食和", "作息调整改善睡眠质量。"]]
    )

    srt = await generate_srt(segments, segmenter=segmenter)
    timecodes = _extract_timecodes(srt)

    assert len(timecodes) == 3
    assert "今天我们来讲一下" in srt
    assert "如何通过饮食和" in srt
    assert "作息调整改善睡眠质量。" in srt
    assert timecodes[0][0] == "00:00:00,000"
    assert timecodes[-1][1] == "00:00:04,000"


@pytest.mark.asyncio
async def test_generate_srt_uses_clip_text_coverage_for_timing():
    segments = [
        ExportClip(
            script_index=0,
            clip_index=0,
            start_time=0.0,
            end_time=1.0,
            script_text="大家好朋友们今天讲一本好书",
            transcript_text="大家好朋友们",
        ),
        ExportClip(
            script_index=0,
            clip_index=1,
            start_time=1.0,
            end_time=3.0,
            script_text="大家好朋友们今天讲一本好书",
            transcript_text="今天讲一本好书",
        ),
    ]
    segmenter = _StaticSegmenter([["大家好朋友们", "今天讲一本好书"]])

    srt = await generate_srt(
        segments,
        text_source="transcript",
        segmenter=segmenter,
    )

    assert "00:00:00,000 --> 00:00:01,000" in srt
    assert "00:00:01,000 --> 00:00:03,000" in srt


@pytest.mark.asyncio
async def test_generate_srt_rejects_invalid_llm_segments():
    segments = [
        ExportClip(
            script_index=0,
            clip_index=0,
            start_time=0.0,
            end_time=2.0,
            script_text="大家好今天讲一本书",
        )
    ]

    with pytest.raises(SRTSegmentationError):
        await generate_srt(
            segments,
            segmenter=_StaticSegmenter([["大家好", "今天"]]),
        )


@pytest.mark.asyncio
async def test_generate_srt_fallback_segments_long_text_when_cache_misses():
    """When text is not in cache, split_by_rules should segment it instead of leaving as single segment."""
    long_text = "今天我们来讲一下，如何通过饮食调整改善睡眠质量。"
    segments = [
        ExportClip(
            script_index=0,
            clip_index=0,
            start_time=0.0,
            end_time=4.0,
            script_text=long_text,
        )
    ]
    # Pass a cache that does NOT contain this text
    srt = await generate_srt(segments, segment_cache={})

    # Should be segmented (not a single long subtitle)
    timecodes = _extract_timecodes(srt)
    assert len(timecodes) > 1, f"Expected multiple segments for {len(long_text)}-char text, got {len(timecodes)}"
    # Verify all text is present
    srt_text = "\n".join(line for line in srt.split("\n") if line and not line[0].isdigit() and "-->" not in line)
    assert "".join(srt_text.split("\n")) == long_text


@pytest.mark.asyncio
async def test_generate_srt_enforces_max_chars_on_llm_segments():
    """Even if LLM returns a valid but oversized segment, enforce_segment_limits should split it."""
    text = "今天我们来讲一下如何通过饮食和作息调整改善睡眠质量大家来看一看"
    segments = [
        ExportClip(
            script_index=0,
            clip_index=0,
            start_time=0.0,
            end_time=4.0,
            script_text=text,
        )
    ]
    # LLM returns the whole thing as one segment (doesn't segment)
    segmenter = _StaticSegmenter([[text]])

    srt = await generate_srt(segments, segmenter=segmenter)
    timecodes = _extract_timecodes(srt)

    # enforce_segment_limits should have split this
    assert len(timecodes) > 1, f"Expected split for {len(text)}-char text"
