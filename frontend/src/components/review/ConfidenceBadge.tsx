import { getConfidenceColor, getConfidenceLevel } from '../../utils/confidence';

interface ConfidenceBadgeProps {
  score: number;
}

export default function ConfidenceBadge({ score }: ConfidenceBadgeProps) {
  const level = getConfidenceLevel(score);
  const color = getConfidenceColor(level);
  const pct = Math.round(score);

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 font-mono text-[11px] font-medium ${color}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${
        level === 'high' ? 'bg-success' : level === 'medium' ? 'bg-warning' : 'bg-danger'
      }`} />
      {pct}%
    </span>
  );
}
