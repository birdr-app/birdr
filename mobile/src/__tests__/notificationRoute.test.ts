import { routeForNotificationData } from '../lib/notificationRoute';

describe('routeForNotificationData', () => {
  it('routes league pushes to the League screen with the country', () => {
    expect(routeForNotificationData({ type: 'league', country_code: 'nl' })).toEqual({
      name: 'League',
      params: { countryCode: 'NL' },
    });
    expect(routeForNotificationData({ type: 'league' })).toEqual({ name: 'League' });
  });

  it('routes daily challenge pushes to the challenge when an id is present', () => {
    for (const type of ['daily_challenge_reminder', 'daily_challenge_invite', 'daily_challenge_ranking']) {
      expect(routeForNotificationData({ type, challenge_id: 42 })).toEqual({
        name: 'DailyChallengeDetail',
        params: { challengeId: 42 },
      });
    }
    expect(routeForNotificationData({ type: 'daily_challenge' })).toEqual({ name: 'DailyChallenge' });
    expect(routeForNotificationData({ type: 'signup_test' })).toEqual({ name: 'DailyChallenge' });
  });

  it('routes admin pushes to the chosen screen, defaulting to Home', () => {
    expect(routeForNotificationData({ type: 'route', screen: 'Home' })).toEqual({ name: 'Home' });
    expect(routeForNotificationData({ type: 'route', screen: 'SurvivalStart' })).toEqual({ name: 'SurvivalStart' });
    expect(routeForNotificationData({ type: 'route', screen: 'LeagueLeaderboard', country_code: 'lt' })).toEqual({
      name: 'LeagueLeaderboard',
      params: { countryCode: 'LT' },
    });
    expect(routeForNotificationData({ type: 'route', screen: 'GamePlay' })).toEqual({ name: 'Home' });
    expect(routeForNotificationData({ type: 'route' })).toEqual({ name: 'Home' });
  });

  it('routes flock challenges to the flock', () => {
    expect(routeForNotificationData({ type: 'flock_challenge', flock_slug: 'owls' })).toEqual({
      name: 'FlockDetail',
      params: { slug: 'owls' },
    });
    expect(routeForNotificationData({ type: 'flock_challenge' })).toBeNull();
  });

  it('ignores unknown or empty payloads', () => {
    expect(routeForNotificationData(undefined)).toBeNull();
    expect(routeForNotificationData({ type: 'something_else' })).toBeNull();
  });
});
