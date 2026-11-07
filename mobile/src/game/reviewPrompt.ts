/**
 * When to ask for a store rating: on a results screen after a good game, once the player has
 * finished a few games, and at most once per app version. The store decides whether the
 * sheet actually shows (both stores rate-limit it), so this only picks the moment.
 */

export const REVIEW_PROMPT_MIN_GAMES = 3;

/** Share of correct answers that counts as a good game. */
export const REVIEW_PROMPT_GOOD_ACCURACY = 0.8;

/** App version we last asked a rating for. */
export const REVIEW_ASKED_VERSION_STORAGE_KEY = 'birdr-review-asked-version';

export function isGoodAccuracy(correct: number, total: number): boolean {
  return total > 0 && correct / total >= REVIEW_PROMPT_GOOD_ACCURACY;
}

export function shouldAskForReview(input: {
  goodResult: boolean;
  gamesPlayed: number;
  appVersion: string | null;
  askedVersion: string | null;
}): boolean {
  const { goodResult, gamesPlayed, appVersion, askedVersion } = input;
  if (!goodResult || !appVersion) return false;
  if (gamesPlayed < REVIEW_PROMPT_MIN_GAMES) return false;
  return askedVersion !== appVersion;
}
