import { analyzeContract } from
'@/lib/api/jobs'

import { ContractType } from '@/lib/api/types'

export const useUploadJob = () => {
    const upload = async (file: File,
    contractType: ContractType) => {
    const res = await analyzeContract(file, contractType)
    return res.job_id
    }
    return {upload}
}