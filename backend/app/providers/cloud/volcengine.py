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
        """Convert seconds to [HH:MM:SS] format."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"[{h:02d}:{m:02d}:{s:02d}]"

    def _build_timestamped_transcript(
        self, transcript_segments: list[dict]
    ) -> tuple[str, list[dict]]:
        """Build a timestamped transcript string and a flat word list.

        Returns:
            (timestamped_text, all_words)
            where all_words is a list of {"word": str, "start": float, "end": float, "seg_idx": int}
        """
        lines: list[str] = []
        all_words: list[dict] = []

        for seg_idx, seg in enumerate(transcript_segments):
            ts = self._format_timestamp(seg.get("start", 0.0))
            seg_text = seg.get("text", "")
            lines.append(f"{ts} {seg_text}")

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
    ) -> tuple[int, int]:
        """Map character offsets in the flat word string to word indices."""
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

    def _time_to_word_indices(
        self, start_time: float, end_time: float, all_words: list[dict]
    ) -> tuple[int, int]:
        """Map start/end times (seconds) to word indices."""
        start_word_idx = 0
        end_word_idx = len(all_words)

        # Find first word that starts at or after start_time
        for idx, w in enumerate(all_words):
            if w["start"] >= start_time - 0.05:
                start_word_idx = idx
                break

        # Find last word that ends at or before end_time
        for idx in range(len(all_words) - 1, -1, -1):
            if all_words[idx]["end"] <= end_time + 0.05:
                end_word_idx = idx + 1
                break

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
            f"## 转录片段（带时间戳）：\n{timestamped_transcript}\n\n"
            "请为脚本中的每个句子找到对应的转录片段时间范围。\n"
            "输出JSON数组，每个元素包含：\n"
            '  - "script_index": int（脚本句子编号）\n'
            '  - "start_time": float（对应转录的开始时间，秒）\n'
            '  - "end_time": float（对应转录的结束时间，秒）\n'
            '  - "score": int（匹配置信度 0-100）\n\n'
            "如果某句在转录中找不到对应，score设为0。\n"
            "注意：脚本开头几句可能是从后面复制到前面的'钩子'，不要假设脚本顺序等于时间顺序。\n\n"
            "只返回合法的JSON数组，不要输出其他内容。"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
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

                # Use time-based mapping (primary) — LLM returns times
                start_time = m.get("start_time")
                end_time = m.get("end_time")

                if start_time is not None and end_time is not None:
                    start_word_idx, end_word_idx = self._time_to_word_indices(
                        float(start_time), float(end_time), all_words
                    )
                else:
                    # Fallback: char-based mapping if LLM returned chars
                    start_char = m.get("start_char", 0)
                    end_char = m.get("end_char", 0)
                    start_word_idx, end_word_idx = self._char_to_word_indices(
                        start_char, end_char, all_words
                    )

                results.append(MatchResult(
                    script_index=script_index,
                    transcript_start_word_idx=start_word_idx,
                    transcript_end_word_idx=end_word_idx,
                    score=score,
                ))

            return results
        except Exception as e:
            logger.error(f"LLM batch matching failed: {e}")
            return []

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
