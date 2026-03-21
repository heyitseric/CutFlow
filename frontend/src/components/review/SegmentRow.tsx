import type { AlignedSegment } from '../../api/types';
import { getConfidenceLevel } from '../../utils/confidence';
import { formatShort } from '../../utils/timecode';
import AudioPlayer from './AudioPlayer';

interface SegmentRowProps {
  segment: AlignedSegment;
  index: number;
  playing: boolean;
  currentTime: number;
  onTogglePlay: (start: number, end: number) => void;
  onToggleKeep: (index: number) => void;
  isKept: boolean;
}

export default function SegmentRow({
  segment,
  index,
  playing,
  currentTime,
  onTogglePlay,
  onToggleKeep,
  isKept,
}: SegmentRowProps) {
  const level = getConfidenceLevel(segment.confidence);
  const pct = Math.round(segment.confidence);

  const confidenceColorClass =
    level === 'high'
      ? 'text-success'
      : level === 'medium'
        ? 'text-warning'
        : 'text-danger';

  const borderClass = !isKept
    ? 'border-border-subtle bg-base opacity-50'
    : playing
      ? 'border-amber/30 bg-amber-glow'
      : 'border-border bg-surface hover:border-border hover:bg-elevated/50';

  return (
    <div
      className={`rounded-xl border transition-all duration-200 ${borderClass} animate-fade-in`}
    >
      {/* Top bar: index, play button, time range, confidence, keep checkbox */}
      <div className="flex items-center gap-3 px-4 py-3">
        {/* Segment number */}
        <span className="font-mono text-xs font-semibold text-text-muted w-8 shrink-0">
          #{index + 1}
        </span>

        {/* Hook badge */}
        {segment.isCopy && (
          <span
            className="inline-flex items-center gap-0.5 rounded-md bg-purple-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-purple-400 shrink-0"
            title={
              segment.copySourceIndex != null
                ? `Hook: 复制自第 ${segment.copySourceIndex + 1} 句`
                : 'Hook 复制'
            }
          >
            Hook
          </span>
        )}

        {/* Play button - prominent */}
        <AudioPlayer
          playing={playing}
          currentTime={currentTime}
          startTime={segment.startTime}
          endTime={segment.endTime}
          onToggle={() => onTogglePlay(segment.startTime, segment.endTime)}
        />

        {/* Time range */}
        <span className="font-mono text-[11px] text-text-faint shrink-0">
          {formatShort(segment.startTime)} → {formatShort(segment.endTime)}
        </span>

        {/* Right side: confidence + keep checkbox */}
        <div className="ml-auto flex items-center gap-4">
          <span className={`font-mono text-xs font-semibold ${confidenceColorClass}`}>
            {pct}%
          </span>

          {/* Simple checkbox toggle */}
          <label
            className="flex items-center gap-1.5 cursor-pointer select-none"
            onClick={(e) => e.stopPropagation()}
          >
            <input
              type="checkbox"
              checked={isKept}
              onChange={() => onToggleKeep(index)}
              className="h-4 w-4 rounded border-border bg-base text-amber accent-amber cursor-pointer"
            />
            <span className="text-xs text-text-secondary">
              保留
            </span>
          </label>
        </div>
      </div>

      {/* Script and transcript text - stacked layout */}
      <div className="px-4 pb-3 space-y-2">
        {/* Script text - primary */}
        <div>
          <span className="text-[10px] font-medium text-text-faint">
            脚本
          </span>
          <p className="mt-0.5 text-sm leading-relaxed text-text-primary">
            {segment.scriptText}
          </p>
        </div>

        {/* Transcript text - secondary, smaller, lighter */}
        <div>
          <span className="text-[10px] text-text-faint">
            转录 · <span className="font-normal">AI 识别的音频内容（用于验证匹配准确性）</span>
          </span>
          <p className="mt-0.5 text-xs leading-relaxed text-text-faint">
            {segment.transcriptText}
          </p>
        </div>
      </div>
    </div>
  );
}
