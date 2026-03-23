import type { AlignedSegment } from '../../api/types';
import { getConfidenceLevel } from '../../utils/confidence';
import { formatShort } from '../../utils/timecode';
import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface TimelinePreviewProps {
  segments: AlignedSegment[];
  audioDuration: number;
}

const COLORS: Record<string, string> = {
  high: '#22c55e',
  medium: '#eab308',
  low: '#ef4444',
  reordered: '#a855f7',
  rejected: '#d4d4d8',
};

export default function TimelinePreview({ segments, audioDuration }: TimelinePreviewProps) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  if (!segments.length || audioDuration <= 0) return null;

  const kept = segments.filter((s) => s.status !== 'rejected');

  return (
    <Card>
      <CardContent>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-display text-sm font-semibold text-foreground">时间线预览</h3>
          <span className="font-mono text-xs text-muted-foreground">
            总时长 {formatShort(audioDuration)}
          </span>
        </div>

        {/* Timeline track */}
        <div className="relative h-12 w-full overflow-hidden rounded-lg bg-muted">
          {/* Grid lines for time reference */}
          {Array.from({ length: 10 }, (_, i) => (
            <div
              key={i}
              className="absolute top-0 h-full w-px bg-border"
              style={{ left: `${(i + 1) * 10}%` }}
            />
          ))}

          {/* Segments */}
          <TooltipProvider delayDuration={0}>
            {segments.map((seg, i) => {
              const left = (seg.startTime / audioDuration) * 100;
              const width = ((seg.endTime - seg.startTime) / audioDuration) * 100;
              const isRejected = seg.status === 'rejected';
              const level = getConfidenceLevel(seg.confidence);
              const isHovered = hoveredIdx === i;
              const color = isRejected
                ? COLORS.rejected
                : seg.isReordered
                  ? COLORS.reordered
                  : COLORS[level];

              return (
                <Tooltip key={i}>
                  <TooltipTrigger asChild>
                    <div
                      className={`absolute top-1 bottom-1 rounded-sm transition-all duration-200 ${
                        isHovered ? 'z-10 brightness-110 scale-y-110' : ''
                      } ${isRejected ? 'opacity-40' : ''}`}
                      style={{
                        left: `${left}%`,
                        width: `${Math.max(width, 0.3)}%`,
                        backgroundColor: color,
                      }}
                      onMouseEnter={() => setHoveredIdx(i)}
                      onMouseLeave={() => setHoveredIdx(null)}
                    />
                  </TooltipTrigger>
                  <TooltipContent side="top" sideOffset={4}>
                    <span className="font-mono text-[11px]">
                      #{i + 1} {formatShort(seg.startTime)} - {formatShort(seg.endTime)}
                      {seg.isReordered && <span className="ml-1.5 text-purple-300">复制</span>}
                    </span>
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </TooltipProvider>
        </div>

        {/* Legend */}
        <div className="mt-4 flex flex-wrap items-center gap-5 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-5 rounded-sm" style={{ backgroundColor: COLORS.high }} />
            高置信 ({kept.filter(s => getConfidenceLevel(s.confidence) === 'high').length})
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-5 rounded-sm" style={{ backgroundColor: COLORS.medium }} />
            中置信
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-5 rounded-sm" style={{ backgroundColor: COLORS.low }} />
            低置信
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-5 rounded-sm" style={{ backgroundColor: COLORS.reordered }} />
            重排/复制
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-5 rounded-sm" style={{ backgroundColor: COLORS.rejected }} />
            已跳过
          </span>
          <span className="ml-auto text-muted-foreground">
            保留 {kept.length} / {segments.length} 段
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
