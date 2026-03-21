import type { JobResponse, JobSummary, SSEStatusData, DictionaryData, DictionaryEntry, ExportRequest } from './types';

const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

// ── Job endpoints ──

interface UploadResponse {
  job_id: string;
  message: string;
  script_filename: string;
  audio_filename: string;
}

export async function uploadJob(
  scriptFile: File,
  audioFile: File,
  provider: 'local' | 'cloud',
): Promise<{ id: string; scriptFilename: string; audioFilename: string }> {
  const form = new FormData();
  form.append('script', scriptFile);
  form.append('audio', audioFile);
  form.append('provider', provider);

  const res = await fetch(`${BASE}/upload`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Upload failed ${res.status}: ${body}`);
  }
  const raw: UploadResponse = await res.json();
  return {
    id: raw.job_id,
    scriptFilename: raw.script_filename,
    audioFilename: raw.audio_filename,
  };
}

/** Raw shape returned by the backend GET /api/jobs/:id */
interface BackendJobResponse {
  job_id: string;
  state: string;
  progress: number;
  message: string;
  created_at: string;
  updated_at: string;
  script_filename: string;
  audio_filename: string;
  alignment: JobResponse['alignment'];
  transcription: unknown;
}

function mapBackendState(state: string): string {
  if (state === 'review' || state === 'done' || state === 'exporting') return 'completed';
  if (state === 'error') return 'failed';
  return 'processing';
}

export async function getJob(jobId: string): Promise<JobResponse & { scriptName: string; audioName: string; createdAt: string }> {
  const raw = await request<BackendJobResponse>(`/jobs/${jobId}`);
  return {
    id: raw.job_id,
    status: mapBackendState(raw.state),
    progress: raw.progress,
    audioDuration: null,
    alignment: raw.alignment,
    error: raw.state === 'error' ? raw.message : null,
    scriptName: raw.script_filename,
    audioName: raw.audio_filename,
    createdAt: raw.created_at,
  };
}

export async function listJobs(): Promise<JobSummary[]> {
  return request<JobSummary[]>('/jobs');
}

/** Mapped SSE data that matches what the job store expects */
export interface SSEMappedData {
  status: string;
  progress: number;
  error: string | null;
  elapsedSeconds: number;
  estimatedRemainingSeconds: number | null;
  stageProgress?: {
    stage: number;
    stage_name: string;
    stage_detail: string;
    progress: number;
    elapsed_seconds: number;
    estimated_remaining_seconds: number | null;
  };
}

function mapSSEStatus(state: string): string {
  if (state === 'review' || state === 'done' || state === 'exporting') return 'completed';
  if (state === 'error') return 'failed';
  return 'processing';
}

export function connectJobSSE(
  jobId: string,
  onMessage: (data: SSEMappedData) => void,
  onError?: (err: Event) => void,
): EventSource {
  const es = new EventSource(`${BASE}/jobs/${jobId}/status`);

  function handleEvent(event: MessageEvent) {
    try {
      const raw = JSON.parse(event.data) as SSEStatusData;
      const mapped: SSEMappedData = {
        status: mapSSEStatus(raw.state),
        progress: raw.progress,
        error: raw.state === 'error' ? (raw.message || 'Unknown error') : null,
        elapsedSeconds: raw.elapsed_seconds,
        estimatedRemainingSeconds: raw.estimated_remaining_seconds,
        stageProgress: {
          stage: raw.stage,
          stage_name: raw.stage_name,
          stage_detail: raw.stage_detail,
          progress: raw.progress,
          elapsed_seconds: raw.elapsed_seconds,
          estimated_remaining_seconds: raw.estimated_remaining_seconds,
        },
      };
      onMessage(mapped);
    } catch {
      // ignore parse errors
    }
  }

  // Backend sends named events: "status" and "complete"
  es.addEventListener('status', handleEvent);
  es.addEventListener('complete', handleEvent);
  // Also handle unnamed messages as fallback
  es.onmessage = handleEvent;

  es.onerror = (err) => {
    onError?.(err);
  };
  return es;
}

// ── Segment update ──

export async function updateSegment(
  jobId: string,
  segmentIndex: number,
  updates: Record<string, unknown>,
): Promise<void> {
  await request(`/jobs/${jobId}/segments/${segmentIndex}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

// ── Export ──

export async function exportJob(
  jobId: string,
  req: ExportRequest,
): Promise<{ downloadUrl: string }> {
  return request(`/jobs/${jobId}/export`, {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export function getExportDownloadUrl(jobId: string, format: string): string {
  return `${BASE}/jobs/${jobId}/export/download?format=${format}`;
}

// ── Dictionary ──

export async function getDictionary(): Promise<DictionaryData> {
  return request<DictionaryData>('/dictionary');
}

export async function addDictionaryEntry(
  entry: Omit<DictionaryEntry, 'addedAt' | 'frequency'>,
): Promise<DictionaryEntry> {
  return request<DictionaryEntry>('/dictionary/entries', {
    method: 'POST',
    body: JSON.stringify(entry),
  });
}

export async function deleteDictionaryEntry(wrong: string): Promise<void> {
  await request(`/dictionary/entries/${encodeURIComponent(wrong)}`, {
    method: 'DELETE',
  });
}

export async function importDictionary(data: DictionaryData): Promise<DictionaryData> {
  return request<DictionaryData>('/dictionary/import', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function exportDictionary(): Promise<DictionaryData> {
  return request<DictionaryData>('/dictionary/export');
}
