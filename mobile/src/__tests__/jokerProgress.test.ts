import {
  PRACTICE_JOKERS,
  countWrongAnswers,
  mergeSessionAnswers,
  practiceFailed,
  remainingJokers,
} from '../game/jokerProgress';

const right = (sequence: number) => ({ sequence, correct: true });
const wrong = (sequence: number) => ({ sequence, correct: false });

describe('practice jokers', () => {
  it('merges answers by sequence and lets the first list win', () => {
    const server = [right(1), wrong(2)];
    const seen = [wrong(2), right(3)];
    expect(mergeSessionAnswers(server, seen)).toEqual([right(1), wrong(2), right(3)]);
    expect(mergeSessionAnswers([wrong(2)], [right(2)])).toEqual([wrong(2)]);
  });

  it('keeps the used hearts after the next question starts', () => {
    // Question 1 was answered wrong; the screen remembers it although the game scores are stale.
    const remembered = mergeSessionAnswers([], [wrong(1)]);
    expect(remainingJokers(PRACTICE_JOKERS, remembered, null)).toBe(1);
  });

  it('fails only with more wrong answers than jokers', () => {
    const two = [wrong(1), right(2), wrong(3)];
    expect(countWrongAnswers(two)).toBe(2);
    expect(practiceFailed(PRACTICE_JOKERS, two)).toBe(false);
    expect(practiceFailed(PRACTICE_JOKERS, two, wrong(4))).toBe(true);
    expect(practiceFailed(PRACTICE_JOKERS, [...two, wrong(4)])).toBe(true);
    expect(practiceFailed(PRACTICE_JOKERS, two, right(4))).toBe(false);
  });
});
