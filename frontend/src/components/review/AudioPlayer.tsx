import { Play, Pause } from 'lucide-react';
import { Button } from '@/components/ui/button';

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
      <Button
        variant={playing ? 'default' : 'outline'}
        size="icon-xs"
        onClick={onToggle}
      >
        {playing ? (
          <Pause className="h-3 w-3" />
        ) : (
          <Play className="h-3 w-3 ml-0.5" />
        )}
      </Button>
      <div className="h-1 w-16 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-100"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
