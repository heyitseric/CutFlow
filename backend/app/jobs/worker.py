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
from app.services.transcript_consolidator import consolidate_segments
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
        sub_tasks: Optional[dict[str, str]] = None,
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
            sub_tasks=sub_tasks,
        )

    def start_subtask(self, key: str):
        """Mark a sub-task as in_progress."""
        self.manager.update_job(
            self.job.job_id,
            sub_tasks={key: "in_progress"},
        )

    def complete_subtask(self, key: str):
        """Mark a sub-task as completed."""
        self.manager.update_job(
            self.job.job_id,
            sub_tasks={key: "completed"},
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
        # Initialize all stage-1 sub-tasks as pending
        p.update(1, "解析脚本", 0.0, "正在解析脚本文件…", state=JobState.TRANSCRIBING,
                 sub_tasks={"read_md": "pending", "extract_sentences": "pending", "load_dict": "pending"})

        p.start_subtask("read_md")
        script_text = Path(job.script_path).read_text(encoding="utf-8")
        job.script_text = script_text
        p.complete_subtask("read_md")

        p.start_subtask("extract_sentences")
        p.update(1, "解析脚本", 0.5, "正在提取句子…")
        script_sentences = parse_script(script_text)
        if not script_sentences:
            raise ValueError("No sentences found in script")
        logger.info(f"Parsed {len(script_sentences)} sentences from script")
        p.complete_subtask("extract_sentences")

        p.start_subtask("load_dict")
        p.update(1, "解析脚本", 0.8, "正在加载词典…")
        # Dict loading happens in stage 2 but we report the sub-task here
        p.complete_subtask("load_dict")

        p.update(1, "解析脚本", 1.0, f"脚本解析完成，共 {len(script_sentences)} 句")

        # ---- Stage 2: Load models (8%) ----
        p.update(2, "加载模型", 0.0, "正在初始化转录引擎…",
                 sub_tasks={"init_engine": "pending", "load_model": "pending"})

        p.start_subtask("init_engine")
        p.update(2, "加载模型", 0.1, "正在初始化字典服务…")

        dict_service = DictionaryService(settings.DICTIONARY_DIR)
        dict_service.inject_into_jieba()

        try:
            transcriber = get_transcriber(provider=job.provider)
        except ImportError as e:
            logger.warning(f"Local transcription unavailable: {e}")
            raise ValueError(
                "No transcription backend available. "
                "Install whisperx, stable-ts, or openai-whisper."
            )
        p.complete_subtask("init_engine")

        p.start_subtask("load_model")
        p.update(2, "加载模型", 0.5, "正在加载 Whisper 模型（首次需下载约1.3GB）…")
        await asyncio.to_thread(transcriber._ensure_model)
        p.complete_subtask("load_model")

        p.update(2, "加载模型", 1.0, "模型加载完成")

        tx_service = TranscriptionService(
            transcriber=transcriber,
            dictionary_service=dict_service,
        )

        # ---- Stage 3: Transcribe audio (55%) ----
        p.update(3, "语音转录", 0.0, "正在开始转录…", state=JobState.TRANSCRIBING,
                 sub_tasks={"transcribe": "pending", "vad": "pending", "segments": "pending"})

        p.start_subtask("transcribe")

        def progress_cb(pct: float, msg: str):
            # pct is 0-1 within transcription
            # Map sub-task transitions based on progress thresholds
            if pct > 0.0 and pct < 0.7:
                p.update(3, "语音转录", pct, msg)
            elif pct >= 0.7 and pct < 0.9:
                p.complete_subtask("transcribe")
                p.start_subtask("vad")
                p.update(3, "语音转录", pct, msg)
            elif pct >= 0.9:
                p.complete_subtask("vad")
                p.start_subtask("segments")
                p.update(3, "语音转录", pct, msg)

        transcription = await tx_service.transcribe(
            job.audio_path,
            language=settings.WHISPER_LANGUAGE,
            progress_callback=progress_cb,
        )
        job.transcription = transcription

        # Ensure all sub-tasks are completed
        p.complete_subtask("transcribe")
        p.complete_subtask("vad")
        p.complete_subtask("segments")

        logger.info(
            f"Transcription complete: {len(transcription.segments)} segments, "
            f"duration={transcription.duration:.1f}s"
        )

        # Consolidate fine-grained segments into sentence-level groups
        # so that the matcher receives manageable, sentence-sized chunks
        # instead of thousands of word-level fragments.
        raw_segment_count = len(transcription.segments)
        transcription = consolidate_segments(transcription)
        if len(transcription.segments) != raw_segment_count:
            logger.info(
                f"Segments consolidated: {raw_segment_count} -> "
                f"{len(transcription.segments)}"
            )
        job.transcription = transcription

        p.update(
            3, "语音转录", 1.0,
            f"转录完成，共 {len(transcription.segments)} 段，"
            f"时长 {transcription.duration:.0f} 秒",
        )

        # ---- Stage 4: Match script to transcript (20%) ----
        p.update(4, "文本匹配", 0.0, "正在准备匹配器…", state=JobState.MATCHING,
                 sub_tasks={"init_matcher": "pending", "fuzzy_match": "pending",
                            "llm_match": "pending"})

        p.start_subtask("init_matcher")
        # Always get local (RapidFuzz) matcher as fallback
        local_matcher = get_local_matcher()
        cloud_matcher = None
        if settings.CLOUD_PROVIDER == "volcengine" and settings.ARK_API_KEY:
            try:
                from app.providers.cloud.volcengine import VolcEngineMatcher
                cloud_matcher = VolcEngineMatcher()
                logger.info("LLM matcher (VolcEngine) enabled as primary")
            except Exception as e:
                logger.warning(f"Failed to init LLM matcher: {e}")

        matcher_service = MatcherService(
            matcher=local_matcher,
            cloud_matcher=cloud_matcher,
        )
        p.complete_subtask("init_matcher")

        p.start_subtask("fuzzy_match")
        p.update(4, "文本匹配", 0.2, "正在进行文本匹配…")

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
        p.complete_subtask("fuzzy_match")

        p.start_subtask("llm_match")
        p.update(4, "文本匹配", 0.5, "正在进行智能匹配…")

        match_results = await matcher_service.match(
            [s.text for s in script_sentences],
            transcript_dicts,
        )
        p.complete_subtask("llm_match")

        logger.info(f"Matching complete: {len(match_results)} match candidates")

        p.update(
            4, "文本匹配", 1.0,
            f"匹配完成，共 {len(match_results)} 个匹配候选",
        )

        # ---- Stage 5: Detect pauses (5%) ----
        p.update(5, "停顿检测", 0.0, "正在检测语音停顿…", state=JobState.ALIGNING,
                 sub_tasks={"detect_pauses": "pending", "mark_errors": "pending"})

        p.start_subtask("detect_pauses")
        pauses = detect_pauses(transcription, script_sentences)
        logger.info(f"Detected {len(pauses)} pauses")
        p.complete_subtask("detect_pauses")

        p.start_subtask("mark_errors")
        p.update(5, "停顿检测", 0.7, "正在标记口误片段…")
        p.complete_subtask("mark_errors")

        p.update(5, "停顿检测", 1.0, f"停顿检测完成，发现 {len(pauses)} 个停顿")

        # ---- Stage 6: Align segments (5%) ----
        p.update(6, "对齐校准", 0.0, "正在对齐脚本与音频片段…",
                 sub_tasks={"align": "pending", "buffer": "pending"})

        p.start_subtask("align")
        alignment = align_segments(
            script_sentences, match_results, transcription, pauses
        )
        p.complete_subtask("align")

        p.start_subtask("buffer")
        p.update(6, "对齐校准", 0.7, "对齐完成，准备应用缓冲…")

        # NOTE: Leading/trailing pause trimming is handled in
        # alignment_engine.align_segments() — do NOT duplicate it here.

        p.complete_subtask("buffer")

        p.update(6, "对齐校准", 1.0, "对齐校准完成")

        # ---- Stage 7: Generate results / apply buffer (5%) ----
        p.update(7, "生成结果", 0.0, "正在应用缓冲…",
                 sub_tasks={"apply_buffer": "pending", "gen_results": "pending", "preview": "pending"})

        p.start_subtask("apply_buffer")
        alignment = apply_buffer(alignment, settings.BUFFER_DURATION)
        job.alignment = alignment
        p.complete_subtask("apply_buffer")

        p.start_subtask("gen_results")
        p.update(7, "生成结果", 0.5, "正在生成匹配结果…")

        matched_count = sum(
            1 for s in alignment
            if s.status.value in ("matched", "copy", "approved")
        )
        logger.info(
            f"Alignment complete: {matched_count}/{len(alignment)} segments matched"
        )
        p.complete_subtask("gen_results")

        p.start_subtask("preview")
        p.update(7, "生成结果", 0.8, "正在生成预览数据…")
        p.complete_subtask("preview")

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

    except TimeoutError as e:
        logger.error(f"Pipeline timed out for job {job.job_id}: {e}", exc_info=True)
        manager.update_job(
            job.job_id, state=JobState.ERROR, progress=0.0,
            message=f"请求超时，请检查网络连接后重试: {e}",
            estimated_remaining_seconds=None,
        )
        job.error = str(e)
    except Exception as e:
        logger.error(f"Pipeline failed for job {job.job_id}: {e}", exc_info=True)
        manager.update_job(
            job.job_id, state=JobState.ERROR, progress=0.0,
            message=f"Error: {str(e)}",
            estimated_remaining_seconds=None,
        )
        job.error = str(e)
