import { EXPERIENCED_AFTER, modeVisibility } from '../core/game-modes';

const beginner = { gamesPlayed: 0, showAll: false, inLeague: false, inFlock: false, playedSurvival: false };

describe('modeVisibility', () => {
  it('keeps a new player simple', () => {
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

  it('shows modes you already use full size', () => {
    const v = modeVisibility({ ...beginner, inLeague: true, inFlock: true, playedSurvival: true });
    expect([v.league, v.survival, v.flock]).toEqual(['full', 'full', 'full']);
    expect(v.stage).toBe('beginner');
    expect(v.showMenuExtras).toBe(false);
  });

  it(`unlocks after ${EXPERIENCED_AFTER} finished games, with a one-time banner`, () => {
    const v = modeVisibility({ ...beginner, gamesPlayed: EXPERIENCED_AFTER });
    expect(v.stage).toBe('full');
    expect([v.league, v.survival]).toEqual(['full', 'full']);
    expect(v.showMenuExtras).toBe(true);
    expect(v.showUnlockBanner).toBe(true);
    expect(modeVisibility({ ...beginner, gamesPlayed: EXPERIENCED_AFTER, unlockSeen: true }).showUnlockBanner).toBe(false);
    expect(modeVisibility({ ...beginner, gamesPlayed: EXPERIENCED_AFTER - 1 }).stage).toBe('beginner');
  });

  it('shows everything full size when you choose to, flocks included', () => {
    const v = modeVisibility({ ...beginner, showAll: true });
    expect([v.league, v.survival, v.flock]).toEqual(['full', 'full', 'full']);
    expect(v.hasTiles).toBe(false);
    expect(v.showUnlockBanner).toBe(false); // chosen, not earned
  });

  it('flocks start as a tile for beginners who are not in one', () => {
    expect(modeVisibility({ ...beginner, gamesPlayed: EXPERIENCED_AFTER - 1 }).flock).toBe('tile');
    expect(modeVisibility({ ...beginner, gamesPlayed: EXPERIENCED_AFTER }).flock).toBe('full');
  });
});
