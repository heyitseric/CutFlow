from app.models.schemas import (
    MatchResult,
    ScriptSentence,
    SegmentStatus,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionWord,
)
from app.services.alignment_engine import align_segments


def _word(char: str, start: float, end: float) -> TranscriptionWord:
    return TranscriptionWord(word=char, start=start, end=end, confidence=1.0)


def test_align_segments_refines_window_to_script_boundaries():
    script = [ScriptSentence(index=0, text="甲乙丙")]
    transcription = TranscriptionResult(
        segments=[
            TranscriptionSegment(
                text="杂甲乙丙杂",
                start=0.0,
                end=0.5,
                words=[
                    _word("杂", 0.0, 0.1),
                    _word("甲", 0.1, 0.2),
                    _word("乙", 0.2, 0.3),
                    _word("丙", 0.3, 0.4),
                    _word("杂", 0.4, 0.5),
                ],
            )
        ]
    )
    matches = [
        MatchResult(
            script_index=0,
            transcript_start_word_idx=0,
            transcript_end_word_idx=5,
            score=95.0,
        )
    ]

    aligned = align_segments(script, matches, transcription)

    assert len(aligned) == 1
    assert aligned[0].status == SegmentStatus.MATCHED
    assert aligned[0].transcript_text == "甲乙丙"
    assert aligned[0].start_time == 0.1
    assert aligned[0].end_time == 0.4


def test_align_segments_preserves_non_hook_reordered_matches_as_copy():
    script = [
        ScriptSentence(index=0, text="甲甲甲"),
        ScriptSentence(index=1, text="乙乙乙"),
        ScriptSentence(index=2, text="丙丙丙"),
    ]
    transcription = TranscriptionResult(
        segments=[
            TranscriptionSegment(
                text="甲甲甲",
                start=0.0,
                end=0.3,
                words=[
                    _word("甲", 0.0, 0.1),
                    _word("甲", 0.1, 0.2),
                    _word("甲", 0.2, 0.3),
                ],
            ),
            TranscriptionSegment(
                text="丙丙丙",
                start=0.4,
                end=0.7,
                words=[
                    _word("丙", 0.4, 0.5),
                    _word("丙", 0.5, 0.6),
                    _word("丙", 0.6, 0.7),
                ],
            ),
            TranscriptionSegment(
                text="乙乙乙",
                start=0.8,
                end=1.1,
                words=[
                    _word("乙", 0.8, 0.9),
                    _word("乙", 0.9, 1.0),
                    _word("乙", 1.0, 1.1),
                ],
            ),
        ]
    )
    matches = [
        MatchResult(
            script_index=0,
            transcript_start_word_idx=0,
            transcript_end_word_idx=3,
            score=95.0,
        ),
        MatchResult(
            script_index=1,
            transcript_start_word_idx=6,
            transcript_end_word_idx=9,
            score=95.0,
        ),
        MatchResult(
            script_index=2,
            transcript_start_word_idx=3,
            transcript_end_word_idx=6,
            score=95.0,
        ),
    ]

    aligned = align_segments(script, matches, transcription)

    assert [seg.status for seg in aligned] == [
        SegmentStatus.MATCHED,
        SegmentStatus.COPY,
        SegmentStatus.MATCHED,
    ]
    assert aligned[1].transcript_text == "乙乙乙"
    assert aligned[1].start_time == 0.8
    assert aligned[1].end_time == 1.1
    assert aligned[1].is_reordered is True
    assert aligned[1].is_copy is False
    assert aligned[1].original_position == 6
