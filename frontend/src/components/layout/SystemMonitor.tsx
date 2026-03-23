import { useEffect, useState } from 'react';

interface SystemStats {
  cpu_percent: number;
  memory_used_gb: number;
  memory_total_gb: number;
  memory_percent: number;
  gpu_name: string | null;
  gpu_percent: number | null;
  gpu_memory_used_gb: number | null;
  gpu_memory_total_gb: number | null;
  platform: string;
}

function textColor(pct: number): string {
  if (pct >= 80) return 'text-danger';
  if (pct >= 50) return 'text-warning';
  return 'text-muted-foreground';
}

export default function SystemMonitor() {
  const [stats, setStats] = useState<SystemStats | null>(null);

  useEffect(() => {
    let active = true;

    async function fetchStats() {
      try {
        const res = await fetch('/api/system/stats');
        if (res.ok && active) {
          setStats(await res.json());
        }
      } catch {
        // silently ignore — monitor is non-critical
      }
    }

    fetchStats();
    const interval = setInterval(fetchStats, 3000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  if (!stats) {
    return (
      <div className="fixed bottom-3 right-3 z-50 rounded-lg border border-border bg-card px-3 py-1.5 shadow-sm">
        <span className="font-mono text-[10px] text-muted-foreground">系统监控加载中…</span>
      </div>
    );
  }

  const cpuPct = Math.round(stats.cpu_percent);
  const memPct = Math.round(stats.memory_percent);
  const gpuPct = stats.gpu_percent != null ? Math.round(stats.gpu_percent) : null;

  return (
    <div className="fixed bottom-3 right-3 z-50 flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-1.5 shadow-sm">
      <span className="font-mono text-[10px] text-muted-foreground">CPU</span>
      <span className={`font-mono text-[10px] tabular-nums ${textColor(cpuPct)}`}>{cpuPct}%</span>

      <span className="text-border">|</span>

      <span className="font-mono text-[10px] text-muted-foreground">RAM</span>
      <span className={`font-mono text-[10px] tabular-nums ${textColor(memPct)}`}>
        {stats.memory_used_gb}/{stats.memory_total_gb}G
      </span>

      <span className="text-border">|</span>

      <span className="font-mono text-[10px] text-muted-foreground">GPU</span>
      {gpuPct != null ? (
        <span className={`font-mono text-[10px] tabular-nums ${textColor(gpuPct)}`}>{gpuPct}%</span>
      ) : (
        <span className="font-mono text-[10px] text-muted-foreground">N/A</span>
      )}
    </div>
  );
}
