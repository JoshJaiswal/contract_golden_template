import { useEffect, useState } from 'react'
import { listJobs } from '@/lib/api/jobs'
import type { JobRecord } from '@/lib/api/types'

export const useJobList = () => {
    const [jobs, setJobs] = useState<JobRecord[]>([]);

    useEffect(() => {
        listJobs().then(data => setJobs(data.jobs));
    }, []);

    return { jobs };
};