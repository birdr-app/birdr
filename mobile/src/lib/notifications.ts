import { Alert, AppState, Linking, Platform } from 'react-native';
import { requireOptionalNativeModule } from 'expo-modules-core';
import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';
import { getAccessToken } from '../api/auth';
import { registerPushWithBackend } from '../api/pushRegister';
import { navigateWhenReady } from '../navigation/navigationRef';
import { routeForNotificationData } from './notificationRoute';

const WELCOME_TITLE = 'Motmot';
const WELCOME_BODY = "You're good to go!";
const ANDROID_CHANNEL_ID = 'default';

/** Avoid top-level `expo-device` import (loads ExpoDevice native module at bundle eval). */
function isPhysicalDevice(): boolean {
  if (Platform.OS === 'web') return true;
  const expoDevice = requireOptionalNativeModule<{ isDevice?: boolean }>('ExpoDevice');
  if (expoDevice && typeof expoDevice.isDevice === 'boolean') {
    return expoDevice.isDevice;
  }
  if (__DEV__) {
    console.warn(
      '[push] ExpoDevice native module unavailable — rebuild the iOS dev client (npm run ios). Treating as simulator.'
    );
  }
  return false;
}

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export type PushOnboardingResult =
  | 'granted_registered'
  | 'granted_local_only'
  | 'granted_no_token'
  | 'denied'
  | 'denied_can_open_settings';

function getExpoProjectId(): string | undefined {
  const extra = Constants.expoConfig?.extra as { eas?: { projectId?: string } } | undefined;
  return extra?.eas?.projectId ?? Constants.easConfig?.projectId;
}

async function ensureAndroidChannel(): Promise<void> {
  if (Platform.OS !== 'android') return;
  await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL_ID, {
    name: 'Motmot',
    importance: Notifications.AndroidImportance.HIGH,
    vibrationPattern: [0, 250, 250, 250],
    lightColor: '#2D5A3D',
    sound: 'default',
    enableVibrate: true,
    showBadge: true,
  });
}

function getDeviceTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

async function requestNotificationPermission(): Promise<{
  granted: boolean;
  canAskAgain: boolean;
  newlyGranted: boolean;
}> {
  const existing = await Notifications.getPermissionsAsync();
  if (existing.status === Notifications.PermissionStatus.GRANTED) {
    return { granted: true, canAskAgain: true, newlyGranted: false };
  }
  if (
    existing.status === Notifications.PermissionStatus.DENIED &&
    existing.canAskAgain === false
  ) {
    return { granted: false, canAskAgain: false, newlyGranted: false };
  }
  const requested = await Notifications.requestPermissionsAsync({
    ios: {
      allowAlert: true,
      allowBadge: true,
      allowSound: true,
    },
  });
  const granted = requested.status === Notifications.PermissionStatus.GRANTED;
  return {
    granted,
    canAskAgain: requested.canAskAgain !== false,
    newlyGranted: granted,
  };
}

async function hasNotificationPermission(): Promise<boolean> {
  const existing = await Notifications.getPermissionsAsync();
  return existing.status === Notifications.PermissionStatus.GRANTED;
}

/** Whether this phone currently allows Motmot notifications (re-check when the app returns to the foreground). */
export async function isPushPermissionGranted(): Promise<boolean> {
  try {
    return await hasNotificationPermission();
  } catch {
    return false;
  }
}

/** Show welcome banner immediately (works in foreground + background). */
async function showLocalWelcomeNotification(): Promise<void> {
  await ensureAndroidChannel();
  await Notifications.scheduleNotificationAsync({
    content: {
      title: WELCOME_TITLE,
      body: WELCOME_BODY,
      data: { type: 'signup_test' },
      sound: 'default',
      ...(Platform.OS === 'android' ? { channelId: ANDROID_CHANNEL_ID } : {}),
    },
    trigger: null,
  });
}

async function registerTokenWithBackend(
  expoPushToken: string,
  options: { sendWelcome?: boolean } = {}
): Promise<{
  ok: boolean;
  testPushSent?: boolean;
  error?: string;
}> {
  const access = await getAccessToken();
  if (!access) {
    return { ok: false, error: 'not_logged_in' };
  }
  try {
    const result = await registerPushWithBackend({
      expo_push_token: expoPushToken,
      timezone: getDeviceTimezone(),
      platform: Platform.OS === 'ios' ? 'ios' : 'android',
      send_welcome: options.sendWelcome === true,
    });
    return { ok: true, testPushSent: result.test_push_sent };
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'registration_failed';
    if (__DEV__) {
      console.warn('[push] backend registration failed', msg);
    }
    return { ok: false, error: msg };
  }
}

function maybeShowDevPushAlert(result: PushOnboardingResult, detail?: string): void {
  if (!__DEV__) return;
  Alert.alert('Push onboarding (dev)', `${result}${detail ? `\n${detail}` : ''}`);
}

/**
 * Register push token when permission is already granted (e.g. app launch).
 * Does not prompt or send welcome notifications.
 */
export async function syncPushRegistrationIfPermittedAsync(): Promise<void> {
  try {
    await ensureAndroidChannel();
    if (!(await hasNotificationPermission())) {
      return;
    }
    if (!isPhysicalDevice()) {
      return;
    }
    const projectId = getExpoProjectId();
    const tokenResponse = await Notifications.getExpoPushTokenAsync(
      projectId ? { projectId } : undefined
    );
    const expoPushToken = tokenResponse.data;
    if (!expoPushToken) {
      return;
    }
    await registerTokenWithBackend(expoPushToken, { sendWelcome: false });
  } catch (e) {
    if (__DEV__) {
      const msg = e instanceof Error ? e.message : String(e);
      console.warn('[push] syncPushRegistrationIfPermittedAsync failed', msg);
    }
  }
}

