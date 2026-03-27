import type { AlignedSegment } from '../../api/types';
import { getConfidenceLevel } from '../../utils/confidence';
import { formatShort } from '../../utils/timecode';
import AudioPlayer from './AudioPlayer';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';

interface SegmentRowProps {
  segment: AlignedSegment;
  index: number;
  playing: boolean;
  currentTime: number;
  onTogglePlay: (start: number, end: number) => void;
  onToggleKeep: (index: number) => void;
  isKept: boolean;
  saveStatus?: 'saving' | 'saved' | 'error' | null;
}

export default function SegmentRow({
  segment,
  index,
  playing,
  currentTime,
  onTogglePlay,
  onToggleKeep,
  isKept,
  saveStatus,
}: SegmentRowProps) {
  const level = getConfidenceLevel(segment.confidence);
  const pct = Math.round(segment.confidence);

  const confidenceBadgeClass =
    level === 'high'
      ? 'bg-success/10 text-success border-success/20'
      : level === 'medium'
        ? 'bg-warning/10 text-warning border-warning/20'
        : 'bg-danger/10 text-danger border-danger/20';

  const confidenceTitle =
    pct >= 85
      ? '匹配准确'
      : pct >= 60
        ? '基本匹配，建议检查'
        : '匹配较差，建议仔细核对';

  return (
    <Card
      size="sm"
      className={`transition-all duration-200 ${
        !isKept
          ? 'opacity-50 ring-border'
          : playing
            ? 'ring-2 ring-primary/30 bg-primary/5'
            : ''
      }`}
    >
      {/* Top bar: index, play button, time range, confidence, keep checkbox */}
      <div className="flex items-center gap-3 px-4">
        {/* Segment number */}
        <span className="font-mono text-xs font-semibold text-muted-foreground w-8 shrink-0">
          #{index + 1}
        </span>

        {/* Hook badge */}
        {segment.isCopy && (
          <Badge
            variant="outline"
            className="bg-purple/10 text-purple border-purple/20 text-[10px] px-1.5 py-0 h-4"
            title={
              segment.copySourceIndex != null
                ? `开头钩子 · 复制自第 ${segment.copySourceIndex + 1} 句（正常现象）`
                : '开头钩子（正常现象）'
            }
          >
            钩子
          </Badge>
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
        <span className="font-mono text-[11px] text-muted-foreground/50 shrink-0">
          {formatShort(segment.startTime)} → {formatShort(segment.endTime)}
        </span>

        {/* Right side: confidence + keep checkbox */}
        <div className="ml-auto flex items-center gap-4">
          <Badge
            variant="outline"
            className={`font-mono text-[11px] font-semibold ${confidenceBadgeClass}`}
            title={confidenceTitle}
          >
            {pct}%
          </Badge>

          {/* Save status indicator */}
          {saveStatus === 'saving' && (
            <span className="text-[10px] text-muted-foreground" title="保存中...">...</span>
          )}
          {saveStatus === 'error' && (
            <span className="text-[10px] text-danger" title="保存失败，请检查网络">!</span>
          )}

          {/* Checkbox toggle */}
          <label
            className="flex items-center gap-1.5 cursor-pointer select-none"
            onClick={(e) => e.stopPropagation()}
          >
            <Checkbox
              checked={isKept}
              onCheckedChange={() => onToggleKeep(index)}
            />
            <span className="text-xs text-muted-foreground">
              保留
            </span>
          </label>
        </div>
      </div>

      {/* Script and transcript text - stacked layout */}
      <CardContent className="space-y-2 pt-0">
        {/* Script text - primary */}
        <div>
          <span className="text-[10px] font-medium text-muted-foreground/50">
            脚本
          </span>
          <p className="mt-0.5 text-sm leading-relaxed text-foreground">
            {segment.scriptText}
          </p>
        </div>

        {/* Transcript text - secondary, smaller, lighter */}
        <div>
          <span className="text-[10px] text-muted-foreground/50">
            转录 · <span className="font-normal">AI 识别的音频内容（用于验证匹配准确性）</span>
          </span>
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground/50">
            {segment.transcriptText}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
