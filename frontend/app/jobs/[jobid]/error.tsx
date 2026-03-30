'use client';

import { ArrowLeft, TriangleAlert } from 'lucide-react';
import Link from 'next/link';

export default function JobError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-white p-6">
      <div className="max-w-md rounded-2xl border border-zinc-200 bg-white p-8 shadow-soft">
        <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-yellow-100 text-zinc-900">
          <TriangleAlert className="h-5 w-5" />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Job workspace error</h1>
        <p className="mt-2 text-sm text-zinc-600">The workspace could not be loaded. Try again or return to the dashboard.</p>
        <div className="mt-6 flex gap-3">
          <button onClick={reset} className="inline-flex items-center gap-2 rounded-xl bg-yellow-300 px-4 py-2 text-sm font-semibold text-zinc-900 hover:bg-yellow-400">
            Retry
          </button>
          <Link href="/jobs" className="inline-flex items-center gap-2 rounded-xl border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-900 hover:bg-zinc-50">
            <ArrowLeft className="h-4 w-4" />
            Back to jobs
          </Link>
        </div>
      </div>
    </main>
  );
}