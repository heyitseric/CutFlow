import { useEffect, useRef } from 'react';
import { connectJobSSE } from '../api/client';
import { useJobStore } from '../stores/jobStore';

const MAX_RECONNECT_ATTEMPTS = 10;

/**
 * SSE hook: subscribes to job status updates for a specific jobId.
 * Supports multiple concurrent connections (one per jobId).
 * Auto-reconnects on error with a maximum retry limit.
 */
export function useJob(jobId: string | null | undefined) {
  const updateJobFromSSE = useJobStore((s) => s.updateJobFromSSE);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) return;

    let reconnectTimer: ReturnType<typeof setTimeout>;
    let closed = false;
    let reconnectAttempts = 0;

    function connect() {
      if (closed) return;

      if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        console.warn(`[useJob] SSE reconnect limit reached for job ${jobId}`);
        updateJobFromSSE(jobId!, {
          status: 'failed',
          message: '连接中断，请刷新页面重试',
        });
        return;
      }

      const es = connectJobSSE(
        jobId!,
        (data) => {
          // Successfully received data — reset reconnect counter
          reconnectAttempts = 0;
          updateJobFromSSE(jobId!, data);
          // close when terminal
          if (data.status === 'completed' || data.status === 'failed') {
            es.close();
          }
        },
        () => {
          es.close();
          if (!closed) {
            reconnectAttempts++;
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
