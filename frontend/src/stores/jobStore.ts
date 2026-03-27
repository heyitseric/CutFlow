import { create } from 'zustand';
import type { AlignedSegment, JobSummary, PauseSegment, ProgressEvent } from '../api/types';
import { listJobs, updateSegment as patchSegment, renameJob as apiRenameJob, deleteJob as apiDeleteJob } from '../api/client';

// ── Per-job state ──

export interface SingleJobState {
  jobId: string;
  status: string;
  progress: number;
  audioDuration: number | null;
  alignment: AlignedSegment[] | null;
  error: string | null;
  stageProgress: ProgressEvent | null;
  scriptName: string;
  audioName: string;
  displayName: string;
  createdAt: string;

  // Time tracking — persisted from SSE so they survive job switching
  elapsedSeconds: number;
  estimatedRemainingSeconds: number | null;

  // user edits layered on top of alignment
  editedSegments: Map<number, Partial<AlignedSegment>>;
  editedPauses: Map<string, Partial<PauseSegment>>; // key: "segIdx-pauseIdx"

  // save status tracking for segment edits: key = segment index
  saveStatus: Map<number, 'saving' | 'saved' | 'error'>;
}

function createEmptyJob(jobId: string, scriptName = '', audioName = '', createdAt = '', displayName = ''): SingleJobState {
  return {
    jobId,
    status: 'processing',
    progress: 0,
    audioDuration: null,
    alignment: null,
    error: null,
    stageProgress: null,
    scriptName,
    audioName,
    displayName: displayName || scriptName,
    createdAt: createdAt || new Date().toISOString(),
    elapsedSeconds: 0,
    estimatedRemainingSeconds: null,
    editedSegments: new Map(),
    editedPauses: new Map(),
    saveStatus: new Map(),
  };
}

// ── Store interface ──

interface JobStoreState {
  jobs: Record<string, SingleJobState>;
  activeJobId: string | null;
  sidebarOpen: boolean;

  // actions
  addJob(jobId: string, scriptName: string, audioName: string): void;
  setActiveJob(jobId: string | null): void;
  toggleSidebar(): void;
  setSidebarOpen(open: boolean): void;

  /** Legacy setJob — initialises or overwrites a job from a full API response */
  setJob: (job: {
    id: string;
    status: string;
    progress: number;
    audioDuration: number | null;
    alignment: AlignedSegment[] | null;
    error: string | null;
    stageProgress?: ProgressEvent;
    scriptName?: string;
    audioName?: string;
    createdAt?: string;
  }) => void;

  /** Update a specific job from SSE data */
  updateJobFromSSE: (jobId: string, data: {
    status: string;
    progress: number;
    audioDuration?: number | null;
    alignment?: AlignedSegment[] | null;
    error: string | null;
    stageProgress?: ProgressEvent;
    elapsedSeconds?: number;
    estimatedRemainingSeconds?: number | null;
  }) => void;

  /** Fetch job list from backend and populate store */
  fetchJobList: () => Promise<void>;

  /** Rename a job's display name */
  renameJob: (jobId: string, newName: string) => Promise<void>;

  /** Delete a job */
  deleteJobAction: (jobId: string) => Promise<void>;

  // segment editing (scoped to active job)
  updateSegment: (index: number, updates: Partial<AlignedSegment>) => void;
  approveSegment: (index: number) => void;
  rejectSegment: (index: number) => void;
  updatePause: (segIdx: number, pauseIdx: number, updates: Partial<PauseSegment>) => void;
  batchUpdatePauses: (pauseType: PauseSegment['pauseType'], action: PauseSegment['action']) => void;
  getSegment: (index: number) => AlignedSegment | null;
  getSaveStatus: (index: number) => 'saving' | 'saved' | 'error' | null;
}

