'use client';

import { useMemo, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardBody } from '@/components/ui/card';
import { Tabs } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';

import { PreviewPane } from './PreviewPane';
import { JsonViewer } from './JsonViewer';

import { SummarySection } from '@/components/summary/SummarySection';
import { ConflictList } from '@/components/conflicts/ConflictList';
import { MissingFieldTree } from '@/components/missing/MissingFieldTree';

import { JobActions } from '@/components/jobs/JobActions';
import { JobProgress } from '@/components/jobs/JobProgress';
import { JobTimeline } from '@/components/jobs/JobTimeline';

import {
  formatContractType,
  formatDateTime,
  extractConflicts,
  extractMissingFields,
  extractSummarySections,
  cnKeyToLabel, // ✅ used to build a human label for conflicts
} from '@/lib/format';

import { useRegenerateJob } from '@/hooks/useRegenerateJob';
import type { JobRecord } from '@/lib/api/types';

// ✅ Subscribe to the edit state so UI reacts to "Save value" / "Dismiss"
import { useAppStore } from '@/store/useAppStore';

// ---------- helpers to apply overrides by dot-path ----------
function setByPath<T extends Record<string, any>>(obj: T, path: string, value: any): T {
  const clone: any = Array.isArray(obj) ? [...obj] : { ...obj };
  const parts = path.split('.');
  let cur = clone;

  for (let i = 0; i < parts.length - 1; i++) {
    const p = parts[i];
    if (cur[p] == null || typeof cur[p] !== 'object') {
      cur[p] = {};
    }
    cur = cur[p];
  }

  cur[parts[parts.length - 1]] = value;
  return clone;
}

function applyOverrides<T extends Record<string, any>>(canonical: T | null, overrides: Record<string, string>): T | null {
  if (!canonical) return canonical as any;
  let out: any =
    typeof structuredClone === 'function'
      ? structuredClone(canonical)
      : JSON.parse(JSON.stringify(canonical));

  for (const [path, val] of Object.entries(overrides)) {
    out = setByPath(out, path, val);
  }
  return out;
}

function stringifyVal(v: unknown): string {
  if (Array.isArray(v)) return v.join(', ');
  if (typeof v === 'object' && v !== null) return JSON.stringify(v);
  return String(v ?? '');
}
// ---------- end helpers ----------

