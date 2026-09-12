import axios from '../axios-config';
import { getApiBaseUrl, getSocialLoginBaseUrl } from '../baseUrl';
import { clearBirdrJourneySession } from '../birdrJourney';

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterCredentials {
  email: string;
  password: string;
  username?: string;
}

export interface TokenResponse {
  access: string;
  refresh: string;
  access_token?: string;
  refresh_token?: string;
}

export interface AuthError {
  message: string;
  details?: any;
}

/** Seconds before access token expiry to proactively refresh (clock skew + overlap). */
const ACCESS_REFRESH_SKEW_SEC = 120;

/** Same-tab login/logout. `storage` only fires in other tabs. */
export const AUTH_CHANGED_EVENT = 'birdr-auth-changed';

function notifyAuthChanged(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
}

let ensureAccessPromise: Promise<boolean> | null = null;

class AuthService {
  // getApiBaseUrl() returns correct origin for web and Capacitor (Android/iOS)
  private get baseURL(): string {
    return getApiBaseUrl();
  }

  /** Decode JWT payload for `exp` (SimpleJWT access tokens always include exp). */
  private getJwtExp(accessToken: string): number | null {
    try {
      const payload = accessToken.split('.')[1];
      if (!payload) return null;
      const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
      const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
      const json = atob(padded);
      const data = JSON.parse(json) as { exp?: number };
      return typeof data.exp === 'number' ? data.exp : null;
    } catch {
      return null;
    }
  }

  /**
   * Ensure stored access token is valid: refresh using refresh token when expired or near expiry.
   * Call before relying on the access token (e.g. after the app was idle for days).
   * Single-flight: concurrent callers share one refresh.
   */
  async ensureValidAccessToken(): Promise<boolean> {
    if (ensureAccessPromise) return ensureAccessPromise;
    ensureAccessPromise = this.doEnsureValidAccessToken().finally(() => {
      ensureAccessPromise = null;
    });
    return ensureAccessPromise;
  }

  private async doEnsureValidAccessToken(): Promise<boolean> {
    const refresh = this.getRefreshToken();
    const access = this.getAccessToken();
    if (!access && !refresh) return false;
    if (!refresh) {
      return !!access;
    }
    if (!access) {
      return this.persistRefresh(refresh);
    }
    const exp = this.getJwtExp(access);
    const now = Math.floor(Date.now() / 1000);
    if (exp != null && exp > now + ACCESS_REFRESH_SKEW_SEC) {
      return true;
    }
    if (exp == null) {
      return true;
    }
    return this.persistRefresh(refresh);
  }

  private async persistRefresh(refresh: string): Promise<boolean> {
    try {
      const tokens = await this.refreshToken(refresh);
      this.storeTokens({
        access: tokens.access,
        refresh: tokens.refresh || refresh,
      });
      return true;
    } catch {
      this.clearTokens();
      return false;
    }
  }

