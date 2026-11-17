/**
 * When to ask for a store rating: on a results screen after a good game, once the player has
 * finished a few games, and at most once per app version. The store decides whether the
 * sheet actually shows (both stores rate-limit it), so this only picks the moment.
 */

export const REVIEW_PROMPT_MIN_GAMES = 3;

/** Share of correct answers that counts as a good game. */
export const REVIEW_PROMPT_GOOD_ACCURACY = 0.7;

/** App version we last asked a rating for. */
export const REVIEW_ASKED_VERSION_STORAGE_KEY = 'birdr-review-asked-version';

/** When (ms since epoch) we last asked, so a long-lived version can be asked again. */
export const REVIEW_ASKED_AT_STORAGE_KEY = 'birdr-review-asked-at';

/**
 * Within one app version, ask again after this many days. The stores decide whether the
 * sheet shows (iOS caps it at three a year), so an extra ask costs a happy player nothing.
 */
export const REVIEW_REASK_AFTER_DAYS = 45;

export function isGoodAccuracy(correct: number, total: number): boolean {
  return total > 0 && correct / total >= REVIEW_PROMPT_GOOD_ACCURACY;
}

export function shouldAskForReview(input: {
  goodResult: boolean;
  gamesPlayed: number;
  appVersion: string | null;
  askedVersion: string | null;
  /** When we last asked (ms since epoch), if known. */
  askedAt?: number | null;
  now?: number;
}): boolean {
  const { goodResult, gamesPlayed, appVersion, askedVersion, askedAt = null, now = Date.now() } = input;
  if (!goodResult || !appVersion) return false;
  if (gamesPlayed < REVIEW_PROMPT_MIN_GAMES) return false;
  if (askedVersion !== appVersion) return true;
  return askedAt != null && now - askedAt >= REVIEW_REASK_AFTER_DAYS * 86_400_000;
}
