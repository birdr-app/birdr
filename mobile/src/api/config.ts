import Constants from 'expo-constants';

const extra = Constants.expoConfig?.extra as { apiBaseUrl?: string } | undefined;

/** Override with EXPO_PUBLIC_API_URL in mobile/.env for local Django (e.g. http://10.0.2.2:8000). */
export const API_BASE_URL = (extra?.apiBaseUrl || 'https://motmot.club').replace(/\/$/, '');

/**
 * Web OAuth 2.0 client ID from Google Console (type "Web application").
 * This is NOT the Android client ID — it's the *web* client ID that the Android app
 * sends to GoogleSignin.configure({ webClientId }) so that Google returns an idToken.
 */
export const GOOGLE_WEB_CLIENT_ID = '56451813101-pab6limmhoe0tqhtf0oel1tht3ja0rqq.apps.googleusercontent.com';

/**
 * iOS OAuth client ID from Google Console (type "iOS").
 * Required for Google Sign-In on iOS; pass as iosClientId to GoogleSignin.configure().
 */
export const GOOGLE_IOS_CLIENT_ID = '56451813101-kkjv7e0agsujmmtuuq5gs6mdkumdmp71.apps.googleusercontent.com';

export function apiUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${p}`;
}

/** WebSocket URL for game (wss on production). */
export function getWebSocketUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`;
  const wsBase = API_BASE_URL.replace(/^https/, 'wss').replace(/^http/, 'ws');
  return `${wsBase}${p}`;
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

/** Resolve API media paths (/media/...). Keep http for local Django; upgrade other http to https. */
export function resolveMediaUrl(url: string | null | undefined): string | null {
  if (!url?.trim()) return null;
  const trimmed = url.trim();
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    try {
      const parsed = new URL(trimmed);
      if (isLocalHostname(parsed.hostname)) {
        if (parsed.protocol === 'https:') parsed.protocol = 'http:';
        return parsed.toString();
      }
    } catch {
      // fall through
    }
    if (trimmed.startsWith('http://')) return `https://${trimmed.slice(7)}`;
    return trimmed;
  }
  if (trimmed.startsWith('/')) return apiUrl(trimmed);
  return trimmed;
}
