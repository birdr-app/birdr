import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { authService } from './services/auth.service';
import { getApiBaseUrl } from './baseUrl';
import { clientInfoHeaders } from './clientInfo';

// Use shared API base URL so requests work in Capacitor (Android/iOS) as well as web
axios.defaults.baseURL = getApiBaseUrl();

// Create a separate axios instance for refresh calls to avoid interceptor loops
const refreshAxios = axios.create();
(refreshAxios.defaults as { baseURL?: string }).baseURL = getApiBaseUrl();

// Flag to prevent multiple simultaneous refresh attempts
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: any) => void;
  reject: (error?: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  
  failedQueue = [];
};

// Request interceptor: Add Bearer token to all requests
axios.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const infoHeaders = clientInfoHeaders();
    if (config.headers) {
      Object.entries(infoHeaders).forEach(([key, value]) => {
        if (!config.headers[key]) {
          config.headers[key] = value;
        }
      });
    }
    // For endpoints that allow anonymous access, only add token if we have a valid refresh token
    // This allows anonymous users to use these endpoints, but still links authenticated users
    const anonymousEndpoints = ['/api/player/', '/api/compare/'];
    const isCommunityCompare = config.url?.includes('/api/compare/community/');
    const isAnonymousEndpoint = !isCommunityCompare && anonymousEndpoints.some(endpoint => config.url?.includes(endpoint));
    
    if (isAnonymousEndpoint && (config.method === 'post' || config.method === 'get')) {
      const refreshToken = authService.getRefreshToken();
      // Only add Authorization header if we have a refresh token (indicating valid auth)
      if (!refreshToken) {
        // No refresh token means user is anonymous, don't add Authorization header
        // Also explicitly remove any existing Authorization header to be safe
        if (config.headers) {
          delete config.headers.Authorization;
        }
        return config;
      }
      // User is authenticated, proceed to add token below
    }
    
    // Always get fresh token from storage (in case it was updated)
    // Only add token if not already set (allows manual override)
    if (config.headers && !config.headers.Authorization) {
      const token = authService.getAccessToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } else if (config.headers?.Authorization) {
      // If Authorization is already set, make sure it's using the latest token
      // This ensures we use the refreshed token even if it was set before refresh
      const currentToken = authService.getAccessToken();
      if (currentToken && config.headers.Authorization !== `Bearer ${currentToken}`) {
        config.headers.Authorization = `Bearer ${currentToken}`;
      } else if (!currentToken && isAnonymousEndpoint) {
        // If we're on an anonymous endpoint and no token exists, remove the header
        delete config.headers.Authorization;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor: Handle 401 errors and refresh tokens
axios.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // If error is 401 and we haven't already retried
    // Also skip if this is a refresh token request to avoid infinite loops
    if (error.response?.status === 401 && !originalRequest._retry && !originalRequest.url?.includes('/token/refresh/')) {
      if (isRefreshing) {
        // If already refreshing, queue this request
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
            }
            return axios(originalRequest);
          })
          .catch((err) => {
            return Promise.reject(err);
          });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = authService.getRefreshToken();
      
      if (!refreshToken) {
        // No refresh token, clear everything and redirect
        authService.clearTokens();
        processQueue(new Error('No refresh token available'), null);
        isRefreshing = false;
        
        // Redirect to login if we're not already there
        if (window.location.pathname !== '/login' && window.location.pathname !== '/') {
          window.location.href = '/';
        }
        
        return Promise.reject(error);
      }

      try {
        // Attempt to refresh the token
        // Use getApiBaseUrl() so refresh works in Capacitor (Android/iOS) too
        const refreshResponse = await refreshAxios.post(
          `${getApiBaseUrl()}/token/refresh/`,
          { refresh: refreshToken },
          { headers: { 'Content-Type': 'application/json' } }
        );
        
        // rest_framework_simplejwt returns {"access": "..."}
        const newAccessToken = refreshResponse.data.access;
        const newRefreshToken = refreshResponse.data.refresh || refreshToken;
        
        if (!newAccessToken) {
          throw new Error('No access token in refresh response');
        }
        
        // Store new tokens IMMEDIATELY
        authService.storeTokens({
          access: newAccessToken,
          refresh: newRefreshToken,
        });
        
        // Update the original request with new token BEFORE retrying
        // Clear any existing Authorization header first to ensure fresh token
        if (originalRequest.headers) {
          delete originalRequest.headers.Authorization;
          originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        }
        
        // Process queued requests with the new token
        processQueue(null, newAccessToken);
        isRefreshing = false;
        
        // Retry the original request with the new token
        // Create a fresh request config to ensure we use the new token
        const retryConfig = {
          ...originalRequest,
          headers: {
            ...originalRequest.headers,
            Authorization: `Bearer ${newAccessToken}`,
          },
        };
        
        return axios(retryConfig);
      } catch (refreshError) {
        // Refresh failed, clear tokens and redirect
        authService.clearTokens();
        processQueue(refreshError, null);
        isRefreshing = false;
        
        // Redirect to login if we're not already there
        if (window.location.pathname !== '/login' && window.location.pathname !== '/') {
          window.location.href = '/';
        }
        
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default axios;

