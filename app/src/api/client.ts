// API Client - Centralized HTTP client with configurable base URL and headers
import { getApiBaseUrl } from './baseUrl';
import { clientInfoHeaders } from './clientInfo';

export interface ApiClientConfig {
  baseURL?: string;
  getAuthToken?: () => string | null;
  getHeaders?: () => Record<string, string>;
}

/** Prefer JWT (logged-in user) so auth endpoints use request.user; fall back to player token. */
function defaultGetAuthToken(): string | null {
  return (
    localStorage.getItem('access_token') ||
    localStorage.getItem('jw_token') ||
    localStorage.getItem('player-token')
  );
}

export class ApiClient {
  private baseURLOverride: string | undefined;
  private getAuthToken: () => string | null;
  private getHeaders: () => Record<string, string>;

  constructor(config: ApiClientConfig = {}) {
    this.baseURLOverride = config.baseURL !== undefined && config.baseURL !== '' ? config.baseURL : undefined;
    this.getAuthToken = config.getAuthToken || defaultGetAuthToken;
    this.getHeaders = config.getHeaders || (() => ({
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      'Cache-Control': 'no-cache, no-store, must-revalidate',
      'Pragma': 'no-cache',
      'Expires': '0',
      ...clientInfoHeaders(),
    }));
  }

  private getBaseURL(): string {
    return this.baseURLOverride ?? getApiBaseUrl();
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.getBaseURL()}${endpoint}`;
    const token = this.getAuthToken();
    const defaultHeaders = this.getHeaders();

    const headers: Record<string, string> = {
      ...defaultHeaders,
      ...(options.headers as Record<string, string> || {}),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
      cache: options.cache || 'no-store',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(`API Error: ${response.status} - ${JSON.stringify(errorData)}`);
    }

    return response.json();
  }

  async get<T>(endpoint: string, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
  }

  async post<T>(endpoint: string, data?: unknown, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async patch<T>(endpoint: string, data?: unknown, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  }
}

// Default client instance
export const apiClient = new ApiClient();

