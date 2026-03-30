import { API_BASE_PATH, API_KEY } from '@/lib/constants';

export class APIError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload?: unknown) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.payload = payload;
  }
}

function authHeaders(extra?: HeadersInit) {
  const headers = new Headers(extra);

  if (API_KEY) {
    headers.set('X-API-Key', API_KEY);
  }

  return headers;
}

export async function requestJson<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_BASE_PATH}${path}`, {
    ...init,
    headers: authHeaders(init?.headers),
    cache: 'no-store',
  });

  if (!response.ok) {
    let payload: unknown = null;

    try {
      payload = await response.json();
    } catch {
      try {
        payload = await response.text();
      } catch {
        payload = null;
      }
    }

    throw new APIError(
      (payload as any)?.detail ||
        `Request failed with status ${response.status}`,
      response.status,
      payload
    );
  }

  return response.json() as Promise<T>;
}

export async function requestBlob(
  path: string,
  init?: RequestInit
): Promise<Blob> {
  const response = await fetch(`${API_BASE_PATH}${path}`, {
    ...init,
    headers: authHeaders(init?.headers),
    cache: 'no-store',
  });

  if (!response.ok) {
    let payload: unknown = null;

    try {
      payload = await response.json();
    } catch {
      try {
        payload = await response.text();
      } catch {
        payload = null;
      }
    }

    throw new APIError(
      (payload as any)?.detail ||
        `Request failed with status ${response.status}`,
      response.status,
      payload
    );
  }

  return response.blob();
}

export function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');

  a.href = url;
  a.download = filename;
  a.style.display = 'none';

  document.body.appendChild(a);
  a.click();

  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}