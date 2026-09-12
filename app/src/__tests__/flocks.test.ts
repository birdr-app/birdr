import enMessages from '../locales/en.json';
import nlMessages from '../locales/nl.json';
import {
  buildFlockInviteWebUrl,
  buildFlockResultWebUrl,
  buildWhatsAppShareUrl,
  clearFlockPlayContext,
  formatFlockInviteShareMessage,
  formatFlockResultShareMessage,
  getFlockDetailPath,
  getFlockInvitePath,
  getFlockInviteWebPath,
  getFlockLeaderboardPath,
  getFlockHistoryPath,
  getFlockMembersPath,
  getFlockPlayContext,
  getFlockResultPath,
  getFlocksIntroPath,
  getFlocksCreatePath,
  getFlocksJoinPath,
  getFlocksPath,
  setFlockPlayContext,
} from '../api/flocks';

const FLOCKS_I18N_KEYS = [
  'flocks_title',
  'flocks_overview_hint',
  'flocks_home_cta',
  'flocks_home_start_cta',
  'flocks_start',
  'flocks_intro_title',
  'flocks_intro_cta',
  'flocks_login_required',
  'flocks_create',
  'flocks_my_flocks',
  'flocks_empty',
  'flocks_join_title',
  'flocks_join_login_prompt',
  'flocks_join_play_web',
  'flocks_join_with_code',
  'flocks_invite_web_first',
  'flocks_leaderboard',
  'flocks_view_members',
  'flocks_invite_members',
  'flocks_invite_more',
  'flocks_view_leaderboard',
  'flocks_weekly_progress',
  'flocks_invite_share',
  'flocks_result_title',
  'flocks_share_whatsapp',
  'flocks_saving_result',
  'back_to_flock',
] as const;

describe('flocks share helpers', () => {
  it('builds WhatsApp share URL with encoded message', () => {
    const message = 'Join My Club on Birdr! https://birdr.pro/join/flock/abc/web';
    expect(buildWhatsAppShareUrl(message)).toBe(
      `https://wa.me/?text=${encodeURIComponent(message)}`
    );
  });

  it('formats flock invite share message', () => {
    const url = 'https://birdr.pro/join/flock/token123/web';
    const message = formatFlockInviteShareMessage('Dutch Birders', url);
    expect(message).toContain('Dutch Birders');
    expect(message).toContain('20 birds');
    expect(message).toContain(url);
  });

  it('formats flock result share message with optional rank', () => {
    const url = 'https://birdr.pro/flocks/results/res456';
    const withRank = formatFlockResultShareMessage(15, 20, 'Dutch Birders', url, '#3 of 12');
    expect(withRank).toContain('15/20');
    expect(withRank).toContain('#3 of 12');
    expect(withRank).toContain(url);

    const withoutRank = formatFlockResultShareMessage(10, 20, 'Dutch Birders', url);
    expect(withoutRank).not.toContain('ranked');
    expect(withoutRank).toContain('10/20');
  });

  it('builds web paths and absolute URLs', () => {
    expect(getFlocksPath()).toBe('/flocks/list');
    expect(getFlocksIntroPath()).toBe('/flocks/intro');
    expect(getFlocksCreatePath()).toBe('/flocks/create');
    expect(getFlocksJoinPath()).toBe('/flocks/join');
    expect(getFlockDetailPath('my-club')).toBe('/flocks/my-club');
    expect(getFlockMembersPath('my-club')).toBe('/flocks/my-club/members');
    expect(getFlockInvitePath('my-club')).toBe('/flocks/my-club/invite');
    expect(getFlockLeaderboardPath('my-club', 9)).toBe(
      '/flocks/my-club/challenges/9/leaderboard'
    );
    expect(getFlockHistoryPath('abcToken')).toBe('/flocks/c/abcToken/history/');
    expect(getFlockInviteWebPath('tok')).toBe('/join/flock/tok/web');
    expect(getFlockResultPath('res')).toBe('/flocks/results/res');
    expect(buildFlockInviteWebUrl('tok', 'https://birdr.pro')).toBe(
      'https://birdr.pro/join/flock/tok/web'
    );
    expect(buildFlockResultWebUrl('res', 'https://birdr.pro/')).toBe(
      'https://birdr.pro/flocks/results/res'
    );
  });
});

describe('flocks play context', () => {
  beforeEach(() => {
    clearFlockPlayContext();
  });

  afterEach(() => {
    clearFlockPlayContext();
  });

  it('stores and clears flock play context in sessionStorage', () => {
    expect(getFlockPlayContext()).toBeNull();
    setFlockPlayContext({ flockSlug: 'dutch-birders', challengeId: 42 });
    expect(getFlockPlayContext()).toEqual({
      flockSlug: 'dutch-birders',
      challengeId: 42,
    });
    clearFlockPlayContext();
    expect(getFlockPlayContext()).toBeNull();
  });
});

describe('flocks i18n keys', () => {
  it.each(FLOCKS_I18N_KEYS)('includes %s in en and nl', (key) => {
    expect(enMessages).toHaveProperty(key);
    expect(nlMessages).toHaveProperty(key);
    expect(typeof (enMessages as Record<string, string>)[key]).toBe('string');
    expect(typeof (nlMessages as Record<string, string>)[key]).toBe('string');
    expect((enMessages as Record<string, string>)[key].length).toBeGreaterThan(0);
    expect((nlMessages as Record<string, string>)[key].length).toBeGreaterThan(0);
  });
});
