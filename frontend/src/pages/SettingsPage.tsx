import { useEffect, useState, useCallback } from 'react';
import {
  getApiKeys,
  updateApiKeys,
  testLlmConnection,
  testTranscriptionConnection,
} from '../api/client';
import type { ApiKeyStatus, ApiKeysResponse } from '../api/types';

/* ── Easing ── */
const EASE_SPRING = 'cubic-bezier(0.34, 1.56, 0.64, 1)';
const EASE_SMOOTH_OUT = 'cubic-bezier(0.22, 1, 0.36, 1)';
const EASE_SNAPPY = 'cubic-bezier(0.2, 0, 0, 1)';

/* ── LLM Provider Presets ── */
interface ProviderPreset {
  id: string;
  label: string;
  baseUrl: string;
  model: string;
  helpUrl: string;
  helpText: string;
}

const LLM_PRESETS: ProviderPreset[] = [
  {
    id: 'volcengine',
    label: '火山方舟',
    baseUrl: 'https://ark.cn-beijing.volces.com/api/coding/v3',
    model: 'doubao-seed-2.0-lite',
    helpUrl: 'https://console.volcengine.com/ark',
    helpText: '前往火山方舟控制台创建 API Key',
  },
  {
    id: 'openai',
    label: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini',
    helpUrl: 'https://platform.openai.com/api-keys',
    helpText: '前往 OpenAI 平台创建 API Key',
  },
  {
    id: 'deepseek',
    label: 'DeepSeek',
    baseUrl: 'https://api.deepseek.com/v1',
    model: 'deepseek-chat',
    helpUrl: 'https://platform.deepseek.com',
    helpText: '前往 DeepSeek 平台创建 API Key',
  },
  {
    id: 'custom',
    label: '自定义',
    baseUrl: '',
    model: '',
    helpUrl: '',
    helpText: '填入任意 OpenAI 兼容 API 的地址和模型名',
  },
];

const TRANSCRIPTION_HELP = {
  url: 'https://console.volcengine.com',
  text: '前往火山引擎控制台开通音视频字幕服务',
};

/* ── Component ── */