  /**
   * Login with email and password using Django JWT
   */
  async loginWithEmail(credentials: LoginCredentials): Promise<TokenResponse> {
    try {
      const response = await axios.post<TokenResponse>(
        `${this.baseURL}/token/`,
        {
          username: credentials.email,
          password: credentials.password,
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      return {
        access: response.data.access,
        refresh: response.data.refresh,
      };
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  /**
   * Register a new user with email and password
   */
  async register(credentials: RegisterCredentials): Promise<TokenResponse> {
    try {
      const response = await axios.post<any>(
        `${this.baseURL}/api/register/`,
        {
          email: credentials.email,
          password: credentials.password,
          username: credentials.username || credentials.email,
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      return {
        access: response.data.access,
        refresh: response.data.refresh,
      };
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  /**
   * Get the OAuth redirect URL for social login.
   * Uses getSocialLoginBaseUrl() so in local dev the browser hits the backend directly;
   * that way the session cookie and Google's callback URL match and "Session value state missing" is avoided.
   */
  getSocialLoginUrl(provider: 'google-oauth2' | 'apple-id', redirectUri: string): string {
    const oauthBase = getSocialLoginBaseUrl();
    return `${oauthBase}/auth/login/${provider}/?redirect_uri=${encodeURIComponent(redirectUri)}`;
  }

  /**
   * Convert OAuth code to JWT tokens using Django's convert-token endpoint
   * This is called from the OAuth callback
   */
  async convertOAuthToken(code: string, provider: 'google-oauth2' | 'apple-id'): Promise<TokenResponse> {
    try {
      const response = await axios.post<any>(
        `${this.baseURL}/token/convert-token/`,
        {
          grant_type: 'convert_token',
          backend: provider,
          token: code,
        }
      );

      return {
        access: response.data.access_token || response.data.access,
        refresh: response.data.refresh_token || response.data.refresh,
      };
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  /**
   * Login with Google OAuth token (alternative method if using Google Sign-In JS SDK)
   * This uses the custom GoogleLoginView endpoint
   */
  async loginWithGoogleToken(token: string): Promise<TokenResponse> {
    try {
      const response = await axios.post<TokenResponse>(
        `${this.baseURL}/api/google-login/`,
        {
          token: token,
        }
      );

      return {
        access: response.data.access,
        refresh: response.data.refresh,
      };
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  /**
   * Login with Apple identity token (e.g. from Sign in with Apple JS or native)
   * Optional user object for first-time sign-in: { name?: { firstName, lastName }, email? }
   */
  async loginWithAppleToken(
    identityToken: string,
    user?: { name?: { firstName?: string; lastName?: string }; email?: string }
  ): Promise<TokenResponse> {
    try {
      const response = await axios.post<TokenResponse>(
        `${this.baseURL}/api/apple-login/`,
        {
          identity_token: identityToken,
          user: user ?? undefined,
        }
      );

      return {
        access: response.data.access,
        refresh: response.data.refresh,
      };
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  /**
   * Request password reset - sends email with reset link
   */
  async requestPasswordReset(email: string, frontendUrl?: string): Promise<void> {
    try {
      await axios.post(
        `${this.baseURL}/api/password-reset/`,
        {
          email,
          frontend_url: frontendUrl || window.location.origin,
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  /**
   * Confirm password reset with token and set new password
   */
  async confirmPasswordReset(uid: string, token: string, newPassword: string): Promise<void> {
    try {
      await axios.post(
        `${this.baseURL}/api/password-reset/confirm/`,
        {
          uid,
          token,
          new_password: newPassword,
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  /**
   * Refresh access token using refresh token
   * Note: rest_framework_simplejwt returns {"access": "..."} not {"access_token": "..."}
   */
  async refreshToken(refreshToken: string): Promise<TokenResponse> {
    try {
      const response = await axios.post<{ access: string; refresh?: string }>(
        `${this.baseURL}/token/refresh/`,
        {
          refresh: refreshToken,
        }
      );

      // rest_framework_simplejwt returns {"access": "..."}
      return {
        access: response.data.access,
        refresh: response.data.refresh || refreshToken, // Keep old refresh token if new one not provided
      };
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  /**
   * Store tokens in localStorage
   */
  storeTokens(tokens: TokenResponse): void {
    localStorage.setItem('access_token', tokens.access);
    localStorage.setItem('refresh_token', tokens.refresh);
    localStorage.setItem('jw_token', tokens.access); // For backward compatibility
    notifyAuthChanged();
  }

  /**
   * Get stored access token
   */
  getAccessToken(): string | null {
    return localStorage.getItem('access_token') || localStorage.getItem('jw_token');
  }

  /**
   * Get stored refresh token
   */
  getRefreshToken(): string | null {
    return localStorage.getItem('refresh_token');
  }

  /**
   * Clear stored tokens
   */
  clearTokens(): void {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('jw_token');
    clearBirdrJourneySession();
    localStorage.removeItem('player-token');
    notifyAuthChanged();
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return !!this.getAccessToken();
  }

  private handleError(error: any): AuthError {
    if (error.response) {
      // Server responded with error
      const message = error.response.data?.detail || 
                     error.response.data?.error || 
                     error.response.data?.message ||
                     'Authentication failed';
      return {
        message,
        details: error.response.data,
      };
    } else if (error.request) {
      // Request made but no response
      return {
        message: 'Network error. Please check your connection.',
      };
    } else {
      // Something else happened
      return {
        message: error.message || 'An unexpected error occurred',
      };
    }
  }
}

export const authService = new AuthService();

