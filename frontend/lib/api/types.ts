export type JobStatus = 'queued' | 'processing' | 'complete' | 'failed';
export type ContractType = 'auto' | 'nda' | 'sow' | 'both';
export interface JobRecord { job_id: string; status: JobStatus; created_at: string; completed_at?: string | null; file_name: string; contract_type: ContractType; outputs?: Record<string, string> | null; error?: string | null; download_urls?: Record<string, string>; }
export interface AnalyzeResponse { job_id: string; status: JobStatus; message: string; poll_url: string; }
export interface JobsListResponse { total: number; jobs: JobRecord[]; }
export interface RegenerateRequest { overrides: Record<string, string>; dismissed_fields: string[]; }
export type CanonicalDocument = Record<string, any>;