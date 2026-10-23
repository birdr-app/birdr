/** Pure mapping from a push notification's `data` payload to a screen (unit-tested). */

export type NotificationRoute = { name: string; params?: Record<string, unknown> };

/** Screens an admin push ({type: 'route', screen}) may open; anything else falls back to Home. */
const ADMIN_PUSH_SCREENS = new Set([
  'Home',
  'Start',
  'SurvivalStart',
  'FlockList',
  'BirdrJourneyList',
  'Updates',
  'Scores',
  'LeagueLeaderboard',
]);

export function routeForNotificationData(data: unknown): NotificationRoute | null {
  if (!data || typeof data !== 'object') return null;
  const d = data as {
    type?: string;
    flock_slug?: string;
    token?: string;
    country_code?: string;
    screen?: string;
    challenge_id?: number | string;
  };
  switch (d.type) {
    case 'route': {
      const screen = typeof d.screen === 'string' && ADMIN_PUSH_SCREENS.has(d.screen) ? d.screen : 'Home';
      if (screen === 'LeagueLeaderboard') {
        const countryCode = typeof d.country_code === 'string' ? d.country_code.toUpperCase() : '';
        return countryCode ? { name: screen, params: { countryCode } } : { name: 'Home' };
      }
      return { name: screen };
    }
    case 'league': {
      const countryCode = typeof d.country_code === 'string' ? d.country_code.toUpperCase() : '';
      return countryCode ? { name: 'League', params: { countryCode } } : { name: 'League' };
    }
    case 'signup_test':
    case 'daily_challenge':
    case 'daily_challenge_reminder':
    case 'daily_challenge_invite':
    case 'daily_challenge_ranking':
    case 'daily_challenge_ended': {
      const challengeId = Number(d.challenge_id);
      if (Number.isFinite(challengeId) && challengeId > 0) {
        return { name: 'DailyChallengeDetail', params: { challengeId } };
      }
      return { name: 'DailyChallenge' };
    }
    case 'flock_challenge':
      return d.flock_slug ? { name: 'FlockDetail', params: { slug: d.flock_slug } } : null;
    case 'shared_game':
      // A member posted a game to the flock's Extra games.
      if (typeof d.token === 'string' && d.token) return { name: 'SharedGameDetail', params: { token: d.token } };
      return d.flock_slug ? { name: 'FlockDetail', params: { slug: d.flock_slug } } : null;
    default:
      return null;
  }
}
