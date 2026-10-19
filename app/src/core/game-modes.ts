/**
 * Gradual disclosure of game modes: new players see one big "Start a game" button and the
 * Country Challenge, with Survival / National league / Flocks as small tiles. After
 * EXPERIENCED_AFTER finished games (or when they choose "Show all game modes") those become
 * full cards and the menus show their extras. Modes a player already uses always stay full.
 */

export const EXPERIENCED_AFTER = 3;

export type ModeSize = 'full' | 'tile';

export type ModeVisibilityInput = {
  gamesPlayed: number;
  showAll: boolean;
  inLeague: boolean;
  inFlock: boolean;
  playedSurvival: boolean;
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
  /** Small "More ways to play" tiles exist and the "Show all game modes" link applies. */
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

// --- Local storage (guests, and instant updates before the server catches up) ---

const SHOW_ALL_KEY = 'birdr-show-all-modes';
const GAMES_PLAYED_KEY = 'birdr-games-played';
const COUNTED_GAMES_KEY = 'birdr-games-counted';
const UNLOCK_SEEN_KEY = 'birdr-modes-unlock-seen';
export const GAME_MODES_EVENT = 'birdr-game-modes-changed';

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
  try {
    window.dispatchEvent(new Event(GAME_MODES_EVENT));
  } catch {
    /* ignore */
  }
}

export function readStoredShowAll(): boolean {
  return read(SHOW_ALL_KEY) === '1';
}

export function writeStoredShowAll(value: boolean): void {
  write(SHOW_ALL_KEY, value ? '1' : '0');
}

export function readLocalGamesPlayed(): number {
  const n = Number(read(GAMES_PLAYED_KEY));
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
}

/** Count a finished game once (by token), so the unlock happens without a server round trip. */
export function recordGameFinished(gameToken: string | null | undefined, serverCount = 0): void {
  if (!gameToken) return;
  let counted: string[] = [];
  try {
    counted = JSON.parse(read(COUNTED_GAMES_KEY) || '[]');
  } catch {
    counted = [];
  }
  if (!Array.isArray(counted)) counted = [];
  if (counted.includes(gameToken)) return;
  write(COUNTED_GAMES_KEY, JSON.stringify([...counted, gameToken].slice(-50)));
  write(GAMES_PLAYED_KEY, String(Math.max(readLocalGamesPlayed(), serverCount) + 1));
}

export function readUnlockSeen(): boolean {
  return read(UNLOCK_SEEN_KEY) === '1';
}

export function markUnlockSeen(): void {
  write(UNLOCK_SEEN_KEY, '1');
}
