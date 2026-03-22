export interface TranscriptionWord {
  word: string;
  start: number;
  end: number;
  confidence: number;
}

export interface AlignedSegment {
  scriptIndex: number;
  scriptText: string;
  transcriptText: string;
  startTime: number;
  endTime: number;
  rawStartTime: number;
  rawEndTime: number;
  confidence: number;
  confidenceLevel: 'high' | 'medium' | 'low';
  status: 'auto_approved' | 'needs_review' | 'approved' | 'rejected';
  isReordered: boolean;
  originalPosition: number | null;
  isCopy: boolean;
  copySourceIndex: number | null;
  pauses: PauseSegment[];
}

export interface PauseSegment {
  start: number;
  end: number;
  duration: number;
  pauseType: 'breath' | 'natural' | 'thinking' | 'long';
  action: 'keep' | 'shorten' | 'remove' | 'review';
}

export interface JobResponse {
  id: string;
  status: string;
  progress: number;
  audioDuration: number | null;
  alignment: AlignedSegment[] | null;
  error: string | null;
  /** New detailed progress info from SSE; may be absent on older backends */
  stageProgress?: ProgressEvent;
}

export interface DictionaryEntry {
  wrong: string;
  correct: string;
  category: string;
  addedAt: string;
  frequency: number;
}

export interface DictionaryData {
  version: string;
  entries: DictionaryEntry[];
  customTerms: string[];
}

export interface ProgressEvent {
  stage: number;
  stage_name: string;
  stage_detail: string;
  progress: number;
  elapsed_seconds: number;
  estimated_remaining_seconds: number | null;
  /** Sub-task key -> status ("pending" | "in_progress" | "completed") */
  sub_tasks?: Record<string, string>;
}

export interface ExportRequest {
  format?: 'edl' | 'fcpxml' | 'srt' | 'all';
  formats?: Array<'edl' | 'fcpxml' | 'srt'>;
  frameRate: number;
  bufferDuration: number;
  subtitleSource: 'script' | 'transcript' | 'llm_corrected';
  videoFilename?: string;
}

export interface JobSummary {
  job_id: string;
  status: 'processing' | 'completed' | 'failed';
  progress: number;
  stage_name: string;
  script_name: string;
  audio_name: string;
  display_name: string;
  created_at: string;
  elapsed_seconds: number;
}

// ── Storage management ──

export interface StorageJobInfo {
  job_id: string;
  display_name: string;
  status: string;
  created_at: string;
  upload_bytes: number;
  output_bytes: number;
  total_bytes: number;
  total_display: string;
  files: Record<string, number>;
}

export interface StorageStats {
  total_bytes: number;
  total_display: string;
  jobs: StorageJobInfo[];
}

export interface CleanupRequest {
  job_ids: string[];
  delete_uploads: boolean;
  delete_outputs: boolean;
  delete_job: boolean;
}

export interface CleanupResponse {
  deleted_count: number;
  freed_bytes: number;
  freed_display: string;
}

// ── Settings / API key management ──

export interface ApiKeyStatus {
  key_name: string;
  display_name: string;
  group: 'llm' | 'transcription';
  is_set: boolean;
  masked_value: string;
  required: boolean;
  description: string;
}

export interface ApiKeysResponse {
  keys: ApiKeyStatus[];
  llm_base_url: string;
  llm_model: string;
}

export interface ApiKeyUpdate {
  key_name: string;
  value: string;
}

export interface TestResult {
  ok: boolean;
  message: string;
}

export interface HealthStatus {
  status: string;
  version: string;
  cloud_provider: string;
  has_api_key: boolean;
  has_caption_keys: boolean;
}

/** Shape of data sent by the backend SSE stream */
export interface SSEStatusData {
  job_id: string;
  state: string;
  progress: number;
  message: string;
  updated_at: string;
  stage: number;
  stage_name: string;
  stage_detail: string;
  elapsed_seconds: number;
  estimated_remaining_seconds: number | null;
  /** Sub-task key -> status ("pending" | "in_progress" | "completed") */
  sub_tasks?: Record<string, string>;
}
