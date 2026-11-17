export const PRACTICE_JOKERS = 2;
/** @deprecated Use PRACTICE_JOKERS */
export const PAIR_PRACTICE_JOKERS = PRACTICE_JOKERS;

export type JokerProgressResult = 'open' | 'correct' | 'joker' | 'incorrect';

export type SessionAnswer = {
  sequence: number;
  correct: boolean;
};

export function countWrongAnswers(
  answers: SessionAnswer[],
  pending?: SessionAnswer | null,
): number {
  let count = answers.filter((a) => !a.correct).length;
  if (pending && !pending.correct && !answers.some((a) => a.sequence === pending.sequence)) {
    count += 1;
  }
  return count;
}

export function remainingJokers(
  totalJokers: number,
  answers: SessionAnswer[],
  pending?: SessionAnswer | null,
): number {
  return Math.max(0, totalJokers - countWrongAnswers(answers, pending));
}

/**
 * Union of several answer lists by question sequence; the first list wins when two know the
 * same question. The game's scores only refresh now and then, so the screen also remembers
 * the results it has seen itself and merges both.
 */
export function mergeSessionAnswers(...lists: SessionAnswer[][]): SessionAnswer[] {
  const bySequence = new Map<number, SessionAnswer>();
  lists.forEach((list) =>
    list.forEach((a) => {
      if (!bySequence.has(a.sequence)) bySequence.set(a.sequence, a);
    }),
  );
  return Array.from(bySequence.values()).sort((a, b) => a.sequence - b.sequence);
}

/** More wrong answers than jokers: the practice quiz is not passed (the player may still finish it). */
export function practiceFailed(
  totalJokers: number,
  answers: SessionAnswer[],
  pending?: SessionAnswer | null,
): boolean {
  return countWrongAnswers(answers, pending) > totalJokers;
}

export function sessionAnswersFromGameScores(
  scores: Array<{ name?: string; answers?: Array<{ sequence?: number; correct?: boolean }> }> | undefined,
  playerName: string | undefined,
): SessionAnswer[] {
  const scoreRow = scores?.find((s) => s.name === playerName);
  return (scoreRow?.answers ?? [])
    .map((a) => ({
      sequence: Number(a.sequence ?? 0),
      correct: !!a.correct,
    }))
    .filter((a) => a.sequence > 0);
}
