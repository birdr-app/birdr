import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { linkStoredPlayerToAccount } from '../api/player';
import { AUTH_CHANGED_EVENT, authService } from '../api/services/auth.service';
import { profileService, type UserProfile } from '../api/services/profile.service';

const AUTH_STORAGE_KEYS = ['access_token', 'refresh_token', 'jw_token'];
const ACCESS_REFRESH_SKEW_SEC = 120;

type AuthProfileState = {
  isAuthenticated: boolean;
  ready: boolean;
  profile: UserProfile | null;
  userEmail: string | null;
  refresh: () => Promise<void>;
  applyProfile: (profile: UserProfile | null) => void;
};

const AuthProfileContext = createContext<AuthProfileState>({
  isAuthenticated: false,
  ready: false,
  profile: null,
  userEmail: null,
  refresh: async () => {},
  applyProfile: () => {},
});

function jwtPayload(accessToken: string): { exp?: number; email?: string; username?: string } | null {
  try {
    const payload = accessToken.split('.')[1];
    if (!payload) return null;
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    return JSON.parse(atob(padded)) as { exp?: number; email?: string; username?: string };
  } catch {
    return null;
  }
}

function jwtExp(accessToken: string): number | null {
  const data = jwtPayload(accessToken);
  return typeof data?.exp === 'number' ? data.exp : null;
}

function jwtEmail(accessToken: string): string | null {
  const data = jwtPayload(accessToken);
  return data?.email || data?.username || null;
}

export function AuthProfileProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(() => !!authService.getAccessToken());
  const [ready, setReady] = useState(false);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(() => {
    const token = authService.getAccessToken();
    return token ? jwtEmail(token) : null;
  });
  const [accessToken, setAccessToken] = useState<string | null>(() => authService.getAccessToken());
  const expiryTimerRef = useRef<number | undefined>(undefined);
  const inFlightRef = useRef<Promise<void> | null>(null);
  const linkedRef = useRef(false);

  const applyProfile = useCallback((next: UserProfile | null) => {
    setProfile(next);
  }, []);

  const refresh = useCallback(() => {
    if (!inFlightRef.current) {
      inFlightRef.current = (async () => {
        const token = authService.getAccessToken();
        if (!token) {
          linkedRef.current = false;
          setIsAuthenticated(false);
          setUserEmail(null);
          setProfile(null);
          setAccessToken(null);
          return;
        }
        setIsAuthenticated(true);
        setUserEmail(jwtEmail(token));
        setAccessToken(token);
        const ok = await authService.ensureValidAccessToken();
        const access = authService.getAccessToken();
        if (!ok || !access) {
          linkedRef.current = false;
          setIsAuthenticated(false);
          setUserEmail(null);
          setProfile(null);
          setAccessToken(null);
          return;
        }
        setUserEmail(jwtEmail(access));
        setAccessToken(access);
        if (!linkedRef.current) {
          linkedRef.current = true;
          try {
            await linkStoredPlayerToAccount();
          } catch {
            /* non-fatal */
          }
        }
        try {
          setProfile(await profileService.getProfile());
        } catch {
          setProfile(null);
          if (!authService.getAccessToken()) {
            linkedRef.current = false;
            setIsAuthenticated(false);
            setUserEmail(null);
            setAccessToken(null);
          }
        }
      })().finally(() => {
        inFlightRef.current = null;
        setReady(true);
      });
    }
    return inFlightRef.current;
  }, []);

  useEffect(() => {
    void refresh();

    const onVisibility = () => {
      if (document.visibilityState === 'visible') void refresh();
    };
    const onStorage = (event: StorageEvent) => {
      if (!event.key || AUTH_STORAGE_KEYS.includes(event.key)) void refresh();
    };
    const onAuthChanged = () => {
      void refresh();
    };
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('storage', onStorage);
    window.addEventListener(AUTH_CHANGED_EVENT, onAuthChanged);
    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('storage', onStorage);
      window.removeEventListener(AUTH_CHANGED_EVENT, onAuthChanged);
    };
  }, [refresh]);

  useEffect(() => {
    const arm = () => {
      if (expiryTimerRef.current) {
        window.clearTimeout(expiryTimerRef.current);
        expiryTimerRef.current = undefined;
      }
      if (document.visibilityState !== 'visible') return;
      if (!accessToken) return;
      const exp = jwtExp(accessToken);
      if (exp == null) return;
      const now = Math.floor(Date.now() / 1000);
      const delayMs = (exp - ACCESS_REFRESH_SKEW_SEC - now) * 1000;
      if (delayMs <= 0 || delayMs > 24 * 60 * 60 * 1000) return;
      expiryTimerRef.current = window.setTimeout(() => {
        void refresh();
      }, delayMs);
    };
    arm();
    document.addEventListener('visibilitychange', arm);
    return () => {
      document.removeEventListener('visibilitychange', arm);
      if (expiryTimerRef.current) window.clearTimeout(expiryTimerRef.current);
    };
  }, [accessToken, refresh]);

  return (
    <AuthProfileContext.Provider
      value={{ isAuthenticated, ready, profile, userEmail, refresh, applyProfile }}
    >
      {children}
    </AuthProfileContext.Provider>
  );
}

export function useAuthProfile(): AuthProfileState {
  return useContext(AuthProfileContext);
}

export default AuthProfileContext;
