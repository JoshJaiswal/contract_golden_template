'use client';

import { useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { regenerateJob } from '@/lib/api/jobs';

export function useRegenerateJob(jobId: string) {
  const overrides = useAppStore((s) => s.overrides);
  const dismissedFields = useAppStore((s) => s.dismissedFields);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);

    try {
      return await regenerateJob(jobId, {
        overrides,
        dismissed_fields: dismissedFields,
      });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Regeneration failed';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return { run, loading, error };
}