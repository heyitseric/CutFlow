import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useJobStore } from '../../stores/jobStore';
import type { SingleJobState } from '../../stores/jobStore';


// ── Helpers ──

function relativeTime(isoDate: string): string {
  const now = Date.now();
  const then = new Date(isoDate).getTime();
  if (isNaN(then)) return '';
  const diff = Math.max(0, Math.floor((now - then) / 1000));
  if (diff < 60) return '刚刚';
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
  return `${Math.floor(diff / 86400)}天前`;
}

function statusIndicator(status: string) {
  switch (status) {
    case 'completed':
      return <span className="h-2 w-2 shrink-0 rounded-full bg-success" title="已完成" />;
    case 'failed':
      return <span className="h-2 w-2 shrink-0 rounded-full bg-danger" title="失败" />;
    default:
      return <span className="h-2 w-2 shrink-0 rounded-full bg-warning animate-gentle-pulse" title="处理中" />;
  }
}

function truncate(str: string, maxLen: number): string {
  if (!str) return '未命名';
  return str.length > maxLen ? str.slice(0, maxLen) + '...' : str;
}

function jobRoute(job: SingleJobState): string {
  if (job.status === 'completed' && job.alignment) {
    return `/review/${job.jobId}`;
  }
  if (job.status === 'failed') {
    return `/processing/${job.jobId}`;
  }
  return `/processing/${job.jobId}`;
}

// ── Component ──

export default function Sidebar() {
  const navigate = useNavigate();

  const jobs = useJobStore((s) => s.jobs);
  const activeJobId = useJobStore((s) => s.activeJobId);
  const sidebarOpen = useJobStore((s) => s.sidebarOpen);
  const setActiveJob = useJobStore((s) => s.setActiveJob);
  const toggleSidebar = useJobStore((s) => s.toggleSidebar);
  const fetchJobList = useJobStore((s) => s.fetchJobList);

  // Fetch job list on mount and periodically
  useEffect(() => {
    fetchJobList();
    const interval = setInterval(fetchJobList, 10000);
    return () => clearInterval(interval);
  }, [fetchJobList]);

  // Sort jobs: newest first
  const sortedJobs = Object.values(jobs).sort((a, b) => {
    const ta = new Date(a.createdAt).getTime() || 0;
    const tb = new Date(b.createdAt).getTime() || 0;
    return tb - ta;
  });

  function handleJobClick(job: SingleJobState) {
    setActiveJob(job.jobId);
    navigate(jobRoute(job));
  }

  function handleNewJob() {
    setActiveJob(null);
    navigate('/');
  }

  return (
    <>
      {/* Toggle button (visible when sidebar is collapsed) */}
      {!sidebarOpen && (
        <button
          onClick={toggleSidebar}
          className="fixed left-3 top-[72px] z-40 flex h-8 w-8 items-center justify-center rounded-lg bg-elevated text-text-muted hover:bg-hover hover:text-text-primary transition-colors"
          title="展开侧栏"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      )}

      {/* Sidebar panel */}
      <aside
        className={`
          shrink-0 overflow-hidden border-r border-border-subtle bg-[rgba(255,255,255,0.02)]
          transition-all duration-300 ease-in-out
          ${sidebarOpen ? 'w-[260px]' : 'w-0'}
        `}
      >
        <div className="flex h-full w-[260px] flex-col">
          {/* Header */}
          <div className="flex h-14 items-center justify-between border-b border-border-subtle px-4">
            <span className="font-display text-sm font-semibold text-text-secondary">历史记录</span>
            <div className="flex items-center gap-1">
              <button
                onClick={handleNewJob}
                className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber/15 text-amber hover:bg-amber/25 transition-colors"
                title="新建任务"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" d="M12 5v14M5 12h14" />
                </svg>
              </button>
              <button
                onClick={toggleSidebar}
                className="flex h-7 w-7 items-center justify-center rounded-lg text-text-muted hover:bg-elevated hover:text-text-primary transition-colors"
                title="收起侧栏"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                </svg>
              </button>
            </div>
          </div>

          {/* Job list (scrollable, takes remaining space above monitor) */}
          <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
            {sortedJobs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-elevated text-text-muted">
                  <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                  </svg>
                </div>
                <p className="text-xs text-text-muted">暂无任务</p>
                <p className="mt-1 text-[10px] text-text-faint">点击 + 开始新任务</p>
              </div>
            ) : (
              <div className="flex flex-col gap-0.5">
                {sortedJobs.map((job) => {
                  const isActive = job.jobId === activeJobId;
                  const pct = Math.round((job.progress ?? 0) * 100);
                  const safeProgress = Number.isFinite(pct) ? pct : 0;

                  return (
                    <button
                      key={job.jobId}
                      onClick={() => handleJobClick(job)}
                      className={`
                        group flex w-full flex-col gap-1 rounded-xl px-3 py-2.5 text-left
                        transition-all duration-200
                        ${isActive
                          ? 'bg-amber-glow/40 ring-1 ring-amber/20'
                          : 'hover:bg-elevated/60'
                        }
                      `}
                    >
                      {/* Top row: name + status */}
                      <div className="flex items-center gap-2">
                        {statusIndicator(job.status)}
                        <span className={`flex-1 truncate text-xs font-medium ${
                          isActive ? 'text-amber' : 'text-text-primary'
                        }`}>
                          {truncate(job.scriptName, 20)}
                        </span>
                      </div>

                      {/* Bottom row: progress + time */}
                      <div className="flex items-center justify-between pl-4">
                        {job.status === 'processing' ? (
                          <span className="font-mono text-[10px] text-text-muted">
                            {safeProgress}%
                          </span>
                        ) : job.status === 'completed' ? (
                          <span className="text-[10px] text-success">已完成</span>
                        ) : (
                          <span className="text-[10px] text-danger">失败</span>
                        )}
                        <span className="text-[10px] text-text-faint">
                          {relativeTime(job.createdAt)}
                        </span>
                      </div>

                      {/* Progress bar for active processing jobs */}
                      {job.status === 'processing' && (
                        <div className="ml-4 h-0.5 overflow-hidden rounded-full bg-elevated">
                          <div
                            className="h-full rounded-full bg-amber/60 transition-all duration-700"
                            style={{ width: `${safeProgress}%` }}
                          />
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

        </div>
      </aside>
    </>
  );
}
