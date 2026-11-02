import { apiUrl, getWebSocketUrl } from '../api/config';

describe('api config', () => {
  it('apiUrl prepends base and normalizes path', () => {
    expect(apiUrl('/api/games/')).toBe('https://motmot.club/api/games/');
    expect(apiUrl('api/games/')).toBe('https://motmot.club/api/games/');
  });

  it('getWebSocketUrl converts https to wss', () => {
    expect(getWebSocketUrl('/ws/game/')).toBe('wss://motmot.club/ws/game/');
  });

  it('getWebSocketUrl converts http to ws', () => {
    const url = getWebSocketUrl('/ws/');
    expect(url.startsWith('ws')).toBe(true);
    expect(url).not.toContain('https');
  });
});
