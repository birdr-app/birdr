import { Platform } from 'react-native';
import { clientInfoHeaders, clientInfoPayload, getDeviceType } from '../api/clientInfo';

jest.mock('../utils/appVersion', () => ({
  getAppVersionDisplay: () => ({ version: '1.8.2', build: '87', codename: 'Goose' }),
}));

describe('clientInfoHeaders', () => {
  const originalOS = Platform.OS;
  const originalVersion = Platform.Version;
  const originalConstants = Platform.constants;

  afterEach(() => {
    Object.defineProperty(Platform, 'OS', { value: originalOS });
    Object.defineProperty(Platform, 'Version', { value: originalVersion });
    Object.defineProperty(Platform, 'constants', { value: originalConstants });
  });

  it('sends app identity headers for Android', () => {
    Object.defineProperty(Platform, 'OS', { value: 'android' });
    Object.defineProperty(Platform, 'Version', { value: 34 });
    Object.defineProperty(Platform, 'constants', { value: { Release: '14' } });

    expect(getDeviceType()).toBe('android');
    const headers = clientInfoHeaders();
    expect(headers['X-App-Version']).toBe('1.8.2');
    expect(headers['X-App-Build']).toBe('87');
    expect(headers['X-Platform']).toBe('android');
    expect(headers['X-OS-Version']).toBe('14');
    expect(headers['X-Birdr-App-Version']).toBe('1.8.2');
  });

  it('includes identity on the websocket join payload', () => {
    Object.defineProperty(Platform, 'OS', { value: 'ios' });
    Object.defineProperty(Platform, 'Version', { value: '18.0' });
    const payload = clientInfoPayload();
    expect(payload.platform).toBe('ios');
    expect(payload.app_version).toBe('1.8.2');
    expect(payload.app_build).toBe('87');
    expect(payload.os_version).toBe('18.0');
  });
});
