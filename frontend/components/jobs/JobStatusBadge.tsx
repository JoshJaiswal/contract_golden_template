import { Badge } from '@/components/ui/badge';
import { JOB_STATUS_LABELS } from '@/lib/constants';
export function JobStatusBadge({ status }: { status: string }) { const tone = status === 'complete' ? 'success' : status === 'failed' ? 'danger' : status === 'processing' ? 'warning' : 'neutral'; return <Badge tone={tone as any}>{JOB_STATUS_LABELS[status] ?? status}</Badge>; }