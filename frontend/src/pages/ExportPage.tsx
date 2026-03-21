import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import PageContainer from '../components/layout/PageContainer';
import Stepper from '../components/layout/Stepper';
import { exportJob, downloadExportFile } from '../api/client';
import { useJobStore } from '../stores/jobStore';
import type { ExportRequest } from '../api/types';

const FRAME_RATES = [23.976, 24, 25, 29.97, 30];

const FORMAT_INFO: Record<string, { label: string; desc: string }> = {
  edl: { label: 'EDL', desc: 'Premiere / Resolve' },
  fcpxml: { label: 'FCPXML', desc: 'Final Cut Pro' },
  srt: { label: 'SRT', desc: '通用字幕' },
};

export default function ExportPage() {
  const { id } = useParams<{ id: string }>();
  const setActiveJob = useJobStore((s) => s.setActiveJob);
  const audioName = useJobStore((s) => (id && s.jobs[id]) ? s.jobs[id].audioName : '');
  const scriptName = useJobStore((s) => (id && s.jobs[id]) ? s.jobs[id].scriptName : '');

  useEffect(() => {
    if (id) setActiveJob(id);
  }, [id, setActiveJob]);

  // Derive default video filename from audio filename (e.g. "110-audio.mp3" -> "110-audio.mp4")
  const defaultVideoFilename = audioName
    ? audioName.replace(/\.[^.]+$/, '.mp4')
    : '';

  const [formats, setFormats] = useState({ edl: true, fcpxml: true, srt: true });
  const [frameRate, setFrameRate] = useState(25);
  const [buffer, setBuffer] = useState(0.15);
  const [subtitleSource, setSubtitleSource] = useState<ExportRequest['subtitleSource']>('script');
  const [exporting, setExporting] = useState(false);
  const [readyFormats, setReadyFormats] = useState<string[]>([]);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function toggleFormat(f: keyof typeof formats) {
    setFormats((prev) => ({ ...prev, [f]: !prev[f] }));
  }

  async function handleExport() {
    if (!id) return;
    setExporting(true);
    setError(null);
    setReadyFormats([]);

    const selectedFormats = Object.entries(formats)
      .filter(([, v]) => v)
      .map(([k]) => k);

    if (selectedFormats.length === 0) {
      setError('请至少选择一种格式');
      setExporting(false);
      return;
    }

    // Auto-derive video filename from audio filename
    const finalVideoFilename = defaultVideoFilename || 'video.mp4';

    try {
      // Always generate all formats — they're small text files.
      // The user only downloads the ones they selected.
      await exportJob(id, {
        format: 'all',
        frameRate,
        bufferDuration: buffer,
        subtitleSource,
        videoFilename: finalVideoFilename,
      });
      setReadyFormats(selectedFormats);
    } catch (err) {
      setError(err instanceof Error ? err.message : '导出失败');
    } finally {
      setExporting(false);
    }
  }

  async function handleDownload(format: string) {
    if (!id) return;
    setDownloading(format);
    try {
      await downloadExportFile(id, format, scriptName || undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : '下载失败');
    } finally {
      setDownloading(null);
    }
  }

  const subtitleOptions: { value: ExportRequest['subtitleSource']; label: string; desc: string }[] = [
    { value: 'script', label: '脚本文字', desc: '编导校对版' },
    { value: 'transcript', label: '转录文字', desc: '与音频同步' },
    { value: 'llm_corrected', label: 'LLM 校对', desc: '智能纠错版' },
  ];

  return (
    <>
      <Stepper currentStep={3} jobId={id} />
      <PageContainer>
        <div className="mb-10 text-center animate-fade-in-up">
          <h1 className="font-display text-3xl font-bold tracking-tight text-text-primary">导出</h1>
          <p className="mt-3 text-sm text-text-secondary">选择格式和参数，导出剪辑文件</p>
        </div>

        <div className="mx-auto max-w-lg space-y-5">
          {/* Format selection */}
          <div className="animate-fade-in-up delay-1 rounded-2xl border border-border bg-surface p-5">
            <h3 className="mb-4 font-display text-sm font-semibold text-text-secondary">导出格式</h3>
            <div className="grid grid-cols-3 gap-3">
              {(['edl', 'fcpxml', 'srt'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => toggleFormat(f)}
                  className={`flex flex-col items-center gap-1 rounded-xl border-2 p-4 text-center transition-all duration-300 ${
                    formats[f]
                      ? 'border-amber/40 bg-amber-glow'
                      : 'border-border hover:border-border hover:bg-elevated'
                  }`}
                >
                  <span className={`font-display text-sm font-semibold ${formats[f] ? 'text-amber' : 'text-text-primary'}`}>
                    {FORMAT_INFO[f].label}
                  </span>
                  <span className="text-[10px] text-text-muted">{FORMAT_INFO[f].desc}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Frame rate */}
          <div className="animate-fade-in-up delay-2 rounded-2xl border border-border bg-surface p-5">
            <h3 className="mb-4 font-display text-sm font-semibold text-text-secondary">帧率</h3>
            <div className="flex gap-2">
              {FRAME_RATES.map((fr) => (
                <button
                  key={fr}
                  onClick={() => setFrameRate(fr)}
                  className={`flex-1 rounded-xl border-2 py-2.5 font-mono text-sm transition-all duration-300 ${
                    frameRate === fr
                      ? 'border-amber/40 bg-amber-glow text-amber font-medium'
                      : 'border-border text-text-muted hover:border-border hover:bg-elevated'
                  }`}
                >
                  {fr}
                </button>
              ))}
            </div>
          </div>

          {/* Buffer duration */}
          <div className="animate-fade-in-up delay-3 rounded-2xl border border-border bg-surface p-5">
            <div className="mb-4 flex items-baseline justify-between">
              <h3 className="font-display text-sm font-semibold text-text-secondary">缓冲时长</h3>
              <span className="font-mono text-sm text-amber">{buffer.toFixed(2)}s</span>
            </div>
            <input
              type="range"
              min="0"
              max="0.5"
              step="0.01"
              value={buffer}
              onChange={(e) => setBuffer(parseFloat(e.target.value))}
              className="w-full"
            />
            <div className="mt-2 flex justify-between font-mono text-[10px] text-text-faint">
              <span>0s</span>
              <span>0.5s</span>
            </div>
          </div>

          {/* Subtitle source */}
          <div className="animate-fade-in-up delay-4 rounded-2xl border border-border bg-surface p-5">
            <h3 className="mb-4 font-display text-sm font-semibold text-text-secondary">字幕文字来源</h3>
            <div className="grid grid-cols-3 gap-3">
              {subtitleOptions.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setSubtitleSource(opt.value)}
                  className={`flex flex-col items-center gap-1 rounded-xl border-2 p-3 text-center transition-all duration-300 ${
                    subtitleSource === opt.value
                      ? 'border-teal/40 bg-teal-glow'
                      : 'border-border hover:border-border hover:bg-elevated'
                  }`}
                >
                  <span className={`text-sm font-medium ${subtitleSource === opt.value ? 'text-teal' : 'text-text-primary'}`}>
                    {opt.label}
                  </span>
                  <span className="text-[10px] text-text-muted">{opt.desc}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Video filename - auto-derived, shown as info only */}
          {defaultVideoFilename && (
            <div className="animate-fade-in-up delay-5 rounded-2xl border border-border bg-surface p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs text-text-muted">导出后链接的视频文件</span>
                <span className="font-mono text-xs text-text-secondary">{defaultVideoFilename}</span>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="animate-slide-down rounded-xl border border-danger/20 bg-danger-surface p-4 text-sm text-danger">
              {error}
            </div>
          )}

          {/* Export button */}
          <button
            onClick={handleExport}
            disabled={exporting}
            className={`w-full rounded-2xl py-3.5 font-display text-base font-semibold tracking-wide transition-all duration-300 ${
              exporting
                ? 'bg-elevated text-text-muted cursor-not-allowed'
                : 'bg-amber text-deep hover:bg-amber/90 hover:shadow-lg hover:shadow-amber/20 active:scale-[0.98]'
            }`}
          >
            {exporting ? (
              <span className="flex items-center justify-center gap-2.5">
                <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                导出中...
              </span>
            ) : (
              '导出文件'
            )}
          </button>

          {/* Download links */}
          {readyFormats.length > 0 && (
            <div className="animate-slide-down rounded-2xl border border-success/20 bg-success-surface p-5">
              <h3 className="mb-3 font-display text-sm font-semibold text-success">导出完成</h3>
              <div className="flex flex-col gap-2">
                {readyFormats.map((format) => (
                  <button
                    key={format}
                    onClick={() => handleDownload(format)}
                    disabled={downloading === format}
                    className="flex items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3 text-sm font-medium text-text-primary hover:bg-elevated transition-colors disabled:opacity-50"
                  >
                    <svg className="h-4 w-4 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    {downloading === format ? '下载中...' : `下载 ${format.toUpperCase()} 文件`}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </PageContainer>
    </>
  );
}
