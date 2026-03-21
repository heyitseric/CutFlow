import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageContainer from '../components/layout/PageContainer';
import Stepper from '../components/layout/Stepper';
import FileDropZone from '../components/upload/FileDropZone';
import { uploadJob } from '../api/client';
import { useJobStore } from '../stores/jobStore';

export default function UploadPage() {
  const navigate = useNavigate();
  const addJob = useJobStore((s) => s.addJob);

  const [scriptFile, setScriptFile] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [provider, setProvider] = useState<'local' | 'cloud'>('cloud');
  const [scriptPreview, setScriptPreview] = useState<string>('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        {/* Hero heading */}
        <div className="mb-10 text-center animate-fade-in-up">
          <h1 className="font-display text-3xl font-bold tracking-tight text-text-primary">
            上传文件
          </h1>
          <p className="mt-3 text-sm text-text-secondary">
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
            icon={
              <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
            }
          />

          <FileDropZone
            accept=".mp3,.wav,.m4a"
            label="音频文件（.mp3 / .wav / .m4a）"
            file={audioFile}
            onFile={setAudioFile}
            icon={
              <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z" />
              </svg>
            }
          />
        </div>

        {/* Script preview */}
        {scriptPreview && (
          <div className="mt-6 animate-slide-down rounded-2xl border border-border bg-surface p-5">
            <h3 className="mb-3 font-display text-sm font-semibold text-text-secondary">脚本预览</h3>
            <div className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded-lg bg-base p-4 text-sm text-text-secondary leading-relaxed">
              {scriptPreview}
            </div>
          </div>
        )}

        {/* Provider selection */}
        <div className="mt-6 animate-fade-in-up delay-2 rounded-2xl border border-border bg-surface p-5">
          <h3 className="mb-4 font-display text-sm font-semibold text-text-secondary">转录引擎</h3>
          <div className="grid gap-4 md:grid-cols-2">
            <label
              className={`group flex cursor-pointer items-center gap-4 rounded-xl border-2 p-4 transition-all duration-300 transition-cinematic ${
                provider === 'cloud'
                  ? 'border-amber/40 bg-amber-glow'
                  : 'border-border hover:border-border hover:bg-elevated'
              }`}
            >
              <input
                type="radio"
                name="provider"
                value="cloud"
                checked={provider === 'cloud'}
                onChange={() => setProvider('cloud')}
                className="sr-only"
              />
              <div className={`flex h-10 w-10 items-center justify-center rounded-xl transition-colors transition-smooth ${
                provider === 'cloud' ? 'bg-amber/15 text-amber' : 'bg-elevated text-text-muted'
              }`}>
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
                </svg>
              </div>
              <div>
                <p className={`text-sm font-medium transition-colors transition-smooth ${provider === 'cloud' ? 'text-amber' : 'text-text-primary'}`}>
                  云端模型（Seed 2.0 Lite）
                </p>
                <p className="mt-0.5 text-xs text-text-muted">速度快，精度高，需要网络</p>
              </div>
              {provider === 'cloud' && (
                <div className="ml-auto h-2 w-2 rounded-full bg-amber animate-gentle-pulse" />
              )}
            </label>

            <label
              className={`group flex cursor-pointer items-center gap-4 rounded-xl border-2 p-4 transition-all duration-300 transition-cinematic ${
                provider === 'local'
                  ? 'border-teal/40 bg-teal-glow'
                  : 'border-border hover:border-border hover:bg-elevated'
              }`}
            >
              <input
                type="radio"
                name="provider"
                value="local"
                checked={provider === 'local'}
                onChange={() => setProvider('local')}
                className="sr-only"
              />
              <div className={`flex h-10 w-10 items-center justify-center rounded-xl transition-colors transition-smooth ${
                provider === 'local' ? 'bg-teal/15 text-teal' : 'bg-elevated text-text-muted'
              }`}>
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0V12a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 12V5.25" />
                </svg>
              </div>
              <div>
                <p className={`text-sm font-medium transition-colors transition-smooth ${provider === 'local' ? 'text-teal' : 'text-text-primary'}`}>
                  本地模型
                </p>
                <p className="mt-0.5 text-xs text-text-muted">离线可用，速度取决于硬件</p>
              </div>
              {provider === 'local' && (
                <div className="ml-auto h-2 w-2 rounded-full bg-teal animate-gentle-pulse" />
              )}
            </label>
          </div>
          <p className="mt-3 text-xs text-text-muted">推荐使用云端模型，速度更快且精度更高</p>
        </div>

        {/* Error message */}
        {error && (
          <div className="mt-4 animate-slide-down rounded-xl border border-danger/20 bg-danger-surface p-4 text-sm text-danger">
            {error}
          </div>
        )}

        {/* Start button */}
        <div className="mt-10 flex justify-center animate-fade-in-up delay-3">
          <button
            onClick={handleStart}
            disabled={!scriptFile || !audioFile || uploading}
            className={`
              group relative overflow-hidden rounded-2xl px-12 py-3.5
              font-display text-base font-semibold tracking-wide
              transition-all duration-300 transition-cinematic transition-spring
              ${!scriptFile || !audioFile || uploading
                ? 'bg-elevated text-text-muted cursor-not-allowed'
                : 'bg-amber text-deep hover:bg-amber/90 hover:shadow-lg hover:shadow-amber/20 active:scale-[0.98]'
              }
            `}
          >
            {uploading ? (
              <span className="flex items-center gap-2.5">
                <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                上传中...
              </span>
            ) : (
              <>
                开始处理
                <span className="ml-2 inline-block transition-transform transition-spring group-hover:translate-x-1">→</span>
              </>
            )}
          </button>
        </div>
      </PageContainer>
    </>
  );
}
