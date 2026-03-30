import { JobRow } from './JobRow';
import type { JobRecord } from '@/lib/api/types';
import { Card, CardBody } from '@/components/ui/card';
export function JobList({ jobs }: { jobs: JobRecord[] }) { if (!jobs.length) return <Card><CardBody><p className="text-sm text-zinc-500">No jobs yet. Upload a file to start the first analysis.</p></CardBody></Card>; return <div className="space-y-3">{jobs.map((job) => <JobRow key={job.job_id} job={job} />)}</div>; }