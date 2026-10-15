import { apiUrl } from '../api/baseUrl';

const SESSION_KEY = 'birdr_analytics_sid';
const LANDING_REFERER_KEY = 'birdr_analytics_landing_referer';
let lastTrackedPath = '';
let lastTrackedAt = 0;

function getSessionId(): string {
  try {
    let sid = localStorage.getItem(SESSION_KEY);
    if (!sid) {
      sid = crypto.randomUUID();
      localStorage.setItem(SESSION_KEY, sid);
    }
    return sid;
  } catch {
    return 'anonymous';
  }
}

function getPlatform(): 'web' | 'ios' | 'android' {
  if (typeof window !== 'undefined' && window.Capacitor?.isNativePlatform?.()) {
    const native = window.Capacitor.getPlatform?.();
    if (native === 'ios' || native === 'android') {
      return native;
    }
  }
  return 'web';
}

/** Keep the first external document.referrer for the browser session. */
function landingReferer(): string {
  if (typeof document === 'undefined') {
    return '';
  }
  try {
    const stored = sessionStorage.getItem(LANDING_REFERER_KEY);
    if (stored !== null) {
      return stored;
    }
    const current = document.referrer || '';
    sessionStorage.setItem(LANDING_REFERER_KEY, current);
    return current;
  } catch {
    return document.referrer || '';
  }
}

function utmFromLocation(): {
  utm_source: string;
  utm_medium: string;
  utm_campaign: string;
} {
  if (typeof window === 'undefined') {
    return { utm_source: '', utm_medium: '', utm_campaign: '' };
  }
  const params = new URLSearchParams(window.location.search);
  return {
    utm_source: params.get('utm_source') || '',
    utm_medium: params.get('utm_medium') || '',
    utm_campaign: params.get('utm_campaign') || '',
  };
}

export function trackPageView(path: string, countryCode?: string): void {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  const now = Date.now();
  if (normalized === lastTrackedPath && now - lastTrackedAt < 2000) {
    return;
  }
  lastTrackedPath = normalized;
  lastTrackedAt = now;

  const utm = utmFromLocation();
  const body = JSON.stringify({
    path: normalized,
    event_type: 'page_view',
    platform: getPlatform(),
    session_key: getSessionId(),
    country_code: countryCode || '',
    referer: landingReferer(),
    ...utm,
  });

  const url = apiUrl('/api/analytics/event/');
  if (navigator.sendBeacon) {
    navigator.sendBeacon(url, new Blob([body], { type: 'application/json' }));
    return;
  }

  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
    keepalive: true,
  }).catch(() => {});
}

export function trackFeature(path: string, metadata?: Record<string, unknown>, countryCode?: string): void {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  const utm = utmFromLocation();
  const body = JSON.stringify({
    path: normalized,
    event_type: 'feature',
    platform: getPlatform(),
    session_key: getSessionId(),
    country_code: countryCode || '',
    referer: landingReferer(),
    ...utm,
    metadata: metadata || {},
  });

  fetch(apiUrl('/api/analytics/event/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
    keepalive: true,
  }).catch(() => {});
}
