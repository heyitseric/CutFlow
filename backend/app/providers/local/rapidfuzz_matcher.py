import json
import logging
from pathlib import Path
from typing import Optional

import jieba
from rapidfuzz import fuzz

from app.models.schemas import MatchResult
from app.providers.base import Matcher

logger = logging.getLogger(__name__)


class RapidFuzzMatcher(Matcher):
    def __init__(self, dictionary_dir: Optional[Path] = None):
        self.dictionary_dir = dictionary_dir
        self._jieba_initialized = False

    def _init_jieba(self):
        if self._jieba_initialized:
            return
        if self.dictionary_dir:
            dict_path = self.dictionary_dir / "user_dict.json"
            if dict_path.exists():
                try:
                    data = json.loads(dict_path.read_text(encoding="utf-8"))
                    for term in data.get("custom_terms", []):
                        jieba.add_word(term)
                    for entry in data.get("entries", []):
                        jieba.add_word(entry.get("correct", ""))
                    logger.info("Loaded custom dictionary into jieba")
                except Exception as e:
                    logger.warning(f"Failed to load custom dictionary: {e}")
        self._jieba_initialized = True

    def _tokenize(self, text: str) -> str:
        """Tokenize text using jieba for Chinese, keeping English words intact."""
        self._init_jieba()
        tokens = jieba.lcut(text)
        return " ".join(t.strip() for t in tokens if t.strip())

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

    async def match_segments(
        self,
        script_sentences: list[str],
        transcript_segments: list[dict],
    ) -> list[MatchResult]:
        all_words = self._build_transcript_text(transcript_segments)
        if not all_words:
            return []

        full_transcript_tokens = [w["word"] for w in all_words]
        results: list[MatchResult] = []

        for script_idx, sentence in enumerate(script_sentences):
            tokenized_sentence = self._tokenize(sentence)
            sentence_token_count = len(tokenized_sentence.split())

            # Sliding window: window size proportional to sentence length
            min_window = max(sentence_token_count, 3)
            max_window = min(len(full_transcript_tokens), min_window * 4)

            best_candidates: list[tuple[float, int, int]] = []

            for window_size in range(min_window, max_window + 1, max(1, min_window // 2)):
                for start_idx in range(0, len(full_transcript_tokens) - window_size + 1):
                    end_idx = start_idx + window_size
                    window_text = "".join(full_transcript_tokens[start_idx:end_idx])
                    tokenized_window = self._tokenize(window_text)

                    score = fuzz.token_set_ratio(tokenized_sentence, tokenized_window)

                    if score > 40:
                        best_candidates.append((score, start_idx, end_idx))

            # Sort by score descending, take top 3
            best_candidates.sort(key=lambda x: x[0], reverse=True)

            # Deduplicate overlapping windows, keep top 3
            selected: list[tuple[float, int, int]] = []
            for cand in best_candidates:
                if len(selected) >= 3:
                    break
                # Check overlap with already selected
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