/**
 * Ask for push permission and register with the API when logged in.
 * When the user newly grants permission they get exactly one welcome notification:
 * the server push if the backend sent it, otherwise a local one.
 */
export async function registerForPushNotificationsAsync(): Promise<PushOnboardingResult> {
  try {
    await ensureAndroidChannel();

    const { granted, canAskAgain, newlyGranted } = await requestNotificationPermission();
    if (!granted) {
      const result = canAskAgain ? 'denied' : 'denied_can_open_settings';
      maybeShowDevPushAlert(result);
      return result;
    }

    if (!isPhysicalDevice()) {
      if (newlyGranted) {
        await showLocalWelcomeNotification();
      }
      maybeShowDevPushAlert('granted_local_only', 'simulator');
      return 'granted_local_only';
    }

    const projectId = getExpoProjectId();
    let expoPushToken: string | undefined;
    try {
      const tokenResponse = await Notifications.getExpoPushTokenAsync(
        projectId ? { projectId } : undefined
      );
      expoPushToken = tokenResponse.data;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (newlyGranted) {
        await showLocalWelcomeNotification();
      }
      maybeShowDevPushAlert('granted_no_token', msg);
      return 'granted_no_token';
    }

    if (!expoPushToken) {
      if (newlyGranted) {
        await showLocalWelcomeNotification();
      }
      maybeShowDevPushAlert('granted_no_token');
      return 'granted_no_token';
    }

    const backend = await registerTokenWithBackend(expoPushToken, {
      sendWelcome: newlyGranted,
    });
    if (newlyGranted && !backend.testPushSent) {
      await showLocalWelcomeNotification();
    }
    if (backend.ok) {
      const detail = backend.testPushSent
        ? 'server test push sent'
        : 'server test push not sent (check SEND_PUSH_NOTIFICATIONS)';
      maybeShowDevPushAlert('granted_registered', detail);
      return 'granted_registered';
    }

    maybeShowDevPushAlert(
      'granted_local_only',
      backend.error === 'not_logged_in'
        ? 'guest — sign in for server pushes'
        : backend.error
    );
    return 'granted_local_only';
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    if (__DEV__) {
      console.warn('[push] registerForPushNotificationsAsync failed', msg);
      Alert.alert('Push onboarding failed', msg);
    }
    return 'denied';
  }
}

function promptOpenSettings(message: string): void {
  Alert.alert('Notifications', message, [
    { text: 'Not now', style: 'cancel' },
    { text: 'Open settings', onPress: () => Linking.openSettings() },
  ]);
}

/**
 * Ask for permission (if needed) and register this device with the backend.
 * Use when the user opts into something that sends pushes (e.g. joining the National League).
 * Offers system settings when notifications were turned off earlier.
 */
export async function requestPushPermissionAndRegister(settingsMessage?: string): Promise<PushOnboardingResult> {
  const result = await registerForPushNotificationsAsync();
  if (result === 'denied_can_open_settings') {
    // The phone no longer shows its own prompt once notifications were denied: only Settings can undo that.
    promptOpenSettings(
      settingsMessage ??
        'Notifications are turned off for Motmot. Enable them in system settings to get your daily reminders.'
    );
  }
  return result;
}

/** Call when the user starts Motmot Journey (after country is chosen). */
export async function runBirdrJourneyPushOnboarding(): Promise<void> {
  const result = await registerForPushNotificationsAsync();
  if (result === 'denied_can_open_settings') {
    promptOpenSettings(
      'Notifications are turned off for Motmot. Enable them in system settings to get daily challenge reminders.'
    );
  }
}

function handleNotificationResponse(response: Notifications.NotificationResponse): void {
  const route = routeForNotificationData(response.notification.request.content.data);
  if (route) {
    navigateWhenReady(route.name, route.params);
  }
}

/**
 * Route notification taps. Also handles the tap that launched the app from a killed
 * state (the listener is attached too late to see it); navigation waits until the
 * NavigationContainer is ready.
 */
/**
 * Reset the app-icon badge (the red "1" league pushes set) whenever the app is
 * opened or comes back to the foreground. Returns an unsubscribe function.
 */
export function clearAppBadgeOnForeground(): () => void {
  const clear = () => {
    Notifications.setBadgeCountAsync(0).catch(() => {});
  };
  clear();
  const sub = AppState.addEventListener('change', (state) => {
    if (state === 'active') clear();
  });
  return () => sub.remove();
}

export function setupNotificationResponseHandler(): () => void {
  let handledId: string | null = null;
  const handleOnce = (response: Notifications.NotificationResponse) => {
    const id = response.notification.request.identifier;
    if (id && id === handledId) return;
    handledId = id;
    handleNotificationResponse(response);
  };
  const sub = Notifications.addNotificationResponseReceivedListener(handleOnce);
  Notifications.getLastNotificationResponseAsync()
    .then((response) => {
      if (response) {
        handleOnce(response);
        Notifications.clearLastNotificationResponse();
      }
    })
    .catch(() => {});
  return () => sub.remove();
}
