import { useEffect, useState, useCallback } from 'react';
import {
  getApiKeys,
  updateApiKeys,
  testLlmConnection,
  testTranscriptionConnection,
} from '../api/client';
import type { ApiKeyStatus, ApiKeysResponse } from '../api/types';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import {
  Loader2,
  Eye,
  EyeOff,
  ExternalLink,
  Sparkles,
  Mic,
  Info,
  Plug,
  Check,
  X as XIcon,
  AlertCircle,
} from 'lucide-react';

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
        toast.info('没有需要保存的更改');
        setSaving(false);
        return;
      }

      const data = await updateApiKeys(updates);
      setServerData(data);
      setFormValues({});
      setDirty(false);
      toast.success('配置已保存');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '保存失败');
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
    <div className="mx-auto max-w-3xl px-6 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          服务配置
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          配置云端 API 以启用智能匹配和语音转录功能
        </p>
      </div>

      {/* Local mode info banner */}
      <Alert className="mb-8">
        <Info className="size-4" />
        <AlertDescription>
          <p className="text-sm font-medium text-foreground">不配置也可以使用</p>
          <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
            工具会自动使用本地 Whisper 模型进行转录和匹配，无需联网。
            云端服务的优势：更快的处理速度和更高的准确率。
          </p>
        </AlertDescription>
      </Alert>

      {/* Loading */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-24">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
          <p className="mt-4 text-sm text-muted-foreground">正在加载配置信息...</p>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <Alert variant="destructive" className="text-center">
          <AlertCircle className="size-4" />
          <AlertDescription>
            <p className="text-sm">{error}</p>
            <Button
              variant="destructive"
              size="sm"
              onClick={loadKeys}
              className="mt-3"
            >
              重试
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Main content */}
      {serverData && !loading && (
        <div className="space-y-6">

          {/* ═══════ LLM Section ═══════ */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="flex size-8 items-center justify-center rounded-lg bg-muted">
                  <Sparkles className="size-4 text-foreground" />
                </div>
                <div>
                  <CardTitle className="text-sm font-semibold">
                    LLM 智能匹配服务
                  </CardTitle>
                  <CardDescription>用于脚本匹配、SRT 分段和精剪决策</CardDescription>
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-5">
              {/* Provider selector */}
              <div>
                <Label className="mb-2">供应商</Label>
                <div className="flex gap-2">
                  {LLM_PRESETS.map((preset) => (
                    <Button
                      key={preset.id}
                      variant={selectedProvider === preset.id ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => handleProviderChange(preset.id)}
                    >
                      {preset.label}
                    </Button>
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
                <Label className="mb-1.5">Base URL</Label>
                <Input
                  type="text"
                  value={baseUrl}
                  onChange={(e) => handleBaseUrlChange(e.target.value)}
                  placeholder={selectedProvider === 'custom' ? '输入 API 地址' : currentPreset.baseUrl}
                  className="font-mono"
                />
              </div>

              {/* Model */}
              <div>
                <Label className="mb-1.5">模型名称</Label>
                <Input
                  type="text"
                  value={model}
                  onChange={(e) => handleModelChange(e.target.value)}
                  placeholder={selectedProvider === 'custom' ? '输入模型标识符' : currentPreset.model}
                  className="font-mono"
                />
              </div>

              {/* Help link + Test button */}
              <div className="flex items-center justify-between pt-1">
                {currentPreset.helpUrl ? (
                  <a
                    href={currentPreset.helpUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <ExternalLink className="size-3.5" />
                    {currentPreset.helpText}
                  </a>
                ) : (
                  <span className="text-xs text-muted-foreground">{currentPreset.helpText}</span>
                )}

                <TestButton
                  loading={llmTest.loading}
                  ok={llmTest.ok}
                  message={llmTest.msg}
                  onClick={handleTestLlm}
                />
              </div>
            </CardContent>
          </Card>

          {/* ═══════ Transcription Section ═══════ */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="flex size-8 items-center justify-center rounded-lg bg-muted">
                  <Mic className="size-4 text-foreground" />
                </div>
                <div>
                  <CardTitle className="text-sm font-semibold">
                    语音转录服务
                  </CardTitle>
                  <CardDescription>火山引擎音视频字幕 -- 云端语音识别与时间戳对齐</CardDescription>
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-5">
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
                  className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  <ExternalLink className="size-3.5" />
                  {TRANSCRIPTION_HELP.text}
                </a>

                <TestButton
                  loading={transcriptionTest.loading}
                  ok={transcriptionTest.ok}
                  message={transcriptionTest.msg}
                  onClick={handleTestTranscription}
                />
              </div>
            </CardContent>
          </Card>

          {/* ═══════ Save button ═══════ */}
          <div className="flex justify-end pt-2">
            <Button
              onClick={handleSave}
              disabled={saving || !dirty}
              size="lg"
            >
              {saving ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="size-4 animate-spin" />
                  保存中...
                </span>
              ) : (
                '保存配置'
              )}
            </Button>
          </div>
        </div>
      )}
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
        <Label>{keyStatus.display_name}</Label>
        {keyStatus.required && !keyStatus.is_set && value === '' && (
          <Badge variant="outline" className="text-warning border-warning/30 bg-warning/10 text-[10px]">
            必填
          </Badge>
        )}
        {!keyStatus.required && (
          <span className="text-[10px] text-muted-foreground/50">可选</span>
        )}
        {keyStatus.is_set && value === '' && (
          <Badge variant="outline" className="text-success border-success/30 bg-success/10 text-[10px]">
            已配置
          </Badge>
        )}
      </div>
      <div className="relative">
        <Input
          type={isSecret && !isVisible ? 'password' : 'text'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="pr-10 font-mono"
        />
        {isSecret && (
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            onClick={onToggleVisibility}
            className="absolute right-2 top-1/2 -translate-y-1/2"
          >
            {isVisible ? (
              <EyeOff className="size-4" />
            ) : (
              <Eye className="size-4" />
            )}
          </Button>
        )}
      </div>
      <p className="mt-1 text-[11px] text-muted-foreground/50">{keyStatus.description}</p>
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
        <span className={`text-xs ${ok ? 'text-success' : 'text-destructive'}`}>
          {message}
        </span>
      )}
      <Button
        variant="outline"
        size="sm"
        onClick={onClick}
        disabled={loading}
      >
        {loading ? (
          <>
            <Loader2 className="size-3.5 animate-spin" />
            测试中...
          </>
        ) : ok === true ? (
          <>
            <Check className="size-3.5 text-success" />
            测试连接
          </>
        ) : ok === false ? (
          <>
            <XIcon className="size-3.5 text-destructive" />
            测试连接
          </>
        ) : (
          <>
            <Plug className="size-3.5" />
            测试连接
          </>
        )}
      </Button>
    </div>
  );
}
