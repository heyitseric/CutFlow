import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import PageContainer from '../components/layout/PageContainer';
import Stepper from '../components/layout/Stepper';
import { useJob } from '../hooks/useJob';
import { useJobStore } from '../stores/jobStore';
import { getJob } from '../api/client';
import { formatDuration } from '../utils/timecode';

const STAGE_LABELS: Record<string, string> = {
  uploading: '上传中',
  transcribing: '转录中',
  aligning: '对齐中',
  matching: '匹配中',
  processing: '处理中',
  completed: '处理完成',
  failed: '处理失败',
};

const STAGE_DESCRIPTIONS: Record<string, string> = {
  uploading: '正在上传文件到服务器...',
  transcribing: '正在识别音频内容，提取词级时间戳...',
  aligning: '正在将脚本与转录内容进行对齐...',
  matching: '正在进行模糊匹配，计算置信度...',
  processing: '正在处理数据...',
  completed: '即将跳转至审核页面',
  failed: '处理过程中出现错误',
};

export default function ProcessingPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { status, progress, error, audioDuration } = useJobStore();
  const setJob = useJobStore((s) => s.setJob);

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

  const stageLabel = STAGE_LABELS[status] ?? status;
  const stageDesc = STAGE_DESCRIPTIONS[status] ?? '';
  const pct = Math.round(progress * 100);
  const estimatedRemaining =
    audioDuration && progress > 0 && progress < 1
      ? ((audioDuration * 0.3) / progress) * (1 - progress)
      : null;

  const isFailed = status === 'failed';
  const isComplete = status === 'completed';
  const circumference = 2 * Math.PI * 54;

  return (
    <>
      <Stepper currentStep={1} jobId={id} />
      <PageContainer>
        <div className="flex flex-col items-center gap-10 py-16 animate-fade-in-up">

          {/* Circular progress */}
          <div className="relative h-44 w-44">
            {/* Ambient glow */}
            <div
              className="absolute inset-0 rounded-full blur-2xl transition-opacity duration-1000"
              style={{
                background: isFailed
                  ? 'radial-gradient(circle, rgba(248,113,113,0.15) 0%, transparent 70%)'
                  : isComplete
                    ? 'radial-gradient(circle, rgba(52,211,153,0.15) 0%, transparent 70%)'
                    : 'radial-gradient(circle, rgba(232,168,56,0.12) 0%, transparent 70%)',
              }}
            />

            <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
              {/* Track */}
              <circle
                cx="60" cy="60" r="54"
                fill="none"
                stroke="var(--color-elevated)"
                strokeWidth="5"
              />
              {/* Progress arc */}
              <circle
                cx="60" cy="60" r="54"
                fill="none"
                stroke={isFailed ? 'var(--color-danger)' : isComplete ? 'var(--color-success)' : 'var(--color-amber)'}
                strokeWidth="5"
                strokeLinecap="round"
                strokeDasharray={circumference}
                strokeDashoffset={circumference * (1 - progress)}
                className="transition-[stroke-dashoffset] duration-700 ease-out"
              />
            </svg>

            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-display text-4xl font-bold tracking-tight text-text-primary">{pct}</span>
              <span className="font-mono text-xs text-text-muted">%</span>
            </div>
          </div>

          {/* Stage label */}
          <div className="text-center">
            <p className="font-display text-xl font-semibold text-text-primary">{stageLabel}</p>
            <p className="mt-2 text-sm text-text-muted">{stageDesc}</p>
            {estimatedRemaining !== null && (
              <p className="mt-2 font-mono text-xs text-text-muted">
                预计剩余 {formatDuration(estimatedRemaining)}
              </p>
            )}
          </div>

          {/* Progress bar */}
          <div className="w-full max-w-md">
            <div className="h-1.5 overflow-hidden rounded-full bg-elevated">
              <div
                className={`h-full rounded-full transition-all duration-700 ease-out ${
                  isFailed ? 'bg-danger' : isComplete ? 'bg-success' : 'bg-amber progress-stripe'
                }`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>

          {/* Pulsing dots */}
          {!isComplete && !isFailed && (
            <div className="flex gap-2">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="h-1.5 w-1.5 rounded-full bg-amber animate-gentle-pulse"
                  style={{ animationDelay: `${i * 200}ms` }}
                />
              ))}
            </div>
          )}

          {/* Error */}
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

          {/* Completed */}
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
