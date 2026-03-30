'use client';
import { AppShell } from '@/components/layout/AppShell';
import { NavTabs } from '@/components/layout/NavTabs';
import { PageHero } from '@/components/shared/PageHero';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingOverlay } from '@/components/shared/LoadingOverlay';
import { MetricsPanel } from '@/components/dashboard/MetricsPanel';
import { JobList } from '@/components/dashboard/JobList';
import { EmptyDashboard } from '@/components/dashboard/EmptyDashboard';
import { Button } from '@/components/ui/button';
import { useJobList } from '@/hooks/useJobList';
import { extractJobStats } from '@/lib/format';
export default function JobsPage() { const { jobs, loading, error, refresh } = useJobList(); const stats = extractJobStats(jobs); return <AppShell><NavTabs current="jobs" /><PageHero eyebrow="Operations dashboard" title="Job dashboard" subtitle="Monitor recent analyses, check statuses, and reopen any job workspace from one place." right={<Button variant="secondary" onClick={() => void refresh()}>Refresh</Button>} /><div className="mt-6 space-y-6">{loading ? <LoadingOverlay label="Loading jobs…" /> : error ? <ErrorState message={error} onRetry={() => void refresh()} /> : <><MetricsPanel total={stats.total} complete={stats.complete} processing={stats.processing} failed={stats.failed} />{jobs.length ? <JobList jobs={jobs} /> : <EmptyDashboard />}</>}</div></AppShell>; }