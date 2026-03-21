import { useEffect, useRef } from 'react';
import { connectJobSSE } from '../api/client';
import { useJobStore } from '../stores/jobStore';

/**
 * SSE hook: subscribes to job status updates for a specific jobId.
 * Supports multiple concurrent connections (one per jobId).
 * Auto-reconnects on error.
 */
export function useJob(jobId: string | null | undefined) {
  const updateJobFromSSE = useJobStore((s) => s.updateJobFromSSE);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) return;

    let reconnectTimer: ReturnType<typeof setTimeout>;
    let closed = false;

    function connect() {
      if (closed) return;
      const es = connectJobSSE(
        jobId!,
        (data) => {
          updateJobFromSSE(jobId!, data);
          // close when terminal
          if (data.status === 'completed' || data.status === 'failed') {
            es.close();
          }
        },
        () => {
          es.close();
          if (!closed) {
            reconnectTimer = setTimeout(connect, 3000);
          }
        },
      );
      esRef.current = es;
    }

    connect();

    return () => {
      closed = true;
      clearTimeout(reconnectTimer);
      esRef.current?.close();
    };
  }, [jobId, updateJobFromSSE]);
}
