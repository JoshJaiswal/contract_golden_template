export const API_BASE_PATH = '/api/backend';

export const API_KEY =
  process.env.NEXT_PUBLIC_CONTRACT_API_KEY ?? '';

export const CONTRACT_TYPE_OPTIONS = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'nda', label: 'NDA' },
  { value: 'sow', label: 'SOW' },
  { value: 'both', label: 'Generate both' },
] as const;

export const SUPPORTED_EXTENSIONS = [
  '.pdf',
  '.docx',
  '.doc',
  '.eml',
  '.mp3',
  '.wav',
  '.m4a',
] as const;

export const JOB_STATUS_LABELS: Record<string, string> = {
  queued: 'Queued',
  processing: 'Processing',
  complete: 'Complete',
  failed: 'Failed',
};

export const JOB_STATUS_STYLES: Record<string, string> = {
  queued: 'bg-zinc-100 text-zinc-600 border-zinc-200',
  processing: 'bg-amber-50 text-amber-700 border-amber-200',
  complete: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  failed: 'bg-red-50 text-red-700 border-red-200',
};