interface AudioPlayerProps {
  playing: boolean;
  currentTime: number;
  startTime: number;
  endTime: number;
  onToggle: () => void;
}

export default function AudioPlayer({
  playing,
  currentTime,
  startTime,
  endTime,
  onToggle,
}: AudioPlayerProps) {
  const duration = endTime - startTime;
  const elapsed = Math.max(0, Math.min(currentTime - startTime, duration));
  const pct = duration > 0 ? (elapsed / duration) * 100 : 0;

  return (
    <div className="flex items-center gap-2.5">
      <button
        onClick={onToggle}
        className={`flex h-7 w-7 items-center justify-center rounded-lg transition-all duration-200 transition-snappy ${
          playing
            ? 'bg-amber/15 text-amber shadow-sm shadow-amber/10'
            : 'bg-elevated text-text-muted hover:bg-amber/10 hover:text-amber'
        }`}
      >
        {playing ? (
          <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="4" width="4" height="16" rx="1" />
            <rect x="14" y="4" width="4" height="16" rx="1" />
          </svg>
        ) : (
          <svg className="h-3 w-3 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z" />
          </svg>
        )}
      </button>
      <div className="h-1 w-16 overflow-hidden rounded-full bg-elevated">
        <div
          className="h-full rounded-full bg-amber transition-all duration-100 transition-smooth"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
