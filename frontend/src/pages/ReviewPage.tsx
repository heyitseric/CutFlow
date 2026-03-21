import { useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import PageContainer from '../components/layout/PageContainer';
import Stepper from '../components/layout/Stepper';
import SegmentRow from '../components/review/SegmentRow';
import TimelinePreview from '../components/review/TimelinePreview';
import { useJobStore, useActiveJob } from '../stores/jobStore';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import { getJob } from '../api/client';

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const setActiveJob = useJobStore((s) => s.setActiveJob);
  const setJob = useJobStore((s) => s.setJob);
  const approveSegment = useJobStore((s) => s.approveSegment);
  const rejectSegment = useJobStore((s) => s.rejectSegment);

  const { alignment, audioDuration, editedSegments } = useActiveJob();

  // Ensure active job is set
  useEffect(() => {
    if (id) {
      setActiveJob(id);
    }
  }, [id, setActiveJob]);

  // Always fetch job data when entering review — ensures alignment data is fresh
  useEffect(() => {
    if (id) {
      getJob(id).then(setJob).catch((err) => {
        console.error('[ReviewPage] Failed to fetch job:', err);
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const audioUrl = id ? `/api/jobs/${id}/audio` : null;
  const { playing, currentTime, toggle } = useAudioPlayer(audioUrl);

  const mergedSegments = useMemo(() => {
    if (!alignment) return [];
    return alignment.map((seg, i) => {
      const edits = editedSegments.get(i);
      return edits ? { ...seg, ...edits } : seg;
    });
  }, [alignment, editedSegments]);

  const stats = useMemo(() => {
    const total = mergedSegments.length;
    const kept = mergedSegments.filter(
      (s) => s.status !== 'rejected',
    ).length;
    const removed = total - kept;
    return { total, kept, removed };
  }, [mergedSegments]);

  function isSegmentKept(seg: (typeof mergedSegments)[number]): boolean {
    return seg.status !== 'rejected';
  }

  function handleToggleKeep(index: number) {
    const seg = mergedSegments[index];
    if (seg.status === 'rejected') {
      approveSegment(index);
    } else {
      rejectSegment(index);
    }
  }

  function handleKeepAll() {
    mergedSegments.forEach((seg, i) => {
      if (seg.status === 'rejected' || seg.status === 'needs_review') {
        approveSegment(i);
      }
    });
  }

  if (!alignment) {
    return (
      <>
        <Stepper currentStep={2} jobId={id} />
        <PageContainer wide>
          <div className="flex items-center justify-center py-20 text-text-muted animate-gentle-pulse">
            <svg className="mr-3 h-5 w-5 animate-spin text-amber" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            加载对齐结果...
          </div>
        </PageContainer>
      </>
    );
  }

  return (
    <>
      <Stepper currentStep={2} jobId={id} />
      <PageContainer wide>
        {/* Header */}
        <div className="mb-4 animate-fade-in-up">
          <div className="flex items-center justify-between">
            <h1 className="font-display text-2xl font-bold tracking-tight text-text-primary">
              检查匹配结果
            </h1>
            <div className="flex items-center gap-2">
              <button
                onClick={handleKeepAll}
                className="rounded-lg bg-success/15 px-3.5 py-1.5 text-xs font-medium text-success hover:bg-success/20 transition-colors"
              >
                全部保留
              </button>
              <button
                onClick={() => navigate(`/export/${id}`)}
                className="rounded-lg bg-amber px-4 py-1.5 text-xs font-semibold text-deep hover:bg-amber/90 transition-colors"
              >
                前往导出 →
              </button>
            </div>
          </div>

          {/* Explanation text */}
          <p className="mt-2 text-sm text-text-muted leading-relaxed">
            以下是脚本和音频的匹配结果。绿色表示匹配准确，黄色需注意，红色建议检查。不需要的段落取消「保留」即可。
          </p>

          {/* Summary stats */}
          <p className="mt-1.5 text-xs text-text-faint">
            共 <span className="font-mono text-text-secondary">{stats.total}</span> 段
            {' · '}
            已保留 <span className="font-mono text-success">{stats.kept}</span>
            {' · '}
            已移除 <span className="font-mono text-danger">{stats.removed}</span>
          </p>
        </div>

        {/* Segment rows */}
        <div className="flex flex-col gap-2">
          {mergedSegments.map((seg, i) => (
            <SegmentRow
              key={i}
              segment={seg}
              index={i}
              playing={playing && currentTime >= seg.startTime && currentTime <= seg.endTime}
              currentTime={currentTime}
              onTogglePlay={(start, end) => toggle(start, end)}
              onToggleKeep={handleToggleKeep}
              isKept={isSegmentKept(seg)}
            />
          ))}
        </div>

        {/* Timeline */}
        <div className="mt-8">
          <TimelinePreview
            segments={mergedSegments}
            audioDuration={audioDuration ?? 0}
          />
        </div>
      </PageContainer>
    </>
  );
}
