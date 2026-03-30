'use client';
import { useMemo } from 'react';
import type { JobRecord } from '@/lib/api/types';
export function useDownloadUrls(job?: JobRecord | null) { return useMemo(() => job?.download_urls ?? {}, [job]); }