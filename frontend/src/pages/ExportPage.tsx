import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import PageContainer from '../components/layout/PageContainer';
import Stepper from '../components/layout/Stepper';
import { exportJob, downloadExportFile } from '../api/client';
import { useJobStore } from '../stores/jobStore';
import type { ExportRequest } from '../api/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import {
  ArrowLeft,
  Download,
  Loader2,
  CheckCircle2,
  FileText,
  Film,
  Subtitles,
  Info,
} from 'lucide-react';

const FRAME_RATES = [23.976, 24, 25, 29.97, 30];

const FORMAT_INFO: Record<string, { label: string; desc: string; icon: typeof FileText }> = {
  edl: { label: 'EDL', desc: '适用于 Premiere、DaVinci Resolve', icon: FileText },
  fcpxml: { label: 'FCPXML', desc: '适用于 Final Cut Pro、剪映', icon: Film },
  srt: { label: 'SRT', desc: '字幕文件，可导入任何播放器', icon: Subtitles },
};

export default function ExportPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
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
      await exportJob(id, {
        formats: selectedFormats as Array<'edl' | 'fcpxml' | 'srt'>,
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
        <div className="mb-10 text-center">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/review/${id}`)}
            className="mb-4 text-muted-foreground"
          >
            <ArrowLeft className="size-3.5" />
            返回审核
          </Button>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">导出</h1>
          <p className="mt-3 text-sm text-muted-foreground">选择格式和参数，导出剪辑文件</p>
        </div>

        <div className="mx-auto max-w-lg space-y-5">
          {/* Format selection */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-muted-foreground">导出格式</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-3">
                {(['edl', 'fcpxml', 'srt'] as const).map((f) => {
                  const Icon = FORMAT_INFO[f].icon;
                  return (
                    <button
                      key={f}
                      onClick={() => toggleFormat(f)}
                      className={`flex flex-col items-center gap-2 rounded-lg border-2 p-4 text-center transition-all ${
                        formats[f]
                          ? 'border-primary bg-primary/5'
                          : 'border-border hover:border-border hover:bg-accent'
                      }`}
                    >
                      <Icon className={`size-4 ${formats[f] ? 'text-foreground' : 'text-muted-foreground'}`} />
                      <span className={`text-sm font-semibold ${formats[f] ? 'text-foreground' : 'text-foreground'}`}>
                        {FORMAT_INFO[f].label}
                      </span>
                      <span className="text-[10px] text-muted-foreground">{FORMAT_INFO[f].desc}</span>
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* Frame rate */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-muted-foreground">帧率</CardTitle>
            </CardHeader>
            <CardContent>
              <RadioGroup
                value={String(frameRate)}
                onValueChange={(v) => setFrameRate(parseFloat(v))}
                className="flex gap-2"
              >
                {FRAME_RATES.map((fr) => (
                  <Label
                    key={fr}
                    htmlFor={`fr-${fr}`}
                    className={`flex flex-1 cursor-pointer items-center justify-center rounded-lg border-2 py-2.5 font-mono text-sm transition-all ${
                      frameRate === fr
                        ? 'border-primary bg-primary/5 font-medium text-foreground'
                        : 'border-border text-muted-foreground hover:bg-accent'
                    }`}
                  >
                    <RadioGroupItem value={String(fr)} id={`fr-${fr}`} className="sr-only" />
                    {fr}
                  </Label>
                ))}
              </RadioGroup>
              <p className="text-xs text-muted-foreground mt-2">不确定？大多数视频使用 30 或 25 帧率</p>
            </CardContent>
          </Card>

          {/* Buffer duration */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-baseline justify-between">
                <CardTitle className="text-sm font-semibold text-muted-foreground">缓冲时长（防误切）</CardTitle>
                <span className="font-mono text-sm font-medium text-foreground">{buffer.toFixed(2)}s</span>
              </div>
            </CardHeader>
            <CardContent>
              <Slider
                min={0}
                max={0.5}
                step={0.01}
                value={[buffer]}
                onValueChange={([v]) => setBuffer(v)}
              />
              <div className="mt-2 flex justify-between font-mono text-[10px] text-muted-foreground/50">
                <span>0s</span>
                <span>0.5s</span>
              </div>
              <p className="text-xs text-muted-foreground mt-2">在每段前后保留少量余量，方便后续微调</p>
            </CardContent>
          </Card>

          {/* Subtitle source */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-muted-foreground">字幕文字来源</CardTitle>
            </CardHeader>
            <CardContent>
              <RadioGroup
                value={subtitleSource}
                onValueChange={(v) => setSubtitleSource(v as ExportRequest['subtitleSource'])}
                className="grid grid-cols-3 gap-3"
              >
                {subtitleOptions.map((opt) => (
                  <Label
                    key={opt.value}
                    htmlFor={`sub-${opt.value}`}
                    className={`flex cursor-pointer flex-col items-center gap-1 rounded-lg border-2 p-3 text-center transition-all ${
                      subtitleSource === opt.value
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:bg-accent'
                    }`}
                  >
                    <RadioGroupItem value={opt.value} id={`sub-${opt.value}`} className="sr-only" />
                    <span className={`text-sm font-medium ${subtitleSource === opt.value ? 'text-foreground' : 'text-foreground'}`}>
                      {opt.label}
                    </span>
                    <span className="text-[10px] text-muted-foreground">{opt.desc}</span>
                  </Label>
                ))}
              </RadioGroup>
            </CardContent>
          </Card>

          {/* Video filename - auto-derived, shown as info only */}
          {defaultVideoFilename && (
            <Card>
              <CardContent className="py-3">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Info className="size-3.5" />
                    导出后链接的视频文件
                  </span>
                  <span className="font-mono text-xs text-muted-foreground">{defaultVideoFilename}</span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Error */}
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Export button */}
          <Button
            onClick={handleExport}
            disabled={exporting}
            className="w-full h-11 text-base"
            size="lg"
          >
            {exporting ? (
              <span className="flex items-center justify-center gap-2.5">
                <Loader2 className="size-5 animate-spin" />
                导出中...
              </span>
            ) : (
              '导出文件'
            )}
          </Button>

          {/* Download links */}
          {readyFormats.length > 0 && (
            <Alert className="border-success/20 bg-success/5">
              <CheckCircle2 className="size-4 text-success" />
              <AlertDescription>
                <h3 className="mb-3 text-sm font-semibold text-success">导出完成</h3>
                <div className="flex flex-col gap-2">
                  {readyFormats.map((format) => (
                    <Button
                      key={format}
                      variant="outline"
                      onClick={() => handleDownload(format)}
                      disabled={downloading === format}
                      className="justify-start gap-3"
                    >
                      <Download className="size-4 text-success" />
                      {downloading === format ? '下载中...' : `下载 ${format.toUpperCase()} 文件`}
                    </Button>
                  ))}
                </div>
              </AlertDescription>
            </Alert>
          )}
        </div>
      </PageContainer>
    </>
  );
}
