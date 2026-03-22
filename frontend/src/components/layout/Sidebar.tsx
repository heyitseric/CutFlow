import { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useJobStore } from '../../stores/jobStore';
import type { SingleJobState } from '../../stores/jobStore';
import { getStorageStats } from '../../api/client';


// ── Easing tokens (inline style) ──

const EASE_SPRING = 'cubic-bezier(0.34, 1.56, 0.64, 1)';
const EASE_SMOOTH_OUT = 'cubic-bezier(0.22, 1, 0.36, 1)';
const EASE_SNAPPY = 'cubic-bezier(0.2, 0, 0, 1)';
const EASE_CINEMATIC = 'cubic-bezier(0.77, 0, 0.175, 1)';


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
  return `/processing/${job.jobId}`;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const val = bytes / Math.pow(1024, i);
  return `${val.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}


// ── JobItem sub-component ──

interface JobItemProps {
  job: SingleJobState;
  isActive: boolean;
  onSelect: (job: SingleJobState) => void;
}

function JobItem({ job, isActive, onSelect }: JobItemProps) {
  const renameJob = useJobStore((s) => s.renameJob);
  const deleteJobAction = useJobStore((s) => s.deleteJobAction);

  const [menuOpen, setMenuOpen] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const nameClickTimerRef = useRef<number | null>(null);

  const menuRef = useRef<HTMLDivElement>(null);
  const deletePopoverRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function clearPendingNameClick() {
    if (nameClickTimerRef.current !== null) {
      window.clearTimeout(nameClickTimerRef.current);
      nameClickTimerRef.current = null;
    }
  }

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [menuOpen]);

  // Close delete popover on outside click
  useEffect(() => {
    if (!confirmingDelete) return;
    function handleClick(e: MouseEvent) {
      if (deletePopoverRef.current && !deletePopoverRef.current.contains(e.target as Node)) {
        setConfirmingDelete(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [confirmingDelete]);

  // Focus input when renaming starts
  useEffect(() => {
    if (isRenaming && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isRenaming]);

  useEffect(() => {
    return () => clearPendingNameClick();
  }, []);

  function startRename() {
    clearPendingNameClick();
    setMenuOpen(false);
    setRenameValue(job.displayName || job.scriptName || '');
    setIsRenaming(true);
  }

  async function commitRename() {
    const trimmed = renameValue.trim();
    if (trimmed && trimmed !== (job.displayName || job.scriptName)) {
      await renameJob(job.jobId, trimmed);
    }
    setIsRenaming(false);
  }

  function cancelRename() {
    setIsRenaming(false);
  }

  function startDelete() {
    setMenuOpen(false);
    setConfirmingDelete(true);
  }

  async function confirmDelete() {
    setConfirmingDelete(false);
    await deleteJobAction(job.jobId);
  }

  const pct = Math.round((job.progress ?? 0) * 100);
  const safeProgress = Number.isFinite(pct) ? pct : 0;
  const displayLabel = job.displayName || job.scriptName || '未命名';

  return (
    <div className="relative">
      <button
        onClick={() => {
          if (!isRenaming && !confirmingDelete) onSelect(job);
        }}
        className={`
          group flex w-full flex-col gap-1 rounded-xl px-3 py-2.5 text-left
          ${isActive
            ? 'bg-amber-glow/40 ring-1 ring-amber/20'
            : 'hover:bg-elevated/60'
          }
        `}
        style={{
          transition: `all 200ms ${EASE_SNAPPY}`,
        }}
      >
        {/* Top row: name + status + menu trigger */}
        <div className="flex items-center gap-2">
          {statusIndicator(job.status)}

          {isRenaming ? (
            <input
              ref={inputRef}
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitRename();
                if (e.key === 'Escape') cancelRename();
              }}
              onBlur={commitRename}
              onClick={(e) => e.stopPropagation()}
              className="flex-1 rounded-md border border-amber/30 bg-deep px-1.5 py-0.5 text-xs font-medium text-text-primary outline-none focus:border-amber/60 focus:ring-1 focus:ring-amber/20"
              style={{
                transition: `border-color 200ms ${EASE_SMOOTH_OUT}, box-shadow 200ms ${EASE_SMOOTH_OUT}`,
              }}
              maxLength={60}
            />
          ) : (
            <span
              className={`flex-1 truncate text-xs font-medium ${
                isActive ? 'text-amber' : 'text-text-primary'
              }`}
              onClick={(e) => {
                e.stopPropagation();
                if (isRenaming || confirmingDelete) return;
                clearPendingNameClick();
                nameClickTimerRef.current = window.setTimeout(() => {
                  nameClickTimerRef.current = null;
                  onSelect(job);
                }, 250);
              }}
              onDoubleClick={(e) => {
                e.stopPropagation();
                startRename();
              }}
              title="双击重命名"
            >
              {truncate(displayLabel, 20)}
            </span>
          )}

          {/* "..." menu trigger — visible on hover */}
          {!isRenaming && (
            <div
              ref={menuRef}
              className="relative"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setMenuOpen((v) => !v);
                  setConfirmingDelete(false);
                }}
                className="flex h-5 w-5 items-center justify-center rounded-md text-text-faint opacity-0 group-hover:opacity-100 hover:bg-elevated hover:text-text-primary"
                style={{
                  transition: `opacity 180ms ${EASE_SMOOTH_OUT}, background-color 150ms ${EASE_SNAPPY}`,
                }}
                title="更多操作"
              >
                <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
                  <circle cx="12" cy="6" r="1.5" />
                  <circle cx="12" cy="12" r="1.5" />
                  <circle cx="12" cy="18" r="1.5" />
                </svg>
              </button>

              {/* Context dropdown */}
              {menuOpen && (
                <div
                  className="absolute right-0 top-6 z-50 min-w-[120px] overflow-hidden rounded-lg border border-border-subtle bg-surface shadow-xl"
                  style={{
                    animation: `sidebar-dropdown-in 180ms ${EASE_SPRING} forwards`,
                  }}
                >
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      startRename();
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-text-secondary hover:bg-elevated hover:text-text-primary"
                    style={{ transition: `all 120ms ${EASE_SNAPPY}` }}
                  >
                    <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                    </svg>
                    重命名
                  </button>
                  <div className="mx-2 border-t border-border-subtle" />
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      startDelete();
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-danger hover:bg-danger/10"
                    style={{ transition: `all 120ms ${EASE_SNAPPY}` }}
                  >
                    <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                    </svg>
                    删除
                  </button>
                </div>
              )}
            </div>
          )}
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
              className="h-full rounded-full bg-amber/60"
              style={{
                width: `${safeProgress}%`,
                transition: `width 700ms ${EASE_CINEMATIC}`,
              }}
            />
          </div>
        )}
      </button>

      {/* Delete confirmation popover */}
      {confirmingDelete && (
        <div
          ref={deletePopoverRef}
          className="absolute left-2 right-2 top-full z-50 mt-1 rounded-lg border border-danger/30 bg-surface p-3 shadow-xl"
          style={{
            animation: `sidebar-popover-in 200ms ${EASE_SPRING} forwards`,
          }}
        >
          <p className="mb-2.5 text-[11px] leading-relaxed text-text-secondary">
            确定删除此任务及所有文件？
          </p>
          <div className="flex items-center justify-end gap-2">
            <button
              onClick={() => setConfirmingDelete(false)}
              className="rounded-md px-2.5 py-1 text-[11px] text-text-muted hover:bg-elevated hover:text-text-primary"
              style={{ transition: `all 150ms ${EASE_SNAPPY}` }}
            >
              取消
            </button>
            <button
              onClick={confirmDelete}
              className="rounded-md bg-danger/15 px-2.5 py-1 text-[11px] font-medium text-danger hover:bg-danger/25"
              style={{ transition: `all 150ms ${EASE_SNAPPY}` }}
            >
              确认删除
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


// ── Main Sidebar ──

export default function Sidebar() {
  const navigate = useNavigate();

  const jobs = useJobStore((s) => s.jobs);
  const activeJobId = useJobStore((s) => s.activeJobId);
  const sidebarOpen = useJobStore((s) => s.sidebarOpen);
  const setActiveJob = useJobStore((s) => s.setActiveJob);
  const toggleSidebar = useJobStore((s) => s.toggleSidebar);
  const fetchJobList = useJobStore((s) => s.fetchJobList);

  const [storageDisplay, setStorageDisplay] = useState<string | null>(null);

  // Fetch job list on mount and periodically
  useEffect(() => {
    fetchJobList();
    const interval = setInterval(fetchJobList, 10000);
    return () => clearInterval(interval);
  }, [fetchJobList]);

  // Fetch storage stats
  const fetchStorage = useCallback(async () => {
    try {
      const stats = await getStorageStats();
      setStorageDisplay(stats.total_display || formatBytes(stats.total_bytes));
    } catch {
      setStorageDisplay(null);
    }
  }, []);

  useEffect(() => {
    fetchStorage();
    const interval = setInterval(fetchStorage, 30000);
    return () => clearInterval(interval);
  }, [fetchStorage]);

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
      {/* Keyframes for dropdown & popover animations */}
      <style>{`
        @keyframes sidebar-dropdown-in {
          from {
            opacity: 0;
            transform: scale(0.92) translateY(-4px);
          }
          to {
            opacity: 1;
            transform: scale(1) translateY(0);
          }
        }
        @keyframes sidebar-popover-in {
          from {
            opacity: 0;
            transform: scale(0.95) translateY(-6px);
          }
          to {
            opacity: 1;
            transform: scale(1) translateY(0);
          }
        }
        @keyframes sidebar-storage-in {
          from {
            opacity: 0;
            transform: translateY(8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>

      {/* Toggle button (visible when sidebar is collapsed) */}
      {!sidebarOpen && (
        <button
          onClick={toggleSidebar}
          className="fixed left-3 top-[72px] z-40 flex h-8 w-8 items-center justify-center rounded-lg bg-elevated text-text-muted hover:bg-hover hover:text-text-primary"
          style={{
            transition: `all 200ms ${EASE_SNAPPY}`,
          }}
          title="展开侧栏"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      )}

      {/* Sidebar panel */}
      <aside
        className="shrink-0 overflow-hidden border-r border-border-subtle bg-[rgba(255,255,255,0.02)]"
        style={{
          width: sidebarOpen ? 260 : 0,
          transition: `width 300ms ${EASE_CINEMATIC}`,
        }}
      >
        <div className="flex h-full w-[260px] flex-col">
          {/* Header */}
          <div className="flex h-14 items-center justify-between border-b border-border-subtle px-4">
            <span className="font-display text-sm font-semibold text-text-secondary">历史记录</span>
            <div className="flex items-center gap-1">
              <button
                onClick={handleNewJob}
                className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber/15 text-amber hover:bg-amber/25"
                style={{ transition: `all 180ms ${EASE_SPRING}` }}
                title="新建任务"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" d="M12 5v14M5 12h14" />
                </svg>
              </button>
              <button
                onClick={toggleSidebar}
                className="flex h-7 w-7 items-center justify-center rounded-lg text-text-muted hover:bg-elevated hover:text-text-primary"
                style={{ transition: `all 180ms ${EASE_SNAPPY}` }}
                title="收起侧栏"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                </svg>
              </button>
            </div>
          </div>

          {/* Job list (scrollable) */}
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
                {sortedJobs.map((job) => (
                  <JobItem
                    key={job.jobId}
                    job={job}
                    isActive={job.jobId === activeJobId}
                    onSelect={handleJobClick}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Storage indicator (bottom) */}
          {storageDisplay !== null && (
            <div
              className="border-t border-border-subtle px-4 py-2.5"
              style={{
                animation: `sidebar-storage-in 350ms ${EASE_SMOOTH_OUT} forwards`,
              }}
            >
              <button
                onClick={() => navigate('/storage')}
                className="group flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-elevated/60"
                style={{ transition: `all 180ms ${EASE_SNAPPY}` }}
              >
                <svg
                  className="h-3.5 w-3.5 shrink-0 text-text-faint group-hover:text-amber"
                  style={{ transition: `color 200ms ${EASE_SMOOTH_OUT}` }}
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
                </svg>
                <span className="text-[11px] text-text-faint group-hover:text-text-secondary" style={{ transition: `color 200ms ${EASE_SMOOTH_OUT}` }}>
                  已用存储
                </span>
                <span
                  className="ml-auto font-mono text-[11px] text-text-muted group-hover:text-amber"
                  style={{ transition: `color 200ms ${EASE_SMOOTH_OUT}` }}
                >
                  {storageDisplay}
                </span>
              </button>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
