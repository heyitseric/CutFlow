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
    """Use VolcEngine (Doubao) LLM to match script sentences to transcript."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=settings.ARK_API_KEY,
            base_url=settings.CLOUD_BASE_URL,
        )
        self.model = settings.CLOUD_MODEL

    async def match_segments(
        self,
        script_sentences: list[str],
        transcript_segments: list[dict],
    ) -> list[MatchResult]:
        # Build transcript text with word indices
        all_words = []
        for seg in transcript_segments:
            for w in seg.get("words", []):
                all_words.append(w.get("word", ""))

        transcript_text = "".join(all_words)

        # Build numbered script
        numbered_script = "\n".join(
            f"[{i}] {s}" for i, s in enumerate(script_sentences)
        )

        prompt = (
            "You are a script-to-transcript alignment expert for Chinese video editing.\n\n"
            f"SCRIPT SENTENCES:\n{numbered_script}\n\n"
            f"TRANSCRIPT:\n{transcript_text}\n\n"
            "For each script sentence, find the corresponding text span in the transcript. "
            "Return a JSON array where each element has:\n"
            '  - "script_index": the sentence number\n'
            '  - "start_char": start character index in transcript\n'
            '  - "end_char": end character index in transcript\n'
            '  - "score": confidence 0-100\n\n'
            "If a sentence is not found in the transcript, set score to 0.\n"
            "Return ONLY valid JSON, no other text."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            content = response.choices[0].message.content.strip()

            # Parse JSON from response (handle markdown code blocks)
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])
            matches_data = json.loads(content)

            results = []
            for m in matches_data:
                # Convert character indices to word indices (approximate)
                start_char = m.get("start_char", 0)
                end_char = m.get("end_char", 0)

                # Map character position to word index
                char_count = 0
                start_word_idx = 0
                end_word_idx = 0
                for idx, word in enumerate(all_words):
                    if char_count <= start_char:
                        start_word_idx = idx
                    char_count += len(word)
                    if char_count >= end_char:
                        end_word_idx = idx + 1
                        break
                else:
                    end_word_idx = len(all_words)

                results.append(MatchResult(
                    script_index=m["script_index"],
                    transcript_start_word_idx=start_word_idx,
                    transcript_end_word_idx=end_word_idx,
                    score=float(m.get("score", 0)),
                ))

            return results
        except Exception as e:
            logger.error(f"Cloud matching failed: {e}")
            return []
