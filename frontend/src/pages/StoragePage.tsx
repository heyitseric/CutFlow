import { useEffect, useState, useCallback } from 'react';
import { getStorageStats, cleanupStorage } from '../api/client';
import type { StorageStats, StorageJobInfo } from '../api/types';

/* ── Easing CSS variables ── */
const EASE_SPRING = 'cubic-bezier(0.34, 1.56, 0.64, 1)';
const EASE_SMOOTH_OUT = 'cubic-bezier(0.22, 1, 0.36, 1)';
const EASE_SNAPPY = 'cubic-bezier(0.2, 0, 0, 1)';
const EASE_CINEMATIC = 'cubic-bezier(0.77, 0, 0.175, 1)';

/* ── Helpers ── */

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  return `${d.getFullYear()}-${month}-${day} ${hours}:${minutes}`;
}

const STATUS_MAP: Record<string, { label: string; color: string; bg: string }> = {
  completed: { label: '已完成', color: 'text-success', bg: 'bg-success/10' },
  done: { label: '已完成', color: 'text-success', bg: 'bg-success/10' },
  review: { label: '待审核', color: 'text-teal', bg: 'bg-teal/10' },
  processing: { label: '处理中', color: 'text-amber', bg: 'bg-amber/10' },
  error: { label: '错误', color: 'text-danger', bg: 'bg-danger/10' },
  uploading: { label: '上传中', color: 'text-teal', bg: 'bg-teal/10' },
  created: { label: '已创建', color: 'text-text-secondary', bg: 'bg-panel' },
  orphan: { label: '残留文件', color: 'text-warning', bg: 'bg-warning/10' },
};

function statusInfo(status: string) {
  return STATUS_MAP[status] ?? { label: status, color: 'text-text-secondary', bg: 'bg-panel' };
}

/* ── Component ── */

