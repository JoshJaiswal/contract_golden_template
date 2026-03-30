import type { ContractType, JobRecord } from './api/types';

export function cnKeyToLabel(key: string) {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (m) => m.toUpperCase())
    .trim();
}

export function formatBytes(bytes?: number | null) {
  if (!bytes || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const idx = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, idx)).toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

export function formatDateTime(iso?: string | null) {
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function formatContractType(type?: ContractType | string) {
  if (!type) return '—';
  return type === 'auto' ? 'Auto-detect' : type === 'both' ? 'Both' : String(type).toUpperCase();
}

export function getFileExtension(name?: string | null) {
  if (!name) return '';
  const idx = name.lastIndexOf('.');
  return idx >= 0 ? name.slice(idx).toLowerCase() : '';
}

export function extractJobStats(jobs: JobRecord[]) {
  const counts = { total: jobs.length, queued: 0, processing: 0, complete: 0, failed: 0 };
  for (const job of jobs) if (job.status in counts) counts[job.status as keyof typeof counts] += 1;
  return counts;
}

export function humanizeField(field: string) {
  return cnKeyToLabel(field.replace(/\./g, ' '));
}

function asArray(value: unknown): any[] {
  if (Array.isArray(value)) return value;
  if (value && typeof value === 'object') return Object.values(value as Record<string, unknown>);
  return [];
}

export function extractSummarySections(canonical: Record<string, any> | null | undefined) {
  if (!canonical) return [];
  const sections = ['parties', 'scope', 'commercials', 'confidentiality'];
  return sections
    .map((section) => {
      const value = canonical[section];
      if (!value || typeof value !== 'object') return null;
      const items = Object.entries(value)
        .filter(([, v]) => typeof v !== 'object' || v === null)
        .map(([key, value]) => ({ key, value }));
      if (!items.length) return null;
      return { title: cnKeyToLabel(section), items };
    })
    .filter(Boolean) as { title: string; items: { key: string; value: any }[] }[];
}

export function extractConflicts(canonical: Record<string, any> | null | undefined) {
  const raw = canonical?.conflicts ?? canonical?.review?.conflicts ?? canonical?.conflictList;
  const items = asArray(raw);
  return items.map((item, index) => {
    const obj = item && typeof item === 'object' ? item : { value: item };
    const field = String(obj.field ?? obj.name ?? obj.key ?? `conflict_${index + 1}`);
    return {
      field,
      label: String(obj.label ?? humanizeField(field)),
      current: String(obj.current ?? obj.left ?? obj.source ?? obj.value ?? ''),
      proposed: String(obj.proposed ?? obj.right ?? obj.alternative ?? obj.suggestion ?? ''),
      note: String(obj.note ?? obj.explanation ?? obj.reason ?? ''),
      options: asArray(obj.options ?? obj.choices),
    };
  });
}

export function extractMissingFields(canonical: Record<string, any> | null | undefined) {
  const raw = canonical?.missingFields ?? canonical?.missing_fields ?? canonical?.missing ?? canonical?.gaps;
  const groups = asArray(raw);
  return groups.map((group: any, index) => {
    if (group && typeof group === 'object' && !Array.isArray(group)) {
      const name = String(group.section ?? group.group ?? group.title ?? group.name ?? `Section ${index + 1}`);
      const items = asArray(group.items ?? group.fields ?? group.missing).map((item: any, itemIndex) => {
        if (item && typeof item === 'object') {
          const field = String(item.field ?? item.name ?? item.key ?? `field_${itemIndex + 1}`);
          return { field, hint: String(item.hint ?? item.note ?? item.description ?? ''), suggested: String(item.suggested ?? item.value ?? '') };
        }
        return { field: String(item), hint: '', suggested: '' };
      });
      return { name, items };
    }
    return { name: `Section ${index + 1}`, items: [{ field: String(group), hint: '', suggested: '' }] };
  });
}

export function safeJson(value: unknown) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '{}';
  }
}