import { REVIEW_PROMPT_MIN_GAMES, isGoodAccuracy, shouldAskForReview } from '../game/reviewPrompt';

const base = {
  goodResult: true,
  gamesPlayed: REVIEW_PROMPT_MIN_GAMES,
  appVersion: '1.70.0',
  askedVersion: null,
};

describe('shouldAskForReview', () => {
  it('asks after a good game once enough games are played', () => {
    expect(shouldAskForReview(base)).toBe(true);
  });

  it('waits until the player has finished a few games', () => {
    expect(shouldAskForReview({ ...base, gamesPlayed: REVIEW_PROMPT_MIN_GAMES - 1 })).toBe(false);
  });

  it('only asks after a good result', () => {
    expect(shouldAskForReview({ ...base, goodResult: false })).toBe(false);
  });

  it('asks at most once per app version', () => {
    expect(shouldAskForReview({ ...base, askedVersion: '1.70.0' })).toBe(false);
    expect(shouldAskForReview({ ...base, askedVersion: '1.69.0' })).toBe(true);
  });

  it('does not ask without a known app version', () => {
    expect(shouldAskForReview({ ...base, appVersion: null })).toBe(false);
  });
});

describe('isGoodAccuracy', () => {
  it('needs 80% correct', () => {
    expect(isGoodAccuracy(8, 10)).toBe(true);
    expect(isGoodAccuracy(7, 10)).toBe(false);
    expect(isGoodAccuracy(0, 0)).toBe(false);
  });
});
