import asyncio
import logging
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.jobs.manager import JobData, get_job_manager
from app.models.schemas import JobState
from app.providers.config import get_local_matcher, get_matcher, get_transcriber
from app.services.alignment_engine import align_segments
from app.services.buffer import apply_buffer
from app.services.dictionary import DictionaryService
from app.services.matcher import MatcherService
from app.services.pause_processor import detect_pauses
from app.services.script_parser import parse_script
from app.services.transcription import TranscriptionService

logger = logging.getLogger(__name__)


async def run_pipeline(job: JobData) -> None:
    """
    Execute the full processing pipeline:
    1. Parse script
    2. Transcribe audio
    3. Match script to transcript
    4. Align segments
    5. Detect pauses
    6. Apply buffer
    """
    settings = get_settings()
    manager = get_job_manager()

    try:
        # --- Step 1: Parse script ---
        manager.update_job(
            job.job_id, state=JobState.TRANSCRIBING, progress=0.05,
            message="Parsing script...",
        )

        script_text = Path(job.script_path).read_text(encoding="utf-8")
        job.script_text = script_text
        script_sentences = parse_script(script_text)

        if not script_sentences:
            raise ValueError("No sentences found in script")

        logger.info(f"Parsed {len(script_sentences)} sentences from script")

        # --- Step 2: Transcribe audio ---
        manager.update_job(
            job.job_id, state=JobState.TRANSCRIBING, progress=0.1,
            message="Starting transcription...",
        )

        dict_service = DictionaryService(settings.DICTIONARY_DIR)
        dict_service.inject_into_jieba()

        try:
            transcriber = get_transcriber()
        except ImportError as e:
            logger.warning(f"Local transcription unavailable: {e}")
            raise ValueError(
                "No transcription backend available. "
                "Install whisperx, stable-ts, or openai-whisper."
            )

        tx_service = TranscriptionService(
            transcriber=transcriber,
            dictionary_service=dict_service,
        )

        def progress_cb(pct: float, msg: str):
            overall = 0.1 + pct * 0.4  # Transcription is 10-50%
            manager.update_job(
                job.job_id, progress=overall, message=msg,
            )

        transcription = await tx_service.transcribe(
            job.audio_path,
            language=settings.WHISPER_LANGUAGE,
            progress_callback=progress_cb,
        )
        job.transcription = transcription

        logger.info(
            f"Transcription complete: {len(transcription.segments)} segments, "
            f"duration={transcription.duration:.1f}s"
        )

        # --- Step 3: Match script to transcript ---
        manager.update_job(
            job.job_id, state=JobState.MATCHING, progress=0.55,
            message="Matching script to transcript...",
        )

        matcher = get_matcher()
        cloud_matcher = None
        if settings.CLOUD_PROVIDER == "volcengine" and settings.ARK_API_KEY:
            try:
                from app.providers.cloud.volcengine import VolcEngineMatcher
                cloud_matcher = VolcEngineMatcher()
            except Exception:
                pass

        matcher_service = MatcherService(
            matcher=matcher,
            cloud_matcher=cloud_matcher,
        )

        transcript_dicts = [
            {
                "text": seg.text,
                "start": seg.start,
                "end": seg.end,
                "words": [
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "confidence": w.confidence,
                    }
                    for w in seg.words
                ],
            }
            for seg in transcription.segments
        ]

        match_results = await matcher_service.match(
            [s.text for s in script_sentences],
            transcript_dicts,
        )

        logger.info(f"Matching complete: {len(match_results)} match candidates")

        # --- Step 4: Detect pauses ---
        manager.update_job(
            job.job_id, state=JobState.ALIGNING, progress=0.7,
            message="Detecting pauses...",
        )

        pauses = detect_pauses(transcription, script_sentences)
        logger.info(f"Detected {len(pauses)} pauses")

        # --- Step 5: Align segments ---
        manager.update_job(
            job.job_id, progress=0.8, message="Aligning segments...",
        )

        alignment = align_segments(
            script_sentences, match_results, transcription, pauses
        )

        # --- Step 6: Apply buffer ---
        manager.update_job(
            job.job_id, progress=0.9, message="Applying buffer...",
        )

        alignment = apply_buffer(alignment, settings.BUFFER_DURATION)

        job.alignment = alignment

        matched_count = sum(
            1 for s in alignment
            if s.status.value in ("matched", "copy", "approved")
        )
        logger.info(
            f"Alignment complete: {matched_count}/{len(alignment)} segments matched"
        )

        # --- Done ---
        manager.update_job(
            job.job_id, state=JobState.REVIEW, progress=1.0,
            message="Processing complete. Ready for review.",
        )

    except Exception as e:
        logger.error(f"Pipeline failed for job {job.job_id}: {e}", exc_info=True)
        manager.update_job(
            job.job_id, state=JobState.ERROR, progress=0.0,
            message=f"Error: {str(e)}",
        )
        job.error = str(e)
