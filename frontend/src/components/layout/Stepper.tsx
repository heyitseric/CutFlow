import { useNavigate } from 'react-router-dom';

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
                    isCompleted ? 'bg-amber' : 'bg-border'
                  }`}
                />
              </div>
            )}
            <button
              onClick={() => handleClick(i)}
              disabled={!isClickable}
              className={`group flex items-center gap-2.5 rounded-full px-4 py-2 text-sm font-medium transition-all duration-300 ${
                isActive
                  ? 'bg-amber/15 text-amber ring-1 ring-amber/30'
                  : isCompleted
                    ? 'text-amber/80 hover:bg-amber/8 cursor-pointer'
                    : 'text-text-muted cursor-default'
              }`}
            >
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full font-mono text-xs transition-all duration-300 ${
                  isActive
                    ? 'bg-amber text-deep font-semibold'
                    : isCompleted
                      ? 'bg-amber/20 text-amber'
                      : 'bg-elevated text-text-muted'
                }`}
              >
                {isCompleted ? (
                  <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
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
