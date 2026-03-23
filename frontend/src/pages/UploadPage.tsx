import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Upload, Cloud, Monitor, FileText, AlertTriangle, Loader2 } from 'lucide-react';
import PageContainer from '../components/layout/PageContainer';
import Stepper from '../components/layout/Stepper';
import FileDropZone from '../components/upload/FileDropZone';
import { uploadJob, getHealthStatus } from '../api/client';
import { useJobStore } from '../stores/jobStore';
import { Alert, AlertTitle, AlertDescription, AlertAction } from '@/components/ui/alert';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';

export default function UploadPage() {
  const navigate = useNavigate();
  const addJob = useJobStore((s) => s.addJob);

  const [scriptFile, setScriptFile] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [provider, setProvider] = useState<'local' | 'cloud'>('cloud');
  const [scriptPreview, setScriptPreview] = useState<string>('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showConfigBanner, setShowConfigBanner] = useState(false);

  useEffect(() => {
    getHealthStatus()
      .then((health) => {
        if (!health.has_api_key && !health.has_caption_keys) {
          setShowConfigBanner(true);
        }
      })
      .catch(() => {});
  }, []);

  function handleScriptFile(file: File) {
    setScriptFile(file);
    const reader = new FileReader();
    reader.onload = () => {
      setScriptPreview(reader.result as string);
    };
    reader.readAsText(file);
  }

  async function handleStart() {
    if (!scriptFile || !audioFile) return;
    setUploading(true);
    setError(null);
    try {
      const result = await uploadJob(scriptFile, audioFile, provider);
      // Add job to multi-job store (does NOT destroy existing jobs)
      addJob(result.id, scriptFile.name, audioFile.name);
      navigate(`/processing/${result.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传失败');
    } finally {
      setUploading(false);
    }
  }

  return (
    <>
      <Stepper currentStep={0} />
      <PageContainer>
        {/* Cloud config banner */}
        {showConfigBanner && (
          <Alert className="mb-6 animate-fade-in-up">
            <AlertTriangle className="size-4 text-warning" />
            <AlertTitle>尚未配置云端服务</AlertTitle>
            <AlertDescription>
              前往「服务配置」填写 API 密钥以启用云端匹配和转录功能，获得更快速度和更高准确率。当前将使用本地模型处理。
            </AlertDescription>
            <AlertAction>
              <Button variant="outline" size="sm" asChild>
                <Link to="/settings">前往配置 &rarr;</Link>
              </Button>
            </AlertAction>
          </Alert>
        )}

        {/* Hero heading */}
        <div className="mb-10 text-center animate-fade-in-up">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            上传文件
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">
            上传编导脚本和音频文件，开始智能粗剪
          </p>
        </div>

        {/* Drop zones */}
        <div className="grid gap-6 md:grid-cols-2 animate-fade-in-up delay-1">
          <FileDropZone
            accept=".md,.markdown,.txt"
            label="脚本文件（.md / .txt）"
            file={scriptFile}
            onFile={handleScriptFile}
            icon={<FileText className="h-7 w-7" />}
          />

          <FileDropZone
            accept=".mp3,.wav,.m4a"
            label="音频文件（.mp3 / .wav / .m4a）"
            file={audioFile}
            onFile={setAudioFile}
            icon={<Upload className="h-7 w-7" />}
          />
        </div>

        {/* Script preview */}
        {scriptPreview && (
          <Card className="mt-6 animate-slide-down">
            <CardContent>
              <h3 className="mb-3 text-sm font-semibold text-muted-foreground">脚本预览</h3>
              <div className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded-lg bg-muted p-4 text-sm text-muted-foreground leading-relaxed">
                {scriptPreview}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Provider selection */}
        <Card className="mt-6 animate-fade-in-up delay-2">
          <CardContent>
            <h3 className="mb-4 text-sm font-semibold text-muted-foreground">转录引擎</h3>
            <RadioGroup
              value={provider}
              onValueChange={(val) => setProvider(val as 'local' | 'cloud')}
              className="grid gap-4 md:grid-cols-2"
            >
              <label
                className={`group flex cursor-pointer items-center gap-4 rounded-xl border p-4 transition-all duration-200 ${
                  provider === 'cloud'
                    ? 'border-border bg-accent shadow-sm'
                    : 'border-border/50 hover:border-border hover:bg-accent/50'
                }`}
              >
                <RadioGroupItem value="cloud" className="sr-only" />
                <div className={`flex h-10 w-10 items-center justify-center rounded-xl transition-colors ${
                  provider === 'cloud' ? 'bg-primary/10 text-foreground' : 'bg-muted text-muted-foreground'
                }`}>
                  <Cloud className="h-5 w-5" />
                </div>
                <div className="flex-1">
                  <p className={`text-sm font-medium transition-colors ${provider === 'cloud' ? 'text-foreground font-semibold' : 'text-foreground'}`}>
                    云端模型（Seed 2.0 Lite）
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">速度快，精度高，需要网络</p>
                </div>
                {provider === 'cloud' && (
                  <div className="ml-auto h-2 w-2 rounded-full bg-primary animate-pulse" />
                )}
              </label>

              <label
                className={`group flex cursor-pointer items-center gap-4 rounded-xl border p-4 transition-all duration-200 ${
                  provider === 'local'
                    ? 'border-border bg-accent shadow-sm'
                    : 'border-border/50 hover:border-border hover:bg-accent/50'
                }`}
              >
                <RadioGroupItem value="local" className="sr-only" />
                <div className={`flex h-10 w-10 items-center justify-center rounded-xl transition-colors ${
                  provider === 'local' ? 'bg-primary/10 text-foreground' : 'bg-muted text-muted-foreground'
                }`}>
                  <Monitor className="h-5 w-5" />
                </div>
                <div className="flex-1">
                  <p className={`text-sm font-medium transition-colors ${provider === 'local' ? 'text-foreground font-semibold' : 'text-foreground'}`}>
                    本地模型
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">离线可用，速度取决于硬件</p>
                </div>
                {provider === 'local' && (
                  <div className="ml-auto h-2 w-2 rounded-full bg-primary animate-pulse" />
                )}
              </label>
            </RadioGroup>
            <p className="mt-3 text-xs text-muted-foreground">推荐使用云端模型，速度更快且精度更高</p>
          </CardContent>
        </Card>

        {/* Error message */}
        {error && (
          <Alert variant="destructive" className="mt-4 animate-slide-down">
            <AlertTriangle className="size-4" />
            <AlertTitle>上传失败</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Start button */}
        <div className="mt-10 flex justify-center animate-fade-in-up delay-3">
          <Button
            onClick={handleStart}
            disabled={!scriptFile || !audioFile || uploading}
            size="lg"
            className="px-12 py-3.5 text-base font-semibold tracking-wide rounded-2xl h-auto"
          >
            {uploading ? (
              <span className="flex items-center gap-2.5">
                <Loader2 className="h-5 w-5 animate-spin" />
                上传中...
              </span>
            ) : (
              <>
                开始处理
                <span className="ml-2 inline-block transition-transform group-hover/button:translate-x-1">&rarr;</span>
              </>
            )}
          </Button>
        </div>
      </PageContainer>
    </>
  );
}
