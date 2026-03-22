import pytest

from app.models.schemas import MatchResult
from app.providers.base import Matcher
from app.services.matcher import MatcherService


class _CloudMatcher(Matcher):
    async def match_segments(
        self,
        script_sentences: list[str],
        transcript_segments: list[dict],
    ) -> list[MatchResult]:
        return [
            MatchResult(
                script_index=0,
                transcript_start_word_idx=10,
                transcript_end_word_idx=15,
                score=92.0,
            )
        ]


class _LocalMatcher(Matcher):
    async def match_segments(
        self,
        script_sentences: list[str],
        transcript_segments: list[dict],
    ) -> list[MatchResult]:
        assert script_sentences == ["second line"]
        return [
            MatchResult(
                script_index=0,
                transcript_start_word_idx=20,
                transcript_end_word_idx=25,
                score=88.0,
            )
        ]


class _OverlappingLocalMatcher(Matcher):
    async def match_segments(
        self,
        script_sentences: list[str],
        transcript_segments: list[dict],
    ) -> list[MatchResult]:
        assert script_sentences == ["second line"]
        return [
            MatchResult(
                script_index=0,
                transcript_start_word_idx=12,
                transcript_end_word_idx=18,
                score=99.0,
            ),
            MatchResult(
                script_index=0,
                transcript_start_word_idx=20,
                transcript_end_word_idx=25,
                score=88.0,
            ),
        ]


@pytest.mark.asyncio
async def test_matcher_service_supplements_missing_llm_results():
    service = MatcherService(
        matcher=_LocalMatcher(),
        cloud_matcher=_CloudMatcher(),
    )

    results = await service.match(
        ["first line", "second line"],
        transcript_segments=[],
    )

    assert [
        (result.script_index, result.transcript_start_word_idx, result.score)
        for result in results
    ] == [
        (0, 10, 92.0),
        (1, 20, 88.0),
    ]


@pytest.mark.asyncio
async def test_matcher_service_skips_overlapping_local_candidates():
    service = MatcherService(
        matcher=_OverlappingLocalMatcher(),
        cloud_matcher=_CloudMatcher(),
    )

    results = await service.match(
        ["first line", "second line"],
        transcript_segments=[],
    )

    assert [
        (
            result.script_index,
            result.transcript_start_word_idx,
            result.transcript_end_word_idx,
            result.score,
        )
        for result in results
    ] == [
        (0, 10, 15, 92.0),
        (1, 20, 25, 88.0),
    ]
