import { useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import PageContainer from '../components/layout/PageContainer';
import Stepper from '../components/layout/Stepper';
import SegmentRow from '../components/review/SegmentRow';
import TimelinePreview from '../components/review/TimelinePreview';
import { useJobStore, useActiveJob } from '../stores/jobStore';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import { getJob } from '../api/client';
import type { PauseSegment } from '../api/types';

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const setActiveJob = useJobStore((s) => s.setActiveJob);
  const setJob = useJobStore((s) => s.setJob);
  const approveSegment = useJobStore((s) => s.approveSegment);
  const rejectSegment = useJobStore((s) => s.rejectSegment);
  const updateSegment = useJobStore((s) => s.updateSegment);
  const updatePause = useJobStore((s) => s.updatePause);
  const batchUpdatePauses = useJobStore((s) => s.batchUpdatePauses);

  const { alignment, audioDuration, editedSegments, editedPauses } = useActiveJob();

  // Ensure active job is set
  useEffect(() => {
    if (id) {
      setActiveJob(id);
    }
  }, [id, setActiveJob]);

  useEffect(() => {
    if (id && !alignment) {
      getJob(id).then(setJob).catch(() => {});
    }
  }, [id, alignment, setJob]);

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
    const approved = mergedSegments.filter(
      (s) => s.status === 'approved' || s.status === 'auto_approved',
    ).length;
    const needsReview = mergedSegments.filter((s) => s.status === 'needs_review').length;
    const rejected = mergedSegments.filter((s) => s.status === 'rejected').length;
    return { total, approved, needsReview, rejected };
  }, [mergedSegments]);

  function handleUpdateTimestamps(index: number, start: number, end: number) {
    updateSegment(index, { startTime: start, endTime: end });
  }

  function handleUpdatePause(segIdx: number, pauseIdx: number, action: PauseSegment['action']) {
    updatePause(segIdx, pauseIdx, { action });
  }

  function handleApproveAll() {
    mergedSegments.forEach((seg, i) => {
      if (seg.status === 'needs_review' || seg.status === 'auto_approved') {
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
        {/* Header bar */}
        <div className="mb-6 flex items-start justify-between animate-fade-in-up">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight text-text-primary">审核对齐结果</h1>
            <div className="mt-2 flex items-center gap-4 text-sm">
              <span className="text-text-muted">共 <span className="font-mono text-text-secondary">{stats.total}</span> 段</span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-success" />
                <span className="text-text-muted">已通过 <span className="font-mono text-success">{stats.approved}</span></span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-warning" />
                <span className="text-text-muted">待审核 <span className="font-mono text-warning">{stats.needsReview}</span></span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-danger" />
                <span className="text-text-muted">已拒绝 <span className="font-mono text-danger">{stats.rejected}</span></span>
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => batchUpdatePauses('long', 'shorten')}
              className="rounded-lg border border-danger/20 bg-danger-surface px-3 py-1.5 text-xs font-medium text-danger hover:bg-danger/15 transition-colors"
            >
              缩短长停顿
            </button>
            <button
              onClick={() => batchUpdatePauses('thinking', 'keep')}
              className="rounded-lg border border-warning/20 bg-warning-surface px-3 py-1.5 text-xs font-medium text-warning hover:bg-warning/15 transition-colors"
            >
              保留思考停顿
            </button>
            <button
              onClick={handleApproveAll}
              className="rounded-lg bg-success/15 px-3.5 py-1.5 text-xs font-medium text-success hover:bg-success/20 transition-colors"
            >
              全部批准
            </button>
            <button
              onClick={() => navigate(`/export/${id}`)}
              className="rounded-lg bg-amber px-4 py-1.5 text-xs font-semibold text-deep hover:bg-amber/90 transition-colors"
            >
              前往导出 →
            </button>
          </div>
        </div>

        {/* Column headers */}
        <div className="mb-3 flex items-center rounded-xl bg-elevated px-1 py-2.5 text-xs font-medium text-text-muted animate-fade-in-up delay-1">
          <div className="w-12 text-center font-mono">#</div>
          <div className="flex-1 px-4 font-display">脚本文字</div>
          <div className="flex-1 px-4 font-display">转录文字</div>
          <div className="w-56 px-3 font-display">操作</div>
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
              onApprove={approveSegment}
              onReject={rejectSegment}
              onUpdateTimestamps={handleUpdateTimestamps}
              onUpdatePause={handleUpdatePause}
              editedPauses={editedPauses}
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
