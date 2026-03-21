import logging
from typing import Optional

from app.config import get_settings
from app.models.schemas import MatchResult
from app.providers.base import Matcher

logger = logging.getLogger(__name__)


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
