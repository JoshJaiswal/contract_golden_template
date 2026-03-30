'use client';
import { useEffect, useRef } from 'react';
import { getJob } from '@/lib/api/jobs';
import { APIError } from '@/lib/api/client';
import type { JobRecord } from '@/lib/api/types';
export function useJobPolling(jobId: string, onUpdate: (job: JobRecord) => void, options?: { enabled?: boolean; intervalMs?: number; onNotFound?: () => void; onError?: (message: string) => void; }) {
  const intervalMs = options?.intervalMs ?? 3000;
  const enabled = options?.enabled ?? true;
  const timer = useRef<number | null>(null);
  useEffect(() => {
    if (!enabled || !jobId) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const job = await getJob(jobId);
        if (cancelled) return;
        onUpdate(job);
        if (job.status === 'complete' || job.status === 'failed') { if (timer.current) window.clearInterval(timer.current); timer.current = null; }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof APIError && err.status === 404) { options?.onNotFound?.(); return; }
        options?.onError?.(err instanceof Error ? err.message : 'Unable to fetch job');
      }
    };
    void tick();
    timer.current = window.setInterval(tick, intervalMs);
    return () => { cancelled = true; if (timer.current) window.clearInterval(timer.current); timer.current = null; };
  }, [enabled, jobId, intervalMs, onUpdate, options?.onError, options?.onNotFound]);
}