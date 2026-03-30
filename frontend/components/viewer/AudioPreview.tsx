'use client';

import { useEffect, useRef, useState } from 'react';
import { fetchSourceBlob } from '@/lib/api/jobs';
import { LoadingOverlay } from '@/components/shared/LoadingOverlay';

export function AudioPreview({ jobId }: { jobId: string }) {
  const [loading, setLoading] = useState(true);
  const [url, setUrl] = useState<string | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setUrl(null);

    fetchSourceBlob(jobId)
      .then((blob) => {
        if (cancelled) return;
        const objectUrl = URL.createObjectURL(blob);
        objectUrlRef.current = objectUrl;
        setUrl(objectUrl);
        setLoading(false);
      })
      .catch(() => setLoading(false));

    return () => {
      cancelled = true;
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, [jobId]);

  if (loading) return <LoadingOverlay label="Loading audio…" />;
  if (!url) return <div className="rounded-2xl border border-dashed border-zinc-200 p-6 text-sm text-zinc-500">Preview unavailable.</div>;
  return <audio controls src={url} className="w-full" />;
}