import { useEffect, useRef } from 'react';
import { AppState, type AppStateStatus } from 'react-native';

/** Shorter trips away (a permission dialog, a notification shade pull) are not worth a resync. */
const MIN_AWAY_MS = 2000;

/**
 * Calls `onResume` when the app returns to the foreground after being away a moment.
 * Timers and requests that were in flight while the app was in the background may never
 * have finished, so play screens use this to re-read the server state.
 */
export function useResumeResync(onResume: () => void, enabled = true) {
  const callbackRef = useRef(onResume);
  callbackRef.current = onResume;

  useEffect(() => {
    if (!enabled) return;
    let leftAt: number | null = null;
    const sub = AppState.addEventListener('change', (state: AppStateStatus) => {
      if (state === 'active') {
        const awayMs = leftAt == null ? 0 : Date.now() - leftAt;
        leftAt = null;
        if (awayMs >= MIN_AWAY_MS) callbackRef.current();
        return;
      }
      if (leftAt == null) leftAt = Date.now();
    });
    return () => sub.remove();
  }, [enabled]);
}