export default function StoragePage() {
  const [stats, setStats] = useState<StorageStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState<'delete' | 'clean'>('delete');
  const [deleting, setDeleting] = useState(false);
  const [result, setResult] = useState<{ freed: string; count: number } | null>(null);

  const loadStats = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getStorageStats();
      setStats(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const maxJobBytes = stats
    ? Math.max(...stats.jobs.map((j) => j.total_bytes), 1)
    : 1;

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (!stats) return;
    if (selected.size === stats.jobs.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(stats.jobs.map((j) => j.job_id)));
    }
  };

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectedBytes = stats
    ? stats.jobs
        .filter((j) => selected.has(j.job_id))
        .reduce((sum, j) => sum + j.total_bytes, 0)
    : 0;

  const openModal = (mode: 'delete' | 'clean') => {
    setModalMode(mode);
    setShowModal(true);
  };

  const handleConfirm = async () => {
    if (!stats) return;
    setDeleting(true);
    try {
      const isFullDelete = modalMode === 'delete';
      const res = await cleanupStorage({
        job_ids: Array.from(selected),
        delete_uploads: true,
        delete_outputs: true,
        delete_job: isFullDelete,
      });
      setResult({ freed: res.freed_display, count: res.deleted_count });
      setSelected(new Set());
      setShowModal(false);
      await loadStats();
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败');
      setShowModal(false);
    } finally {
      setDeleting(false);
    }
  };

  /* ── Render ── */

  return (
    <div className="animate-fade-in-up mx-auto max-w-5xl px-6 py-8">
      {/* ── Header ── */}
      <div className="mb-8">
        <h1 className="font-display text-2xl font-bold tracking-tight text-text-primary">
          存储管理
        </h1>
        {stats && (
          <div className="mt-3 flex items-baseline gap-4">
            <span
              className="font-mono text-4xl font-bold text-amber"
              style={{ transition: `all 0.5s ${EASE_SMOOTH_OUT}` }}
            >
              {stats.total_display}
            </span>
            <span className="text-sm text-text-muted">
              {stats.jobs.length} 个任务
            </span>
          </div>
        )}
      </div>

      {/* ── Result toast ── */}
      {result && (
        <div
          className="animate-slide-down mb-6 flex items-center gap-3 rounded-xl border border-success/20 bg-success/5 px-5 py-3"
          style={{ animationTimingFunction: EASE_SPRING }}
        >
          <svg className="h-5 w-5 shrink-0 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-sm text-success">
            已清理 {result.count} 个任务，释放 {result.freed}
          </span>
          <button
            className="ml-auto text-text-muted hover:text-text-primary"
            onClick={() => setResult(null)}
            style={{ transition: `color 0.2s ${EASE_SNAPPY}` }}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* ── Loading ── */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-24">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber/30 border-t-amber" />
          <p className="mt-4 text-sm text-text-muted">正在加载存储信息...</p>
        </div>
      )}

      {/* ── Error ── */}
      {error && !loading && (
        <div className="rounded-xl border border-danger/20 bg-danger/5 px-5 py-4 text-center">
          <p className="text-sm text-danger">{error}</p>
          <button
            onClick={loadStats}
            className="mt-3 rounded-lg bg-danger/10 px-4 py-1.5 text-xs font-medium text-danger hover:bg-danger/20"
            style={{ transition: `background-color 0.2s ${EASE_SNAPPY}` }}
          >
            重试
          </button>
        </div>
      )}

      {/* ── Empty state ── */}
      {stats && stats.jobs.length === 0 && !loading && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-border bg-surface py-20">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-elevated">
            <svg className="h-8 w-8 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
          </div>
          <p className="text-lg font-medium text-text-secondary">暂无任务数据</p>
          <p className="mt-1 text-sm text-text-muted">创建新任务后，存储信息会在此显示</p>
        </div>
      )}

      {/* ── Job list ── */}
      {stats && stats.jobs.length > 0 && !loading && (
        <div className="space-y-3">
          {/* Select-all bar */}
          <div className="flex items-center gap-3 px-1 pb-2">
            <button
              onClick={toggleAll}
              className="flex h-5 w-5 shrink-0 items-center justify-center rounded border border-border bg-elevated hover:border-amber/50"
              style={{ transition: `border-color 0.2s ${EASE_SNAPPY}` }}
            >
              {selected.size === stats.jobs.length && stats.jobs.length > 0 && (
                <svg className="h-3.5 w-3.5 text-amber" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              )}
              {selected.size > 0 && selected.size < stats.jobs.length && (
                <div className="h-2 w-2 rounded-sm bg-amber" />
              )}
            </button>
            <span className="text-xs text-text-muted">
              {selected.size > 0
                ? `已选 ${selected.size} 个任务`
                : '全选'}
            </span>
          </div>

          {/* Jobs */}
          {stats.jobs.map((job, i) => (
            <JobRow
              key={job.job_id}
              job={job}
              index={i}
              isSelected={selected.has(job.job_id)}
              isExpanded={expanded.has(job.job_id)}
              maxBytes={maxJobBytes}
              onToggleSelect={() => toggleSelect(job.job_id)}
              onToggleExpand={() => toggleExpand(job.job_id)}
            />
          ))}
        </div>
      )}

      {/* ── Sticky action bar ── */}
      {selected.size > 0 && (
        <div
          className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-surface/95 backdrop-blur-md"
          style={{
            animation: `slideUpBar 0.35s ${EASE_SPRING} both`,
          }}
        >
          <style>{`
            @keyframes slideUpBar {
              from { transform: translateY(100%); opacity: 0; }
              to   { transform: translateY(0);    opacity: 1; }
            }
          `}</style>
          <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
            <div className="flex items-center gap-3">
              <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-full bg-amber/15 px-2 font-mono text-xs font-semibold text-amber">
                {selected.size}
              </span>
              <span className="text-sm text-text-secondary">
                已选中 &middot; {formatBytes(selectedBytes)}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => openModal('clean')}
                className="rounded-lg border border-border bg-elevated px-4 py-2 text-sm font-medium text-text-secondary hover:border-amber/30 hover:text-text-primary"
                style={{ transition: `all 0.2s ${EASE_SNAPPY}` }}
              >
                仅清理文件
              </button>
              <button
                onClick={() => openModal('delete')}
                className="rounded-lg bg-danger/15 px-4 py-2 text-sm font-medium text-danger hover:bg-danger/25"
                style={{ transition: `background-color 0.2s ${EASE_SNAPPY}` }}
              >
                删除选中任务
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete confirmation modal ── */}
      {showModal && (
        <ConfirmModal
          mode={modalMode}
          count={selected.size}
          bytes={selectedBytes}
          deleting={deleting}
          onCancel={() => setShowModal(false)}
          onConfirm={handleConfirm}
        />
      )}
    </div>
  );
}

