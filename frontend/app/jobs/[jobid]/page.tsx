'use client';

import { use, useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import { AppShell } from '@/components/layout/AppShell';
import { NavTabs } from '@/components/layout/NavTabs';
import { PageHero } from '@/components/shared/PageHero';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingOverlay } from '@/components/shared/LoadingOverlay';
import { ContractViewer } from '@/components/viewer/ContractViewer';

import { fetchCanonicalBlob, getJob } from '@/lib/api/jobs';
import { APIError } from '@/lib/api/client';
import type { CanonicalDocument, JobRecord } from '@/lib/api/types';

import { useAppStore } from '@/store/useAppStore';
import { useJobPolling } from '@/hooks/useJobPolling';

export default function JobPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = use(params); // ← Next.js 15 auto-promise unwrap
  const router = useRouter();

  const setJobId = useAppStore((s) => s.setJobId);
  const resetEdits = useAppStore((s) => s.resetEdits);

  const [job, setJob] = useState<JobRecord | null>(null);
  const [canonical, setCanonical] = useState<CanonicalDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Sync state → NOT source of truth
  useEffect(() => {
    if (!jobId) return;
    setJobId(jobId);
    resetEdits();
  }, [jobId, resetEdits, setJobId]);

  // ✅ canonical loader
  const loadCanonical = useCallback(async () => {
    try {
      const blob = await fetchCanonicalBlob(jobId);
      const text = await blob.text();
      return JSON.parse(text) as CanonicalDocument;
    } catch (err) {
      console.error('canonical parse error:', err);
      return null;
    }
  }, [jobId]);

  // ✅ Initial load with your debug logs
  useEffect(() => {
    if (!jobId) return;
    let mounted = true;

    const load = async () => {
      setLoading(true);
      setError(null);

      try {
        console.log('1. fetching job...');
        const result = await getJob(jobId);
        console.log('2. job result:', result.status);

        if (!mounted) return;
        setJob(result);

        if (result.status === 'complete') {
          console.log('3. fetching canonical...');
          const c = await loadCanonical();
          console.log('4. canonical:', c);

          if (mounted) setCanonical(c);
        }
      } catch (err) {
        console.error('load error:', err);

        if (err instanceof APIError && err.status === 404) {
          toast.error('Job not found or expired. Please re-upload the file.');
          router.replace('/jobs');
          return;
        }

        setError(err instanceof Error ? err.message : 'Unable to load job');
      } finally {
        console.log('5. setting loading false');
        if (mounted) setLoading(false);
      }
    };

    void load();
    return () => {
      mounted = false;
    };
  }, [jobId, loadCanonical, router]);

  // ✅ Polling updates
  const handlePollingUpdate = useCallback(
    async (updated: JobRecord) => {
      setJob(updated);
      if (updated.status === 'complete') {
        const c = await loadCanonical();
        console.log('canonical loaded (polling):', c);
        setCanonical(c);
      }
    },
    [loadCanonical]
  );

  const handleNotFound = useCallback(() => {
    toast.error('Job not found or expired.');
    router.replace('/jobs');
  }, [router]);

  useJobPolling(jobId, handlePollingUpdate, {
    enabled: Boolean(jobId),
    onNotFound: handleNotFound,
    onError: (msg) => toast.error(msg),
  });

  // ✅ Manual refresh
  const refreshJob = useCallback(async () => {
    const fresh = await getJob(jobId);
    setJob(fresh);
    if (fresh.status === 'complete') {
      const c = await loadCanonical();
      console.log('canonical loaded (manual refresh):', c);
      setCanonical(c);
    }
  }, [jobId, loadCanonical]);

  // ✅ JSX builder
  const workspace = useMemo(() => {
    if (loading) return <LoadingOverlay label="Loading job workspace…" />;
    if (error || !job)
      return (
        <ErrorState
          message={error || 'Job unavailable'}
          onRetry={() => router.refresh()}
        />
      );
    return (
      <ContractViewer job={job} canonical={canonical} onRefresh={refreshJob} />
    );
  }, [canonical, error, job, loading, refreshJob, router]);

  return (
    <AppShell>
      <NavTabs current="jobs" />
      <PageHero
        eyebrow="Workspace"
        title={job?.file_name || 'Job workspace'}
        subtitle="Resolve conflicts, fill missing values, inspect canonical JSON and download outputs."
      />
      <div className="mt-6">{workspace}</div>
    </AppShell>
  );
}