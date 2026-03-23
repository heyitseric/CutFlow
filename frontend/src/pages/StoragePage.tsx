import { useEffect, useState, useCallback } from 'react';
import { getStorageStats, cleanupStorage } from '../api/client';
import type { StorageStats, StorageJobInfo } from '../api/types';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
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
import {
  Loader2,
  CheckCircle2,
  X,
  ChevronDown,
  Package,
  Trash2,
  FileX,
  AlertCircle,
} from 'lucide-react';

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

const STATUS_MAP: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
  completed: { label: '已完成', variant: 'secondary' },
  done: { label: '已完成', variant: 'secondary' },
  review: { label: '待审核', variant: 'outline' },
  processing: { label: '处理中', variant: 'default' },
  error: { label: '错误', variant: 'destructive' },
  uploading: { label: '上传中', variant: 'outline' },
  created: { label: '已创建', variant: 'secondary' },
  orphan: { label: '残留文件', variant: 'destructive' },
};

function statusInfo(status: string) {
  return STATUS_MAP[status] ?? { label: status, variant: 'secondary' as const };
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
    <div className="mx-auto max-w-5xl px-6 py-8">
      {/* ── Header ── */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          存储管理
        </h1>
        {stats && (
          <div className="mt-3 flex items-baseline gap-4">
            <span className="font-mono text-4xl font-bold text-foreground">
              {stats.total_display}
            </span>
            <span className="text-sm text-muted-foreground">
              {stats.jobs.length} 个任务
            </span>
          </div>
        )}
      </div>

      {/* ── Result toast ── */}
      {result && (
        <Alert className="mb-6 border-success/20 bg-success/5">
          <CheckCircle2 className="size-4 text-success" />
          <AlertDescription className="flex items-center justify-between">
            <span className="text-sm text-success">
              已清理 {result.count} 个任务，释放 {result.freed}
            </span>
            <Button variant="ghost" size="icon-xs" onClick={() => setResult(null)}>
              <X className="size-3.5" />
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* ── Loading ── */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-24">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
          <p className="mt-4 text-sm text-muted-foreground">正在加载存储信息...</p>
        </div>
      )}

      {/* ── Error ── */}
      {error && !loading && (
        <Alert variant="destructive" className="text-center">
          <AlertCircle className="size-4" />
          <AlertDescription>
            <p className="text-sm">{error}</p>
            <Button
              variant="destructive"
              size="sm"
              onClick={loadStats}
              className="mt-3"
            >
              重试
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* ── Empty state ── */}
      {stats && stats.jobs.length === 0 && !loading && (
        <Card className="flex flex-col items-center justify-center py-20">
          <div className="mb-4 flex size-16 items-center justify-center rounded-2xl bg-muted">
            <Package className="size-8 text-muted-foreground" />
          </div>
          <p className="text-lg font-medium text-foreground">暂无任务数据</p>
          <p className="mt-1 text-sm text-muted-foreground">创建新任务后，存储信息会在此显示</p>
        </Card>
      )}

      {/* ── Job list ── */}
      {stats && stats.jobs.length > 0 && !loading && (
        <div className="space-y-3">
          {/* Select-all bar */}
          <div className="flex items-center gap-3 px-1 pb-2">
            <Checkbox
              checked={
                selected.size === stats.jobs.length && stats.jobs.length > 0
                  ? true
                  : selected.size > 0
                    ? 'indeterminate'
                    : false
              }
              onCheckedChange={toggleAll}
            />
            <span className="text-xs text-muted-foreground">
              {selected.size > 0
                ? `已选 ${selected.size} 个任务`
                : '全选'}
            </span>
          </div>

          {/* Jobs */}
          {stats.jobs.map((job) => (
            <JobRow
              key={job.job_id}
              job={job}
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
        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 backdrop-blur-md animate-in slide-in-from-bottom duration-300">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
            <div className="flex items-center gap-3">
              <Badge variant="secondary" className="font-mono">
                {selected.size}
              </Badge>
              <span className="text-sm text-muted-foreground">
                已选中 &middot; {formatBytes(selectedBytes)}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => openModal('clean')}
              >
                <FileX className="size-4" />
                仅清理文件
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => openModal('delete')}
              >
                <Trash2 className="size-4" />
                删除选中任务
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete confirmation modal ── */}
      <AlertDialog open={showModal} onOpenChange={setShowModal}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {modalMode === 'delete' ? '确定删除？' : '确定清理文件？'}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {modalMode === 'delete'
                ? `将永久删除 ${selected.size} 个任务及其所有文件`
                : `将清理 ${selected.size} 个任务的上传和输出文件，保留任务记录`}
            </AlertDialogDescription>
          </AlertDialogHeader>

          <div className="rounded-lg bg-muted px-4 py-3 text-center">
            <span className="text-xs text-muted-foreground">预计释放空间</span>
            <p className="mt-1 font-mono text-xl font-bold text-foreground">
              {formatBytes(selectedBytes)}
            </p>
          </div>

          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              variant={modalMode === 'delete' ? 'destructive' : 'default'}
              onClick={handleConfirm}
              disabled={deleting}
            >
              {deleting ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="size-3.5 animate-spin" />
                  处理中...
                </span>
              ) : modalMode === 'delete' ? (
                '确定删除'
              ) : (
                '确定清理'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

/* ═════════════════════════════════════════
   Job Row
   ═════════════════════════════════════════ */

interface JobRowProps {
  job: StorageJobInfo;
  isSelected: boolean;
  isExpanded: boolean;
  maxBytes: number;
  onToggleSelect: () => void;
  onToggleExpand: () => void;
}

function JobRow({
  job,
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
    <Card
      className={`overflow-hidden transition-colors ${
        isSelected ? 'border-primary/30 bg-primary/[0.02]' : ''
      }`}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        {/* Checkbox */}
        <Checkbox
          checked={isSelected}
          onCheckedChange={onToggleSelect}
        />

        {/* Info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium text-foreground">
              {job.display_name}
            </span>
            <Badge variant={si.variant}>
              {si.label}
            </Badge>
          </div>
          <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
            <span>{formatDate(job.created_at)}</span>
            {job.upload_bytes > 0 && (
              <span>
                <span className="text-muted-foreground/50">上传</span> {formatBytes(job.upload_bytes)}
              </span>
            )}
            {job.output_bytes > 0 && (
              <span>
                <span className="text-muted-foreground/50">输出</span> {formatBytes(job.output_bytes)}
              </span>
            )}
          </div>
          {/* Size bar */}
          <div className="mt-2">
            <Progress value={pct} className="h-1" />
          </div>
        </div>

        {/* Size + expand */}
        <div className="flex shrink-0 items-center gap-3">
          <span className="font-mono text-sm font-semibold text-muted-foreground">
            {job.total_display}
          </span>
          {files.length > 0 && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={onToggleExpand}
            >
              <ChevronDown
                className={`size-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
              />
            </Button>
          )}
        </div>
      </div>

      {/* Expanded file list */}
      {isExpanded && files.length > 0 && (
        <CardContent className="border-t border-border bg-muted/30 px-4 py-2.5">
          <div className="space-y-1">
            {files.map(([name, size]) => (
              <div key={name} className="flex items-center justify-between py-1">
                <span className="truncate font-mono text-xs text-muted-foreground">{name}</span>
                <span className="ml-4 shrink-0 font-mono text-xs text-muted-foreground/50">
                  {formatBytes(size)}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      )}
    </Card>
  );
}
