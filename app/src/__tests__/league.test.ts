import {
  clearLeaguePlayContext,
  getLeagueLeaderboardPath,
  getLeaguePath,
  getLeaguePlayContext,
  leagueErrorMessage,
  readLeagueResult,
  setLeaguePlayContext,
  storeLeagueResult,
} from '../api/league';

describe('league helpers', () => {
  beforeEach(() => sessionStorage.clear());

  test('builds league paths with upper-case country codes', () => {
    expect(getLeaguePath('nl')).toBe('/league/NL');
    expect(getLeagueLeaderboardPath('nl')).toBe('/league/NL/leaderboard');
    expect(getLeagueLeaderboardPath('nl', 'caps')).toBe('/league/NL/leaderboard?period=caps');
  });

  test('round-trips and clears the play context', () => {
    expect(getLeaguePlayContext()).toBeNull();
    setLeaguePlayContext({ countryCode: 'NL', countryName: 'Netherlands', attemptId: 7, gameToken: 'abc' });
    expect(getLeaguePlayContext()).toEqual({
      countryCode: 'NL',
      countryName: 'Netherlands',
      attemptId: 7,
      gameToken: 'abc',
    });
    clearLeaguePlayContext();
    expect(getLeaguePlayContext()).toBeNull();
  });

  test('ignores a malformed play context', () => {
    sessionStorage.setItem('birdr-league-play', JSON.stringify({ countryCode: 'NL', attemptId: 'x' }));
    expect(getLeaguePlayContext()).toBeNull();
  });

  test('stores the last result for the result page', () => {
    storeLeagueResult({
      countryCode: 'NL',
      score: 812,
      correct: 9,
      length: 10,
      rank_today: 1,
      players_today: 40,
      week_rank: 2,
      week_rank_previous: 5,
      week_rank_change: 3,
      week_total: 2400,
      took_lead: false,
      perfect: false,
      week_days_played: 3,
      share_message: 'hi',
    });
    expect(readLeagueResult()?.score).toBe(812);
  });

  test('reads API error messages', () => {
    expect(leagueErrorMessage({ response: { data: { detail: 'Closed' } } }, 'x')).toBe('Closed');
    expect(leagueErrorMessage({ response: { data: { error: ['Nope'] } } }, 'x')).toBe('Nope');
    expect(leagueErrorMessage({}, 'fallback')).toBe('fallback');
  });
});
