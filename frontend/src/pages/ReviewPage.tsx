import { useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import PageContainer from '../components/layout/PageContainer';
import Stepper from '../components/layout/Stepper';
import SegmentRow from '../components/review/SegmentRow';
import TimelinePreview from '../components/review/TimelinePreview';
import { useJobStore, useActiveJob } from '../stores/jobStore';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import { getJob } from '../api/client';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const setActiveJob = useJobStore((s) => s.setActiveJob);
  const setJob = useJobStore((s) => s.setJob);
  const approveSegment = useJobStore((s) => s.approveSegment);
  const rejectSegment = useJobStore((s) => s.rejectSegment);
  const getSaveStatus = useJobStore((s) => s.getSaveStatus);

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
          <div className="flex items-center justify-center py-20 text-muted-foreground">
            <Loader2 className="mr-3 h-5 w-5 animate-spin text-foreground" />
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
            <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
              检查匹配结果
            </h1>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleKeepAll}
                className="text-success border-success/30 hover:bg-success/10"
              >
                全部保留
              </Button>
              <Button
                size="sm"
                onClick={() => navigate(`/export/${id}`)}
              >
                前往导出 →
              </Button>
            </div>
          </div>

          {/* Explanation text */}
          <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
            以下是脚本和音频的匹配结果。绿色表示匹配准确，黄色需注意，红色建议检查。不需要的段落取消「保留」即可。
          </p>

          {/* Summary stats */}
          <div className="mt-2 flex items-center gap-2">
            <Badge variant="secondary" className="font-mono">
              共 {stats.total} 段
            </Badge>
            <Badge variant="outline" className="font-mono text-success border-success/30">
              已保留 {stats.kept}
            </Badge>
            <Badge variant="outline" className="font-mono text-danger border-danger/30">
              已移除 {stats.removed}
            </Badge>
          </div>
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
              saveStatus={getSaveStatus(i)}
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
