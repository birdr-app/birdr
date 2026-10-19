import { EXPERIENCED_AFTER, modeVisibility, parseGamesPlayed } from '../game/gameModes';
import { translations } from '../i18n/translations';

const beginner = {
  gamesPlayed: 0,
  showAll: false,
  inLeague: false,
  inFlock: false,
  hasJourney: false,
  playedSurvival: false,
  isAuthenticated: false,
};

describe('modeVisibility', () => {
  it('shows tiles and no menu extras to a fresh guest', () => {
    expect(modeVisibility(beginner)).toEqual({
      stage: 'beginner',
      league: 'tile',
      survival: 'tile',
      flock: 'tile',
      showMenuExtras: false,
      hasTiles: true,
      showUnlockBanner: false,
    });
  });

  it('keeps modes the player already uses as full cards', () => {
    const v = modeVisibility({ ...beginner, isAuthenticated: true, inLeague: true, inFlock: true, playedSurvival: true });
    expect(v.stage).toBe('beginner');
    expect(v.league).toBe('full');
    expect(v.survival).toBe('full');
    expect(v.flock).toBe('full');
    expect(v.hasTiles).toBe(false);
    expect(v.showMenuExtras).toBe(false);
  });

  it('switches to the full stage at the threshold and celebrates once', () => {
    expect(modeVisibility({ ...beginner, gamesPlayed: EXPERIENCED_AFTER - 1 }).stage).toBe('beginner');
    const v = modeVisibility({ ...beginner, gamesPlayed: EXPERIENCED_AFTER });
    expect(v.stage).toBe('full');
    expect(v.league).toBe('full');
    expect(v.survival).toBe('full');
    expect(v.showMenuExtras).toBe(true);
    expect(v.showUnlockBanner).toBe(true);
    expect(modeVisibility({ ...beginner, gamesPlayed: 5, unlockSeen: true }).showUnlockBanner).toBe(false);
  });

  it('shows everything when the player chooses to, without a banner', () => {
    const v = modeVisibility({ ...beginner, showAll: true });
    expect(v.stage).toBe('full');
    expect(v.league).toBe('full');
    expect(v.survival).toBe('full');
    expect(v.showMenuExtras).toBe(true);
    expect(v.showUnlockBanner).toBe(false);
  });

  it('makes flocks big once modes are disclosed, like league and survival', () => {
    expect(modeVisibility({ ...beginner, gamesPlayed: 2 }).flock).toBe('tile');
    expect(modeVisibility({ ...beginner, gamesPlayed: 10 }).flock).toBe('full');
    expect(modeVisibility({ ...beginner, showAll: true }).flock).toBe('full');
    expect(modeVisibility({ ...beginner, gamesPlayed: 10 }).hasTiles).toBe(false);
    expect(modeVisibility({ ...beginner, inFlock: true }).flock).toBe('full');
  });
});

describe('parseGamesPlayed', () => {
  it('reads stored counts defensively', () => {
    expect(parseGamesPlayed('4')).toBe(4);
    expect(parseGamesPlayed(null)).toBe(0);
    expect(parseGamesPlayed('abc')).toBe(0);
    expect(parseGamesPlayed('-2')).toBe(0);
  });
});

describe('game modes i18n', () => {
  const keys = ['more_ways_to_play', 'show_all_game_modes', 'show_all_game_modes_hint', 'game_modes_unlocked'];

  it('has every key in every locale', () => {
    for (const [locale, catalog] of Object.entries(translations)) {
      for (const key of keys) {
        expect([locale, key, typeof catalog[key]]).toEqual([locale, key, 'string']);
      }
    }
  });

  it('translates them beyond English', () => {
    for (const [locale, catalog] of Object.entries(translations)) {
      if (locale === 'en') continue;
      expect([locale, catalog.show_all_game_modes]).not.toEqual([locale, translations.en.show_all_game_modes]);
    }
  });
});