export const useJobStore = create<JobStoreState>((set, get) => ({
  jobs: {},
  activeJobId: null,
  sidebarOpen: true,

  addJob: (jobId, scriptName, audioName) =>
    set((state) => ({
      jobs: {
        ...state.jobs,
        [jobId]: state.jobs[jobId] ?? createEmptyJob(jobId, scriptName, audioName),
      },
      activeJobId: jobId,
    })),

  setActiveJob: (jobId) => set({ activeJobId: jobId }),

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  setSidebarOpen: (open) => set({ sidebarOpen: open }),

  setJob: (job) =>
    set((state) => {
      const existing = state.jobs[job.id];
      return {
        jobs: {
          ...state.jobs,
          [job.id]: {
            ...(existing ?? createEmptyJob(job.id)),
            jobId: job.id,
            status: job.status,
            progress: job.progress,
            audioDuration: job.audioDuration ?? existing?.audioDuration ?? null,
            alignment: job.alignment ?? existing?.alignment ?? null,
            error: job.error,
            stageProgress: job.stageProgress ?? existing?.stageProgress ?? null,
            scriptName: job.scriptName ?? existing?.scriptName ?? '',
            audioName: job.audioName ?? existing?.audioName ?? '',
            createdAt: job.createdAt ?? existing?.createdAt ?? new Date().toISOString(),
            editedSegments: existing?.editedSegments ?? new Map(),
            editedPauses: existing?.editedPauses ?? new Map(),
          },
        },
        activeJobId: job.id,
      };
    }),

  updateJobFromSSE: (jobId, data) =>
    set((state) => {
      const existing = state.jobs[jobId];
      if (!existing) return {};
      return {
        jobs: {
          ...state.jobs,
          [jobId]: {
            ...existing,
            status: data.status,
            progress: data.progress,
            audioDuration: data.audioDuration ?? existing.audioDuration,
            alignment: data.alignment ?? existing.alignment,
            error: data.error,
            stageProgress: data.stageProgress ?? existing.stageProgress,
            elapsedSeconds: data.elapsedSeconds ?? existing.elapsedSeconds,
            estimatedRemainingSeconds: data.estimatedRemainingSeconds !== undefined
              ? data.estimatedRemainingSeconds
              : existing.estimatedRemainingSeconds,
          },
        },
      };
    }),

  fetchJobList: async () => {
    try {
      const summaries: JobSummary[] = await listJobs();
      set((state) => {
        const next = { ...state.jobs };
        for (const s of summaries) {
          if (!next[s.job_id]) {
            next[s.job_id] = {
              ...createEmptyJob(s.job_id, s.script_name, s.audio_name, s.created_at, s.display_name),
              status: s.status,
              progress: s.progress / 100, // backend sends 0-100, frontend uses 0-1
            };
          } else {
            // Update status/progress but keep any richer data we already have
            next[s.job_id] = {
              ...next[s.job_id],
              status: s.status,
              progress: s.progress / 100,
              scriptName: s.script_name || next[s.job_id].scriptName,
              audioName: s.audio_name || next[s.job_id].audioName,
              displayName: s.display_name || next[s.job_id].displayName,
              createdAt: s.created_at || next[s.job_id].createdAt,
            };
          }
        }
        return { jobs: next };
      });
    } catch {
      // Silently ignore — sidebar will just be empty
    }
  },

  renameJob: async (jobId, newName) => {
    try {
      await apiRenameJob(jobId, newName);
      set((state) => {
        const job = state.jobs[jobId];
        if (!job) return {};
        return {
          jobs: { ...state.jobs, [jobId]: { ...job, displayName: newName } },
        };
      });
    } catch (err) {
      console.error('[jobStore] Failed to rename job:', err);
    }
  },

  deleteJobAction: async (jobId) => {
    try {
      await apiDeleteJob(jobId);
      set((state) => {
        const next = { ...state.jobs };
        delete next[jobId];
        return {
          jobs: next,
          activeJobId: state.activeJobId === jobId ? null : state.activeJobId,
        };
      });
    } catch (err) {
      console.error('[jobStore] Failed to delete job:', err);
      throw err;
    }
  },

  // ── Segment editing (scoped to active job) ──

  updateSegment: (index, updates) => {
    const jobId = get().activeJobId;
    if (!jobId) return;

    // Helper to update saveStatus for this segment
    const setSaveStatus = (status: 'saving' | 'saved' | 'error') => {
      set((state) => {
        const job = state.jobs[jobId];
        if (!job) return {};
        const nextStatus = new Map(job.saveStatus);
        nextStatus.set(index, status);
        return { jobs: { ...state.jobs, [jobId]: { ...job, saveStatus: nextStatus } } };
      });
    };

    // Optimistic update: apply edit locally immediately
    set((state) => {
      if (!state.jobs[jobId]) return {};
      const job = state.jobs[jobId];
      const next = new Map(job.editedSegments);
      const existing = next.get(index) ?? {};
      next.set(index, { ...existing, ...updates });
      return {
        jobs: { ...state.jobs, [jobId]: { ...job, editedSegments: next } },
      };
    });

    // Persist to backend with retry on failure
    setSaveStatus('saving');
    patchSegment(jobId, index, updates as Record<string, unknown>)
      .then(() => {
        setSaveStatus('saved');
        // Clear "saved" indicator after 2s to reduce visual noise
        setTimeout(() => {
          const job = get().jobs[jobId];
          if (job?.saveStatus.get(index) === 'saved') {
            setSaveStatus('saved'); // keep saved, will naturally fade in UI
          }
        }, 2000);
      })
      .catch(() => {
        // Retry once after 2s
        setTimeout(() => {
          patchSegment(jobId, index, updates as Record<string, unknown>)
            .then(() => setSaveStatus('saved'))
            .catch((err) => {
              console.error('[jobStore] Failed to persist segment update after retry:', err);
              setSaveStatus('error');
            });
        }, 2000);
      });
  },

  approveSegment: (index) => get().updateSegment(index, { status: 'approved' }),

  rejectSegment: (index) => get().updateSegment(index, { status: 'rejected' }),

  updatePause: (segIdx, pauseIdx, updates) =>
    set((state) => {
      const jobId = state.activeJobId;
      if (!jobId || !state.jobs[jobId]) return {};
      const job = state.jobs[jobId];
      const key = `${segIdx}-${pauseIdx}`;
      const next = new Map(job.editedPauses);
      const existing = next.get(key) ?? {};
      next.set(key, { ...existing, ...updates });
      return {
        jobs: { ...state.jobs, [jobId]: { ...job, editedPauses: next } },
      };
    }),

  batchUpdatePauses: (pauseType, action) =>
    set((state) => {
      const jobId = state.activeJobId;
      if (!jobId || !state.jobs[jobId]) return {};
      const job = state.jobs[jobId];
      if (!job.alignment) return {};
      const next = new Map(job.editedPauses);
      job.alignment.forEach((seg, segIdx) => {
        seg.pauses.forEach((pause, pauseIdx) => {
          if (pause.pauseType === pauseType) {
            const key = `${segIdx}-${pauseIdx}`;
            const existing = next.get(key) ?? {};
            next.set(key, { ...existing, action });
          }
        });
      });
      return {
        jobs: { ...state.jobs, [jobId]: { ...job, editedPauses: next } },
      };
    }),

  getSegment: (index) => {
    const state = get();
    const jobId = state.activeJobId;
    if (!jobId || !state.jobs[jobId]) return null;
    const job = state.jobs[jobId];
    if (!job.alignment || !job.alignment[index]) return null;
    const base = job.alignment[index];
    const edits = job.editedSegments.get(index);
    return edits ? { ...base, ...edits } : base;
  },

  getSaveStatus: (index) => {
    const state = get();
    const jobId = state.activeJobId;
    if (!jobId || !state.jobs[jobId]) return null;
    return state.jobs[jobId].saveStatus.get(index) ?? null;
  },
}));

// ── Convenience hook: get the active job's fields (mimics old flat store shape) ──

export function useActiveJob() {
  const activeJobId = useJobStore((s) => s.activeJobId);
  const job = useJobStore((s) => (activeJobId ? s.jobs[activeJobId] : null));

  return {
    currentJobId: activeJobId,
    status: job?.status ?? 'idle',
    progress: job?.progress ?? 0,
    audioDuration: job?.audioDuration ?? null,
    alignment: job?.alignment ?? null,
    error: job?.error ?? null,
    stageProgress: job?.stageProgress ?? null,
    elapsedSeconds: job?.elapsedSeconds ?? 0,
    estimatedRemainingSeconds: job?.estimatedRemainingSeconds ?? null,
    editedSegments: job?.editedSegments ?? new Map<number, Partial<AlignedSegment>>(),
    editedPauses: job?.editedPauses ?? new Map<string, Partial<PauseSegment>>(),
  };
}