export default function SettingsPage() {
  // Data from server
  const [serverData, setServerData] = useState<ApiKeysResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state — editable values
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [selectedProvider, setSelectedProvider] = useState('volcengine');
  const [baseUrl, setBaseUrl] = useState('');
  const [model, setModel] = useState('');

  // Dirty tracking
  const [dirty, setDirty] = useState(false);

  // Visibility toggles for password fields
  const [visible, setVisible] = useState<Record<string, boolean>>({});

  // Save state
  const [saving, setSaving] = useState(false);
  const [saveResult, setSaveResult] = useState<{ ok: boolean; msg: string } | null>(null);

  // Test states
  const [llmTest, setLlmTest] = useState<{ loading: boolean; ok?: boolean; msg?: string }>({
    loading: false,
  });
  const [transcriptionTest, setTranscriptionTest] = useState<{
    loading: boolean;
    ok?: boolean;
    msg?: string;
  }>({ loading: false });

  // ── Load data ──
  const loadKeys = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getApiKeys();
      setServerData(data);

      // Detect current provider from base_url
      const matched = LLM_PRESETS.find((p) => p.baseUrl === data.llm_base_url);
      setSelectedProvider(matched?.id ?? 'custom');
      setBaseUrl(data.llm_base_url);
      setModel(data.llm_model);

      // Reset form values
      setFormValues({});
      setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载配置失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadKeys();
  }, [loadKeys]);

  // ── Unsaved changes prompt ──
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);


  // ── Handlers ──

  function handleFieldChange(keyName: string, value: string) {
    setFormValues((prev) => ({ ...prev, [keyName]: value }));
    setDirty(true);
  }

  function handleProviderChange(providerId: string) {
    const preset = LLM_PRESETS.find((p) => p.id === providerId)!;
    setSelectedProvider(providerId);
    if (providerId !== 'custom') {
      setBaseUrl(preset.baseUrl);
      setModel(preset.model);
    }
    setDirty(true);
  }

  function handleBaseUrlChange(value: string) {
    setBaseUrl(value);
    setDirty(true);
  }

  function handleModelChange(value: string) {
    setModel(value);
    setDirty(true);
  }

  function toggleVisibility(keyName: string) {
    setVisible((prev) => ({ ...prev, [keyName]: !prev[keyName] }));
  }

  // Get the effective value for a field (form override > server masked)
  function getDisplayValue(key: ApiKeyStatus): string {
    if (formValues[key.key_name] !== undefined) return formValues[key.key_name];
    return '';
  }

  function getPlaceholder(key: ApiKeyStatus): string {
    if (key.is_set) return key.masked_value;
    return key.required ? '必填' : '可选';
  }

  // ── Save ──
  async function handleSave() {
    setSaving(true);
    setSaveResult(null);
    try {
      const updates: { key_name: string; value: string }[] = [];

      // Collect changed API key fields
      for (const [keyName, value] of Object.entries(formValues)) {
        if (value !== '') {
          updates.push({ key_name: keyName, value });
        }
      }

      // Always send base_url and model if they differ from server
      if (serverData && baseUrl !== serverData.llm_base_url) {
        updates.push({ key_name: 'CLOUD_BASE_URL', value: baseUrl });
      }
      if (serverData && model !== serverData.llm_model) {
        updates.push({ key_name: 'CLOUD_MODEL', value: model });
      }

      if (updates.length === 0) {
        setSaveResult({ ok: false, msg: '没有需要保存的更改' });
        setSaving(false);
        return;
      }

      const data = await updateApiKeys(updates);
      setServerData(data);
      setFormValues({});
      setDirty(false);
      setSaveResult({ ok: true, msg: '配置已保存' });
    } catch (e) {
      setSaveResult({ ok: false, msg: e instanceof Error ? e.message : '保存失败' });
    } finally {
      setSaving(false);
    }
  }

  // ── Test LLM ──
  async function handleTestLlm() {
    setLlmTest({ loading: true });
    try {
      const apiKey = formValues['ARK_API_KEY'] || '';
      if (!apiKey && !serverData?.keys.find((k) => k.key_name === 'ARK_API_KEY')?.is_set) {
        setLlmTest({ loading: false, ok: false, msg: '请先填写 API Key' });
        return;
      }
      // If user hasn't entered a new key, we can't test (we don't have the real key)
      if (!apiKey) {
        setLlmTest({
          loading: false,
          ok: false,
          msg: '请重新输入 API Key 以测试连接（出于安全，已保存的密钥不会回传）',
        });
        return;
      }
      const result = await testLlmConnection({
        api_key: apiKey,
        base_url: baseUrl,
        model,
      });
      setLlmTest({ loading: false, ok: result.ok, msg: result.message });
    } catch (e) {
      setLlmTest({ loading: false, ok: false, msg: e instanceof Error ? e.message : '测试失败' });
    }
  }

  // ── Test Transcription ──
  async function handleTestTranscription() {
    setTranscriptionTest({ loading: true });
    const appid = formValues['VOLCENGINE_CAPTION_APPID'] || '';
    const token = formValues['VOLCENGINE_CAPTION_TOKEN'] || '';

    if (!appid && !serverData?.keys.find((k) => k.key_name === 'VOLCENGINE_CAPTION_APPID')?.is_set) {
      setTranscriptionTest({ loading: false, ok: false, msg: '请先填写 App ID' });
      return;
    }
    if (!token && !serverData?.keys.find((k) => k.key_name === 'VOLCENGINE_CAPTION_TOKEN')?.is_set) {
      setTranscriptionTest({ loading: false, ok: false, msg: '请先填写 Token' });
      return;
    }
    if (!appid || !token) {
      setTranscriptionTest({
        loading: false,
        ok: false,
        msg: '请重新输入 App ID 和 Token 以测试（出于安全，已保存的密钥不会回传）',
      });
      return;
    }

    try {
      const result = await testTranscriptionConnection({ appid, token });
      setTranscriptionTest({ loading: false, ok: result.ok, msg: result.message });
    } catch (e) {
      setTranscriptionTest({
        loading: false,
        ok: false,
        msg: e instanceof Error ? e.message : '测试失败',
      });
    }
  }

  const currentPreset = LLM_PRESETS.find((p) => p.id === selectedProvider)!;
  const llmKeys = serverData?.keys.filter((k) => k.group === 'llm' && k.key_name === 'ARK_API_KEY') ?? [];
  const transcriptionKeys = serverData?.keys.filter((k) => k.group === 'transcription') ?? [];

  /* ── Render ── */

  return (
    <div className="animate-fade-in-up mx-auto max-w-3xl px-6 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-display text-2xl font-bold tracking-tight text-text-primary">
          服务配置
        </h1>
        <p className="mt-2 text-sm text-text-muted">
          配置云端 API 以启用智能匹配和语音转录功能
        </p>
      </div>

      {/* Local mode info banner */}
      <div
        className="mb-8 rounded-xl border border-teal/15 bg-teal/[0.04] px-5 py-4"
        style={{ animation: `fadeInUp 0.4s ${EASE_SMOOTH_OUT} both 0.1s` }}
      >
        <div className="flex gap-3">
          <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-teal/10">
            <svg className="h-3.5 w-3.5 text-teal" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path strokeLinecap="round" d="M12 16v-4m0-4h.01" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium text-teal/90">不配置也可以使用</p>
            <p className="mt-1 text-xs text-text-muted leading-relaxed">
              工具会自动使用本地 Whisper 模型进行转录和匹配，无需联网。
              云端服务的优势：更快的处理速度和更高的准确率。
            </p>
          </div>
        </div>
      </div>

      {/* Save result toast */}
      {saveResult && (
        <div
          className={`mb-6 flex items-center gap-3 rounded-xl border px-5 py-3 ${
            saveResult.ok
              ? 'border-success/20 bg-success/5'
              : 'border-danger/20 bg-danger/5'
          }`}
          style={{ animation: `slideDown 0.35s ${EASE_SPRING} both` }}
        >
          {saveResult.ok ? (
            <svg className="h-5 w-5 shrink-0 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <svg className="h-5 w-5 shrink-0 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <circle cx="12" cy="12" r="10" />
              <path strokeLinecap="round" d="M12 8v4m0 4h.01" />
            </svg>
          )}
          <span className={`text-sm ${saveResult.ok ? 'text-success' : 'text-danger'}`}>
            {saveResult.msg}
          </span>
          <button
            className="ml-auto text-text-muted hover:text-text-primary"
            onClick={() => setSaveResult(null)}
            style={{ transition: `color 0.2s ${EASE_SNAPPY}` }}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-24">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber/30 border-t-amber" />
          <p className="mt-4 text-sm text-text-muted">正在加载配置信息...</p>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="rounded-xl border border-danger/20 bg-danger/5 px-5 py-4 text-center">
          <p className="text-sm text-danger">{error}</p>
          <button
            onClick={loadKeys}
            className="mt-3 rounded-lg bg-danger/10 px-4 py-1.5 text-xs font-medium text-danger hover:bg-danger/20"
            style={{ transition: `background-color 0.2s ${EASE_SNAPPY}` }}
          >
            重试
          </button>
        </div>
      )}

      {/* Main content */}
      {serverData && !loading && (
        <div className="space-y-6">

          {/* ═══════ LLM Section ═══════ */}
          <section
            className="rounded-2xl border border-border bg-surface overflow-hidden"
            style={{ animation: `fadeInUp 0.4s ${EASE_SMOOTH_OUT} both 0.15s` }}
          >
            {/* Section header */}
            <div className="border-b border-border-subtle bg-elevated/30 px-5 py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber/10">
                  <svg className="h-4 w-4 text-amber" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
                  </svg>
                </div>
                <div>
                  <h2 className="font-display text-sm font-semibold text-text-primary">
                    LLM 智能匹配服务
                  </h2>
                  <p className="text-xs text-text-muted">用于脚本匹配、SRT 分段和精剪决策</p>
                </div>
              </div>
            </div>

            <div className="space-y-5 px-5 py-5">
              {/* Provider selector */}
              <div>
                <label className="mb-2 block text-xs font-medium text-text-muted">供应商</label>
                <div className="flex gap-2">
                  {LLM_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      onClick={() => handleProviderChange(preset.id)}
                      className={`rounded-lg px-3.5 py-2 text-sm font-medium transition-all ${
                        selectedProvider === preset.id
                          ? 'bg-amber/15 text-amber border border-amber/30'
                          : 'bg-elevated text-text-secondary border border-border hover:border-amber/20 hover:text-text-primary'
                      }`}
                      style={{ transition: `all 0.2s ${EASE_SNAPPY}` }}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* API Key */}
              {llmKeys.map((key) => (
                <KeyInput
                  key={key.key_name}
                  keyStatus={key}
                  value={getDisplayValue(key)}
                  placeholder={getPlaceholder(key)}
                  isVisible={visible[key.key_name] ?? false}
                  onChange={(v) => handleFieldChange(key.key_name, v)}
                  onToggleVisibility={() => toggleVisibility(key.key_name)}
                />
              ))}

              {/* Base URL */}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-text-muted">
                  Base URL
                </label>
                <input
                  type="text"
                  value={baseUrl}
                  onChange={(e) => handleBaseUrlChange(e.target.value)}
                  placeholder={selectedProvider === 'custom' ? '输入 API 地址' : currentPreset.baseUrl}
                  className="w-full rounded-lg border border-border bg-elevated px-3.5 py-2.5 font-mono text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-amber/40 focus:ring-1 focus:ring-amber/20 transition-colors"
                />
              </div>

              {/* Model */}
              <div>
                <label className="mb-1.5 block text-xs font-medium text-text-muted">
                  模型名称
                </label>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => handleModelChange(e.target.value)}
                  placeholder={selectedProvider === 'custom' ? '输入模型标识符' : currentPreset.model}
                  className="w-full rounded-lg border border-border bg-elevated px-3.5 py-2.5 font-mono text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-amber/40 focus:ring-1 focus:ring-amber/20 transition-colors"
                />
              </div>

              {/* Help link + Test button */}
              <div className="flex items-center justify-between pt-1">
                {currentPreset.helpUrl ? (
                  <a
                    href={currentPreset.helpUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs text-text-muted hover:text-amber transition-colors"
                  >
                    <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                    </svg>
                    {currentPreset.helpText}
                  </a>
                ) : (
                  <span className="text-xs text-text-muted">{currentPreset.helpText}</span>
                )}

                <TestButton
                  loading={llmTest.loading}
                  ok={llmTest.ok}
                  message={llmTest.msg}
                  onClick={handleTestLlm}
                />
              </div>
            </div>
          </section>

          {/* ═══════ Transcription Section ═══════ */}
          <section
            className="rounded-2xl border border-border bg-surface overflow-hidden"
            style={{ animation: `fadeInUp 0.4s ${EASE_SMOOTH_OUT} both 0.25s` }}
          >
            {/* Section header */}
            <div className="border-b border-border-subtle bg-elevated/30 px-5 py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal/10">
                  <svg className="h-4 w-4 text-teal" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
                  </svg>
                </div>
                <div>
                  <h2 className="font-display text-sm font-semibold text-text-primary">
                    语音转录服务
                  </h2>
                  <p className="text-xs text-text-muted">火山引擎音视频字幕 — 云端语音识别与时间戳对齐</p>
                </div>
              </div>
            </div>

            <div className="space-y-5 px-5 py-5">
              {transcriptionKeys.map((key) => (
                <KeyInput
                  key={key.key_name}
                  keyStatus={key}
                  value={getDisplayValue(key)}
                  placeholder={getPlaceholder(key)}
                  isVisible={visible[key.key_name] ?? false}
                  onChange={(v) => handleFieldChange(key.key_name, v)}
                  onToggleVisibility={() => toggleVisibility(key.key_name)}
                />
              ))}

              {/* Help link + Test button */}
              <div className="flex items-center justify-between pt-1">
                <a
                  href={TRANSCRIPTION_HELP.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs text-text-muted hover:text-teal transition-colors"
                >
                  <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                  </svg>
                  {TRANSCRIPTION_HELP.text}
                </a>

                <TestButton
                  loading={transcriptionTest.loading}
                  ok={transcriptionTest.ok}
                  message={transcriptionTest.msg}
                  onClick={handleTestTranscription}
                />
              </div>
            </div>
          </section>

          {/* ═══════ Save button ═══════ */}
          <div
            className="flex justify-end pt-2"
            style={{ animation: `fadeInUp 0.4s ${EASE_SMOOTH_OUT} both 0.35s` }}
          >
            <button
              onClick={handleSave}
              disabled={saving || !dirty}
              className="rounded-xl bg-amber px-8 py-3 text-sm font-semibold text-deep hover:bg-amber/90 disabled:bg-elevated disabled:text-text-muted transition-all"
              style={{ transition: `all 0.25s ${EASE_SNAPPY}` }}
            >
              {saving ? (
                <span className="inline-flex items-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-deep/30 border-t-deep" />
                  保存中...
                </span>
              ) : (
                '保存配置'
              )}
            </button>
          </div>
        </div>
      )}

      {/* Keyframe styles */}
      <style>{`
        @keyframes slideDown {
          from { opacity: 0; transform: translateY(-8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(16px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

/* ═════════════════════════════════════════
   Key Input Field
   ═════════════════════════════════════════ */

interface KeyInputProps {
  keyStatus: ApiKeyStatus;
  value: string;
  placeholder: string;
  isVisible: boolean;
  onChange: (value: string) => void;
  onToggleVisibility: () => void;
}

function KeyInput({ keyStatus, value, placeholder, isVisible, onChange, onToggleVisibility }: KeyInputProps) {
  const isSecret = ['ARK_API_KEY', 'VOLCENGINE_CAPTION_TOKEN'].includes(keyStatus.key_name);

  return (
    <div>
      <div className="mb-1.5 flex items-center gap-2">
        <label className="text-xs font-medium text-text-muted">
          {keyStatus.display_name}
        </label>
        {keyStatus.required && !keyStatus.is_set && value === '' && (
          <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium text-warning bg-warning/10">
            必填
          </span>
        )}
        {!keyStatus.required && (
          <span className="text-[10px] text-text-faint">可选</span>
        )}
        {keyStatus.is_set && value === '' && (
          <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium text-success bg-success/10">
            已配置
          </span>
        )}
      </div>
      <div className="relative">
        <input
          type={isSecret && !isVisible ? 'password' : 'text'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-lg border border-border bg-elevated px-3.5 py-2.5 pr-10 font-mono text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-amber/40 focus:ring-1 focus:ring-amber/20 transition-colors"
        />
        {isSecret && (
          <button
            type="button"
            onClick={onToggleVisibility}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors"
          >
            {isVisible ? (
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
              </svg>
            ) : (
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            )}
          </button>
        )}
      </div>
      <p className="mt-1 text-[11px] text-text-faint">{keyStatus.description}</p>
    </div>
  );
}

/* ═════════════════════════════════════════
   Test Connection Button
   ═════════════════════════════════════════ */

interface TestButtonProps {
  loading: boolean;
  ok?: boolean;
  message?: string;
  onClick: () => void;
}

function TestButton({ loading, ok, message, onClick }: TestButtonProps) {
  return (
    <div className="flex items-center gap-3">
      {message && !loading && (
        <span
          className={`text-xs ${ok ? 'text-success' : 'text-danger'}`}
          style={{ animation: `fadeInUp 0.25s ${EASE_SPRING} both` }}
        >
          {message}
        </span>
      )}
      <button
        onClick={onClick}
        disabled={loading}
        className="inline-flex items-center gap-2 rounded-lg border border-border bg-elevated px-3.5 py-2 text-xs font-medium text-text-secondary hover:border-amber/30 hover:text-text-primary disabled:opacity-60 transition-all"
        style={{ transition: `all 0.2s ${EASE_SNAPPY}` }}
      >
        {loading ? (
          <>
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-text-muted/30 border-t-text-muted" />
            测试中...
          </>
        ) : ok === true ? (
          <>
            <svg className="h-3.5 w-3.5 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            测试连接
          </>
        ) : ok === false ? (
          <>
            <svg className="h-3.5 w-3.5 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
            测试连接
          </>
        ) : (
          <>
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" />
            </svg>
            测试连接
          </>
        )}
      </button>
    </div>
  );
}
