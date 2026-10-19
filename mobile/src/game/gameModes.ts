/**
 * Gradual disclosure of game modes: new players see one big "Start a game" button and the
 * Country Challenge, with Survival / National league / Flocks as small tiles. After
 * EXPERIENCED_AFTER finished games (or when they choose "Show all game modes") those become
 * full cards and the menus show their extras. Modes a player already uses always stay full.
 * Same rules as the web app (app/src/core/game-modes.ts).
 */

export const EXPERIENCED_AFTER = 3;

export const SHOW_ALL_MODES_STORAGE_KEY = 'birdr-show-all-modes';
export const GAMES_PLAYED_STORAGE_KEY = 'birdr-games-played';
export const PLAYED_SURVIVAL_STORAGE_KEY = 'birdr-played-survival';
export const MODES_UNLOCK_SEEN_STORAGE_KEY = 'birdr-modes-unlock-seen';

export type ModeSize = 'full' | 'tile';

export type ModeVisibilityInput = {
  gamesPlayed: number;
  showAll: boolean;
  inLeague: boolean;
  inFlock: boolean;
  /** Country Challenge in progress (always a normal card; kept for parity with the plan). */
  hasJourney?: boolean;
  playedSurvival: boolean;
  isAuthenticated?: boolean;
  /** One-time "unlocked" banner already dismissed or shown. */
  unlockSeen?: boolean;
};

export type ModeVisibility = {
  stage: 'beginner' | 'full';
  league: ModeSize;
  survival: ModeSize;
  /** Full once modes are disclosed, or straight away when you are in a flock. */
  flock: ModeSize;
  /** Extra items in the menus (leaderboards, tricky birds, review media, …). */
  showMenuExtras: boolean;
  /** Small "More ways to play" tiles exist. */
  hasTiles: boolean;
  /** Show the one-time "New game modes unlocked" banner. */
  showUnlockBanner: boolean;
};

export function modeVisibility(input: ModeVisibilityInput): ModeVisibility {
  const experienced = input.gamesPlayed >= EXPERIENCED_AFTER;
  const full = experienced || input.showAll;
  const league: ModeSize = full || input.inLeague ? 'full' : 'tile';
  const survival: ModeSize = full || input.playedSurvival ? 'full' : 'tile';
  const flock: ModeSize = full || input.inFlock ? 'full' : 'tile';
  return {
    stage: full ? 'full' : 'beginner',
    league,
    survival,
    flock,
    showMenuExtras: full,
    hasTiles: league === 'tile' || survival === 'tile' || flock === 'tile',
    // Only an earned unlock is celebrated; flipping the switch yourself needs no banner.
    showUnlockBanner: experienced && !input.unlockSeen,
  };
}

/** Parse a stored games-played count; anything invalid is 0. */
export function parseGamesPlayed(value: string | null | undefined): number {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
}
