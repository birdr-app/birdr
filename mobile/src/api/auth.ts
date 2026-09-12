import { apiUrl } from './config';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { clientInfoHeaders } from './clientInfo';

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

/** Seconds before access token expiry to proactively refresh. */
const ACCESS_REFRESH_SKEW_SEC = 120;

let ensureAccessInFlight: Promise<string | null> | null = null;

function decodeJwtExp(accessToken: string): number | null {
  try {
    const part = accessToken.split('.')[1];
    if (!part) return null;
    const base64 = part.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    const json = globalThis.atob(padded);
    const data = JSON.parse(json) as { exp?: number };
    return typeof data.exp === 'number' ? data.exp : null;
  } catch {
    return null;
  }
}

async function persistRefresh(refresh: string): Promise<string | null> {
  const response = await fetch(apiUrl('/token/refresh/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.access) {
    await clearTokens();
    return null;
  }
  await storeTokens({
    access: data.access,
    refresh: data.refresh ?? refresh,
  });
  return data.access as string;
}

/**
 * Return a valid access token, refreshing with the refresh token when expired or near expiry.
 * Clears tokens and returns null if the session cannot be renewed.
 */
export async function ensureFreshAccessToken(): Promise<string | null> {
  if (ensureAccessInFlight) return ensureAccessInFlight;

  ensureAccessInFlight = (async (): Promise<string | null> => {
    const refresh = await getRefreshToken();
    const access = await getAccessToken();
    if (!access && !refresh) return null;
    if (!refresh) return access;
    if (!access) return persistRefresh(refresh);

    const exp = decodeJwtExp(access);
    const now = Math.floor(Date.now() / 1000);
    if (exp != null && exp > now + ACCESS_REFRESH_SKEW_SEC) {
      return access;
    }
    if (exp == null) {
      return access;
    }
    return persistRefresh(refresh);
  })().finally(() => {
    ensureAccessInFlight = null;
  });

  return ensureAccessInFlight;
}

export type TokenResponse = {
  access: string;
  refresh: string;
  access_token?: string;
  refresh_token?: string;
};

export type AuthError = { message: string; details?: unknown };

function getStored(key: string): Promise<string | null> {
  return AsyncStorage.getItem(key);
}

export async function loginWithEmail(email: string, password: string): Promise<TokenResponse> {
  const response = await fetch(apiUrl('/token/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: email, password }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg = data.detail ?? data.error ?? data.message ?? 'Login failed';
    throw { message: typeof msg === 'string' ? msg : 'Login failed' };
  }
  return {
    access: data.access ?? data.access_token,
    refresh: data.refresh ?? data.refresh_token,
  };
}

export async function register(
  email: string,
  password: string,
  username?: string
): Promise<TokenResponse> {
  const response = await fetch(apiUrl('/api/register/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      password,
      username: username || email,
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg = data.detail ?? data.error ?? data.message ?? 'Registration failed';
    throw { message: typeof msg === 'string' ? msg : 'Registration failed' };
  }
  return {
    access: data.access ?? data.access_token,
    refresh: data.refresh ?? data.refresh_token,
  };
}

export function getSocialLoginUrl(
  provider: 'google-oauth2' | 'apple-id',
  redirectUri: string
): string {
  return `${apiUrl('/auth/login/' + provider + '/')}?redirect_uri=${encodeURIComponent(redirectUri)}`;
}

export async function convertOAuthToken(
  code: string,
  provider: 'google-oauth2' | 'apple-id'
): Promise<TokenResponse> {
  const response = await fetch(apiUrl('/token/convert-token/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      grant_type: 'convert_token',
      backend: provider,
      token: code,
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg = data.detail ?? data.error ?? data.message ?? 'Authentication failed';
    throw { message: typeof msg === 'string' ? msg : 'Authentication failed' };
  }
  return {
    access: data.access_token ?? data.access,
    refresh: data.refresh_token ?? data.refresh,
  };
}

/** Log in with Apple identity token (from native Sign in with Apple on iOS). Stays in-app, no browser. */
export async function loginWithAppleToken(identityToken: string, user?: { email?: string | null; fullName?: { givenName?: string; familyName?: string } | null }): Promise<TokenResponse> {
  const response = await fetch(apiUrl('/api/apple-login/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      identity_token: identityToken,
      ...(user && (user.email || user.fullName) && {
        user: {
          email: (user.email && String(user.email).trim()) || undefined,
          name: user.fullName
            ? {
                firstName: (user.fullName.givenName != null && String(user.fullName.givenName).trim()) || '',
                lastName: (user.fullName.familyName != null && String(user.fullName.familyName).trim()) || '',
              }
            : undefined,
        },
      }),
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg =
      (typeof data.error === 'string' ? data.error : null) ??
      data.detail ??
      'Apple sign-in failed';
    if (__DEV__) {
      console.error('[Apple sign-in]', response.status, data);
    }
    throw { message: typeof msg === 'string' ? msg : 'Apple sign-in failed' };
  }
  return {
    access: data.access,
    refresh: data.refresh,
  };
}

/** Log in with a Google ID token (from native in-app Google Sign-In). Stays in-app, no browser. */
export async function loginWithGoogleToken(idToken: string): Promise<TokenResponse> {
  const response = await fetch(apiUrl('/api/google-login/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: idToken }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg =
      (typeof data.message === 'string' ? data.message : null) ??
      data.error ??
      data.detail ??
      'Google sign-in failed';
    if (__DEV__) {
      console.error('[Google sign-in]', response.status, data);
    }
    throw { message: typeof msg === 'string' ? msg : 'Google sign-in failed' };
  }
  return {
    access: data.access,
    refresh: data.refresh,
  };
}

export async function storeTokens(tokens: TokenResponse): Promise<void> {
  await AsyncStorage.multiSet([
    [ACCESS_TOKEN_KEY, tokens.access],
    [REFRESH_TOKEN_KEY, tokens.refresh],
  ]);
}

export async function getAccessToken(): Promise<string | null> {
  return getStored(ACCESS_TOKEN_KEY);
}

/** Returns headers with Bearer token for authenticated API calls (refreshes access token when needed). */
export async function getAuthHeaders(): Promise<HeadersInit> {
  const token = await ensureFreshAccessToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...clientInfoHeaders(),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

export async function getRefreshToken(): Promise<string | null> {
  return getStored(REFRESH_TOKEN_KEY);
}

export async function clearTokens(): Promise<void> {
  await AsyncStorage.multiRemove([ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY]);
}

export async function isAuthenticated(): Promise<boolean> {
  const t = await getAccessToken();
  return !!t;
}

/** Request password reset email. Link in email goes to frontend_url (e.g. https://birdr.pro for web reset page). */
export async function requestPasswordReset(
  email: string,
  frontendUrl?: string
): Promise<void> {
  const url = apiUrl('/api/password-reset/');
  const body: { email: string; frontend_url?: string } = { email };
  if (frontendUrl) body.frontend_url = frontendUrl;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg = data.detail ?? data.email?.[0] ?? data.error ?? data.message ?? 'Failed to send reset email';
    throw { message: typeof msg === 'string' ? msg : 'Failed to send reset email' };
  }
}

/** Confirm password reset with token from email link. */
export async function confirmPasswordReset(
  uid: string,
  token: string,
  newPassword: string
): Promise<void> {
  const response = await fetch(apiUrl('/api/password-reset/confirm/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ uid, token, new_password: newPassword }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg = data.error ?? data.detail ?? data.message ?? 'Invalid or expired reset link';
    throw { message: typeof msg === 'string' ? msg : 'Invalid or expired reset link' };
  }
}