export function ContractViewer({
  job,
  canonical,
  onRefresh,
}: {
  job: JobRecord;
  canonical: Record<string, any> | null;
  onRefresh: () => Promise<void>;
}) {
  const [tab, setTab] = useState('overview');
  const { run, loading } = useRegenerateJob(job.job_id);

  // ✅ Pull live state so this component re-renders after Save/Dismiss
  const overrides = useAppStore((s) => s.overrides);
  const dismissedFields = useAppStore((s) => s.dismissedFields);

  // ✅ Merge overrides so Summary/JSON reflect edits immediately
  const effectiveCanonical = useMemo(
    () => applyOverrides(canonical, overrides),
    [canonical, overrides]
  );

  // ✅ Build view models from the effective canonical
  const summarySections = useMemo(
    () => extractSummarySections(effectiveCanonical),
    [effectiveCanonical]
  );

  // ---- Conflicts: adapt to ConflictList's expected type ----
  const rawConflicts = useMemo(
    () => extractConflicts(effectiveCanonical),
    [effectiveCanonical]
  );

  // ConflictList expects: { field, label, current, proposed, note? }[]
  const conflictsForList = useMemo(() => {
    return rawConflicts.map((c) => {
      const proposedFirst = c.alternatives?.[0];
      const proposedValue =
        proposedFirst?.value != null ? stringifyVal(proposedFirst.value) : c.chosen;

      const altNote =
        c.alternatives && c.alternatives.length
          ? `Alternatives: ${c.alternatives
              .map((a) => `${stringifyVal(a.value)} (source: ${a.source || 'n/a'})`)
              .join(' | ')}`
          : 'No alternatives';

      return {
        field: c.field,
        label: cnKeyToLabel(c.field),
        current: stringifyVal(c.chosen),
        proposed: proposedValue,
        note: `Chosen source: ${c.chosenSource || 'n/a'}. ${altNote}`,
      };
    });
  }, [rawConflicts]);

  // ---- Missing fields: start from original, then hide overridden/dismissed ----
  const rawMissing = useMemo(
    () => extractMissingFields(canonical),
    [canonical]
  );

  // ✅ Hide items that are overridden or dismissed
  const missing = useMemo(() => {
    const filtered = rawMissing
      .map((g) => ({
        ...g,
        items: g.items.filter((it: any) => {
          const fieldPath = (it.full ?? it.field) as string | undefined;
          if (!fieldPath) return true; // if we don't know the path, keep it
          const hasOverride = Boolean(overrides[fieldPath]);
          const isDismissed = dismissedFields.includes(fieldPath);
          return !hasOverride && !isDismissed;
        }),
      }))
      .filter((g) => g.items.length > 0);

    return filtered;
  }, [rawMissing, overrides, dismissedFields]);

  const counts = [
    { value: 'overview', label: 'Overview' },
    { value: 'summary', label: 'Summary', count: summarySections.length },
    { value: 'conflicts', label: 'Conflicts', count: conflictsForList.length }, // ✅ using adapted list
    {
      value: 'missing',
      label: 'Missing Fields',
      // ✅ count after filtering
      count: missing.reduce((sum, g) => sum + g.items.length, 0),
    },
    { value: 'source', label: 'Source' },
    { value: 'json', label: 'Canonical JSON' },
    { value: 'downloads', label: 'Downloads' },
  ];

  const handleRegenerate = async () => {
    try {
      await run();
      toast.success('Regeneration queued');
      await onRefresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Regeneration failed');
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardBody className="space-y-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="text-xs font-mono uppercase tracking-[0.24em] text-yellow-700">
                Job workspace
              </p>

              <h1 className="mt-2 font-[family-name:var(--font-syne)] text-3xl font-bold tracking-tight text-zinc-900">
                {job.file_name}
              </h1>

              <p className="mt-2 text-sm text-zinc-500">{job.job_id}</p>

              <div className="mt-3 flex flex-wrap gap-2">
                <Badge
                  tone={
                    job.status === 'complete'
                      ? 'success'
                      : job.status === 'failed'
                      ? 'danger'
                      : job.status === 'processing'
                      ? 'warning'
                      : 'neutral'
                  }
                >
                  {job.status}
                </Badge>

                <Badge tone="neutral">
                  {formatContractType(job.contract_type)}
                </Badge>

                <Badge tone="neutral">
                  Created {formatDateTime(job.created_at)}
                </Badge>
              </div>
            </div>

            <JobActions jobId={job.job_id} onRegenerate={handleRegenerate} regenLoading={loading} />
          </div>

          <JobProgress status={job.status} />
          <JobTimeline status={job.status} />
        </CardBody>
      </Card>

      <Tabs value={tab} onChange={setTab} items={counts as any} />

      {/* OVERVIEW TAB */}
      {tab === 'overview' && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardBody>
              <h2 className="mb-3 text-lg font-semibold text-zinc-900">Overview</h2>

              <p className="text-sm text-zinc-600">
                Use the tabs to inspect the summary, resolve conflicts, fill missing fields, and generate NDA/SOW outputs.
              </p>

              <div className="mt-4 space-y-2 text-sm text-zinc-700">
                <p>
                  <span className="font-medium">Status:</span> {job.status}
                </p>
                <p>
                  <span className="font-medium">File:</span> {job.file_name}
                </p>
                <p>
                  <span className="font-medium">Type:</span> {formatContractType(job.contract_type)}
                </p>
                <p>
                  <span className="font-medium">Created:</span> {formatDateTime(job.created_at)}
                </p>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <h2 className="mb-3 text-lg font-semibold text-zinc-900">Source preview</h2>
              <PreviewPane jobId={job.job_id} fileName={job.file_name} />
            </CardBody>
          </Card>
        </div>
      )}

      {/* SUMMARY TAB */}
      {tab === 'summary' && (
        <Card>
          <CardBody>
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-zinc-900">Summary</h2>

              <Button variant="primary" onClick={() => void handleRegenerate()} disabled={loading}>
                Regenerate
              </Button>
            </div>

            {/* ✅ Use effective canonical so summary reflects saved values */}
            <SummarySection sections={summarySections} />
          </CardBody>
        </Card>
      )}

      {/* CONFLICTS TAB */}
      {tab === 'conflicts' && (
        <Card>
          <CardBody>
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-zinc-900">Conflicts</h2>

              <Button variant="primary" onClick={() => void handleRegenerate()} disabled={loading}>
                Regenerate
              </Button>
            </div>

            {/* ✅ Adapted list to match ConflictList prop type */}
            <ConflictList conflicts={conflictsForList} />
          </CardBody>
        </Card>
      )}

      {/* MISSING FIELDS TAB */}
      {tab === 'missing' && (
        <Card>
          <CardBody>
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-zinc-900">Missing fields</h2>

              <Button variant="primary" onClick={() => void handleRegenerate()} disabled={loading}>
                Regenerate
              </Button>
            </div>

            {/* ✅ Pass filtered groups so saved/dismissed items disappear */}
            <MissingFieldTree groups={missing} />
          </CardBody>
        </Card>
      )}

      {/* SOURCE TAB */}
      {tab === 'source' && (
        <Card>
          <CardBody>
            <h2 className="mb-4 text-lg font-semibold text-zinc-900">Source preview</h2>
            <PreviewPane jobId={job.job_id} fileName={job.file_name} />
          </CardBody>
        </Card>
      )}

      {/* JSON TAB */}
      {/* ✅ Show effective canonical (with overrides applied) */}
      {tab === 'json' && <JsonViewer value={effectiveCanonical ?? {}} />}

      {/* DOWNLOADS TAB */}
      {tab === 'downloads' && (
        <Card>
          <CardBody className="space-y-4">
            <h2 className="text-lg font-semibold text-zinc-900">Downloads</h2>

            <p className="text-sm text-zinc-600">
              Download the generated NDA, SOW, source file or canonical JSON as needed.
            </p>

            <div className="flex flex-wrap gap-3">
              <Button
                variant="primary"
                onClick={() =>
                  import('@/lib/api/jobs')
                    .then((m) =>
                      m.downloadArtifact(
                        job.job_id,
                        'nda',
                        `${job.file_name.replace(/\.[^.]+$/, '')}-nda.pdf`
                      )
                    )
                    .catch((e) =>
                      toast.error(e instanceof Error ? e.message : 'Download failed')
                    )
                }
              >
                NDA
              </Button>

              <Button
                variant="primary"
                onClick={() =>
                  import('@/lib/api/jobs')
                    .then((m) =>
                      m.downloadArtifact(
                        job.job_id,
                        'sow',
                        `${job.file_name.replace(/\.[^.]+$/, '')}-sow.pdf`
                      )
                    )
                    .catch((e) =>
                      toast.error(e instanceof Error ? e.message : 'Download failed')
                    )
                }
              >
                SOW
              </Button>

              <Button
                variant="secondary"
                onClick={() =>
                  import('@/lib/api/jobs')
                    .then((m) => m.downloadArtifact(job.job_id, 'source', job.file_name))
                    .catch((e) =>
                      toast.error(e instanceof Error ? e.message : 'Download failed')
                    )
                }
              >
                Source
              </Button>

              <Button
                variant="secondary"
                onClick={() =>
                  import('@/lib/api/jobs')
                    .then((m) =>
                      m.downloadArtifact(job.job_id, 'canonical', `${job.job_id}-canonical.json`)
                    )
                    .catch((e) =>
                      toast.error(e instanceof Error ? e.message : 'Download failed')
                    )
                }
              >
                Canonical JSON
              </Button>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}