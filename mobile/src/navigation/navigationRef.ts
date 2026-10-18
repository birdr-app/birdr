import { createNavigationContainerRef } from '@react-navigation/native';

export const navigationRef = createNavigationContainerRef();

type PendingNavigation = { name: string; params?: Record<string, unknown> };

/** Navigation requested before the container was ready (e.g. cold-start notification tap). */
let pending: PendingNavigation | null = null;

function navigate(name: string, params?: Record<string, unknown>): void {
  // Untyped root navigator: route names are strings registered in AppNavigator.
  (navigationRef.navigate as unknown as (n: string, p?: object) => void)(name, params);
}

/** Navigate now, or remember the latest request until flushPendingNavigation() runs. */
export function navigateWhenReady(name: string, params?: Record<string, unknown>): void {
  if (navigationRef.isReady()) {
    navigate(name, params);
    return;
  }
  pending = { name, params };
}

/** Call from NavigationContainer onReady. */
export function flushPendingNavigation(): void {
  if (!pending || !navigationRef.isReady()) return;
  const { name, params } = pending;
  pending = null;
  navigate(name, params);
}

export function navigateToDailyChallenge(): void {
  navigateWhenReady('DailyChallenge');
}

export function navigateToFlockDetail(slug: string): void {
  if (slug) {
    navigateWhenReady('FlockDetail', { slug });
  }
}
