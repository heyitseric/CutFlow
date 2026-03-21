import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import PageContainer from '../components/layout/PageContainer';
import Stepper from '../components/layout/Stepper';
import { useJob } from '../hooks/useJob';
import { useJobStore, useActiveJob } from '../stores/jobStore';
import { getJob } from '../api/client';

// ── Sub-task types ──

interface SubTask {
  key: string;
  label: string;
}

// ── Stage definitions (aligned with backend 1-7) ──

const PROCESSING_STAGES = [
  { id: 1, name: '解析脚本' },
  { id: 2, name: '加载模型' },
  { id: 3, name: '语音转录' },
  { id: 4, name: '文本匹配' },
  { id: 5, name: '停顿检测' },
  { id: 6, name: '对齐校准' },
  { id: 7, name: '生成结果' },
] as const;

// ── Sub-tasks for each stage ──

const STAGE_SUBTASKS: Record<number, SubTask[]> = {
  1: [
    { key: 'read_md', label: '读取 Markdown 文件' },
    { key: 'extract_sentences', label: '提取句子' },
    { key: 'load_dict', label: '加载自定义词典' },
  ],
  2: [
    { key: 'init_engine', label: '初始化转录引擎' },
    { key: 'load_model', label: '加载 Whisper 模型' },
  ],
  3: [
    { key: 'transcribe', label: '音频转录' },
    { key: 'vad', label: '语音活动检测' },
    { key: 'segments', label: '分段处理' },
  ],
  4: [
    { key: 'init_matcher', label: '准备匹配器' },
    { key: 'fuzzy_match', label: '模糊文本匹配' },
    { key: 'llm_match', label: 'LLM 智能匹配' },
    { key: 'verify', label: '匹配结果验证' },
  ],
  5: [
    { key: 'detect_pauses', label: '检测停顿间隔' },
    { key: 'mark_errors', label: '标记口误片段' },
  ],
  6: [
    { key: 'align', label: '时间轴对齐' },
    { key: 'buffer', label: '添加缓冲区间 (0.15s)' },
  ],
  7: [
    { key: 'apply_buffer', label: '应用缓冲' },
    { key: 'gen_results', label: '生成匹配结果' },
    { key: 'preview', label: '生成预览数据' },
  ],
};

// ── Sub-task status resolution ──

type SubTaskStatus = 'completed' | 'active' | 'pending';

/**
 * Resolve sub-task statuses from backend-provided sub_tasks map.
 * Falls back to stage-level status when backend data is unavailable.
 */
function resolveSubTaskStatuses(
  stageId: number,
  stageStatus: 'done' | 'active' | 'pending',
  backendSubTasks: Record<string, string> | undefined,
): Record<string, SubTaskStatus> {
  const subtasks = STAGE_SUBTASKS[stageId];
  if (!subtasks) return {};

  const result: Record<string, SubTaskStatus> = {};

  // If the whole stage is done, all sub-tasks are completed
  if (stageStatus === 'done') {
    for (const st of subtasks) result[st.key] = 'completed';
    return result;
  }

  // If the stage hasn't started yet, all sub-tasks are pending
  if (stageStatus === 'pending') {
    for (const st of subtasks) result[st.key] = 'pending';
    return result;
  }

  // Stage is active — use backend sub-task data if available
  if (backendSubTasks) {
    for (const st of subtasks) {
      const backendStatus = backendSubTasks[st.key];
      if (backendStatus === 'completed') {
        result[st.key] = 'completed';
      } else if (backendStatus === 'in_progress') {
        result[st.key] = 'active';
      } else {
        result[st.key] = 'pending';
      }
    }
    return result;
  }

  // Fallback: no backend data, mark first sub-task as active
  for (let i = 0; i < subtasks.length; i++) {
    result[subtasks[i].key] = i === 0 ? 'active' : 'pending';
  }
  return result;
}

// ── Time formatting helpers ──

