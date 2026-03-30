import { useEffect, useState } from 'react';
import { listJobs } from '@/lib/api/jobs';
import type { JobRecord } from '@/lib/api/types';

export function useJobList() {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = async () => {
    setLoading(true);
    try {
      const res = await listJobs();
      setJobs(res.jobs);   // ← unwrap .jobs here
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetch();
  }, []);

  return { jobs, loading, error, refresh: fetch };
}