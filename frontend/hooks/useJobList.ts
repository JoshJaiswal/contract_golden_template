import {useEffect, useState } from 'react'
import { getJob } from '@/lib/api/jobs'

export const useJobList = () => {
    const [jobs, setJobs] = useState([])

    useEffect(() => {
        getJobs().then(setJobs)
    }, [])

    return { jobs }
}