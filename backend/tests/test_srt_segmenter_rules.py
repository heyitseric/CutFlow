"""Tests for the rule-based SRT segmenter."""

import pytest

from app.services.srt_segmenter_rules import enforce_segment_limits, split_by_rules


# ---------------------------------------------------------------------------
# split_by_rules
# ---------------------------------------------------------------------------


class TestSplitByRulesShortAndEmpty:
    def test_short_text_returned_unchanged(self):
        text = "今天天气真好"
        assert len(text) <= 15
        result = split_by_rules(text)
        assert result == [text]

    def test_empty_text_returns_empty_list(self):
        assert split_by_rules("") == []


class TestSplitByRulesPunctuation:
    def test_split_at_sentence_ending_punctuation(self):
        text = "今天的天气真的特别好啊。明天应该也不错吧。"
        assert len(text) > 15  # must exceed max_chars to trigger splitting
        result = split_by_rules(text)
        assert len(result) >= 2
        # Punctuation stays at the end of its segment
        assert result[0].endswith("。")
        assert "".join(result) == text

    def test_split_at_clause_punctuation(self):
        text = "我们今天来讲一下，如何通过饮食调整改善睡眠。"
        result = split_by_rules(text)
        assert len(result) >= 2
        assert "".join(result) == text

    def test_punctuation_at_end_of_segment_not_start_of_next(self):
        text = "今天天气真好。明天也不错。后天下雨了。"
        result = split_by_rules(text)
        for seg in result:
            # No segment should start with sentence-ending punctuation
            assert not seg.startswith("。")
            assert not seg.startswith("！")
            assert not seg.startswith("？")

    def test_mixed_punctuation_levels(self):
        """Text with both sentence-ending and clause punctuation."""
        text = "今天天气真好，阳光明媚。明天可能会下雨，大家注意。"
        result = split_by_rules(text)
        assert len(result) >= 2
        assert "".join(result) == text


class TestSplitByRulesJieba:
    def test_split_at_jieba_word_boundaries_no_punctuation(self):
        text = "今天我们来详细讲解一下关于人工智能的最新发展"
        assert len(text) > 15
        result = split_by_rules(text)
        assert len(result) >= 2
        for seg in result:
            assert len(seg) <= 15
        assert "".join(result) == text


class TestSplitByRulesMerging:
    def test_merge_short_segments(self):
        """Segments shorter than min_chars should be merged with neighbors."""
        # Use a text that would naturally produce a very short trailing segment
        text = "今天天气非常好啊。是。"
        result = split_by_rules(text, max_chars=15, min_chars=5)
        for seg in result:
            # After merging, no segment should be shorter than min_chars
            # (unless it is the only segment or merging would exceed max_chars)
            if len(result) > 1:
                assert len(seg) >= 5 or len(seg) + len(result[0]) > 15
        assert "".join(result) == text


class TestSplitByRulesReconstruction:
    """Reconstruction validation: ''.join(result) == original for all inputs."""

    @pytest.mark.parametrize(
        "text",
        [
            "短句",
            "今天天气真好。明天也不错。",
            "我们今天来讲一下，如何通过饮食调整改善睡眠。",
            "今天我们来详细讲解一下关于人工智能的最新发展",
            "这是一个很长的句子没有任何标点符号但是超过了十五个字符需要被分割",
            "你好！世界？测试。",
        ],
    )
    def test_reconstruction(self, text: str):
        result = split_by_rules(text)
        assert "".join(result) == text


# ---------------------------------------------------------------------------
# enforce_segment_limits
# ---------------------------------------------------------------------------


class TestEnforceSegmentLimitsPassthrough:
    def test_all_within_limits_returns_unchanged(self):
        segments = ["今天天气真好", "明天也不错啊"]
        result = enforce_segment_limits(segments)
        assert result == segments

    def test_empty_input_returns_empty(self):
        assert enforce_segment_limits([]) == []


class TestEnforceSegmentLimitsSplit:
    def test_oversized_segment_gets_split(self):
        long_seg = "今天我们来详细讲解一下关于人工智能的最新发展"
        assert len(long_seg) > 15
        result = enforce_segment_limits([long_seg])
        assert len(result) > 1
        for seg in result:
            assert len(seg) <= 15
        assert "".join(result) == long_seg


class TestEnforceSegmentLimitsMerge:
    def test_undersized_segment_gets_merged(self):
        segments = ["大家好", "今天我们来讲"]
        assert len(segments[0]) < 5
        result = enforce_segment_limits(segments, max_chars=15, min_chars=5)
        # The short "大家好" (3 chars) should be merged with its neighbor
        assert len(result) <= len(segments)
        assert "".join(result) == "".join(segments)


class TestEnforceSegmentLimitsMixed:
    def test_mixed_too_long_and_too_short(self):
        segments = [
            "好",  # too short
            "今天我们来详细讲解一下关于人工智能的最新发展趋势",  # too long
            "谢谢",  # too short
        ]
        result = enforce_segment_limits(segments, max_chars=15, min_chars=5)
        for seg in result:
            assert len(seg) <= 15
        assert "".join(result) == "".join(segments)


class TestEnforceSegmentLimitsReconstruction:
    @pytest.mark.parametrize(
        "segments",
        [
            ["今天天气真好", "明天也不错"],
            ["好", "今天我们来详细讲解一下关于人工智能的最新发展趋势"],
            ["一", "二", "三"],
            ["这是正常长度的段落", "这也是正常长度的"],
        ],
    )
    def test_reconstruction(self, segments: list[str]):
        result = enforce_segment_limits(segments)
        assert "".join(result) == "".join(segments)
