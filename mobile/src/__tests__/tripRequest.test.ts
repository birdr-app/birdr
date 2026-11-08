jest.mock('../api/config', () => ({ apiUrl: (path: string) => path }));
jest.mock('../api/auth', () => ({ getAuthHeaders: async () => ({}) }));

import { postFeedback, tripRequestComment } from '../api/feedback';

describe('trip request', () => {
  test('the comment names the country first, then the note and the app language', () => {
    expect(tripRequestComment(' Costa Rica ', 'Going in March', 'nl')).toBe(
      'Trip prep request: Costa Rica\n\nGoing in March\n\n(app language: nl)'
    );
  });

  test('an empty note is left out', () => {
    expect(tripRequestComment('Peru', '  ', 'en')).toBe('Trip prep request: Peru\n\n(app language: en)');
  });

  test('it is sent as feedback with the player token', async () => {
    const fetchMock = jest.fn(async () => ({ ok: true }));
    (global as any).fetch = fetchMock;
    await expect(postFeedback(tripRequestComment('Peru', '', 'en'), 'tok')).resolves.toBe(true);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/feedback/');
    expect(JSON.parse(init.body as string)).toEqual({
      comment: 'Trip prep request: Peru\n\n(app language: en)',
      player_token: 'tok',
    });
  });
});
