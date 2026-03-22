from app.models.schemas import (
    AlignedSegment,
    ConfidenceLevel,
    SegmentStatus,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionWord,
)
from app.services.fine_cut import (
    _rebalance_clause_boundaries,
    fine_cut_segments,
)


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


def test_fine_cut_segments_splits_long_sentence_into_script_clauses():
    transcription = TranscriptionResult(
        segments=[
            TranscriptionSegment(
                text="我前两天刚发的视频",
                start=0.0,
                end=0.5,
                words=[
                    _word("我", 0.00, 0.05),
                    _word("前", 0.05, 0.10),
                    _word("两", 0.10, 0.15),
                    _word("天", 0.15, 0.20),
                    _word("刚", 0.20, 0.25),
                    _word("发", 0.25, 0.30),
                    _word("的", 0.30, 0.35),
                    _word("视", 0.35, 0.40),
                    _word("频", 0.40, 0.45),
                ],
            ),
            TranscriptionSegment(
                text="给大家推荐非常好的一本书",
                start=0.85,
                end=1.55,
                words=[
                    _word("给", 0.85, 0.90),
                    _word("大", 0.90, 0.95),
                    _word("家", 0.95, 1.00),
                    _word("推", 1.00, 1.05),
                    _word("荐", 1.05, 1.10),
                    _word("非", 1.10, 1.15),
                    _word("常", 1.15, 1.20),
                    _word("好", 1.20, 1.25),
                    _word("的", 1.25, 1.30),
                    _word("一", 1.30, 1.35),
                    _word("本", 1.35, 1.40),
                    _word("书", 1.40, 1.45),
                ],
            ),
            TranscriptionSegment(
                text="这本书我的那个推荐",
                start=1.95,
                end=2.55,
                words=[
                    _word("这", 1.95, 2.00),
                    _word("本", 2.00, 2.05),
                    _word("书", 2.05, 2.10),
                    _word("我", 2.10, 2.15),
                    _word("的", 2.15, 2.20),
                    _word("那", 2.20, 2.25),
                    _word("个", 2.25, 2.30),
                    _word("推", 2.30, 2.35),
                    _word("荐", 2.35, 2.40),
                ],
            ),
        ]
    )
    aligned = [
        _segment(
            "我前两天刚发的视频，给大家推荐非常好的一本书，这本书我的那个推荐。",
            "我前两天刚发的视频给大家推荐非常好的一本书这本书我的那个推荐",
            0.0,
            2.55,
        )
    ]

    refined = fine_cut_segments(aligned, transcription)

    assert len(refined) == 3
    assert [seg.script_text for seg in refined] == [
        "我前两天刚发的视频，",
        "给大家推荐非常好的一本书，",
        "这本书我的那个推荐。",
    ]
    assert [(seg.start_time, seg.end_time) for seg in refined] == [
        (0.0, 0.45),
        (0.85, 1.45),
        (1.95, 2.40),
    ]


def test_fine_cut_segments_falls_back_when_clause_coverage_is_too_low():
    transcription = TranscriptionResult(
        segments=[
            TranscriptionSegment(
                text="完全不是脚本内容",
                start=0.0,
                end=0.5,
                words=[
                    _word("完", 0.0, 0.1),
                    _word("全", 0.1, 0.2),
                    _word("不", 0.2, 0.3),
                    _word("是", 0.3, 0.4),
                    _word("脚", 0.4, 0.5),
                ],
            )
        ]
    )
    aligned = [
        _segment(
            "第一句很长，第二句也很长。",
            "完全不是脚本内容",
            0.0,
            0.5,
        )
    ]

    refined = fine_cut_segments(aligned, transcription)

    assert len(refined) == 1
    assert refined[0].script_text == aligned[0].script_text
    assert refined[0].start_time == aligned[0].start_time
    assert refined[0].end_time == aligned[0].end_time


def test_rebalance_clause_boundaries_recovers_dropped_boundary_character():
    left_text = "然后他也是在一些知名的医学院里面当教授"
    right_text = "去培养别的医生出来的这么一个人"
    all_words = [
        {"word": ch, "start": idx * 0.1, "end": idx * 0.1 + 0.1}
        for idx, ch in enumerate(left_text + right_text)
    ]
    dropped_char_boundary = len(left_text) - 1
    clause_matches = [
        (f"{left_text}，", 0, dropped_char_boundary),
        (f"{right_text}，", dropped_char_boundary + 1, len(all_words)),
    ]

    rebalanced = _rebalance_clause_boundaries(clause_matches, all_words)

    assert rebalanced[0] == (
        f"{left_text}，",
        0,
        len(left_text),
    )
    assert rebalanced[1] == (
        f"{right_text}，",
        len(left_text),
        len(all_words),
    )


def test_rebalance_clause_boundaries_preserves_real_gap_word():
    left_text = "甲乙丙"
    right_text = "丁戊己"
    all_words = [
        {"word": ch, "start": idx * 0.1, "end": idx * 0.1 + 0.1}
        for idx, ch in enumerate(left_text + "啊" + right_text)
    ]
    clause_matches = [
        (f"{left_text}，", 0, len(left_text)),
        (f"{right_text}。", len(left_text) + 1, len(all_words)),
    ]

    rebalanced = _rebalance_clause_boundaries(clause_matches, all_words)

    assert rebalanced == clause_matches
