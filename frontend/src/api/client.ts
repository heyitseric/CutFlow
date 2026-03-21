import type { JobResponse, DictionaryData, DictionaryEntry, ExportRequest } from './types';

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

export async function uploadJob(
  scriptFile: File,
  audioFile: File,
  provider: 'local' | 'cloud',
): Promise<JobResponse> {
  const form = new FormData();
  form.append('script', scriptFile);
  form.append('audio', audioFile);
  form.append('provider', provider);

  const res = await fetch(`${BASE}/jobs/upload`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Upload failed ${res.status}: ${body}`);
  }
  return res.json();
}

export async function getJob(jobId: string): Promise<JobResponse> {
  return request<JobResponse>(`/jobs/${jobId}`);
}

export function connectJobSSE(
  jobId: string,
  onMessage: (data: JobResponse) => void,
  onError?: (err: Event) => void,
): EventSource {
  const es = new EventSource(`${BASE}/jobs/${jobId}/stream`);
  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as JobResponse;
      onMessage(data);
    } catch {
      // ignore parse errors
    }
  };
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
