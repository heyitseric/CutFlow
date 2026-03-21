import type { AlignedSegment } from '../../api/types';
import { getConfidenceLevel } from '../../utils/confidence';
import { formatShort } from '../../utils/timecode';
import { useState } from 'react';

interface TimelinePreviewProps {
  segments: AlignedSegment[];
  audioDuration: number;
}

const COLORS: Record<string, string> = {
  high: '#34d399',
  medium: '#fbbf24',
  low: '#f87171',
  reordered: '#a78bfa',
  rejected: '#3d3a4e',
};

export default function TimelinePreview({ segments, audioDuration }: TimelinePreviewProps) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  if (!segments.length || audioDuration <= 0) return null;

  const kept = segments.filter((s) => s.status !== 'rejected');

  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-display text-sm font-semibold text-text-secondary">时间线预览</h3>
        <span className="font-mono text-xs text-text-muted">
          总时长 {formatShort(audioDuration)}
        </span>
      </div>

      {/* Timeline track */}
      <div className="relative h-12 w-full overflow-hidden rounded-lg bg-elevated">
        {/* Grid lines for time reference */}
        {Array.from({ length: 10 }, (_, i) => (
          <div
            key={i}
            className="absolute top-0 h-full w-px bg-border/30"
            style={{ left: `${(i + 1) * 10}%` }}
          />
        ))}

        {/* Segments */}
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
            <div
              key={i}
              className={`absolute top-1 bottom-1 rounded-sm transition-all duration-200 ${
                isHovered ? 'z-10 brightness-125 scale-y-110' : ''
              } ${isRejected ? 'opacity-30' : ''}`}
              style={{
                left: `${left}%`,
                width: `${Math.max(width, 0.3)}%`,
                backgroundColor: color,
              }}
              onMouseEnter={() => setHoveredIdx(i)}
              onMouseLeave={() => setHoveredIdx(null)}
            />
          );
        })}

        {/* Hover tooltip */}
        {hoveredIdx !== null && segments[hoveredIdx] && (() => {
          const seg = segments[hoveredIdx];
          const leftPct = ((seg.startTime + seg.endTime) / 2 / audioDuration) * 100;
          return (
            <div
              className="pointer-events-none absolute -top-11 z-20 -translate-x-1/2 rounded-lg bg-panel px-2.5 py-1.5 font-mono text-[11px] text-text-primary whitespace-nowrap shadow-lg shadow-black/30 border border-border"
              style={{ left: `${Math.min(Math.max(leftPct, 8), 92)}%` }}
            >
              #{hoveredIdx + 1} {formatShort(seg.startTime)} - {formatShort(seg.endTime)}
              {seg.isReordered && <span className="ml-1.5 text-purple">复制</span>}
            </div>
          );
        })()}
      </div>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap items-center gap-5 text-xs text-text-muted">
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
          已移除
        </span>
        <span className="ml-auto text-text-muted">
          保留 {kept.length} / {segments.length} 段
        </span>
      </div>
    </div>
  );
}
