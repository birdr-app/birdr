import { apiUrl } from './config';

export const API_PROBE_TIMEOUT_MS = 8000;

export type AppVersionResponse = {
  min_version: string;
  store_version: string;
  app_store_url: string;
  play_store_url: string;
  store_release_label_ios?: string | null;
  store_release_label_android?: string | null;
};

export type AppApiProbeResult =
  | { reachable: true; data: AppVersionResponse }
  | { reachable: false };

function timeoutSignal(ms: number): { signal: AbortSignal; cancel: () => void } {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  return {
    signal: controller.signal,
    cancel: () => clearTimeout(timer),
  };
}

/** Lightweight reachability check used for maintenance and force-update. */
export async function probeAppApi(): Promise<AppApiProbeResult> {
  const { signal, cancel } = timeoutSignal(API_PROBE_TIMEOUT_MS);
  try {
    const url = `${apiUrl('/api/app-version/')}?_=${Date.now()}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        'Cache-Control': 'no-cache',
        Pragma: 'no-cache',
      },
      cache: 'no-store',
      signal,
    });
    if (!response.ok) return { reachable: false };
    const data = (await response.json()) as AppVersionResponse;
    return { reachable: true, data };
  } catch {
    return { reachable: false };
  } finally {
    cancel();
  }
}

export async function fetchAppVersionRequirements(): Promise<AppVersionResponse | null> {
  const result = await probeAppApi();
  return result.reachable ? result.data : null;
}
