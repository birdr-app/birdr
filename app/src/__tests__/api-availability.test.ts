import { probeApiAvailability } from '../api/apiAvailability';

describe('probeApiAvailability', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    jest.useRealTimers();
  });

  it('returns reachable when the API responds OK', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200 });
    await expect(probeApiAvailability()).resolves.toBe('reachable');
  });

  it('returns unreachable when the API is down', async () => {
    global.fetch = jest.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(probeApiAvailability()).resolves.toBe('unreachable');
  });

  it('returns unreachable on a 503 maintenance response', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 503 });
    await expect(probeApiAvailability()).resolves.toBe('unreachable');
  });
});
