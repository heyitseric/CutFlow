import { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useJobStore } from '../../stores/jobStore';
import type { SingleJobState } from '../../stores/jobStore';
import { getStorageStats } from '../../api/client';
import { MoreVertical, Pencil, Trash2, Plus, ChevronLeft, ChevronRight, Database, FileText } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';


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

  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const nameClickTimerRef = useRef<number | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);

  function clearPendingNameClick() {
    if (nameClickTimerRef.current !== null) {
      window.clearTimeout(nameClickTimerRef.current);
      nameClickTimerRef.current = null;
    }
  }

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
            ? 'bg-accent ring-1 ring-border'
            : 'hover:bg-accent/50'
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
              className="flex-1 rounded-md border border-input bg-background px-1.5 py-0.5 text-xs font-medium text-foreground outline-none focus:border-ring focus:ring-1 focus:ring-ring/20"
              style={{
                transition: `border-color 200ms ${EASE_SMOOTH_OUT}, box-shadow 200ms ${EASE_SMOOTH_OUT}`,
              }}
              maxLength={60}
            />
          ) : (
            <span
              className={`flex-1 truncate text-xs font-medium ${
                isActive ? 'text-foreground' : 'text-foreground'
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
            <div onClick={(e) => e.stopPropagation()}>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    className="flex h-5 w-5 items-center justify-center rounded-md text-muted-foreground/50 opacity-0 group-hover:opacity-100 hover:bg-accent hover:text-foreground"
                    style={{
                      transition: `opacity 180ms ${EASE_SMOOTH_OUT}, background-color 150ms ${EASE_SNAPPY}`,
                    }}
                    title="更多操作"
                  >
                    <MoreVertical className="h-3.5 w-3.5" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="min-w-[120px]">
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      startRename();
                    }}
                    className="text-xs gap-2"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    重命名
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      setConfirmingDelete(true);
                    }}
                    className="text-xs gap-2 text-destructive focus:text-destructive"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    删除
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          )}
        </div>

        {/* Bottom row: progress + time */}
        <div className="flex items-center justify-between pl-4">
          {job.status === 'processing' ? (
            <span className="font-mono text-[10px] text-muted-foreground">
              {safeProgress}%
            </span>
          ) : job.status === 'completed' ? (
            <span className="text-[10px] text-success">已完成</span>
          ) : (
            <span className="text-[10px] text-danger">失败</span>
          )}
          <span className="text-[10px] text-muted-foreground/50">
            {relativeTime(job.createdAt)}
          </span>
        </div>

        {/* Progress bar for active processing jobs */}
        {job.status === 'processing' && (
          <div className="ml-4 h-0.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary/60"
              style={{
                width: `${safeProgress}%`,
                transition: `width 700ms ${EASE_CINEMATIC}`,
              }}
            />
          </div>
        )}
      </button>

      {/* Delete confirmation dialog */}
      <AlertDialog open={confirmingDelete} onOpenChange={setConfirmingDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              确定删除此任务及所有文件？此操作无法撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              确认删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
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
      {/* Toggle button (visible when sidebar is collapsed) */}
      {!sidebarOpen && (
        <button
          onClick={toggleSidebar}
          className="fixed left-3 top-[72px] z-40 flex h-8 w-8 items-center justify-center rounded-lg bg-muted text-muted-foreground hover:bg-accent hover:text-foreground"
          style={{
            transition: `all 200ms ${EASE_SNAPPY}`,
          }}
          title="展开侧栏"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      )}

      {/* Sidebar panel */}
      <aside
        className="shrink-0 overflow-hidden border-r border-border bg-card"
        style={{
          width: sidebarOpen ? 260 : 0,
          transition: `width 300ms ${EASE_CINEMATIC}`,
        }}
      >
        <div className="flex h-full w-[260px] flex-col">
          {/* Header */}
          <div className="flex h-14 items-center justify-between border-b border-border px-4">
            <span className="font-display text-sm font-semibold text-muted-foreground">历史记录</span>
            <div className="flex items-center gap-1">
              <button
                onClick={handleNewJob}
                className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-foreground hover:bg-primary/20"
                style={{ transition: `all 180ms ${EASE_SPRING}` }}
                title="新建任务"
              >
                <Plus className="h-4 w-4" />
              </button>
              <button
                onClick={toggleSidebar}
                className="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground"
                style={{ transition: `all 180ms ${EASE_SNAPPY}` }}
                title="收起侧栏"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Job list (scrollable) */}
          <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
            {sortedJobs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-muted text-muted-foreground">
                  <FileText className="h-5 w-5" />
                </div>
                <p className="text-xs text-muted-foreground">暂无任务</p>
                <p className="mt-1 text-[10px] text-muted-foreground/50">点击 + 开始新任务</p>
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
            <div className="border-t border-border px-4 py-2.5">
              <button
                onClick={() => navigate('/storage')}
                className="group flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-accent/50"
                style={{ transition: `all 180ms ${EASE_SNAPPY}` }}
              >
                <Database
                  className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50 group-hover:text-foreground"
                  style={{ transition: `color 200ms ${EASE_SMOOTH_OUT}` }}
                />
                <span
                  className="text-[11px] text-muted-foreground/50 group-hover:text-muted-foreground"
                  style={{ transition: `color 200ms ${EASE_SMOOTH_OUT}` }}
                >
                  已用存储
                </span>
                <span
                  className="ml-auto font-mono text-[11px] text-muted-foreground group-hover:text-foreground"
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
