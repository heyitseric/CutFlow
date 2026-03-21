import { create } from 'zustand';
import type { AlignedSegment, JobResponse, PauseSegment } from '../api/types';

interface JobState {
  currentJobId: string | null;
  status: string;
  progress: number;
  audioDuration: number | null;
  alignment: AlignedSegment[] | null;
  error: string | null;

  // user edits layered on top of alignment
  editedSegments: Map<number, Partial<AlignedSegment>>;
  editedPauses: Map<string, Partial<PauseSegment>>; // key: "segIdx-pauseIdx"

  // actions
  setJob: (job: JobResponse) => void;
  updateFromSSE: (job: JobResponse) => void;
  updateSegment: (index: number, updates: Partial<AlignedSegment>) => void;
  approveSegment: (index: number) => void;
  rejectSegment: (index: number) => void;
  updatePause: (segIdx: number, pauseIdx: number, updates: Partial<PauseSegment>) => void;
  batchUpdatePauses: (pauseType: PauseSegment['pauseType'], action: PauseSegment['action']) => void;
  getSegment: (index: number) => AlignedSegment | null;
  reset: () => void;
}

const initialState = {
  currentJobId: null,
  status: 'idle',
  progress: 0,
  audioDuration: null,
  alignment: null,
  error: null,
  editedSegments: new Map<number, Partial<AlignedSegment>>(),
  editedPauses: new Map<string, Partial<PauseSegment>>(),
};

export const useJobStore = create<JobState>((set, get) => ({
  ...initialState,

  setJob: (job) =>
    set({
      currentJobId: job.id,
      status: job.status,
      progress: job.progress,
      audioDuration: job.audioDuration,
      alignment: job.alignment,
      error: job.error,
      editedSegments: new Map(),
      editedPauses: new Map(),
    }),

  updateFromSSE: (job) =>
    set((state) => ({
      status: job.status,
      progress: job.progress,
      audioDuration: job.audioDuration ?? state.audioDuration,
      alignment: job.alignment ?? state.alignment,
      error: job.error,
    })),

  updateSegment: (index, updates) =>
    set((state) => {
      const next = new Map(state.editedSegments);
      const existing = next.get(index) ?? {};
      next.set(index, { ...existing, ...updates });
      return { editedSegments: next };
    }),

  approveSegment: (index) =>
    get().updateSegment(index, { status: 'approved' }),

  rejectSegment: (index) =>
    get().updateSegment(index, { status: 'rejected' }),

  updatePause: (segIdx, pauseIdx, updates) =>
    set((state) => {
      const key = `${segIdx}-${pauseIdx}`;
      const next = new Map(state.editedPauses);
      const existing = next.get(key) ?? {};
      next.set(key, { ...existing, ...updates });
      return { editedPauses: next };
    }),

  batchUpdatePauses: (pauseType, action) =>
    set((state) => {
      if (!state.alignment) return {};
      const next = new Map(state.editedPauses);
      state.alignment.forEach((seg, segIdx) => {
        seg.pauses.forEach((pause, pauseIdx) => {
          if (pause.pauseType === pauseType) {
            const key = `${segIdx}-${pauseIdx}`;
            const existing = next.get(key) ?? {};
            next.set(key, { ...existing, action });
          }
        });
      });
      return { editedPauses: next };
    }),

  getSegment: (index) => {
    const state = get();
    if (!state.alignment || !state.alignment[index]) return null;
    const base = state.alignment[index];
    const edits = state.editedSegments.get(index);
    return edits ? { ...base, ...edits } : base;
  },

  reset: () => set(initialState),
}));
