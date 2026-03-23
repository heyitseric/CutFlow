import { getConfidenceColor, getConfidenceLevel } from '../../utils/confidence';
import { Badge } from '@/components/ui/badge';

interface ConfidenceBadgeProps {
  score: number;
}

export default function ConfidenceBadge({ score }: ConfidenceBadgeProps) {
  const level = getConfidenceLevel(score);
  const color = getConfidenceColor(level);
  const pct = Math.round(score);

  return (
    <Badge variant="outline" className={`font-mono text-[11px] font-medium ${color}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${
        level === 'high' ? 'bg-success' : level === 'medium' ? 'bg-warning' : 'bg-danger'
      }`} />
      {pct}%
    </Badge>
  );
}