function formatElapsed(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0秒';
  const s = Math.floor(seconds);
  if (s < 60) return `${s}秒`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}分${rem}秒`;
}

function formatRemaining(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return '计算中...';
  const s = Math.round(seconds);
  if (s < 60) return `约${s}秒`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `约${m}分${rem}秒`;
}

// ── Fallback stage inference from legacy status ──

function inferStageFromStatus(status: string): number {
  switch (status) {
    case 'uploading': return 0;
    case 'transcribing': return 3;
    case 'matching': return 4;
    case 'aligning': return 6;
    case 'processing': return 4;
    case 'completed': return 8;
    case 'failed': return 0;
    default: return 0;
  }
}

// ── Safe percentage formatting ──

function safePercent(progress: number): number {
  const pct = Math.round(progress * 100);
  return Number.isFinite(pct) ? Math.max(0, Math.min(100, pct)) : 0;
}

// ── Sub-task status icon components ──

function SubTaskCheckIcon() {
  return (
    <svg className="h-3.5 w-3.5 text-success shrink-0" viewBox="0 0 20 20" fill="currentColor">
      <path
        fillRule="evenodd"
        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function SubTaskSpinnerIcon() {
  return (
    <div className="h-3 w-3 rounded-full border-[1.5px] border-amber border-t-transparent animate-spin shrink-0" />
  );
}

function SubTaskPendingIcon() {
  return (
    <div className="h-2 w-2 rounded-full bg-text-faint shrink-0" />
  );
}

// ── Chevron icon ──

function ChevronIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg
      className={`h-3.5 w-3.5 text-text-faint transition-transform duration-300 ${expanded ? 'rotate-90' : ''}`}
      viewBox="0 0 20 20"
      fill="currentColor"
    >
      <path
        fillRule="evenodd"
        d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
        clipRule="evenodd"
      />
    </svg>
  );
}

// ── Component ──

export default function ProcessingPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const setJob = useJobStore((s) => s.setJob);
  const setActiveJob = useJobStore((s) => s.setActiveJob);
  const { status, progress, error, stageProgress, elapsedSeconds, estimatedRemainingSeconds } = useActiveJob();

  // Track which stages are expanded (by stage id)
  const [expandedStages, setExpandedStages] = useState<Set<number>>(new Set());

  const toggleStage = useCallback((stageId: number) => {
    setExpandedStages((prev) => {
      const next = new Set(prev);
      if (next.has(stageId)) {
        next.delete(stageId);
      } else {
        next.add(stageId);
      }
      return next;
    });
  }, []);

  // Ensure active job is set when navigating directly to this page
  useEffect(() => {
    if (id) {
      setActiveJob(id);
    }
  }, [id, setActiveJob]);

  useJob(id);

  useEffect(() => {
    if (id) {
      getJob(id).then(setJob).catch(() => {});
    }
  }, [id, setJob]);

  useEffect(() => {
    if (status === 'completed' && id) {
      const timer = setTimeout(() => navigate(`/review/${id}`), 1200);
      return () => clearTimeout(timer);
    }
  }, [status, id, navigate]);

  const isFailed = status === 'failed';
  const isComplete = status === 'completed';
  const pct = safePercent(progress);

  // Determine current stage (1-based) from stageProgress or fallback
  const currentStage = stageProgress?.stage ?? inferStageFromStatus(status);
  const stageDetail = stageProgress?.stage_detail ?? '';
  const elapsed = elapsedSeconds;
  const estimatedRemaining = estimatedRemainingSeconds;

  // All stages collapsed by default — user clicks to expand/collapse

  return (
    <>
      <Stepper currentStep={1} jobId={id} />
      <PageContainer>
        <div className="flex flex-col items-center gap-8 py-12 animate-fade-in-up">

          {/* ── Stage todo list ── */}
          <div className="w-full max-w-md">
            <ul className="flex flex-col gap-1">
              {PROCESSING_STAGES.map((stage) => {
                const isDone = isComplete || currentStage > stage.id;
                const isActive = !isComplete && !isFailed && currentStage === stage.id;
                const isPending = !isDone && !isActive;
                const stageStatus: 'done' | 'active' | 'pending' = isDone ? 'done' : isActive ? 'active' : 'pending';

                const subtasks = STAGE_SUBTASKS[stage.id] ?? [];
                const hasSubtasks = subtasks.length > 0;
                const isExpanded = expandedStages.has(stage.id);
                const subtaskStatuses = resolveSubTaskStatuses(stage.id, stageStatus, stageProgress?.sub_tasks);

                return (
                  <li key={stage.id} className="transition-all duration-500">
                    {/* Main stage row */}
                    <div
                      className={`
                        flex items-start gap-3 rounded-xl px-4 py-3 transition-all duration-500
                        ${isActive ? 'bg-amber-glow/40' : ''}
                        ${hasSubtasks ? 'cursor-pointer select-none' : ''}
                      `}
                      onClick={hasSubtasks ? () => toggleStage(stage.id) : undefined}
                    >
                      {/* Status icon */}
                      <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center">
                        {isDone && (
                          <svg
                            className="h-5 w-5 text-success animate-fade-in"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                          >
                            <path
                              fillRule="evenodd"
                              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                              clipRule="evenodd"
                            />
                          </svg>
                        )}
                        {isActive && (
                          <div className="h-4 w-4 rounded-full border-2 border-amber border-t-transparent animate-spin" />
                        )}
                        {isPending && (
                          <div className="h-3 w-3 rounded-full bg-text-faint" />
                        )}
                      </div>

                      {/* Text */}
                      <div className="min-w-0 flex-1">
                        <span
                          className={`
                            font-display text-sm font-medium transition-colors duration-300
                            ${isDone ? 'text-text-secondary' : ''}
                            ${isActive ? 'text-amber' : ''}
                            ${isPending ? 'text-text-muted' : ''}
                          `}
                        >
                          {stage.name}
                        </span>
                        {isActive && stageDetail && !isExpanded && (
                          <p className="mt-0.5 text-xs text-text-muted animate-fade-in truncate">
                            {stageDetail}
                          </p>
                        )}
                      </div>

                      {/* Chevron */}
                      {hasSubtasks && (
                        <div className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center">
                          <ChevronIcon expanded={isExpanded} />
                        </div>
                      )}
                    </div>

                    {/* Expandable sub-tasks */}
                    <div
                      className="overflow-hidden transition-all duration-300 ease-in-out"
                      style={{
                        maxHeight: isExpanded ? `${subtasks.length * 36 + 8}px` : '0px',
                        opacity: isExpanded ? 1 : 0,
                      }}
                    >
                      <div className="ml-[2.75rem] pb-1 pt-0.5">
                        {subtasks.map((subtask, idx) => {
                          const isLast = idx === subtasks.length - 1;
                          const stStatus = subtaskStatuses[subtask.key] ?? 'pending';
                          const connector = isLast ? '\u2514\u2500' : '\u251C\u2500';

                          return (
                            <div
                              key={subtask.key}
                              className="flex items-center gap-2 py-1"
                            >
                              {/* Tree connector */}
                              <span
                                className="text-xs font-mono select-none shrink-0"
                                style={{ color: 'rgba(255,255,255,0.15)', width: '1rem' }}
                              >
                                {connector}
                              </span>

                              {/* Sub-task status icon */}
                              <div className="flex h-4 w-4 items-center justify-center shrink-0">
                                {stStatus === 'completed' && <SubTaskCheckIcon />}
                                {stStatus === 'active' && <SubTaskSpinnerIcon />}
                                {stStatus === 'pending' && <SubTaskPendingIcon />}
                              </div>

                              {/* Sub-task label */}
                              <span
                                className={`
                                  text-xs transition-colors duration-300
                                  ${stStatus === 'completed' ? 'text-text-secondary/70' : ''}
                                  ${stStatus === 'active' ? 'text-text-secondary' : ''}
                                  ${stStatus === 'pending' ? 'text-text-muted/50' : ''}
                                `}
                              >
                                {subtask.label}
                              </span>

                              {/* Show detail text next to active sub-task */}
                              {stStatus === 'active' && isActive && stageDetail && (
                                <span className="text-[11px] text-text-muted truncate ml-1 animate-fade-in">
                                  {stageDetail}
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>

          {/* ── Progress bar ── */}
          <div className="w-full max-w-md">
            <div className="h-1.5 overflow-hidden rounded-full bg-elevated">
              <div
                className={`h-full rounded-full transition-all duration-700 ease-out ${
                  isFailed ? 'bg-danger' : isComplete ? 'bg-success' : 'bg-amber progress-stripe'
                }`}
                style={{ width: `${pct}%` }}
              />
            </div>

            {/* Percentage — show "准备中..." when 0 and not yet started */}
            <div className="mt-2 text-center">
              <span className="font-mono text-xs text-text-muted">
                {pct === 0 && !isComplete && !isFailed ? '准备中...' : `${pct}%`}
              </span>
            </div>

            {/* Time info */}
            {!isComplete && !isFailed && (
              <div className="mt-1 flex justify-between">
                <span className="font-mono text-[11px] text-text-muted">
                  已耗时: {formatElapsed(elapsed)}
                </span>
                <span className="font-mono text-[11px] text-text-muted">
                  预计剩余: {formatRemaining(estimatedRemaining)}
                </span>
              </div>
            )}
          </div>

          {/* ── Error state ── */}
          {error && (
            <div className="max-w-md animate-slide-down rounded-2xl border border-danger/20 bg-danger-surface p-5">
              <p className="font-display text-sm font-semibold text-danger">处理出错</p>
              <p className="mt-2 text-sm text-text-secondary">{error}</p>
              <button
                onClick={() => navigate('/')}
                className="mt-4 rounded-xl bg-danger/10 px-5 py-2 text-sm font-medium text-danger hover:bg-danger/20 transition-colors"
              >
                返回重试
              </button>
            </div>
          )}

          {/* ── Completed state ── */}
          {isComplete && (
            <div className="animate-slide-down rounded-2xl border border-success/20 bg-success-surface p-5 text-center">
              <div className="flex items-center justify-center gap-2 text-sm text-success">
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                处理完成，即将跳转至审核页面...
              </div>
            </div>
          )}
        </div>
      </PageContainer>
    </>
  );
}
