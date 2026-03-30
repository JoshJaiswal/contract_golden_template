'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import { AppShell } from '@/components/layout/AppShell';
import { NavTabs } from '@/components/layout/NavTabs';
import { PageHero } from '@/components/shared/PageHero';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingOverlay } from '@/components/shared/LoadingOverlay';
import { ContractViewer } from '@/components/viewer/ContractViewer';
import { fetchCanonical, getJob } from '@/lib/api/jobs';
import { APIError } from '@/lib/api/client';
import type { CanonicalDocument, JobRecord } from '@/lib/api/types';
import { useAppStore } from '@/store/useAppStore';
import { useJobPolling } from '@/hooks/useJobPolling';

export default function JobPage({ params }: { params: { jobId: string } }) {
  const router = useRouter();
  const { jobId } = params;
  const setJobId = useAppStore((s) => s.setJobId);
  const resetEdits = useAppStore((s) => s.resetEdits);

  const [job, setJob] = useState<JobRecord | null>(null);
  const [canonical, setCanonical] = useState<CanonicalDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setJobId(jobId);
    resetEdits();
  }, [jobId, resetEdits, setJobId]);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      setLoading(true);
      setError(null);

      try {
        const result = await getJob(jobId);
        if (!mounted) return;
        setJob(result);

        if (result.status === 'complete') {
          try {
            const c = await fetchCanonical(jobId);
            if (mounted) setCanonical(c);
          } catch {
            if (mounted) setCanonical(null);
          }
        }
      } catch (err) {
        if (!mounted) return;
        if (err instanceof APIError && err.status === 404) {
          toast.error('Job not found or expired. Please re-upload the file.');
          router.replace('/jobs');
          return;
        }
        setError(err instanceof Error ? err.message : 'Unable to load job');
      } finally {
        if (mounted) setLoading(false);
      }
    };

    void load();
    return () => {
      mounted = false;
    };
  }, [jobId, router]);

  const handlePollingUpdate = useCallback(async (updated: JobRecord) => {
    setJob(updated);

    if (updated.status === 'complete') {
      try {
        const c = await fetchCanonical(jobId);
        setCanonical(c);
      } catch {
        setCanonical(null);
      }
    }
  }, [jobId]);

  const handleNotFound = useCallback(() => {
    toast.error('Job not found or expired. Please re-upload the file.');
    router.replace('/jobs');
  }, [router]);

  const handlePollingError = useCallback((message: string) => {
    toast.error(message);
  }, []);

  useJobPolling(jobId, handlePollingUpdate, {
    enabled: Boolean(jobId),
    onNotFound: handleNotFound,
    onError: handlePollingError,
  });

  const refreshJob = useCallback(async () => {
    const fresh = await getJob(jobId);
    setJob(fresh);
    if (fresh.status === 'complete') {
      try {
        const c = await fetchCanonical(jobId);
        setCanonical(c);
      } catch {
        setCanonical(null);
      }
    }
  }, [jobId]);

  const workspace = useMemo(() => {
    if (loading) {
      return <LoadingOverlay label="Loading job workspace…" />;
    }

    if (error || !job) {
      return <ErrorState message={error || 'Job unavailable'} onRetry={() => router.refresh()} />;
    }

    return <ContractViewer job={job} canonical={canonical} onRefresh={refreshJob} />;
  }, [canonical, error, job, loading, refreshJob, router]);

  return (
    <AppShell>
      <NavTabs current="jobs" />
      <PageHero
        eyebrow="Workspace"
        title={job?.file_name || 'Job workspace'}
        subtitle="Resolve conflicts, fill missing values, inspect the canonical JSON and download outputs."
      />
      <div className="mt-6">{workspace}</div>
    </AppShell>
  );
}