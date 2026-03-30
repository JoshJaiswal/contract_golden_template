'use client';
import { Download, RefreshCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { downloadArtifact } from '@/lib/api/jobs';
import { toast } from 'sonner';
export function JobActions({ jobId, onRegenerate, regenLoading }: { jobId: string; onRegenerate: () => Promise<void>; regenLoading: boolean }) { return <div className="flex flex-wrap gap-3"><Button variant="primary" onClick={() => void onRegenerate()} disabled={regenLoading}><RefreshCcw className={`h-4 w-4 ${regenLoading ? 'animate-spin' : ''}`} />{regenLoading ? 'Regenerating…' : 'Regenerate'}</Button><Button variant="secondary" onClick={() => downloadArtifact(jobId, 'canonical', `${jobId}-canonical.json`).catch((e) => toast.error(e instanceof Error ? e.message : 'Download failed'))}><Download className="h-4 w-4" />Canonical</Button></div>; }