/* ═════════════════════════════════════════
   Job Row
   ═════════════════════════════════════════ */

interface JobRowProps {
  job: StorageJobInfo;
  index: number;
  isSelected: boolean;
  isExpanded: boolean;
  maxBytes: number;
  onToggleSelect: () => void;
  onToggleExpand: () => void;
}

function JobRow({
  job,
  index,
  isSelected,
  isExpanded,
  maxBytes,
  onToggleSelect,
  onToggleExpand,
}: JobRowProps) {
  const pct = maxBytes > 0 ? (job.total_bytes / maxBytes) * 100 : 0;
  const si = statusInfo(job.status);
  const files = Object.entries(job.files);

  return (
    <div
      className={`animate-fade-in-up rounded-xl border ${
        isSelected
          ? 'border-amber/30 bg-amber/[0.03]'
          : 'border-border bg-surface'
      } overflow-hidden`}
      style={{
        animationDelay: `${index * 0.04}s`,
        transition: `border-color 0.25s ${EASE_SNAPPY}, background-color 0.25s ${EASE_SNAPPY}`,
      }}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        {/* Checkbox */}
        <button
          onClick={onToggleSelect}
          className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border ${
            isSelected
              ? 'border-amber bg-amber/20'
              : 'border-border bg-elevated hover:border-amber/40'
          }`}
          style={{ transition: `all 0.2s ${EASE_SPRING}` }}
        >
          {isSelected && (
            <svg className="h-3.5 w-3.5 text-amber" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          )}
        </button>

        {/* Info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium text-text-primary">
              {job.display_name}
            </span>
            <span className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-medium ${si.color} ${si.bg}`}>
              {si.label}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-3 text-xs text-text-muted">
            <span>{formatDate(job.created_at)}</span>
            {job.upload_bytes > 0 && (
              <span>
                <span className="text-text-faint">上传</span> {formatBytes(job.upload_bytes)}
              </span>
            )}
            {job.output_bytes > 0 && (
              <span>
                <span className="text-text-faint">输出</span> {formatBytes(job.output_bytes)}
              </span>
            )}
          </div>
          {/* Size bar */}
          <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-elevated">
            <div
              className="h-full rounded-full bg-amber/40"
              style={{
                width: `${pct}%`,
                transition: `width 0.6s ${EASE_CINEMATIC}`,
              }}
            />
          </div>
        </div>

        {/* Size + expand */}
        <div className="flex shrink-0 items-center gap-3">
          <span className="font-mono text-sm font-semibold text-text-secondary">
            {job.total_display}
          </span>
          {files.length > 0 && (
            <button
              onClick={onToggleExpand}
              className="flex h-7 w-7 items-center justify-center rounded-lg text-text-muted hover:bg-elevated hover:text-text-primary"
              style={{ transition: `all 0.2s ${EASE_SNAPPY}` }}
            >
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
                style={{
                  transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: `transform 0.3s ${EASE_SPRING}`,
                }}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Expanded file list */}
      {isExpanded && files.length > 0 && (
        <div
          className="border-t border-border/50 bg-elevated/30 px-4 py-2.5"
          style={{
            animation: `expandIn 0.3s ${EASE_SMOOTH_OUT} both`,
          }}
        >
          <style>{`
            @keyframes expandIn {
              from { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; }
              to   { opacity: 1; max-height: 500px; }
            }
          `}</style>
          <div className="space-y-1">
            {files.map(([name, size]) => (
              <div key={name} className="flex items-center justify-between py-1">
                <span className="truncate font-mono text-xs text-text-muted">{name}</span>
                <span className="ml-4 shrink-0 font-mono text-xs text-text-faint">
                  {formatBytes(size)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ═════════════════════════════════════════
   Confirm Modal
   ═════════════════════════════════════════ */

interface ConfirmModalProps {
  mode: 'delete' | 'clean';
  count: number;
  bytes: number;
  deleting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

function ConfirmModal({ mode, count, bytes, deleting, onCancel, onConfirm }: ConfirmModalProps) {
  const isFullDelete = mode === 'delete';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-deep/80 backdrop-blur-sm"
        onClick={!deleting ? onCancel : undefined}
        style={{ animation: `fadeIn 0.2s ${EASE_SNAPPY} both` }}
      />

      {/* Dialog */}
      <div
        className="relative w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-2xl"
        style={{
          animation: `modalIn 0.35s ${EASE_SPRING} both`,
        }}
      >
        <style>{`
          @keyframes modalIn {
            from {
              opacity: 0;
              transform: scale(0.92) translateY(12px);
            }
            to {
              opacity: 1;
              transform: scale(1) translateY(0);
            }
          }
        `}</style>

        {/* Icon */}
        <div
          className={`mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl ${
            isFullDelete ? 'bg-danger/10' : 'bg-warning/10'
          }`}
        >
          {isFullDelete ? (
            <svg className="h-6 w-6 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          ) : (
            <svg className="h-6 w-6 text-warning" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 13h6m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          )}
        </div>

        {/* Title */}
        <h3 className="text-center font-display text-lg font-bold text-text-primary">
          {isFullDelete ? '确定删除？' : '确定清理文件？'}
        </h3>

        {/* Description */}
        <p className="mt-2 text-center text-sm text-text-secondary">
          {isFullDelete
            ? `将永久删除 ${count} 个任务及其所有文件`
            : `将清理 ${count} 个任务的上传和输出文件，保留任务记录`}
        </p>

        {/* Space freed */}
        <div className="mt-4 rounded-xl bg-elevated px-4 py-3 text-center">
          <span className="text-xs text-text-muted">预计释放空间</span>
          <p className="mt-1 font-mono text-xl font-bold text-amber">
            {formatBytes(bytes)}
          </p>
        </div>

        {/* Actions */}
        <div className="mt-6 flex gap-3">
          <button
            onClick={onCancel}
            disabled={deleting}
            className="flex-1 rounded-xl border border-border bg-elevated py-2.5 text-sm font-medium text-text-secondary hover:bg-hover hover:text-text-primary disabled:opacity-50"
            style={{ transition: `all 0.2s ${EASE_SNAPPY}` }}
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            disabled={deleting}
            className={`flex-1 rounded-xl py-2.5 text-sm font-semibold disabled:opacity-60 ${
              isFullDelete
                ? 'bg-danger/20 text-danger hover:bg-danger/30'
                : 'bg-warning/20 text-warning hover:bg-warning/30'
            }`}
            style={{ transition: `background-color 0.2s ${EASE_SNAPPY}` }}
          >
            {deleting ? (
              <span className="inline-flex items-center gap-2">
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current/30 border-t-current" />
                处理中...
              </span>
            ) : isFullDelete ? (
              '确定删除'
            ) : (
              '确定清理'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
