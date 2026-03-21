import logging
from typing import Optional

from app.config import get_settings
from app.models.schemas import MatchResult
from app.providers.base import Matcher

logger = logging.getLogger(__name__)


class MatcherService:
    def __init__(
        self,
        matcher: Matcher,
        cloud_matcher: Optional[Matcher] = None,
    ):
        self.matcher = matcher
        self.cloud_matcher = cloud_matcher

    async def match(
        self,
        script_sentences: list[str],
        transcript_segments: list[dict],
    ) -> list[MatchResult]:
        """
        Match script sentences to transcript segments.

        1. Run local matcher
        2. For low-confidence matches, optionally re-verify with cloud
        """
        settings = get_settings()

        # Step 1: Local matching
        results = await self.matcher.match_segments(
            script_sentences, transcript_segments
        )

        # Step 2: Cloud re-verification for low-confidence matches
        if self.cloud_matcher:
            low_conf_indices = set()
            for r in results:
                if r.score < settings.MEDIUM_CONFIDENCE_THRESHOLD:
                    low_conf_indices.add(r.script_index)

            if low_conf_indices:
                low_conf_sentences = [
                    s for i, s in enumerate(script_sentences)
                    if i in low_conf_indices
                ]
                if low_conf_sentences:
                    try:
                        cloud_results = await self.cloud_matcher.match_segments(
                            low_conf_sentences, transcript_segments
                        )
                        # Replace low-confidence local results with cloud results
                        # if cloud results are better
                        cloud_map = {}
                        for cr in cloud_results:
                            if cr.script_index not in cloud_map or cr.score > cloud_map[cr.script_index].score:
                                cloud_map[cr.script_index] = cr

                        # Remap cloud indices to original indices
                        low_conf_list = sorted(low_conf_indices)
                        remapped = {}
                        for cloud_idx, original_idx in enumerate(low_conf_list):
                            if cloud_idx in cloud_map:
                                result = cloud_map[cloud_idx]
                                result.script_index = original_idx
                                remapped[original_idx] = result

                        # Replace in results
                        new_results = []
                        seen_indices = set()
                        for r in results:
                            if r.script_index in remapped:
                                if r.script_index not in seen_indices:
                                    new_result = remapped[r.script_index]
                                    if new_result.score > r.score:
                                        new_results.append(new_result)
                                    else:
                                        new_results.append(r)
                                    seen_indices.add(r.script_index)
                            else:
                                new_results.append(r)

                        results = new_results
                    except Exception as e:
                        logger.warning(f"Cloud re-verification failed: {e}")

        return results
