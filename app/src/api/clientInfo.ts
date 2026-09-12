import packageJson from '../../package.json';

export type DeviceType = 'ios' | 'android' | 'web';

export function getDeviceType(): DeviceType {
  if (typeof window !== 'undefined' && window.Capacitor?.isNativePlatform?.()) {
    const platform = window.Capacitor.getPlatform?.();
    if (platform === 'ios' || platform === 'android') return platform;
  }
  return 'web';
}

export function getAppVersion(): string {
  return (packageJson as { version?: string }).version || '';
}

export function getOsVersion(): string {
  if (typeof navigator === 'undefined') return '';
  const ua = navigator.userAgent || '';
  const ios = ua.match(/OS (\d+[._]\d+)/);
  if (ios) return ios[1].replace('_', '.');
  const android = ua.match(/Android (\d+(?:\.\d+)?)/);
  if (android) return android[1];
  return '';
}

export function clientInfoPayload(): {
  app_version?: string;
  os_version?: string;
  device_type: DeviceType;
  platform: DeviceType;
} {
  const app_version = getAppVersion();
  const os_version = getOsVersion();
  const device_type = getDeviceType();
  const payload: {
    app_version?: string;
    os_version?: string;
    device_type: DeviceType;
    platform: DeviceType;
  } = {
    device_type,
    platform: device_type,
  };
  if (app_version) payload.app_version = app_version;
  if (os_version) payload.os_version = os_version;
  return payload;
}

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
  const os_version = getOsVersion();
  if (os_version) headers['X-OS-Version'] = os_version;
  return headers;
}
