import logging
from collections import defaultdict
from typing import Optional

from app.config import get_settings
from app.models.schemas import MatchResult
from app.providers.base import Matcher

logger = logging.getLogger(__name__)


def _spans_overlap(
    start_a: int,
    end_a: int,
    start_b: int,
    end_b: int,
) -> bool:
    return start_a < end_b and start_b < end_a


class MatcherService:
    """Orchestrates script-to-transcript matching.

    Strategy:
    - If a cloud_matcher (LLM) is available, use it as the PRIMARY matcher.
    - Fall back to the local matcher (RapidFuzz) only when the LLM returns
      no results or raises an error.
    """

    def __init__(
        self,
        matcher: Matcher,
        cloud_matcher: Optional[Matcher] = None,
    ):
        self.local_matcher = matcher
        self.cloud_matcher = cloud_matcher

    async def match(
        self,
        script_sentences: list[str],
        transcript_segments: list[dict],
    ) -> list[MatchResult]:
        """
        Match script sentences to transcript segments.

        1. If LLM matcher is available, use it as primary
        2. Fall back to local (RapidFuzz) matcher if LLM fails or returns empty
        """

        # --- Primary: LLM matching ---
        if self.cloud_matcher:
            try:
                logger.info("Using LLM as primary matcher")
                results = await self.cloud_matcher.match_segments(
                    script_sentences, transcript_segments
                )
                if results:
                    logger.info(
                        f"LLM matcher returned {len(results)} results"
                    )
                    claimed_spans = [
                        (
                            r.transcript_start_word_idx,
                            r.transcript_end_word_idx,
                        )
                        for r in results
                        if r.transcript_end_word_idx > r.transcript_start_word_idx
                    ]
                    matched_script_indices = {
                        r.script_index for r in results if r.score > 0
                    }
                    missing_indices = [
                        idx
                        for idx in range(len(script_sentences))
                        if idx not in matched_script_indices
                    ]
                    if not missing_indices:
                        return results

                    logger.warning(
                        "LLM matcher missed %d script sentences, supplementing "
                        "with local matcher: %s",
                        len(missing_indices),
                        missing_indices,
                    )
                    local_results = await self._match_missing_with_local(
                        script_sentences,
                        transcript_segments,
                        missing_indices,
                        claimed_spans,
                    )
                    if local_results:
                        logger.info(
                            "Local matcher supplemented %d candidates for missing sentences",
                            len(local_results),
                        )
                        return results + local_results
                    return results
                else:
                    logger.warning(
                        "LLM matcher returned empty results, "
                        "falling back to local matcher"
                    )
            except Exception as e:
                logger.warning(
                    f"LLM matching failed, falling back to local matcher: {e}"
                )

        # --- Fallback: local (RapidFuzz) matching ---
        logger.info("Using local (RapidFuzz) matcher")
        results = await self.local_matcher.match_segments(
            script_sentences, transcript_segments
        )
        return results

    async def _match_missing_with_local(
        self,
        script_sentences: list[str],
        transcript_segments: list[dict],
        missing_indices: list[int],
        occupied_spans: list[tuple[int, int]],
    ) -> list[MatchResult]:
        if not missing_indices:
            return []

        subset = [
            (orig_idx, script_sentences[orig_idx])
            for orig_idx in missing_indices
        ]
        local_results = await self.local_matcher.match_segments(
            [text for _, text in subset],
            transcript_segments,
        )
        remapped: dict[int, list[MatchResult]] = defaultdict(list)
        index_map = {
            local_idx: orig_idx for local_idx, (orig_idx, _) in enumerate(subset)
        }
        for result in local_results:
            orig_idx = index_map.get(result.script_index)
            if orig_idx is None:
                continue
            remapped[orig_idx].append(MatchResult(
                script_index=orig_idx,
                transcript_start_word_idx=result.transcript_start_word_idx,
                transcript_end_word_idx=result.transcript_end_word_idx,
                score=result.score,
            ))

        accepted: list[MatchResult] = []
        used_spans = list(occupied_spans)

        for orig_idx in missing_indices:
            candidates = sorted(
                remapped.get(orig_idx, []),
                key=lambda r: r.score,
                reverse=True,
            )
            for candidate in candidates:
                overlaps_existing = any(
                    _spans_overlap(
                        candidate.transcript_start_word_idx,
                        candidate.transcript_end_word_idx,
                        start,
                        end,
                    )
                    for start, end in used_spans
                )
                if overlaps_existing:
                    continue

                accepted.append(candidate)
                used_spans.append(
                    (
                        candidate.transcript_start_word_idx,
                        candidate.transcript_end_word_idx,
                    )
                )
                break

        return accepted
