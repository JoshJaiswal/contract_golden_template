// lib/env.ts
export const API_BASE_PATH =
  typeof window !== 'undefined'
    ? ''  // client-side: use relative URLs via Next.js rewrite
    : process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const API_KEY =
  process.env.NEXT_PUBLIC_API_KEY || 'GoldenEY1479';