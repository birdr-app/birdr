import { Platform } from 'react-native';
import { getAppVersionDisplay } from '../utils/appVersion';

export type DeviceType = 'ios' | 'android' | 'web';

export function getDeviceType(): DeviceType {
  if (Platform.OS === 'ios') return 'ios';
  if (Platform.OS === 'android') return 'android';
  return 'web';
}

export function getAppVersion(): string {
  const version = getAppVersionDisplay().version;
  return version && version !== '—' ? version : '';
}

export function getAppBuild(): string {
  return getAppVersionDisplay().build ?? '';
}

export function getOsVersion(): string {
  if (Platform.OS === 'android') {
    const release = (Platform.constants as { Release?: string } | undefined)?.Release;
    if (release) return String(release);
  }
  return Platform.Version != null ? String(Platform.Version) : '';
}

export function clientInfoPayload(): {
  app_version?: string;
  app_build?: string;
  os_version?: string;
  device_type: DeviceType;
  platform: DeviceType;
} {
  const app_version = getAppVersion();
  const app_build = getAppBuild();
  const os_version = getOsVersion();
  const device_type = getDeviceType();
  const payload: {
    app_version?: string;
    app_build?: string;
    os_version?: string;
    device_type: DeviceType;
    platform: DeviceType;
  } = {
    device_type,
    platform: device_type,
  };
  if (app_version) payload.app_version = app_version;
  if (app_build) payload.app_build = app_build;
  if (os_version) payload.os_version = os_version;
  return payload;
}

/** Identity headers for HTTP and native WebSocket handshakes. */
export function clientInfoHeaders(): Record<string, string> {
  const device_type = getDeviceType();
  const headers: Record<string, string> = {
    'X-Platform': device_type,
    'X-Birdr-Device-Type': device_type,
    'X-Birdr-Platform': device_type,
  };
  const app_version = getAppVersion();
  if (app_version) {
    headers['X-App-Version'] = app_version;
    headers['X-Birdr-App-Version'] = app_version;
  }
  const app_build = getAppBuild();
  if (app_build) headers['X-App-Build'] = app_build;
  const os_version = getOsVersion();
  if (os_version) headers['X-OS-Version'] = os_version;
  return headers;
}
