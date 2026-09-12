import { getTranslation, translations } from '../i18n/translations';
import {
  buildFlockInviteShareMessage,
  buildFlockResultShareMessage,
  flockInviteUrl,
  isFlockRoute,
  parseFlockJoinUrl,
  type FlockInvite,
} from '../api/flocks';

const FLOCK_I18N_KEYS = [
  'flocks',
  'flocks_hint',
  'new_flock',
  'flock_name_placeholder',
  'create_flock',
  'my_flocks',
  'no_flocks_yet',
  'flock_invite_title',
  'flock_join',
  'flock_leaderboard',
  'flocks_weekly_progress',
  'flocks_weekly_score',
  'flocks_weekly_correct',
  'flocks_weekly_rank',
  'flocks_weekly_cumulative',
  'flock_play_challenge',
  'flock_add_logo',
  'flock_share_result',
  'back_to_flock',
  'you',
];

describe('flocks i18n', () => {
  it.each(FLOCK_I18N_KEYS)('has en and nl strings for %s', (key) => {
    expect(translations.en[key]).toBeTruthy();
    expect(translations.nl[key]).toBeTruthy();
    expect(getTranslation('en', key)).not.toBe(key);
    expect(getTranslation('nl', key)).not.toBe(key);
  });
});

describe('parseFlockJoinUrl', () => {
  it('parses birdr scheme links', () => {
    expect(parseFlockJoinUrl('birdr://join/flock/abc123')).toBe('abc123');
  });

  it('parses https web links', () => {
    expect(parseFlockJoinUrl('https://birdr.pro/join/flock/xyz-token/')).toBe('xyz-token');
  });

  it('returns null for game join links', () => {
    expect(parseFlockJoinUrl('birdr://join/game123')).toBeNull();
    expect(parseFlockJoinUrl('https://birdr.pro/join/challenge/tok')).toBeNull();
  });
});

describe('isFlockRoute', () => {
  it('recognizes flock screens', () => {
    expect(isFlockRoute('FlockList')).toBe(true);
    expect(isFlockRoute('FlockDetail')).toBe(true);
    expect(isFlockRoute('FlockWeeklyProgress')).toBe(true);
    expect(isFlockRoute('FlockInviteLanding')).toBe(true);
    expect(isFlockRoute('FlockChallengeResult')).toBe(true);
    expect(isFlockRoute('Home')).toBe(false);
  });
});

describe('flockInviteUrl', () => {
  it('prefers server invite_url', () => {
    const invite: FlockInvite = {
      code: 'ABCD',
      token: 'tok',
      invite_url: 'https://birdr.pro/join/flock/tok/',
    };
    expect(flockInviteUrl(invite)).toBe('https://birdr.pro/join/flock/tok/');
  });
});

describe('share message builders', () => {
  it('builds localized invite message', () => {
    const msg = buildFlockInviteShareMessage('Amsterdam Birders', 'https://birdr.pro/join/flock/x/', 'en');
    expect(msg).toContain('Amsterdam Birders');
    expect(msg).toContain('https://birdr.pro/join/flock/x/');
  });

  it('builds localized result message with rank', () => {
    const msg = buildFlockResultShareMessage(
      {
        scoreLabel: '15/20',
        rankLabel: '#3 of 10',
        flockName: 'Amsterdam Birders',
        resultUrl: 'https://birdr.pro/flocks/results/abc/',
      },
      'en'
    );
    expect(msg).toContain('15/20');
    expect(msg).toContain('#3 of 10');
    expect(msg).toContain('Amsterdam Birders');
    expect(msg).toContain('https://birdr.pro/flocks/results/abc/');
  });

  it('builds dutch result message', () => {
    const msg = buildFlockResultShareMessage(
      {
        scoreLabel: '12/20',
        rankLabel: null,
        flockName: 'Test Flock',
        resultUrl: 'https://birdr.pro/flocks/results/t/',
      },
      'nl'
    );
    expect(msg).toContain('12/20');
    expect(msg).toContain('Test Flock');
  });
});
