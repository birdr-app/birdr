import { probeAppApi, fetchAppVersionRequirements } from '../api/appVersion';

describe('probeAppApi', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('returns reachable data when the API responds OK', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ min_version: '1.0.0' }),
    });
    await expect(probeAppApi()).resolves.toEqual({
      reachable: true,
      data: { min_version: '1.0.0' },
    });
  });

  it('returns unreachable when the API cannot be reached', async () => {
    global.fetch = jest.fn().mockRejectedValue(new TypeError('Network request failed'));
    await expect(probeAppApi()).resolves.toEqual({ reachable: false });
  });

  it('returns unreachable on a 503 maintenance response', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 503 });
    await expect(probeAppApi()).resolves.toEqual({ reachable: false });
  });

  it('fetchAppVersionRequirements returns null when unreachable', async () => {
    global.fetch = jest.fn().mockRejectedValue(new TypeError('Network request failed'));
    await expect(fetchAppVersionRequirements()).resolves.toBeNull();
  });
});
