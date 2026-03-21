"""
Volcengine Caption API transcriber (音视频字幕生成).

Uses the ByteDance OpenSpeech API to transcribe audio with word-level
timestamps, returning results in the standard TranscriptionResult format.
"""

import asyncio
import logging
import mimetypes
from pathlib import Path
from typing import Callable, Optional

import httpx

from app.models.schemas import (
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionWord,
)
from app.providers.base import Transcriber

logger = logging.getLogger(__name__)


class VolcengineCaptionTranscriber(Transcriber):
    """Transcribe audio via the Volcengine Caption (字幕生成) REST API."""

    def __init__(self, appid: str, token: str):
        self.appid = appid
        self.token = token
        self.base_url = "https://openspeech.bytedance.com/api/v1/vc"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def transcribe(
        self,
        audio_path: str,
        language: str = "zh",
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> TranscriptionResult:
        """Submit audio to the cloud API and poll until results are ready."""

        def _progress(pct: float, msg: str) -> None:
            if progress_callback:
                progress_callback(pct, msg)

        # 1. Read audio file
        _progress(0.1, "读取音频文件...")
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        audio_data = audio_file.read_bytes()
        content_type = self._content_type(audio_file)

        # 2. Submit to API
        _progress(0.2, "提交到火山引擎云端...")
        task_id = await self._submit(audio_data, content_type, language)
        logger.info("Volcengine caption task submitted: %s", task_id)

        # 3. Poll for results
        result_json = await self._poll(task_id, _progress)

        # 4. Convert to TranscriptionResult
        _progress(0.9, "解析转录结果...")
        transcription = self._parse_response(result_json, language)

        _progress(1.0, "转录完成")
        return transcription

    # ------------------------------------------------------------------
    # No model to load – provide a no-op so the worker doesn't crash
    # ------------------------------------------------------------------

    def _ensure_model(self) -> None:  # noqa: D401
        """Cloud transcriber has no local model to load."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _content_type(path: Path) -> str:
        ext = path.suffix.lower()
        mapping = {
            ".wav": "audio/wav",
            ".mp3": "audio/mp3",
            ".m4a": "audio/mp4",
            ".aac": "audio/aac",
            ".flac": "audio/flac",
            ".ogg": "audio/ogg",
        }
        return mapping.get(ext, mimetypes.guess_type(str(path))[0] or "audio/wav")

    @staticmethod
    def _lang_code(language: str) -> str:
        """Map short language codes to the API's expected format."""
        mapping = {
            "zh": "zh-CN",
            "en": "en-US",
            "ja": "ja-JP",
        }
        return mapping.get(language, language)

    # ---- submit -------------------------------------------------------

    async def _submit(
        self, audio_data: bytes, content_type: str, language: str
    ) -> str:
        params = {
            "appid": self.appid,
            "language": self._lang_code(language),
            "use_itn": "True",
            "use_punc": "True",
            "caption_type": "speech",
            "use_ddc": "True",
            "words_per_line": "15",
            "max_lines": "1",
        }
        headers = {
            "Authorization": f"Bearer; {self.token}",
            "Content-Type": content_type,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/submit",
                params=params,
                headers=headers,
                content=audio_data,
            )
            resp.raise_for_status()
            body = resp.json()

        code = str(body.get("code", ""))
        if code != "0":
            raise RuntimeError(
                f"Volcengine submit failed (code={code}): "
                f"{body.get('message', 'unknown error')}"
            )

        task_id = body.get("id")
        if not task_id:
            raise RuntimeError("Volcengine submit returned no task id")
        return task_id

    # ---- poll ---------------------------------------------------------

    async def _poll(
        self,
        task_id: str,
        _progress: Callable[[float, str], None],
        *,
        interval: float = 2.0,
        max_attempts: int = 300,  # 10 minutes at 2s intervals
    ) -> dict:
        params = {
            "appid": self.appid,
            "id": task_id,
            "blocking": "0",
        }
        headers = {
            "Authorization": f"Bearer; {self.token}",
        }

        for attempt in range(max_attempts):
            # Progress ramps from 0.3 → 0.8 during polling
            poll_pct = 0.3 + 0.5 * min(attempt / 60, 1.0)
            _progress(poll_pct, "云端转录中...")

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self.base_url}/query",
                    params=params,
                    headers=headers,
                )
                resp.raise_for_status()
                body = resp.json()

            code = body.get("code")
            # code 2000 means still processing
            if code == 2000 or str(code) == "2000":
                await asyncio.sleep(interval)
                continue

            if code == 0 or str(code) == "0":
                return body

            # Any other code is an error
            raise RuntimeError(
                f"Volcengine transcription failed (code={code}): "
                f"{body.get('message', 'unknown error')}"
            )

        raise TimeoutError(
            f"Volcengine transcription timed out after {max_attempts * interval:.0f}s"
        )

    # ---- parse --------------------------------------------------------

    @staticmethod
    def _parse_response(data: dict, language: str) -> TranscriptionResult:
        duration = float(data.get("duration", 0.0))
        utterances = data.get("utterances", [])

        segments: list[TranscriptionSegment] = []
        for utt in utterances:
            text = utt.get("text", "").strip()

            # Skip silent utterances (use_ddc artifacts)
            if not text:
                attr = utt.get("attribute", {})
                if attr.get("event") == "silent":
                    continue
                # Also skip any other empty-text utterances
                continue

            start = float(utt.get("start_time", 0)) / 1000.0
            end = float(utt.get("end_time", 0)) / 1000.0

            words: list[TranscriptionWord] = []
            for w in utt.get("words", []):
                w_text = w.get("text", "")
                if not w_text:
                    continue
                words.append(
                    TranscriptionWord(
                        word=w_text,
                        start=float(w.get("start_time", 0)) / 1000.0,
                        end=float(w.get("end_time", 0)) / 1000.0,
                        confidence=1.0,
                    )
                )

            # If the utterance has text but no word-level breakdown,
            # synthesize a single word from the segment text/timestamps
            # so the flat word list used by matchers isn't missing content.
            if not words and text:
                words.append(
                    TranscriptionWord(
                        word=text,
                        start=start,
                        end=end,
                        confidence=0.8,
                    )
                )

            segments.append(
                TranscriptionSegment(
                    text=text,
                    start=start,
                    end=end,
                    words=words,
                )
            )

        return TranscriptionResult(
            segments=segments,
            language=language,
            duration=duration,
        )
