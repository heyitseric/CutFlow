import { useState, useCallback } from 'react';
import type { AlignedSegment, PauseSegment } from '../../api/types';
import ConfidenceBadge from './ConfidenceBadge';
import AudioPlayer from './AudioPlayer';
import TextCorrectionPopover from './TextCorrectionPopover';
import { getStatusLabel, getStatusColor, getPauseColor, getPauseLabel } from '../../utils/confidence';
import { formatShort } from '../../utils/timecode';

interface SegmentRowProps {
  segment: AlignedSegment;
  index: number;
  playing: boolean;
  currentTime: number;
  onTogglePlay: (start: number, end: number) => void;
  onApprove: (index: number) => void;
  onReject: (index: number) => void;
  onUpdateTimestamps: (index: number, start: number, end: number) => void;
  onUpdatePause: (segIdx: number, pauseIdx: number, action: PauseSegment['action']) => void;
  editedPauses: Map<string, Partial<PauseSegment>>;
}

export default function SegmentRow({
  segment,
  index,
  playing,
  currentTime,
  onTogglePlay,
  onApprove,
  onReject,
  onUpdateTimestamps,
  onUpdatePause,
  editedPauses,
}: SegmentRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [editingTimestamps, setEditingTimestamps] = useState(false);
  const [startInput, setStartInput] = useState(String(segment.startTime));
  const [endInput, setEndInput] = useState(String(segment.endTime));
  const [popover, setPopover] = useState<{ text: string; x: number; y: number } | null>(null);

  const handleTextSelect = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.toString().trim()) return;
    const text = sel.toString().trim();
    const range = sel.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    setPopover({ text, x: rect.left, y: rect.bottom });
  }, []);

  function diffWords(script: string, transcript: string) {
    const sWords = script.split(/\s+/).filter(Boolean);
    const tWords = new Set(transcript.split(/\s+/).filter(Boolean));
    return sWords.map((w) => ({ word: w, missing: !tWords.has(w) }));
  }

  function diffTranscriptWords(script: string, transcript: string) {
    const sWords = new Set(script.split(/\s+/).filter(Boolean));
    const tWords = transcript.split(/\s+/).filter(Boolean);
    return tWords.map((w) => ({ word: w, extra: !sWords.has(w) }));
  }

  const scriptDiff = diffWords(segment.scriptText, segment.transcriptText);
  const transcriptDiff = diffTranscriptWords(segment.scriptText, segment.transcriptText);
  const isRejected = segment.status === 'rejected';
  const needsReview = segment.status === 'needs_review';

  return (
    <div className="group relative animate-fade-in">
      <div
        className={`rounded-xl border transition-all duration-300 ${
          isRejected
            ? 'border-border-subtle bg-base opacity-50'
            : needsReview
              ? 'border-warning/20 bg-warning-surface'
              : playing
                ? 'border-amber/30 bg-amber-glow'
                : 'border-border bg-surface hover:border-border hover:bg-elevated/50'
        }`}
      >
        {/* Main row */}
        <div className="flex items-stretch">
          {/* Index */}
          <div className="flex w-12 flex-shrink-0 items-center justify-center border-r border-border-subtle">
            <span className="font-mono text-xs text-text-muted">{index + 1}</span>
          </div>

          {/* Script text (left column) */}
          <div className="flex-1 border-r border-border-subtle p-4">
            <div className="text-sm leading-relaxed text-text-primary">
              {scriptDiff.map((w, i) => (
                <span
                  key={i}
                  className={w.missing ? 'rounded bg-danger/15 text-danger px-0.5 mx-0.5' : ''}
                >
                  {w.word}{' '}
                </span>
              ))}
            </div>
          </div>

          {/* Transcript text (right column) */}
          <div className="flex-1 p-4" onMouseUp={handleTextSelect}>
            <div className="text-sm leading-relaxed text-text-secondary select-text cursor-text">
              {transcriptDiff.map((w, i) => (
                <span
                  key={i}
                  className={w.extra ? 'rounded bg-teal/15 text-teal px-0.5 mx-0.5' : ''}
                >
                  {w.word}{' '}
                </span>
              ))}
            </div>
            <div className="mt-2 font-mono text-[10px] text-text-faint">
              {formatShort(segment.startTime)} — {formatShort(segment.endTime)}
            </div>
          </div>

          {/* Actions column */}
          <div className="flex w-56 flex-shrink-0 flex-col items-start justify-center gap-2 border-l border-border-subtle p-3">
            {/* Badges */}
            <div className="flex flex-wrap items-center gap-1.5">
              <ConfidenceBadge score={segment.confidence} />
              <span className={`rounded-md px-2 py-0.5 text-[10px] font-medium ${getStatusColor(segment.status)}`}>
                {getStatusLabel(segment.status)}
              </span>
              {segment.isReordered && (
                <span className="rounded-md bg-purple-surface px-2 py-0.5 text-[10px] font-medium text-purple">
                  ↗ 复制
                </span>
              )}
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-1">
              <button
                onClick={() => onApprove(index)}
                className="rounded-lg px-2 py-1 text-[11px] font-medium text-success hover:bg-success/10 transition-colors"
              >
                ✓ 批准
              </button>
              <button
                onClick={() => onReject(index)}
                className="rounded-lg px-2 py-1 text-[11px] font-medium text-danger hover:bg-danger/10 transition-colors"
              >
                ✗ 拒绝
              </button>
              <button
                onClick={() => {
                  setEditingTimestamps(!editingTimestamps);
                  setExpanded(true);
                }}
                className="rounded-lg px-2 py-1 text-[11px] font-medium text-teal hover:bg-teal/10 transition-colors"
              >
                ✎ 时间
              </button>
            </div>

            {/* Player */}
            <AudioPlayer
              playing={playing}
              currentTime={currentTime}
              startTime={segment.startTime}
              endTime={segment.endTime}
              onToggle={() => onTogglePlay(segment.startTime, segment.endTime)}
            />
          </div>
        </div>

        {/* Expandable detail */}
        {expanded && (
          <div className="animate-slide-down border-t border-border-subtle px-5 py-3">
            {editingTimestamps && (
              <div className="mb-3 flex items-center gap-3">
                <label className="text-xs text-text-muted">开始:</label>
                <input
                  type="number"
                  step="0.01"
                  value={startInput}
                  onChange={(e) => setStartInput(e.target.value)}
                  className="w-24 rounded-lg border border-border bg-elevated px-2.5 py-1.5 font-mono text-xs text-text-primary outline-none focus:border-amber/50"
                />
                <label className="text-xs text-text-muted">结束:</label>
                <input
                  type="number"
                  step="0.01"
                  value={endInput}
                  onChange={(e) => setEndInput(e.target.value)}
                  className="w-24 rounded-lg border border-border bg-elevated px-2.5 py-1.5 font-mono text-xs text-text-primary outline-none focus:border-amber/50"
                />
                <button
                  onClick={() => {
                    onUpdateTimestamps(index, parseFloat(startInput), parseFloat(endInput));
                    setEditingTimestamps(false);
                  }}
                  className="rounded-lg bg-amber px-3.5 py-1.5 text-xs font-medium text-deep hover:bg-amber/90 transition-colors"
                >
                  保存
                </button>
                <button
                  onClick={() => setEditingTimestamps(false)}
                  className="rounded-lg px-3 py-1.5 text-xs text-text-secondary hover:bg-elevated transition-colors"
                >
                  取消
                </button>
              </div>
            )}

            <div className="font-mono text-xs text-text-muted">
              原始时间: {formatShort(segment.rawStartTime)} — {formatShort(segment.rawEndTime)}
              {segment.originalPosition !== null && (
                <span className="ml-3 text-purple">原始位置: #{segment.originalPosition + 1}</span>
              )}
            </div>
          </div>
        )}

        {/* Toggle expand */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex w-full items-center justify-center border-t border-border-subtle py-1.5 text-[10px] text-text-faint hover:bg-elevated/50 hover:text-text-muted transition-colors"
        >
          {expanded ? '收起 ▲' : '展开详情 ▼'}
        </button>
      </div>

      {/* Pauses after this segment */}
      {segment.pauses.length > 0 && (
        <div className="flex items-center gap-3 py-1.5 px-14">
          {segment.pauses.map((pause, pi) => {
            const key = `${index}-${pi}`;
            const edited = editedPauses.get(key);
            const effectiveAction = edited?.action ?? pause.action;

            return (
              <div key={pi} className="flex items-center gap-1.5">
                <span className={`h-2 w-2 rounded-full ${getPauseColor(pause.pauseType)}`} />
                <span className="font-mono text-[10px] text-text-muted">
                  {getPauseLabel(pause.pauseType)} {pause.duration.toFixed(1)}s
                </span>
                <select
                  value={effectiveAction}
                  onChange={(e) => onUpdatePause(index, pi, e.target.value as PauseSegment['action'])}
                  className="rounded-md border border-border bg-elevated px-1.5 py-0.5 text-[10px] text-text-muted outline-none focus:border-amber/40"
                >
                  <option value="keep">保留</option>
                  <option value="shorten">缩短</option>
                  <option value="remove">移除</option>
                  <option value="review">待审</option>
                </select>
              </div>
            );
          })}
        </div>
      )}

      {/* Text correction popover */}
      {popover && (
        <TextCorrectionPopover
          selectedText={popover.text}
          position={{ x: popover.x, y: popover.y }}
          onClose={() => setPopover(null)}
          onSaved={() => setPopover(null)}
        />
      )}
    </div>
  );
}
