import pytest

from app.models.schemas import (
    AlignedSegment,
    ConfidenceLevel,
    SegmentStatus,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionWord,
)
from app.services.semantic_fine_cut import SemanticFineCutService


def _word(char: str, start: float, end: float) -> TranscriptionWord:
    return TranscriptionWord(word=char, start=start, end=end, confidence=1.0)


def _segment(script_text: str, transcript_text: str, start: float, end: float) -> AlignedSegment:
    return AlignedSegment(
        script_index=0,
        script_text=script_text,
        transcript_text=transcript_text,
        start_time=start,
        end_time=end,
        raw_start_time=start,
        raw_end_time=end,
        confidence=95.0,
        confidence_level=ConfidenceLevel.HIGH,
        status=SegmentStatus.MATCHED,
    )


@pytest.mark.asyncio
async def test_semantic_fine_cut_removes_middle_off_script_chunk_locally():
    transcription = TranscriptionResult(
        segments=[
            TranscriptionSegment(
                text="大家好",
                start=0.0,
                end=0.2,
                words=[
                    _word("大", 0.00, 0.05),
                    _word("家", 0.05, 0.10),
                    _word("好", 0.10, 0.15),
                ],
            ),
            TranscriptionSegment(
                text="嗯其实",
                start=0.55,
                end=0.75,
                words=[
                    _word("嗯", 0.55, 0.60),
                    _word("其", 0.60, 0.65),
                    _word("实", 0.65, 0.70),
                ],
            ),
            TranscriptionSegment(
                text="今天讲一本书",
                start=1.10,
                end=1.55,
                words=[
                    _word("今", 1.10, 1.15),
                    _word("天", 1.15, 1.20),
                    _word("讲", 1.20, 1.25),
                    _word("一", 1.25, 1.30),
                    _word("本", 1.30, 1.35),
                    _word("书", 1.35, 1.40),
                ],
            ),
        ]
    )
    segments = [
        _segment(
            "大家好今天讲一本书",
            "大家好嗯其实今天讲一本书",
            0.0,
            1.55,
        )
    ]

    refined = await SemanticFineCutService().refine(segments, transcription)

    assert len(refined) == 2
    assert [(seg.start_time, seg.end_time) for seg in refined] == [
        (0.0, 0.15),
        (1.10, 1.40),
    ]


class _AggressiveDecider:
    async def decide(self, **_kwargs):
        return [
            {"idx": 0, "action": "REMOVE"},
            {"idx": 1, "action": "REMOVE"},
            {"idx": 2, "action": "KEEP"},
        ]


@pytest.mark.asyncio
async def test_semantic_fine_cut_rejects_over_aggressive_llm_trim():
    transcription = TranscriptionResult(
        segments=[
            TranscriptionSegment(
                text="大家好",
                start=0.0,
                end=0.2,
                words=[
                    _word("大", 0.00, 0.05),
                    _word("家", 0.05, 0.10),
                    _word("好", 0.10, 0.15),
                ],
            ),
            TranscriptionSegment(
                text="今天讲一本书",
                start=0.55,
                end=1.0,
                words=[
                    _word("今", 0.55, 0.60),
                    _word("天", 0.60, 0.65),
                    _word("讲", 0.65, 0.70),
                    _word("一", 0.70, 0.75),
                    _word("本", 0.75, 0.80),
                    _word("书", 0.80, 0.85),
                ],
            ),
            TranscriptionSegment(
                text="好的",
                start=1.30,
                end=1.5,
                words=[
                    _word("好", 1.30, 1.35),
                    _word("的", 1.35, 1.40),
                ],
            ),
        ]
    )
    segments = [
        _segment(
            "大家好今天讲一本书",
            "大家好今天讲一本书好的",
            0.0,
            1.5,
        )
    ]

    refined = await SemanticFineCutService(decider=_AggressiveDecider()).refine(
        segments,
        transcription,
    )

    assert len(refined) == 1
    assert refined[0].start_time == 0.0
    assert refined[0].end_time == 1.5


@pytest.mark.asyncio
async def test_semantic_fine_cut_removes_repeated_start_that_does_not_advance_script():
    transcription = TranscriptionResult(
        segments=[
            TranscriptionSegment(
                text="大家好",
                start=0.0,
                end=0.2,
                words=[
                    _word("大", 0.00, 0.05),
                    _word("家", 0.05, 0.10),
                    _word("好", 0.10, 0.15),
                ],
            ),
            TranscriptionSegment(
                text="大家好",
                start=0.45,
                end=0.65,
                words=[
                    _word("大", 0.45, 0.50),
                    _word("家", 0.50, 0.55),
                    _word("好", 0.55, 0.60),
                ],
            ),
            TranscriptionSegment(
                text="今天讲一本书",
                start=1.0,
                end=1.45,
                words=[
                    _word("今", 1.00, 1.05),
                    _word("天", 1.05, 1.10),
                    _word("讲", 1.10, 1.15),
                    _word("一", 1.15, 1.20),
                    _word("本", 1.20, 1.25),
                    _word("书", 1.25, 1.30),
                ],
            ),
        ]
    )
    segments = [
        _segment(
            "大家好今天讲一本书",
            "大家好大家好今天讲一本书",
            0.0,
            1.45,
        )
    ]

    refined = await SemanticFineCutService().refine(segments, transcription)

    assert len(refined) == 2
    assert [(seg.start_time, seg.end_time) for seg in refined] == [
        (0.0, 0.15),
        (1.0, 1.30),
    ]
