import type {
  AnalyzeResponse,
  CanonicalDocument,
  ContractType,
  JobRecord,
  JobsListResponse,
  RegenerateRequest,
} from './types';

import { requestBlob, requestJson, triggerDownload } from './client';

/* ------------------------- ANALYZE CONTRACT ------------------------- */
/* stays as-is, no /api/ prefix */
export function analyzeContract(file: File, contractType: ContractType) {
  const form = new FormData();
  form.append('file', file);
  form.append('contract_type', contractType);

  return requestJson<AnalyzeResponse>('/analyze', {
    method: 'POST',
    body: form,
  });
}

/* ---------------------------- JOB QUERIES ---------------------------- */

export function getJob(jobId: string) {
  return requestJson<JobRecord>(`/api/jobs/${jobId}`);
}

export function listJobs() {
  return requestJson<JobsListResponse>('/api/jobs');
}

export function regenerateJob(jobId: string, payload: RegenerateRequest) {
  return requestJson<AnalyzeResponse>(`/api/jobs/${jobId}/regenerate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

/* --------------------------- FILE DOWNLOADS --------------------------- */

export function fetchSourceBlob(jobId: string) {
  return requestBlob(`/api/download/${jobId}/source`);
}

export function fetchCanonicalBlob(jobId: string) {
  return requestBlob(`/api/download/${jobId}/canonical`);
}

export function fetchNdaBlob(jobId: string) {
  return requestBlob(`/api/download/${jobId}/nda`);
}

export function fetchSowBlob(jobId: string) {
  return requestBlob(`/api/download/${jobId}/sow`);
}

/* --------------------------- ARTIFACT DOWNLOAD ------------------------- */

export async function downloadArtifact(
  jobId: string,
  kind: 'nda' | 'sow' | 'canonical' | 'source',
  filename?: string
) {
  const blob =
    kind === 'nda'
      ? await fetchNdaBlob(jobId)
      : kind === 'sow'
      ? await fetchSowBlob(jobId)
      : kind === 'canonical'
      ? await fetchCanonicalBlob(jobId)
      : await fetchSourceBlob(jobId);

  triggerDownload(blob, filename || `${jobId}-${kind}`);
}