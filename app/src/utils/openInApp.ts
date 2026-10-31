import { getMobileOS } from './device';

const SKIP_PREFIXES = [
  '/join',
  '/login',
  '/game/',
  '/reset-password',
  '/forgot-password',
];

function isCapacitor(): boolean {
  return !!(typeof window !== 'undefined' && window.Capacitor?.isNativePlatform?.());
}

export function shouldTryOpenInApp(pathname: string): boolean {
  if (typeof window === 'undefined') return false;
  if (isCapacitor()) return false;
  if (pathname === '/' || pathname === '') return false;
  if (!getMobileOS()) return false;
  for (const prefix of SKIP_PREFIXES) {
    if (pathname.startsWith(prefix)) return false;
  }
  return true;
}

/** Map a web path to a Motmot app deep link, or null to skip. */
export function buildAppDeepLink(pathname: string): string | null {
  const path = pathname.replace(/\/+$/, '') || '/';

  const updateMatch = path.match(/^\/updates\/(\d+)$/);
  if (updateMatch) {
    return `birdr://updates/${updateMatch[1]}`;
  }

  return 'birdr://home';
}

export function tryOpenInApp(pathname: string): void {
  const deepLink = buildAppDeepLink(pathname);
  if (!deepLink) return;
  window.location.href = deepLink;
}

export const OPEN_IN_APP_SESSION_KEY = 'birdr_app_open_attempted';
