import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Check, Loader2, Circle, CheckCircle2, ChevronRight, AlertTriangle } from 'lucide-react';
import PageContainer from '../components/layout/PageContainer';
import Stepper from '../components/layout/Stepper';
import { useJob } from '../hooks/useJob';
import { useJobStore, useActiveJob } from '../stores/jobStore';
import { getJob } from '../api/client';
import { Progress } from '@/components/ui/progress';
import { Card, CardContent } from '@/components/ui/card';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';

// ── Sub-task types ──

interface SubTask {
  key: string;
  label: string;
}

// ── Stage definitions (aligned with backend 1-8) ──

// ── Stage definitions — adapt to cloud vs local transcription ──

function getProcessingStages(isCloud: boolean) {
  return [
    { id: 1, name: '解析脚本' },
    { id: 2, name: isCloud ? '连接云端' : '加载模型' },
    { id: 3, name: isCloud ? '云端转录' : '本地转录' },
    { id: 4, name: '文本匹配' },
    { id: 5, name: '停顿检测' },
    { id: 6, name: '对齐校准' },
    { id: 7, name: '片段优化' },
    { id: 8, name: '生成结果' },
  ];
}

function getStageSubtasks(isCloud: boolean): Record<number, SubTask[]> {
  return {
    1: [
      { key: 'read_md', label: '读取 Markdown 文件' },
      { key: 'extract_sentences', label: '提取句子' },
      { key: 'load_dict', label: '加载自定义词典' },
    ],
    2: isCloud
      ? [
          { key: 'init_engine', label: '初始化云端 API' },
          { key: 'upload_audio', label: '上传音频文件' },
        ]
      : [
          { key: 'init_engine', label: '初始化转录引擎' },
          { key: 'load_model', label: '加载 Whisper 模型' },
        ],
    3: isCloud
      ? [
          { key: 'transcribe', label: '云端语音识别' },
          { key: 'segments', label: '解析字级时间戳' },
        ]
      : [
          { key: 'transcribe', label: '音频转录' },
          { key: 'vad', label: '语音活动检测' },
          { key: 'segments', label: '分段处理' },
        ],
    4: isCloud
      ? [
          { key: 'init_matcher', label: '准备匹配器' },
          { key: 'llm_match', label: 'LLM 语义匹配' },
          { key: 'verify', label: '匹配结果验证' },
        ]
      : [
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
      { key: 'fine_cut', label: '按脚本精剪内容' },
      { key: 'semantic_trim', label: '语义 KEEP/REMOVE' },
      { key: 'buffer', label: '添加缓冲区间 (0.15s)' },
    ],
    7: [
      { key: 'optimize_clips', label: '优化剪辑点' },
    ],
    8: [
      { key: 'apply_buffer', label: '应用缓冲' },
      { key: 'gen_results', label: '生成匹配结果' },
      { key: 'preview', label: '生成预览数据' },
    ],
  };
}

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
  stageSubtasks: Record<number, SubTask[]>,
): Record<string, SubTaskStatus> {
  const subtasks = stageSubtasks[stageId];
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
    let cancelled = false;
    if (id) {
      getJob(id).then((job) => {
        if (!cancelled) setJob(job);
      }).catch(() => {});
    }
    return () => { cancelled = true; };
  }, [id, setJob]);

  useEffect(() => {
    if (status === 'completed' && id) {
      const timer = setTimeout(() => navigate(`/review/${id}`), 2500);
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

  // Detect cloud vs local from stage detail messages
  const isCloud = (stageDetail?.includes('云端') || stageDetail?.includes('Volcengine') || stageDetail?.includes('cloud')) ?? false;
  const stages = getProcessingStages(isCloud);
  const stageSubtasks = getStageSubtasks(isCloud);

  // All stages collapsed by default — user clicks to expand/collapse

  return (
    <>
      <Stepper currentStep={1} jobId={id} />
      <PageContainer>
        <div className="flex flex-col items-center gap-8 py-12 animate-fade-in-up">

          {/* ── Stage todo list ── */}
          <div className="w-full max-w-md">
            <ul className="flex flex-col gap-1">
              {stages.map((stage) => {
                const isDone = isComplete || currentStage > stage.id;
                const isActive = !isComplete && !isFailed && currentStage === stage.id;
                const isPending = !isDone && !isActive;
                const stageStatus: 'done' | 'active' | 'pending' = isDone ? 'done' : isActive ? 'active' : 'pending';

                const subtasks = stageSubtasks[stage.id] ?? [];
                const hasSubtasks = subtasks.length > 0;
                const isExpanded = expandedStages.has(stage.id);
                const subtaskStatuses = resolveSubTaskStatuses(stage.id, stageStatus, stageProgress?.sub_tasks, stageSubtasks);

                return (
                  <li key={stage.id} className="transition-all duration-500">
                    {/* Main stage row */}
                    <div
                      className={`
                        flex items-start gap-3 rounded-xl px-4 py-3 transition-all duration-300
                        ${isActive ? 'bg-accent' : ''}
                        ${hasSubtasks ? 'cursor-pointer select-none' : ''}
                      `}
                      onClick={hasSubtasks ? () => toggleStage(stage.id) : undefined}
                    >
                      {/* Status icon */}
                      <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center">
                        {isDone && (
                          <Check className="h-5 w-5 text-success animate-fade-in" />
                        )}
                        {isActive && (
                          <Loader2 className="h-4 w-4 text-foreground animate-spin" />
                        )}
                        {isPending && (
                          <Circle className="h-3 w-3 text-muted-foreground/50" />
                        )}
                      </div>

                      {/* Text */}
                      <div className="min-w-0 flex-1">
                        <span
                          className={`
                            text-sm font-medium transition-colors duration-300
                            ${isDone ? 'text-muted-foreground' : ''}
                            ${isActive ? 'text-foreground font-semibold' : ''}
                            ${isPending ? 'text-muted-foreground' : ''}
                          `}
                        >
                          {stage.name}
                        </span>
                        {isActive && stageDetail && !isExpanded && (
                          <p className="mt-0.5 text-xs text-muted-foreground animate-fade-in truncate">
                            {stageDetail}
                          </p>
                        )}
                      </div>

                      {/* Chevron */}
                      {hasSubtasks && (
                        <div className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center">
                          <ChevronRight
                            className={`h-3.5 w-3.5 text-muted-foreground/50 transition-transform duration-300 ${isExpanded ? 'rotate-90' : ''}`}
                          />
                        </div>
                      )}
                    </div>

                    {/* Expandable sub-tasks */}
                    <div
                      className="overflow-hidden transition-all duration-300"
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
                                className="text-xs font-mono select-none shrink-0 text-border"
                                style={{ width: '1rem' }}
                              >
                                {connector}
                              </span>

                              {/* Sub-task status icon */}
                              <div className="flex h-4 w-4 items-center justify-center shrink-0">
                                {stStatus === 'completed' && <Check className="h-3.5 w-3.5 text-success" />}
                                {stStatus === 'active' && <Loader2 className="h-3 w-3 text-foreground animate-spin" />}
                                {stStatus === 'pending' && <Circle className="h-2 w-2 text-muted-foreground/50" />}
                              </div>

                              {/* Sub-task label */}
                              <span
                                className={`
                                  text-xs transition-colors duration-300
                                  ${stStatus === 'completed' ? 'text-muted-foreground/70' : ''}
                                  ${stStatus === 'active' ? 'text-foreground' : ''}
                                  ${stStatus === 'pending' ? 'text-muted-foreground/50' : ''}
                                `}
                              >
                                {subtask.label}
                              </span>

                              {/* Show detail text next to active sub-task */}
                              {stStatus === 'active' && isActive && stageDetail && (
                                <span className="text-[11px] text-muted-foreground truncate ml-1 animate-fade-in">
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
            <Progress
              value={pct}
              className={`h-1.5 ${isFailed ? '[&>[data-slot=progress-indicator]]:bg-danger' : isComplete ? '[&>[data-slot=progress-indicator]]:bg-success' : ''}`}
            />

            {/* Percentage — show "准备中..." when 0 and not yet started */}
            <div className="mt-2 text-center">
              <span className="font-mono text-xs text-muted-foreground">
                {pct === 0 && !isComplete && !isFailed ? '正在启动处理流程...' : `${pct}%`}
              </span>
            </div>

            {/* Time info */}
            {!isComplete && !isFailed && (
              <div className="mt-1 flex justify-between">
                <span className="font-mono text-[11px] text-muted-foreground">
                  已耗时: {formatElapsed(elapsed)}
                </span>
                <span className="font-mono text-[11px] text-muted-foreground">
                  预计剩余: {formatRemaining(estimatedRemaining)}
                </span>
              </div>
            )}
          </div>

          {/* ── Error state ── */}
          {error && (
            <Card className="max-w-md animate-slide-down border-danger/20">
              <CardContent>
                <Alert variant="destructive" className="border-0 p-0">
                  <AlertTriangle className="size-4" />
                  <AlertTitle>处理出错</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => navigate('/')}
                  className="mt-4"
                >
                  重新上传
                </Button>
              </CardContent>
            </Card>
          )}

          {/* ── Completed state ── */}
          {isComplete && (
            <Card className="animate-slide-down border-success/20">
              <CardContent>
                <div className="flex items-center justify-center gap-2 text-sm text-success">
                  <CheckCircle2 className="h-5 w-5" />
                  处理完成！正在进入审核页面...
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </PageContainer>
    </>
  );
}
