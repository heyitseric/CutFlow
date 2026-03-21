import asyncio
import logging
import time
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

# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------
# Each stage has: (number, chinese_name, weight_pct)
# Weights sum to 100 and define how much of the overall progress bar each
# stage occupies.
STAGES = [
    (1, "解析脚本", 2),       # Parsing script
    (2, "加载模型", 8),       # Loading models
    (3, "语音转录", 55),      # Transcribing audio
    (4, "文本匹配", 20),      # Matching text
    (5, "停顿检测", 5),       # Detecting pauses
    (6, "对齐校准", 5),       # Alignment
    (7, "生成结果", 5),       # Generating results
]

# Pre-compute cumulative offsets so we can quickly map stage-local progress
# to an overall 0-100 value.
_STAGE_OFFSET: dict[int, float] = {}
_STAGE_WEIGHT: dict[int, float] = {}
_cumulative = 0.0
for _num, _name, _weight in STAGES:
    _STAGE_OFFSET[_num] = _cumulative
    _STAGE_WEIGHT[_num] = _weight
    _cumulative += _weight


def _overall_progress(stage: int, local_pct: float = 0.0) -> float:
    """Convert stage number + local 0-1 fraction to overall 0-1 progress."""
    offset = _STAGE_OFFSET.get(stage, 0.0)
    weight = _STAGE_WEIGHT.get(stage, 0.0)
    return (offset + weight * max(0.0, min(1.0, local_pct))) / 100.0


def _estimate_remaining(start_time: float, progress: float) -> Optional[float]:
    """Estimate remaining seconds based on elapsed time and progress so far."""
    if progress <= 0.01:
        return None
    elapsed = time.monotonic() - start_time
    total_estimated = elapsed / progress
    remaining = total_estimated - elapsed
    return max(0.0, remaining)


class _ProgressHelper:
    """Small helper that emits granular progress updates via the manager."""

    def __init__(self, job: JobData):
        self.job = job
        self.manager = get_job_manager()

    def update(
        self,
        stage: int,
        stage_name: str,
        local_pct: float = 0.0,
        detail: str = "",
        state: Optional[JobState] = None,
    ):
        progress = _overall_progress(stage, local_pct)
        remaining = _estimate_remaining(self.job.pipeline_start_time, progress)
        self.manager.update_job(
            self.job.job_id,
            state=state,
            progress=progress,
            message=detail or stage_name,
            stage=stage,
            stage_name=stage_name,
            stage_detail=detail,
            estimated_remaining_seconds=remaining,
        )


async def run_pipeline(job: JobData) -> None:
    """
    Execute the full processing pipeline:
    1. Parse script          (2%)
    2. Load models           (8%)
    3. Transcribe audio      (55%)
    4. Match script          (20%)
    5. Detect pauses         (5%)
    6. Align segments        (5%)
    7. Generate results      (5%)
    """
    settings = get_settings()
    manager = get_job_manager()

    # Mark pipeline start for elapsed/ETA calculations
    job.pipeline_start_time = time.monotonic()

    p = _ProgressHelper(job)

    try:
        # ---- Stage 1: Parse script (2%) ----
        p.update(1, "解析脚本", 0.0, "正在解析脚本文件…", state=JobState.TRANSCRIBING)

        script_text = Path(job.script_path).read_text(encoding="utf-8")
        job.script_text = script_text
        script_sentences = parse_script(script_text)

        if not script_sentences:
            raise ValueError("No sentences found in script")

        logger.info(f"Parsed {len(script_sentences)} sentences from script")
        p.update(1, "解析脚本", 1.0, f"脚本解析完成，共 {len(script_sentences)} 句")

        # ---- Stage 2: Load models (8%) ----
        p.update(2, "加载模型", 0.0, "正在初始化字典服务…")

        dict_service = DictionaryService(settings.DICTIONARY_DIR)
        dict_service.inject_into_jieba()

        p.update(2, "加载模型", 0.3, "正在加载转录模型…")

        try:
            transcriber = get_transcriber(provider=job.provider)
        except ImportError as e:
            logger.warning(f"Local transcription unavailable: {e}")
            raise ValueError(
                "No transcription backend available. "
                "Install whisperx, stable-ts, or openai-whisper."
            )

        # Eagerly load the model so the user sees progress during download
        p.update(2, "加载模型", 0.5, "正在加载 Whisper 模型（首次需下载约1.3GB）…")
        await asyncio.to_thread(transcriber._ensure_model)

        p.update(2, "加载模型", 1.0, "模型加载完成")

        tx_service = TranscriptionService(
            transcriber=transcriber,
            dictionary_service=dict_service,
        )

        # ---- Stage 3: Transcribe audio (55%) ----
        p.update(3, "语音转录", 0.0, "正在开始转录…", state=JobState.TRANSCRIBING)

        def progress_cb(pct: float, msg: str):
            # pct is 0-1 within transcription
            p.update(3, "语音转录", pct, msg)

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
        p.update(
            3, "语音转录", 1.0,
            f"转录完成，共 {len(transcription.segments)} 段，"
            f"时长 {transcription.duration:.0f} 秒",
        )

        # ---- Stage 4: Match script to transcript (20%) ----
        p.update(4, "文本匹配", 0.0, "正在准备匹配器…", state=JobState.MATCHING)

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

        p.update(4, "文本匹配", 0.2, "正在匹配脚本与转录文本…")

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
        p.update(
            4, "文本匹配", 1.0,
            f"匹配完成，共 {len(match_results)} 个匹配候选",
        )

        # ---- Stage 5: Detect pauses (5%) ----
        p.update(5, "停顿检测", 0.0, "正在检测语音停顿…", state=JobState.ALIGNING)

        pauses = detect_pauses(transcription, script_sentences)
        logger.info(f"Detected {len(pauses)} pauses")

        p.update(5, "停顿检测", 1.0, f"停顿检测完成，发现 {len(pauses)} 个停顿")

        # ---- Stage 6: Align segments (5%) ----
        p.update(6, "对齐校准", 0.0, "正在对齐脚本与音频片段…")

        alignment = align_segments(
            script_sentences, match_results, transcription, pauses
        )

        p.update(6, "对齐校准", 1.0, "对齐校准完成")

        # ---- Stage 7: Generate results / apply buffer (5%) ----
        p.update(7, "生成结果", 0.0, "正在应用缓冲…")

        alignment = apply_buffer(alignment, settings.BUFFER_DURATION)
        job.alignment = alignment

        matched_count = sum(
            1 for s in alignment
            if s.status.value in ("matched", "copy", "approved")
        )
        logger.info(
            f"Alignment complete: {matched_count}/{len(alignment)} segments matched"
        )

        p.update(
            7, "生成结果", 1.0,
            f"处理完成：{matched_count}/{len(alignment)} 段已匹配",
        )

        # ---- Done ----
        manager.update_job(
            job.job_id,
            state=JobState.REVIEW,
            progress=1.0,
            message="处理完成，可以开始审阅。",
            stage=7,
            stage_name="完成",
            stage_detail="处理完成，可以开始审阅。",
            estimated_remaining_seconds=0.0,
        )

    except Exception as e:
        logger.error(f"Pipeline failed for job {job.job_id}: {e}", exc_info=True)
        manager.update_job(
            job.job_id, state=JobState.ERROR, progress=0.0,
            message=f"Error: {str(e)}",
            estimated_remaining_seconds=None,
        )
        job.error = str(e)
