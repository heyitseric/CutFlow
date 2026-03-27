import json
import logging
from typing import Callable, Optional

from openai import AsyncOpenAI

from app.config import get_settings
from app.models.schemas import (
    MatchResult,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionWord,
)
from app.providers.base import Matcher, Transcriber

logger = logging.getLogger(__name__)


class VolcEngineTranscriber(Transcriber):
    """Use VolcEngine (Doubao) LLM to correct/enhance local transcription."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=settings.ARK_API_KEY,
            base_url=settings.CLOUD_BASE_URL,
        )
        self.model = settings.CLOUD_MODEL

    async def transcribe(
        self,
        audio_path: str,
        language: str = "zh",
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> TranscriptionResult:
        """
        Cloud transcription: since we can't directly send audio to the LLM,
        this requires a local transcription first, then uses the LLM to
        correct the text. The caller should provide a local transcription
        result and use correct_transcription() instead.
        """
        raise NotImplementedError(
            "Direct audio transcription via VolcEngine LLM is not supported. "
            "Use a local Whisper backend for transcription, then use "
            "correct_transcription() to improve accuracy."
        )

    async def correct_transcription(
        self,
        transcription: TranscriptionResult,
        script_text: str = "",
    ) -> TranscriptionResult:
        """Use LLM to correct transcription text based on script context."""
        full_text = " ".join(seg.text for seg in transcription.segments)

        prompt = (
            "You are a Chinese speech transcription corrector. "
            "Fix any recognition errors in the transcription below. "
            "Keep the same structure, only correct wrong characters/words.\n\n"
        )
        if script_text:
            prompt += f"Reference script (may differ in order):\n{script_text}\n\n"
        prompt += f"Transcription to correct:\n{full_text}\n\n"
        prompt += (
            "Return ONLY the corrected text, nothing else. "
            "Keep the same sentence boundaries."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                timeout=60,
            )
            corrected_text = response.choices[0].message.content.strip()

            # Update segment texts while preserving timestamps
            corrected_segments = corrected_text.split("\n")
            for i, seg in enumerate(transcription.segments):
                if i < len(corrected_segments) and corrected_segments[i].strip():
                    seg.text = corrected_segments[i].strip()

            return transcription
        except Exception as e:
            logger.warning(f"Cloud correction failed: {e}")
            return transcription


class VolcEngineMatcher(Matcher):
    """Use VolcEngine (Doubao) LLM as PRIMARY matcher for script-to-transcript alignment.

    Sends transcript WITH segment-level timestamps so the LLM can identify
    time ranges.  For long scripts (>20 sentences) the request is split into
    batches of 15 to keep each LLM call focused and within context limits.
    """

    BATCH_SIZE = 15  # max script sentences per LLM call

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=settings.ARK_API_KEY,
            base_url=settings.CLOUD_BASE_URL,
        )
        self.model = settings.CLOUD_MODEL

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Convert seconds to [HH:MM:SS.s] format with 1-decimal precision.

        Sub-second precision is critical: the LLM reads these timestamps and
        returns start_time / end_time values.  Integer-second precision
        (the old format) caused up to 1s of error, which for Chinese speech
        (~3-5 chars/s) means wrong word ranges and garbled cut points.
        """
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"[{h:02d}:{m:02d}:{s:04.1f}]"

    def _build_timestamped_transcript(
        self, transcript_segments: list[dict]
    ) -> tuple[str, list[dict]]:
        """Build a timestamped transcript string and a flat word list.

        The transcript includes segment indices so the LLM can reference
        segment ranges for multi-segment matching.

        Returns:
            (timestamped_text, all_words)
            where all_words is a list of {"word": str, "start": float, "end": float, "seg_idx": int}
        """
        lines: list[str] = []
        all_words: list[dict] = []

        for seg_idx, seg in enumerate(transcript_segments):
            ts = self._format_timestamp(seg.get("start", 0.0))
            seg_text = seg.get("text", "")
            lines.append(f"[{seg_idx}] {ts} {seg_text}")

            for w in seg.get("words", []):
                all_words.append({
                    "word": w.get("word", ""),
                    "start": w.get("start", 0.0),
                    "end": w.get("end", 0.0),
                    "seg_idx": seg_idx,
                })

        return "\n".join(lines), all_words

    @staticmethod
    def _parse_json_response(content: str) -> list[dict]:
        """Extract a JSON array from LLM response, handling markdown fences."""
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first line (```json) and last line (```)
            end = len(lines) - 1
            while end > 0 and not lines[end].strip().startswith("```"):
                end -= 1
            content = "\n".join(lines[1:end])
        return json.loads(content)

    def _char_to_word_indices(
        self, start_char: int, end_char: int, all_words: list[dict]
    ) -> Optional[tuple[int, int]]:
        """Map character offsets in the flat word string to word indices."""
        if not all_words:
            return None

        char_count = 0
        start_word_idx = 0
        end_word_idx = len(all_words)

        for idx, w in enumerate(all_words):
            word_text = w["word"]
            if char_count <= start_char:
                start_word_idx = idx
            char_count += len(word_text)
            if char_count >= end_char:
                end_word_idx = idx + 1
                break

        return start_word_idx, end_word_idx

    def _seg_range_to_word_indices(
        self, start_seg: int, end_seg: int, all_words: list[dict]
    ) -> Optional[tuple[int, int]]:
        """Map a segment index range [start_seg, end_seg] (inclusive) to word indices.

        This is the most precise mapping method: it finds ALL words that
        belong to the specified segment range and returns the first and
        last+1 word indices.  Since words carry per-character timestamps,
        the resulting range gives exact speech boundaries without any
        leading/trailing silence.
        """
        if not all_words:
            return None

        if start_seg < 0 or end_seg < 0 or start_seg > end_seg:
            logger.warning(
                "Invalid segment range [%d, %d] from LLM response",
                start_seg, end_seg,
            )
            return None

        start_word_idx = len(all_words)
        end_word_idx = 0

        for idx, w in enumerate(all_words):
            seg_idx = w.get("seg_idx", -1)
            if start_seg <= seg_idx <= end_seg:
                if idx < start_word_idx:
                    start_word_idx = idx
                if idx + 1 > end_word_idx:
                    end_word_idx = idx + 1

        # Fallback if no words found in the segment range
        if start_word_idx >= end_word_idx:
            logger.warning(
                "No words found for segment range [%d, %d]",
                start_seg, end_seg,
            )
            return None

        return start_word_idx, end_word_idx

    def _time_to_word_indices(
        self, start_time: float, end_time: float, all_words: list[dict]
    ) -> Optional[tuple[int, int]]:
        """Map start/end times (seconds) to word indices.

        Strategy: find all words that *overlap* with the [start_time, end_time]
        window.  A word overlaps if its interval intersects the query interval,
        i.e. word.start < end_time AND word.end > start_time.

        This is more robust than the previous approach which could miss words
        when the LLM-returned times had limited precision.
        """
        if not all_words:
            return None

        tolerance = 0.15  # seconds — forgive small LLM rounding errors

        start_word_idx = len(all_words)
        end_word_idx = 0

        for idx, w in enumerate(all_words):
            w_start = w["start"]
            w_end = w["end"]
            # Word overlaps the query window?
            if w_start < end_time + tolerance and w_end > start_time - tolerance:
                if idx < start_word_idx:
                    start_word_idx = idx
                if idx + 1 > end_word_idx:
                    end_word_idx = idx + 1

        # If no overlap found, fall back to nearest word by start_time
        if start_word_idx >= end_word_idx:
            best_idx = 0
            best_dist = float("inf")
            for idx, w in enumerate(all_words):
                dist = abs(w["start"] - start_time)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = idx
            start_word_idx = best_idx
            end_word_idx = best_idx + 1

        return start_word_idx, end_word_idx

    # ------------------------------------------------------------------
    # core matching
    # ------------------------------------------------------------------

    async def _match_batch(
        self,
        batch_sentences: list[tuple[int, str]],
        timestamped_transcript: str,
        all_words: list[dict],
    ) -> list[MatchResult]:
        """Match a single batch of script sentences against the full transcript."""

        numbered_script = "\n".join(
            f"[{idx}] {text}" for idx, text in batch_sentences
        )

        prompt = (
            "你是一位专业的视频剪辑师助手。我需要你帮我将脚本文本与视频的语音识别转录结果进行对齐匹配。\n\n"
            "语音识别可能存在同音字错误，请忽略这些差异，按语义匹配。\n\n"
            f"## 脚本原文：\n{numbered_script}\n\n"
            f"## 转录片段（带编号和时间戳）：\n{timestamped_transcript}\n\n"
            "请为脚本中的每个句子找到对应的转录片段范围。\n\n"
            "**重要：一句脚本可能对应多个连续的转录片段。**\n"
            "例如，脚本中一句长句\"你说这个事情可不可笑就是说白了我是个帮你看病的\"，\n"
            "说话人可能在中间停顿了一下，所以实际上跨了转录片段[45]和[46]两个片段。\n"
            "这种情况下，start_seg_index=45，end_seg_index=46。\n\n"
            "**每个脚本句子必须完整匹配，宁多不少。如果一个脚本句子跨越多个转录段落，"
            "end_seg_index 必须覆盖到最后一个包含相关内容的段落。**\n"
            "**对于长句子（>30个字），特别注意不要只匹配前半段而遗漏后半段。**\n\n"
            "输出JSON数组，每个元素包含：\n"
            '  - "script_index": int（脚本句子编号）\n'
            '  - "start_seg_index": int（对应转录的起始片段编号，含）\n'
            '  - "end_seg_index": int（对应转录的结束片段编号，含）\n'
            '  - "score": int（匹配置信度 0-100）\n\n'
            "片段编号就是转录片段前面方括号里的数字。\n"
            "如果某句在转录中找不到对应，score设为0。\n"
            "注意：脚本开头几句可能是从后面复制到前面的'钩子'，不要假设脚本顺序等于时间顺序。\n\n"
            "只返回合法的JSON数组，不要输出其他内容。"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                timeout=60,
            )
            content = response.choices[0].message.content.strip()
            matches_data = self._parse_json_response(content)

            results: list[MatchResult] = []
            for m in matches_data:
                score = float(m.get("score", 0))
                script_index = m["script_index"]

                if score == 0:
                    results.append(MatchResult(
                        script_index=script_index,
                        transcript_start_word_idx=0,
                        transcript_end_word_idx=0,
                        score=0.0,
                    ))
                    continue

                # Primary: segment-index-based mapping (new format)
                start_seg = m.get("start_seg_index")
                end_seg = m.get("end_seg_index")
                mapped_indices: Optional[tuple[int, int]] = None

                if start_seg is not None and end_seg is not None:
                    mapped_indices = self._seg_range_to_word_indices(
                        int(start_seg), int(end_seg), all_words
                    )
                if mapped_indices is None:
                    # Fallback: time-based mapping (legacy format)
                    start_time = m.get("start_time")
                    end_time = m.get("end_time")

                    if start_time is not None and end_time is not None:
                        mapped_indices = self._time_to_word_indices(
                            float(start_time), float(end_time), all_words
                        )

                if mapped_indices is None:
                    # Last resort: char-based mapping
                    start_char = m.get("start_char", 0)
                    end_char = m.get("end_char", 0)
                    mapped_indices = self._char_to_word_indices(
                        start_char, end_char, all_words
                    )

                if mapped_indices is None:
                    # No trustworthy coordinates were returned, so treat this
                    # as an unmatched sentence rather than inventing a
                    # transcript position.
                    results.append(MatchResult(
                        script_index=script_index,
                        transcript_start_word_idx=0,
                        transcript_end_word_idx=0,
                        score=0.0,
                    ))
                    continue

                start_word_idx, end_word_idx = mapped_indices

                results.append(MatchResult(
                    script_index=script_index,
                    transcript_start_word_idx=start_word_idx,
                    transcript_end_word_idx=end_word_idx,
                    score=score,
                ))

            # Post-processing: validate coverage and expand truncated matches
            results = self._validate_coverage(
                results, batch_sentences, all_words, matches_data
            )

            return results
        except Exception as e:
            logger.error(f"LLM batch matching failed: {e}")
            return []

    def _validate_coverage(
        self,
        results: list[MatchResult],
        batch_sentences: list[tuple[int, str]],
        all_words: list[dict],
        matches_data: list[dict],
    ) -> list[MatchResult]:
        """Check matched transcript text covers enough of the script sentence.

        If coverage < 70%, try expanding end_seg_index by 1-2 segments to
        capture the rest of a truncated sentence.
        """
        sentence_map = {idx: text for idx, text in batch_sentences}
        match_data_map = {
            int(m.get("script_index", -1)): m for m in matches_data
        }

        for i, result in enumerate(results):
            if result.score == 0:
                continue

            script_text = sentence_map.get(result.script_index, "")
            if not script_text or len(script_text) < 10:
                continue  # skip short sentences, coverage check not meaningful

            # Get matched transcript text from word indices
            matched_words = all_words[
                result.transcript_start_word_idx:result.transcript_end_word_idx
            ]
            matched_text = "".join(w["word"] for w in matched_words)

            # Calculate character coverage
            script_chars = set(script_text.replace(" ", ""))
            matched_chars = set(matched_text.replace(" ", ""))
            overlap = len(script_chars & matched_chars)
            coverage = overlap / len(script_chars) if script_chars else 1.0

            if coverage >= 0.7:
                continue  # good enough

            # Try expanding end_seg_index by 1-2
            m_data = match_data_map.get(result.script_index)
            if m_data is None:
                continue

            start_seg = m_data.get("start_seg_index")
            end_seg = m_data.get("end_seg_index")
            if start_seg is None or end_seg is None:
                continue

            best_coverage = coverage
            best_indices = (result.transcript_start_word_idx, result.transcript_end_word_idx)

            # Try expanding end_seg_index by 1-2 (captures truncated tail)
            for expand in range(1, 3):
                expanded = self._seg_range_to_word_indices(
                    int(start_seg), int(end_seg) + expand, all_words
                )
                if expanded is None:
                    break
                exp_words = all_words[expanded[0]:expanded[1]]
                exp_text = "".join(w["word"] for w in exp_words)
                exp_chars = set(exp_text.replace(" ", ""))
                exp_overlap = len(script_chars & exp_chars)
                exp_coverage = exp_overlap / len(script_chars) if script_chars else 1.0

                if exp_coverage > best_coverage:
                    best_coverage = exp_coverage
                    best_indices = expanded

            # Try expanding start_seg_index backward by 1-2 (captures truncated head)
            for expand in range(1, 3):
                new_start = int(start_seg) - expand
                if new_start < 0:
                    break
                expanded = self._seg_range_to_word_indices(
                    new_start, int(end_seg), all_words
                )
                if expanded is None:
                    break
                exp_words = all_words[expanded[0]:expanded[1]]
                exp_text = "".join(w["word"] for w in exp_words)
                exp_chars = set(exp_text.replace(" ", ""))
                exp_overlap = len(script_chars & exp_chars)
                exp_coverage = exp_overlap / len(script_chars) if script_chars else 1.0

                if exp_coverage > best_coverage:
                    best_coverage = exp_coverage
                    best_indices = expanded

            if best_indices != (result.transcript_start_word_idx, result.transcript_end_word_idx):
                logger.info(
                    "Coverage fix for script[%d]: %.0f%% -> %.0f%% by expanding segments",
                    result.script_index,
                    coverage * 100,
                    best_coverage * 100,
                )
                results[i] = MatchResult(
                    script_index=result.script_index,
                    transcript_start_word_idx=best_indices[0],
                    transcript_end_word_idx=best_indices[1],
                    score=result.score,
                )

        return results

    async def match_segments(
        self,
        script_sentences: list[str],
        transcript_segments: list[dict],
    ) -> list[MatchResult]:
        """Match script sentences to transcript using LLM with batching."""

        timestamped_transcript, all_words = self._build_timestamped_transcript(
            transcript_segments
        )

        # If few sentences, do a single call
        if len(script_sentences) <= self.BATCH_SIZE:
            indexed = list(enumerate(script_sentences))
            return await self._match_batch(
                indexed, timestamped_transcript, all_words
            )

        # Otherwise split into batches
        all_results: list[MatchResult] = []
        for batch_start in range(0, len(script_sentences), self.BATCH_SIZE):
            batch_end = min(batch_start + self.BATCH_SIZE, len(script_sentences))
            batch = [
                (i, script_sentences[i])
                for i in range(batch_start, batch_end)
            ]
            logger.info(
                f"LLM matching batch: sentences {batch_start}-{batch_end - 1} "
                f"of {len(script_sentences)}"
            )
            batch_results = await self._match_batch(
                batch, timestamped_transcript, all_words
            )
            all_results.extend(batch_results)

        return all_results
