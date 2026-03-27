import json
import logging
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz

from app.models.schemas import MatchResult
from app.providers.base import Matcher
from app.utils.text_normalize import clean_for_matching

logger = logging.getLogger(__name__)


def _clean_text(text: str) -> str:
    """Remove punctuation and whitespace for character-level comparison."""
    return clean_for_matching(text)


class RapidFuzzMatcher(Matcher):
    def __init__(self, dictionary_dir: Optional[Path] = None):
        self.dictionary_dir = dictionary_dir

    def _build_transcript_text(self, segments: list[dict]) -> list[dict]:
        """Flatten transcript segments into a word-level list with indices."""
        all_words = []
        for seg in segments:
            for w in seg.get("words", []):
                all_words.append({
                    "word": w.get("word", ""),
                    "start": w.get("start", 0.0),
                    "end": w.get("end", 0.0),
                    "confidence": w.get("confidence", 1.0),
                })
        return all_words

    def _build_segment_ranges(self, segments: list[dict], all_words: list[dict]) -> list[tuple[int, int, str]]:
        """Return (start_word_idx, end_word_idx, segment_text) for each consolidated segment."""
        ranges = []
        word_idx = 0
        for seg in segments:
            n_words = len(seg.get("words", []))
            seg_text = "".join(w.get("word", "") for w in seg.get("words", []))
            ranges.append((word_idx, word_idx + n_words, seg_text))
            word_idx += n_words
        return ranges

    async def match_segments(
        self,
        script_sentences: list[str],
        transcript_segments: list[dict],
    ) -> list[MatchResult]:
        all_words = self._build_transcript_text(transcript_segments)
        if not all_words:
            return []

        full_transcript_tokens = [w["word"] for w in all_words]
        segment_ranges = self._build_segment_ranges(transcript_segments, all_words)

        results: list[MatchResult] = []

        for script_idx, sentence in enumerate(script_sentences):
            clean_sentence = _clean_text(sentence)
            char_count = len(clean_sentence)

            if char_count == 0:
                continue

            # ----- Phase 1: Segment-level pre-filtering -----
            # Score each consolidated segment against the script sentence
            seg_scores: list[tuple[float, int]] = []
            for seg_i, (seg_start, seg_end, seg_text) in enumerate(segment_ranges):
                clean_seg = _clean_text(seg_text)
                if not clean_seg:
                    continue
                score = fuzz.token_set_ratio(clean_sentence, clean_seg)
                seg_scores.append((score, seg_i))

            # Take top-5 segments (or fewer) as candidates
            seg_scores.sort(key=lambda x: x[0], reverse=True)
            top_segments = seg_scores[:5]

            # Build candidate word ranges from top segments (+ neighbors)
            candidate_ranges: list[tuple[int, int]] = []
            for _, seg_i in top_segments:
                # Include the segment and its immediate neighbors
                for offset in (-1, 0, 1):
                    ni = seg_i + offset
                    if 0 <= ni < len(segment_ranges):
                        s, e, _ = segment_ranges[ni]
                        candidate_ranges.append((s, e))

            # Merge overlapping / adjacent ranges
            if not candidate_ranges:
                continue
            candidate_ranges.sort()
            merged: list[tuple[int, int]] = [candidate_ranges[0]]
            for s, e in candidate_ranges[1:]:
                if s <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], e))
                else:
                    merged.append((s, e))

            # ----- Phase 2: Character-level sliding window within candidate ranges -----
            # Window sizing based on character count (since words are individual chars)
            min_window = max(char_count - 5, 3)
            max_window = min(len(full_transcript_tokens), char_count * 3)
            # Coarse step for initial scan, then refine around best hits
            coarse_step = max(1, min_window // 3)
            window_step = max(1, min_window // 2)

            best_candidates: list[tuple[float, int, int]] = []

            for range_start, range_end in merged:
                for window_size in range(min_window, max_window + 1, window_step):
                    for start_idx in range(range_start, min(range_end, len(full_transcript_tokens)) - window_size + 1, coarse_step):
                        end_idx = start_idx + window_size
                        window_text = "".join(full_transcript_tokens[start_idx:end_idx])

                        # Compare raw Chinese text directly, no jieba tokenization
                        score = fuzz.ratio(clean_sentence, _clean_text(window_text))

                        if score > 40:
                            best_candidates.append((score, start_idx, end_idx))

            # ----- Phase 2b: Refine top hits with step=1 around their boundaries -----
            if best_candidates:
                best_candidates.sort(key=lambda x: x[0], reverse=True)
                refine_seeds = best_candidates[:5]
                for _, seed_start, seed_end in refine_seeds:
                    seed_size = seed_end - seed_start
                    for dw in range(-3, 4):
                        ws = seed_size + dw
                        if ws < 3:
                            continue
                        for ds in range(-coarse_step, coarse_step + 1):
                            si = seed_start + ds
                            ei = si + ws
                            if si < 0 or ei > len(full_transcript_tokens):
                                continue
                            wt = "".join(full_transcript_tokens[si:ei])
                            sc = fuzz.ratio(clean_sentence, _clean_text(wt))
                            if sc > 40:
                                best_candidates.append((sc, si, ei))

            # Sort by score descending
            best_candidates.sort(key=lambda x: x[0], reverse=True)

            # Deduplicate overlapping windows, keep top 3
            selected: list[tuple[float, int, int]] = []
            for cand in best_candidates:
                if len(selected) >= 3:
                    break
                overlap = False
                for sel in selected:
                    overlap_start = max(cand[1], sel[1])
                    overlap_end = min(cand[2], sel[2])
                    if overlap_end > overlap_start:
                        overlap_ratio = (overlap_end - overlap_start) / (cand[2] - cand[1])
                        if overlap_ratio > 0.5:
                            overlap = True
                            break
                if not overlap:
                    selected.append(cand)

            for score, start_idx, end_idx in selected:
                results.append(MatchResult(
                    script_index=script_idx,
                    transcript_start_word_idx=start_idx,
                    transcript_end_word_idx=end_idx,
                    score=score,
                ))

        return results
