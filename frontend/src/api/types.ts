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

export interface ExportRequest {
  format: 'edl' | 'fcpxml' | 'srt' | 'all';
  frameRate: number;
  bufferDuration: number;
  subtitleSource: 'script' | 'transcript' | 'llm_corrected';
}
