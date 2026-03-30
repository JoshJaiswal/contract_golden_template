'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useUploadJob } from '@/hooks/useUploadJob';
import { useAppStore } from '@/store/useAppStore';
import type { ContractType } from '@/lib/api/types';

const SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.eml', '.mp3', '.wav', '.m4a'];

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes < 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

export default function HomePage() {
  const router = useRouter();
  const { upload } = useUploadJob();
  const setJobId = useAppStore((s) => s.setJobId);

  const [file, setFile] = useState<File | null>(null);
  const [contractType, setContractType] = useState<ContractType>('auto');
  const [loading, setLoading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = useMemo(() => Boolean(file) && !loading, [file, loading]);

  const validateFile = (picked: File | null) => {
    if (!picked) return 'No file selected';

    const name = picked.name.toLowerCase();
    const isSupported = SUPPORTED_EXTENSIONS.some((ext) => name.endsWith(ext));

    if (!isSupported) {
      return `Unsupported file type. Allowed: ${SUPPORTED_EXTENSIONS.map((x) => x.replace('.', '').toUpperCase()).join(', ')}`;
    }

    return null;
  };

  const handleFileSelect = (picked: File | null) => {
    setError(null);
    setMessage(null);

    if (!picked) {
      setFile(null);
      return;
    }

    const validationError = validateFile(picked);
    if (validationError) {
      setFile(null);
      setError(validationError);
      return;
    }

    setFile(picked);
  };

  const onInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const picked = event.target.files?.[0] ?? null;
    handleFileSelect(picked);
  };

  const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);

    const picked = event.dataTransfer.files?.[0] ?? null;
    handleFileSelect(picked);
  };

  const onSubmit = async () => {
    if (!file || loading) return;

    setLoading(true);
    setError(null);
    setMessage(null);

    try {
      const jobId = await upload(file, contractType);
      setJobId(jobId);
      setMessage('Analysis started. Redirecting to the job workspace...');
      router.push(`/jobs/${jobId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-white text-zinc-900">
      <div className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex w-full max-w-7xl items-center gap-3 px-6 py-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FFE600] text-sm font-extrabold text-black shadow-sm">
            EY
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Contract Intelligence</h1>
            <p className="text-sm text-zinc-500">EY consulting-style workspace</p>
          </div>
        </div>
      </div>

      <div className="mx-auto grid w-full max-w-7xl gap-8 px-6 py-8 lg:grid-cols-[1.3fr_0.7fr]">
        <section className="space-y-6">
          <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
            <div
              onDragEnter={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                setIsDragging(false);
              }}
              onDrop={onDrop}
              className={[
                'flex min-h-[280px] flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition',
                isDragging ? 'border-[#FFE600] bg-yellow-50' : 'border-zinc-200 bg-zinc-50',
              ].join(' ')}
            >
              <div className="mb-4 rounded-full bg-white p-4 shadow-sm">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M12 16V4M7 9l5-5 5 5M5 20h14"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>

              <h2 className="text-2xl font-semibold tracking-tight">Drop a contract file here</h2>
              <p className="mt-3 max-w-xl text-sm leading-6 text-zinc-500">
                Upload PDF, DOCX, DOC, EML, MP3, WAV or M4A files. The backend will extract a canonical document and
                generate NDA or SOW outputs.
              </p>

              <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                <label className="inline-flex cursor-pointer items-center rounded-xl bg-[#FFE600] px-5 py-3 text-sm font-semibold text-black shadow-sm transition hover:opacity-90">
                  Choose file
                  <input
                    type="file"
                    className="hidden"
                    accept={SUPPORTED_EXTENSIONS.join(',')}
                    onChange={onInputChange}
                  />
                </label>

                <button
                  type="button"
                  onClick={() => handleFileSelect(null)}
                  className="rounded-xl border border-zinc-200 bg-white px-5 py-3 text-sm font-medium text-zinc-700 transition hover:bg-zinc-50"
                >
                  Clear
                </button>
              </div>

              <div className="mt-6 text-sm text-zinc-500">
                Supported files: PDF, DOCX, DOC, EML, MP3, WAV, M4A. Upload one contract at a time for analysis.
              </div>
            </div>

            <div className="mt-6 flex flex-col gap-3 rounded-2xl border border-zinc-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-medium text-zinc-900">
                  {file ? file.name : 'No file selected'}
                </div>
                <div className="text-xs text-zinc-500">
                  {file ? `${formatBytes(file.size)} • Ready to analyze` : 'Pick a single supported file to continue'}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span className="rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 text-xs font-medium text-zinc-600">
                  {file ? 'Ready' : 'Waiting'}
                </span>
              </div>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-5">
                <h3 className="text-base font-semibold">What happens next</h3>
                <ol className="mt-3 space-y-2 text-sm leading-6 text-zinc-600">
                  <li>1. File uploads to the backend analyzer.</li>
                  <li>2. A job is created and polled automatically.</li>
                  <li>3. The workspace opens with summary, conflicts, missing fields, source preview and downloads.</li>
                </ol>
              </div>

              <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-5">
                <h3 className="text-base font-semibold">Supported files</h3>
                <p className="mt-3 text-sm leading-6 text-zinc-600">
                  PDF, DOCX, DOC, EML, MP3, WAV, M4A. Upload one contract at a time for analysis.
                </p>
              </div>
            </div>

            {error ? (
              <div className="mt-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            ) : null}

            {message ? (
              <div className="mt-6 rounded-2xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
                {message}
              </div>
            ) : null}
          </div>
        </section>

        <aside className="space-y-6">
          <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
            <h3 className="text-base font-semibold tracking-tight">Contract type</h3>

            <label className="mt-4 block text-sm font-medium text-zinc-700">Choose analysis mode</label>
            <select
              value={contractType}
              onChange={(e) => setContractType(e.target.value as ContractType)}
              className="mt-2 w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-900 outline-none transition focus:border-[#FFE600] focus:ring-2 focus:ring-yellow-200"
            >
              <option value="auto">Auto-detect</option>
              <option value="nda">NDA</option>
              <option value="sow">SOW</option>
              <option value="both">Both</option>
            </select>

            <button
              type="button"
              onClick={onSubmit}
              disabled={!canSubmit}
              className="mt-6 inline-flex w-full items-center justify-center rounded-xl bg-[#FFE600] px-5 py-3 text-sm font-semibold text-black shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? 'Starting analysis…' : 'Start analysis'}
            </button>

            <p className="mt-3 text-xs leading-5 text-zinc-500">
              Upload a file first, then choose the desired contract mode. The job will open automatically after upload.
            </p>
          </div>

          <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
            <h3 className="text-base font-semibold tracking-tight">Need to know</h3>
            <div className="mt-4 space-y-4 text-sm leading-6 text-zinc-600">
              <p>
                The frontend sends the file to your FastAPI backend, receives a job id, and then navigates to the
                job workspace.
              </p>
              <p>
                If the backend restarts, in-memory jobs can disappear, so the app should always treat the URL as the
                source of truth.
              </p>
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
}