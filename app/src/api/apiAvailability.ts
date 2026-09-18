import { apiUrl } from './baseUrl';

export const API_PROBE_TIMEOUT_MS = 8000;

export type ApiAvailability = 'reachable' | 'unreachable';

async function fetchWithTimeout(url: string, init: RequestInit, ms: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

/** Lightweight reachability check against a public API endpoint. */
export async function probeApiAvailability(): Promise<ApiAvailability> {
  try {
    const response = await fetchWithTimeout(
      `${apiUrl('/api/app-version/')}?_=${Date.now()}`,
      {
        method: 'GET',
        headers: {
          Accept: 'application/json',
          'Cache-Control': 'no-cache',
          Pragma: 'no-cache',
        },
        cache: 'no-store',
      },
      API_PROBE_TIMEOUT_MS,
    );
    return response.ok ? 'reachable' : 'unreachable';
  } catch {
    return 'unreachable';
  }
}
