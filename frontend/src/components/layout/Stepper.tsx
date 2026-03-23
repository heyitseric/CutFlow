import { useNavigate } from 'react-router-dom';
import { Check } from 'lucide-react';

const STEPS = [
  { key: 'upload', label: '上传', icon: '01', path: '/' },
  { key: 'processing', label: '处理', icon: '02', path: '/processing' },
  { key: 'review', label: '审核', icon: '03', path: '/review' },
  { key: 'export', label: '导出', icon: '04', path: '/export' },
] as const;

interface StepperProps {
  currentStep: number;
  jobId?: string | null;
}

export default function Stepper({ currentStep, jobId }: StepperProps) {
  const navigate = useNavigate();

  function handleClick(index: number) {
    if (index >= currentStep) return;
    const step = STEPS[index];
    if (index === 0) {
      navigate('/');
    } else if (jobId) {
      navigate(`${step.path}/${jobId}`);
    }
  }

  return (
    <div className="flex items-center justify-center gap-1 py-5">
      {STEPS.map((step, i) => {
        const isActive = i === currentStep;
        const isCompleted = i < currentStep;
        const isClickable = i < currentStep;

        return (
          <div key={step.key} className="flex items-center">
            {i > 0 && (
              <div className="mx-1.5 flex items-center">
                <div
                  className={`h-px w-12 transition-colors duration-500 ${
                    isCompleted ? 'bg-primary' : 'bg-border'
                  }`}
                />
              </div>
            )}
            <button
              onClick={() => handleClick(i)}
              disabled={!isClickable}
              className={`group flex items-center gap-2.5 rounded-full px-4 py-2 text-sm font-medium transition-all duration-300 ${
                isActive
                  ? 'bg-primary/10 text-foreground ring-1 ring-border'
                  : isCompleted
                    ? 'text-foreground hover:bg-accent cursor-pointer'
                    : 'text-muted-foreground cursor-default'
              }`}
            >
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full font-mono text-xs transition-all duration-300 ${
                  isActive
                    ? 'bg-primary text-primary-foreground font-semibold'
                    : isCompleted
                      ? 'bg-muted text-foreground'
                      : 'bg-muted text-muted-foreground'
                }`}
              >
                {isCompleted ? (
                  <Check className="h-3 w-3" />
                ) : (
                  step.icon
                )}
              </span>
              <span className="font-display">{step.label}</span>
            </button>
          </div>
        );
      })}
    </div>
  );
}
