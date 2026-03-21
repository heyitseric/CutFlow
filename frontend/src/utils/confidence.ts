export const CONFIDENCE_HIGH = 85;
export const CONFIDENCE_MEDIUM = 65;

export type ConfidenceLevel = 'high' | 'medium' | 'low';

export function getConfidenceLevel(score: number): ConfidenceLevel {
  if (score >= CONFIDENCE_HIGH) return 'high';
  if (score >= CONFIDENCE_MEDIUM) return 'medium';
  return 'low';
}

export function getConfidenceColor(level: ConfidenceLevel): string {
  switch (level) {
    case 'high':
      return 'bg-success/10 text-success border-success/20';
    case 'medium':
      return 'bg-warning/10 text-warning border-warning/20';
    case 'low':
      return 'bg-danger/10 text-danger border-danger/20';
  }
}

export function getConfidenceDot(level: ConfidenceLevel): string {
  switch (level) {
    case 'high':
      return 'bg-success';
    case 'medium':
      return 'bg-warning';
    case 'low':
      return 'bg-danger';
  }
}

export type SegmentStatus = 'auto_approved' | 'needs_review' | 'approved' | 'rejected';

export function getStatusLabel(status: SegmentStatus): string {
  switch (status) {
    case 'auto_approved':
      return '自动通过';
    case 'needs_review':
      return '待审核';
    case 'approved':
      return '已批准';
    case 'rejected':
      return '已拒绝';
  }
}

export function getStatusColor(status: SegmentStatus): string {
  switch (status) {
    case 'auto_approved':
      return 'bg-success/10 text-success';
    case 'needs_review':
      return 'bg-warning/10 text-warning';
    case 'approved':
      return 'bg-teal/10 text-teal';
    case 'rejected':
      return 'bg-danger/10 text-danger';
  }
}

export function getPauseColor(pauseType: string): string {
  switch (pauseType) {
    case 'breath':
    case 'natural':
      return 'bg-success';
    case 'thinking':
      return 'bg-warning';
    case 'long':
      return 'bg-danger';
    default:
      return 'bg-text-muted';
  }
}

export function getPauseLabel(pauseType: string): string {
  switch (pauseType) {
    case 'breath':
      return '呼吸';
    case 'natural':
      return '自然';
    case 'thinking':
      return '思考';
    case 'long':
      return '长停顿';
    default:
      return '未知';
  }
}
