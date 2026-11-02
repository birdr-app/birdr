/**
 * Central API base URL for all requests.
 * When running in Capacitor (Android/iOS), the app origin is capacitor://localhost,
 * so we must use the production API URL. On web, use same origin or REACT_APP_API_URL.
 */
declare global {
  interface Window {
    Capacitor?: {
      isNativePlatform: () => boolean;
      getPlatform: () => string;
    };
  }
}

export function getApiBaseUrl(): string {
  if (typeof window === 'undefined') {
    return process.env.REACT_APP_API_URL || 'https://motmot.club';
  }
  // Capacitor: app runs from capacitor://localhost; API must be absolute
  if (window.Capacitor?.isNativePlatform?.()) {
    return process.env.REACT_APP_API_URL || 'https://motmot.club';
  }
  return process.env.REACT_APP_API_URL || window.location.origin;
}

/**
 * Base URL for the OAuth start (e.g. /auth/login/google-oauth2/).
 * Must be the same host that receives the OAuth callback, so the session cookie is sent.
 * In local dev we use the backend URL directly so login and callback both hit the same origin.
 */
export function getSocialLoginBaseUrl(): string {
  if (typeof window === 'undefined') {
    return process.env.REACT_APP_API_URL || 'https://motmot.club';
  }
  if (window.Capacitor?.isNativePlatform?.()) {
    return process.env.REACT_APP_API_URL || 'https://motmot.club';
  }
  const isLocalDev =
    window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  if (isLocalDev) {
    return process.env.REACT_APP_API_URL || 'http://127.0.0.1:8050';
  }
  return getApiBaseUrl();
}

/** Full URL for an API path (e.g. apiUrl('/api/player/') for fetch and relative paths). */
export function apiUrl(path: string): string {
  const base = getApiBaseUrl();
  const p = path.startsWith('/') ? path : `/${path}`;
  return base + p;
}

/** WebSocket URL for the same host as the API (ws in dev, wss in production/Capacitor). */
export function getWebSocketUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`;
  if (typeof window !== 'undefined' && window.location.host === 'localhost:3000') {
    return `ws://127.0.0.1:8050${p}`;
  }
  const base = getApiBaseUrl();
  const wsBase = base.replace(/^https/, 'wss').replace(/^http/, 'ws');
  return wsBase + p;
}

function isLocalHostname(hostname: string): boolean {
  return (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname === '0.0.0.0' ||
    hostname === '10.0.2.2' ||
    hostname.endsWith('.local') ||
    hostname.startsWith('192.168.') ||
    hostname.startsWith('10.') ||
    /^172\.(1[6-9]|2\d|3[0-1])\./.test(hostname)
  );
}

/**
 * Resolve API media paths (/media/...) for <img> tags.
 * Production http URLs are upgraded to https. Local Django URLs stay http
 * (or same-origin /media/... on the CRA dev server) so icons load.
 */
export function resolveMediaUrl(url: string | null | undefined): string | null {
  if (!url?.trim()) return null;
  const trimmed = url.trim();

  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    try {
      const parsed = new URL(trimmed);
      if (isLocalHostname(parsed.hostname)) {
        if (parsed.protocol === 'https:') {
          parsed.protocol = 'http:';
        }
        const onLocalWeb =
          typeof window !== 'undefined' &&
          isLocalHostname(window.location.hostname) &&
          parsed.pathname.startsWith('/media/');
        if (onLocalWeb) {
          return `${parsed.pathname}${parsed.search}`;
        }
        return parsed.toString();
      }
    } catch {
      // fall through
    }
    if (trimmed.startsWith('http://')) {
      return `https://${trimmed.slice(7)}`;
    }
    return trimmed;
  }

  if (trimmed.startsWith('/')) return apiUrl(trimmed);
  return trimmed;
}
