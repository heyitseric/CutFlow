import type { AlignedSegment, PauseSegment, JobResponse, JobSummary, SSEStatusData, DictionaryData, DictionaryEntry, ExportRequest, StorageStats, CleanupRequest, CleanupResponse } from './types';

const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',
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
  alignment: BackendAlignedSegment[] | null;
  transcription: unknown;
}

/** Backend uses snake_case for AlignedSegment fields */
interface BackendPauseSegment {
  start: number;
  end: number;
  duration: number;
  pause_type: string;
  action: string;
}

interface BackendAlignedSegment {
  script_index: number;
  script_text: string;
  transcript_text: string;
  start_time: number;
  end_time: number;
  raw_start_time: number;
  raw_end_time: number;
  confidence: number;
  confidence_level: string;
  status: string;
  is_reordered: boolean;
  original_position: number | null;
  is_copy: boolean;
  copy_source_index: number | null;
  pauses: BackendPauseSegment[];
}

/** Map backend snake_case alignment data to frontend camelCase types */
function mapAlignment(segments: BackendAlignedSegment[] | null): AlignedSegment[] | null {
  if (!segments) return null;
  // Debug: log raw backend data for first segment to verify mapping
  if (segments.length > 0 && import.meta.env.DEV) {
    const s = segments[0];
    console.debug('[mapAlignment] raw backend segment[0]:', {
      script_text: s.script_text,
      transcript_text: s.transcript_text,
      start_time: s.start_time,
      end_time: s.end_time,
      confidence: s.confidence,
      status: s.status,
      keys: Object.keys(s),
    });
  }
  return segments.map((seg) => ({
    scriptIndex: seg.script_index,
    scriptText: seg.script_text,
    transcriptText: seg.transcript_text ?? '',
    startTime: seg.start_time ?? 0,
    endTime: seg.end_time ?? 0,
    rawStartTime: seg.raw_start_time ?? 0,
    rawEndTime: seg.raw_end_time ?? 0,
    confidence: seg.confidence ?? 0,
    confidenceLevel: (seg.confidence_level ?? 'low') as AlignedSegment['confidenceLevel'],
    status: mapSegmentStatus(seg.status),
    isReordered: seg.is_reordered ?? false,
    originalPosition: seg.original_position ?? null,
    isCopy: seg.is_copy ?? false,
    copySourceIndex: seg.copy_source_index ?? null,
    pauses: (seg.pauses ?? []).map((p) => ({
      start: p.start,
      end: p.end,
      duration: p.duration,
      pauseType: (p.pause_type ?? 'natural') as PauseSegment['pauseType'],
      action: (p.action ?? 'keep') as PauseSegment['action'],
    })),
  }));
}

/** Map backend segment status values to frontend status values */
function mapSegmentStatus(status: string): AlignedSegment['status'] {
  // Backend uses: matched, copy, deleted, unmatched, approved, rejected
  // Frontend uses: auto_approved, needs_review, approved, rejected
  switch (status) {
    case 'approved': return 'approved';
    case 'rejected': return 'rejected';
    case 'matched': return 'auto_approved';
    case 'copy': return 'auto_approved';
    default: return 'needs_review';
  }
}

function mapBackendState(state: string): string {
  if (state === 'review' || state === 'done' || state === 'exporting') return 'completed';
  if (state === 'error') return 'failed';
  return 'processing';
}

export async function getJob(jobId: string): Promise<JobResponse & { scriptName: string; audioName: string; createdAt: string }> {
  const raw = await request<BackendJobResponse>(`/jobs/${jobId}`);
  if (import.meta.env.DEV) {
    console.debug('[getJob] raw response:', {
      state: raw.state,
      alignmentPresent: raw.alignment != null,
      alignmentLength: raw.alignment?.length ?? 0,
      firstSegment: raw.alignment?.[0] ? {
        transcript_text: raw.alignment[0].transcript_text,
        start_time: raw.alignment[0].start_time,
        end_time: raw.alignment[0].end_time,
        confidence: raw.alignment[0].confidence,
      } : null,
    });
  }
  return {
    id: raw.job_id,
    status: mapBackendState(raw.state),
    progress: raw.progress,
    audioDuration: null,
    alignment: mapAlignment(raw.alignment),
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
    sub_tasks?: Record<string, string>;
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
          sub_tasks: raw.sub_tasks,
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

export async function downloadExportFile(jobId: string, format: string, baseName?: string): Promise<void> {
  const url = getExportDownloadUrl(jobId, format);
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Download failed ${res.status}: ${body}`);
  }
  const blob = await res.blob();
  // Use the provided baseName (script filename stem) if available, otherwise fall back to jobId
  const stem = baseName ? baseName.replace(/\.[^.]+$/, '') : jobId;
  const filename = `${stem}.${format}`;
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(blobUrl);
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

// ── Job management ──

export async function renameJob(jobId: string, displayName: string): Promise<void> {
  await request(`/jobs/${jobId}`, {
    method: 'PATCH',
    body: JSON.stringify({ display_name: displayName }),
  });
}

export async function deleteJob(jobId: string): Promise<void> {
  await request(`/jobs/${jobId}`, { method: 'DELETE' });
}

// ── Storage management ──

export async function getStorageStats(): Promise<StorageStats> {
  return request<StorageStats>('/storage/stats');
}

export async function cleanupStorage(req: CleanupRequest): Promise<CleanupResponse> {
  return request<CleanupResponse>('/storage/cleanup', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}
